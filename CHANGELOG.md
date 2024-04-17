# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Save image cache on exit to persist any user driven changes
- Tag user blurred images in the image cache to persist on exit
- Load only image types supported PIL - ignore other files
- Support addition of files to directory processed earlier
- Remove missing files from image cache on initial load
- Propagate blur/unblur to parent and child windows
- Add brightness detection and display comparison on GUI

### Changed

- Normalize user provided paths into absolute paths
- Limit similarity comparisons to images taken within 2 minutes, reduced from 5 minutes
- Store image cache in the source directory as blurry.db - no longer one monolithic file in the home directory
- Cache similarity metadata $TEMP/blurry to save time when rescanning an image directory
- Clean up GUI display of image characteristics
- Save cache after loading image characteristics but before comparing for similarties
- Move similarity metadata from image cache to separate similarity cache since it is not saved to disk
- Improved layout to not redraw the entire window when updating images
- Set maximum parallel workers to number of CPU cores

### Fixed

- Call img_pil.close() after img_tk is created to avoid future hang in PIL.Image.open()
- Ignore errors when removing temporary directories
- Use image file creation date if EXIF date is missing
- Rescan images if similarity info is missing
- Fixed fullscreen on MacOS