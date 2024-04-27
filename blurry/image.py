"All image processing functionality"

# Standard library imports
import datetime
import functools
import hashlib
import json
import lzma
import os.path
import shutil
import tempfile

# 3rd party imports
import cv2
import numpy

from PIL import Image, ImageDraw, ImageFilter, ExifTags, TiffImagePlugin

# Package imports
from . import helper
from . import similar as sim

# Image resampling quality
RESAMPLER = Image.Resampling.LANCZOS

BLUR = "blur"
BLURRED = "blurred"
BRIGHTNESS = "brightness"
CONTRAST = "contrast"
DC = "diskcache"
EXIF = "exif"
FACE = "faces"
HASH = "hash"
SIZE = "size"
TIME = "mtime"

@helper.debugclass
class BlurryImage:
    "Main class to handle all image processing"
    blurrydb = None
    img_cache = None

    blurry = None
    sim = None
    dir = None
    files = None

    tempdirs = None
    is_temp = False

    is_rescan = False

    face_model_file = None
    face_config_file = None


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

        # Setup cv2 face detection
        path = os.path.dirname(__file__)
        self.face_model_file = os.path.join(path, "models", "opencv_face_detector_uint8.pb")
        self.face_config_file = os.path.join(path, "models", "opencv_face_detector.pbtxt")

        self.init_cache()
        self.read_images()

    def __del__(self):
        for directory in self.tempdirs.values():
            # Delete any temp directories
            shutil.rmtree(directory, ignore_errors=True)

    # Image info caching

    def init_cache(self):
        "Load image cache from disk for this directory if present"
        self.img_cache = {}

        self.blurrydb = os.path.join(self.dir, "blurry.db")
        if os.path.exists(self.blurrydb):
            try:
                with lzma.open(self.blurrydb, "r") as cdb:
                    self.img_cache = json.load(cdb)
            except json.decoder.JSONDecodeError:
                pass

            # Remove any non-existent files from cache
            self.clean_cache()

    def save_cache(self):
        "Save directory cache in memory to disk"
        self.img_cache[TIME] = os.path.getmtime(self.dir)
        try:
            with lzma.open(self.blurrydb, "wt") as cdb:
                json.dump(self.img_cache, cdb)
        except PermissionError:
            pass
        del self.img_cache[TIME]

    def clean_cache(self):
        "Remove any non-existent files from cache"
        for file in list(self.img_cache.keys()):
            if file == TIME:
                continue
            if not os.path.exists(os.path.join(self.dir, file)):
                # Remove file from similar files
                for file1 in self.img_cache[file][sim.SIMILAR]:
                    if file in self.img_cache[file1][sim.SIMILAR]:
                        del self.img_cache[file1][sim.SIMILAR][file]

                # Remove file from image cache
                del self.img_cache[file]

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

            if flag in ["all", "db"]:
                self.img_cache = {}
                cleared = True

            if flag in ["all", DC]:
                self.blurry.cache[DC].clear()

            if flag in [BLUR, BRIGHTNESS, CONTRAST, EXIF, FACE, sim.SIMILAR]:
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
    def brightness(self, gray):
        "Return the RMS to gauge brightness"
        return numpy.sqrt(numpy.mean(gray ** 2))

    @helper.timeit
    def contrast(self, gray):
        "Return contrast (standard deviation) of image"
        return numpy.std(gray)

    # Image info

    @helper.timeit
    def faces(self, image):
        "Detect faces using OpenCV DNN"
        net = cv2.dnn.readNetFromTensorflow(self.face_model_file, self.face_config_file)

        # Create blob from the image
        (h, w) = image.shape[:2]
        blob = cv2.dnn.blobFromImage(image, 1.0, (300, 300), [104, 117, 123], False, False)

        # Detect faces
        net.setInput(blob)
        detections = net.forward()
        faces = []
        for i in range(0, detections.shape[2]):
            confidence = detections[0, 0, i, 2]
            if confidence > 0.5:
                box = detections[0, 0, i, 3:7] * numpy.array([w, h, w, h])
                faces.append([int(val) for val in box])

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

        # Fallback on file creation date if no EXIF data
        return os.path.getctime(os.path.join(self.dir, file))

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

    def check_sim_rescan(self):
        "Check if similarity rescan is required - new files added or similarity missing in cache"
        is_sim_rescan = False
        for file in self.files:
            if file not in self.img_cache or sim.SIMILAR not in self.img_cache[file]:
                is_sim_rescan = True
                break
        return is_sim_rescan

    @helper.timeit
    def read_file_info(self, file):
        "Load image file info from disk"

        # Get path to current file
        filepath = os.path.join(self.dir, file)

        # File modification time
        mtime = os.path.getmtime(filepath)
        if file not in self.img_cache or mtime != self.img_cache[file][TIME]:
            # Not in cache or file has changed - reinit
            self.img_cache[file] = {TIME: mtime}

        # File size
        size = os.path.getsize(filepath)
        if SIZE not in self.img_cache[file]:
            # Size not in cache
            self.img_cache[file][SIZE] = size
        elif self.img_cache[file][SIZE] != size:
            # File has changed - reinit
            self.img_cache[file] = {TIME: mtime, SIZE: size}

        return filepath

    @helper.timeit
    def read_images(self):
        "Read every image from disk and generate info"

        # Skip for temp directories
        if self.is_temp:
            return

        # Remove dir time since img_cache is dict of files
        if TIME in self.img_cache:
            dtime = self.img_cache[TIME]
            del self.img_cache[TIME]
        else:
            dtime = 0

        # Clear cache if requested
        is_clear_cache = self.clear_cache()

        # Check if rescan of files is required
        is_sim_rescan = self.check_sim_rescan()

        self.is_rescan = dtime < os.path.getmtime(self.dir) or is_clear_cache or is_sim_rescan

        if self.is_rescan:
            # Directory changed - files added/removed/renamed
            # Some cache elements cleared
            # Similarity rescan required

            # Initialize progress bar - get info + find similar
            self.blurry.gui.setup_progress(len(self.files) * 2)

            # Load all files to get info
            self.is_rescan = True
            helper.parallelize((self.read_image, self.files),
                               final=self.blurry.gui.update_progress,
                               executor = self.blurry.executor)
            self.is_rescan = False

            # Find similar
            self.save_cache()
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
    def read_image(self, file):
        "Read image from disk and get info"

        # Load image file if not already
        filepath = self.read_file_info(file)

        # Open as PIL image
        with open(filepath, "rb") as fobj:
            img_pil = Image.open(fobj)
            img_pil.load()

        # Get info for the image
        img_pil = self.get_info(file, img_pil)

        return img_pil

    @helper.timeit
    def get_file_hash(self, file):
        "Generate file hash based on mtime, size and EXIF data"
        key = "%d-%d-%s" % (self.img_cache[file][TIME], self.img_cache[file][SIZE], json.dumps(self.img_cache[file][EXIF], sort_keys=True))
        return hashlib.sha1(key.encode()).hexdigest()

    @helper.timeit
    def get_info(self, file, img_pil):
        "Get all image info - file, EXIF, blurriness, brightness, contrast, histogram, etc."

        # Get EXIF
        if EXIF not in self.img_cache[file]:
            self.img_cache[file][EXIF] = self.exif(img_pil)

        # Generate unique hash
        if HASH not in self.img_cache[file]:
            self.img_cache[file][HASH] = self.get_file_hash(file)

        # Reorient if required
        img_pil = self.reorient(file, img_pil)

        # Done for temp directories
        if self.is_temp:
            return img_pil

        if self.is_rescan:
            ops = []
            if FACE not in self.img_cache[file]:
                ops.append(self.faces)

            key = f"{self.img_cache[file][HASH]}_{sim.SIMDEFAULT}"
            if key in self.blurry.cache[DC]:
                # Load similarity metadata from cache
                self.sim.sim_cache[file] = self.blurry.cache[DC][key]
            else:
                # Regenerate similarity metadata
                ops.append(self.sim.simop)

            if len(ops) != 0:
                # Convert into opencv format
                image = cv2.cvtColor(numpy.array(img_pil), cv2.COLOR_RGB2BGR)

                # Get all image info
                results = {}
                helper.parallelize((ops, image), results=results)

            # Get faces
            if FACE not in self.img_cache[file]:
                self.img_cache[file][FACE] = results[self.faces]

            # Get similarity metadata
            if self.sim.simop in results:
                # Load into image cache
                self.sim.sim_cache[file] = results[self.sim.simop]
                # Save similarity metadata to disk cache
                self.blurry.cache[DC][key] = self.sim.sim_cache[file]
        return img_pil

    def blur_image(self, file):
        "Mark image as blurred or unblurred"
        if BLURRED in self.img_cache[file]:
            del self.img_cache[file][BLURRED]
        else:
            self.img_cache[file][BLURRED] = True

    def compare_ratings(self, files):
        "Get relative comparison of blurriness, brightness and contrast for specified images"
        sharpness = {}
        brightness = {}
        contrast = {}
        for file in files:
            if BLUR in self.img_cache[file]:
                sharpness[file] = self.img_cache[file][BLUR]
            if BRIGHTNESS in self.img_cache[file]:
                brightness[file] = self.img_cache[file][BRIGHTNESS]
            if CONTRAST in self.img_cache[file]:
                contrast[file] = self.img_cache[file][CONTRAST]

        # Scale values from 0-100 relative to maximum value
        for value in [sharpness, brightness, contrast]:
            if len(value) != 0:
                maxvalue = max(value.values())
                for key, val in value.items():
                    value[key] = (val / maxvalue) * 100 if maxvalue != 0 else 0

        return sharpness, brightness, contrast

    def get_faces(self, file):
        "Return all faces in the image if any"
        return self.img_cache[file].get(FACE, [])

    def extract_faces(self, file):
        "Create a temp directory with faces from specified image"
        if file in self.tempdirs:
            return self.tempdirs[file]

        faces = self.get_faces(file)
        if len(faces) != 0:
            hash = self.img_cache[file][HASH]
            directory = tempfile.mkdtemp(prefix=f"blurry-{hash}-faces-")
            img_pil = self.read_image(file)
            _, ext = os.path.splitext(file)
            for i, face in enumerate(self.img_cache[file][FACE]):
                cimg = img_pil.crop(tuple(face))
                cimg.save(os.path.join(directory, f"{hash}-{i:04}.{ext}"))

            self.tempdirs[file] = directory
            return directory
        return None

    def update_image(self, file, img_pil):
        "Update image with face info and user settings"

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
        if BLURRED in self.img_cache[file]:
            img_pil = self.blurimage(img_pil)

        return img_pil

    def get_similar(self, file):
        "Return all images similar to the specified file"
        return self.sim.get_similar(file)

def get_supported_exts():
    "Get supported image formats from PIL"
    return [ext for ext, fmt in Image.registered_extensions().items() if fmt in Image.OPEN]

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
