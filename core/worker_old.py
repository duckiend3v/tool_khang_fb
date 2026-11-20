# from PyQt5.QtCore import QThread
# import time
# from gui.signals import WorkerSignals
# from browser.chrome_launcher import ChromeLauncher
# from browser.profile_manager import ProfileManager
# from facebook.fb_tasks import FacebookBot
# from tiktok.tk_tasks import TikTokBot

# class FarmWorker(QThread):
#     def __init__(self, index, account_data, platform, config):
#         super().__init__()
#         self.index = index
#         self.acc_data = account_data
#         self.platform = platform
#         self.config = config
#         self.signals = WorkerSignals()
#         self.driver = None
#         self.is_running = True  # <--- QUAN TRỌNG: Cờ để kiểm tra trạng thái chạy

#     def run(self):
#         try:
#             self.signals.started.emit(self.index)
#             self.signals.status.emit(self.index, "Khởi động Chrome...")

#             pm = ProfileManager()
#             profile_path = pm.get_profile_path(self.platform, self.acc_data['id'])
            
#             # Khởi tạo Chrome
#             self.driver = ChromeLauncher.launch(profile_path, self.acc_data.get('proxy'))

#             if not self.driver:
#                 raise Exception("Không thể mở trình duyệt (Driver = None)")

#             # Nếu vừa mở lên đã bấm Stop thì dừng luôn
#             if not self.is_running: return 

#             # --- ĐIỀU HƯỚNG THEO NỀN TẢNG ---
            # --- ĐIỀU HƯỚNG THEO NỀN TẢNG ---

            if self.platform == "facebook":

                self.bot = FacebookBot(self.driver)

                mode = self.config.get('mode', 'farm')

                

                if mode == 'seed':

                    self.signals.status.emit(self.index, "Chế độ Seeding Đa Nhiệm...")

                    

                    # Lấy danh sách nhiệm vụ

                    tasks = self.config.get('seed_tasks', [])

                    

                    for idx, task in enumerate(tasks):

                        task_type = task['type'].upper()

                        self.signals.status.emit(self.index, f"Đang chạy Seeding: {task_type} ({idx+1}/{len(tasks)})")

                        

                        # Gọi hàm seeding cho từng nhiệm vụ

                        self.bot.run_seeding_scenario(task, update_callback=self.send_status)

                        

                        # Nghỉ một chút giữa các nhiệm vụ seeding (để tránh spam)

                        if idx < len(tasks) - 1:

                            self.signals.status.emit(self.index, "Nghỉ 10s chuyển bài...")

                            time.sleep(10)

                elif mode == 'scrape':

                    self.signals.status.emit(self.index, "Chế độ Cào Dữ Liệu...")

                    scrape_cfg = self.config.get('scrape', {})

                    page_url = scrape_cfg.get('page_url')

                    page_id = scrape_cfg.get('page_id')

                    max_posts = scrape_cfg.get('max_posts', 10)

                    folder_name = scrape_cfg.get('folder_name')

                    self.bot.scrape_posts_from_page(page_url, page_id, max_posts, update_callback=self.send_status, folder_name=folder_name)

                else:

                    self.signals.status.emit(self.index, "Chế độ Nuôi/Đăng...")

                    self.bot.run_custom_scenario(self.config, update_callback=self.send_status)
                    self.signals.status.emit(self.index, "Chế độ Nuôi/Đăng...")
                    self.bot.run_custom_scenario(self.config, update_callback=self.send_status)
                
#             elif self.platform == "tiktok":
#                 self.bot = TikTokBot(self.driver)
#                 mode = self.config.get('mode', 'farm')
                
#                 if mode == 'seed':
#                     self.signals.status.emit(self.index, "Chế độ Seeding TikTok...")
#                     seed_cfg = self.config.get('seed', {})
#                     self.bot.run_seeding_scenario(seed_cfg, update_callback=self.send_status)
#                 else:
#                     self.signals.status.emit(self.index, "Chế độ Nuôi TikTok...")
#                     self.bot.run_foryou_farm(self.config, update_callback=self.send_status)
            
#             self.signals.status.emit(self.index, "Hoàn thành!")
#             time.sleep(2)

