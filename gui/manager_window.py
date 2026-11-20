import json
import time
import os
import re
import random
import tempfile
import shutil
import requests
from core.totp import generate_totp, totp_seconds_remaining
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QTableWidget, QTableWidgetItem, QPushButton, 
                             QLabel, QSpinBox, QMessageBox, QHeaderView, QInputDialog,
                              QGroupBox, QCheckBox, QFormLayout, QFileDialog, QLineEdit, QTextEdit, 
                             QDialog, QDialogButtonBox, QAbstractItemView, QTabWidget, QRadioButton, QButtonGroup,
                             QComboBox,
                             QScrollArea)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QGuiApplication
from core.worker import FarmWorker
from browser.profile_manager import ProfileManager

# Global variable for page creation index
CURRENT_INDEX = 0

def save_index():
    global CURRENT_INDEX
    with open("index.txt", "w") as f:
        f.write(str(CURRENT_INDEX))

def load_index():
    global CURRENT_INDEX
    try:
        with open("index.txt", "r") as f:
            CURRENT_INDEX = int(f.read())
    except:
        CURRENT_INDEX = 0
        
def get_next_page(file_path="data_name_page.txt"):
    global CURRENT_INDEX

    with open(file_path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if "|" in line]

    if CURRENT_INDEX >= len(lines):
        return None

    line = lines[CURRENT_INDEX]
    CURRENT_INDEX += 1

    industry, name, desc, category = line.split("|")

    return name, category, desc

