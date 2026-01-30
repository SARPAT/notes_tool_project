"""PDF viewer component with text selection support."""

import fitz  # PyMuPDF
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QScrollArea, QLabel, QToolBar,
    QFileDialog, QSpinBox, QHBoxLayout, QPushButton, QApplication
)
from PyQt6.QtGui import QPixmap, QImage, QPainter, QPen, QColor, QKeyEvent, QWheelEvent, QNativeGestureEvent
from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QRect, QEvent


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

        # Lazy loading support
        self._page_number = -1
        self._is_rendered = False
        self._placeholder_size = (0, 0)

    def set_placeholder(self, page_num: int, width: int, height: int):
        """Set up a placeholder for lazy loading."""
        self._page_number = page_num
        self._is_rendered = False
        self._placeholder_size = (width, height)
        self._page = None
        self._selection_start = None
        self._selection_end = None
        self._selected_text = ""

        # Create a gray placeholder with page number
        placeholder = QPixmap(width, height)
        placeholder.fill(QColor(200, 200, 200))

        # Draw page number in center
        painter = QPainter(placeholder)
        painter.setPen(QPen(QColor(100, 100, 100)))
        font = painter.font()
        font.setPointSize(24)
        painter.setFont(font)
        painter.drawText(placeholder.rect(), Qt.AlignmentFlag.AlignCenter, f"Page {page_num + 1}")
        painter.end()

        self.setPixmap(placeholder)
        self.setFixedSize(width, height)

    def unload_page(self):
        """Unload the rendered page and revert to placeholder to free memory."""
        if self._is_rendered and self._placeholder_size[0] > 0:
            width, height = self._placeholder_size
            self._page = None
            self._is_rendered = False
            self._selection_start = None
            self._selection_end = None
            self._selected_text = ""

            # Recreate placeholder
            placeholder = QPixmap(width, height)
            placeholder.fill(QColor(200, 200, 200))

            painter = QPainter(placeholder)
            painter.setPen(QPen(QColor(100, 100, 100)))
            font = painter.font()
            font.setPointSize(24)
            painter.setFont(font)
            painter.drawText(placeholder.rect(), Qt.AlignmentFlag.AlignCenter, f"Page {self._page_number + 1}")
            painter.end()

            self.setPixmap(placeholder)

    def get_page_number(self) -> int:
        """Return the page number this widget displays."""
        return self._page_number

    def is_rendered(self) -> bool:
        """Return whether the page is currently rendered."""
        return self._is_rendered

    def set_page(self, page: fitz.Page, zoom: float = 1.0):
        """Set the PDF page to display."""
        self._page = page
        self._zoom = zoom
        self._is_rendered = True
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