#         except Exception as e:
#             # Nếu là do người dùng bấm Stop (is_running = False) thì không báo lỗi đỏ
#             if not self.is_running:
#                 self.signals.status.emit(self.index, "Đã dừng thủ công.")
#             else:
#                 self.signals.error.emit(self.index, str(e))
#                 self.signals.status.emit(self.index, f"Lỗi: {str(e)[:20]}")
#         finally:
#             # Dọn dẹp driver khi xong việc hoặc bị lỗi
#             if self.driver:
#                 try:
#                     self.driver.quit()
#                 except:
#                     pass
#             self.signals.finished.emit(self.index)

#     def send_status(self, text):
#         """Hàm gửi trạng thái về GUI, có kiểm tra cờ is_running"""
#         if self.is_running:
#             self.signals.status.emit(self.index, text)
#         else:
#             # Nếu đã bấm stop, ta ném lỗi để thoát khỏi vòng lặp bên trong Bot
#             raise Exception("Force Stop")

#     # --- ĐÂY LÀ HÀM ÔNG ĐANG THIẾU ---
#     def stop(self):
#         """Hàm này được gọi từ GUI khi bấm nút Dừng"""
#         self.is_running = False # Đánh dấu ngừng chạy
#         self.signals.status.emit(self.index, "Đang dừng...")
        
#         # Kill trình duyệt ngay lập tức để ngắt bot
#         if self.driver:
#             try:
#                 self.driver.quit()
#                 self.driver = None
#             except:
#                 pass
        
#         self.wait() # Đợi thread tắt hẳn




# # import time
# # import os
# # from PyQt5.QtCore import QThread, pyqtSignal, QObject
# # import undetected_chromedriver as uc
# # from browser.profile_manager import ProfileManager

# # # Import Logic Bots
# # from facebook.fb_tasks import FacebookBot
# # from tiktok.tk_tasks import TikTokBot

# # class WorkerSignals(QObject):
# #     status = pyqtSignal(int, str)    # Gửi trạng thái (Index, Message)
# #     finished = pyqtSignal(int)       # Gửi tín hiệu xong (Index)
# #     error = pyqtSignal(int, str)     # Gửi lỗi
# #     started = pyqtSignal(int)        # Tín hiệu bắt đầu

# # class FarmWorker(QThread):
# #     def __init__(self, index, account_data, platform, config):
# #         super().__init__()
# #         self.index = index
# #         self.acc_data = account_data
# #         self.platform = platform
# #         self.config = config
# #         self.signals = WorkerSignals()
# #         self.driver = None
# #         self.bot = None
# #         self.is_running = True  # Cờ kiểm soát trạng thái chạy

# #     def send_status(self, msg):
# #         """Hàm callback để Bot gửi trạng thái về GUI"""
# #         if self.is_running:
# #             self.signals.status.emit(self.index, msg)
# #         else:
# #             # Nếu đã bấm Stop, ném lỗi để thoát ngay lập tức khỏi Bot
# #             raise Exception("Force Stop")

# #     def run(self):
# #         try:
# #             self.signals.started.emit(self.index)
# #             self.send_status("Khởi động Chrome...")

# #             pm = ProfileManager()
            
# #             # === FIX LỖI INVALID ARGUMENT (QUAN TRỌNG) ===
# #             # Chrome bắt buộc dùng đường dẫn tuyệt đối
# #             raw_path = pm.get_profile_path(self.platform, self.acc_data['id'])
# #             profile_path = os.path.abspath(raw_path)
# #             # =============================================

# #             proxy = self.acc_data.get('proxy', "")

# #             # Setup Chrome Options trực tiếp tại đây để kiểm soát tốt nhất
# #             options = uc.ChromeOptions()
# #             options.add_argument(f'--user-data-dir={profile_path}')
            
# #             if proxy:
# #                 options.add_argument(f'--proxy-server={proxy}')

# #             # Các options tối ưu
# #             options.add_argument('--no-first-run --no-service-autorun --password-store=basic')

# #             # Khởi tạo Driver
# #             self.driver = uc.Chrome(options=options)
# #             self.driver.set_window_size(1280, 720)

# #             if not self.driver:
# #                 raise Exception("Không thể mở trình duyệt (Driver Init Failed)")

# #             # Nếu vừa mở lên đã bấm Stop thì dừng luôn
# #             if not self.is_running: return 

