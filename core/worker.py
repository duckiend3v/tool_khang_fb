from PyQt5.QtCore import QThread
import time
from gui.signals import WorkerSignals
from browser.chrome_launcher import ChromeLauncher
from browser.profile_manager import ProfileManager
from facebook.fb_tasks import FacebookBot
from tiktok.tk_tasks import TikTokBot


class FarmWorker(QThread):
    def __init__(self, index, account_data, platform, config):
        super().__init__()
        self.index = index
        self.acc_data = account_data
        self.platform = platform
        self.config = config
        self.signals = WorkerSignals()
        self.driver = None
        self.is_running = True  # <--- QUAN TRỌNG: Cờ để kiểm tra trạng thái chạy

    def is_facebook_session_alive(self, navigate=False):
        try:
            if navigate:
                self.driver.get('https://www.facebook.com/')
                time.sleep(4)

            current_url = self.driver.current_url.lower()
            if current_url.startswith('about:blank') or current_url.startswith('chrome://'):
                return False
            if "login" in current_url or "checkpoint" in current_url:
                return False

            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            from selenium.webdriver.common.by import By

            # Check for login form markers - if ANY exist, NOT logged in
            login_form_markers = [
                (By.ID, "email"),
                (By.ID, "pass"),
                (By.NAME, "login"),
                (By.XPATH, "//form[contains(@action, 'login')]"),
                (By.XPATH, "//input[@name='email' or @name='pass']"),
            ]

            for locator in login_form_markers:
                try:
                    WebDriverWait(self.driver, 1).until(EC.presence_of_element_located(locator))
                    print(f"   Warning: Found login form marker: {locator}")
                    return False
                except:
                    continue

            # Multiple session indicators - need at least ONE
            indicators = [
                # Primary indicators (most reliable)
                (By.XPATH, "//a[@aria-label='Your profile']", "Profile link"),
                (By.XPATH, "//a[contains(@href, '/me/')]", "Me link"),
                (By.XPATH, "//div[@role='feed']", "Feed div"),
                
                # Secondary indicators
                (By.XPATH, "//a[@aria-label='Notifications' or @aria-label='Menu']", "Notifications"),
                (By.XPATH, "//a[@aria-label='Messenger']", "Messenger"),
                (By.XPATH, "//nav[@aria-label='Navigation']", "Nav bar"),
                
                # Fallback indicators
                (By.XPATH, "//div[contains(@class, 'x1y1aw88')]", "Main content"),
                (By.XPATH, "//span[contains(text(), 'What') or contains(text(), 'what')]", "What's on your mind"),
                (By.XPATH, "//input[@placeholder]", "Any input field"),
                (By.XPATH, "//*[@data-testid='feed']", "Feed by testid"),
            ]

            found_indicators = []
            for by, value, name in indicators:
                try:
                    WebDriverWait(self.driver, 2).until(EC.presence_of_element_located((by, value)))
                    found_indicators.append(name)
                    print(f"   Found: {name}")
                except:
                    continue

            if found_indicators:
                print(f"   Session active! Found {len(found_indicators)} indicators")
                return True
            
            print(f"   No session indicators found")
            return False
        except Exception as e:
            print(f"   Session check error: {str(e)[:40]}")
            return False

    def apply_facebook_support_data(self):
        """Login using the assigned UID/password and handle 2FA if requested."""
        try:
            self.bot = getattr(self, 'bot', None) or FacebookBot(self.driver)
            return self.bot.login_account_with_credentials(self.acc_data)
        except Exception as e:
            self.signals.status.emit(self.index, f"Login UID/password lỗi: {str(e)[:40]}")
            return False

    def run(self):
        try:
            self.signals.started.emit(self.index)
            self.signals.status.emit(self.index, "Khởi động Chrome...")

            pm = ProfileManager()
            profile_path = pm.get_profile_path(self.platform, self.acc_data['id'])
            
            # Khởi tạo Chrome
            self.driver = ChromeLauncher.launch(profile_path, self.acc_data.get('proxy'))

            if not self.driver:
                raise Exception("Không thể mở trình duyệt (Driver = None)")

            # Nếu vừa mở lên đã bấm Stop thì dừng luôn
            if not self.is_running: return 

            # --- ĐIỀU HƯỚNG THEO NỀN TẢNG ---
            if self.platform == "facebook":
                # One navigation per worker. The launcher must stay generic and
                # must not navigate once for proxy verification and again here.
                self.driver.get('https://www.facebook.com/')
                self.bot = FacebookBot(self.driver)
                has_support_data = self.acc_data.get('id') and self.acc_data.get('password')
                if has_support_data and not self.is_facebook_session_alive():
                    # --- THỬ LOGIN BẰNG COOKIE TRƯỚC (NHANH HƠN) ---
                    cookie_str = self.acc_data.get('cookie', '')
                    cookie_login_ok = False
                    if cookie_str:
                        self.signals.status.emit(self.index, "Đăng nhập bằng Cookie...")
                        cookie_login_ok = self.bot.login_with_cookie(cookie_str)
                        if cookie_login_ok:
                            self.signals.status.emit(self.index, "✅ Cookie login thành công!")

                    # --- FALLBACK: LOGIN BẰNG UID/PASSWORD ---
                    if not cookie_login_ok:
                        self.signals.status.emit(self.index, "Đăng nhập bằng UID/password...")
                        self.apply_facebook_support_data()
                elif not has_support_data:
                    self.signals.status.emit(self.index, "Thiếu UID/password Facebook")
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
                    self.bot.scrape_posts_from_page(page_url, page_id, max_posts, callback=self.send_status, folder_name=folder_name)
                else:
                    self.signals.status.emit(self.index, "Chế độ Nuôi/Đăng...")
                    self.bot.run_custom_scenario(self.config, update_callback=self.send_status)
                
            elif self.platform == "tiktok":
                self.bot = TikTokBot(self.driver)
                mode = self.config.get('mode', 'farm')
                
                if mode == 'seed':
                    self.signals.status.emit(self.index, "Chế độ Seeding TikTok...")
                    seed_cfg = self.config.get('seed', {})
                    self.bot.run_seeding_scenario(seed_cfg, update_callback=self.send_status)
                else:
                    self.signals.status.emit(self.index, "Chế độ Nuôi TikTok...")
                    self.bot.run_foryou_farm(self.config, update_callback=self.send_status)
            
            self.signals.status.emit(self.index, "Hoàn thành!")
            time.sleep(2)

        except Exception as e:
            # Nếu là do người dùng bấm Stop (is_running = False) thì không báo lỗi đỏ
            if not self.is_running:
                self.signals.status.emit(self.index, "Đã dừng thủ công.")
            else:
                self.signals.error.emit(self.index, str(e))
                self.signals.status.emit(self.index, f"Lỗi: {str(e)[:20]}")
        finally:
            # Dọn dẹp driver khi xong việc hoặc bị lỗi
            if self.driver:
                try:
                    self.driver.quit()
                except:
                    pass
            self.signals.finished.emit(self.index)

    def send_status(self, text):
        """Hàm gửi trạng thái về GUI, có kiểm tra cờ is_running"""
        if self.is_running:
            self.signals.status.emit(self.index, text)

    def stop(self):
        """Dừng worker"""
        self.is_running = False
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass


