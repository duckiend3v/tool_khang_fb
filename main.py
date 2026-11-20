import sys
import os
from PyQt5.QtWidgets import QApplication
from gui.launcher_ui import LauncherWindow

# Đảm bảo Python nhận diện được các module trong thư mục hiện tại
sys.path.append(os.getcwd())

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Khởi chạy cửa sổ chọn nền tảng
    launcher = LauncherWindow()
    launcher.show()
    
    sys.exit(app.exec_())