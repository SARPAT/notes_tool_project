"""Interactive image placement overlay for positioning and resizing images."""

from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import (
    QImage, QPainter, QPen, QColor, QCursor, QMouseEvent, QKeyEvent, QBrush
)
from PyQt6.QtCore import Qt, QRect, QPoint, QSize, pyqtSignal


class ResizeHandle(QWidget):
    """Small draggable handle at each corner for resizing."""

    resize_started = pyqtSignal()
    resize_moved = pyqtSignal(QPoint)  # delta movement
    resize_finished = pyqtSignal()

    HANDLE_SIZE = 12

    def __init__(self, corner: str, parent=None):
        """Initialize resize handle.

        Args:
            corner: One of 'top_left', 'top_right', 'bottom_left', 'bottom_right'
            parent: Parent widget
        """
        super().__init__(parent)
        self._corner = corner
        self._dragging = False
        self._drag_start_pos = QPoint()

        self.setFixedSize(self.HANDLE_SIZE, self.HANDLE_SIZE)
        self._update_cursor()

    def _update_cursor(self):
        """Set cursor based on corner position."""
        if self._corner in ('top_left', 'bottom_right'):
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        else:
            self.setCursor(Qt.CursorShape.SizeBDiagCursor)

    def paintEvent(self, event):
        """Draw the handle as a blue-bordered white square."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # White fill
        painter.setBrush(QBrush(QColor(255, 255, 255)))
        # Blue border
        pen = QPen(QColor(0, 120, 215))  # #0078D7
        pen.setWidth(2)
        painter.setPen(pen)

        painter.drawRect(1, 1, self.HANDLE_SIZE - 2, self.HANDLE_SIZE - 2)

    def mousePressEvent(self, event: QMouseEvent):
        """Start resize drag."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._drag_start_pos = event.globalPosition().toPoint()
            self.resize_started.emit()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        """Handle resize drag movement."""
        if self._dragging:
            current_pos = event.globalPosition().toPoint()
            delta = current_pos - self._drag_start_pos
            self._drag_start_pos = current_pos
            self.resize_moved.emit(delta)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        """Finish resize drag."""
        if event.button() == Qt.MouseButton.LeftButton and self._dragging:
            self._dragging = False
            self.resize_finished.emit()
            event.accept()

    @property
    def corner(self) -> str:
        """Get the corner position of this handle."""
        return self._corner


class ImagePlacementOverlay(QWidget):
    """Floating image widget for interactive placement and resizing."""

    placement_confirmed = pyqtSignal(QImage, QRect)  # final image and rect
    placement_cancelled = pyqtSignal()

    MIN_SIZE = 50  # Minimum width/height

    def __init__(self, image: QImage, parent=None):
        """Initialize the overlay.

        Args:
            image: The QImage to display and manipulate
            parent: Parent widget
        """
        super().__init__(parent)
        self._original_image = image
        self._dragging = False
        self._drag_start_pos = QPoint()

        # Calculate initial size (fit within 400x400 maintaining aspect)
        self._calculate_initial_size()

        # Set up widget
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        # Create resize handles
        self._handles: dict[str, ResizeHandle] = {}
        for corner in ('top_left', 'top_right', 'bottom_left', 'bottom_right'):
            handle = ResizeHandle(corner, self)
            handle.resize_moved.connect(
                lambda delta, c=corner: self._on_handle_resize_moved(c, delta)
            )
            self._handles[corner] = handle

        self._update_handle_positions()
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def _calculate_initial_size(self):
        """Calculate initial size to fit within 400x400."""
        max_size = 400
        img_width = self._original_image.width()
        img_height = self._original_image.height()

        if img_width <= max_size and img_height <= max_size:
            # Image fits, use original size
            self._current_width = img_width
            self._current_height = img_height
        else:
            # Scale down maintaining aspect ratio
            scale = min(max_size / img_width, max_size / img_height)
            self._current_width = int(img_width * scale)
            self._current_height = int(img_height * scale)

        self.setMinimumSize(self.MIN_SIZE, self.MIN_SIZE)
        self.resize(self._current_width, self._current_height)

    def _update_handle_positions(self):
        """Position handles at the four corners."""
        hs = ResizeHandle.HANDLE_SIZE
        half = hs // 2

        self._handles['top_left'].move(-half, -half)
        self._handles['top_right'].move(self.width() - half, -half)
        self._handles['bottom_left'].move(-half, self.height() - half)
        self._handles['bottom_right'].move(self.width() - half, self.height() - half)

    def paintEvent(self, event):
        """Draw the image with a dashed blue border."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        # Draw scaled image
        scaled_image = self._original_image.scaled(
            self.width(), self.height(),
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        painter.drawImage(0, 0, scaled_image)

        # Draw dashed blue border
        pen = QPen(QColor(0, 120, 215))  # #0078D7
        pen.setWidth(2)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.drawRect(1, 1, self.width() - 2, self.height() - 2)

    def mousePressEvent(self, event: QMouseEvent):
        """Start dragging the image."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._drag_start_pos = event.globalPosition().toPoint() - self.pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        """Handle drag movement."""
        if self._dragging:
            new_pos = event.globalPosition().toPoint() - self._drag_start_pos
            # Constrain to parent bounds
            if self.parent():
                parent_rect = self.parent().rect()
                new_x = max(0, min(new_pos.x(), parent_rect.width() - self.width()))
                new_y = max(0, min(new_pos.y(), parent_rect.height() - self.height()))
                new_pos = QPoint(new_x, new_y)
            self.move(new_pos)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        """End dragging."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            event.accept()

    def keyPressEvent(self, event: QKeyEvent):
        """Handle key events - Escape to cancel."""
        if event.key() == Qt.Key.Key_Escape:
            self.placement_cancelled.emit()
            self.close()
            event.accept()
        else:
            super().keyPressEvent(event)

    def _on_handle_resize_moved(self, corner: str, delta: QPoint):
        """Handle resize from a corner.

        Independent (non-proportional) resize based on which corner is dragged.
        """
        current_rect = self.geometry()
        new_rect = QRect(current_rect)

        if corner == 'top_left':
            new_rect.setTopLeft(current_rect.topLeft() + delta)
        elif corner == 'top_right':
            new_rect.setTopRight(current_rect.topRight() + delta)
        elif corner == 'bottom_left':
            new_rect.setBottomLeft(current_rect.bottomLeft() + delta)
        elif corner == 'bottom_right':
            new_rect.setBottomRight(current_rect.bottomRight() + delta)

        # Enforce minimum size
        if new_rect.width() < self.MIN_SIZE:
            if corner in ('top_left', 'bottom_left'):
                new_rect.setLeft(new_rect.right() - self.MIN_SIZE)
            else:
                new_rect.setRight(new_rect.left() + self.MIN_SIZE)

        if new_rect.height() < self.MIN_SIZE:
            if corner in ('top_left', 'top_right'):
                new_rect.setTop(new_rect.bottom() - self.MIN_SIZE)
            else:
                new_rect.setBottom(new_rect.top() + self.MIN_SIZE)

        # Apply new geometry
        self.setGeometry(new_rect)
        self._current_width = new_rect.width()
        self._current_height = new_rect.height()
        self._update_handle_positions()
        self.update()

    def get_final_image(self) -> QImage:
        """Return the scaled image at the current size."""
        return self._original_image.scaled(
            self.width(), self.height(),
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )

    def confirm_placement(self):
        """Confirm the current placement and emit signal."""
        final_image = self.get_final_image()
        self.placement_confirmed.emit(final_image, self.geometry())
        self.close()
