from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QPushButton, QLabel, QHBoxLayout)
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt
from gui.manager_window import SocialManagerWindow

class LauncherWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Social Farm Launcher")
        self.resize(400, 300)
        
        self.fb_window = None
        self.tk_window = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(50, 50, 50, 50)
        
        title = QLabel("CHỌN TOOL")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("Arial", 16, QFont.Bold))
        layout.addWidget(title)

        # FB Button
        btn_fb = QPushButton("FACEBOOK")
        btn_fb.setMinimumHeight(60)
        btn_fb.setStyleSheet("background-color: #1877F2; color: white; font-weight: bold; font-size: 16px;")
        btn_fb.clicked.connect(self.open_fb)
        layout.addWidget(btn_fb)

        # TikTok Button
        btn_tk = QPushButton("TIKTOK")
        btn_tk.setMinimumHeight(60)
        btn_tk.setStyleSheet("background-color: #000000; color: white; font-weight: bold; font-size: 16px;")
        btn_tk.clicked.connect(self.open_tk)
        layout.addWidget(btn_tk)

        self.setLayout(layout)

    def open_fb(self):
        if not self.fb_window:
            self.fb_window = SocialManagerWindow("facebook")
        self.fb_window.show()

    def open_tk(self):
        if not self.tk_window:
            self.tk_window = SocialManagerWindow("tiktok")
        self.tk_window.show()