# #             # --- ĐIỀU HƯỚNG THEO NỀN TẢNG ---
# #             if self.platform == "facebook":
# #                 self.bot = FacebookBot(self.driver)
# #                 mode = self.config.get('mode', 'farm')
                
# #                 if mode == 'seed':
# #                     self.signals.status.emit(self.index, "Chế độ Seeding Đa Nhiệm...")
                    
# #                     # Lấy danh sách nhiệm vụ từ config
# #                     tasks = self.config.get('seed_tasks', [])
                    
# #                     for idx, task in enumerate(tasks):
# #                         if not self.is_running: break # Check dừng
                        
# #                         task_type = task['type'].upper()
# #                         self.signals.status.emit(self.index, f"Chạy Task {idx+1}/{len(tasks)}: {task_type}")
                        
# #                         # Gọi hàm seeding
# #                         self.bot.run_seeding_scenario(task, update_callback=self.send_status)
                        
# #                         # Nghỉ giữa các bài
# #                         if idx < len(tasks) - 1:
# #                             self.signals.status.emit(self.index, "Nghỉ 10s chuyển bài...")
# #                             time.sleep(10)
# #                 else:
# #                     self.signals.status.emit(self.index, "Chế độ Nuôi/Đăng...")
# #                     self.bot.run_custom_scenario(self.config, update_callback=self.send_status)
                
# #             elif self.platform == "tiktok":
# #                 self.bot = TikTokBot(self.driver)
# #                 mode = self.config.get('mode', 'farm')
                
# #                 if mode == 'seed':
# #                     self.signals.status.emit(self.index, "Chế độ Seeding TikTok...")
                    
# #                     # --- CẬP NHẬT LOGIC LOOP CHO TIKTOK (GIỐNG FB) ---
# #                     tasks = self.config.get('seed_tasks', [])
                    
# #                     for idx, task in enumerate(tasks):
# #                         if not self.is_running: break # Check dừng
                        
# #                         task_type = task['type'].upper()
# #                         self.signals.status.emit(self.index, f"Chạy Task {idx+1}/{len(tasks)}: {task_type}")
                        
# #                         self.bot.run_seeding_scenario(task, update_callback=self.send_status)
                        
# #                         if idx < len(tasks) - 1:
# #                             self.signals.status.emit(self.index, "Nghỉ 5s chuyển bài...")
# #                             time.sleep(5)
# #                     # ------------------------------------------------
# #                 else:
# #                     self.signals.status.emit(self.index, "Chế độ Nuôi TikTok...")
# #                     self.bot.run_foryou_farm(self.config, update_callback=self.send_status)
            
# #             if self.is_running:
# #                 self.signals.status.emit(self.index, "Hoàn thành!")
# #                 time.sleep(2)

# #         except Exception as e:
# #             # Nếu là lỗi do Force Stop thì bỏ qua, còn lại thì báo lỗi
# #             if str(e) == "Force Stop" or not self.is_running:
# #                 self.signals.status.emit(self.index, "Đã dừng.")
# #             else:
# #                 self.signals.error.emit(self.index, str(e))
# #                 self.signals.status.emit(self.index, f"Lỗi: {str(e)[:20]}")
        
# #         finally:
# #             # Dọn dẹp driver
# #             # if self.driver:
# #             #     try:
# #             #         self.driver.quit()
# #             #     except: pass
# #             self.signals.finished.emit(self.index)

# #     def stop(self):
# #         """Hàm này được gọi từ GUI khi bấm nút Dừng"""
# #         self.is_running = False # Đánh dấu ngừng chạy
# #         self.signals.status.emit(self.index, "Đang dừng...")
        
# #         # Kill trình duyệt ngay lập tức
# #         if self.driver:
# #             try:
# #                 self.driver.quit()
# #                 self.driver = None
# #             except: pass
        
# #         self.wait() # Đợi thread tắt hẳn







# # import time
# # import os
# # import threading # <--- Thư viện quan trọng để khóa luồng
# # from PyQt5.QtCore import QThread, pyqtSignal, QObject
# # import undetected_chromedriver as uc
# # from browser.profile_manager import ProfileManager

# # # Import Logic Bots
# # from facebook.fb_tasks import FacebookBot
# # from tiktok.tk_tasks import TikTokBot