class PDFPageContainer(QWidget):
    """Container widget holding all PDF pages in a vertical layout."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(10, 10, 10, 10)
        self._layout.setSpacing(20)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self._page_widgets: list[PDFPageWidget] = []

    def clear_pages(self):
        """Remove all page widgets."""
        for widget in self._page_widgets:
            self._layout.removeWidget(widget)
            widget.deleteLater()
        self._page_widgets.clear()

    def add_page_widget(self, widget: PDFPageWidget):
        """Add a page widget to the container."""
        self._layout.addWidget(widget)
        self._page_widgets.append(widget)

    def get_page_widget(self, page_num: int) -> PDFPageWidget | None:
        """Get the widget for a specific page number."""
        if 0 <= page_num < len(self._page_widgets):
            return self._page_widgets[page_num]
        return None

    def get_page_widgets(self) -> list[PDFPageWidget]:
        """Return all page widgets."""
        return self._page_widgets

    def page_count(self) -> int:
        """Return the number of page widgets."""
        return len(self._page_widgets)


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
        self._gesture_base_zoom = 1.0  # Zoom level when gesture started
        self._in_gesture = False
        self._pending_rerender = False

        self._setup_ui()

        # Throttle timer for smoother gesture updates
        from PyQt6.QtCore import QTimer
        self._rerender_timer = QTimer()
        self._rerender_timer.setSingleShot(True)
        self._rerender_timer.timeout.connect(self._throttled_rerender)

        self.grabGesture(Qt.GestureType.PinchGesture)
        self.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents, True)

    def _setup_ui(self):
        """Set up the viewer UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Toolbar
        self.toolbar = self._create_toolbar()
        layout.addWidget(self.toolbar)

        # Scroll area for PDF pages
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setStyleSheet("background-color: #525659;")

        # Page container for all pages
        self.page_container = PDFPageContainer()
        self.scroll_area.setWidget(self.page_container)

        # Connect scroll events for lazy loading
        self.scroll_area.verticalScrollBar().valueChanged.connect(self._on_scroll_changed)

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

            # Clear existing pages
            self.page_container.clear_pages()

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

            # Create placeholder widgets for all pages
            for page_num in range(page_count):
                page = self._doc[page_num]
                rect = page.rect
                # Calculate display size at current zoom
                width = int(rect.width * self._zoom * 2)
                height = int(rect.height * self._zoom * 2)

                page_widget = PDFPageWidget()
                page_widget.text_selected.connect(self._on_text_selected)
                page_widget.set_placeholder(page_num, width, height)
                self.page_container.add_page_widget(page_widget)

            # Render initial visible pages
            self._update_visible_pages()
            self.zoom_label.setText(f"{int(self._zoom * 100)}%")

            self.pdf_loaded.emit(path)
            self.status_message.emit(f"Loaded: {path}")

            return True

        except Exception as e:
            self.status_message.emit(f"Error loading PDF: {e}")
            return False

    def _on_scroll_changed(self, value: int):
        """Handle scroll changes - update visible pages and page indicator."""
        self._update_visible_pages()
        self._update_page_indicator()

    def _update_visible_pages(self):
        """Render pages in viewport, unload distant ones."""
        if not self._doc:
            return

        viewport_top = self.scroll_area.verticalScrollBar().value()
        viewport_height = self.scroll_area.viewport().height()
        viewport_bottom = viewport_top + viewport_height

        # Buffer: render 1 page above and below viewport
        buffer_pixels = viewport_height

        for widget in self.page_container.get_page_widgets():
            widget_top = widget.y()
            widget_bottom = widget_top + widget.height()
            page_num = widget.get_page_number()

            # Check if widget is in viewport (with buffer)
            in_view = (widget_bottom >= viewport_top - buffer_pixels and
                       widget_top <= viewport_bottom + buffer_pixels)

            if in_view and not widget.is_rendered():
                # Render this page
                page = self._doc[page_num]
                widget.set_page(page, self._zoom)
            elif not in_view and widget.is_rendered():
                # Unload distant page
                widget.unload_page()

    def _update_page_indicator(self):
        """Update toolbar page number based on scroll position."""
        if not self._doc:
            return

        viewport_center = (self.scroll_area.verticalScrollBar().value() +
                           self.scroll_area.viewport().height() // 2)

        # Find which page the center of viewport is on
        for widget in self.page_container.get_page_widgets():
            widget_top = widget.y()
            widget_bottom = widget_top + widget.height()

            if widget_top <= viewport_center <= widget_bottom:
                page_num = widget.get_page_number()
                if page_num != self._current_page:
                    self._current_page = page_num
                    self.page_spin.blockSignals(True)
                    self.page_spin.setValue(page_num + 1)
                    self.page_spin.blockSignals(False)
                break

    def _rerender_all_pages(self):
        """Re-render all pages after zoom change."""
        if not self._doc:
            return

        # Update placeholder sizes and re-render visible pages
        for widget in self.page_container.get_page_widgets():
            page_num = widget.get_page_number()
            page = self._doc[page_num]
            rect = page.rect
            width = int(rect.width * self._zoom * 2)
            height = int(rect.height * self._zoom * 2)

            # Reset as placeholder with new size
            widget.set_placeholder(page_num, width, height)

        # Re-render visible pages
        self._update_visible_pages()
        self.zoom_label.setText(f"{int(self._zoom * 100)}%")

    def _on_page_spin_changed(self, value: int):
        """Handle page spinner change."""
        self.go_to_page(value - 1)

    def go_to_page(self, page_num: int):
        """Go to a specific page (0-indexed) by scrolling to it."""
        if self._doc and 0 <= page_num < len(self._doc):
            self._current_page = page_num
            self.page_spin.blockSignals(True)
            self.page_spin.setValue(page_num + 1)
            self.page_spin.blockSignals(False)

            # Scroll to the page widget
            widget = self.page_container.get_page_widget(page_num)
            if widget:
                self.scroll_area.ensureWidgetVisible(widget, 0, 50)
                self._update_visible_pages()

    def next_page(self):
        """Go to the next page by scrolling."""
        if self._doc and self._current_page < len(self._doc) - 1:
            self.go_to_page(self._current_page + 1)

    def previous_page(self):
        """Go to the previous page by scrolling."""
        if self._doc and self._current_page > 0:
            self.go_to_page(self._current_page - 1)

    def zoom_in(self):
        """Increase zoom level."""
        if self._zoom < 3.0:
            self._zoom += 0.25
            self._rerender_all_pages()

    def zoom_out(self):
        """Decrease zoom level."""
        if self._zoom > 0.25:
            self._zoom -= 0.25
            self._rerender_all_pages()

    def _on_text_selected(self, text: str):
        """Handle text selection from page widget."""
        self.status_message.emit(f"Selected {len(text)} characters. Press 'C' to copy.")

    def _find_widget_with_selection(self) -> PDFPageWidget | None:
        """Find the page widget that has an active selection."""
        for widget in self.page_container.get_page_widgets():
            if widget.has_selection():
                return widget
        return None

    def keyPressEvent(self, event: QKeyEvent):
        """Handle key press events."""
        if event.key() == Qt.Key.Key_C and not event.modifiers():
            # Copy selected text - find widget with selection
            widget = self._find_widget_with_selection()
            if widget:
                text = widget.get_selected_text()
                if text:
                    self.text_copied.emit(text)
                    # Also copy to system clipboard
                    QApplication.clipboard().setText(text)
                    self.status_message.emit(f"Copied: {text[:50]}..." if len(text) > 50 else f"Copied: {text}")
        elif event.key() == Qt.Key.Key_S and not event.modifiers():
            # Capture screenshot of selection
            widget = self._find_widget_with_selection()
            if widget:
                image = widget.capture_selection_screenshot()
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

    def event(self, event):
        """Override event handler to intercept gesture events."""
        if event.type() == QEvent.Type.Gesture:
            return self._gesture_event(event)
        elif event.type() == QEvent.Type.NativeGesture:
            return self._native_gesture_event(event)
        return super().event(event)

    def _gesture_event(self, event):
        """Handle gesture events, extracting pinch gestures."""
        pinch = event.gesture(Qt.GestureType.PinchGesture)
        if pinch:
            self._pinch_triggered(pinch)
        return True

    def _throttled_rerender(self):
        """Throttled re-render for smoother gesture updates."""
        if self._pending_rerender:
            self._pending_rerender = False
            self._rerender_all_pages()

    def _request_rerender(self, immediate=False):
        """Request a re-render, throttled during gestures."""
        if immediate or not self._in_gesture:
            self._rerender_timer.stop()
            self._rerender_all_pages()
        else:
            # Throttle: only re-render every 150ms during gesture
            self._pending_rerender = True
            if not self._rerender_timer.isActive():
                self._rerender_timer.start(150)

    def _pinch_triggered(self, gesture):
        """Handle pinch gesture to adjust zoom level."""
        state = gesture.state()

        # Track gesture start
        if state == Qt.GestureState.GestureStarted:
            self._gesture_base_zoom = self._zoom
            self._in_gesture = True

        change_flags = gesture.changeFlags()
        if change_flags & gesture.ChangeFlag.ScaleFactorChanged:
            scale = gesture.scaleFactor()
            new_zoom = self._gesture_base_zoom * scale
            if 0.25 <= new_zoom <= 3.0:
                self._zoom = new_zoom
                self.zoom_label.setText(f"{int(self._zoom * 100)}%")
                self._request_rerender()

        # Final re-render when gesture is finished
        if state == Qt.GestureState.GestureFinished:
            self._in_gesture = False
            self._request_rerender(immediate=True)

    def _native_gesture_event(self, event: QNativeGestureEvent):
        """Handle native touchpad gestures (Linux/macOS pinch-to-zoom)."""
        gesture_type = event.gestureType()

        if gesture_type == Qt.NativeGestureType.BeginNativeGesture:
            self._gesture_base_zoom = self._zoom
            self._in_gesture = True
            return True
        elif gesture_type == Qt.NativeGestureType.ZoomNativeGesture:
            # value() returns the zoom delta (positive = zoom in, negative = zoom out)
            delta = event.value()
            new_zoom = self._zoom * (1.0 + delta)
            if 0.25 <= new_zoom <= 3.0:
                self._zoom = new_zoom
                self.zoom_label.setText(f"{int(self._zoom * 100)}%")
                self._request_rerender()
            return True
        elif gesture_type == Qt.NativeGestureType.EndNativeGesture:
            self._in_gesture = False
            self._request_rerender(immediate=True)
            return True
        return False

    def get_pdf_path(self) -> str:
        """Get the current PDF path."""
        return self._pdf_path

    def close_pdf(self):
        """Close the current PDF."""
        if self._doc:
            # Clear all pages before closing doc
            self.page_container.clear_pages()
            self._doc.close()
            self._doc = None
            self._pdf_path = ""
