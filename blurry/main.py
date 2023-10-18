"Main blurry application"

# Standard library imports
import collections
import copy
import multiprocessing
import os
import sys

# 3rd party imports
from PIL import ImageTk

# Package imports
import blurry
from . import gui
from . import helper
from . import image

# Constants
PAGECACHE = 5           # Maximum number of pages to cache
PAGESIZE = 8            # Default number of files to load per page
ZOOMD = 0.5             # Increase or decrease zoom by this delta

# Cache keys
TK = "tk"
ZOOM = "zoom"

@helper.debugclass
class Blurry:
    "Main application class"
    dir = None
    files = None
    allfiles = None
    cache = None
    flags = None

    parent = None
    image = None
    gui = None

    zoom = 1.0
    zoomp = 1.0
    mouse_x = 0
    mouse_y = 0

    rows = None
    cols = None
    screen_width = None
    screen_height = None
    view_width = None
    view_height = None

    cursor = 0
    cursorp = None
    offsets = None
    selected = None

    # Show all the files or group similar as specified
    is_allfiles = False
    # Show images in B&W
    is_blackwhite = False
    # Highlight faces on images
    is_facehighlight = False
    # Set to true to reload app on exit
    is_reload = False
    # Test mode for unit tests
    is_testing = False

    # Images selected with key so don't clear with clicks
    is_keyselected = False

    def __init__(self, args, parent=None, is_allfiles=False, root=None, is_testing=False):
        """
        Start application
        - args = CLI args that includes filepaths and --flags
        - parent = parent window if any
        - is_allfiles = True if all files should be displayed or group similar
        - is_testing = True if testing mode
        """
        self.parent = parent
        self.is_testing = self.parent.is_testing if self.parent is not None else is_testing
        self.is_allfiles = is_allfiles

        # Start GUI
        self.gui = gui.Gui(self, root=root)

        # Get filepaths from arguments - store flags separately
        filepaths, self.flags = self.parse_args(args)

        # Initialize application
        self.init(filepaths)

    def parse_args(self, args):
        """
        Parse command line arguments and return filepaths
        Store --flags in self.flags
        """
        filepaths = []
        flags = []
        for arg in args:
            if arg.startswith("--"):
                flags.append(arg)
            else:
                filepaths.append(arg)
        return filepaths, flags

    def init(self, filepaths):
        "Initialize application - used at startup and when dir is changed"
        self.cache = {
            TK: {},
            ZOOM: {},
        }
        self.offsets = []
        self.selected = []
        self.popups = []
        # Init previous cursor positions - deque
        self.cursorp = collections.deque(maxlen = PAGESIZE)

        # Load all files
        self.find_files(filepaths)

        if self.parent is not None and self.dir == self.parent.dir:
            # Reuse parent image functions
            self.image = self.parent.image
        else:
            # Load image functions
            self.image = image.BlurryImage(self, self.dir, self.allfiles)

        # Group similar images
        self.group_images()

        # Setup and show main window
        self.gui.show_window()

    def start(self):
        "Start GUI mainloop"
        self.gui.start()

    def find_files(self, filepaths):
        """
        If directory - fetch all files in directory if first entry in filepaths

        If file(s) - fetch all files from first file base dir and load it and others
        specified into initial view

        Assumes that all filepaths are in the same directory as the first entry
        """
        if len(filepaths) == 0:
            # Choose directory if no filepaths specified
            filepaths = self.gui.choose_dir()
            if len(filepaths) == 0:
                sys.exit()

        if os.path.isdir(filepaths[0]):
            self.dir = os.path.abspath(filepaths[0])
        elif os.path.isfile(filepaths[0]):
            self.dir = os.path.abspath(os.path.dirname(filepaths[0]))
        else:
            # Bad filepath, ask user to choose again
            self.gui.show_error(title="Error", message=f"Invalid filepath: {filepaths[0]}")
            filepaths = self.gui.choose_dir()
            self.find_files(filepaths)
            return

        if self.parent is not None and self.dir == self.parent.dir:
            # Get all files from parent
            self.allfiles = self.parent.allfiles
        else:
            # Find all files in directory
            self.allfiles = []
            exts = image.get_supported_exts()
            for file in os.listdir(self.dir):
                if os.path.isfile(os.path.join(self.dir, file)):
                    if os.path.splitext(file)[1].lower() in exts:
                        self.allfiles.append(file)

        if os.path.isfile(filepaths[0]):
            for filepath in filepaths:
                self.offsets.append(self.allfiles.index(os.path.basename(filepath)))

        if len(self.offsets) != 0:
            # Specific files loaded into view - choose from all files
            self.files = self.allfiles

    def group_images(self):
        "Group similar images unless is_allfiles"
        if len(self.offsets) != 0:
            # Specific files loaded already
            return

        if not self.is_allfiles:
            # Group similar images together
            filtered = set()
            self.files = []
            for file in self.allfiles:
                if file not in filtered:
                    self.files.append(file)
                    filtered.update(self.image.get_similar(file))
        else:
            # is_allfiles so load all and don't group
            self.files = self.allfiles

        # Show first PAGESIZE images on initial load
        self.offsets = list(range(min(PAGESIZE, len(self.files))))

    def set_cursor(self, cursor):
        "Update cursor position saving previous position"
        if cursor != self.cursor:
            self.cursorp.append(self.cursor)
            self.cursor = cursor

    def add_selected(self, offset):
        "Add offset to selected if not already present"
        if offset not in self.selected:
            self.selected.append(offset)

    def del_selected(self, offset):
        "Remove offset from selected if present"
        if offset in self.selected:
            self.selected.remove(offset)

    # Callbacks

    def getkey(self, event):
        "Convert keysym into KEYMAP format"
        key = event.keysym
        control = event.state & 0x4 != 0
        shift = event.state & 0x1 != 0
        if control:
            if shift:
                key = f"Control-Shift-{key}"
            else:
                key = f"Control-{key}"
        elif shift:
            key = f"Shift-{key}"

        if len(key) != 1:
            key = f"<{key}>"

        return key

    def do_shift(self, dirn, count = None):
        """
        Shift one row or count images based on direction

        Called at view edges to pull in the next (set) of images
        """
        count = count or len(self.offsets) // self.rows
        if dirn > 0:
            # Shift right - load image(s) from left/above
            while self.offsets[0] - count < 0:
                # Limit since not enough images left
                count -= 1
            if count == 0:
                # No images remain to shift
                return
            for _ in range(count):
                self.offsets.insert(0, self.offsets[0]-1)
            self.offsets = self.offsets[:-count]
        elif dirn < 0:
            # Shift left - load image(s) from right/below
            while self.offsets[-1] + count > len(self.files)-1:
                # Limit since not enough images left
                count -= 1
            if count == 0:
                # No images remain to shift
                return
            for _ in range(count):
                self.offsets.append(self.offsets[-1]+1)
            self.offsets = self.offsets[count:]

        self.gui.layout()

    def do_navigate(self, event):
        """
        Move cursor based on keyboard events

        If cursor is at the edge of a view, update the view based on direction
        """
        key = self.getkey(event)
        if key == gui.KEYMAP["Home"]:
            if self.cursor == 0:
                # Already at beginning of view, go to first page
                self.do_page(event)
            else:
                # Move cursor to first image in view
                self.set_cursor(0)
        elif key == gui.KEYMAP["End"]:
            dst = len(self.offsets)-1
            if self.cursor == dst:
                # Already at end of view, go to last page
                self.do_page(event)
            else:
                # Move cursor to last image in view
                self.set_cursor(dst)
        elif key in [gui.KEYMAP["Left"], gui.KEYMAP["Right"]]:
            inc = 1 if key == gui.KEYMAP["Right"] else -1
            cursor = self.cursor + inc
            if cursor < 0 or cursor == len(self.offsets):
                # At the edge, attempt to shift one image
                self.do_shift(-inc, 1)
            else:
                # Move cursor by one image
                self.set_cursor(cursor)
        elif key in [gui.KEYMAP["Up"], gui.KEYMAP["Down"]]:
            row = self.cursor // self.cols
            col = self.cursor % self.cols

            if key == gui.KEYMAP["Up"]:
                if row > 0:
                    # Move cursor to previous row
                    self.set_cursor(((row - 1) * self.cols) + col)
                else:
                    # At the edge, shift in previous row
                    self.do_shift(1)
            elif key == gui.KEYMAP["Down"]:
                if row < self.rows - 1:
                    # Move cursor to next row
                    self.set_cursor(((row + 1) * self.cols) + col)
                else:
                    # At the edge, shift in next row
                    self.do_shift(-1)

        # If not using KEYMAP["Select"]
        if not self.is_keyselected:
            # Unselect all if cursor moves
            self.do_unselect_all(event)

        self.gui.highlight()

    def do_page(self, event):
        """
        Switch view to previous/next page if possible

        Handle case where there aren't enough images to fill next view so
        retain some images from current view to fit PAGESIZE
        """
        key = self.getkey(event)
        prevoffsets = copy.deepcopy(self.offsets)
        numfiles = len(self.files)
        pagesize = len(self.offsets)
        if key in [gui.KEYMAP["Home"], gui.KEYMAP["PageHome"]]:
            # Go to first page - PageHome or already at beginning of view
            first = 0
            last = min(first + pagesize, numfiles)
            self.set_cursor(0)
        elif key in [gui.KEYMAP["End"], gui.KEYMAP["PageEnd"]]:
            # Go to last page - PageEnd or already at the end of view
            last = numfiles
            first = last - pagesize
            if first < 0:
                first = 0
            self.set_cursor(pagesize - 1)
        else:
            if key == gui.KEYMAP["PageUp"] or event.delta > 0:
                # Previous page
                last = self.offsets[0]
                first = last - pagesize
                while first < 0:
                    first += 1
                    last += 1
                    if last >= numfiles:
                        last  = numfiles - 1
            elif key == gui.KEYMAP["PageDown"] or event.delta < 0:
                # Next page
                first = self.offsets[-1]+1
                if first >= numfiles:
                    return
                last = first + pagesize
                while last > numfiles:
                    first -= 1
                    last -= 1
                    if first < 0:
                        first = 0
        self.offsets = list(range(first, last))

        # Layout if list changed
        if self.offsets != prevoffsets:
            self.gui.layout()

    def do_select(self, event):
        "Select/unselect the image clicked or under cursor"

        # Ignore if only one image - already under cursor
        if len(self.offsets) == 1:
            return

        if event.type == gui.KeyPress:
            key = self.getkey(event)
            if key == gui.KEYMAP["Select"]:
                # Add image under cursor to selection
                offset = self.offsets[self.cursor]
                if offset not in self.selected:
                    # Select since not selected
                    self.selected.append(offset)
                    self.is_keyselected = True
                else:
                    # Unselect since selected
                    self.selected.remove(offset)
            elif key in [gui.KEYMAP["SelectUp"], gui.KEYMAP["SelectDown"]]:
                row = self.cursor // self.cols
                col = self.cursor % self.cols

                cursor = 0
                first = 0
                last = 0
                if key == gui.KEYMAP["SelectUp"]:
                    if row > 0:
                        # Move cursor to previous row
                        cursor = ((row - 1) * self.cols) + col
                        first = cursor+1
                        last = self.cursor+1
                    else:
                        # At the edge, do nothing
                        return
                elif key == gui.KEYMAP["SelectDown"]:
                    if row < self.rows - 1:
                        # Move cursor to next row
                        cursor = ((row + 1) * self.cols) + col
                        first = self.cursor
                        last = cursor
                    else:
                        # At the edge, do nothing
                        return
                if self.offsets[cursor] not in self.selected:
                    # If destination not selected, select until cursor
                    func = self.add_selected
                else:
                    # Unselect destination
                    func = self.del_selected
                # Select/unselect range
                for i in range(first, last):
                    try:
                        func(self.offsets[i])
                    except ValueError:
                        pass
                # Move cursor
                self.set_cursor(cursor)
            elif key in [gui.KEYMAP["SelectLeft"], gui.KEYMAP["SelectRight"]]:
                inc = 1 if key == gui.KEYMAP["SelectRight"] else -1
                cursor = self.cursor + inc
                if cursor < 0 or cursor == len(self.offsets):
                    # At the edge, do nothing
                    return
                else:
                    if self.offsets[cursor] not in self.selected:
                        # If destination not selected, select source
                        self.selected.append(self.offsets[self.cursor])
                    else:
                        # Unselect destination
                        self.selected.remove(self.offsets[cursor])
                    # Move cursor
                    self.set_cursor(cursor)
        elif gui.ButtonPress:
            # Check if image label
            if isinstance(event.widget, gui.MyLabel):
                # Image was clicked
                offset = event.widget.offset
                control = event.state & 0x4 != 0
                shift = event.state & 0x1 != 0
                # New cursor position
                cursor = self.offsets.index(offset)
                if control:
                    # Control-click - add/remove from selection
                    if offset in self.selected:
                        self.selected.remove(offset)
                        if cursor == self.cursor and len(self.selected) != 0:
                            # Go to previous cursor position
                            self.set_cursor(self.cursorp.pop())
                    else:
                        self.selected.append(offset)
                        if cursor != self.cursor:
                            # Cursor moved, add previous image to selection if not already
                            offsetp = self.offsets[self.cursor]
                            if offsetp not in self.selected:
                                self.selected.append(offsetp)
                        self.set_cursor(cursor)
                elif shift:
                    # Shift-click - select/unselect images until destination
                    if self.offsets[cursor] not in self.selected:
                        # If destination not selected, select until cursor
                        func = self.add_selected
                    else:
                        # Unselect destination
                        func = self.del_selected
                    first = cursor+1 if cursor < self.cursor else self.cursor
                    last = self.cursor+1 if cursor < self.cursor else cursor
                    # Select/unselect range
                    for i in range(first, last):
                        try:
                            func(self.offsets[i])
                        except ValueError:
                            pass
                    # Move cursor
                    self.set_cursor(cursor)
                else:
                    # Clicking an image unselects all
                    self.do_unselect_all(None)

                    self.set_cursor(cursor)
            else:
                # Clicking the blank space unselects all
                self.do_unselect_all(None)
        else:
            return

        self.gui.highlight()

    def do_select_all(self, _):
        "Add all images in view to selection"
        self.selected = copy.deepcopy(self.offsets)
        self.gui.highlight()

    def do_unselect_all(self, _):
        "Unselect all images in view - cursor is still highlighted"
        self.selected = []
        self.is_keyselected = False
        self.gui.highlight()

    def do_add(self, event):
        """
        Add previous or next image from cursor to view not already in view

        Expands pagesize to accommodate new image
        """

        # Too many images in view - only 5 x 5 supported as of now
        if len(self.offsets) == gui.MAXROWS * gui.MAXCOLS:
            return

        # Insert = add next, Ctrl-Insert - add previous
        inc = -1 if event.state & 0x4 != 0 else 1

        next_img = self.offsets[self.cursor]
        while next_img in self.offsets:
            nimg = next_img + inc
            if nimg < 0 or nimg > len(self.files)-1:
                # No more images
                return
            next_img = nimg
        self.cursor += 0 if inc < 0 else 1
        self.offsets.insert(self.cursor, next_img)

        # Reset TK image cache - pagesize changed
        self.cache[TK] = {}

        self.gui.layout()

    def do_next(self, event):
        "Replace image at cursor with previous or next image not already in view"

        # ReplaceFromRight = 1
        # ReplaceFromLeft = -1
        key = self.getkey(event)
        inc = 1 if key == gui.KEYMAP["ReplaceFromRight"] else -1

        next_img = self.offsets[self.cursor]
        while next_img in self.offsets:
            nimg = next_img + inc
            if nimg < 0 or nimg > len(self.files)-1:
                # No more images
                return

            # if len(self.offsets) > 1 and ((right and not last and ni > self.offsets[-1]) or
            #     (last and not right and ni < self.offsets[0])):
            #     # Beyond first/last when more than one selected
            #     return
            next_img = nimg
        self.offsets[self.cursor] = next_img

        self.gui.layout()

    def do_delete(self, event):
        "Delete images from view depending on cursor position"
        key = self.getkey(event)

        #  Don't remove if single image remains
        if len(self.offsets) == 1:
            return

        if key == gui.KEYMAP["Delete"]:
            # Remove selected image from view
            del self.offsets[self.cursor]
            if self.cursor != 0:
                self.cursor -= 1
        elif key == gui.KEYMAP["DeleteToEnd"]:
            # Remove all images selection onwards
            if self.cursor == 0:
                self.offsets = self.offsets[:1]
            else:
                self.offsets = self.offsets[:self.cursor]
                self.cursor -= 1
        elif key == gui.KEYMAP["BackSpace"]:
            if self.cursor > 0:
                # Remove image before selection
                del self.offsets[self.cursor-1]
                self.cursor -= 1
            else:
                return
        elif key == gui.KEYMAP["BackSpaceToHome"]:
            if self.cursor > 0:
                # Remove all images before selection
                self.offsets = self.offsets[self.cursor:]
                self.set_cursor(0)
            else:
                return

        # Reset TK image cache - pagesize changed
        self.cache[TK] = {}

        self.gui.layout()

    # Actions

    def do_allfiles(self, _):
        "Toggle to show all files or group similar (default)"
        self.is_allfiles = not self.is_allfiles
        self.offsets = []
        self.cursor = 0
        self.group_images()

        # Reset TK image cache
        self.cache[TK] = {}

        self.gui.set_title()
        self.gui.layout()

    def do_compare(self, event):
        "Open selected images in new popup window for comparison"

        # Ignore if only one image
        if len(self.offsets) == 1:
            return

        filepaths = []
        if event.type == gui.KeyPress:
            # Popup selected
            offsets = set(self.selected)
            offsets.add(self.offsets[self.cursor])
            for offset in offsets:
                filepath = os.path.join(self.dir, self.files[offset])
                filepaths.append(filepath)
        elif gui.ButtonPress:
            # Check if image label
            if not isinstance(event.widget, gui.MyLabel):
                return

            # File double clicked
            offset = event.widget.offset
            filepaths = [os.path.join(self.dir, self.files[offset])]
        else:
            return

        # Start new instance for popup
        popup = Blurry(filepaths, parent=self)
        self.popups.append(popup)
        if not self.is_testing:
            popup.gui.root.wait_window()
            self.popups.remove(popup)
            popup = None

    def do_faces(self, _):
        "Show all faces in image in popup"
        directory = self.image.extract_faces(self.files[self.offsets[self.cursor]])
        if directory is not None:
            popup = Blurry([directory], parent=self, is_allfiles=True)
            self.popups.append(popup)
            if not self.is_testing:
                popup.gui.root.wait_window()
                self.popups.remove(popup)
                popup = None

    def do_facehighlight(self, _):
        "Toggle highlighting of faces"
        self.is_facehighlight = not self.is_facehighlight

        # Reset TK image cache
        self.cache[TK] = {}

        self.gui.set_title()
        self.gui.layout()

    def do_similar(self, _):
        "Show image under cursor and all similar ones in new popup window for comparison"
        file1 = self.files[self.offsets[self.cursor]]
        filepaths = [os.path.join(self.dir, file1)]
        for file2 in self.image.get_similar(file1):
            filepaths.append(file2)

        if len(filepaths) == 1:
            # No similar files
            return

        popup = Blurry(filepaths, parent=self)
        self.popups.append(popup)
        if not self.is_testing:
            popup.gui.root.wait_window()
            self.popups.remove(popup)
            popup = None

    def do_simfilter(self, event):
        "Tighten or loosen the similar image filter"
        key = self.getkey(event)

        if key == gui.KEYMAP["SimTight"]:
            # Tighten similarity filter
            self.image.sim.filterdown()
        elif key == gui.KEYMAP["SimLoose"]:
            # Loosen similarity filter
            self.image.sim.filterup()
        else:
            return

        self.offsets = []
        self.cursor = 0
        self.group_images()

        # Reset TK image cache
        self.cache[TK] = {}

        self.gui.set_title()
        self.gui.layout()

    def do_sort(self, _):
        "Sort the images in view by file order"
        selected = self.offsets[self.cursor]
        self.offsets.sort()
        self.set_cursor(self.offsets.index(selected))

        self.gui.layout()

    # Window

    def do_new(self, _):
        "Create a new instance of blurry"
        multiprocessing.Process(target=blurry.startup).start()

    def do_chdir(self, _):
        "Change directory with a selection dialog"
        filepaths = self.gui.choose_dir()
        if len(filepaths) != 0:
            self.init(filepaths)

    def do_quit(self, _):
        "Close the app"
        if self.parent is None:
            # Save cache on exit
            self.image.save_cache()

        self.gui.quit()

    def do_reload(self, _):
        "Reload the app by destroying the main window and setting reload flag"
        self.is_reload = True
        self.gui.quit()

    # Image manipulation

    def do_blackwhite(self, _):
        "Toggle black and white mode"
        self.is_blackwhite = not self.is_blackwhite

        # Reset TK image cache - all obsolete
        self.cache[TK] = {}

        self.gui.layout()

    def do_blur(self, _):
        "Blur/unblur selected images"
        selected = self.selected + [self.offsets[self.cursor]]
        for offset in selected:
            file = self.files[offset]
            self.image.blur_image(file)

            # Reset TK image cache for affected offsets
            if offset in self.cache[TK]:
                del self.cache[TK][offset]

        self.gui.layout()

        self.propagate_blur(selected, down=True)
        self.propagate_blur(selected, down=False)

    def propagate_blur(self, offsets, down=True):
        "Propagate blur of selected offsets to all parent and child windows"
        if down:
            # Propagate blur down to all child windows
            for popup in self.popups:
                if self.dir != popup.dir:
                    # Child popup not for same image directory
                    continue

                refresh = False
                for offset in offsets:
                    if offset in popup.cache[TK]:
                        # Reset TK image cache for affected offsets
                        del popup.cache[TK][offset]
                        refresh = True
                if refresh:
                    # Redraw GUI if any images affected
                    popup.gui.layout()

                # Propagate blur further down
                popup.propagate_blur(offsets, down)
        else:
            if self.parent is not None and self.dir == self.parent.dir:
                # Parent is not for same image directory
                refresh = False
                for offset in offsets:
                    if offset in self.parent.cache[TK]:
                        # Reset TK image cache for affected offsets
                        del self.parent.cache[TK][offset]
                        refresh = True
                if refresh:
                    # Redraw GUI if any images affected
                    self.parent.gui.layout()

                # Propagate blur further up
                self.parent.propagate_blur(offsets, down=False)

    def do_zoomkey(self, event):
        """
        Zoom in/out of image or reset zoom using keyboard

        """
        key = self.getkey(event)
        ratio = ZOOMD
        if key == gui.KEYMAP["ZoomReset"]:
            # Reset zoom
            if self.zoom == 1.0:
                # Already reset
                return
            ratio = -100
        elif key in [gui.KEYMAP["ZoomOutUp"], gui.KEYMAP["ZoomOutDown"]]:
            # Zoom out
            ratio = -ZOOMD
        elif key in [gui.KEYMAP["ZoomInUp"], gui.KEYMAP["ZoomInDown"]]:
            # Zoom in
            ratio = ZOOMD

        self.zoomp = self.zoom
        self.zoom += ratio
        if self.zoom < 1.0:
            # Don't shrink beyond fit
            self.zoom = 1.0
            self.zoomp = 1.0

        # Always zoom in the middle of image along x-axis
        self.mouse_x = int(self.view_width / 2)
        if key in [gui.KEYMAP["ZoomInDown"], gui.KEYMAP["ZoomOutDown"]]:
            # If Control pressed, zoom in/out at the bottom of image
            self.mouse_y = self.view_height
        else:
            # If not, zoom in/out at the top of the image
            self.mouse_y = 0

        # Reset TK image cache - obsolete
        self.cache[TK] = {}

        self.gui.layout()

    def do_wheel(self, event):
        "Handle mouse wheel events - zoom or shift a row depending on Control"
        control = event.state & 0x4 != 0
        if control:
            # Zoom in/out
            self.zoomp = self.zoom
            if event.delta > 0:
                # Mousewheel up
                self.zoom += ZOOMD
            else:
                # Mousewheel down
                self.zoom -= ZOOMD
            if self.zoom < 1.0:
                # Don't shrink beyond fit
                self.zoom = 1.0
                self.zoomp = 1.0

            # Save mouse location to focus zoom
            self.mouse_x = event.x
            self.mouse_y = event.y

            # Reset TK image cache - obsolete
            self.cache[TK] = {}

            self.gui.layout()
        else:
            # Shift left / right
            self.do_shift(event.delta)

    def do_pagesize(self, event):
        "Update pagesize based on size requested"
        key = self.getkey(event)
        if key == gui.KEYMAP["View1x1"]:
            pagesize = 1
        elif key == gui.KEYMAP["View1x2"]:
            pagesize = 2
        elif key == gui.KEYMAP["View1x3"]:
            pagesize = 3
        elif key == gui.KEYMAP["View2x2"]:
            pagesize = 4
        elif key == gui.KEYMAP["View2x3"]:
            pagesize = 6
        elif key == gui.KEYMAP["View2x4"]:
            pagesize = 8
        elif key == gui.KEYMAP["View3x3"]:
            pagesize = 9
        elif key == gui.KEYMAP["View3x4"]:
            pagesize = 12
        elif key == gui.KEYMAP["View4x4"]:
            pagesize = 16
        elif key == gui.KEYMAP["View4x5"]:
            pagesize = 20
        elif key == gui.KEYMAP["View5x5"]:
            pagesize = 25

        # If pagesize is the same, return
        if pagesize == len(self.offsets):
            return

        # Expand view
        while len(self.offsets) < pagesize:
            if self.offsets[-1] + 1 < len(self.files):
                # Add from right first
                self.offsets.append(self.offsets[-1]+1)
            elif self.offsets[0] - 1 > 0:
                # Add from left next
                self.offsets.insert(0, self.offsets[0]-1)
            else:
                # Not enough images to fit view
                # Could be that there are enough files in between but
                # were previously deleted from view
                break

        # Reduce view
        while len(self.offsets) > pagesize:
            # Trim from right side
            del self.offsets[-1]

        # Update cursorp max size
        self.cursorp = collections.deque(self.cursorp, maxlen = pagesize)

        # Clear TK image cache - pagesize changed
        self.cache[TK] = {}

        self.gui.layout()

    def _do_resize(self, event):
        "Handle window resize event"
        if event.widget == self.gui.root:
            # Check if size actually changed
            if self.screen_width != event.width or self.screen_height != event.height:
                # Clear TK image cache - window resized
                self.cache[TK] = {}

                self.gui.layout()

    # Image processing

    def scale_image(self, img_pil, offset):
        "Scale image to fit to screen"

        # Calculate the aspect ratios of the image and the screen
        img_width_orig, img_height_orig = img_pil.size
        img_aspect_ratio = img_width_orig / img_height_orig
        aspect_ratio = self.view_width / self.view_height

        # Calculate the scaling factor and the size of the image on the screen
        if img_aspect_ratio > aspect_ratio:
            scale_factor = self.view_width / img_width_orig
        else:
            scale_factor = self.view_height / img_height_orig
        img_width_scaled = int(img_width_orig * scale_factor)
        img_height_scaled = int(img_height_orig * scale_factor)

        # New size to resize to based on zoom level
        img_width_zoom = int(img_width_scaled * self.zoom)
        img_height_zoom = int(img_height_scaled * self.zoom)

        # Resize the image to fit the screen
        img_resized = img_pil.resize((img_width_zoom, img_height_zoom), image.RESAMPLER)

        if self.zoom != 1.0:
            ltx_prev = rbx_prev = lty_prev = rby_prev = 0
            ltx = rbx = lty = rby = 0
            if offset not in self.cache[ZOOM]:
                ltx_prev, lty_prev, rbx_prev, rby_prev = 0, 0, img_width_scaled, img_height_scaled
            else:
                ltx_prev, lty_prev, rbx_prev, rby_prev = self.cache[ZOOM][offset]

            if img_width_zoom > self.view_width:
                center = int((rbx_prev - ltx_prev) / 2)
                if self.mouse_x > center:
                    # Right
                    rbx = int(rbx_prev / self.zoomp * self.zoom)
                    ltx = rbx - self.view_width
                    if ltx < 0:
                        rbx -= ltx
                        ltx = 0
                elif self.mouse_x < center:
                    # Left
                    ltx = int(ltx_prev / self.zoomp * self.zoom)
                    rbx = ltx + self.view_width
                    if rbx > img_width_zoom:
                        ltx += img_width_zoom - rbx
                        rbx = img_width_zoom
                else:
                    # Center
                    ltx = (img_width_zoom - self.view_width) / 2
                    rbx = ltx + self.view_width
            else:
                ltx, rbx = 0, img_width_zoom

            if img_height_zoom > self.view_height:
                center = int((rby_prev - lty_prev) / 2)
                if self.mouse_y > center:
                    # Bottom
                    rby = int(rby_prev / self.zoomp * self.zoom)
                    lty = rby - self.view_height
                    if lty < 0:
                        rby -= lty
                        lty = 0
                elif self.mouse_y < center:
                    # Top
                    lty = int(lty_prev / self.zoomp * self.zoom)
                    rby = lty + self.view_height
                    if rby > img_height_zoom:
                        lty += img_height_zoom - rby
                        rby = img_height_zoom
                else:
                    # Center
                    lty = (img_height_zoom - self.view_height) / 2
                    rby = lty + self.view_height
            else:
                lty, rby = 0, img_height_zoom

            self.cache[ZOOM][offset] = (ltx, lty, rbx, rby)
            crop_box = (ltx, lty, rbx, rby)

            img_resized = img_resized.crop(crop_box)
        elif offset in self.cache[ZOOM]:
            del self.cache[ZOOM][offset]

        return img_resized

    def load_image(self, offset):
        "Load image scaled to fit to screen"

        # Load image for this offset
        img_pil = self.image.read_image(self.files[offset])

        # Scale to fit screen
        return self.scale_image(img_pil, offset)

    def load_prevnext(self):
        "Load previous and next page worth of images for performance"
        new_offsets = []
        # Identify previous page of images
        for offset in range(max(self.offsets[0]-len(self.offsets), 0), self.offsets[0]):
            if offset not in self.cache[TK] and offset not in self.offsets:
                new_offsets.append(offset)
            else:
                # Refresh position in cache
                self.cache[TK][offset] = self.cache[TK].pop(offset)

        # Identify next page of images
        last = self.offsets[-1]
        for offset in range(last+1, min(last + len(self.offsets) + 1, len(self.files))):
            if offset not in self.cache[TK] and offset not in self.offsets:
                new_offsets.append(offset)
            else:
                # Refresh position in cache
                self.cache[TK][offset] = self.cache[TK].pop(offset)

        # Load images in parallel
        if len(new_offsets) > 0:
            helper.parallelize((self.load_image, new_offsets),
                               post=ImageTk.PhotoImage, results=self.cache[TK])

        # Remove older images from cache
        keys = list(self.cache[TK].keys())
        count = len(keys) - len(self.offsets) * PAGECACHE
        while count > 0:
            key = keys.pop(0)
            while key in self.offsets:
                key = keys.pop(0)
            del self.cache[TK][key]
            count -= 1

        # Delete after
        self.gui.after.pop(0)

    def load_new(self):
        "Load all new images in view"

        # Identify images to load
        new_offsets = []
        for offset in self.offsets:
            if offset not in self.cache[TK]:
                new_offsets.append(offset)
            else:
                # Refresh position in cache
                self.cache[TK][offset] = self.cache[TK].pop(offset)

        # Load new images in parallel
        if len(new_offsets) > 0:
            helper.parallelize((self.load_image, new_offsets),
                               post=ImageTk.PhotoImage, results=self.cache[TK])

    def get_imagetk(self, offset):
        "Get ImageTK for offset from cache"
        return self.cache[TK].get(offset)