# # # --- KHÓA TOÀN CỤC (GLOBAL LOCK) ---
# # # Biến này giúp các luồng xếp hàng, tránh lỗi WinError 183 khi mở nhiều Chrome cùng lúc
# # driver_init_lock = threading.Lock()

# # class WorkerSignals(QObject):
# #     status = pyqtSignal(int, str)    # Gửi trạng thái (Index, Message)
# #     finished = pyqtSignal(int)       # Gửi tín hiệu xong (Index)
# #     error = pyqtSignal(int, str)     # Gửi lỗi
# #     started = pyqtSignal(int)        # Tín hiệu bắt đầu

# # class FarmWorker(QThread):
# #     def __init__(self, index, account_data, platform, config):
# #         super().__init__()
# #         self.index = index
# #         self.acc_data = account_data
# #         self.platform = platform
# #         self.config = config
# #         self.signals = WorkerSignals()
# #         self.driver = None
# #         self.bot = None
# #         self.is_running = True  # Cờ kiểm soát trạng thái chạy

# #     def smart_sleep(self, seconds):
# #         """
# #         Hàm ngủ thông minh:
# #         Thay vì ngủ liền một mạch, nó chia nhỏ giấc ngủ để kiểm tra lệnh Stop.
# #         Trả về True nếu ngủ đủ giấc, False nếu bị đánh thức bởi lệnh Stop.
# #         """
# #         steps = int(seconds * 10) # Chia nhỏ mỗi bước 0.1s
# #         for _ in range(steps):
# #             if not self.is_running:
# #                 return False
# #             time.sleep(0.1)
# #         return True

# #     def send_status(self, msg):
# #         """Hàm callback để Bot gửi trạng thái về GUI"""
# #         if self.is_running:
# #             self.signals.status.emit(self.index, msg)
# #         # Không raise Exception ở đây nữa để luồng thoát mượt mà hơn

# #     def run(self):
# #         try:
# #             self.signals.started.emit(self.index)
# #             self.send_status("Chuẩn bị khởi động...")

# #             pm = ProfileManager()
            
# #             # === FIX LỖI INVALID ARGUMENT ===
# #             raw_path = pm.get_profile_path(self.platform, self.acc_data['id'])
# #             profile_path = os.path.abspath(raw_path)

# #             proxy = self.acc_data.get('proxy', "")

# #             # Setup Chrome Options
# #             options = uc.ChromeOptions()
# #             options.add_argument(f'--user-data-dir={profile_path}')
            
# #             if proxy:
# #                 options.add_argument(f'--proxy-server={proxy}')

# #             options.add_argument('--no-first-run --no-service-autorun --password-store=basic')

# #             # === KHỞI TẠO DRIVER VỚI KHÓA AN TOÀN (FIX WINERROR 183) ===
# #             self.send_status("Đang xếp hàng mở Chrome...")
            
# #             with driver_init_lock: # <--- Bắt đầu khóa
# #                 try:
# #                     # Chỉ 1 luồng được chạy đoạn này tại 1 thời điểm
# #                     self.driver = uc.Chrome(options=options, version_main=None)
# #                     self.driver.set_window_size(1280, 720)
# #                 except Exception as e:
# #                     raise Exception(f"Lỗi mở Chrome: {str(e)}")
# #             # <--- Kết thúc khóa, luồng khác được phép chạy tiếp

# #             if not self.driver:
# #                 raise Exception("Driver Init Failed")

# #             # Check Stop ngay sau khi mở
# #             if not self.is_running: return 

# #             self.send_status("Trình duyệt đã mở!")

# #             # --- ĐIỀU HƯỚNG FACEBOOK ---
# #             if self.platform == "facebook":
# #                 self.bot = FacebookBot(self.driver)
# #                 mode = self.config.get('mode', 'farm')
                
# #                 if mode == 'seed':
# #                     self.send_status("Chế độ Seeding...")
# #                     tasks = self.config.get('seed_tasks', [])
                    
# #                     for idx, task in enumerate(tasks):
# #                         if not self.is_running: break
                        
# #                         task_type = task['type'].upper()
# #                         self.send_status(f"Task {idx+1}/{len(tasks)}: {task_type}")
                        
# #                         self.bot.run_seeding_scenario(task, update_callback=self.send_status)
                        
