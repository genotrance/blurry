"GUI functionality"

# Tkinter imports
import tkinter as tk
import tkinter.filedialog as tkfd
import tkinter.messagebox as tkmb
import tkinter.ttk as ttk

# 3rd party imports
import screeninfo

# Package imports
from . import helper
from . import version

# TK shortcuts
ButtonPress = tk.EventType.ButtonPress
KeyPress = tk.EventType.KeyPress

# Colors
BLACK = "black"
COLORCURSOR = "#66ff00"
COLORSELECTED = "#66cc00"

# Constants
MAXROWS = 5             # Maximum number of rows supported
MAXCOLS = 5             # Maximum number of columns supported

# Keymap
KEYMAP = {
    # Navigation
    "Up": "<Up>",
    "Down": "<Down>",
    "Left": "<Left>",
    "Right": "<Right>",
    "Home": "<Home>",
    "End": "<End>",

    # Paging
    "PageHome": "<Control-Home>",
    "PageEnd": "<Control-End>",
    "PageUp": "<Prior>",
    "PageDown": "<Next>",

    # Selection
    "Select": "<space>",
    "SelectUp": "<Shift-Up>",
    "SelectDown": "<Shift-Down>",
    "SelectLeft": "<Shift-Left>",
    "SelectRight": "<Shift-Right>",
    "SelectAll": "<Control-a>",
    "UnselectAll": "<Escape>",

    # Add/remove
    "InsertFromRight": "<Insert>",
    "InsertFromLeft": "<Control-Insert>",
    "ReplaceFromRight": "<Control-Right>",
    "ReplaceFromLeft": "<Control-Left>",
    "Delete": "<Delete>",
    "BackSpace": "<BackSpace>",
    "DeleteToEnd": "<Control-Delete>",
    "BackSpaceToHome": "<Control-BackSpace>",

    # Actions
    "Allfiles": "a",
    "Compare": "c",
    "Faces": "f",
    "FaceHighlight": "F",
    "Similar": "s",
    "SimTight": "<bracketleft>",
    "SimLoose": "<bracketright>",
    "Sort": "S",

    # Window
    "NewWindow": "<Control-n>",
    "ChangeDir": "<Control-o>",
    "Quit": "<Control-q>",
    "Reload": "<Control-r>",

    # Image manipulation
    "BlackWhite": "B",
    "Blur": "b",

    # Zoom
    "ZoomInUp": "<plus>",
    "ZoomOutUp": "<minus>",
    "ZoomInDown": "<Control-plus>",
    "ZoomOutDown": "<Control-minus>",
    "ZoomReset": "z",

    # Pagesize
    "View1x1": "<F1>",
    "View1x2": "<F2>",
    "View1x3": "<F3>",
    "View2x2": "<F4>",
    "View2x3": "<F5>",
    "View2x4": "<F6>",
    "View3x3": "<F7>",
    "View3x4": "<F8>",
    "View4x4": "<F9>",
    "View4x5": "<F10>",
    "View5x5": "<F11>"
}

class MyLabel(tk.Label):
    "Custom label class to track offset of image"
    offset = -1

class MyProgressbar(tk.Toplevel):
    "Custom popup for progressbar with labels"
    pbar = None
    percent = None
    status = None

