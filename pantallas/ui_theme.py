from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout


APP_STYLE = """
* {
    font-family: "Segoe UI Variable", "Segoe UI";
    font-size: 10pt;
}
QMainWindow, QWidget {
    background: #0b0d12;
    color: #f4f7fb;
}
QWidget#Sidebar {
    background: #11141b;
    border-right: 1px solid #242a35;
}
QLabel#Brand {
    font-size: 20pt;
    font-weight: 800;
    color: #ffffff;
}
QLabel#BrandSub, QLabel#Muted {
    color: #8d97a8;
}
QLabel#PageTitle {
    font-size: 22pt;
    font-weight: 800;
}
QLabel#PageSubtitle {
    color: #8d97a8;
    font-size: 10.5pt;
}
QFrame#Card, QFrame#StatCard {
    background: #131720;
    border: 1px solid #252c38;
    border-radius: 14px;
}
QFrame#Card:hover {
    border-color: #38465c;
}
QTabWidget::pane {
    border: 0;
    background: transparent;
}
QTabBar::tab {
    background: #11151d;
    color: #8d97a8;
    border: 1px solid #252c38;
    padding: 9px 18px;
    margin: 8px 4px 0 0;
    border-radius: 9px;
    font-weight: 700;
}
QTabBar::tab:selected {
    background: #1d2940;
    color: #9bb7ff;
    border-color: #3a4d72;
}
QTabBar::tab:hover:!selected {
    background: #181d27;
    color: #f4f7fb;
}
QLabel#StatValue {
    font-size: 22pt;
    font-weight: 800;
}
QLabel#StatLabel {
    color: #8d97a8;
}
QPushButton {
    min-height: 34px;
    padding: 0 13px;
    border-radius: 8px;
    border: 1px solid #2a313d;
    background: #191e28;
    color: #f4f7fb;
    font-weight: 600;
}
QPushButton:hover {
    background: #222937;
    border-color: #3a4659;
}
QPushButton:pressed {
    background: #161b24;
}
QPushButton:disabled {
    color: #5d6572;
    background: #11141a;
    border-color: #20252e;
}
QPushButton#PrimaryButton {
    background: #4d7cff;
    border-color: #638dff;
    color: white;
}
QPushButton#PrimaryButton:hover {
    background: #5a86ff;
}
QPushButton#DangerButton {
    background: #341a20;
    border-color: #66313b;
    color: #ffb7c1;
}
QPushButton#DangerButton:hover {
    background: #47212a;
}
QPushButton#NavButton {
    min-height: 42px;
    border: 0;
    border-radius: 10px;
    text-align: left;
    padding-left: 14px;
    background: transparent;
    color: #9ba5b6;
    font-weight: 600;
}
QPushButton#NavButton:hover {
    background: #181d27;
    color: white;
}
QPushButton#NavButton:checked {
    background: #1d2940;
    color: #8fb0ff;
}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    min-height: 34px;
    border-radius: 8px;
    border: 1px solid #2a313d;
    background: #0e1117;
    color: #f4f7fb;
    padding: 0 9px;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border-color: #4d7cff;
}
QComboBox::drop-down {
    border: 0;
    width: 28px;
}
QTableWidget {
    background: #0e1117;
    alternate-background-color: #121720;
    border: 1px solid #252c38;
    border-radius: 10px;
    gridline-color: #202631;
    selection-background-color: #1d315d;
    selection-color: white;
}
QHeaderView::section {
    background: #151a23;
    color: #9aa4b4;
    border: 0;
    border-bottom: 1px solid #252c38;
    padding: 9px;
    font-weight: 700;
}
QSlider::groove:horizontal {
    height: 6px;
    border-radius: 3px;
    background: #2b3240;
}
QSlider::sub-page:horizontal {
    background: #4d7cff;
    border-radius: 3px;
}
QSlider::handle:horizontal {
    width: 18px;
    height: 18px;
    margin: -6px 0;
    border-radius: 9px;
    background: #ffffff;
    border: 3px solid #4d7cff;
}
QCheckBox {
    spacing: 8px;
    min-height: 28px;
}
QScrollArea {
    border: 0;
    background: transparent;
}
QScrollBar:vertical {
    width: 10px;
    background: transparent;
}
QScrollBar::handle:vertical {
    background: #303847;
    border-radius: 5px;
    min-height: 28px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QStatusBar {
    background: #10131a;
    color: #8d97a8;
    border-top: 1px solid #222833;
}
QMenu {
    background: #151922;
    color: #f4f7fb;
    border: 1px solid #2a313d;
    border-radius: 8px;
    padding: 6px;
}
QMenu::item {
    padding: 8px 28px 8px 10px;
    border-radius: 6px;
}
QMenu::item:selected {
    background: #24314d;
}
QProgressBar {
    min-height: 10px;
    max-height: 10px;
    border: 0;
    border-radius: 5px;
    background: #262d39;
    text-align: center;
}
QProgressBar::chunk {
    border-radius: 5px;
    background: #4d7cff;
}
"""


class Card(QFrame):
    def __init__(self, title: str = "", subtitle: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(18, 16, 18, 16)
        self.body.setSpacing(10)
        if title:
            label = QLabel(title)
            label.setStyleSheet("font-size: 12pt; font-weight: 750;")
            self.body.addWidget(label)
        if subtitle:
            sub = QLabel(subtitle)
            sub.setObjectName("Muted")
            sub.setWordWrap(True)
            self.body.addWidget(sub)


class StatCard(QFrame):
    def __init__(self, label: str, value: str = "—", hint: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("StatCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(3)
        self.value_label = QLabel(value)
        self.value_label.setObjectName("StatValue")
        self.label_label = QLabel(label)
        self.label_label.setObjectName("StatLabel")
        layout.addWidget(self.value_label)
        layout.addWidget(self.label_label)
        if hint:
            hint_label = QLabel(hint)
            hint_label.setObjectName("Muted")
            hint_label.setWordWrap(True)
            layout.addWidget(hint_label)


def primary_button(text: str) -> QPushButton:
    button = QPushButton(text)
    button.setObjectName("PrimaryButton")
    return button


def danger_button(text: str) -> QPushButton:
    button = QPushButton(text)
    button.setObjectName("DangerButton")
    return button
