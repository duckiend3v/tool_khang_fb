from PyQt5.QtCore import QObject, pyqtSignal

class WorkerSignals(QObject):
    started = pyqtSignal(int)          # Báo hiệu bắt đầu (ID hàng)
    finished = pyqtSignal(int)         # Báo hiệu kết thúc (ID hàng)
    error = pyqtSignal(int, str)       # Báo lỗi (ID hàng, nội dung lỗi)
    status = pyqtSignal(int, str)      # Cập nhật trạng thái (ID hàng, text)