@helper.debugclass
class Gui:
    "Class to handle all GUI functionality"
    blurry = None
    root = None
    progress = None
    labels = None
    after = None

    def __init__(self, blurry, root=None):
        self.blurry = blurry

        if root is None:
            if self.blurry.parent is not None:
                # Create a child window
                self.root = tk.Toplevel(self.blurry.parent.gui.root)
            else:
                # Create a tkinter window
                self.root = tk.Tk()
        else:
            # tkinter window already created for us - test mode
            self.root = root

        # Hide parent window
        self.root.withdraw()

        # Cache for labels
        self.labels = {}
        self.after = []

    def start(self):
        "Start the main Tkinter loop"
        self.root.mainloop()

    def quit(self):
        "Destroy the GUI"
        for after in self.after:
            self.root.after_cancel(after)
        self.after = []
        self.root.destroy()
        self.root = None

    def bind(self, key, callback):
        "Bind shortcuts from KEYMAP to callbacks"
        self.root.bind(KEYMAP[key], callback)

    def bind_all(self):
        "Bind all keyboard and mouse shortcuts to actions"

        # Navigation
        for key in ["Up", "Down", "Left", "Right", "Home", "End"]:
            self.bind(key, self.blurry.do_navigate)

        # Paging
        for key in ["PageUp", "PageDown", "PageHome", "PageEnd"]:
            self.bind(key, self.blurry.do_page)

        # Selection
        for key in ["Select", "SelectUp", "SelectDown", "SelectLeft", "SelectRight"]:
            self.bind(key, self.blurry.do_select)
        self.bind("SelectAll", self.blurry.do_select_all)
        self.bind("UnselectAll", self.blurry.do_unselect_all)

        # Add/remove
        for key in ["InsertFromRight", "InsertFromLeft"]:
            self.bind(key, self.blurry.do_add)
        for key in ["ReplaceFromRight", "ReplaceFromLeft"]:
            self.bind(key, self.blurry.do_next)
        for key in ["Delete", "BackSpace", "DeleteToEnd", "BackSpaceToHome"]:
            self.bind(key, self.blurry.do_delete)

        # Actions
        # Show all files or group similar (default)
        self.bind("Allfiles", self.blurry.do_allfiles)
        # Compare selected images in popup
        self.bind("Compare", self.blurry.do_compare)
        # Show faces in image in popup
        self.bind("Faces", self.blurry.do_faces)
        # Toggle highlighting of faces
        self.bind("FaceHighlight", self.blurry.do_facehighlight)
        # Show images in popup
        self.bind("Similar", self.blurry.do_similar)
        # Tighten similarity filter
        self.bind("SimTight", self.blurry.do_simfilter)
        # Loosen similarity filter
        self.bind("SimLoose", self.blurry.do_simfilter)
        # Sort images in order
        self.bind("Sort", self.blurry.do_sort)

        # Window
        # Open new window
        self.bind("NewWindow", self.blurry.do_new)
        # Open another directory
        self.bind("ChangeDir", self.blurry.do_chdir)
        # Quit application / close window
        self.bind("Quit", self.blurry.do_quit)
        # Close and reload
        self.bind("Reload", self.blurry.do_reload)

        # Image manipulation
        self.bind("BlackWhite", self.blurry.do_blackwhite)
        self.bind("Blur", self.blurry.do_blur)

        # Zoom
        for key in ["ZoomInUp", "ZoomOutUp", "ZoomInDown", "ZoomOutDown", "ZoomReset"]:
            self.bind(key, self.blurry.do_zoomkey)

        # Change PAGESIZE
        for key in [key for key in KEYMAP if key.startswith("View")]:
            self.bind(key, self.blurry.do_pagesize)

        # Mouse events are fixed
        # Select / unselect image
        self.root.bind("<Button-1>", self.blurry.do_select)
        # Open double-clicked image in popup
        self.root.bind("<Double-Button-1>", self.blurry.do_compare)
        # Zoom and Page
        self.root.bind("<MouseWheel>", self.blurry.do_wheel)

        # Handle window resize
        self.root.bind("<Configure>", self.blurry._do_resize)

    def set_title(self):
        "Set title for window"
        sep = " - "
        title = sep.join([f"Blurry v{version.__version__}",
                            f'"{self.blurry.dir}"',
                            f"{len(self.blurry.allfiles)} images"])
        if not self.blurry.is_allfiles:
            title = sep.join([title, f"{len(self.blurry.files)} groups",
                                 f"({self.blurry.image.sim.simfilter})"])
        self.root.title(title)

    def show_window(self):
        "Setup and show the window when ready"

        # Get monitor info
        monitors = screeninfo.get_monitors()

        # This is the primary window if no parent
        is_primary = self.blurry.parent is None

        # Put window on correct monitor
        for mon in monitors:
            if mon.is_primary is is_primary or len(monitors) == 1:
                # If multi-monitor: put a primary window on primary monitor, sec on sec
                # If only one monitor, leave window there
                geom = f"+{mon.x}+{mon.y}"
                self.root.geometry(geom)
                break

        # Get focus
        self.root.focus_force()

        # Maximize the window
        self.root.state("zoomed")

        # Set background to black
        self.root.configure(background="black")

        # Set window title
        self.set_title()

        # Update to get window size
        self.root.update()

        # Set window size to full screen if unmaximized
        geom = f"{self.root.winfo_width()}x{self.root.winfo_height()}"
        self.root.geometry(geom)

        # Load images
        self.layout()

        # Bind all shortcuts
        self.bind_all()

        # Test mode
        if self.blurry.is_testing:
            self.root.update()

    def show_error(self, title, message):
        "Show error message popup"
        tkmb.showerror(title, message, parent=self.root)

    def layout(self):
        "Draw the screen of images based on current selection and state"

        # Split screen based on number of images
        self.split_screen()

        # Clear any existing layout
        self.clear_grid()

        row = 0
        col = 0

        # Load new images in view
        self.blurry.load_new()

        # Get relative ratings of images in view
        files = [self.blurry.files[offset] for offset in self.blurry.offsets]
        sharpness, brightness, contrast = self.blurry.image.compare_ratings(files)

        # Load previous/next page in background
        self.after.append(self.root.after(500, self.blurry.load_prevnext))

        # Layout on GUI
        for offset in self.blurry.offsets:
            # Create a label to display the image
            label = MyLabel(self.root, image=self.blurry.get_imagetk(offset))

            # Set the label to fill the window
            label.grid(row=row, column=col)

            # Set background and highlight to black
            label.configure(background="black", highlightbackground="black", highlightthickness=2)

            # Add ratings text
            file = self.blurry.files[offset]
            text = ""
            if file in sharpness:
                text += f"{int(sharpness[file])}#\n"
            if file in brightness:
                text += f"{int(brightness[file])}b\n"
            if file in contrast:
                text += f"{int(contrast[file])}c\n"
            numfaces = len(self.blurry.image.get_faces(file))
            if numfaces > 0:
                text += f"{numfaces}f\n"
            numsim = len(self.blurry.image.get_similar(file))
            if numsim > 0:
                text += f"{numsim}s\n"
            if len(text) != 0:
                textlabel = tk.Label(self.root, text=text.rstrip(), font=("Fixedsys", 10), bg="black", fg="white")
                textlabel.grid(row=row, column=col, sticky="nw", pady=2)

            # Label <=> offset tracking
            label.offset = offset
            self.labels[offset] = label

            col += 1
            if col == self.blurry.cols:
                row += 1
                col = 0

        # Fill space in active grids, reset others
        for row in range(MAXROWS):
            self.root.rowconfigure(row, weight = 1 if row < self.blurry.rows else 0)
        for col in range(MAXCOLS):
            self.root.columnconfigure(col, weight = 1 if col < self.blurry.cols else 0)

        # Select image
        if self.blurry.cursor not in range(len(self.blurry.offsets)):
            self.blurry.set_cursor(0)

        # Unselect images that went out of view
        for offset in self.blurry.selected:
            if offset not in self.blurry.offsets:
                self.blurry.selected.remove(offset)

        self.highlight()

    def highlight(self):
        "Draw a border around images that are selected and the one under the cursor"
        for widget in self.root.winfo_children():
            if isinstance(widget, MyLabel):
                color = BLACK
                if widget.offset == self.blurry.offsets[self.blurry.cursor]:
                    color = COLORCURSOR
                elif widget.offset in self.blurry.selected:
                    color = COLORSELECTED

                widget.configure(highlightbackground=color)

    def clear_grid(self):
        "Clear all widgets in the grid and relevant cache entries"
        for widget in self.root.grid_slaves():
            widget.grid_forget()
            widget.destroy()

        # Clear all labels
        self.labels = {}

    def choose_dir(self):
        "Open a directory selection dialog"
        directory = tkfd.askdirectory(parent=self.root, initialdir=self.blurry.dir)
        return [directory] if len(directory) > 0 else []

    def setup_progress(self, size):
        "Show progress bar when processing"

        # Hide parent window
        self.root.withdraw()

        # Popup window for progres bar
        self.progress = MyProgressbar(self.root)

        # Window title
        self.progress.title(self.blurry.dir + " - Processing ...")

        # Progress bar widget
        self.progress.pbar = ttk.Progressbar(
            self.progress, orient="horizontal", length=400, maximum=size, mode="determinate")

        # Status label showing what was completed at the bottom
        self.progress.status = tk.Label(self.progress)
        self.progress.status.pack(side="bottom", pady=5)

        # Progress bar on the left
        self.progress.pbar.pack(side="left", padx=10, pady=5)

        # Percentage completed on the right
        self.progress.percent = tk.Label(self.progress, text="0%")
        self.progress.percent.pack(side="right", padx=10, pady=5)

        # Get focus
        self.progress.focus_force()

        # Draw the GUI hidden to get window size
        self.progress.withdraw()
        self.progress.update()

        # Center on screen
        width = self.progress.winfo_width()
        height = self.progress.winfo_height()
        ltx = (self.progress.winfo_screenwidth() // 2) - (width // 2)
        lty = (self.progress.winfo_screenheight() // 2) - (height // 2)
        self.progress.geometry(f"{width}x{height}+{ltx}+{lty}")

        # Show the GUI
        self.progress.deiconify()
        self.progress.update()

    def update_progress(self, text):
        "Update progress bar by 1 unit with text status"

        # Bump count by 1 and set percent completed
        self.progress.pbar.step(1)
        percent = int(self.progress.pbar["value"]/self.progress.pbar["maximum"]*100)
        self.progress.percent.configure(text=f"{percent}%")

        # Update progress status text
        self.progress.status.configure(text=f"Processed: {text}")
        self.progress.update()

    def close_progress(self):
        "Destroy progress bar and associated label widgets"
        self.progress.percent.destroy()
        self.progress.status.destroy()
        self.progress.pbar.destroy()
        self.progress.destroy()
        self.progress = None

        # Get focus
        self.root.focus_force()

        # Show parent window
        self.root.deiconify()
        self.root.update()

    def split_screen(self):
        "Split screen into rows and columns depending on number of images in view"

        # Number of splits
        num = len(self.blurry.offsets)

        if num < 1:
            raise ValueError("Too few images")
        # 1 row - 1x1, 1x2, 1x3
        elif num <= 3:
            self.blurry.rows, self.blurry.cols = 1, num
        # 2 rows - 2x2, 2x3, 2x4
        elif num <= 8:
            if num % 2 != 0:
                num += 1
            self.blurry.rows, self.blurry.cols = 2, num//2
        # 3 rows - 3x3, 3x4
        elif num == 9:
            self.blurry.rows, self.blurry.cols = 3, 3
        elif num <= 12:
            num = 12
            self.blurry.rows, self.blurry.cols = 3, 4
        # 4 rows - 4x4, 4x5
        elif num <= 16:
            num = 16
            self.blurry.rows, self.blurry.cols = 4, 4
        elif num <= 20:
            num = 20
            self.blurry.rows, self.blurry.cols = 4, 5
        # 5 rows - 5x5
        elif num <= 25:
            num = 25
            self.blurry.rows, self.blurry.cols = 5, 5
        else:
            raise ValueError("Too many images")

        # Get the screen width and height
        self.blurry.screen_width = self.root.winfo_width()
        self.blurry.screen_height = self.root.winfo_height()

        # Size of each split
        self.blurry.view_width = self.blurry.screen_width//self.blurry.cols
        self.blurry.view_height = self.blurry.screen_height//self.blurry.rows
