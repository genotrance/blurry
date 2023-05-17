"All image processing functionality"

# Standard library imports
import datetime
import functools
import json
import lzma
import mmap
import os.path
import shutil
import sys
import tempfile

# 3rd party imports
import cv2
import dlib
import numpy

from PIL import Image, ImageDraw, ImageFilter, ExifTags, TiffImagePlugin

# Package imports
from . import helper
from . import similar as sim

# Image resampling quality
RESAMPLER = Image.Resampling.BILINEAR

BLUR = "blur"
CONTRAST = "contrast"
EXIF = "exif"
FACE = "faces"
TIME = "mtime"

@helper.debugclass
class BlurryImage:
    "Main class to handle all image processing"
    cachedb = None
    img_cache = None
    mmap_cache = None

    blurry = None
    sim = None
    dir = None
    files = None

    tempdirs = None
    is_temp = False

    def __init__(self, blurry, directory, files):
        self.blurry = blurry
        self.dir = directory
        self.files = files
        self.tempdirs = {}

        if self.blurry.parent is not None:
            if self.dir in self.blurry.parent.image.tempdirs.values():
                # Don't process images in temp dir
                self.is_temp = True

        self.sim = sim.Similar(self)

        self.init_cache()
        self.read_images()

    def __del__(self):
        self.mmap_cache = {}

        for directory in self.tempdirs.values():
            # Delete any temp directories
            shutil.rmtree(directory)

    # Image info caching

    def init_cache(self):
        "Load image cache from disk for this directory if present"
        self.mmap_cache = {}
        self.img_cache = {}

        homedir = os.path.expanduser("~")
        self.cachedb = os.path.join(homedir, ".blurry", "cache.db")
        if os.path.exists(self.cachedb):
            cache = {}
            try:
                with lzma.open(self.cachedb, "r") as cdb:
                    cache = json.load(cdb)
            except json.decoder.JSONDecodeError:
                pass
            if self.dir in cache:
                # Load only this directory from cache
                self.img_cache = cache[self.dir]

    def save_cache(self):
        "Save directory cache in memory to disk"
        self.img_cache[TIME] = os.path.getmtime(self.dir)
        if os.path.exists(self.cachedb):
            cdata = {}
            try:
                with lzma.open(self.cachedb, "r") as cdb:
                    cdata = json.load(cdb)
            except json.decoder.JSONDecodeError:
                pass
            cdata[self.dir] = self.img_cache
        else:
            os.makedirs(os.path.dirname(self.cachedb), exist_ok=True)
            cdata = {self.dir: self.img_cache}
        with lzma.open(self.cachedb, "wt") as cdb:
            json.dump(cdata, cdb)

    def clear_cache(self):
        "Clear specified fields from cache"
        cleared = False
        drop = []
        for i, flag in enumerate(self.blurry.flags):
            if flag.startswith("--clear-"):
                flag = flag[len("--clear-"):]
                drop.append(i)
            else:
                continue

            if flag == "all":
                self.img_cache = {}
                cleared = True
            elif flag in [BLUR, CONTRAST, EXIF, FACE, sim.SIMILAR]:
                cleared = True
                for file in self.img_cache:
                    if flag in self.img_cache[file]:
                        del self.img_cache[file][flag]

        return cleared

    # Detect blurriness

    @helper.timeit
    def sobel(self, gray):
        "Return the standard deviation of sobel magnitude to gauge blurriness"

        # Calculate the gradient magnitude using the Sobel operator
        grad_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        grad_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        gradient = cv2.magnitude(grad_x, grad_y)

        # Calculate the standard deviation of the gradient magnitude
        return gradient.std()

    @helper.timeit
    def laplacian(self, gray):
        "Return the variance of Laplacian to gauge blurriness"
        return cv2.Laplacian(gray, cv2.CV_64F).var()

    @helper.timeit
    def mean_spectrum(self, gray):
        "Return the mean spectrum to gauge blurriness"
        dft = cv2.dft(numpy.float32(gray), flags=cv2.DFT_COMPLEX_OUTPUT)
        dft_shift = numpy.fft.fftshift(dft)

        absval = cv2.magnitude(dft_shift[:, :, 0], dft_shift[:, :, 1])
        magnitude_spectrum = 20 * numpy.log(absval, where=absval > 0)

        # Compute the mean of the magnitude spectrum
        return numpy.mean(magnitude_spectrum)

    @helper.timeit
    def contrast(self, gray):
        "Return contrast (standard deviation) of image"
        return numpy.std(gray)

    # Image info

    @helper.timeit
    def faces(self, gray):
        "Detect faces in the image"
        dets = dlib.get_frontal_face_detector()(gray, 1)
        faces = []
        for face in dets:
            faces.append([face.left(), face.top(), face.right(), face.bottom()])
        return faces

    @helper.timeit
    def exif(self, img_pil):
        "Get EXIF information from image"
        exif = img_pil.getexif()
        exif_dict = {}
        for key, val in exif.items():
            if key in ExifTags.TAGS:
                exif_dict[ExifTags.TAGS[key]] = cast(val)
        return exif_dict

    @functools.lru_cache
    def get_date(self, file):
        "Get EXIF date as timestamp"
        for key, val in self.img_cache[file][EXIF].items():
            if key.startswith("DateTime"):
                return datetime.datetime.strptime(val, "%Y:%m:%d %H:%M:%S").timestamp()

        return 0

    def reorient(self, file, img_pil):
        "Get EXIF orientation info and transpose image if needed"

        # Get the orientation information from the Exif data
        orientation = int(self.img_cache[file].get(EXIF, {}).get("Orientation", 1))

        # PIL rotates anti-clockwise, EXIF provides clockwise orientation
        if orientation == 1:
            # 1 = Horizontal (normal)
            return img_pil
        elif orientation == 2:
            # 2 = Mirror horizontal
            return img_pil.transpose(Image.FLIP_LEFT_RIGHT)
        elif orientation == 3:
            # 3 = Rotate 180
            return img_pil.rotate(180, expand=True)
        elif orientation == 4:
            # 4 = Mirror vertical
            return img_pil.transpose(Image.FLIP_TOP_BOTTOM)
        elif orientation == 5:
            # 5 = Mirror horizontal and rotate 270 CW
            return img_pil.transpose(Image.FLIP_LEFT_RIGHT).rotate(90, expand=True)
        elif orientation == 6:
            # 6 = Rotate 90 CW
            return img_pil.rotate(270, expand=True)
        elif orientation == 7:
            # 7 = Mirror horizontal and rotate 90 CW
            return img_pil.transpose(Image.FLIP_LEFT_RIGHT).rotate(270, expand=True)
        elif orientation == 8:
            # 8 = Rotate 270 CW
            return img_pil.rotate(90, expand=True)

        return img_pil

    def blackwhite(self, img_pil):
        "Convert image to Black & White"
        return img_pil.convert("L")

    def blurimage(self, img_pil):
        "Blur image"
        return img_pil.filter(ImageFilter.GaussianBlur(radius = 25))

    # Internal

    @helper.timeit
    def read_file(self, file):
        "Load image file from disk"

        # Already loaded
        if file in self.mmap_cache:
            return

        # Get path to current file
        filepath = os.path.join(self.dir, file)

        # mmap file for fast access and OS caching
        with open(filepath, "rb") as fobj:
            self.mmap_cache[file] = mmap.mmap(fobj.fileno(), length = 0, access = mmap.ACCESS_READ)

        mtime = os.path.getmtime(filepath)
        if file not in self.img_cache or mtime > self.img_cache[file][TIME]:
            # Not in cache or file has changed - init
            self.img_cache[file] = {TIME: mtime}

    def read_images(self):
        "Read every image from disk and generate info"

        # Remove dir time since img_cache is dict of files
        if TIME in self.img_cache:
            dtime = self.img_cache[TIME]
            del self.img_cache[TIME]
        else:
            dtime = 0

        if self.is_temp:
            return

        if self.clear_cache() or dtime < os.path.getmtime(self.dir):
            # Some cache elements cleared
            # Directory changed - files added/removed/renamed

            self.blurry.gui.setup_progress(len(self.files) * 2)

            # Generate all info
            helper.parallelize((self.read_image, self.files),
                               final=self.blurry.gui.update_progress)

            # Find similar
            self.sim.find_similar()

            # Save cache
            self.save_cache()
            self.blurry.gui.close_progress()

    def diff_dates(self, file1, file2):
        "Compare two dates and return absolute diff"
        date1 = self.get_date(file1)
        date2 = self.get_date(file2)

        return abs(date1 - date2)

    # API

    @helper.timeit
    def read_image(self, file, is_blurred = False):
        "Read image from disk and get info"

        # Load image file if not already
        self.read_file(file)

        # Open as PIL image
        img_pil = Image.open(self.mmap_cache[file])

        # Get info for the image
        img_pil = self.get_info(file, img_pil)

        # Draw red boxes around faces
        if self.blurry.is_facehighlight:
            if FACE in self.img_cache[file]:
                for (ltx, lty, rbx, rby) in self.img_cache[file][FACE]:
                    draw = ImageDraw.Draw(img_pil)
                    draw.rectangle([ltx, lty, rbx, rby], outline="red", width=4)

        # Set to B&W if needed
        if self.blurry.is_blackwhite:
            img_pil = self.blackwhite(img_pil)

        # Blur image if needed
        if is_blurred:
            img_pil = self.blurimage(img_pil)

        return img_pil

    @helper.timeit
    def get_info(self, file, img_pil):
        "Get all image info - file, EXIF, blurriness, contrast, histogram, etc."

        # Get EXIF
        if EXIF not in self.img_cache[file]:
            self.img_cache[file][EXIF] = self.exif(img_pil)

        # Reorient if required
        img_pil = self.reorient(file, img_pil)

        ops = []
        if BLUR not in self.img_cache[file]:
            ops.extend([self.sobel, self.laplacian, self.mean_spectrum])
        if CONTRAST not in self.img_cache[file]:
            ops.append(self.contrast)
        if FACE not in self.img_cache[file]:
            ops.append(self.faces)
        if sim.SIMILAR not in self.img_cache[file]:
            ops.append(self.sim.simop)

        if not self.is_temp and len(ops) != 0:
            # Convert into opencv format
            image = cv2.cvtColor(numpy.array(img_pil), cv2.COLOR_RGB2BGR)
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

            # Get all image info
            results = {}
            helper.parallelize((ops, gray), results=results)

            # Get blurriness
            if BLUR not in self.img_cache[file]:
                sobel = results[self.sobel]
                laplacian = results[self.laplacian]
                mean_spectrum = results[self.mean_spectrum]
                self.img_cache[file][BLUR] = round(sobel * laplacian * mean_spectrum / 1000, 2)

            # Get contrast
            if CONTRAST not in self.img_cache[file]:
                self.img_cache[file][CONTRAST] = round(results[self.contrast], 2)

            # Get faces
            if FACE not in self.img_cache[file]:
                self.img_cache[file][FACE] = results[self.faces]

            # Get metadata to find similar images
            if sim.SIMILAR not in self.img_cache[file]:
                self.img_cache[file][sim.SIMDEFAULT] = results[self.sim.simop]

        return img_pil

    def compare_ratings(self, files):
        "Get relative comparison of blurriness and contrast for specified images"
        sharpness = {}
        contrast = {}
        for file in files:
            if BLUR in self.img_cache[file]:
                sharpness[file] = self.img_cache[file][BLUR]
            if CONTRAST in self.img_cache[file]:
                contrast[file] = self.img_cache[file][CONTRAST]

        if len(sharpness) != 0:
            # Sharpness %
            maxvalue = max(sharpness.values())
            for key, value in sharpness.items():
                sharpness[key] = (value / maxvalue) * 100 if maxvalue != 0 else 0

        if len(contrast) != 0:
            # Contrast %
            maxvalue = max(contrast.values())
            for key, value in contrast.items():
                contrast[key] = (value / maxvalue) * 100 if maxvalue != 0 else 0

        return sharpness, contrast

    def get_faces(self, file):
        "Return all faces in the image if any"
        return self.img_cache[file].get(FACE, [])

    def extract_faces(self, file):
        "Create a temp directory with faces from specified image"
        if file in self.tempdirs:
            return self.tempdirs[file]

        if len(self.img_cache[file][FACE]) != 0:
            directory = tempfile.mkdtemp(prefix=f"blurry-{file}-")
            img_pil = self.read_image(file)
            for i, face in enumerate(self.img_cache[file][FACE]):
                cimg = img_pil.crop(tuple(face))
                cimg.save(os.path.join(directory, f"{file[:-4]}-{i:04}.jpg"))

            self.tempdirs[file] = directory
            return directory
        return None

    @functools.lru_cache
    def get_similar(self, file):
        "Return all images similar to the specified file"
        return self.sim.get_similar(file)

def cast(value):
    "Cast EXIF data types to JSON supported types"
    # https://github.com/python-pillow/Pillow/issues/6199
    if isinstance(value, TiffImagePlugin.IFDRational):
        return float(value)
    elif isinstance(value, tuple):
        return tuple(cast(tup) for tup in value)
    elif isinstance(value, bytes):
        return value.decode(errors="replace")
    elif isinstance(value, dict):
        for key, val in value.items():
            value[key] = cast(val)
        return value
    else: return value
