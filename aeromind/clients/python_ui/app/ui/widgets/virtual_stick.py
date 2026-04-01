from __future__ import annotations

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QWidget


class VirtualStick(QWidget):
    valueChanged = Signal(int, int)

    def __init__(self, title: str, size: int = 180, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.title = title
        self.stick_size = size
        self.x_value = 0
        self.y_value = 0
        self._dragging = False
        self._knob_offset = QPointF(0.0, 0.0)

        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedSize(size, size)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._set_knob_from_position(event.position())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._dragging:
            self._set_knob_from_position(event.position())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._dragging = False
            self._reset_to_center()
        super().mouseReleaseEvent(event)

    def paintEvent(self, _event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), Qt.transparent)

        center = self.rect().center()
        radius = (min(self.width(), self.height()) / 2) - 18
        knob_radius = radius * 0.26

        painter.setPen(QPen(QColor(148, 163, 184, 72), 1.5))
        painter.setBrush(QColor(15, 23, 42, 84))
        painter.drawEllipse(center, radius, radius)

        painter.setPen(QPen(QColor(100, 116, 139, 72), 1))
        painter.drawLine(center.x() - radius + 12, center.y(), center.x() + radius - 12, center.y())
        painter.drawLine(center.x(), center.y() - radius + 12, center.x(), center.y() + radius - 12)

        knob_center = QPointF(center) + self._knob_offset
        painter.setPen(QPen(QColor(148, 163, 184, 112), 1))
        painter.setBrush(QColor(51, 65, 85, 164))
        painter.drawEllipse(knob_center, knob_radius, knob_radius)

        painter.setPen(QColor("#e2e8f0"))
        title_font = QFont()
        title_font.setPointSize(10)
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.drawText(0, 8, self.width(), 22, Qt.AlignHCenter | Qt.AlignTop, self.title)

        value_font = QFont()
        value_font.setPointSize(8)
        painter.setFont(value_font)
        painter.setPen(QColor("#94a3b8"))
        painter.drawText(
            0,
            self.height() - 24,
            self.width(),
            18,
            Qt.AlignHCenter | Qt.AlignBottom,
            f"X {self.x_value:>4}   Y {self.y_value:>4}",
        )

    def _set_knob_from_position(self, position: QPointF) -> None:
        center = QPointF(self.rect().center())
        offset = position - center
        self._knob_offset = self._clamp_to_radius(offset.x(), offset.y())
        self._update_values()
        self.update()

    def _clamp_to_radius(self, x: float, y: float) -> QPointF:
        radius = (min(self.width(), self.height()) / 2) - 18
        knob_radius = radius * 0.26
        max_distance = radius - knob_radius - 8
        distance = (x ** 2 + y ** 2) ** 0.5
        if distance <= max_distance or distance == 0:
            return QPointF(x, y)
        scale = max_distance / distance
        return QPointF(x * scale, y * scale)

    def _update_values(self) -> None:
        radius = (min(self.width(), self.height()) / 2) - 18
        knob_radius = radius * 0.26
        max_distance = radius - knob_radius - 8
        if max_distance <= 0:
            return

        x_value = int(round((self._knob_offset.x() / max_distance) * 100))
        y_value = int(round((-self._knob_offset.y() / max_distance) * 100))
        if x_value == self.x_value and y_value == self.y_value:
            return

        self.x_value = max(-100, min(100, x_value))
        self.y_value = max(-100, min(100, y_value))
        self.valueChanged.emit(self.x_value, self.y_value)

    def _reset_to_center(self) -> None:
        self._knob_offset = QPointF(0.0, 0.0)
        self._update_values()
        self.update()