# #                         # Dùng smart_sleep
# #                         if idx < len(tasks) - 1:
# #                             self.send_status("Nghỉ 10s chuyển bài...")
# #                             if not self.smart_sleep(10): break
# #                 else:
# #                     self.send_status("Chế độ Nuôi/Đăng...")
# #                     self.bot.run_custom_scenario(self.config, update_callback=self.send_status)
            
# #             # --- ĐIỀU HƯỚNG TIKTOK ---
# #             elif self.platform == "tiktok":
# #                 self.bot = TikTokBot(self.driver)
# #                 mode = self.config.get('mode', 'farm')
                
# #                 if mode == 'seed':
# #                     self.send_status("Chế độ Seeding TikTok...")
# #                     tasks = self.config.get('seed_tasks', [])
                    
# #                     for idx, task in enumerate(tasks):
# #                         if not self.is_running: break
                        
# #                         self.bot.run_seeding_scenario(task, update_callback=self.send_status)
                        
# #                         if idx < len(tasks) - 1:
# #                             self.send_status("Nghỉ 5s...")
# #                             if not self.smart_sleep(5): break
# #                 else:
# #                     self.send_status("Chế độ Nuôi TikTok...")
# #                     self.bot.run_foryou_farm(self.config, update_callback=self.send_status)
            
# #             # --- KẾT THÚC CÔNG VIỆC ---
# #             if self.is_running:
# #                 self.send_status("Hoàn thành! Đóng sau 3s...")
# #                 self.smart_sleep(3) # Đợi xíu cho người dùng nhìn thấy kết quả

# #         except Exception as e:
# #             # Nếu lỗi không phải do người dùng bấm Stop
# #             if self.is_running:
# #                 self.signals.error.emit(self.index, str(e))
# #                 self.signals.status.emit(self.index, f"Lỗi: {str(e)[:30]}")
        
# #         finally:
# #             # --- DỌN DẸP AN TOÀN TRONG LUỒNG WORKER ---
# #             self.send_status("Đang đóng trình duyệt...")
# #             if self.driver:
# #                 try:
# #                     self.driver.quit() # Tắt Chrome
# #                 except: pass
                
# #                 # --- DÒNG QUAN TRỌNG: CẮT ĐỨT QUAN HỆ ---
# #                 # Gán về None để Python không tự động gọi hàm hủy từ Main Thread nữa
# #                 self.driver = None 
            
# #             self.signals.finished.emit(self.index)

# #     def stop(self):
# #         """Hàm này được gọi từ GUI khi bấm nút Dừng"""
# #         # Chỉ đánh dấu cờ, không kill driver ở đây để tránh crash app
# #         self.is_running = False 
# #         self.signals.status.emit(self.index, "Đang dừng (đợi xíu)...")

import time
import os
import json
import threading
from PyQt5.QtCore import QThread, pyqtSignal, QObject
import undetected_chromedriver as uc
from browser.profile_manager import ProfileManager

# Import Logic Bots
from facebook.fb_tasks import FacebookBot
from tiktok.tk_tasks import TikTokBot

# --- KHÓA TOÀN CỤC ---
driver_init_lock = threading.Lock()

class WorkerSignals(QObject):
    status = pyqtSignal(int, str)
    finished = pyqtSignal(int)
    error = pyqtSignal(int, str)
    started = pyqtSignal(int)

