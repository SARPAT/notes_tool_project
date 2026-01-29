"""Rich text notes editor component."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTextEdit, QToolBar, QColorDialog,
    QSpinBox, QLabel, QHBoxLayout
)
from PyQt6.QtGui import (
    QAction, QFont, QTextCharFormat, QTextListFormat,
    QKeyEvent, QImage, QMouseEvent
)
from PyQt6.QtCore import Qt, pyqtSignal, QEvent, QObject, QRect

from .image_placement_overlay import ImagePlacementOverlay


class NotesEditor(QWidget):
    """Rich text editor for taking notes linked to PDFs."""

    content_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._clipboard_text = ""
        self._clipboard_image = None
        self._placement_overlay: ImagePlacementOverlay | None = None
        self._setup_ui()

    def _setup_ui(self):
        """Set up the editor UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Create text editor first (needed by toolbar)
        self.editor = QTextEdit()
        self.editor.setAcceptRichText(True)
        self.editor.setPlaceholderText(
            "Take notes here...\n\n"
            "Press 'P' to paste copied PDF text or screenshot\n"
            "Use the toolbar for formatting"
        )
        self.editor.textChanged.connect(self.content_changed.emit)

        # Create toolbar (after editor exists)
        self.toolbar = self._create_toolbar()
        layout.addWidget(self.toolbar)

        # Add editor to layout
        layout.addWidget(self.editor)

        # Shortcut hint
        hint_layout = QHBoxLayout()
        hint_label = QLabel("Shortcuts: P = Paste text/screenshot | Ctrl+B = Bold | Ctrl+I = Italic | Ctrl+U = Underline")
        hint_label.setStyleSheet("color: gray; font-size: 10px; padding: 2px;")
        hint_layout.addWidget(hint_label)
        hint_layout.addStretch()
        layout.addLayout(hint_layout)

    def _create_toolbar(self) -> QToolBar:
        """Create the formatting toolbar."""
        toolbar = QToolBar("Formatting")
        toolbar.setMovable(False)

        # Bold
        self.bold_action = QAction("B", self)
        self.bold_action.setToolTip("Bold (Ctrl+B)")
        self.bold_action.setCheckable(True)
        self.bold_action.setShortcut("Ctrl+B")
        font = self.bold_action.font()
        font.setBold(True)
        self.bold_action.setFont(font)
        self.bold_action.triggered.connect(self._toggle_bold)
        toolbar.addAction(self.bold_action)

        # Italic
        self.italic_action = QAction("I", self)
        self.italic_action.setToolTip("Italic (Ctrl+I)")
        self.italic_action.setCheckable(True)
        self.italic_action.setShortcut("Ctrl+I")
        font = self.italic_action.font()
        font.setItalic(True)
        self.italic_action.setFont(font)
        self.italic_action.triggered.connect(self._toggle_italic)
        toolbar.addAction(self.italic_action)

        # Underline
        self.underline_action = QAction("U", self)
        self.underline_action.setToolTip("Underline (Ctrl+U)")
        self.underline_action.setCheckable(True)
        self.underline_action.setShortcut("Ctrl+U")
        font = self.underline_action.font()
        font.setUnderline(True)
        self.underline_action.setFont(font)
        self.underline_action.triggered.connect(self._toggle_underline)
        toolbar.addAction(self.underline_action)

        toolbar.addSeparator()

        # Font size
        size_label = QLabel(" Size: ")
        toolbar.addWidget(size_label)

        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 72)
        self.font_size_spin.setValue(12)
        self.font_size_spin.setToolTip("Font Size")
        self.font_size_spin.valueChanged.connect(self._change_font_size)
        toolbar.addWidget(self.font_size_spin)

        toolbar.addSeparator()

        # Text color
        self.color_action = QAction("Color", self)
        self.color_action.setToolTip("Text Color")
        self.color_action.triggered.connect(self._change_text_color)
        toolbar.addAction(self.color_action)

        toolbar.addSeparator()

        # Bullet list
        self.bullet_action = QAction("• List", self)
        self.bullet_action.setToolTip("Bullet List")
        self.bullet_action.triggered.connect(self._toggle_bullet_list)
        toolbar.addAction(self.bullet_action)

        # Numbered list
        self.numbered_action = QAction("1. List", self)
        self.numbered_action.setToolTip("Numbered List")
        self.numbered_action.triggered.connect(self._toggle_numbered_list)
        toolbar.addAction(self.numbered_action)

        # Track cursor position to update toolbar state
        self.editor.cursorPositionChanged.connect(self._update_toolbar_state)

        return toolbar

    def _toggle_bold(self):
        """Toggle bold formatting."""
        fmt = QTextCharFormat()
        if self.editor.fontWeight() == QFont.Weight.Bold:
            fmt.setFontWeight(QFont.Weight.Normal)
        else:
            fmt.setFontWeight(QFont.Weight.Bold)
        self._merge_format(fmt)

    def _toggle_italic(self):
        """Toggle italic formatting."""
        fmt = QTextCharFormat()
        fmt.setFontItalic(not self.editor.fontItalic())
        self._merge_format(fmt)

    def _toggle_underline(self):
        """Toggle underline formatting."""
        fmt = QTextCharFormat()
        fmt.setFontUnderline(not self.editor.fontUnderline())
        self._merge_format(fmt)

    def _change_font_size(self, size: int):
        """Change the font size."""
        fmt = QTextCharFormat()
        fmt.setFontPointSize(size)
        self._merge_format(fmt)

    def _change_text_color(self):
        """Open color dialog and change text color."""
        color = QColorDialog.getColor(self.editor.textColor(), self)
        if color.isValid():
            fmt = QTextCharFormat()
            fmt.setForeground(color)
            self._merge_format(fmt)

    def _toggle_bullet_list(self):
        """Toggle bullet list."""
        cursor = self.editor.textCursor()
        current_list = cursor.currentList()

        if current_list and current_list.format().style() == QTextListFormat.Style.ListDisc:
            # Remove list formatting
            block_fmt = cursor.blockFormat()
            block_fmt.setIndent(0)
            cursor.setBlockFormat(block_fmt)
        else:
            list_fmt = QTextListFormat()
            list_fmt.setStyle(QTextListFormat.Style.ListDisc)
            cursor.createList(list_fmt)

    def _toggle_numbered_list(self):
        """Toggle numbered list."""
        cursor = self.editor.textCursor()
        current_list = cursor.currentList()

        if current_list and current_list.format().style() == QTextListFormat.Style.ListDecimal:
            # Remove list formatting
            block_fmt = cursor.blockFormat()
            block_fmt.setIndent(0)
            cursor.setBlockFormat(block_fmt)
        else:
            list_fmt = QTextListFormat()
            list_fmt.setStyle(QTextListFormat.Style.ListDecimal)
            cursor.createList(list_fmt)

    def _merge_format(self, fmt: QTextCharFormat):
        """Merge format with current selection or cursor position."""
        cursor = self.editor.textCursor()
        if not cursor.hasSelection():
            cursor.select(cursor.SelectionType.WordUnderCursor)
        cursor.mergeCharFormat(fmt)
        self.editor.mergeCurrentCharFormat(fmt)

    def _update_toolbar_state(self):
        """Update toolbar button states based on cursor position."""
        self.bold_action.setChecked(self.editor.fontWeight() == QFont.Weight.Bold)
        self.italic_action.setChecked(self.editor.fontItalic())
        self.underline_action.setChecked(self.editor.fontUnderline())

        # Update font size without triggering change
        self.font_size_spin.blockSignals(True)
        self.font_size_spin.setValue(int(self.editor.fontPointSize()) or 12)
        self.font_size_spin.blockSignals(False)

    def keyPressEvent(self, a0: QKeyEvent | None):
        """Handle key press events."""
        if a0 is None:
            return
        # 'P' key to paste copied PDF text or screenshot
        if a0.key() == Qt.Key.Key_P and not a0.modifiers():
            if self._clipboard_image and self.editor.hasFocus():
                self._show_image_placement_overlay()
                return
            elif self._clipboard_text and self.editor.hasFocus():
                self.editor.insertPlainText(self._clipboard_text)
                return
        super().keyPressEvent(a0)

    def set_clipboard_text(self, text: str):
        """Set the internal clipboard text from PDF selection."""
        self._clipboard_text = text
        self._clipboard_image = None  # Clear image when text is set

    def set_clipboard_image(self, image: QImage):
        """Set the internal clipboard image from PDF screenshot."""
        self._clipboard_image = image
        self._clipboard_text = ""  # Clear text when image is set

    def get_clipboard_text(self) -> str:
        """Get the current clipboard text."""
        return self._clipboard_text

    def get_clipboard_image(self) -> QImage | None:
        """Get the current clipboard image."""
        return self._clipboard_image

    def clear_clipboard_image(self):
        """Clear the clipboard image after paste."""
        self._clipboard_image = None

    def set_content(self, html: str):
        """Set the editor content from HTML."""
        self.editor.setHtml(html)

    def get_content(self) -> str:
        """Get the editor content as HTML."""
        return self.editor.toHtml()

    def clear_content(self):
        """Clear the editor content."""
        self.editor.clear()

    def focus_editor(self):
        """Set focus to the text editor."""
        self.editor.setFocus()

    def start_image_placement(self):
        """Start interactive image placement mode."""
        if self._clipboard_image:
            self._show_image_placement_overlay()

    def _show_image_placement_overlay(self):
        """Create and show the image placement overlay centered on editor."""
        if not self._clipboard_image:
            return

        # Clean up any existing overlay
        if self._placement_overlay:
            self._placement_overlay.close()
            self._placement_overlay = None

        # Create overlay as child of the editor widget
        self._placement_overlay = ImagePlacementOverlay(
            self._clipboard_image, self.editor
        )

        # Connect signals
        self._placement_overlay.placement_confirmed.connect(
            self._on_placement_confirmed
        )
        self._placement_overlay.placement_cancelled.connect(
            self._on_placement_cancelled
        )

        # Center the overlay on the editor
        editor_rect = self.editor.rect()
        overlay_width = self._placement_overlay.width()
        overlay_height = self._placement_overlay.height()
        center_x = (editor_rect.width() - overlay_width) // 2
        center_y = (editor_rect.height() - overlay_height) // 2
        self._placement_overlay.move(center_x, center_y)

        # Install event filter on viewport to detect clicks outside overlay
        viewport = self.editor.viewport()
        if viewport:
            viewport.installEventFilter(self)

        # Show and give focus
        self._placement_overlay.show()
        self._placement_overlay.setFocus()
        self._placement_overlay.raise_()

    def _on_placement_confirmed(self, image: QImage, _rect: QRect):
        """Insert the scaled image and clean up."""
        cursor = self.editor.textCursor()
        cursor.insertImage(image)
        self._clipboard_image = None  # Clear after paste
        self._cleanup_overlay()

    def _on_placement_cancelled(self):
        """Clean up overlay, keep image in clipboard."""
        self._cleanup_overlay()

    def _cleanup_overlay(self):
        """Remove event filter and clean up overlay reference."""
        viewport = self.editor.viewport()
        if viewport:
            viewport.removeEventFilter(self)
        self._placement_overlay = None

    def eventFilter(self, a0: QObject | None, a1: QEvent | None) -> bool:
        """Detect click outside overlay to confirm placement."""
        if a0 == self.editor.viewport() and self._placement_overlay and a1:
            if a1.type() == QEvent.Type.MouseButtonPress and isinstance(a1, QMouseEvent):
                # Get the click position relative to viewport
                click_pos = a1.position().toPoint()

                # Check if click is outside the overlay
                overlay_rect = self._placement_overlay.geometry()
                if not overlay_rect.contains(click_pos):
                    # Use the overlay's position (where user dragged it) for insertion
                    overlay_pos = self._placement_overlay.pos()
                    # Map to viewport coordinates
                    viewport = self.editor.viewport()
                    if viewport is None:
                        return False
                    viewport_pos = viewport.mapFrom(self.editor, overlay_pos)
                    cursor = self.editor.cursorForPosition(viewport_pos)
                    self.editor.setTextCursor(cursor)

                    # Confirm placement
                    self._placement_overlay.confirm_placement()
                    return True  # Consume the event

        return super().eventFilter(a0, a1)
