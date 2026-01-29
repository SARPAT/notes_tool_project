"""PDF viewer component with text selection support."""

import fitz  # PyMuPDF
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QScrollArea, QLabel, QToolBar,
    QFileDialog, QSpinBox, QHBoxLayout, QPushButton, QApplication
)
from PyQt6.QtGui import QPixmap, QImage, QPainter, QPen, QColor, QKeyEvent, QWheelEvent
from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QRect


class PDFPageWidget(QLabel):
    """Widget to display a single PDF page with text selection."""

    text_selected = pyqtSignal(str)
    screenshot_captured = pyqtSignal(QImage)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMouseTracking(True)

        self._page = None
        self._zoom = 1.0
        self._selection_start = None
        self._selection_end = None
        self._selected_text = ""
        self._is_selecting = False

    def set_page(self, page: fitz.Page, zoom: float = 1.0):
        """Set the PDF page to display."""
        self._page = page
        self._zoom = zoom
        self._selection_start = None
        self._selection_end = None
        self._selected_text = ""
        self._render_page()

    def _render_page(self):
        """Render the current page to a pixmap."""
        if self._page is None:
            return

        # Render at higher resolution for better quality
        mat = fitz.Matrix(self._zoom * 2, self._zoom * 2)
        pix = self._page.get_pixmap(matrix=mat)

        # Convert to QImage - must copy immediately as pix.samples buffer
        # may be invalidated when PyMuPDF pixmap is garbage collected
        img = QImage(
            pix.samples,
            pix.width,
            pix.height,
            pix.stride,
            QImage.Format.Format_RGB888 if pix.n == 3 else QImage.Format.Format_RGBA8888
        ).copy()  # Critical: copy to prevent memory leak/corruption

        # Scale down for display
        pixmap = QPixmap.fromImage(img)

        # Draw selection overlay if active
        if self._selection_start and self._selection_end:
            pixmap = self._draw_selection_overlay(pixmap)

        self.setPixmap(pixmap)

    def _draw_selection_overlay(self, pixmap: QPixmap) -> QPixmap:
        """Draw selection rectangle overlay."""
        result = QPixmap(pixmap)
        painter = QPainter(result)

        # Semi-transparent blue selection
        painter.setPen(QPen(QColor(0, 120, 215), 2))
        painter.setBrush(QColor(0, 120, 215, 50))

        x1 = min(self._selection_start.x(), self._selection_end.x())
        y1 = min(self._selection_start.y(), self._selection_end.y())
        x2 = max(self._selection_start.x(), self._selection_end.x())
        y2 = max(self._selection_start.y(), self._selection_end.y())

        painter.drawRect(x1, y1, x2 - x1, y2 - y1)
        painter.end()

        return result

    def mousePressEvent(self, event):
        """Start text selection."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_selecting = True
            pos = event.position().toPoint()
            # Adjust for label positioning
            pixmap = self.pixmap()
            if pixmap:
                offset_x = (self.width() - pixmap.width()) // 2
                offset_y = (self.height() - pixmap.height()) // 2
                self._selection_start = QPoint(pos.x() - offset_x, pos.y() - offset_y)
                self._selection_end = self._selection_start

    def mouseMoveEvent(self, event):
        """Update selection during drag."""
        if self._is_selecting:
            pos = event.position().toPoint()
            pixmap = self.pixmap()
            if pixmap:
                offset_x = (self.width() - pixmap.width()) // 2
                offset_y = (self.height() - pixmap.height()) // 2
                self._selection_end = QPoint(pos.x() - offset_x, pos.y() - offset_y)
                self._render_page()

    def mouseReleaseEvent(self, event):
        """Complete selection and extract text."""
        if event.button() == Qt.MouseButton.LeftButton and self._is_selecting:
            self._is_selecting = False
            self._extract_selected_text()

    def _extract_selected_text(self):
        """Extract text from the selected region."""
        if not self._page or not self._selection_start or not self._selection_end:
            return

        # Convert screen coordinates to PDF coordinates
        scale = self._zoom * 2  # Match rendering scale

        x1 = min(self._selection_start.x(), self._selection_end.x()) / scale
        y1 = min(self._selection_start.y(), self._selection_end.y()) / scale
        x2 = max(self._selection_start.x(), self._selection_end.x()) / scale
        y2 = max(self._selection_start.y(), self._selection_end.y()) / scale

        # Create selection rectangle
        rect = fitz.Rect(x1, y1, x2, y2)

        # Extract text from region
        self._selected_text = self._page.get_text("text", clip=rect).strip()

        if self._selected_text:
            self.text_selected.emit(self._selected_text)

    def get_selected_text(self) -> str:
        """Return the currently selected text."""
        return self._selected_text

    def has_selection(self) -> bool:
        """Check if there is an active selection."""
        return self._selection_start is not None and self._selection_end is not None

    def capture_selection_screenshot(self) -> QImage | None:
        """Capture a screenshot of the selected region."""
        if not self._page or not self._selection_start or not self._selection_end:
            return None

        # Convert screen coordinates to PDF coordinates
        scale = self._zoom * 2  # Match rendering scale

        x1 = min(self._selection_start.x(), self._selection_end.x()) / scale
        y1 = min(self._selection_start.y(), self._selection_end.y()) / scale
        x2 = max(self._selection_start.x(), self._selection_end.x()) / scale
        y2 = max(self._selection_start.y(), self._selection_end.y()) / scale

        # Create clip rectangle
        clip_rect = fitz.Rect(x1, y1, x2, y2)

        # Render the clipped region at full resolution
        mat = fitz.Matrix(self._zoom * 2, self._zoom * 2)
        pix = self._page.get_pixmap(matrix=mat, clip=clip_rect)

        # Convert PyMuPDF pixmap to QImage
        img = QImage(
            pix.samples,
            pix.width,
            pix.height,
            pix.stride,
            QImage.Format.Format_RGB888 if pix.n == 3 else QImage.Format.Format_RGBA8888
        )

        # Return a copy since pix.samples may be invalidated
        return img.copy()

    def clear_selection(self):
        """Clear the current selection."""
        self._selection_start = None
        self._selection_end = None
        self._selected_text = ""
        if self._page is not None:
            self._render_page()


class PDFViewer(QWidget):
    """PDF viewer widget with navigation and text selection."""

    text_copied = pyqtSignal(str)
    pdf_loaded = pyqtSignal(str)
    status_message = pyqtSignal(str)
    screenshot_captured = pyqtSignal(QImage)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._doc = None
        self._current_page = 0
        self._zoom = 1.0
        self._pdf_path = ""

        self._setup_ui()

    def _setup_ui(self):
        """Set up the viewer UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Toolbar
        self.toolbar = self._create_toolbar()
        layout.addWidget(self.toolbar)

        # Scroll area for PDF page
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setStyleSheet("background-color: #525659;")

        # Page widget
        self.page_widget = PDFPageWidget()
        self.page_widget.text_selected.connect(self._on_text_selected)
        self.scroll_area.setWidget(self.page_widget)

        layout.addWidget(self.scroll_area)

        # Shortcut hint
        hint_layout = QHBoxLayout()
        hint_label = QLabel("Shortcuts: C = Copy text | S = Screenshot selection | Scroll = Navigate | Ctrl+Scroll = Zoom")
        hint_label.setStyleSheet("color: gray; font-size: 10px; padding: 2px;")
        hint_layout.addWidget(hint_label)
        hint_layout.addStretch()
        layout.addLayout(hint_layout)

        # Enable keyboard focus
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def _create_toolbar(self) -> QToolBar:
        """Create the PDF viewer toolbar."""
        toolbar = QToolBar("PDF Controls")
        toolbar.setMovable(False)

        # Open button
        self.open_btn = QPushButton("Open PDF")
        self.open_btn.clicked.connect(self.open_file_dialog)
        toolbar.addWidget(self.open_btn)

        toolbar.addSeparator()

        # Previous page
        self.prev_btn = QPushButton("◀ Prev")
        self.prev_btn.clicked.connect(self.previous_page)
        self.prev_btn.setEnabled(False)
        toolbar.addWidget(self.prev_btn)

        # Page indicator
        self.page_spin = QSpinBox()
        self.page_spin.setMinimum(1)
        self.page_spin.setEnabled(False)
        self.page_spin.valueChanged.connect(self._on_page_spin_changed)
        toolbar.addWidget(self.page_spin)

        self.page_count_label = QLabel(" / 0")
        toolbar.addWidget(self.page_count_label)

        # Next page
        self.next_btn = QPushButton("Next ▶")
        self.next_btn.clicked.connect(self.next_page)
        self.next_btn.setEnabled(False)
        toolbar.addWidget(self.next_btn)

        toolbar.addSeparator()

        # Zoom controls
        self.zoom_out_btn = QPushButton("−")
        self.zoom_out_btn.setToolTip("Zoom Out")
        self.zoom_out_btn.clicked.connect(self.zoom_out)
        self.zoom_out_btn.setEnabled(False)
        toolbar.addWidget(self.zoom_out_btn)

        self.zoom_label = QLabel("100%")
        self.zoom_label.setMinimumWidth(50)
        self.zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        toolbar.addWidget(self.zoom_label)

        self.zoom_in_btn = QPushButton("+")
        self.zoom_in_btn.setToolTip("Zoom In")
        self.zoom_in_btn.clicked.connect(self.zoom_in)
        self.zoom_in_btn.setEnabled(False)
        toolbar.addWidget(self.zoom_in_btn)

        return toolbar

    def open_file_dialog(self):
        """Open file dialog to select a PDF."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open PDF File",
            "",
            "PDF Files (*.pdf);;All Files (*)"
        )
        if file_path:
            self.load_pdf(file_path)

    def load_pdf(self, path: str) -> bool:
        """Load a PDF file."""
        try:
            if self._doc:
                self._doc.close()

            self._doc = fitz.open(path)
            self._pdf_path = path
            self._current_page = 0
            self._zoom = 1.0

            # Update UI
            page_count = len(self._doc)
            self.page_spin.setMaximum(page_count)
            self.page_spin.setValue(1)
            self.page_spin.setEnabled(True)
            self.page_count_label.setText(f" / {page_count}")

            self.prev_btn.setEnabled(page_count > 1)
            self.next_btn.setEnabled(page_count > 1)
            self.zoom_in_btn.setEnabled(True)
            self.zoom_out_btn.setEnabled(True)

            self._render_current_page()
            self.pdf_loaded.emit(path)
            self.status_message.emit(f"Loaded: {path}")

            return True

        except Exception as e:
            self.status_message.emit(f"Error loading PDF: {e}")
            return False

    def _render_current_page(self):
        """Render the current page."""
        if self._doc and 0 <= self._current_page < len(self._doc):
            page = self._doc[self._current_page]
            self.page_widget.set_page(page, self._zoom)
            self.zoom_label.setText(f"{int(self._zoom * 100)}%")

    def _on_page_spin_changed(self, value: int):
        """Handle page spinner change."""
        self.go_to_page(value - 1)

    def go_to_page(self, page_num: int):
        """Go to a specific page (0-indexed)."""
        if self._doc and 0 <= page_num < len(self._doc):
            self._current_page = page_num
            self.page_spin.blockSignals(True)
            self.page_spin.setValue(page_num + 1)
            self.page_spin.blockSignals(False)
            self._render_current_page()

    def next_page(self):
        """Go to the next page."""
        if self._doc and self._current_page < len(self._doc) - 1:
            self.go_to_page(self._current_page + 1)

    def previous_page(self):
        """Go to the previous page."""
        if self._doc and self._current_page > 0:
            self.go_to_page(self._current_page - 1)

    def zoom_in(self):
        """Increase zoom level."""
        if self._zoom < 3.0:
            self._zoom += 0.25
            self._render_current_page()

    def zoom_out(self):
        """Decrease zoom level."""
        if self._zoom > 0.25:
            self._zoom -= 0.25
            self._render_current_page()

    def _on_text_selected(self, text: str):
        """Handle text selection from page widget."""
        self.status_message.emit(f"Selected {len(text)} characters. Press 'C' to copy.")

    def keyPressEvent(self, event: QKeyEvent):
        """Handle key press events."""
        if event.key() == Qt.Key.Key_C and not event.modifiers():
            # Copy selected text
            text = self.page_widget.get_selected_text()
            if text:
                self.text_copied.emit(text)
                # Also copy to system clipboard
                QApplication.clipboard().setText(text)
                self.status_message.emit(f"Copied: {text[:50]}..." if len(text) > 50 else f"Copied: {text}")
        elif event.key() == Qt.Key.Key_S and not event.modifiers():
            # Capture screenshot of selection
            if self.page_widget.has_selection():
                image = self.page_widget.capture_selection_screenshot()
                if image:
                    self.screenshot_captured.emit(image)
                    self.status_message.emit("Screenshot captured. Press 'P' in notes to paste.")
            else:
                self.status_message.emit("No selection. Select a region first, then press 'S'.")
        elif event.key() == Qt.Key.Key_Right or event.key() == Qt.Key.Key_PageDown:
            self.next_page()
        elif event.key() == Qt.Key.Key_Left or event.key() == Qt.Key.Key_PageUp:
            self.previous_page()
        else:
            super().keyPressEvent(event)

    def wheelEvent(self, event: QWheelEvent):
        """Handle mouse wheel for scrolling/zooming."""
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            # Zoom with Ctrl+Scroll
            delta = event.angleDelta().y()
            if delta > 0:
                self.zoom_in()
            elif delta < 0:
                self.zoom_out()
        else:
            # Pass to scroll area
            self.scroll_area.wheelEvent(event)

    def get_pdf_path(self) -> str:
        """Get the current PDF path."""
        return self._pdf_path

    def close_pdf(self):
        """Close the current PDF."""
        if self._doc:
            # Clear page reference before closing doc to avoid render on stale page
            self.page_widget._page = None
            self.page_widget.clear_selection()
            self.page_widget.setPixmap(QPixmap())  # Clear the display
            self._doc.close()
            self._doc = None
            self._pdf_path = ""