class FarmWorker(QThread):
    def __init__(self, index, account_data, platform, config):
        super().__init__()
        self.index = index
        self.acc_data = account_data
        self.platform = platform
        self.config = config
        self.signals = WorkerSignals()
        self.driver = None
        self.bot = None
        self.is_running = True

    def smart_sleep(self, seconds):
        steps = int(seconds * 10)
        for _ in range(steps):
            if not self.is_running: return False
            time.sleep(0.1)
        return True

    def send_status(self, msg):
        if self.is_running:
            self.signals.status.emit(self.index, msg)

    def is_facebook_session_alive(self):
        """Return True when this Chrome profile already has a live Facebook session."""
        try:
            self.driver.get('https://www.facebook.com')
            time.sleep(3)

            current_url = self.driver.current_url.lower()
            if "login" in current_url or "checkpoint" in current_url:
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
                    WebDriverWait(self.driver, 1).until(EC.presence_of_element_located(locator))
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
                    WebDriverWait(self.driver, 3).until(EC.presence_of_element_located(locator))
                    return True
                except:
                    continue

            return False
        except Exception:
            return False

    def apply_facebook_support_data(self):
        """Apply cookie/token/2FA data when the Facebook profile is not already logged in."""
        try:
            bot = self.bot or FacebookBot(self.driver)
            self.bot = bot

            cookie_str = self.acc_data.get('cookie', '')
            if cookie_str:
                self.driver.get('https://www.facebook.com')
                time.sleep(2)

                cookies = [c.strip() for c in cookie_str.split(';') if '=' in c]
                cookie_expiry = int(time.time()) + (90 * 24 * 60 * 60)
                for cookie in cookies:
                    try:
                        name, value = cookie.split('=', 1)
                        if not name or value is None:
                            continue

                        cookie_dict = {
                            'name': name.strip(),
                            'value': value.strip(),
                            'domain': '.facebook.com',
                            'path': '/',
                            'expiry': cookie_expiry,
                            'httpOnly': False,
                            'secure': True,
                            'sameSite': 'None'
                        }
                        self.driver.add_cookie(cookie_dict)
                    except Exception:
                        try:
                            js = f"document.cookie = {json.dumps(name + '=' + value + '; domain=.facebook.com; path=/')};"
                            self.driver.execute_script(js)
                        except:
                            pass

                self.driver.refresh()
                time.sleep(3)

            token = self.acc_data.get('token', '')
            if token:
                bot.apply_token_login(token)

            if not self.is_facebook_session_alive():
                uid = self.acc_data.get('id', '')
                fb_password = self.acc_data.get('password', '')
                if uid and fb_password:
                    success = bot.login_with_credentials(uid, fb_password)
                    if success:
                        bot.save_credentials_to_browser(uid, fb_password)
                        bot.enable_chrome_autofill(uid, fb_password)

            email = self.acc_data.get('email', '')
            email_pass = self.acc_data.get('email_password', '')
            if email and email_pass:
                bot.apply_email_login(email, email_pass)

            twofa_code = self.acc_data.get('2fa_code', '')
            if twofa_code:
                bot.wait_for_2fa_and_fill(twofa_code, timeout=30)

        except Exception as e:
            print(f"Warning: Không thể áp dụng support data cho acc {self.acc_data.get('id')}: {e}")

    def run(self):
        try:
            self.signals.started.emit(self.index)
            
            from browser.chrome_launcher import ChromeLauncher
            
            pm = ProfileManager()
            raw_path = pm.get_profile_path(self.platform, self.acc_data['id'])
            profile_path = os.path.abspath(raw_path)
            proxy = self.acc_data.get('proxy', "")

            # Use our improved ChromeLauncher with version detection
            self.send_status("Khởi tạo Chrome...")
            try:
                self.driver = ChromeLauncher.launch(profile_path, proxy=proxy)
                if not self.driver:
                    raise Exception("ChromeLauncher.launch() returned None")
                print(f"--> Driver initialized: {self.driver.capabilities.get('browserVersion', 'Unknown')[:15]}")
                self.send_status("Trình duyệt đã mở!")
            except Exception as e:
                print(f"Error launching Chrome: {e}")
                raise e

            # --- LOGIC FACEBOOK ---
            if self.platform == "facebook":
                self.bot = FacebookBot(self.driver)
                has_support_data = any(self.acc_data.get(key) for key in ('cookie', 'token', 'email', 'email_password', '2fa_code', 'password'))
                self.send_status("Kiểm tra phiên Facebook...")
                already_logged_in = self.is_facebook_session_alive()
                if has_support_data and not already_logged_in:
                    self.send_status("Khôi phục phiên Facebook...")
                    self.apply_facebook_support_data()
                mode = self.config.get('mode', 'farm')
                
                if mode == 'seed':
                    self.send_status("Đang Seeding...")
                    tasks = self.config.get('seed_tasks', [])
                    for idx, task in enumerate(tasks):
                        if not self.is_running: break
                        self.send_status(f"Task {idx+1}: {task['type'].upper()}")
                        self.bot.run_seeding_scenario(task, update_callback=self.send_status)
                        if idx < len(tasks) - 1:
                            self.send_status("Nghỉ chuyển bài...")
                            if not self.smart_sleep(10): break
                else:
                    self.send_status("Đang Nuôi...")
                    self.bot.run_custom_scenario(self.config, update_callback=self.send_status)

            # --- LOGIC TIKTOK ---
            elif self.platform == "tiktok":
                self.bot = TikTokBot(self.driver)
                mode = self.config.get('mode', 'farm')
                if mode == 'seed':
                    self.send_status("Seeding TikTok...")
                    tasks = self.config.get('seed_tasks', [])
                    for idx, task in enumerate(tasks):
                        if not self.is_running: break
                        self.bot.run_seeding_scenario(task, update_callback=self.send_status)
                        if idx < len(tasks) - 1:
                            self.send_status("Nghỉ chuyển bài...")
                            if not self.smart_sleep(5): break
                else:
                    self.send_status("Nuôi TikTok...")
                    self.bot.run_foryou_farm(self.config, update_callback=self.send_status)

            # Treo máy chờ xem kết quả
            if self.is_running:
                self.send_status("Xong! Đóng sau 3s...")
                self.smart_sleep(3)

        except Exception as e:
            if self.is_running:
                self.signals.error.emit(self.index, str(e))
                self.signals.status.emit(self.index, f"Lỗi: {str(e)[:30]}")

        finally:
            self.send_status("Dọn dẹp tài nguyên...")
            if self.driver:
                try:
                    self.driver.quit()
                except: pass
                self.driver = None # [QUAN TRỌNG] Ngắt kết nối để tránh lỗi QObject Timer
            
            self.signals.finished.emit(self.index)

    def stop(self):
        self.is_running = False
        self.signals.status.emit(self.index, "Đang dừng...")