class BatchLoginWorker(QThread):
    TWOFA_SETTLE_SECONDS = 12

    def __init__(self, account_data, platform, row_index, keep_browser_open=True):
        super().__init__()
        self.acc_data = account_data
        self.platform = platform
        self.index = row_index
        self.keep_browser_open = keep_browser_open
        self.signals = WorkerSignals()
        self._browsers = []
        self.success = False
        self.driver = None
        self.is_running = True
        self.login_bot = None

    def get_browsers(self):
        return list(self._browsers)

    def is_facebook_session_alive(self, driver, navigate=False):
        try:
            if navigate:
                driver.get('https://www.facebook.com/')
                time.sleep(4)

            current_url = driver.current_url.lower()
            if current_url.startswith('about:blank') or current_url.startswith('chrome://'):
                return False
            if any(marker in current_url for marker in (
                "login", "checkpoint", "two_step_verification", "two_factor"
            )):
                return False

            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            from selenium.webdriver.common.by import By

            # Check for login form markers - if ANY exist, NOT logged in
            login_form_markers = [
                (By.ID, "email"),
                (By.ID, "pass"),
                (By.NAME, "login"),
                (By.XPATH, "//form[contains(@action, 'login')]"),
                (By.XPATH, "//input[@name='email' or @name='pass']"),
            ]

            for locator in login_form_markers:
                try:
                    WebDriverWait(driver, 1).until(EC.presence_of_element_located(locator))
                    print(f"   Warning: Found login form marker: {locator}")
                    return False
                except:
                    continue

            # Multiple session indicators - need at least ONE
            indicators = [
                # Primary indicators (most reliable)
                (By.XPATH, "//a[@aria-label='Your profile']", "Profile link"),
                (By.XPATH, "//a[contains(@href, '/me/')]", "Me link"),
                (By.XPATH, "//div[@role='feed']", "Feed div"),
                
                # Secondary indicators
                (By.XPATH, "//a[@aria-label='Notifications' or @aria-label='Menu']", "Notifications"),
                (By.XPATH, "//a[@aria-label='Messenger']", "Messenger"),
                (By.XPATH, "//nav[@aria-label='Navigation']", "Nav bar"),
                
                # Fallback indicators
                (By.XPATH, "//*[@data-testid='feed']", "Feed by testid"),
            ]

            found_indicators = []
            for by, value, name in indicators:
                try:
                    WebDriverWait(driver, 2).until(EC.presence_of_element_located((by, value)))
                    found_indicators.append(name)
                    print(f"   Found: {name}")
                except:
                    continue

            if found_indicators:
                print(f"   Session active! Found {len(found_indicators)} indicators")
                return True
            
            print(f"   No session indicators found")
            return False
        except Exception as e:
            print(f"   Session check error: {str(e)[:40]}")
            return False

    def apply_facebook_support_data(self, driver):
        """Use the same UID/password login flow as the per-account Login button."""
        try:
            self.login_bot = FacebookBot(driver)
            self.login_bot.login_cancelled = lambda: not self.is_running
            return self.login_bot.login_account_with_credentials(self.acc_data)
        except Exception as e:
            self.signals.status.emit(self.index, f"Login UID/password lỗi: {str(e)[:40]}")
            return False

    def run(self):
        driver = None
        browser_kept = False
        try:
            self.signals.started.emit(self.index)
            self.signals.status.emit(self.index, "Khởi động Chrome...")

            pm = ProfileManager()
            profile_path = pm.get_profile_path(self.platform, self.acc_data['id'])
            proxy = self.acc_data.get('proxy', '')
            driver = ChromeLauncher.launch(profile_path, proxy=proxy)
            self.driver = driver

            if not driver:
                self.signals.status.emit(self.index, "❌ Mở Chrome thất bại")
                return
            if not self.is_running:
                return

            if self.platform == "facebook":
                # Navigate once before checking the profile/session. This avoids
                # the old blank-tab -> login.php -> Facebook reload chain.
                driver.get('https://www.facebook.com/')
                if not self.is_running:
                    return
                has_support_data = self.acc_data.get('id') and self.acc_data.get('password')
                if has_support_data:
                    if self.is_facebook_session_alive(driver):
                        self.success = True
                    else:
                        if not self.is_running:
                            return
                        # --- THỬ LOGIN BẰNG COOKIE TRƯỚC (NHANH HƠN) ---
                        cookie_str = self.acc_data.get('cookie', '')
                        cookie_login_ok = False
                        if cookie_str:
                            self.signals.status.emit(self.index, "Đăng nhập bằng Cookie...")
                            self.login_bot = FacebookBot(driver)
                            self.login_bot.login_cancelled = lambda: not self.is_running
                            cookie_login_ok = self.login_bot.login_with_cookie(cookie_str)
                            if cookie_login_ok:
                                self.success = True
                                self.signals.status.emit(self.index, "✅ Cookie login thành công!")

                        # --- FALLBACK: LOGIN BẰNG UID/PASSWORD ---
                        if not cookie_login_ok:
                            if not self.is_running:
                                return
                            self.signals.status.emit(self.index, "Đăng nhập bằng UID/password...")
                            self.success = bool(self.apply_facebook_support_data(driver))
                            # The Continue click belongs to the login transaction.
                            # Wait here before run() can emit finished and the GUI can
                            # start the next profile.
                            self._wait_after_twofa_continue()
                elif not has_support_data:
                    self.signals.status.emit(self.index, "❌ Thiếu UID/password Facebook")
            else:
                # Preserve the old Batch Login behavior for other platforms.
                self.success = True

            if not self.is_running:
                return

            if self.success:
                self.signals.status.emit(self.index, "✅ Login xong")
            else:
                twofa_result = getattr(self.login_bot, "twofa_result", None)
                if twofa_result == "submit_failed":
                    self.signals.status.emit(self.index, "❌ Không bấm được Continue 2FA - đã lưu trang")
                elif twofa_result == "rejected":
                    self.signals.status.emit(self.index, "❌ Mã 2FA bị từ chối - đã lưu trang")
                elif twofa_result == "response_timeout":
                    self.signals.status.emit(self.index, "⏸ Đã bấm Continue 2FA, chưa có kết quả - đã lưu trang")
                elif twofa_result == "missing_code":
                    self.signals.status.emit(self.index, "❌ Facebook đang yêu cầu 2FA nhưng tài khoản chưa có mã 2FA - đã lưu trang")
                elif twofa_result == "fill_failed":
                    self.signals.status.emit(self.index, "❌ Ô 2FA không nhận mã - đã lưu trang")
                elif twofa_result == "code_field_timeout":
                    self.signals.status.emit(self.index, "❌ Không tìm thấy ô nhập mã 2FA - đã lưu trang")
                elif twofa_result == "handler_error":
                    self.signals.status.emit(self.index, "❌ Lỗi xử lý màn 2FA - đã lưu trang")
                elif twofa_result == "pending":
                    self.signals.status.emit(self.index, "⏸ Chưa bấm được Continue 2FA - đã lưu trang")
                elif self.keep_browser_open:
                    self.signals.status.emit(self.index, "⏸ Chưa login xong - giữ Chrome để xử lý")
                else:
                    self.signals.status.emit(self.index, "⏸ Chưa login xong - đã lưu bước để Mở Chọn")

            # Save the current Facebook step before any automatic close. The
            # manager uses this URL when the user later presses Mở Chọn.
            if self.platform == "facebook":
                try:
                    current_url = driver.current_url
                    if current_url and not current_url.startswith(("about:", "chrome:")):
                        self.acc_data["login_resume_url"] = current_url
                except Exception:
                    pass

            # Manual Batch Login keeps browsers open. Import auto-login closes
            # every result, including failures, after saving the resume URL.
            if self.keep_browser_open:
                self._browsers.append(driver)
                browser_kept = True
        except Exception as e:
            if not self.is_running:
                self.signals.status.emit(self.index, "⏹ Đã dừng login và đóng Chrome")
            else:
                self.signals.error.emit(self.index, str(e))
                self.signals.status.emit(self.index, f"❌ Lỗi: {str(e)[:40]}")
        finally:
            # Even a rejected code/result must stay open at least twelve seconds
            # after Continue was clicked. Stop remains immediately interruptible.
            clicked_at = getattr(self.login_bot, "twofa_continue_clicked_at", None)
            if driver and not self.keep_browser_open and clicked_at is not None and self.is_running:
                deadline = clicked_at + getattr(self, "TWOFA_SETTLE_SECONDS", 12)
                while self.is_running and time.monotonic() < deadline:
                    time.sleep(min(0.2, max(0, deadline - time.monotonic())))
            if driver and self.platform == "facebook":
                try:
                    current_url = driver.current_url
                    if current_url and not current_url.startswith(("about:", "chrome:")):
                        self.acc_data["login_resume_url"] = current_url
                except Exception:
                    pass
            if driver and (not self.keep_browser_open or not self.is_running):
                try:
                    driver.quit()
                except Exception:
                    pass
            elif driver and self.keep_browser_open and self.is_running and not browser_kept:
                # Manual batch mode keeps an unexpected-error profile open for
                # inspection instead of losing the browser handle.
                self._browsers.append(driver)
            self.signals.finished.emit(self.index)

    def stop(self):
        """Stop this login and close its Chrome profile."""
        self.is_running = False
        if self.driver:
            try:
                # Capture the current checkpoint/2FA/password page before
                # quit() invalidates the WebDriver, so Mở Chọn can restore it.
                if self.platform == "facebook":
                    current_url = self.driver.current_url
                    if current_url and not current_url.startswith(("about:", "chrome:")):
                        self.acc_data["login_resume_url"] = current_url
            except Exception:
                pass
            try:
                self.driver.quit()
            except Exception:
                pass

    def _wait_after_twofa_continue(self):
        """Keep the profile alive for twelve seconds after Continue was clicked."""
        bot = self.login_bot
        if not bot or not (
            getattr(bot, "twofa_continue_submitted", False)
            or getattr(bot, "twofa_continue_clicked_at", None) is not None
        ):
            return

        clicked_at = getattr(bot, "twofa_continue_clicked_at", None)
        if clicked_at is None:
            return

        deadline = clicked_at + getattr(self, "TWOFA_SETTLE_SECONDS", 12)
        self.signals.status.emit(self.index, "Đã bấm Continue 2FA, chờ Facebook load 12s...")
        while self.is_running and time.monotonic() < deadline:
            time.sleep(min(0.2, max(0, deadline - time.monotonic())))
