"Test cases for blurry"

import logging
import os
import sys
import unittest

import tkinter as tk

from PIL import Image

import blurry
import gui

NUMIMAGES = 20

def gen(width, height, color, name):
    "Generate an image with specified color and size"
    img = Image.new('RGB', (width, height), color=color)
    img.save(f"{name}.png")

def gendir(numimages):
    "Generate a directory of images for testing"
    directory = f"temp-{numimages}"
    if not os.path.exists(directory):
        os.mkdir(directory)
        os.chdir(directory)
        for i in range(numimages):
            gen(800, 600, (i * 10, i * 5, i * 12), str(i))
        os.chdir("..")
    return os.path.join(os.getcwd(), directory)

class Tests(unittest.TestCase):
    "All test cases for blurry"
    blurry = None
    root = None
    log = None
    dir = None
    pagesize = 8

    # Helpers

    def send(self, key):
        "Send keypress to blurry GUI"
        keysym = gui.KEYMAP[key]
        self.blurry.gui.root.event_generate(keysym)
        if self.blurry.gui.root is not None:
            self.blurry.gui.root.update()

    def send_popup(self, key):
        "Send keypress to popup"
        self.blurry.popups[0].root.event_generate(key)
        if self.blurry.popups[0].root is not None:
            self.blurry.popups[0].root.update()

    def check_highlight(self):
        "Check that the correct image is highlighted"
        count = 0
        hoff = self.blurry.offsets[self.blurry.cursor]
        for widget in self.blurry.gui.root.winfo_children():
            if isinstance(widget, gui.MyLabel):
                if widget.offset == hoff:
                    self.assertEqual(count, self.blurry.cursor)
                    color = gui.COLORCURSOR
                else:
                    color = "black"
                self.assertEqual(widget.cget("highlightbackground"), color)
                count += 1

    # Setup / tear down

    @classmethod
    def setUpClass(self):
        self.log = logging.getLogger("LOG")

        self.dir = gendir(NUMIMAGES)

    def setUp(self, files = None):
        self.root = tk.Tk()
        files = files or [self.dir]
        files.append("--debug")
        blurry.PAGESIZE = self.pagesize
        self.blurry = blurry.Blurry(files, root = self.root, is_allfiles = True, is_testing = True)

    def tearDown(self):
        self.send("Quit")
        self.assertIsNone(self.blurry.gui.root)
        self.blurry = None
        self.root = None

    # Test cases

    def test_bksp(self):
        "End, BackSpace"
        # Backspace one by one
        offsets = list(range(blurry.PAGESIZE))
        # Go to the end of list
        self.send("End")
        for i in range(blurry.PAGESIZE):
            # Number of images matches
            self.assertEqual(len(self.blurry.offsets), blurry.PAGESIZE - i)
            # Order of images matches what we expect
            self.assertEqual(offsets, self.blurry.offsets)
            # Cursor is on the last image
            self.assertEqual(self.blurry.cursor, len(self.blurry.offsets)-1)
            # Correct image is highlighted
            self.check_highlight()
            # Delete image to the left of cursor
            self.send("BackSpace")
            # Remove from expected list
            offsets.pop(len(offsets)-2)

        # One image should remain even if we try to delete
        self.send("BackSpace")
        self.send("BackSpace")
        self.assertEqual(len(self.blurry.offsets), 1)
        self.assertEqual(self.blurry.cursor, 0)
        # Correct image is highlighted
        self.check_highlight()
        # First image should be the last image
        self.assertEqual(self.blurry.offsets[0], blurry.PAGESIZE-1)

    def test_ctrl_bksp(self):
        "Right, BackSpaceToHome"
        moveby = blurry.PAGESIZE // 2

        # Control-Backspace from the middle
        offsets = list(range(blurry.PAGESIZE))
        # Go to the 5th image
        for _ in range(moveby):
            self.send("Right")
            # Correct image is highlighted
            self.check_highlight()
        self.assertEqual(self.blurry.cursor, moveby)

        # Delete all images to the left of cursor
        self.send("BackSpaceToHome")
        # Remove from expected list
        offsets = offsets[moveby:]
        # Number of images matches
        self.assertEqual(len(self.blurry.offsets), blurry.PAGESIZE - moveby)
        # Order of images matches what we expect
        self.assertEqual(offsets, self.blurry.offsets)
        # Correct image is highlighted
        self.check_highlight()
        # Cursor is on the first image
        self.assertEqual(self.blurry.cursor, 0)

        # Images to the right should remain even if we try to delete
        self.send("BackSpaceToHome")
        self.send("BackSpaceToHome")
        # Left with 4 images
        self.assertEqual(len(self.blurry.offsets), blurry.PAGESIZE-moveby)
        # Cursor should be at the first image
        self.assertEqual(self.blurry.cursor, 0)
        # Correct image is highlighted
        self.check_highlight()
        # First image should be the 5th image
        self.assertEqual(self.blurry.offsets[0], blurry.PAGESIZE-moveby)

    def test_ctrl_del(self):
        "Right, DeleteToEnd"
        moveby = blurry.PAGESIZE // 2

        # Control-Delete from the middle
        offsets = list(range(blurry.PAGESIZE))
        # Go to the moveby'th image
        for _ in range(moveby):
            self.send("Right")
        self.assertEqual(self.blurry.cursor, moveby)

        # Delete all images to the right of cursor
        self.send("DeleteToEnd")
        # Remove from expected list
        offsets = offsets[:moveby]
        # Number of images matches
        self.assertEqual(len(self.blurry.offsets), moveby)
        # Order of images matches what we expect
        self.assertEqual(offsets, self.blurry.offsets)
        # Correct image is highlighted
        self.check_highlight()
        # Cursor is on the moveby-1'th image
        self.assertEqual(self.blurry.cursor, moveby-1)

        # Remove two more images
        self.send("DeleteToEnd")
        self.send("DeleteToEnd")
        # Left with moveby-2 or at least 1 image
        self.assertEqual(len(self.blurry.offsets), max(moveby-2, 1))
        # Cursor should be at the 2nd or 1st image
        self.assertEqual(self.blurry.cursor, max(moveby-3, 0))
        # Correct image is highlighted
        self.check_highlight()
        # First image should still be the first one
        self.assertEqual(self.blurry.offsets[0], 0)

    def test_del(self):
        "Delete"
        # Delete one by one
        offsets = list(range(blurry.PAGESIZE))
        for i in range(blurry.PAGESIZE):
            # NUmber of images matches
            self.assertEqual(len(self.blurry.offsets), blurry.PAGESIZE - i)
            # Order of images matches what we expect
            self.assertEqual(offsets, self.blurry.offsets)
            # Cursor is on the first image
            self.assertEqual(self.blurry.cursor, 0)
            # Correct image is highlighted
            self.check_highlight()
            # Delete image at cursor
            self.send("Delete")
            # Remove from expected list
            offsets.pop(0)

        # One image should remain even if we try to delete
        self.send("Delete")
        self.send("Delete")
        self.assertEqual(len(self.blurry.offsets), 1)
        self.assertEqual(self.blurry.cursor, 0)
        # Correct image is highlighted
        self.check_highlight()
        # It should be the last image
        self.assertEqual(self.blurry.offsets[0], blurry.PAGESIZE-1)

    def test_insert(self):
        "Single file load - InsertFromRight, Home, InsertFromLeft"

        # Close GUI since we want to test loading a specific file
        self.tearDown()

        # Start with one file
        self.setUp(files = [os.path.join(self.dir, "5.png")])

        # Insert on the right
        offsets = [15]
        for i in range(1, 5):
            # Number of images matches
            self.assertEqual(len(self.blurry.offsets), i)
            # On GUI too - textlabels double # of widgets
            self.assertEqual(len(self.blurry.offsets), len(self.blurry.gui.root.winfo_children())/2)
            # Order of images matches what we expect
            self.assertEqual(offsets, self.blurry.offsets)
            # Cursor on the last image
            self.assertEqual(self.blurry.cursor, len(self.blurry.offsets)-1)
            # Correct image is highlighted
            self.check_highlight()

            # Insert image via shortcut
            self.send("InsertFromRight")
            # Insert to expected list
            offsets.append(offsets[-1]+1)

        # 5.png is the 16th of NUMIMAGES files (sort order), no more to insert
        self.send("InsertFromRight")
        self.send("InsertFromRight")
        # Still only 5 images
        self.assertEqual(len(self.blurry.offsets), 5)
        # On GUI too
        self.assertEqual(len(self.blurry.offsets), len(self.blurry.gui.root.winfo_children())/2)
        # List of images matches
        self.assertEqual(offsets, self.blurry.offsets)
        # Cursor at the end
        self.assertEqual(self.blurry.cursor, len(self.blurry.offsets)-1)
        # Correct image is highlighted
        self.check_highlight()

        # Go to first image
        self.send("Home")
        # Cursor is on the first image
        self.assertEqual(self.blurry.cursor, 0)
        # Correct image is highlighted
        self.check_highlight()

        # Insert on the left
        for i in range(1, 16):
            # Send shortcut to insert on left
            self.send("InsertFromLeft")
            # Insert to expected list
            offsets.insert(0, offsets[0]-1)
            # Cursor on inserted image
            self.assertEqual(self.blurry.cursor, 0)
            # Correct image is highlighted
            self.check_highlight()
            # Number of images matches
            self.assertEqual(len(self.blurry.offsets), 5+i)
            # On GUI too
            self.assertEqual(len(self.blurry.offsets), len(self.blurry.gui.root.winfo_children())/2)
            # Order of images matches what we expect
            self.assertEqual(offsets, self.blurry.offsets)

        # Nothing more to insert
        self.send("InsertFromLeft")
        self.send("InsertFromLeft")
        # Total NUMIMAGES images in directory
        self.assertEqual(len(self.blurry.offsets), NUMIMAGES)
        # Order of insertion matches
        self.assertEqual(offsets, self.blurry.offsets)
        # Correct image is highlighted
        self.check_highlight()

    def test_nav(self):
        "End, Left, Home, Right, Up, Down"

        # Go to end
        self.send("End")
        # Cursor at the end
        self.assertEqual(self.blurry.cursor, blurry.PAGESIZE-1)
        # Correct image is highlighted
        self.check_highlight()
        # Move left few times
        for _ in range(1, blurry.PAGESIZE // 2 + 1):
            # Move right
            self.send("Left")
            # Correct image is highlighted
            self.check_highlight()

        # Go home
        self.send("Home")
        # Cursor back to 0
        self.assertEqual(self.blurry.cursor, 0)
        # Correct image is highlighted
        self.check_highlight()
        # Move right few times
        for _ in range(1, blurry.PAGESIZE // 2 + 1):
            # Move right
            self.send("Right")
            # Correct image is highlighted
            self.check_highlight()

        # Up
        self.send("Up")
        # Cursor at 0
        self.assertEqual(self.blurry.cursor, 0)
        # Offset is 0
        self.assertEqual(self.blurry.offsets[self.blurry.cursor], 0)
        # Correct image is highlighted
        self.check_highlight()

        # Down
        self.send("Down")
        # Cursor on next row
        self.assertEqual(self.blurry.cursor, blurry.PAGESIZE // 2)
        # Offset test
        self.assertEqual(self.blurry.offsets[self.blurry.cursor], blurry.PAGESIZE // 2)
        # Correct image is highlighted
        self.check_highlight()

    def test_page(self):
        "PageEnd, PageHome, End End, Home Home, PageDown, PageUp"

        # PageEnd
        self.send("PageEnd")
        # Cursor at end
        self.assertEqual(self.blurry.cursor, len(self.blurry.offsets)-1)
        # Offset is 19
        self.assertEqual(self.blurry.offsets[self.blurry.cursor], len(self.blurry.files)-1)
        # Correct image is highlighted
        self.check_highlight()

        # PageHome
        self.send("PageHome")
        # Cursor at 0
        self.assertEqual(self.blurry.cursor, 0)
        # Offset is 0 again
        self.assertEqual(self.blurry.offsets[self.blurry.cursor], 0)
        # Correct image is highlighted
        self.check_highlight()

        # Double End
        self.send("End")
        self.send("End")
        # Cursor at end
        self.assertEqual(self.blurry.cursor, len(self.blurry.offsets)-1)
        # Offset is 19
        self.assertEqual(self.blurry.offsets[self.blurry.cursor], len(self.blurry.files)-1)
        # Correct image is highlighted
        self.check_highlight()

        # Double Home
        self.send("Home")
        self.send("Home")
        # Cursor at 0
        self.assertEqual(self.blurry.cursor, 0)
        # Offset is 0 again
        self.assertEqual(self.blurry.offsets[self.blurry.cursor], 0)
        # Correct image is highlighted
        self.check_highlight()

        # PageDown
        self.send("PageDown")
        # Cursor at 0
        self.assertEqual(self.blurry.cursor, 0)
        # Offset is blurry.PAGESIZE
        self.assertEqual(self.blurry.offsets[self.blurry.cursor], blurry.PAGESIZE)
        # Correct image is highlighted
        self.check_highlight()

        # PageDown to end
        self.send("PageDown")
        self.send("PageDown")
        self.send("PageDown")
        # Cursor at 0
        self.assertEqual(self.blurry.cursor, 0)
        # Offset is correct
        self.assertEqual(self.blurry.offsets[self.blurry.cursor], NUMIMAGES - blurry.PAGESIZE)
        # Correct image is highlighted
        self.check_highlight()

        # PageUp
        self.send("PageUp")
        # Cursor at 0
        self.assertEqual(self.blurry.cursor, 0)
        # Offset is correct
        self.assertEqual(self.blurry.offsets[self.blurry.cursor], NUMIMAGES - (blurry.PAGESIZE * 2))
        # Correct image is highlighted
        self.check_highlight()

        # PageUp to beginning
        self.send("PageUp")
        self.send("PageUp")
        self.send("PageUp")
        # Cursor at 0
        self.assertEqual(self.blurry.cursor, 0)
        # Offset is 0
        self.assertEqual(self.blurry.offsets[self.blurry.cursor], 0)
        # Correct image is highlighted
        self.check_highlight()

    def test_pagesize(self):
        """
        View1x1, View1x2, View1x3
        View2x2, View2x3, View2x4
        View3x3, View3x4
        View4x4, View4x5
        View5x5
        """
        count = [1, 2, 3, 4, 6, 8, 9, 12, 16, 20, 20] # Only 20 images
        views = [key for key in gui.KEYMAP if key.startswith("View")]
        for key, val in enumerate(views):
            self.send(val)
            self.assertEqual(len(self.blurry.offsets), count[key])

    def test_popup(self):
        "Right, Compare, Quit"

        # Navigate to 3rd image
        for i in range(2):
            # Move right
            self.send("Right")
            # Verify cursor moved
            self.assertEqual(self.blurry.cursor, i+1)
            # Correct image is highlighted
            self.check_highlight()

        # No popup opened yet
        self.assertEqual(len(self.blurry.popups), 0)

        # Open popup with 3rd image
        self.send("Compare")
        # Popup opened
        self.assertEqual(len(self.blurry.popups), 1)
        popup = self.blurry.popups[0]
        # Should be only one image in popup
        self.assertEqual(len(popup.offsets), 1)
        # It should be the 3rd image
        self.assertEqual("10.png",
                         os.path.basename(popup.files[popup.offsets[popup.cursor]]))

        # Close popup
        self.send("Quit")
        # Popup was closed and nulled out
        self.assertIsNone(popup.gui.root)

    def test_shift(self):
        "Down, Up, Right, Left"

        # Shift by row
        step = blurry.PAGESIZE // 2
        count = step
        key = "Down"
        cursor = step
        for i in range(14):
            self.send(key)
            # Cursor on step'th image
            self.assertEqual(self.blurry.cursor, cursor)
            # Offset increases by step
            self.assertEqual(self.blurry.offsets[self.blurry.cursor], count)
            # Correct image is highlighted
            self.check_highlight()
            count = count + (step if key == "Down" else -step)
            if count >= NUMIMAGES:
                # No more to load going Down
                count -= step
            while count + step > NUMIMAGES:
                # NUMIMAGES not divisible by PAGESIZE
                count -= 1
            if count < 0:
                # No more to load going Up
                count = 0
            if i == 6:
                # Switch directions
                key = "Up"
                cursor = 0
                count -= step

        # Shift by one until boundaries
        key = "Right"
        count = 1
        cursor = 1
        for i in range(0, NUMIMAGES*2 + 5):
            self.send(key)
            # Cursor on count'th image
            self.assertEqual(self.blurry.cursor, cursor)
            # Offset increases by step
            self.assertEqual(self.blurry.offsets[self.blurry.cursor], count)
            # Correct image is highlighted
            self.check_highlight()
            count = count + (1 if key == "Right" else -1)
            cursor = cursor + (1 if key == "Right" else -1)
            if count >= NUMIMAGES:
                # No more to load going Right
                count = NUMIMAGES - 1
            if count < 0:
                # No more to load going Left
                count = 0
            if i == 22:
                # Switch directions
                key = "Left"
                count -= 1
                cursor -= 2
            if cursor >= blurry.PAGESIZE:
                cursor = blurry.PAGESIZE - 1
            if cursor < 0:
                cursor = 0

    def test_repl_sort(self):
        "ReplaceFromRight, ReplaceFromLeft, Sort"
        offsets = list(range(blurry.PAGESIZE))
        # Initial state matches expected list
        self.assertEqual(self.blurry.offsets, offsets)
        self.send("ReplaceFromLeft")
        # No images on the left so no change
        self.assertEqual(self.blurry.offsets, offsets)
        # Cursor at 0
        self.assertEqual(self.blurry.cursor, 0)
        # Correct image is highlighted
        self.check_highlight()

        self.send("ReplaceFromRight")
        offsets[0] = offsets[-1] + 1
        # First image is now next after last in view
        self.assertEqual(self.blurry.offsets, offsets)
        # Cursor still where it was
        self.assertEqual(self.blurry.cursor, 0)
        # Correct image is highlighted
        self.check_highlight()

        # Move off of left edge by 2
        self.send("Right")
        self.send("Right")

        self.send("ReplaceFromRight")
        offsets[2] = offsets[-1] + 2
        # Third image now next of next of last
        self.assertEqual(self.blurry.offsets, offsets)
        # Cursor at 2
        self.assertEqual(self.blurry.cursor, 2)
        # Correct image is highlighted
        self.check_highlight()

        self.send("ReplaceFromLeft")
        self.send("ReplaceFromLeft")
        # Third image is now first
        offsets[2] = 0
        self.assertEqual(self.blurry.offsets, offsets)
        # Cursor still at 2
        self.assertEqual(self.blurry.cursor, 2)
        # Correct image is highlighted
        self.check_highlight()

        # Go to end
        self.send("PageEnd")
        offsets = list(range(NUMIMAGES - blurry.PAGESIZE, NUMIMAGES))
        # Initial state matches expected list
        self.assertEqual(self.blurry.offsets, offsets)
        # Cursor at the end
        self.assertEqual(self.blurry.cursor, blurry.PAGESIZE-1)
        # Correct image is highlighted
        self.check_highlight()

        self.send("ReplaceFromRight")
        # No images on the right so no change
        self.assertEqual(self.blurry.offsets, offsets)
        # Cursor still at end
        self.assertEqual(self.blurry.cursor, blurry.PAGESIZE-1)
        # Correct image is highlighted
        self.check_highlight()

        self.send("ReplaceFromLeft")
        offsets[-1] = offsets[0] - 1
        # Last image is now previous of first in view
        self.assertEqual(self.blurry.offsets, offsets)
        # Cursor still where it was
        self.assertEqual(self.blurry.cursor, blurry.PAGESIZE-1)
        # Correct image is highlighted
        self.check_highlight()

        # Sort order should match
        selected = offsets[-1]
        self.send("Sort")
        offsets.sort()
        cursor = offsets.index(selected)
        # Images sorted in order
        self.assertEqual(self.blurry.offsets, offsets)
        # Cursor on same image
        self.assertEqual(self.blurry.cursor, cursor)
        # Correct image is highlighted
        self.check_highlight()

    def test_select(self):
        "Select"

    def test_zoom(self):
        "Zoom"

class Loader(unittest.TestLoader):
    "Enables running tests with multiple pagesizes"
    def load_tests(self):
        "Loads tests with multiple pagesizes"
        tests = []
        pagesizes = sys.argv[1:] or [6, 8]
        if len(pagesizes) == 0:
            pagesizes = [8]
        for pagesize in pagesizes:
            test_cases = self.loadTestsFromTestCase(Tests)
            for test_case in test_cases:
                test_case.pagesize = int(pagesize)
                tests.append(test_case)
        return self.suiteClass(tests)

if __name__ == "__main__":
    logging.basicConfig()
    unittest.TextTestRunner(buffer=True).run(Loader().load_tests())
