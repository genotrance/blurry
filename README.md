Blurry is a free and open source photo culling tool that aims to simplify
the process of selecting the best photos from a large collection of shots.

With hundreds of near-duplicates and variations, it can be tedious to
determine which photos are truly worth keeping. Most people end up saving or
uploading everything, including blurred or poor quality shots, photos
with people caught in unflattering angles or with their eyes closed. The
good ones get lost in the clutter that clogs up drives and online photo
storage.

While there are many tools available that use AI/ML to filter photos
automatically, they can be expensive. Traditional tools like Lightroom and
Photo Mechanic targeted at professional photographers also come with a high
price tag. Other free products may focus on photo editing or viewing galleries,
but lack the necessary culling features.

Blurry makes it easy to quickly review and select the best photos and discard
the rest using various image detection and algorithms and a simple workflow.
Hopefully it makes the culling process less of a chore and results in a photo
collection that is more enjoyable and worth preserving.

Blurry is built using Python and leverages many popular image processing
packages. This choice makes it easy to implement and distribute the app across
multiple platforms. Python's versatility makes it easy to iterate and improve
the app while encouraging users to contribute as well. All contributions are
welcome and appreciated.

### Features

#### Common functionality

- Show pages of photo thumbnails in different grid sizes
  - 1x1, 1x2, 1x3, 2x2, 2x3, 2x4, 3x3, 3x4, 4x4, 4x5, 5x5

- Navigate through pages - up/down/left/right/page

- Zoom in/out using keyboard or mousewheel

- Select/unselect photos for actions

- Popup view on secondary monitor

#### Photo culling related

- Compare photo sharpness and contrast relative to other photos
- Group similar photos and compare them in a popup view
- Face detection, highlighting and close ups in a popup view

### Usage

#### Installation

Blurry is a Python app so it is super easy to install if you have Python already:

	pip install git+https://github.com/genotrance/blurry

Alternatively, the source code can be downloaded and installed locally:

- `git clone https://github.com/genotrance/blurry`

- Download and extract https://github.com/genotrance/blurry/archive/main.zip

Blurry can then be installed along with its dependencies as follows:

	python -m pip install .

More methods to download and install Blurry will be added as needed.

#### Running Blurry

Once installed, Blurry can be run as follows:
- Running `blurry` directly - from `$PYTHON\Scripts`
- Running Python in the background: `pythonw -m blurry`
- Running `python blurry.py` if in the source directory

If no folder is specified in the command-line, Blurry will ask to choose a directory
to process and display.

Blurry can generate a detailed `debug.log` with the `--debug` flag. This can be useful
to debug problems and should be attached to issues when reported.

#### Keyboard shortcuts

| Category     | Action             | Description                                       |
| -------------| ------------------ | ------------------------------------------------- |
|**Navigation**| Up, Down, Left, Right, Home, End | Moves cursor within view, if at the edge, shift if possible |
| **Paging**   | Ctrl-Home, Ctrl-End, PageUp, PageDown | Move to first/last or previous/next page |
| **Selection**| Space              | Select/unselect image at cursor                    |
|              | Shift-Up           | Select/unselect all until cursor                   |
|              | Shift-Down         | Select/unselect all until cursor                   |
|              | Shift-Left         | Select/unselect all until cursor                   |
|              | Shift-Right        | Select/unselect all until cursor                   |
|              | Ctrl-a             | Select all images in view                          |
|              | Escape             | Unselect all across views                          |
|**Add/remove**| Insert             | Add next image                                     |
|              | Ctrl-Insert        | Add previous image                                 |
|              | Ctrl-Right         | Replace image at cursor with next image            |
|              | Ctrl-Left          | Replace image at cursor with previous image        |
|              | Del                | Remove image at cursor from view                   |
|              | Bksp               | Remove image before cursor                         |
|              | Ctrl-Del           | Remove all images cursor onwards                   |
|              | Ctrl-Bksp          | Remove all images before cursor                    |
| **Actions**  | a                  | Show all files or group similar (default)          |
|              | c                  | Compare selected images in new view                |
|              | f                  | Show faces in image in new view                    |
|              | F                  | Highlight faces in image (default: off)            |
|              | s                  | Show similar images in new view                    |
|              | [                  | Tighten similarity filter - exclude less similar   |
|              | ]                  | Loosen similarity filter - include less similar    |
|              | S                  | Sort view by filename                              |
| **Window**   | Ctrl-n             | Open new window                                    |
|              | Ctrl-o             | Open another directory                             |
|              | Ctrl-q             | Quit / close                                       |
|              | Ctrl-r             | Reload                                             |
|**Image manipulation**| B          | Show all images in black and white                 |
|              | b                  | Blur selected images                               |
| **Zoom**     | +                  | Zoom in on top center                              |
|              | -                  | Zoom out on top center                             |
|              | Ctrl-+             | Zoom in on bottom center                           |
|              | Ctrl--             | Zoom out on bottom center                          |
|              | z                  | Reset zoom                                         |
|              | Ctrl-Wheel         | Zoom in/out                                        |
| **Pagesize** | F1                 | 1 image - 1x1                                      |
|              | F2                 | 2 images - 1x2                                     |
|              | F3                 | 3 images - 1x3                                     |
|              | F4                 | 4 images - 2x2                                     |
|              | F5                 | 6 images - 2x3                                     |
|              | F6                 | 8 images - 2x4                                     |
|              | F7                 | 9 images - 3x3                                     |
|              | F8                 | 12 images - 3x4                                    |
|              | F9                 | 16 images - 4x4                                    |
|              | F10                | 20 images - 4x5                                    |
|              | F11                | 25 images - 5x5                                    |
| **Mouse**    | Click              | Move cursor to image                               |
|              | Ctrl-click         | Select clicked image                               |
|              | Shift-click        | Select all images from original to clicked image   |
|              | Doubleclick        | Open image in new view                             |
|              | Wheel              | Page up/down                                       |
|              | Ctrl-wheel         | Zoom in/out                                        |