class SocialManagerWindow(QMainWindow):
    def __init__(self, platform_name):
        super().__init__()
        self.platform = platform_name
        
        # Cấu hình tiêu đề và file data theo nền tảng
        if self.platform == "facebook":
            self.setWindowTitle("FACEBOOK MANAGER - [Enterprise Edition]")
            self.data_file = os.path.join("data", "facebook_accounts.json")
            self.theme_color = "#0078d7" # Xanh Facebook
        else:
            self.setWindowTitle("TIKTOK MANAGER - [Creator Tools]")
            self.data_file = os.path.join("data", "tiktok_accounts.json")
            self.theme_color = "#FE2C55" # Đỏ TikTok

        self.resize(1280, 760)
        self.accounts = []
        self.workers = {} 
        self.queue = []
        self.batch_login_workers = {}
        self.batch_login_queue = []
        self.batch_login_browsers = []
        self.batch_login_total = 0
        self.batch_login_done = 0
        self.batch_login_success_count = 0
        self.batch_login_auto_close = False
        self.batch_login_stop_requested = False
        self.single_login_workers = {}
        self.password_change_workers = {}
        self.password_change_queue = []
        self.password_change_total = 0
        self.password_change_done = 0
        self.password_change_new_password = ""
        self.password_change_results = {}
        self.pages = []
        self.pages_file = os.path.join("data", f"{self.platform}_pages.json")
        self.page_creation_preview = None
        self.page_creation_preview_index = None
        self.open_profile_drivers = {}
        self.manual_2fa_code = ""
        self.manual_2fa_timer = QTimer(self)
        self.manual_2fa_timer.timeout.connect(self.update_manual_2fa_countdown)
        
        self.init_ui()
        self.load_data()

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout()

        # === CỘT TRÁI: QUẢN LÝ NICK ===
        left_layout = QVBoxLayout()
        
        # === SEARCH BAR ===
        search_layout = QHBoxLayout()
        search_label = QLabel("🔍 Tìm UID:")
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Nhập UID để tìm...")
        self.search_input.setMaximumWidth(250)
        self.search_input.textChanged.connect(self.filter_accounts_by_uid)
        
        btn_clear_search = QPushButton("🔄 Xóa Tìm")
        btn_clear_search.setMaximumWidth(80)
        btn_clear_search.clicked.connect(self.clear_search)
        
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(btn_clear_search)
        search_layout.addStretch()
        left_layout.addLayout(search_layout)
        
        toolbar = QHBoxLayout()
        btn_add = QPushButton("➕ Thêm"); btn_add.clicked.connect(self.add_account)
        btn_edit = QPushButton("✏️ Sửa"); btn_edit.clicked.connect(self.edit_account)
        btn_del = QPushButton("❌ Xóa"); btn_del.clicked.connect(self.delete_account)
        btn_import = QPushButton("📥 Import List"); btn_import.clicked.connect(self.import_accounts_list)
        btn_import.setStyleSheet("background-color: #3A8DFF; color: white; font-weight: bold;")
        self.btn_batch_login = QPushButton("🔐 Batch Login"); self.btn_batch_login.clicked.connect(self.batch_login_accounts)
        self.btn_batch_login.setStyleSheet("background-color: #FF6B35; color: white; font-weight: bold;")
        self.btn_login_all = QPushButton("🔐 Chạy Login Tất Cả")
        self.btn_login_all.clicked.connect(self.login_all_accounts)
        self.btn_login_all.setStyleSheet("background-color: #D35400; color: white; font-weight: bold;")
        self.btn_change_password = QPushButton("🔑 Đổi Pass"); self.btn_change_password.clicked.connect(self.batch_change_password)
        self.btn_change_password.setStyleSheet("background-color: #8E44AD; color: white; font-weight: bold;")
        self.btn_open_page_creator = None
        if self.platform == "facebook":
            self.btn_open_page_creator = QPushButton("📄 Mở Tạo Page")
            self.btn_open_page_creator.clicked.connect(self.open_page_creation_for_selected)
            self.btn_open_page_creator.setStyleSheet("background-color: #1877F2; color: white; font-weight: bold;")
        btn_open = QPushButton("🚀 Mở Chọn"); btn_open.clicked.connect(self.open_selected_profiles)
        
        # Style nút mở theo màu nền tảng
        btn_open.setStyleSheet(f"background-color: {self.theme_color}; color: white; font-weight: bold;")
        
        # Thêm nút chọn tất cả và bỏ chọn
        btn_sel_all = QPushButton("✅ Chọn Tất Cả"); btn_sel_all.clicked.connect(self.select_all_accounts)
        btn_sel_all.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        btn_desel = QPushButton("♻️ Bỏ Chọn"); btn_desel.clicked.connect(self.deselect_all_accounts)
        btn_desel.setStyleSheet("background-color: #FF9800; color: white; font-weight: bold;")
        
        toolbar.addWidget(btn_add); toolbar.addWidget(btn_edit); toolbar.addWidget(btn_del); toolbar.addWidget(btn_import); toolbar.addWidget(self.btn_batch_login); toolbar.addWidget(self.btn_login_all); toolbar.addWidget(self.btn_change_password)
        if self.btn_open_page_creator:
            toolbar.addWidget(self.btn_open_page_creator)
        toolbar.addWidget(btn_open)

        btn_check_live = QPushButton("🔎 Check Live")
        btn_check_live.clicked.connect(self.check_selected_accounts_live)
        btn_check_live.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold;")
        toolbar.addWidget(btn_check_live)

        toolbar.addWidget(btn_sel_all); toolbar.addWidget(btn_desel)
        
        # NEW: Buttons for selected/highlighted rows
        btn_sel_highlight = QPushButton("✅ Chọn Đã Highlight"); 
        btn_sel_highlight.clicked.connect(self.select_highlighted_accounts)
        btn_sel_highlight.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        toolbar.addWidget(btn_sel_highlight)
        
        btn_desel_highlight = QPushButton("♻️ Bỏ Chọn Đã Highlight"); 
        btn_desel_highlight.clicked.connect(self.deselect_highlighted_accounts)
        btn_desel_highlight.setStyleSheet("background-color: #FF9800; color: white; font-weight: bold;")
        toolbar.addWidget(btn_desel_highlight)
        
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["☑️  Chọn", "ID", "Tên", "Proxy", "Trạng Thái", "Trạng Thái Nick", "Action"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.account_checkboxes = {}  # Dictionary để lưu reference checkbox
        left_layout.addLayout(toolbar); left_layout.addWidget(self.table)

        # === CỘT PHẢI: CẤU HÌNH ===
        right_container = QWidget()
        right_container.setFixedWidth(480) # Tăng nhẹ độ rộng để hiển thị đẹp hơn
        right_layout = QVBoxLayout()
        right_container.setLayout(right_layout)

        self.tabs = QTabWidget()
        self.tab_farm = QWidget()
        self.tab_seed = QWidget()
        self.tab_pages = QWidget()
        self.tab_2fa = QWidget()
        self.tabs.addTab(self.tab_farm, "🌱 NUÔI & ĐĂNG BÀI")
        self.tabs.addTab(self.tab_seed, "🚀 SEEDING (BUFF)")
        if self.platform == "facebook":
            self.tabs.addTab(self.tab_pages, "📄 PAGE")
            self.tabs.addTab(self.tab_2fa, "🔐 2FA THỦ CÔNG")

        # Gọi các hàm setup giao diện chi tiết
        self.setup_farm_tab()
        self.setup_seed_tab()
        if self.platform == "facebook":
            self.setup_pages_tab()
            self.setup_manual_2fa_tab()

        # System Config
        grp_sys = QGroupBox("Hệ Thống")
        sys_l = QHBoxLayout()
        self.spin_threads = QSpinBox(); self.spin_threads.setValue(2)
        sys_l.addWidget(QLabel("Luồng chạy:")); sys_l.addWidget(self.spin_threads)
        grp_sys.setLayout(sys_l)

        # Start/Stop Buttons
        self.btn_start = QPushButton(f"▶ CHẠY {self.platform.upper()}")
        self.btn_start.setMinimumHeight(50)
        self.btn_start.setStyleSheet("background-color: green; color: white; font-weight: bold; font-size: 14px;")
        self.btn_start.clicked.connect(self.start_campaign)

        self.btn_stop = QPushButton("⏹ DỪNG & ĐÓNG CHROME")
        self.btn_stop.setMinimumHeight(40)
        self.btn_stop.setStyleSheet("background-color: #b30000; color: white;")
        self.btn_stop.clicked.connect(self.stop_campaign)
        self.btn_stop.setEnabled(False)

        right_layout.addWidget(self.tabs)
        right_layout.addWidget(grp_sys)
        right_layout.addWidget(self.btn_start)
        right_layout.addWidget(self.btn_stop)

        main_layout.addLayout(left_layout)
        main_layout.addWidget(right_container)
        main_widget.setLayout(main_layout)

    def setup_manual_2fa_tab(self):
        """Build a local TOTP generator for manual, user-confirmed 2FA entry."""
        layout = QVBoxLayout()

        info = QLabel(
            "Dán Secret Base32 hoặc chuỗi otpauth:// để tạo mã 2FA 6 số.\n"
            "Secret được xử lý cục bộ và không gửi tới dịch vụ bên ngoài."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        secret_box = QGroupBox("2FA Secret")
        secret_layout = QVBoxLayout()
        self.manual_2fa_secret = QTextEdit()
        self.manual_2fa_secret.setPlaceholderText("JBSWY3DPEHPK3PXP hoặc otpauth://totp/...")
        self.manual_2fa_secret.setMinimumHeight(100)
        secret_layout.addWidget(self.manual_2fa_secret)

        actions = QHBoxLayout()
        btn_generate = QPushButton("Tạo mã hiện tại")
        btn_generate.clicked.connect(self.generate_manual_2fa_code)
        btn_clear = QPushButton("Xóa")
        btn_clear.clicked.connect(self.clear_manual_2fa)
        actions.addWidget(btn_generate)
        actions.addWidget(btn_clear)
        secret_layout.addLayout(actions)
        secret_box.setLayout(secret_layout)
        layout.addWidget(secret_box)

        code_box = QGroupBox("2FA Code")
        code_layout = QVBoxLayout()
        self.manual_2fa_code_edit = QLineEdit()
        self.manual_2fa_code_edit.setReadOnly(True)
        self.manual_2fa_code_edit.setAlignment(Qt.AlignCenter)
        self.manual_2fa_code_edit.setStyleSheet("font-size: 24px; font-weight: bold; letter-spacing: 4px;")
        code_layout.addWidget(self.manual_2fa_code_edit)

        code_actions = QHBoxLayout()
        btn_copy = QPushButton("Copy mã")
        btn_copy.clicked.connect(self.copy_manual_2fa_code)
        self.manual_2fa_countdown = QLabel("Chưa tạo mã")
        self.manual_2fa_countdown.setAlignment(Qt.AlignCenter)
        code_actions.addWidget(btn_copy)
        code_actions.addWidget(self.manual_2fa_countdown, 1)
        code_layout.addLayout(code_actions)
        code_box.setLayout(code_layout)
        layout.addWidget(code_box)
        layout.addStretch()

        self.tab_2fa.setLayout(layout)

    def generate_manual_2fa_code(self):
        secret = self.manual_2fa_secret.toPlainText().strip()
        if not secret:
            self.manual_2fa_code_edit.clear()
            self.manual_2fa_countdown.setText("Chưa nhập Secret")
            QMessageBox.warning(self, "2FA", "Vui lòng nhập Secret Base32 hoặc otpauth://.")
            return

        try:
            self.manual_2fa_code = generate_totp(secret)
        except ValueError as exc:
            self.manual_2fa_code = ""
            self.manual_2fa_code_edit.clear()
            self.manual_2fa_countdown.setText("Secret không hợp lệ")
            QMessageBox.warning(self, "2FA", str(exc))
            return
        except Exception as exc:
            self.manual_2fa_code = ""
            self.manual_2fa_code_edit.clear()
            self.manual_2fa_countdown.setText("Không tạo được mã")
            QMessageBox.warning(self, "2FA", f"Không tạo được mã: {exc}")
            return

        self.manual_2fa_code_edit.setText(self.manual_2fa_code)
        self.update_manual_2fa_countdown()
        self.manual_2fa_timer.start(1000)

    def update_manual_2fa_countdown(self):
        if not self.manual_2fa_code:
            self.manual_2fa_countdown.setText("Chưa tạo mã")
            return
        remaining = totp_seconds_remaining()
        self.manual_2fa_countdown.setText(f"Còn {remaining}s")

    def copy_manual_2fa_code(self):
        if not self.manual_2fa_code:
            QMessageBox.information(self, "2FA", "Hãy tạo mã trước khi Copy.")
            return
        QGuiApplication.clipboard().setText(self.manual_2fa_code)
        self.manual_2fa_countdown.setText("Đã Copy mã")

    def clear_manual_2fa(self):
        self.manual_2fa_secret.clear()
        self.manual_2fa_code = ""
        self.manual_2fa_code_edit.clear()
        self.manual_2fa_countdown.setText("Chưa tạo mã")
        self.manual_2fa_timer.stop()

    # --- SETUP TAB NUÔI (FARM) - Đã tách nhóm ---
    def setup_farm_tab(self):
        # Tạo vùng cuộn (Scroll Area)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content_widget = QWidget()
        self.farm_layout = QVBoxLayout(content_widget)
        
        # Dictionary lưu trữ widget Farm
        self.farm_ui_groups = {
            "post": {},
            "action": {}
        }

        # --- A. PHẦN ĐĂNG BÀI (POSTING) ---
        lbl_post = QLabel("A. CẤU HÌNH ĐĂNG BÀI"); lbl_post.setStyleSheet("font-weight: bold; color: #d32f2f; font-size: 13px; margin-top: 10px;")
        self.farm_layout.addWidget(lbl_post)

        # 1. Nhóm Status / Video TikTok
        label_status = "Đăng Status (Kèm Ảnh/Video)" if self.platform == "facebook" else "Đăng Video TikTok"
        self.create_farm_post_group("status", label_status, has_caption=True)

        # 2. Nhóm Reels (Chỉ FB mới tách riêng, TikTok gộp vào trên)
        if self.platform == "facebook":
            self.create_farm_post_group("reels", "Đăng Reels (Video Ngắn)", has_caption=True)

        # 3. Nhóm Story
        self.create_farm_post_group("story", "Đăng Story (Tin)", has_caption=False)

        # --- B. PHẦN TƯƠNG TÁC (ACTIONS) ---
        self.farm_layout.addWidget(QLabel("")) # Spacer
        lbl_act = QLabel("B. CẤU HÌNH TƯƠNG TÁC NUÔI"); lbl_act.setStyleSheet("font-weight: bold; color: #2e7d32; font-size: 13px;")
        self.farm_layout.addWidget(lbl_act)

        # 1. Lướt Feed
        label_feed = "Lướt Newsfeed" if self.platform == "facebook" else "Lướt For You (Dành cho bạn)"
        self.create_farm_action_group("feed", label_feed, "Thời gian:", "phút", 3, 5)

        # 2. Xem Watch
        label_watch = "Xem Video Watch" if self.platform == "facebook" else "Ngâm Video (Deep Watch)"
        self.create_farm_action_group("watch", label_watch, "Thời gian:", "phút", 5, 10)

        # 3. Kết bạn / Follow
        label_friend = "Kết bạn Gợi ý" if self.platform == "facebook" else "Follow Chủ kênh"
        unit_friend = "người" if self.platform == "facebook" else "lần"
        self.create_farm_action_group("friend", label_friend, "Số lượng:", unit_friend, 1, 3)

        # 4. Tham gia nhóm (Chỉ FB)
        if self.platform == "facebook":
            self.create_farm_action_group("group", "Tham gia Nhóm", "Số lượng:", "nhóm", 0, 2)
        
        # 5. Thông báo
        self.chk_notify = QCheckBox("Check Thông báo (Notification)")
        self.chk_notify.setChecked(True)
        self.farm_layout.addWidget(self.chk_notify)

        self.farm_layout.addStretch()
        scroll.setWidget(content_widget)
        
        # Add Scroll vào Tab Farm
        layout = QVBoxLayout()
        layout.addWidget(scroll)
        self.tab_farm.setLayout(layout)

    # --- SETUP TAB SEEDING (BUFF) - Đã tách nhóm ---
    def setup_seed_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content_widget = QWidget()
        self.seed_layout = QVBoxLayout(content_widget)
        self.seed_ui_groups = {}

        # --- 1. NHÓM BUFF FOLLOW (TÁCH RIÊNG) ---
        label_follow = "Tăng Follow/Like Page" if self.platform == "facebook" else "Tăng Follow Kênh TikTok"
        self.create_seed_group("follow", label_follow, show_comment=False, show_like_post=False)

        # --- 2. NHÓM BUFF BÀI VIẾT (POST) ---
        label_post = "Tăng Like/Cmt Bài Viết" if self.platform == "facebook" else "Tăng Tim/Cmt Video"
        self.create_seed_group("post", label_post, show_comment=True, show_like_post=True)

        # --- 3. NHÓM BUFF REELS ---
        if self.platform == "facebook":
            self.create_seed_group("reels", "Tăng Like/Cmt Reels", show_comment=True, show_like_post=True)

        # --- 4. NHÓM BUFF STORY ---
        self.create_seed_group("story", "Tăng View/Tim Story", show_comment=True, show_like_post=True)

        self.seed_layout.addStretch()
        scroll.setWidget(content_widget)
        
        # Add Scroll vào Tab Seed
        main_layout = QVBoxLayout()
        main_layout.addWidget(scroll)
        self.tab_seed.setLayout(main_layout)

    def setup_pages_tab(self):
        layout = QVBoxLayout()

        # Multi-line toolbar cho tab PAGE - tránh chen chúc
        page_toolbar = QVBoxLayout()
        
        row1 = QHBoxLayout()
        btn_add_page = QPushButton("➕ Thêm Page"); btn_add_page.clicked.connect(self.add_page)
        btn_edit_page = QPushButton("✏️ Sửa Page"); btn_edit_page.clicked.connect(self.edit_page)
        btn_del_page = QPushButton("❌ Xóa Page"); btn_del_page.clicked.connect(self.delete_page)
        row1.addWidget(btn_add_page)
        row1.addWidget(btn_edit_page)
        row1.addWidget(btn_del_page)
        
        row2 = QHBoxLayout()
        btn_sync_page = QPushButton("Sync Nick"); btn_sync_page.clicked.connect(self.sync_selected_page_credentials)
        btn_sync_all_pages = QPushButton("Sync Tất Cả"); btn_sync_all_pages.clicked.connect(self.sync_all_page_credentials)
        btn_capture_page = QPushButton("Lấy Page Từ Browser"); btn_capture_page.clicked.connect(self.capture_pages_from_open_browsers)
        row2.addWidget(btn_sync_page)
        row2.addWidget(btn_sync_all_pages)
        row2.addWidget(btn_capture_page)
        
        row3 = QHBoxLayout()
        btn_scrape_page = QPushButton("📊 Cào Dữ Liệu"); btn_scrape_page.clicked.connect(self.scrape_selected_page)
        btn_open_page = QPushButton("🚀 Mở Page"); btn_open_page.clicked.connect(self.open_selected_pages)
        btn_open_page.setStyleSheet(f"background-color: {self.theme_color}; color: white; font-weight: bold;")
        row3.addWidget(btn_scrape_page)
        row3.addWidget(btn_open_page)
        row3.addStretch()  # Spacer
        
        page_toolbar.addLayout(row1)
        page_toolbar.addLayout(row2)
        page_toolbar.addLayout(row3)

        self.pages_table = QTableWidget()
        self.pages_table.setColumnCount(4)
        self.pages_table.setHorizontalHeaderLabels(["Account ID", "Page Name", "Page URL", "Page ID"])
        self.pages_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.pages_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.pages_table.setSelectionMode(QAbstractItemView.SingleSelection)

        preview_box = QGroupBox("Dữ Liệu Tạo Page Tiếp Theo")
        preview_layout = QVBoxLayout()
        self.lbl_page_preview_name = QLabel("Tên: -")
        self.lbl_page_preview_category = QLabel("Ngành: -")
        self.lbl_page_preview_desc = QLabel("Mô tả: -")
        self.lbl_page_preview_desc.setWordWrap(True)

        preview_actions = QHBoxLayout()
        btn_refresh_preview = QPushButton("Làm Mới")
        btn_refresh_preview.clicked.connect(self.refresh_page_creation_preview)
        btn_copy_page_name = QPushButton("Copy Tên")
        btn_copy_page_name.clicked.connect(lambda: self.copy_page_creation_field("name"))
        btn_copy_page_category = QPushButton("Copy Ngành")
        btn_copy_page_category.clicked.connect(lambda: self.copy_page_creation_field("category"))
        btn_copy_page_desc = QPushButton("Copy Mô Tả")
        btn_copy_page_desc.clicked.connect(lambda: self.copy_page_creation_field("description"))
        preview_actions.addWidget(btn_refresh_preview)
        preview_actions.addWidget(btn_copy_page_name)
        preview_actions.addWidget(btn_copy_page_category)
        preview_actions.addWidget(btn_copy_page_desc)

        preview_layout.addWidget(self.lbl_page_preview_name)
        preview_layout.addWidget(self.lbl_page_preview_category)
        preview_layout.addWidget(self.lbl_page_preview_desc)
        preview_layout.addLayout(preview_actions)
        preview_box.setLayout(preview_layout)

        layout.addLayout(page_toolbar)
        layout.addWidget(preview_box)
        layout.addWidget(self.pages_table)
        self.tab_pages.setLayout(layout)

    # --- UI HELPER FUNCTIONS ---

    def create_farm_post_group(self, key, title, has_caption=True):
        group = QGroupBox(title)
        group.setCheckable(True)
        group.setChecked(False)
        lo = QVBoxLayout()

        # 1. Chọn File Media + Cấu hình số lượng
        h_file = QHBoxLayout()
        btn_file = QPushButton("📁 Chọn Kho Media")
        lbl_file = QLabel("0 file")
        btn_file.clicked.connect(lambda: self.select_media_for_label(lbl_file))
        
        # Thêm cấu hình số lượng ảnh/video mỗi bài
        h_file.addWidget(btn_file)
        h_file.addWidget(lbl_file)
        
        # Chỉ hiện chọn số lượng nếu là Status (Reels/Story thường chỉ 1 video)
        spin_min = QSpinBox(); spin_min.setRange(1, 10); spin_min.setValue(1)
        spin_max = QSpinBox(); spin_max.setRange(1, 20); spin_max.setValue(1)
        
        # Nếu là Status thì cho chọn nhiều, còn Reels/Story mặc định là 1
        if key == 'status':
            h_file.addWidget(QLabel("| Lấy Random:"))
            h_file.addWidget(spin_min)
            h_file.addWidget(QLabel("-"))
            h_file.addWidget(spin_max)
            h_file.addWidget(QLabel("file"))
            spin_max.setValue(3) # Mặc định status lấy 1-3 ảnh
        else:
            # Ẩn đi nhưng vẫn cần khởi tạo để code không lỗi
            spin_min.setVisible(False); spin_max.setVisible(False)

        lo.addLayout(h_file)

        # 2. Ô nhập caption (Hỗ trợ Spin)
        txt_cap = None
        if has_caption:
            lo.addWidget(QLabel("Nội dung (Mỗi dòng 1 nội dung để Random):"))
            txt_cap = QTextEdit()
            txt_cap.setPlaceholderText(f"Nhập nội dung 1...\nNhập nội dung 2...\n(Tool sẽ chọn ngẫu nhiên 1 dòng để đăng)")
            txt_cap.setFixedHeight(80) # Cao hơn chút để nhập nhiều
            lo.addWidget(txt_cap)

        group.setLayout(lo)
        self.farm_layout.addWidget(group)

        # Lưu UI lại
        self.farm_ui_groups["post"][key] = {
            "group": group,
            "lbl_file": lbl_file,
            "min": spin_min,
            "max": spin_max,
            "content": txt_cap
        }

    def create_farm_action_group(self, key, title, label_range, unit, min_def, max_def):
        group = QGroupBox(title)
        group.setCheckable(True)
        group.setChecked(True)
        
        h = QHBoxLayout()
        h.addWidget(QLabel(label_range))
        s_min = QSpinBox(); s_min.setRange(0, 999); s_min.setValue(min_def)
        s_max = QSpinBox(); s_max.setRange(0, 999); s_max.setValue(max_def)
        h.addWidget(s_min); h.addWidget(QLabel("-")); h.addWidget(s_max); h.addWidget(QLabel(unit))
        
        group.setLayout(h)
        self.farm_layout.addWidget(group)

        self.farm_ui_groups["action"][key] = {
            "group": group,
            "min": s_min,
            "max": s_max
        }

    def create_seed_group(self, key, title, show_comment=True, show_like_post=True):
        group = QGroupBox(title)
        group.setCheckable(True)
        group.setChecked(False)
        if key == 'follow':
            group.setStyleSheet("QGroupBox { font-weight: bold; border: 2px solid #0078d7; margin-top: 10px; } QGroupBox::title { color: #0078d7; }")
        
        layout = QVBoxLayout()
        
        # Link Input
        h_link = QHBoxLayout()
        txt_url = QLineEdit()
        placeholder = "Link Page/Profile..." if key == 'follow' else f"Link {title}..."
        txt_url.setPlaceholderText(placeholder)
        h_link.addWidget(QLabel("Link:")); h_link.addWidget(txt_url)
        layout.addLayout(h_link)

        # Action
        h_act = QHBoxLayout()
        ui_elements = {"group": group, "url": txt_url, "like": None, "comment": None, "content": None}

        if key == 'follow':
            lbl = QLabel("✅ Chế độ: Chỉ vào Link và bấm Theo dõi/Thích trang")
            h_act.addWidget(lbl)
        else:
            if show_like_post:
                chk_like = QCheckBox("Like/Tim Bài")
                chk_like.setChecked(True)
                h_act.addWidget(chk_like)
                ui_elements["like"] = chk_like
            
            if show_comment:
                chk_comment = QCheckBox("Comment")
                chk_comment.setChecked(True)
                h_act.addWidget(chk_comment)
                ui_elements["comment"] = chk_comment
        
        layout.addLayout(h_act)

        # Comment Input
        if show_comment:
            layout.addWidget(QLabel("Nội dung Comment:"))
            txt_cmt = QTextEdit()
            txt_cmt.setPlaceholderText("Nhập nội dung... (Mỗi dòng 1 comment)")
            txt_cmt.setFixedHeight(60)
            layout.addWidget(txt_cmt)
            ui_elements["content"] = txt_cmt

        group.setLayout(layout)
        self.seed_layout.addWidget(group)
        self.seed_ui_groups[key] = ui_elements

    # --- LOGIC CONTROL ---
    def select_media_for_label(self, label_widget):
        fs, _ = QFileDialog.getOpenFileNames(self, 'Media', '', "Files (*.jpg *.png *.mp4)")
        if fs:
            label_widget.setText(f"Đã chọn {len(fs)} file")
            label_widget.setProperty("file_paths", fs) 
        else:
            label_widget.setText("Chưa chọn file")
            label_widget.setProperty("file_paths", [])

    def get_config(self):
        mode = "farm" if self.tabs.currentIndex() == 0 else "seed"
        
        # --- LẤY CONFIG FARM ---
        ui_posts = self.farm_ui_groups["post"]
        ui_acts = self.farm_ui_groups["action"]
        
        # Gom file media (Ưu tiên lấy từ nhóm Status -> Reels -> Story)
        active_post_type = None
        media_files = []
        captions_list = []
        media_range = (1, 1)
        for k in ["status", "reels", "story"]:
            if k in ui_posts and ui_posts[k]["group"].isChecked():
                active_post_type = k
                # 1. Lấy Media
                media_files = ui_posts[k]["lbl_file"].property("file_paths") or []
                # 2. Lấy Range (Min-Max)
                media_range = (ui_posts[k]["min"].value(), ui_posts[k]["max"].value())
                # 3. Lấy Caption (Tách dòng thành List)
                raw_txt = ui_posts[k]["content"].toPlainText() if ui_posts[k]["content"] else ""
                captions_list = [line.strip() for line in raw_txt.split('\n') if line.strip()]
                break

        post_config = {
            "enable": (active_post_type is not None),
            "type": active_post_type, # 'status', 'reels', 'story'
            "captions": captions_list,     # Danh sách nội dung
            "media_files": media_files,    # Kho media tổng
            "media_range": media_range     # (min, max)
        }

        farm_config = {
            "enable": any(a["group"].isChecked() for a in ui_acts.values()) or self.chk_notify.isChecked(),
            "feed": ui_acts["feed"]["group"].isChecked(),
            "feed_range": (ui_acts["feed"]["min"].value(), ui_acts["feed"]["max"].value()),
            
            "watch": ui_acts["watch"]["group"].isChecked(),
            "watch_range": (ui_acts["watch"]["min"].value(), ui_acts["watch"]["max"].value()),
            
            "friend": ui_acts["friend"]["group"].isChecked(),
            "friend_range": (ui_acts["friend"]["min"].value(), ui_acts["friend"]["max"].value()),
            
            "group": ui_acts["group"]["group"].isChecked() if "group" in ui_acts else False,
            "group_range": (ui_acts["group"]["min"].value(), ui_acts["group"]["max"].value()) if "group" in ui_acts else (0,0),
            
            "notify": self.chk_notify.isChecked()
        }

        # --- LẤY CONFIG SEEDING ---
        seed_tasks = []
        if mode == 'seed':
            for key, ui in self.seed_ui_groups.items():
                if ui["group"].isChecked():
                    url = ui["url"].text().strip()
                    if url:
                        do_follow = True if key == 'follow' else False
                        do_like = ui["like"].isChecked() if ui.get("like") else False
                        do_comment = ui["comment"].isChecked() if ui.get("comment") else False
                        
                        comments = []
                        if ui.get("content"):
                            comments = [line.strip() for line in ui["content"].toPlainText().split('\n') if line.strip()]

                        seed_tasks.append({
                            "type": key, 
                            "url": url, 
                            "do_follow": do_follow,
                            "do_like": do_like, 
                            "do_comment": do_comment, 
                            "comments_list": comments
                        })

        return {
            "mode": mode,
            "threads": self.spin_threads.value(),
            "post": post_config,
            "farm": farm_config,
            "seed_tasks": seed_tasks
        }

    # --- CAMPAIGN MANAGEMENT ---
    def start_campaign(self):
        if self.batch_login_workers or self.batch_login_queue:
            QMessageBox.warning(self, "Đang login", "Hãy dừng luồng login hàng loạt trước khi chạy campaign.")
            return

        config = self.get_config()
        if config['mode'] == 'seed':
            if not config['seed_tasks']:
                QMessageBox.warning(self, "Lỗi", "Vui lòng chọn ít nhất 1 nhóm Seeding và nhập Link!"); return
        
        # Get selected accounts from checkboxes
        selected_indices = [i for i, chk in self.account_checkboxes.items() if chk.isChecked()]
        if not selected_indices:
            QMessageBox.warning(self, "Lỗi", "Vui lòng chọn ít nhất 1 nick để chạy!"); return
        
        # Build queue with only selected accounts
        self.config = config; self.max_threads = config['threads']
        self.queue = []
        for i in selected_indices:
            self.queue.append((i, self.accounts[i]))
        
        selected_count = len(selected_indices)
        QMessageBox.information(self, "Thông báo", f"Đã chọn {selected_count} nick để chạy!\nChương trình sẽ bắt đầu...")
        
        self.btn_start.setEnabled(False); self.btn_stop.setEnabled(True); self.tabs.setEnabled(False)
        self.process_queue()

    def process_queue(self):
        while len(self.workers) < self.max_threads and self.queue:
            job = self.queue.pop(0)
            if len(job) == 2:
                i, acc = job
                worker_config = self.config
            elif len(job) == 3:
                i, acc, worker_config = job
            else:
                raise ValueError(f"Invalid queue item format: {job!r}")

            w = FarmWorker(i, acc, self.platform, worker_config)
            w.signals.status.connect(self.update_status)
            w.signals.finished.connect(self.on_worker_done)
            self.workers[i] = w; w.start()

    def stop_campaign(self):
        login_was_running = bool(
            self.batch_login_workers
            or self.batch_login_queue
            or self.single_login_workers
        )
        if login_was_running:
            self.stop_batch_login()

        # A per-row Login now runs in a background QThread as well. Request
        # cancellation without waiting on the Selenium thread, otherwise the
        # stop button could freeze the UI while Chrome is closing.
        for worker in list(self.single_login_workers.values()):
            try:
                worker.stop()
            except Exception:
                pass

        # Also close browsers opened by the per-row Login / Mở Chọn action.
        # They are not owned by a worker, so they need to be cleaned up here.
        for driver in list(self.open_profile_drivers.values()):
            try:
                driver.quit()
            except Exception:
                pass
        self.open_profile_drivers.clear()

        self.queue.clear()
        for w in self.workers.values():
            try:
                # TẮT CHROME TRIỆT ĐỂ
                if hasattr(w, 'bot') and w.bot and hasattr(w.bot, 'driver') and w.bot.driver:
                    try: w.bot.driver.quit()
                    except: pass
                w.stop(); w.quit(); w.wait()
            except: pass

        self.workers.clear()
        self.btn_start.setEnabled(True)
        self.tabs.setEnabled(True)
        if not self.batch_login_workers and not self.batch_login_queue and not self.single_login_workers:
            self.btn_stop.setEnabled(False)
            self.btn_stop.setText("⏹ DỪNG & ĐÓNG CHROME")
        if not login_was_running:
            QMessageBox.information(self, "Đã Dừng", "Đã dừng chạy và đóng toàn bộ trình duyệt!")

    # --- DATA MANAGEMENT ---
    def load_data(self):
        if not os.path.exists("data"): os.makedirs("data")
        if os.path.exists(self.data_file):
            with open(self.data_file, 'r', encoding='utf-8') as f: self.accounts = json.load(f)
        page_data_changed = False
        if self.platform == "facebook" and os.path.exists(self.pages_file):
            with open(self.pages_file, 'r', encoding='utf-8') as f:
                self.pages = json.load(f)
            page_data_changed = self._backfill_page_records()
        self.refresh_table()
        if self.platform == "facebook" and hasattr(self, "pages_table"):
            self.refresh_pages_table()
        if self.platform == "facebook":
            self.refresh_page_creation_preview()
        if page_data_changed:
            self.save_data()
    
    def save_data(self):
        with open(self.data_file, 'w', encoding='utf-8') as f: json.dump(self.accounts, f, ensure_ascii=False, indent=4)
        if self.platform == "facebook":
            self._backfill_page_records()
            with open(self.pages_file, 'w', encoding='utf-8') as f:
                json.dump(self.pages, f, ensure_ascii=False, indent=4)
    
    def refresh_table(self):
        self.table.setRowCount(0)
        self.account_checkboxes = {}  # Reset checkboxes
        for i, acc in enumerate(self.accounts):
            self.table.insertRow(i)
            
            # Thêm checkbox ở cột 0
            chk = QCheckBox()
            chk_widget = QWidget()
            chk_layout = QHBoxLayout(chk_widget)
            chk_layout.addWidget(chk)
            chk_layout.setContentsMargins(5, 0, 5, 0)
            chk_widget.setLayout(chk_layout)
            self.table.setCellWidget(i, 0, chk_widget)
            self.account_checkboxes[i] = chk  # Lưu reference
            
            # Các cột khác shift sang phải 1 vị trí
            self.table.setItem(i, 1, QTableWidgetItem(acc['id']))
            self.table.setItem(i, 2, QTableWidgetItem(acc['name']))
            self.table.setItem(i, 3, QTableWidgetItem(acc.get('proxy', '')))
            self.table.setItem(i, 4, QTableWidgetItem(acc.get('status', 'Sẵn sàng')))
            self.table.setItem(i, 5, QTableWidgetItem(acc.get('last_live_status', 'Chưa check')))
            btn = QPushButton("Login"); btn.clicked.connect(lambda _, r=i: self.manual_login(r))
            self.table.setCellWidget(i, 6, btn)

    def refresh_pages_table(self):
        self.pages_table.setRowCount(0)
        for i, page in enumerate(self.pages):
            self.pages_table.insertRow(i)
            self.pages_table.setItem(i, 0, QTableWidgetItem(page.get('account_id', '')))
            self.pages_table.setItem(i, 1, QTableWidgetItem(page.get('page_name', '')))
            self.pages_table.setItem(i, 2, QTableWidgetItem(page.get('page_url', '')))
            self.pages_table.setItem(i, 3, QTableWidgetItem(page.get('page_id', '')))

    def _account_choices(self):
        return [(acc.get('id', ''), f"{acc.get('id', '')} | {acc.get('name', '')}") for acc in self.accounts]

    def _build_page_login_account(self, account):
        if not account:
            return {}
        return {
            "id": account.get("id", ""),
            "name": account.get("name", "") or account.get("id", ""),
            "password": account.get("password", ""),
            "cookie": account.get("cookie", ""),
            "token": account.get("token", ""),
            "email": account.get("email", ""),
            "email_password": account.get("email_password", ""),
            "2fa_code": account.get("2fa_code", ""),
            "proxy": account.get("proxy", ""),
        }

    def _ensure_page_metadata(self, page, sync_login=False):
        if not page:
            return False

        changed = False
        account = next((acc for acc in self.accounts if acc.get("id") == page.get("account_id")), None)
        if account and (sync_login or not page.get("login_account")):
            login_account = self._build_page_login_account(account)
            if page.get("login_account") != login_account:
                page["login_account"] = login_account
                changed = True

        base_key = page.get("page_id") or page.get("page_name") or page.get("account_id") or "page"
        safe_key = re.sub(r"[^A-Za-z0-9._-]+", "_", str(base_key)).strip("_") or "page"
        desired_profile_key = f"{page.get('account_id', 'page')}_{safe_key}"
        if page.get("profile_key") != desired_profile_key:
            page["profile_key"] = desired_profile_key
            changed = True

        return changed

    def _backfill_page_records(self):
        changed = False
        for page in self.pages:
            if self._ensure_page_metadata(page, sync_login=False):
                changed = True
        return changed

    def _peek_next_page_data(self, file_path="data_name_page.txt"):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f if "|" in line and line.strip()]
        except Exception:
            return None, None

        if not lines:
            return None, None

        index = CURRENT_INDEX if CURRENT_INDEX < len(lines) else 0
        parts = [part.strip() for part in lines[index].split("|")]
        if len(parts) < 4:
            return None, None

        return {
            "industry": parts[0],
            "name": parts[1],
            "description": parts[2],
            "category": parts[3],
        }, index

    def refresh_page_creation_preview(self):
        data, index = self._peek_next_page_data()
        self.page_creation_preview = data
        self.page_creation_preview_index = index

        if not hasattr(self, "lbl_page_preview_name"):
            return

        if not data:
            self.lbl_page_preview_name.setText("Tên: -")
            self.lbl_page_preview_category.setText("Ngành: -")
            self.lbl_page_preview_desc.setText("Mô tả: Không có dữ liệu trong data_name_page.txt")
            return

        suffix = f" (Dòng {index + 1})" if index is not None else ""
        self.lbl_page_preview_name.setText(f"Tên: {data['name']}{suffix}")
        self.lbl_page_preview_category.setText(f"Ngành: {data['category']} | Chủ đề: {data['industry']}")
        self.lbl_page_preview_desc.setText(f"Mô tả: {data['description']}")

    def copy_page_creation_field(self, field_name):
        if not self.page_creation_preview:
            self.refresh_page_creation_preview()
        if not self.page_creation_preview:
            QMessageBox.warning(self, "Cảnh báo", "Không có dữ liệu page để copy.")
            return

        field_map = {
            "name": self.page_creation_preview.get("name", ""),
            "category": self.page_creation_preview.get("category", ""),
            "description": self.page_creation_preview.get("description", ""),
        }
        value = field_map.get(field_name, "")
        if not value:
            QMessageBox.warning(self, "Cảnh báo", "Trường này đang trống.")
            return

        QGuiApplication.clipboard().setText(value)
        QMessageBox.information(self, "Đã copy", f"Đã copy {field_name}.")

    def _extract_page_id_from_url(self, url):
        if not url:
            return ""
        match = re.search(r"[?&]id=(\d+)", url)
        if match:
            return match.group(1)
        match = re.search(r"/pages/[^/]+/(\d+)", url)
        if match:
            return match.group(1)
        return ""

    def capture_pages_from_open_browsers(self):
        if self.platform != "facebook":
            return

        rows = self._selected_rows_from_ui()
        if not rows:
            QMessageBox.warning(self, "Cảnh báo", "Chọn nick đã mở browser trước khi lấy Page.")
            return

        from facebook.fb_tasks import FacebookBot
        import time

        total_captured = 0
        total_switched = 0
        skipped = []
        last_page_info = {}

        for row in rows:
            if row < 0 or row >= len(self.accounts):
                continue
            account = self.accounts[row]
            account_id = account.get("id")
            driver = self.open_profile_drivers.get(account_id)
            if not driver:
                skipped.append(f"{account_id}: chưa có browser đang mở")
                continue

            try:
                # Navigate to account's pages list
                pages_url = f"https://www.facebook.com/{account_id}/pages/"
                print(f"Navigating to pages list: {pages_url}")
                driver.get(pages_url)
                time.sleep(5)

                bot = FacebookBot(driver)
                
                # Scrape page links - improved selectors
                from selenium.webdriver.common.by import By
                page_links = driver.find_elements(By.XPATH, 
                    "//a[contains(@href, 'profile.php?id=') or (contains(@href, 'facebook.com/') and (contains(@href, '615') or contains(@href, 'id=')))]"
                )
                
                captured_this_account = 0
                pages_this_account = []
                
                for link in page_links[:10]:  # Limit to first 10 visible pages
                    try:
                        href = link.get_attribute("href") or ""
                        # Extract page name from link text or title
                        page_name_candidates = [
                            link.get_attribute("aria-label"),
                            link.text.strip(),
                            link.find_element(By.XPATH, ".//span | .//div[@dir='auto']").text.strip() if link.find_elements(By.XPATH, ".//span | .//div[@dir='auto']") else ""
                        ]
                        page_name = next((name for name in page_name_candidates if name and len(name) > 3), f"Page_{account_id}")
                        page_name = page_name[:50]  # Truncate long names
                        
                        page_id = self._extract_page_id_from_url(href)
                        if not page_id or len(page_id) < 10:
                            continue
                            
                        # Avoid duplicates
                        if next((p for p in self.pages if p.get("account_id") == account_id and p.get("page_id") == page_id), None):
                            continue
                        
                        # Save new page
                        page = {
                            "account_id": account_id,
                            "page_name": page_name,
                            "page_url": href,
                            "page_id": page_id,
                        }
                        self._ensure_page_metadata(page, sync_login=True)
                        self.pages.append(page)
                        pages_this_account.append(page)
                        captured_this_account += 1
                        
                        print(f"✅ Captured: {page_name} ({page_id[:20]}...)")
                    except Exception as link_error:
                        print(f"⚠️ Skip link: {link_error}")
                        continue
                
                total_captured += captured_this_account
                
                # Auto-switch to LAST captured page
                if pages_this_account:
                    last_page = pages_this_account[-1]
                    if bot.switch_to_page_context(last_page["page_name"], last_page["page_id"]):
                        total_switched += 1
                        last_page_info[account_id] = last_page["page_name"]
                        print(f"🔄 Switched browser to: {last_page['page_name']}")
                    else:
                        print(f"⚠️ Failed switch for {last_page['page_name']}")
                
            except Exception as account_error:
                print(f"❌ Account {account_id} error: {account_error}")
                skipped.append(f"{account_id}: lỗi xử lý")

                if total_captured > 0:
                    self.save_data()
                    self.refresh_pages_table()
                    # Auto-select last captured page row
                    if self.pages:
                        self.pages_table.selectRow(len(self.pages) - 1)

        # Rich feedback
        message = f"🚀 **CAPTURE COMPLETE**\\n\\n"
        message += f"✅ **{total_captured} pages** từ **{len(rows)} accounts**\\n"
        if total_switched > 0:
            message += f"🔄 **Auto-switched {total_switched} browsers** sang page context\\n\\n"
        if last_page_info:
            message += "**📋 Browsers ở page cuối:**\\n"
            for acc_id, pg_name in last_page_info.items():
                message += f"  • {acc_id}: **{pg_name}**\\n"
        
        if skipped:
            message += f"\\n⚠️ **Skipped:**\\n" + "\\n".join(skipped[:5])
        
        QMessageBox.information(self, "Capture Hoàn Thành", message)

        # message = f"Đã lưu {captured} page từ browser đang mở."
        if skipped:
            message += "\n\nBỏ qua:\n" + "\n".join(skipped[:10])
        QMessageBox.information(self, "Hoàn thành", message)

    def _page_dialog(self, page=None):
        dialog = QDialog(self)
        dialog.setWindowTitle("Page")
        layout = QFormLayout(dialog)

        account_combo = QComboBox()
        choices = self._account_choices()
        for account_id, label in choices:
            account_combo.addItem(label, account_id)

        page_name = QLineEdit(page.get('page_name', '') if page else '')
        page_url = QLineEdit(page.get('page_url', '') if page else '')
        page_id = QLineEdit(page.get('page_id', '') if page else '')

        if page:
            current_account_id = page.get('account_id', '')
            for idx, (account_id, _) in enumerate(choices):
                if account_id == current_account_id:
                    account_combo.setCurrentIndex(idx)
                    break

        layout.addRow("Account:", account_combo)
        layout.addRow("Page Name:", page_name)
        layout.addRow("Page URL:", page_url)
        layout.addRow("Page ID:", page_id)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec_() != QDialog.Accepted:
            return None

        return {
            "account_id": account_combo.currentData(),
            "page_name": page_name.text().strip(),
            "page_url": page_url.text().strip(),
            "page_id": page_id.text().strip(),
        }

    def add_page(self):
        if not self.accounts:
            QMessageBox.warning(self, "Cảnh báo", "Chưa có account Facebook để gán Page.")
            return
        page = self._page_dialog()
        if not page or not page.get("account_id"):
            return
        self._ensure_page_metadata(page, sync_login=True)
        self.pages.append(page)
        self.save_data()
        self.refresh_pages_table()

    def edit_page(self):
        row = self.pages_table.currentRow()
        if row < 0:
            return
        page = self._page_dialog(self.pages[row])
        if not page or not page.get("account_id"):
            return
        self._ensure_page_metadata(page, sync_login=True)
        self.pages[row] = page
        self.save_data()
        self.refresh_pages_table()

    def sync_selected_page_credentials(self):
        row = self.pages_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Cảnh báo", "Chưa chọn Page nào để sync.")
            return

        page = self.pages[row]
        account = next((acc for acc in self.accounts if acc.get("id") == page.get("account_id")), None)
        if not account:
            QMessageBox.warning(self, "Lỗi", "Không tìm thấy nick gốc của Page này.")
            return

        self._ensure_page_metadata(page, sync_login=True)
        self.save_data()
        self.refresh_pages_table()
        QMessageBox.information(self, "Thành công", f"Đã sync credential cho Page {page.get('page_id') or page.get('page_name')}.")

    def sync_all_page_credentials(self):
        if not self.pages:
            QMessageBox.warning(self, "Cảnh báo", "Chưa có Page nào để sync.")
            return

        synced = 0
        missing = 0
        for page in self.pages:
            account = next((acc for acc in self.accounts if acc.get("id") == page.get("account_id")), None)
            if not account:
                missing += 1
                continue
            self._ensure_page_metadata(page, sync_login=True)
            synced += 1

        self.save_data()
        self.refresh_pages_table()
        QMessageBox.information(
            self,
            "Hoàn thành",
            f"Đã sync {synced} Page từ nick gốc." + (f"\nThiếu nick gốc: {missing} Page." if missing else "")
        )

    def open_page_creation_for_selected(self):
        if self.platform != "facebook":
            return

        use_support = True
        if hasattr(self, "chk_apply_support") and self.chk_apply_support is not None:
            use_support = self.chk_apply_support.isChecked()

        self.open_selected_profiles(
            use_support=use_support,
            target_url="https://www.facebook.com/pages/create"
        )

    def delete_page(self):
        row = self.pages_table.currentRow()
        if row < 0:
            return
        if QMessageBox.question(self, "Xóa Page", "Xác nhận xóa Page đã lưu?", QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        del self.pages[row]
        self.save_data()
        self.refresh_pages_table()

    def open_selected_pages(self):
        row = self.pages_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Cảnh báo", "Chưa chọn Page nào để mở.")
            return

        page = self.pages[row]
        if self._ensure_page_metadata(page):
            self.save_data()
        account_id = page.get("account_id", "")
        account = next((acc for acc in self.accounts if acc.get("id") == account_id), None)
        if not account:
            QMessageBox.warning(self, "Lỗi", "Không tìm thấy account gắn với Page này.")
            return

        page_url = page.get("page_url", "").strip()
        if not page_url:
            QMessageBox.warning(self, "Lỗi", "Page này chưa có URL để mở.")
            return

        pm = ProfileManager()
        from browser.chrome_launcher import ChromeLauncher

        try:
            page_login = page.get("login_account") or self._build_page_login_account(account)
            profile_path = pm.get_profile_path(f"{self.platform}_pages", page.get("profile_key", page.get("page_id", account['id'])))
            proxy = page_login.get('proxy', '') or account.get('proxy', '')
            driver = ChromeLauncher.launch(profile_path, proxy=proxy)
            if not driver:
                QMessageBox.warning(self, "Lỗi", "Không thể mở Chrome profile cho Page này.")
                return
            if not self.is_facebook_session_alive(driver):
                has_support_data = page_login.get('id') and page_login.get('password')
                if has_support_data:
                    self.apply_account_support_data(driver, page_login)
            driver.get(page_url)
            if self.platform == "facebook":
                from facebook.fb_tasks import FacebookBot
                FacebookBot(driver).switch_to_page_context(
                    page_name=page.get("page_name", ""),
                    page_id=page.get("page_id", ""),
                )
        except Exception as e:
            QMessageBox.warning(self, "Lỗi", f"Không thể mở Page: {e}")

    def _find_row_by_account_id(self, account_id):
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 1)
            if item and item.text() == account_id:
                return row
        return -1

    def _selected_rows_from_ui(self):
        checked_rows = [i for i, chk in self.account_checkboxes.items() if chk.isChecked()]
        if checked_rows:
            return sorted(set(checked_rows))
        return sorted(set(i.row() for i in self.table.selectedIndexes()))

    def select_all_accounts(self):
        """Select all accounts in the table"""
        for chk in self.account_checkboxes.values():
            chk.setChecked(True)
        QMessageBox.information(self, "Thành công", f"Đã chọn tất cả {len(self.accounts)} nick!")

    def deselect_all_accounts(self):
        """Deselect all accounts in the table"""
        for chk in self.account_checkboxes.values():
            chk.setChecked(False)
        QMessageBox.information(self, "Thành công", "Đã bỏ chọn tất cả nick!")

    def select_highlighted_accounts(self):
        """Select checkboxes for currently highlighted/selected rows only"""
        highlighted_rows = self._selected_rows_from_ui()
        if not highlighted_rows:
            QMessageBox.information(self, "Thông báo", "Chưa bôi đen row nào để chọn!")
            return
        
        changed = 0
        for row in highlighted_rows:
            if row in self.account_checkboxes:
                if not self.account_checkboxes[row].isChecked():
                    self.account_checkboxes[row].setChecked(True)
                    changed += 1
        
        QMessageBox.information(self, "Thành công", f"Đã chọn {changed}/{len(highlighted_rows)} nick đã bôi đen!")

    def deselect_highlighted_accounts(self):
        """Deselect checkboxes for currently highlighted/selected rows only""" 
        highlighted_rows = self._selected_rows_from_ui()
        if not highlighted_rows:
            QMessageBox.information(self, "Thông báo", "Chưa bôi đen row nào để bỏ chọn!")
            return
        
        changed = 0
        for row in highlighted_rows:
            if row in self.account_checkboxes:
                if self.account_checkboxes[row].isChecked():
                    self.account_checkboxes[row].setChecked(False)
                    changed += 1
        
        QMessageBox.information(self, "Thành công", f"Đã bỏ chọn {changed}/{len(highlighted_rows)} nick đã bôi đen!")

    def check_selected_accounts_live(self):
        """Check live status of selected or highlighted accounts by UID"""
        rows = self._selected_rows_from_ui()
        if not rows:
            QMessageBox.information(self, "Thông báo", "Chưa chọn hoặc bôi đen nick nào để kiểm tra!")
            return

        results = []
        for row in rows:
            if row < 0 or row >= len(self.accounts):
                continue
            account = self.accounts[row]
            fb_uid = self._resolve_facebook_uid(account)
            if not fb_uid:
                self.table.setItem(row, 4, QTableWidgetItem("Không có UID Facebook"))
                self.table.setItem(row, 5, QTableWidgetItem("Không có UID"))
                results.append(f"Row {row+1}: No Facebook UID")
                continue

            self.table.setItem(row, 4, QTableWidgetItem("Đang check..."))
            self.table.setItem(row, 5, QTableWidgetItem("Đang check..."))
            QGuiApplication.processEvents()
            alive, reason = self._check_facebook_uid_live(fb_uid)
            if alive:
                status_text = "LIVE"
            else:
                reason_lower = reason.lower()
                if "locked/die (browser): checkpoint" in reason_lower:
                    status_text = "OFF"
                elif "checkpoint" in reason_lower or "locked" in reason_lower or "vô hiệu hóa" in reason_lower:
                    status_text = "LOCKED"
                elif "404" in reason_lower or "không tồn tại" in reason_lower or "not found" in reason_lower or "content isn't available" in reason_lower or "this content isn't available" in reason_lower or "sorry, something went wrong" in reason_lower:
                    status_text = "DIE"
                else:
                    status_text = "OFF"
            status_text += " [anyf]"
            if reason:
                status_text += f" ({reason})"
            self.table.setItem(row, 5, QTableWidgetItem(status_text))
            self.accounts[row]['last_live_status'] = status_text
            self.accounts[row]['last_live_uid'] = fb_uid
            results.append(f"{fb_uid}: {status_text}")

        self.save_data()
        QMessageBox.information(self, "Kết quả Check Live", "\n".join(results))

    def _resolve_facebook_uid(self, account):
        """Resolve a real Facebook UID from account data or cookie."""
        candidate = str(account.get('uid', '') or account.get('facebook_id', '') or account.get('id', '')).strip()
        if candidate and not candidate.startswith(('fa_', 'ti_')):
            return candidate

        cookie = account.get('cookie', '') or account.get('cookies', '')
        if cookie:
            m = re.search(r"c_user=([0-9]+)", cookie)
            if m:
                return m.group(1)

        token = account.get('token', '')
        if token:
            try:
                resp = requests.get(f"https://graph.facebook.com/me?access_token={token}", timeout=15)
                data = resp.json()
                if isinstance(data, dict) and data.get('id'):
                    return str(data['id'])
            except:
                pass

        return ""

    def _check_facebook_uid_live_with_browser(self, uid, proxy=None):
        """Fallback to a real browser load when request-based public checks are blocked."""
        from browser.chrome_launcher import ChromeLauncher
        from selenium.webdriver.common.by import By

        profile_path = None
        driver = None
        url = f"https://m.facebook.com/profile.php?id={uid}" if uid.isdigit() else f"https://m.facebook.com/{uid}"
        try:
            profile_path = tempfile.mkdtemp(prefix="fb_livecheck_")
            driver = ChromeLauncher.launch(profile_path, proxy=proxy, headless=True)
            if not driver:
                return False, "Browser launch failed"

            driver.get(url)
            time.sleep(6)
            current_url = driver.current_url.lower()
            html = driver.page_source.lower()

            body_text = ""
            try:
                body_text = driver.find_element(By.TAG_NAME, "body").text.lower()
            except:
                pass

            if any(token in current_url for token in ["/checkpoint/", "login.php", "facebook.com/login"]):
                return False, "OFF (browser login/checkpoint URL)"

            title_text = driver.title.lower()
            if "error" in title_text or "error" in current_url:
                return False, "OFF (browser error page)"

            locked_signals = [
                "tài khoản của bạn đã bị vô hiệu hóa",
                "đã bị vô hiệu hóa",
                "content isn't available",
                "this content isn't available",
                "sorry, this content isn't available",
                "page you requested cannot be displayed",
                "account disabled",
                "không khả dụng",
                "confirm your identity",
                "enter login code",
                "account temporarily locked",
                "this account is temporarily locked",
                "security check",
                "sorry, something went wrong",
                "unavailable",
                "not available"
            ]
            for phrase in locked_signals:
                if phrase in html or phrase in body_text:
                    return False, f"LOCKED/DIE (browser): {phrase}"

            if "checkpoint" in title_text:
                return False, "LOCKED/DIE (browser): checkpoint"

            profile_indicators = [
                "profile_pic", "timeline_main_column", "pagelet_timeline_main_column",
                "id=profile_pic_header", "href=\"/profile.php?id=", "name=\"description\"",
                "fb://profile", "timeline_nav", "timelinecoverphoto", "profile_header"
            ]
            if any(signal in html for signal in profile_indicators):
                return True, "Live (browser)"

            if "m.facebook.com/story.php" in current_url or "/about" in current_url:
                return True, "Live (browser)"

            if body_text and len(body_text) > 120 and not any(phrase in body_text for phrase in [
                "log in to facebook", "facebook.com/login", "forgot account",
                "confirm your identity", "enter login code", "security check",
                "sorry, something went wrong", "content isn't available"
            ]):
                return True, "Live (browser unknown page)"

            return False, "OFF (browser unclear)"
        except Exception as e:
            return False, f"Browser error: {e}"
        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass
            if profile_path:
                shutil.rmtree(profile_path, ignore_errors=True)

    def _check_facebook_uid_live(self, uid):
        # 1. Check using graph profile picture redirect (static redirect detection)
        try:
            pic_url = f"https://graph.facebook.com/{uid}/picture?type=normal"
            pic_resp = requests.get(pic_url, timeout=10, allow_redirects=True)
            if pic_resp.status_code >= 400:
                return False, f"DIE (HTTP {pic_resp.status_code})"
            
            final_url = pic_resp.url.lower()
            if "rsrc.php" in final_url or "static.xx.fbcdn.net" in final_url or "static" in final_url:
                return False, "DIE (static image redirect)"
            
            if pic_resp.status_code == 200:
                return True, "Live (image redirect)"
        except Exception as e:
            print(f"Graph check failed for UID {uid}: {e}")

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        }
        session = requests.Session()
        session.headers.update(headers)
        source = 'public'

        url = f"https://m.facebook.com/profile.php?id={uid}" if uid.isdigit() else f"https://m.facebook.com/{uid}"
        try:
            resp = session.get(url, timeout=15, allow_redirects=True)
        except Exception:
            return False, "Lỗi request"

        html = resp.text.lower()
        if resp.status_code in (400, 404, 410):
            return self._check_facebook_uid_live_with_browser(uid)

        blocked_phrases = [
            "tài khoản của bạn đã bị vô hiệu hóa",
            "đã bị vô hiệu hóa",
            "content isn't available",
            "this content isn't available",
            "sorry, this content isn't available",
            "page you requested cannot be displayed",
            "account disabled",
            "không khả dụng",
            "checkpoint",
            "confirm your identity",
            "enter login code",
            "account temporarily locked",
            "this account is temporarily locked",
            "locked",
            "security check",
            "sorry, something went wrong"
        ]
        for phrase in blocked_phrases:
            if phrase in html:
                return False, f"CHECKPOINT/LOCKED ({source}): {phrase}"

        login_phrases = [
            "log in to facebook",
            "đăng nhập vào facebook",
            "đăng nhập bằng facebook",
            "forgot account",
            "m.facebook.com/login",
            "facebook.com/login"
        ]
        if any(phrase in html for phrase in login_phrases):
            return False, "OFF (login required)"

        common_profile_signals = [
            "profile_pic", "timeline_main_column", "pagelet_timeline_main_column",
            "id=profile_pic_header", "href=\"/profile.php?id=", "name=\"description\"",
            "fb://profile", "timeline_nav", "timelinecoverphoto"
        ]

        if resp.status_code == 200 and any(signal in html for signal in common_profile_signals):
            return True, f"Live ({source})"

        # Fallback to browser-based checks when the request path is blocked.
        return self._check_facebook_uid_live_with_browser(uid)

    def add_account(self):
        d = QDialog(self); l = QFormLayout(d); n = QLineEdit(); p = QLineEdit()
        l.addRow("Tên:", n); l.addRow("Proxy:", p); b = QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
        b.accepted.connect(d.accept); b.rejected.connect(d.reject); l.addWidget(b)
        if d.exec_() == QDialog.Accepted:
            import time; self.accounts.append({"id": f"{self.platform[:2]}_{int(time.time())}", "name": n.text(), "proxy": p.text()})
            self.save_data(); self.refresh_table()

    def edit_account(self):
        r = self.table.currentRow(); 
        if r < 0: return
        acc = self.accounts[r]; d = QDialog(self); l = QFormLayout(d); n = QLineEdit(acc['name']); p = QLineEdit(acc.get('proxy',''))
        l.addRow("Tên:", n); l.addRow("Proxy:", p); b = QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
        b.accepted.connect(d.accept); b.rejected.connect(d.reject); l.addWidget(b)
        if d.exec_() == QDialog.Accepted: self.accounts[r]['name'] = n.text(); self.accounts[r]['proxy'] = p.text(); self.save_data(); self.refresh_table()

    def import_accounts_list(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Import danh sách tài khoản")
        layout = QVBoxLayout(dialog)

        layout.addWidget(QLabel("Danh sách Facebook (mỗi dòng một tài khoản):"))
        accounts_input = QTextEdit()
        accounts_input.setPlaceholderText(
            "61583511704175|Hellokity1971|c_user=...;xs=...|EAAAA...|outtendiehn73000@hotmail.com|password123|ABC123|facebookpass"
            "\nFormat: ID|Name|Cookie|Token|Email|EmailPassword|2FACode|FacebookPassword"
            "\nLogin cần ID và FacebookPassword; Cookie/Token được lưu nhưng không dùng đăng nhập"
            "\n2FACode được dùng khi Facebook yêu cầu xác thực hai bước"
        )
        accounts_input.setFixedHeight(180)
        layout.addWidget(accounts_input)

        layout.addWidget(QLabel("Danh sách Proxy (mỗi dòng một proxy):"))
        proxy_input = QTextEdit()
        proxy_input.setPlaceholderText("103.166.184.186:31541:ac4931541:1774837920\n...")
        proxy_input.setFixedHeight(120)
        layout.addWidget(proxy_input)

        self.chk_open_after_import = QCheckBox("Tự động login tuần tự sau khi import")
        self.chk_open_after_import.setChecked(True)
        layout.addWidget(self.chk_open_after_import)

        self.chk_apply_support = QCheckBox("Đăng nhập bằng UID/password và xử lý 2FA khi mở")
        self.chk_apply_support.setChecked(True)
        layout.addWidget(self.chk_apply_support)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec_() != QDialog.Accepted:
            return

        account_lines = [line.strip() for line in accounts_input.toPlainText().splitlines() if line.strip()]
        proxy_lines = [line.strip() for line in proxy_input.toPlainText().splitlines() if line.strip()]

        if not account_lines:
            QMessageBox.warning(self, "Lỗi import", "Danh sách tài khoản rỗng!")
            return

        imported = []
        warnings = []
        for index, line in enumerate(account_lines):
            parsed = self.parse_account_line(line)
            if not parsed:
                warnings.append(f"Dòng {index+1} không đúng định dạng")
                continue

            if index < len(proxy_lines):
                parsed['proxy'] = proxy_lines[index]
            else:
                parsed['proxy'] = parsed.get('proxy', '')

            # Ensure extra fields exist
            parsed.setdefault('cookie', '')
            parsed.setdefault('token', '')
            parsed.setdefault('email', '')
            parsed.setdefault('email_password', '')
            parsed.setdefault('2fa_code', '')
            parsed.setdefault('password', '')
            parsed.setdefault('login_resume_url', '')

            self.accounts.append(parsed)
            imported.append(parsed)

        self.save_data()
        self.refresh_table()

        if warnings:
            QMessageBox.warning(self, "Import hoàn thành với cảnh báo", "\n".join(warnings))

        if imported and self.chk_open_after_import.isChecked():
            if self.platform == "facebook" and self.chk_apply_support.isChecked():
                self.start_sequential_auto_login(imported)
            else:
                # Non-login/open-only mode keeps the previous behavior.
                self.table.clearSelection()
                for row, acc in enumerate(self.accounts):
                    if acc in imported:
                        self.table.selectRow(row)
                self.open_selected_profiles(use_support=self.chk_apply_support.isChecked())

    def scrape_selected_page(self):
        # Hỏi link page để cào
        page_url, ok = QInputDialog.getText(self, "Cào Dữ Liệu", "Nhập link trang Facebook để cào dữ liệu:")
        if not ok or not page_url.strip():
            return

        page_url = page_url.strip()
        # Extract page_id từ URL nếu có
        page_id = ""
        if "facebook.com/" in page_url:
            parts = page_url.split("facebook.com/")[-1].split("/")
            if parts and parts[0]:
                if parts[0].isdigit():
                    page_id = parts[0]
                else:
                    page_id = parts[0]  # Có thể là username

        if not page_id:
            page_id, ok = QInputDialog.getText(self, "Cào Dữ Liệu", "Nhập Page ID hoặc tên:")
            if not ok or not page_id.strip():
                return
            page_id = page_id.strip()

        # Hỏi số bài tối đa
        max_posts, ok = QInputDialog.getInt(self, "Cào Dữ Liệu", "Số bài tối đa để cào:", 10, 1, 100)
        if not ok:
            return

        # Hỏi tên thư mục lưu
        folder_name, ok = QInputDialog.getText(self, "Cào Dữ Liệu", "Tên thư mục lưu dữ liệu (để trống dùng page_id):")
        if not ok:
            return
        folder_name = folder_name.strip() or page_id

        # Chọn account để dùng (dùng account đầu tiên)
        if not self.accounts:
            QMessageBox.warning(self, "Lỗi", "Không có account nào để dùng.")
            return

        account_index = 0
        account = self.accounts[account_index]

        # Tạo config tạm cho scrape
        config = {
            'mode': 'scrape',
            'scrape': {
                'page_url': page_url,
                'page_id': page_id,
                'max_posts': max_posts,
                'folder_name': folder_name
            }
        }

        # Thêm vào queue
        self.max_threads = 1  # Scrape dùng 1 thread
        self.queue.append((account_index, account, config))
        self.process_queue()
        QMessageBox.information(self, "Đã thêm", f"Đã thêm task cào dữ liệu từ {page_url}.")

    def parse_account_line(self, line):
        parts = [part.strip() for part in line.split('|')]
        if len(parts) < 2:
            return None

        def looks_like_cookie(value):
            return value and ('c_user=' in value or 'xs=' in value or 'datr=' in value or 'fr=' in value)

        def looks_like_token(value):
            return value and value.startswith(('EAAA', 'EAAD', 'EAAG', 'EAAB'))

        def looks_like_email(value):
            return value and '@' in value and '.' in value.split('@')[-1]

        account = {
            'id': parts[0],
            'name': parts[0],
            'cookie': '',
            'token': '',
            'email': '',
            'email_password': '',
            '2fa_code': '',
            'password': parts[1] if len(parts) > 1 else '',  # Facebook password
            'proxy': ''
        }

        extra_parts = parts[2:]
        if not extra_parts:
            return account

        normalized = [part for part in extra_parts]

        # Handle malformed imports where an empty field is inserted before cookie or token.
        if len(normalized) >= 2 and not normalized[0] and looks_like_cookie(normalized[1]):
            normalized.pop(0)
        if len(normalized) >= 2 and not normalized[0] and looks_like_token(normalized[1]):
            normalized.pop(0)

        for value in normalized:
            if not value:
                continue
            if not account['cookie'] and looks_like_cookie(value):
                account['cookie'] = value
                continue
            if not account['token'] and looks_like_token(value):
                account['token'] = value
                continue
            if not account['email'] and looks_like_email(value):
                account['email'] = value
                continue
            if account['email'] and not account['email_password']:
                account['email_password'] = value
                continue
            if not account['2fa_code']:
                account['2fa_code'] = value
                continue
            if not account['password']:
                account['password'] = value

        return account

    def delete_account(self):
        rows = sorted(set(i.row() for i in self.table.selectedIndexes()), reverse=True)
        if rows and QMessageBox.question(self, "Xóa", "Xác nhận xóa tài khoản?", QMessageBox.Yes|QMessageBox.No) == QMessageBox.Yes:
            pm = ProfileManager(); 
            for r in rows: pm.delete_profile(self.platform, self.accounts[r]['id']); del self.accounts[r]
            self.save_data(); self.refresh_table()

    def batch_login_accounts(self):
        """Login các account đã chọn với cùng logic như nút Login ở từng dòng."""
        if not self.accounts:
            QMessageBox.warning(self, "Cảnh báo", "Không có tài khoản nào để login!")
            return

        if self.batch_login_workers or self.batch_login_queue:
            QMessageBox.warning(self, "Đang xử lý", "Một luồng login khác đang chạy.")
            return

        if self.workers or self.queue:
            QMessageBox.warning(self, "Đang chạy campaign", "Hãy dừng campaign trước khi login hàng loạt.")
            return

        selected_rows = self._selected_rows_from_ui()
        if not selected_rows:
            QMessageBox.warning(self, "Cảnh báo", "Chưa chọn nick nào để batch login!")
            return

        selected_accounts = [self.accounts[row] for row in selected_rows]
            
        # Xác nhận
        msg = f"Đăng nhập {len(selected_accounts)} nick đã chọn?\n\n"
        msg += "Logic sẽ giống nút Login ở từng dòng: mở profile, áp session/support data nếu có, rồi giữ trình duyệt mở."
        
        if QMessageBox.question(self, "Batch Login", msg, QMessageBox.Yes|QMessageBox.No) != QMessageBox.Yes:
            return
            
        # Disable button để tránh spam click
        self.btn_batch_login.setEnabled(False)
        self.btn_batch_login.setText("🔄 Đang xử lý...")
        self.batch_login_queue = selected_accounts[:]
        self.batch_login_workers = {}
        self.batch_login_browsers = []
        self.batch_login_total = len(selected_accounts)
        self.batch_login_done = 0
        self.batch_login_success_count = 0
        self.batch_login_auto_close = False
        self.batch_login_stop_requested = False
        self.btn_stop.setEnabled(True)
        self.btn_stop.setText("⏹ DỪNG LOGIN")
        self.process_batch_login_queue()

    def login_all_accounts(self):
        """Start the automatic one-by-one login flow for every account."""
        if self.platform != "facebook":
            QMessageBox.warning(self, "Không hỗ trợ", "Chức năng này hiện chỉ hỗ trợ Facebook.")
            return
        if not self.accounts:
            QMessageBox.warning(self, "Cảnh báo", "Không có tài khoản nào để login!")
            return
        if self.batch_login_workers or self.batch_login_queue:
            QMessageBox.warning(self, "Đang xử lý", "Một luồng login khác đang chạy.")
            return
        if self.workers or self.queue:
            QMessageBox.warning(self, "Đang chạy campaign", "Hãy dừng campaign trước khi login hàng loạt.")
            return

        total = len(self.accounts)
        answer = QMessageBox.question(
            self,
            "Chạy Login Tất Cả",
            f"Bắt đầu login tuần tự {total} tài khoản?\n\n"
            "Mỗi lần chỉ mở một Chrome profile. Khi profile xử lý xong, Chrome sẽ đóng "
            "và chuyển sang tài khoản kế tiếp.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            self.start_sequential_auto_login(list(self.accounts))

    def start_sequential_auto_login(self, accounts):
        """Login imported Facebook accounts one at a time and close successes."""
        accounts = list(accounts or [])
        if not accounts:
            QMessageBox.warning(self, "Cảnh báo", "Không có tài khoản nào để login.")
            return
        if self.batch_login_workers or self.batch_login_queue:
            QMessageBox.warning(self, "Đang xử lý", "Một luồng login khác đang chạy.")
            return
        if self.workers or self.queue:
            QMessageBox.warning(self, "Đang chạy campaign", "Hãy dừng campaign trước khi login hàng loạt.")
            return

        self.btn_batch_login.setEnabled(False)
        self.btn_batch_login.setText("🔄 Auto login tuần tự...")
        self.btn_login_all.setEnabled(False)
        self.btn_login_all.setText("🔄 Đang login tuần tự...")
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.btn_stop.setText("⏹ DỪNG LOGIN")
        self.batch_login_queue = list(accounts)
        self.batch_login_workers = {}
        self.batch_login_browsers = []
        self.batch_login_total = len(accounts)
        self.batch_login_done = 0
        self.batch_login_success_count = 0
        self.batch_login_auto_close = True
        self.batch_login_stop_requested = False
        self.process_batch_login_queue()

    def process_batch_login_queue(self):
        from core.worker import BatchLoginWorker

        if self.batch_login_stop_requested:
            return

        max_parallel = 1 if self.batch_login_auto_close else max(1, self.spin_threads.value())
        while len(self.batch_login_workers) < max_parallel and self.batch_login_queue:
            acc = self.batch_login_queue.pop(0)
            row = self._find_row_by_account_id(acc['id'])
            worker = BatchLoginWorker(
                acc,
                self.platform,
                row,
                keep_browser_open=not self.batch_login_auto_close,
            )
            worker.signals.started.connect(self.on_batch_login_started)
            worker.signals.status.connect(self.on_batch_login_status)
            worker.signals.error.connect(self.on_batch_login_error)
            worker.signals.finished.connect(self.on_batch_login_finished)
            self.batch_login_workers[row] = worker
            worker.start()
        
    def on_batch_login_started(self, index):
        """Handle batch login started signal"""
        if index >= 0:
            self.table.setItem(index, 4, QTableWidgetItem("🔄 Đang login..."))
                    
    def on_batch_login_status(self, index, message):
        """Handle batch login status updates"""
        if index >= 0:
            self.table.setItem(index, 4, QTableWidgetItem(message))
            
    def on_batch_login_error(self, index, error_msg):
        """Handle batch login errors"""
        print(f"Batch login error for account {index}: {error_msg}")

    def stop_batch_login(self):
        """Cancel the login queue and close all Chrome instances owned by it."""
        if not self.batch_login_workers and not self.batch_login_queue:
            return False

        self.batch_login_stop_requested = True
        self.batch_login_queue.clear()

        # The active worker owns the current driver. Calling stop() makes the
        # worker stop at its next safe point and closes that profile immediately.
        for worker in list(self.batch_login_workers.values()):
            try:
                worker.stop()
            except Exception:
                pass

        # Manual Batch Login can leave browser handles in this list. Close them
        # as well so the common Stop button has one predictable behavior.
        for driver in list(self.batch_login_browsers):
            try:
                driver.quit()
            except Exception:
                pass
        self.batch_login_browsers.clear()
        try:
            self.save_data()
        except Exception:
            pass

        # Usually the worker's finished signal performs the final UI reset. If
        # the queue was cancelled before a worker was created, reset now.
        if not self.batch_login_workers:
            self._finish_batch_login_ui(interrupted=True)
        return True

    def _finish_batch_login_ui(self, interrupted=False):
        """Restore controls after a batch/automatic login run ends."""
        self.btn_batch_login.setEnabled(True)
        self.btn_batch_login.setText("🔐 Batch Login")
        self.btn_login_all.setEnabled(True)
        self.btn_login_all.setText("🔐 Chạy Login Tất Cả")
        self.btn_start.setEnabled(True)
        self.tabs.setEnabled(True)
        if not self.workers:
            self.btn_stop.setEnabled(False)
            self.btn_stop.setText("⏹ DỪNG & ĐÓNG CHROME")

        if interrupted:
            QMessageBox.information(
                self,
                "Đã dừng login",
                "Đã hủy hàng đợi login và đóng Chrome đang chạy. "
                "Bước login dở đã được lưu để dùng với nút Mở Chọn.",
            )
        
    def on_batch_login_finished(self, index):
        """Handle batch login completion"""
        worker = self.batch_login_workers.pop(index, None)
        if worker:
            self.batch_login_browsers.extend(worker.get_browsers())
            if worker.success:
                self.batch_login_success_count += 1
            # Persist the saved resume URL, or its removal after a successful login,
            # before the next account starts.
            self.save_data()
        self.batch_login_done += 1
        if not self.batch_login_stop_requested:
            self.process_batch_login_queue()

        if not self.batch_login_workers and not self.batch_login_queue:
            interrupted = self.batch_login_stop_requested
            self._finish_batch_login_ui(interrupted=interrupted)

            if not interrupted:
                success_count = self.batch_login_success_count
                if success_count:
                    QMessageBox.information(
                        self,
                        "Hoàn thành",
                        f"✅ Batch login hoàn thành!\n\n"
                        f"🎯 Thành công: {success_count}/{self.batch_login_total} tài khoản\n\n"
                        + ("Các profile login thành công đã được đóng." if self.batch_login_auto_close else "Các trình duyệt sẽ giữ mở để bạn sử dụng.")
                    )
                else:
                    QMessageBox.warning(self, "Thất bại", "Không có tài khoản nào đăng nhập thành công!")

            self.batch_login_browsers = []
            self.batch_login_total = 0
            self.batch_login_done = 0
            self.batch_login_success_count = 0
            self.batch_login_auto_close = False
            self.batch_login_stop_requested = False

    def batch_change_password(self):
        """Change Facebook passwords in bulk for selected accounts."""
        if self.platform != "facebook":
            QMessageBox.warning(self, "Không hỗ trợ", "Chức năng đổi mật khẩu chỉ hỗ trợ Facebook.")
            return
        if not self.accounts:
            QMessageBox.warning(self, "Cảnh báo", "Không có tài khoản nào để đổi mật khẩu!")
            return

        selected_rows = self._selected_rows_from_ui()
        if not selected_rows:
            QMessageBox.warning(self, "Cảnh báo", "Chưa chọn nick nào để đổi mật khẩu!")
            return

        selected_accounts = [self.accounts[row] for row in selected_rows]
        accounts_with_password = [acc for acc in selected_accounts if acc.get('password', '').strip()]
        if not accounts_with_password:
            QMessageBox.warning(self, "Cảnh báo", "Các nick đã chọn chưa có mật khẩu Facebook hiện tại.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Đổi Mật Khẩu Hàng Loạt")
        layout = QFormLayout(dialog)
        new_password = QLineEdit()
        new_password.setEchoMode(QLineEdit.Password)
        confirm_password = QLineEdit()
        confirm_password.setEchoMode(QLineEdit.Password)
        layout.addRow("Mật khẩu mới:", new_password)
        layout.addRow("Nhập lại:", confirm_password)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec_() != QDialog.Accepted:
            return

        new_password_value = new_password.text().strip()
        confirm_password_value = confirm_password.text().strip()
        if not new_password_value:
            QMessageBox.warning(self, "Cảnh báo", "Mật khẩu mới không được để trống!")
            return
        if new_password_value != confirm_password_value:
            QMessageBox.warning(self, "Cảnh báo", "Mật khẩu nhập lại không khớp!")
            return

        msg = f"Đổi mật khẩu cho {len(accounts_with_password)}/{len(selected_accounts)} nick đã chọn?\n\n"
        msg += "Chỉ các nick có mật khẩu Facebook hiện tại mới được xử lý."
        if QMessageBox.question(self, "Đổi Mật Khẩu", msg, QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return

        self.btn_change_password.setEnabled(False)
        self.btn_change_password.setText("🔄 Đang đổi pass...")
        self.password_change_queue = [(self._find_row_by_account_id(acc['id']), acc) for acc in accounts_with_password]
        self.password_change_workers = {}
        self.password_change_total = len(accounts_with_password)
        self.password_change_done = 0
        self.password_change_new_password = new_password_value
        self.password_change_results = {}
        self.process_password_change_queue()

    def process_password_change_queue(self):
        from core.worker import PasswordChangeWorker

        max_parallel = max(1, self.spin_threads.value())
        while len(self.password_change_workers) < max_parallel and self.password_change_queue:
            row, acc = self.password_change_queue.pop(0)
            worker = PasswordChangeWorker(acc, row, self.password_change_new_password)
            worker.signals.started.connect(self.on_password_change_started)
            worker.signals.status.connect(self.on_password_change_status)
            worker.signals.error.connect(self.on_password_change_error)
            worker.signals.finished.connect(self.on_password_change_finished)
            self.password_change_workers[row] = worker
            worker.start()

    def on_password_change_started(self, index):
        if index >= 0:
            self.table.setItem(index, 4, QTableWidgetItem("🔐 Đang đổi mật khẩu..."))

    def on_password_change_status(self, index, message):
        if index >= 0:
            self.table.setItem(index, 4, QTableWidgetItem(message))
            if 0 <= index < len(self.accounts):
                self.password_change_results.setdefault(index, {})
                self.password_change_results[index]["status"] = message

    def on_password_change_error(self, index, error_msg):
        print(f"Password change error for account {index}: {error_msg}")
        if index >= 0:
            self.password_change_results.setdefault(index, {})
            self.password_change_results[index]["error"] = error_msg

    def on_password_change_finished(self, index):
        worker = self.password_change_workers.pop(index, None)
        if worker and worker.success and 0 <= index < len(self.accounts):
            self.accounts[index]['password'] = self.password_change_new_password
            self.save_data()

        self.password_change_done += 1
        self.process_password_change_queue()

        if not self.password_change_workers and not self.password_change_queue:
            self.btn_change_password.setEnabled(True)
            self.btn_change_password.setText("🔑 Đổi Pass")

            success_rows = []
            failed_rows = []
            for index, result in sorted(self.password_change_results.items()):
                if 0 <= index < len(self.accounts):
                    if result.get("status") == "✅ Đổi mật khẩu thành công":
                        success_rows.append(index)
                    else:
                        failed_rows.append(index)

            lines = []
            if success_rows:
                lines.append("Thành công:")
                for index in success_rows:
                    acc = self.accounts[index]
                    lines.append(f"- {acc['id']} | {acc['name']}")
            if failed_rows:
                lines.append("Thất bại:")
                for index in failed_rows:
                    acc = self.accounts[index]
                    error_text = self.password_change_results.get(index, {}).get("error") or self.password_change_results.get(index, {}).get("status") or "Không rõ lỗi"
                    lines.append(f"- {acc['id']} | {acc['name']} | {error_text}")

            QMessageBox.information(
                self,
                "Hoàn thành",
                f"Đổi mật khẩu xong.\n\n"
                f"Đã xử lý: {self.password_change_total} nick\n\n" + "\n".join(lines)
            )
            self.password_change_total = 0
            self.password_change_done = 0
            self.password_change_new_password = ""
            self.password_change_results = {}

    def open_selected_profiles(self, use_support=True, target_url=None, resume_saved=True):
        rows = self._selected_rows_from_ui()
        pm = ProfileManager()
        from browser.chrome_launcher import ChromeLauncher
        
        for r in rows:
            acc = self.accounts[r]
            try:
                self.table.setItem(r, 4, QTableWidgetItem("Opening..."))
                profile_path = pm.get_profile_path(self.platform, acc['id'])
                proxy = acc.get('proxy', '')
                
                # Use our improved ChromeLauncher instead of direct uc.Chrome()
                driver = ChromeLauncher.launch(profile_path, proxy=proxy)
                if driver:
                    self.btn_stop.setEnabled(True)
                    self.open_profile_drivers[acc.get('id')] = driver
                    resume_url = acc.get('login_resume_url', '').strip()
                    opened_status = "✅ Opened"
                    if self.platform == "facebook" and resume_saved and resume_url and not target_url:
                        # Reopen the final page saved by sequential auto-login,
                        # including successful results, without starting login again.
                        driver.get(resume_url)
                        opened_status = "✅ Đã mở lại trang cuối đã lưu"
                    else:
                        has_support_data = acc.get('id') and acc.get('password')
                        if use_support and self.platform == "facebook" and has_support_data:
                            already_logged_in = self.is_facebook_session_alive(driver, navigate=True)
                            if not already_logged_in:
                                login_ok = self.apply_account_support_data(driver, acc, assume_on_facebook=True)
                                if login_ok:
                                    opened_status = "✅ Login xong"
                                else:
                                    opened_status = "⏸ Login chưa xong - giữ Chrome"
                        elif self.platform == "facebook" and not target_url:
                            from facebook.fb_tasks import FacebookBot
                            FacebookBot(driver).switch_to_personal_context()
                    if target_url:
                        driver.get(target_url)
                        opened_status = "✅ Opened"
                    self.table.setItem(r, 4, QTableWidgetItem(opened_status))
                else:
                    self.table.setItem(r, 4, QTableWidgetItem("❌ Failed"))
            except Exception as e:
                print(f"Error opening profile: {e}")
                self.table.setItem(r, 4, QTableWidgetItem("❌ Error"))

    def is_facebook_session_alive(self, driver, navigate=False):
        """Return True when the opened Chrome profile already has a live Facebook session."""
        try:
            if navigate:
                driver.get('https://www.facebook.com')

            current_url = driver.current_url.lower()
            if current_url.startswith('about:blank') or current_url.startswith('chrome://'):
                return False
            if any(marker in current_url for marker in (
                "login",
                "checkpoint",
                "two_step_verification",
                "two_factor",
            )):
                return False

            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            from selenium.webdriver.common.by import By

            login_form_markers = [
                (By.ID, "email"),
                (By.ID, "pass"),
                (By.NAME, "login"),
                (By.XPATH, "//form[contains(@action, 'login')]"),
            ]

            for locator in login_form_markers:
                try:
                    WebDriverWait(driver, 1).until(EC.presence_of_element_located(locator))
                    return False
                except:
                    continue

            indicators = [
                (By.XPATH, "//a[@aria-label='Your profile']"),
                (By.XPATH, "//a[contains(@href, '/me/')]"),
                (By.XPATH, "//div[@role='feed']"),
                (By.XPATH, "//a[@aria-label='Notifications']"),
                (By.XPATH, "//a[@aria-label='Messenger']"),
            ]

            for locator in indicators:
                try:
                    WebDriverWait(driver, 3).until(EC.presence_of_element_located(locator))
                    return True
                except:
                    continue

            return False
        except Exception:
            return False

    def apply_account_support_data(self, driver, acc, assume_on_facebook=False):
        """Login with cookie first, fallback to assigned UID/password; retain the existing 2FA step."""
        try:
            from facebook.fb_tasks import FacebookBot
            bot = FacebookBot(driver)
            cookie_str = acc.get('cookie', '')
            if cookie_str:
                if bot.login_with_cookie(cookie_str):
                    return True
            return bot.login_account_with_credentials(acc)
        except Exception as e:
            print(f"Login lỗi cho acc {acc.get('id')}: {e}")
            return False

    def manual_login(self, i):
        """Start one row's UID/password login without blocking the GUI thread."""
        if self.platform != "facebook":
            self.table.selectRow(i)
            self.open_selected_profiles(resume_saved=False)
            return
        if i < 0 or i >= len(self.accounts):
            return
        if i in self.single_login_workers:
            return

        account = self.accounts[i]
        if not account.get("id") or not account.get("password"):
            self.table.setItem(i, 4, QTableWidgetItem("❌ Thiếu UID/password"))
            return

        from core.worker import BatchLoginWorker

        self.table.selectRow(i)
        self.table.setItem(i, 4, QTableWidgetItem("🔄 Khởi động Chrome..."))
        self.btn_stop.setEnabled(True)
        worker = BatchLoginWorker(
            account,
            self.platform,
            i,
            keep_browser_open=True,
        )
        worker.signals.started.connect(self.on_single_login_started)
        worker.signals.status.connect(self.on_single_login_status)
        worker.signals.error.connect(self.on_single_login_error)
        worker.signals.finished.connect(self.on_single_login_finished)
        self.single_login_workers[i] = worker
        worker.start()

    def on_single_login_started(self, index):
        self.table.setItem(index, 4, QTableWidgetItem("🔄 Đang login..."))

    def on_single_login_status(self, index, message):
        self.table.setItem(index, 4, QTableWidgetItem(message))

    def on_single_login_error(self, index, error_msg):
        print(f"Login error for account {index}: {error_msg}")
        self.table.setItem(index, 4, QTableWidgetItem(f"❌ Lỗi login: {str(error_msg)[:40]}"))

    def on_single_login_finished(self, index):
        worker = self.single_login_workers.pop(index, None)
        if worker:
            try:
                account = self.accounts[index]
                browsers = worker.get_browsers()
                if browsers:
                    self.open_profile_drivers[account.get("id")] = browsers[-1]
                self.save_data()
            except Exception as exc:
                print(f"Could not finalize single login for row {index}: {exc}")

        if not self.single_login_workers and not self.batch_login_workers and not self.batch_login_queue:
            self.btn_stop.setEnabled(False)
            self.btn_stop.setText("⏹ DỪNG & ĐÓNG CHROME")
    
    def filter_accounts_by_uid(self):
        """Filter table by UID search"""
        search_text = self.search_input.text().strip().lower()
        
        if not search_text:
            # Show all rows if search is empty
            for i in range(self.table.rowCount()):
                self.table.setRowHidden(i, False)
            return
        
        # Filter rows based on UID match
        for i in range(self.table.rowCount()):
            if i >= len(self.accounts):
                continue
            
            account = self.accounts[i]
            uid = account.get('id', '').lower()
            name = account.get('name', '').lower()
            
            # Match if UID or name contains search text
            matches = search_text in uid or search_text in name
            self.table.setRowHidden(i, not matches)
    
    def clear_search(self):
        """Clear search input and show all accounts"""
        self.search_input.clear()
        self.filter_accounts_by_uid()
    
    def update_status(self, i, t): self.table.setItem(i, 4, QTableWidgetItem(t))
    def on_worker_done(self, i):
        if i in self.workers: del self.workers[i]
        self.process_queue()
        if not self.workers and not self.queue:
            self.btn_start.setEnabled(True); self.btn_stop.setEnabled(False); self.tabs.setEnabled(True)
            QMessageBox.information(self, "Done", "Hoàn thành chiến dịch!")