class BatchLoginWorker(QThread):
    """Worker for opening selected accounts using the same restore logic as row Login."""
    
    def __init__(self, account, platform, row_index):
        super().__init__()
        self.account = account
        self.platform = platform
        self.row_index = row_index
        self.signals = WorkerSignals()
        self.is_running = True
        self.browsers = []  # Store (account_name, driver) tuples
        
    def run(self):
        try:
            from browser.chrome_launcher import ChromeLauncher
            from browser.profile_manager import ProfileManager
            from facebook.fb_tasks import FacebookBot
            
            pm = ProfileManager()
            acc = self.account

            if not self.is_running:
                return

            self.signals.started.emit(self.row_index)
            self.signals.status.emit(self.row_index, f"Đang đăng nhập: {acc['name']}...")

            try:
                profile_path = pm.get_profile_path(self.platform, acc['id'])
                proxy = acc.get('proxy', '').strip()
                driver = ChromeLauncher.launch(profile_path, proxy=proxy, headless=False)

                if driver:
                    self.browsers.append((acc['name'], driver))

                    if self.platform == "facebook":
                        bot = FacebookBot(driver)

                        def is_logged_in():
                            try:
                                driver.get('https://www.facebook.com')
                                time.sleep(3)
                                current_url = driver.current_url.lower()
                                if "login" in current_url or "checkpoint" in current_url:
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
                            except:
                                return False

                        if not is_logged_in():
                            cookie_str = acc.get('cookie', '')
                            if cookie_str:
                                driver.get('https://www.facebook.com')
                                time.sleep(2)
                                cookie_expiry = int(time.time()) + (90 * 24 * 60 * 60)
                                for cookie in [c.strip() for c in cookie_str.split(';') if '=' in c]:
                                    try:
                                        name, value = cookie.split('=', 1)
                                        if not name or value is None:
                                            continue
                                        driver.add_cookie({
                                            'name': name.strip(),
                                            'value': value.strip(),
                                            'domain': '.facebook.com',
                                            'path': '/',
                                            'expiry': cookie_expiry,
                                            'httpOnly': False,
                                            'secure': True,
                                            'sameSite': 'None'
                                        })
                                    except:
                                        pass
                                driver.refresh()
                                time.sleep(3)

                            if not is_logged_in():
                                token = acc.get('token', '')
                                if token:
                                    bot.apply_token_login(token)

                            if not is_logged_in():
                                uid = acc.get('id', '')
                                fb_password = acc.get('password', '')
                                if uid and fb_password:
                                    success = bot.login_with_credentials(uid, fb_password)
                                    if success:
                                        bot.save_credentials_to_browser(uid, fb_password)
                                        bot.enable_chrome_autofill(uid, fb_password)

                            if not is_logged_in():
                                email = acc.get('email', '')
                                email_pass = acc.get('email_password', '')
                                if email and email_pass:
                                    bot.apply_email_login(email, email_pass)

                            if not is_logged_in():
                                twofa_code = acc.get('2fa_code', '')
                                if twofa_code:
                                    bot.wait_for_2fa_and_fill(twofa_code, timeout=30)

                        self.signals.status.emit(self.row_index, f"✅ {acc['name']} - Đã mở profile")
                    else:
                        driver.get("https://www.tiktok.com")
                        self.signals.status.emit(self.row_index, f"✅ {acc['name']} - Đã mở profile")
                else:
                    self.signals.status.emit(self.row_index, f"❌ {acc['name']} - Lỗi khởi động Chrome")
                    self.signals.error.emit(self.row_index, "Chrome launch failed")

            except Exception as e:
                self.signals.status.emit(self.row_index, f"❌ {acc['name']} - Lỗi: {str(e)[:50]}")
                self.signals.error.emit(self.row_index, str(e))
             
        except Exception as e:
            self.signals.error.emit(0, f"Batch login error: {str(e)}")
        finally:
            self.signals.finished.emit(self.row_index)
            
    def stop(self):
        """Stop batch login and close all browsers"""
        self.is_running = False
        self.signals.status.emit(0, "Đang dừng batch login...")
        
        # Close all browsers
        for name, driver in self.browsers:
            try:
                driver.quit()
            except:
                pass
        self.browsers.clear()
        
    def get_browsers(self):
        """Return list of successfully opened browsers"""
        return self.browsers


