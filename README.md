# Ludexicon

**Game Asset Taxonomy Engine**

Ludexicon is a desktop application built with PyQt6 that helps technical sound designers and game developers standardize, build, and manage naming conventions (taxonomies) for their game assets.

## Core Concepts & Terminology

The application relies on several core components to generate permutations of asset names. To ensure clarity and consistency, the terminology has been updated throughout development:

- **Project**: The overall collection of data and taxonomies.
- **Name Set** (formerly *Preset* or *Pattern*): A structural pattern for naming assets, e.g., `[Entity Class]_[Action]`.
- **Sound Type** (formerly *Element*, *Wildcard*, or *Category*): Different structural parts of the taxonomy (e.g., Entity Class, Action, or Mob ID) that plug directly into Name Sets to generate combinations.
- **Element**: Individual entries populated under a Sound Type.

## Features

- **Automated Matrix Generation**: Select variables from different Sound Types and automatically generate every valid permutation of file names.
- **Lexicon Browser**: Explore both Core and Project-specific taxonomy data through an intuitive tree list.
- **Visual Builder**: Interactively slot literal strings and variables (Sound Types) to build out new Name Sets on the fly.
- **Clipboard & Data Output**: Easily copy generated matrices directly to the clipboard.

## Project Structure

The project has been refactored into distinct files to properly separate application logic, user interface, and storage concerns:

- `src/logic.py`: The underlying data engine, including the `TaxonomyManager` and core data models (`Element`, `Wildcard`, `Pattern`, `Trigger`, etc.).
- `src/ui_main.py`: The PyQt6 graphical user interface consisting of specific dock widgets and interactive layout generation.
- `src/test_ludexicon.py`: Unit tests validating the file structure components and the deterministic logic outputs.
- `data/`: A dedicated folder containing the project’s JSON taxonomies:
  - `dictionary_core.json`: Core master application taxonomy.
  - `dictionary_project.json`: Project-specific taxonomy and customizations.
- `launch.bat`: A convenient Windows batch script to bootstrap the virtual environment and run the application.

## Installation & Running

You can launch the application effortlessly on Windows using the included bootstrapper:

1. Double click `launch.bat` in the project root.
   - *This will automatically create a `.venv` virtual environment if one does not exist, install all dependencies from `requirements.txt`, and launch the PyQt6 interface without leaving a trailing command prompt window open.*

### Manual Installation (Non-Windows or Advanced)

Ensure you have Python 3.10+ installed.

1. Install dependencies from `requirements.txt`:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the application from the `src` directory:
   ```bash
   python src/ui_main.py
   ```
