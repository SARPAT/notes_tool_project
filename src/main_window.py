
"""Main window with split-view layout for PDF viewer and notes editor."""

import os
from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow, QSplitter, QStatusBar, QMenuBar, QMenu,
    QFileDialog, QMessageBox, QApplication
)
from PyQt6.QtGui import QAction, QKeySequence, QDragEnterEvent, QDropEvent, QCloseEvent
from PyQt6.QtCore import Qt, QTimer, QEvent

from .pdf_viewer import PDFViewer
from .notes_editor import NotesEditor
from .storage import NotesStorage


class MainWindow(QMainWindow):
    """Main application window with PDF viewer and notes editor."""

    def __init__(self):
        super().__init__()

        # Initialize storage
        self._storage = NotesStorage(
            str(Path(__file__).parent.parent / "notes_data")
        )
        self._current_pdf_path = ""
        self._unsaved_changes = False

        self._setup_ui()
        self._setup_menu()
        self._setup_autosave()
        self._connect_signals()

        # Enable drag and drop
        self.setAcceptDrops(True)

    def _setup_ui(self):
        """Set up the main window UI."""
        self.setWindowTitle("PDF Notes Tool")
        self.setMinimumSize(1200, 700)

        # Create splitter for split view
        self.splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left panel: PDF viewer
        self.pdf_viewer = PDFViewer()
        self.splitter.addWidget(self.pdf_viewer)

        # Right panel: Notes editor
        self.notes_editor = NotesEditor()
        self.splitter.addWidget(self.notes_editor)

        # Set initial splitter sizes (60% PDF, 40% notes)
        self.splitter.setSizes([700, 500])

        self.setCentralWidget(self.splitter)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready - Open a PDF to get started")

    def _setup_menu(self):
        """Set up the menu bar."""
        menubar = self.menuBar()
        if menubar is None:
            menubar = QMenuBar(self)
            self.setMenuBar(menubar)

        # File menu
        file_menu = menubar.addMenu("&File")
        if file_menu is None:
            return

        open_action = QAction("&Open PDF...", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self.pdf_viewer.open_file_dialog)
        file_menu.addAction(open_action)

        file_menu.addSeparator()

        save_action = QAction("&Save Notes", self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.triggered.connect(self._save_notes)
        file_menu.addAction(save_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Edit menu
        edit_menu = menubar.addMenu("&Edit")
        if edit_menu is None:
            return

        copy_action = QAction("&Copy PDF Text", self)
        copy_action.setShortcut("C")
        copy_action.triggered.connect(self._copy_pdf_text)
        edit_menu.addAction(copy_action)

        paste_action = QAction("&Paste to Notes", self)
        paste_action.setShortcut("P")
        paste_action.triggered.connect(self._paste_to_notes)
        edit_menu.addAction(paste_action)

        # View menu
        view_menu = menubar.addMenu("&View")
        if view_menu is None:
            return

        zoom_in_action = QAction("Zoom &In", self)
        zoom_in_action.setShortcut(QKeySequence.StandardKey.ZoomIn)
        zoom_in_action.triggered.connect(self.pdf_viewer.zoom_in)
        view_menu.addAction(zoom_in_action)

        zoom_out_action = QAction("Zoom &Out", self)
        zoom_out_action.setShortcut(QKeySequence.StandardKey.ZoomOut)
        zoom_out_action.triggered.connect(self.pdf_viewer.zoom_out)
        view_menu.addAction(zoom_out_action)

        # Help menu
        help_menu = menubar.addMenu("&Help")
        if help_menu is None:
            return

        shortcuts_action = QAction("&Keyboard Shortcuts", self)
        shortcuts_action.triggered.connect(self._show_shortcuts)
        help_menu.addAction(shortcuts_action)

        about_action = QAction("&About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _setup_autosave(self):
        """Set up auto-save timer."""
        self.autosave_timer = QTimer(self)
        self.autosave_timer.timeout.connect(self._auto_save)
        self.autosave_timer.start(30000)  # 30 seconds

    def _connect_signals(self):
        """Connect signals between components."""
        # PDF loaded - load associated notes
        self.pdf_viewer.pdf_loaded.connect(self._on_pdf_loaded)

        # Text copied from PDF - set in notes clipboard
        self.pdf_viewer.text_copied.connect(self._on_text_copied)

        # Screenshot captured from PDF - set in notes clipboard
        self.pdf_viewer.screenshot_captured.connect(self._on_screenshot_captured)

        # Status messages
        self.pdf_viewer.status_message.connect(self._show_status)

        # Track content changes
        self.notes_editor.content_changed.connect(self._on_content_changed)

    def _on_pdf_loaded(self, pdf_path: str):
        """Handle PDF loaded event."""
        # Save current notes first if there are unsaved changes
        if self._current_pdf_path and self._unsaved_changes:
            self._save_notes()

        self._current_pdf_path = pdf_path

        # Load notes for this PDF
        notes_data = self._storage.load_notes(pdf_path)
        if notes_data:
            self.notes_editor.set_content(notes_data.get("content", ""))
            self._show_status(f"Loaded notes for: {Path(pdf_path).name}")
        else:
            self.notes_editor.clear_content()
            self._show_status(f"No existing notes for: {Path(pdf_path).name}")

        self._unsaved_changes = False
        self._update_title()

    def _on_text_copied(self, text: str):
        """Handle text copied from PDF."""
        self.notes_editor.set_clipboard_text(text)
        self._show_status(f"Copied to internal clipboard. Press 'P' in notes to paste.")

    def _on_screenshot_captured(self, image):
        """Handle screenshot captured from PDF."""
        self.notes_editor.set_clipboard_image(image)
        self._show_status("Screenshot captured. Press 'P' in notes to paste.")

    def _on_content_changed(self):
        """Handle notes content changed."""
        self._unsaved_changes = True
        self._update_title()

    def _save_notes(self):
        """Save current notes."""
        if not self._current_pdf_path:
            self._show_status("No PDF loaded - cannot save notes")
            return

        content = self.notes_editor.get_content()
        if self._storage.save_notes(self._current_pdf_path, content):
            self._unsaved_changes = False
            self._update_title()
            self._show_status("Notes saved successfully")
        else:
            self._show_status("Error saving notes!")

    def _auto_save(self):
        """Auto-save notes if there are unsaved changes."""
        if self._current_pdf_path and self._unsaved_changes:
            self._save_notes()
            self._show_status("Auto-saved notes")

    def _copy_pdf_text(self):
        """Copy selected text from PDF."""
        self.pdf_viewer.setFocus()
        text = self.pdf_viewer.page_widget.get_selected_text()
        if text:
            self.notes_editor.set_clipboard_text(text)
            clipboard = QApplication.clipboard()
            if clipboard is not None:
                clipboard.setText(text)
            self._show_status(f"Copied: {text[:50]}..." if len(text) > 50 else f"Copied: {text}")

    def _paste_to_notes(self):
        """Paste text or image to notes editor."""
        self.notes_editor.focus_editor()

        # Check for image first - use interactive placement
        image = self.notes_editor.get_clipboard_image()
        if image:
            self.notes_editor.start_image_placement()
            self._show_status("Position and resize image, click to paste")
            return

        # Fall back to text
        text = self.notes_editor.get_clipboard_text()
        if text:
            self.notes_editor.editor.insertPlainText(text)
            self._show_status("Pasted text to notes")

    def _update_title(self):
        """Update window title with current file and save status."""
        title = "PDF Notes Tool"
        if self._current_pdf_path:
            filename = Path(self._current_pdf_path).name
            title = f"{filename} - {title}"
            if self._unsaved_changes:
                title = f"*{title}"
        self.setWindowTitle(title)

    def _show_status(self, message: str):
        """Show a status bar message."""
        self.status_bar.showMessage(message, 5000)

    def _show_shortcuts(self):
        """Show keyboard shortcuts dialog."""
        shortcuts = """
<h3>Keyboard Shortcuts</h3>
<table>
<tr><td><b>C</b></td><td>Copy selected PDF text</td></tr>
<tr><td><b>S</b></td><td>Screenshot selected region</td></tr>
<tr><td><b>P</b></td><td>Paste text/screenshot to notes</td></tr>
<tr><td><b>Ctrl+O</b></td><td>Open PDF file</td></tr>
<tr><td><b>Ctrl+S</b></td><td>Save notes</td></tr>
<tr><td><b>Ctrl+B</b></td><td>Bold text</td></tr>
<tr><td><b>Ctrl+I</b></td><td>Italic text</td></tr>
<tr><td><b>Ctrl+U</b></td><td>Underline text</td></tr>
<tr><td><b>Left/Right</b></td><td>Previous/Next page</td></tr>
<tr><td><b>Ctrl+Scroll</b></td><td>Zoom in/out</td></tr>
</table>
"""
        QMessageBox.information(self, "Keyboard Shortcuts", shortcuts)

    def _show_about(self):
        """Show about dialog."""
        about_text = """
<h3>PDF Notes Tool</h3>
<p>A PDF reader with integrated notes.</p>
<p>Select text in the PDF viewer and press 'C' to copy.<br>
Click in the notes panel and press 'P' to paste.</p>
<p>Notes are automatically saved and linked to each PDF file.</p>
"""
        QMessageBox.about(self, "About PDF Notes Tool", about_text)

    def dragEnterEvent(self, a0: QDragEnterEvent | None):
        """Handle drag enter event for file drop."""
        if a0 is not None:
            mime_data = a0.mimeData()
            if mime_data is not None and mime_data.hasUrls():
                for url in mime_data.urls():
                    if url.toLocalFile().lower().endswith('.pdf'):
                        a0.acceptProposedAction()
                        return

    def dropEvent(self, a0: QDropEvent | None):
        """Handle file drop event."""
        if a0 is None:
            return
        mime_data = a0.mimeData()
        if mime_data is None:
            return
        for url in mime_data.urls():
            file_path = url.toLocalFile()
            if file_path.lower().endswith('.pdf'):
                self.pdf_viewer.load_pdf(file_path)
                break

    def closeEvent(self, a0: QCloseEvent | None):
        """Handle window close event."""
        if a0 is None:
            return
        if self._unsaved_changes:
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                "You have unsaved notes. Save before closing?",
                QMessageBox.StandardButton.Save |
                QMessageBox.StandardButton.Discard |
                QMessageBox.StandardButton.Cancel
            )

            if reply == QMessageBox.StandardButton.Save:
                self._save_notes()
                a0.accept()
            elif reply == QMessageBox.StandardButton.Discard:
                a0.accept()
            else:
                a0.ignore()
        else:
            a0.accept()