class PasswordChangeWorker(QThread):
    """Worker for changing one Facebook account password."""

    def __init__(self, account, row_index, new_password):
        super().__init__()
        self.account = account
        self.row_index = row_index
        self.new_password = new_password
        self.signals = WorkerSignals()
        self.success = False

    def run(self):
        driver = None
        try:
            from browser.chrome_launcher import ChromeLauncher
            from browser.profile_manager import ProfileManager

            self.signals.started.emit(self.row_index)
            self.signals.status.emit(self.row_index, "Khởi tạo Chrome...")

            pm = ProfileManager()
            profile_path = pm.get_profile_path("facebook", self.account['id'])
            proxy = self.account.get('proxy', '').strip()
            driver = ChromeLauncher.launch(profile_path, proxy=proxy, headless=False)
            if not driver:
                raise Exception("Không thể mở Chrome")

            bot = FacebookBot(driver)
            current_password = self.account.get('password', '')
            uid = self.account.get('id', '')

            self.signals.status.emit(self.row_index, "Đăng nhập tài khoản...")
            logged_in = False
            if bot.login_with_credentials(uid, current_password):
                logged_in = True
            else:
                cookie_str = self.account.get('cookie', '')
                if cookie_str:
                    driver.get('https://www.facebook.com')
                    time.sleep(2)
                    cookie_expiry = int(time.time()) + (90 * 24 * 60 * 60)
                    for cookie in [c.strip() for c in cookie_str.split(';') if '=' in c]:
                        try:
                            name, value = cookie.split('=', 1)
                            if not name or value is None:
                                continue
                            driver.add_cookie({
                                'name': name.strip(),
                                'value': value.strip(),
                                'domain': '.facebook.com',
                                'path': '/',
                                'expiry': cookie_expiry,
                                'httpOnly': False,
                                'secure': True,
                                'sameSite': 'None'
                            })
                        except:
                            pass
                    driver.refresh()
                    time.sleep(3)
                    logged_in = bot.login_with_credentials(uid, current_password)

            if not logged_in:
                raise Exception("Không đăng nhập được để đổi mật khẩu")

            self.signals.status.emit(self.row_index, "Đang đổi mật khẩu...")
            self.success = bot.change_password(current_password, self.new_password)
            if not self.success:
                raise Exception("Đổi mật khẩu thất bại")

            bot.save_credentials_to_browser(uid, self.new_password)
            bot.enable_chrome_autofill(uid, self.new_password)
            self.signals.status.emit(self.row_index, "✅ Đổi mật khẩu thành công")

        except Exception as e:
            self.signals.error.emit(self.row_index, str(e))
            self.signals.status.emit(self.row_index, f"❌ {str(e)[:50]}")
        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass
            self.signals.finished.emit(self.row_index)
