# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- Implemented file-based output logging. Application standard output and standard errors are now seamlessly dumped directly into `ludexicon.log` within the project root directory.
- `launch.bat` now launches the application entirely in the background using `pythonw`, closing the command prompt cleanly immediately after launch.

### Fixed
- Fixed an `AttributeError` when launching the application where `ui_main.py` was attempting to add docks to the window menu before the docks were actually initialized.
