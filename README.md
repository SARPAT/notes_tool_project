# PDF Notes Tool

A lightweight desktop application for reading PDF documents and taking rich-text notes side by side. Notes are automatically linked to each PDF file and persist across sessions.

Built with Python, PyQt6, and PyMuPDF.

## Features

### Split-View Interface
- **PDF Viewer** on the left with full navigation and zoom controls
- **Rich Text Editor** on the right for taking notes
- Adjustable split ratio between panels

### PDF Viewer
- Open PDF files via menu, toolbar button, or drag-and-drop
- Page navigation with Previous/Next buttons or arrow keys
- Jump to any page using the page spinner
- Zoom in/out (25% - 300%) with buttons or Ctrl+Scroll
- Text selection with visual highlight overlay
- Screenshot capture of selected regions

### Notes Editor
- Rich text formatting: **Bold**, *Italic*, Underline
- Adjustable font size (8-72pt)
- Custom text colors
- Bullet and numbered lists
- Paste text directly from PDF selections
- Paste and resize screenshots with interactive placement

### Screenshot Capture & Placement
- Select any region in the PDF and press `S` to capture
- Interactive overlay for positioning and resizing images
- Drag to reposition, drag corners to resize
- Click outside the overlay to confirm placement

### Auto-Save & Storage
- Notes auto-save every 30 seconds
- Manual save with Ctrl+S
- Notes stored as JSON files linked to each PDF by path hash
- Unsaved changes indicator in window title
- Prompt to save on close if changes exist

## Installation

### Prerequisites
- Python 3.10 or higher

### Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/pdf-notes-tool.git
cd pdf-notes-tool
```

2. Create a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Starting the Application
```bash
python main.py
```

### Opening a PDF
- Click **Open PDF** button in the toolbar
- Use **File > Open PDF** menu (Ctrl+O)
- Drag and drop a PDF file onto the window

### Taking Notes
1. Select text in the PDF viewer by clicking and dragging
2. Press `C` to copy the selected text
3. Click in the notes editor
4. Press `P` to paste the text

### Capturing Screenshots
1. Select a region in the PDF viewer by clicking and dragging
2. Press `S` to capture the selection as an image
3. Click in the notes editor
4. Press `P` to paste - an interactive overlay appears
5. Drag to position, drag corners to resize
6. Click outside the overlay to insert the image

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `C` | Copy selected PDF text |
| `S` | Screenshot selected region |
| `P` | Paste text/screenshot to notes |
| `Ctrl+O` | Open PDF file |
| `Ctrl+S` | Save notes |
| `Ctrl+B` | Bold text |
| `Ctrl+I` | Italic text |
| `Ctrl+U` | Underline text |
| `Left/Right` | Previous/Next page |
| `Ctrl+Scroll` | Zoom in/out |
| `Esc` | Cancel image placement |

## Project Structure

```
pdf-notes-tool/
├── main.py                 # Application entry point
├── requirements.txt        # Python dependencies
├── LICENSE                 # MIT License
├── notes_data/             # Stored notes (JSON files)
└── src/
    ├── __init__.py
    ├── main_window.py      # Main application window
    ├── pdf_viewer.py       # PDF viewing component
    ├── notes_editor.py     # Rich text editor component
    ├── image_placement_overlay.py  # Image resize overlay
    └── storage.py          # Notes persistence layer
```

## Data Storage

Notes are stored in the `notes_data/` directory as JSON files. Each file contains:
- Original PDF path and filename
- Notes content in HTML format
- Last modified timestamp

File naming uses a hash of the PDF path to handle PDFs with the same name in different directories.

## Dependencies

- **PyQt6** >= 6.4.0 - GUI framework
- **PyMuPDF** >= 1.23.0 - PDF rendering and text extraction

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

Copyright (c) 2026 Saransh Patel
