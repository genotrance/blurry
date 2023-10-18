"Comparing images to gauge similarity"

# 3rd party imports
import cv2
import numpy

# Package imports
from . import helper

PHASH = "phash"
HISTOGRAM = "histogram"
ORB = "orb"
SIFT = "sift"
SURF = "surf"
SIMILAR = "similar"

SIMDEFAULT = ORB

DIFFMINUTES = 2
DIFFHASH = 20
DIFFHIST = 1
DIFFORB = 96
DIFFSIFT = 98

SIMFILTER = {
    PHASH: DIFFHASH,
    HISTOGRAM: DIFFHIST,
    ORB: DIFFORB,
    SIFT: DIFFSIFT
}

SIMDELTA = {
    PHASH: 1,
    HISTOGRAM: 0.1,
    ORB: 1,
    SIFT: 1
}

SIMMAX = {
    PHASH: 25,
    HISTOGRAM: 1.2,
    ORB: 99,
    SIFT: 99
}

@helper.debugclass
class Similar:
    "Class to handle all image similarity operations"
    image = None
    simop = None
    simcompare = None
    simfilter = None

    def __init__(self, image):
        self.image = image

        # Different methods to detect similarity
        self.simop = {
            PHASH: self.phash,
            HISTOGRAM: self.histogram,
            ORB: self.orb,
            SIFT: self.sift
        }[SIMDEFAULT]

        # Comparing similarity between images
        self.simcompare = {
            PHASH: lambda x, y: numpy.count_nonzero(x != y),
            HISTOGRAM: lambda x, y: cv2.compareHist(x, y, cv2.HISTCMP_CHISQR),
            ORB: self.compare_knn,
            SIFT: self.compare_knn
        }[SIMDEFAULT]

        # Cutoff filter for similarity
        self.simfilter = SIMFILTER[SIMDEFAULT]

    def filterup(self):
        "Increase similarity filter value - loosen"
        self.simfilter = min(self.simfilter + SIMDELTA[SIMDEFAULT], SIMMAX[SIMDEFAULT])

    def filterdown(self):
        "Decrease similarity filter value - tighten"
        self.simfilter = max(self.simfilter - SIMDELTA[SIMDEFAULT], 0)

    @helper.timeit
    def histogram(self, gray):
        "Return normalized histogram for image"

        # Calculate the histograms of the grayscale image
        hist = cv2.calcHist([gray], [0], None, [256], [0, 256])

        # Normalize the histograms
        return cv2.normalize(hist, hist).flatten()

    @helper.timeit
    def phash(self, gray):
        "Calculate phash for image - code from imagehash"
        hash_size = 8
        highfreq_factor = 4
        img_size = hash_size * highfreq_factor
        pixels = cv2.resize(gray, dsize=(img_size, img_size), interpolation=cv2.INTER_AREA)
        dct = cv2.dct(pixels.astype(numpy.float32))
        dctlowfreq = dct[:hash_size, :hash_size]
        med = numpy.median(dctlowfreq)
        diff = dctlowfreq > med
        return diff.flatten()

    @helper.timeit
    def orb(self, gray):
        "Detect ORB features in the image"
        orb = cv2.ORB_create(nfeatures=10000)
        _, descriptors = orb.detectAndCompute(gray, None)
        return descriptors

    @helper.timeit
    def sift(self, gray):
        "Detect SIFT features in the image"
        sift = cv2.SIFT_create(nfeatures=10000)
        _, descriptors = sift.detectAndCompute(gray, None)
        return descriptors

    @helper.timeit
    def find_similar(self):
        "Compare all images to find similar images"
        for file in self.image.files:
            if SIMILAR not in self.image.img_cache[file]:
                self.image.img_cache[file][SIMILAR] = {}
        # Compare every file with files after it in parallel
        helper.parallelize((self.compare_similar, self.image.files),
                           final=self.image.blurry.gui.update_progress)

        for file in self.image.img_cache:
            # Sort results by rating
            if SIMILAR in self.image.img_cache[file]:
                self.image.img_cache[file][SIMILAR] = dict(
                    sorted(self.image.img_cache[file][SIMILAR].items(), key=lambda x: x[1]))

            # Remove similarity metadata - takes too much space
            if SIMDEFAULT in self.image.img_cache[file]:
                del self.image.img_cache[file][SIMDEFAULT]

    @helper.timeit
    def compare_similar(self, file1):
        "Compare file1 with all files after it for similarity"
        index = self.image.files.index(file1)
        for file2 in self.image.files[index:]:
            ret = self.compare_file1_file2(file1, file2)
            if ret is not None:
                # Save similarity results for both files
                self.image.img_cache[file1][SIMILAR][file2] = ret
                self.image.img_cache[file2][SIMILAR][file1] = ret

    def compare_knn(self, des1, des2):
        "Compare two image descriptors using KNN"
        index_params = {}
        if SIMDEFAULT == SIFT:
            index_params = dict(algorithm=0, trees=5) # FLANN_INDEX_KDTREE
        elif SIMDEFAULT == ORB:
            index_params = dict(
                algorithm=6, table_number=6, key_size=12, multi_probe_level=1) # FLANN_INDEX_LSH
        search_params = dict(checks=50)
        knn = cv2.FlannBasedMatcher(index_params, search_params)

        matches = knn.knnMatch(des1, des2, k=2)
        good_matches = 0
        for val in matches:
            if len(val) == 2:
                m, n = val
                if m.distance < 0.7 * n.distance:
                    good_matches += 1
        return 100 - (good_matches / len(matches) * 100) if len(matches) > 0 else 0

    @helper.timeit
    def compare_file1_file2(self, file1, file2):
        "Compare file1 and file2 based on similarity algorithm selected"
        if (file1 == file2 or file2 in self.image.img_cache[file1][SIMILAR] or
            self.image.diff_dates(file1, file2) > 60 * DIFFMINUTES):
            # Same file / already compared / more than 5 minutes apart
            return
        if file1 in self.image.img_cache.get(file2, {}).get(SIMILAR, {}):
            # Already compared before, reuse
            return self.image.img_cache[file2][SIMILAR][file1]
        else:
            # Compare and return results
            return self.simcompare(
                self.image.img_cache[file1][SIMDEFAULT], self.image.img_cache[file2][SIMDEFAULT])

    def get_similar(self, file, visited=None):
        "Return all images similar to the specified file - recursively"

        # No similar files
        if SIMILAR not in self.image.img_cache[file]:
            return []

        if visited is None:
            visited = set()

        visited.add(file)

        similar = set()
        for file2, val in self.image.img_cache[file][SIMILAR].items():
            # Filter out values above the threshold
            if val >= self.simfilter:
                continue
            similar.add(file2)

        for sim in similar.copy():
            if sim not in visited:
                similar.update(self.get_similar(sim, visited))

        # Skip the file itself
        similar.discard(file)

        return similar
