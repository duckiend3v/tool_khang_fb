# import time
# import random
# import os
# from selenium.webdriver.common.by import By
# from selenium.webdriver.common.keys import Keys
# from selenium.webdriver.support.ui import WebDriverWait
# from selenium.webdriver.support import expected_conditions as EC
# from selenium.webdriver import ActionChains
# from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException

# class TikTokBot:
#     def __init__(self, driver):
#         self.driver = driver
#         # Tăng thời gian chờ lên 15s để ổn định
#         self.wait = WebDriverWait(self.driver, 15)

#     def random_sleep(self, min_s=2, max_s=5):
#         time.sleep(random.uniform(min_s, max_s))

#     # --- CÁC HÀM HỖ TRỢ (CORE HELPERS) ---
#     def safe_find_element(self, by, value, timeout=10):
#         """Tìm phần tử an toàn"""
#         try:
#             return WebDriverWait(self.driver, timeout).until(
#                 EC.presence_of_element_located((by, value))
#             )
#         except: return None

#     def safe_click(self, element):
#         """Click an toàn: Thử click thường -> thất bại thì dùng JS"""
#         try:
#             self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
#             time.sleep(1)
#             element.click()
#             return True
#         except:
#             try:
#                 # Click cưỡng bức bằng JS nếu bị che
#                 self.driver.execute_script("arguments[0].click();", element)
#                 return True
#             except: return False

#     def is_browser_alive(self):
#         """Kiểm tra trình duyệt còn sống không"""
#         try:
#             self.driver.title
#             return True
#         except: return False

#     def get_random_media(self, media_input):
#         if isinstance(media_input, list) and len(media_input) > 0:
#             return random.choice(media_input)
#         return media_input

#     # ==========================================
#     # 1. CHỨC NĂNG ĐĂNG VIDEO (UPLOAD)
#     # ==========================================
#     def upload_video(self, caption, media_list, callback=None):
#         try:
#             video_path = self.get_random_media(media_list)
#             if not video_path or not os.path.exists(video_path):
#                 if callback: callback("Lỗi: Không tìm thấy file video!")
#                 return

#             if callback: callback(">> Vào trang Upload...")
#             self.driver.get("https://www.tiktok.com/creator-center/upload?from=upload")
#             self.random_sleep(5, 8)

#             # 1. Upload File (Tìm input ẩn)
#             try:
#                 # TikTok hay dùng iframe, cần chắc chắn đang ở main content
#                 file_input = self.safe_find_element(By.XPATH, "//input[@type='file']")
#                 if file_input:
#                     if callback: callback(f">> Đang tải lên: {os.path.basename(video_path)}")
#                     file_input.send_keys(video_path)
                    
#                     # Chờ upload (Rất quan trọng với video nặng)
#                     if callback: callback(">> Đang xử lý video (Chờ 20s)...")
#                     # Vòng lặp chờ thông minh
#                     for _ in range(20):
#                         if not self.is_browser_alive(): return
#                         time.sleep(1)
#                 else:
#                     if callback: callback("Lỗi: Không tìm thấy ô chọn file")
#                     return
#             except Exception as e:
#                 if callback: callback(f"Lỗi Upload: {e}")
#                 return

#             # 2. Nhập Caption
#             if caption:
#                 try:
#                     if callback: callback(">> Nhập Caption...")
#                     # Chờ ô nhập hiện ra
#                     editor = self.safe_find_element(By.XPATH, "//div[contains(@class, 'public-DraftEditor-content')]")
#                     if editor:
#                         editor.click()
#                         # Xóa text cũ (thường là tên file tự điền)
#                         try:
#                             act = ActionChains(self.driver)
#                             act.key_down(Keys.CONTROL).send_keys('a').key_up(Keys.CONTROL).send_keys(Keys.BACKSPACE).perform()
#                             time.sleep(1)
#                         except: pass
                        
#                         editor.send_keys(caption)
#                         self.random_sleep(1, 2)
#                 except: pass

#             self.random_sleep(3, 5)
            
#             # Cuộn xuống cuối
#             self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            
#             # 3. Bấm Đăng
#             if callback: callback(">> Bấm nút Đăng...")
#             # Nút thường có chữ 'Post' hoặc 'Đăng'
#             post_btn = self.safe_find_element(By.XPATH, "//button//div[text()='Post' or text()='Đăng']")
#             if not post_btn:
#                  post_btn = self.safe_find_element(By.XPATH, "//button[contains(@class, 'btn-post')]")

#             if post_btn:
#                 self.safe_click(post_btn)
#                 time.sleep(10) # Chờ chuyển hướng
#                 if callback: callback(">> Đăng video thành công!")
#             else:
#                 if callback: callback("Lỗi: Không thấy nút Đăng (có thể chưa tải xong)")

#         except Exception as e:
#             if callback: callback(f"Lỗi quá trình đăng: {str(e)[:50]}")

#     # ==========================================
#     # 2. NUÔI NICK (FARMING) - CHẠY THEO PHÚT
#     # ==========================================
    
#     def action_scroll_foryou(self, duration_minutes, callback=None):
#         """Lướt 'Dành cho bạn' trong X phút"""
#         if callback: callback(f">> Lướt TikTok trong {duration_minutes} phút...")
        
#         end_time = time.time() + (duration_minutes * 60)
        
#         while time.time() < end_time:
#             # Kiểm tra trình duyệt còn mở không
#             if not self.is_browser_alive(): break

#             # Dùng phím Mũi tên xuống (Tốt nhất cho TikTok Web)
#             try:
#                 self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ARROW_DOWN)
#             except: pass
            
#             # Thời gian xem ngẫu nhiên cho video hiện tại (5s - 15s)
#             watch_segment = random.randint(5, 15)
            
#             # Kiểm tra thời gian còn lại
#             remaining = end_time - time.time()
#             if remaining <= 0: break
            
#             actual_watch = min(watch_segment, remaining)
            
#             # Sleep từng giây để check alive liên tục
#             for _ in range(int(actual_watch)):
#                 if not self.is_browser_alive(): break
#                 time.sleep(1)
            
#             # Tương tác ngẫu nhiên (20% Like)
#             if random.random() < 0.2: 
#                 self.action_like_current(callback)

#     def action_watch_video(self, duration_minutes, callback=None):
#         """Ngâm video (Xem kỹ) trong X phút"""
#         # Trên TikTok, 'Xem kỹ' nghĩa là ở lại trang For You nhưng lướt chậm hơn
#         if callback: callback(f">> Ngâm video (Deep Watch) {duration_minutes} phút...")
        
#         end_time = time.time() + (duration_minutes * 60)
        
#         while time.time() < end_time:
#             if not self.is_browser_alive(): break
            
#             # Lướt sang video khác
#             try: self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ARROW_DOWN)
#             except: pass

#             # Xem lâu hơn bình thường (15s - 30s)
#             watch_segment = random.randint(15, 30)
            
#             remaining = end_time - time.time()
#             if remaining <= 0: break
            
#             # Sleep loop
#             for _ in range(int(min(watch_segment, remaining))):
#                 if not self.is_browser_alive(): break
#                 time.sleep(1)

#     def action_like_current(self, callback=None):
#         try:
#             # Selector e2e của nút tim
#             like_btn = self.safe_find_element(By.XPATH, "//span[@data-e2e='like-icon-display']")
#             if like_btn:
#                 self.safe_click(like_btn)
#                 if callback: callback(">> Đã thả Tim ❤️")
#         except: pass

#     def action_follow_author(self, callback=None):
#         try:
#             if callback: callback(">> Đang Follow chủ kênh...")
#             follow_btn = self.safe_find_element(By.XPATH, "//button[@data-e2e='feed-follow']")
#             if follow_btn:
#                 self.safe_click(follow_btn)
#                 time.sleep(1)
#         except: pass

#     # ==========================================
#     # 3. SEEDING (BUFF)
#     # ==========================================
#     def run_seeding_scenario(self, config, update_callback=None):
#         target_url = config.get('url')
#         do_like = config.get('do_like')
#         do_follow = config.get('do_follow')
#         do_comment = config.get('do_comment')
#         comments_list = config.get('comments_list', [])

#         if update_callback: update_callback("Đang vào Link TikTok...")
#         self.driver.get(target_url)
#         self.random_sleep(5, 8)

#         # 1. Buff Tim
#         if do_like:
#             try:
#                 like_icon = self.safe_find_element(By.XPATH, "//span[@data-e2e='browse-like-icon' or @data-e2e='like-icon-display']")
#                 if like_icon:
#                     self.safe_click(like_icon)
#                     if update_callback: update_callback(">> Đã Tim Video")
#                     self.random_sleep(2, 4)
#             except: 
#                 if update_callback: update_callback("Lỗi: Không tìm thấy nút tim")

#         # 2. Buff Comment
#         if do_comment and comments_list:
#             try:
#                 content = random.choice(comments_list)
#                 if update_callback: update_callback("Đang viết Comment...")
                
#                 # Tìm ô input comment
#                 comment_input = self.safe_find_element(By.XPATH, "//div[@data-e2e='comment-input']//div[@contenteditable='true' or @data-e2e='comment-text']")
                
#                 if comment_input:
#                     comment_input.click()
#                     time.sleep(1)
                    
#                     # Human Typing (Gõ từng ký tự để tránh spam)
#                     for char in content:
#                         comment_input.send_keys(char)
#                         time.sleep(random.uniform(0.05, 0.15))
                    
#                     time.sleep(1)
#                     comment_input.send_keys(Keys.ENTER)
                    
#                     # Fallback: Bấm nút Post nếu Enter không ăn
#                     post_btn = self.safe_find_element(By.XPATH, "//div[@data-e2e='comment-post']")
#                     if post_btn: self.safe_click(post_btn)

#                     if update_callback: update_callback(f">> Đã Cmt: {content}")
#                     time.sleep(5)
#                 else:
#                     if update_callback: update_callback("Lỗi: Không thấy ô comment (Cần đăng nhập?)")

#             except Exception as e:
#                 if update_callback: update_callback(f"Lỗi Cmt: {str(e)[:30]}")
#         # 3. Buff Follow
#         # if do_follow:
#         #     try:
#         #         if update_callback: update_callback("Tìm nút Follow...")
#         #         # Trên TikTok Web:
#         #         # 1. Trang Profile: Nút đỏ lớn data-e2e="follow-button"
#         #         # 2. Trang Video: Nút nhỏ cạnh avatar data-e2e="video-follow-button" hoặc "browse-follow"
                
#         #         # Thử tìm nút Follow ở trang Video (phổ biến nhất khi seeding video)
#         #         follow_btn = self.safe_find_element(By.XPATH, "//button[@data-e2e='browse-follow']")
#         #         if not follow_btn:
#         #             follow_btn = self.safe_find_element(By.XPATH, "//button[contains(@class, 'follow-button')]")
                
#         #         if follow_btn:
#         #             # Kiểm tra xem đã follow chưa (thường nút sẽ đổi thành 'Tin nhắn' hoặc 'Đang follow')
#         #             text = follow_btn.text.lower()
#         #             if "follow" in text or "theo dõi" in text:
#         #                 self.safe_click(follow_btn)
#         #                 if update_callback: update_callback(">> Đã Follow kênh!")
#         #                 self.random_sleep(2, 3)
#         #             else:
#         #                 if update_callback: update_callback("Đã Follow từ trước.")
#         #     except: pass

#         # if update_callback: update_callback("Seeding Hoàn tất!")
#         # return True
        
#         # 1. BUFF FOLLOW (ĐÃ TỐI ƯU LOGIC CHECK TRẠNG THÁI)
#         if do_follow:
#             try:
#                 if update_callback: update_callback("Đang kiểm tra trạng thái Follow...")

#                 # --- BƯỚC 1: KIỂM TRA XEM ĐÃ FOLLOW CHƯA ---
#                 # Tìm các dấu hiệu đã follow: nút "Đang theo dõi", "Đã thích", "Following", "Liked"
#                 is_followed = False
                
#                 # Check các từ khóa phổ biến
#                 followed_keywords = [
#                     "//div[@aria-label='Đang theo dõi']", "//div[@aria-label='Following']",
#                     "//div[@aria-label='Đã thích']", "//div[@aria-label='Liked']",
#                     "//span[text()='Đang theo dõi']", "//span[text()='Following']",
#                     "//span[text()='Đã thích']", "//span[text()='Liked']"
#                 ]
                
#                 for xpath in followed_keywords:
#                     if self.safe_find_element(By.XPATH, xpath, timeout=2):
#                         is_followed = True
#                         break
                
#                 if is_followed:
#                     if update_callback: update_callback(">> Đã Follow từ trước (Bỏ qua).")
#                 else:
#                     # --- BƯỚC 2: NẾU CHƯA FOLLOW THÌ MỚI TÌM NÚT ĐỂ BẤM ---
#                     target_btn = None
                    
#                     # Ưu tiên 1: Tìm nút "Theo dõi" (Profile/New Page)
#                     follow_xpaths = [
#                         "//button[@aria-label='Theo dõi']", 
#                         "//button[@aria-label='Follow']",
#                         "//div[text()='Theo dõi']", 
#                         "//div[text()='Follow']"
#                     ]
                    
#                     for xp in follow_xpaths:
#                         target_btn = self.safe_find_element(By.XPATH, xp, timeout=2)
#                         if target_btn: break
                    
#                     # Ưu tiên 2: Tìm nút "Thích" (Page cổ điển)
#                     # Mẹo: Nút thích Page thường nằm trong cụm header, ta tìm nút có kích thước lớn hoặc class đặc biệt
#                     # Hoặc đơn giản là tìm nút Thích mà KHÔNG PHẢI là nút thích bài viết (thường bài viết có aria-label='Thích, bình luận...')
#                     if not target_btn:
#                         # Tìm nút thích đơn giản
#                         like_xpaths = ["//div[@aria-label='Thích']", "//div[@aria-label='Like']"]
#                         for xp in like_xpaths:
#                             elements = self.driver.find_elements(By.XPATH, xp)
#                             if elements:
#                                 # Lấy nút đầu tiên tìm thấy (Thường header load trước feed)
#                                 target_btn = elements[0]
#                                 break

#                     # --- BƯỚC 3: THỰC HIỆN CLICK ---
#                     if target_btn:
#                         if self.safe_click(target_btn):
#                             if update_callback: update_callback(">> Đã bấm Follow/Thích Page!")
#                             self.random_sleep(3, 5)
#                     else:
#                         if update_callback: update_callback("Không tìm thấy nút Follow.")

#             except Exception as e:
#                 # print(e) # Debug nếu cần
#                 pass

#     # ==========================================
#     # QUY TRÌNH CHÍNH (FARM)
#     # ==========================================
#     def run_foryou_farm(self, config, update_callback=None):
#         if update_callback: update_callback("Đang mở TikTok ForYou...")
#         self.driver.get("https://www.tiktok.com/foryou")
#         self.random_sleep(5, 7)

#         # Check Login (Cảnh báo nhẹ nếu chưa login)
#         if self.safe_find_element(By.XPATH, "//button[@data-e2e='top-login-button']"):
#              if update_callback: update_callback("Cảnh báo: Chưa đăng nhập!")

#         # --- A. ĐĂNG VIDEO ---
#         post_cfg = config.get('post', {})
#         if post_cfg.get('enable'):
#             if post_cfg.get('status') or post_cfg.get('reels') or post_cfg.get('story'):
#                 self.upload_video(
#                     post_cfg.get('content', ''), 
#                     post_cfg.get('media_files', []), 
#                     update_callback
#                 )

#         # --- B. NUÔI NICK ---
#         farm_cfg = config.get('farm', {})
#         if farm_cfg.get('enable'):
#             # 1. Lướt Feed (Theo Phút)
#             if farm_cfg.get('feed'):
#                 min_t, max_t = farm_cfg.get('feed_range', (5, 10))
#                 duration = random.randint(min_t, max_t)
#                 self.action_scroll_foryou(duration, update_callback)
                
#             # 2. Xem Watch (Theo Phút)
#             if farm_cfg.get('watch'):
#                 min_t, max_t = farm_cfg.get('watch_range', (10, 20))
#                 duration = random.randint(min_t, max_t)
#                 self.action_watch_video(duration, update_callback)

#             # 3. Follow
#             if farm_cfg.get('friend'):
#                 if random.random() < 0.15: # 15% cơ hội follow
#                     self.action_follow_author(update_callback)

#         if update_callback: update_callback("Hoàn thành nhiệm vụ!")
#         return True






import time
import random
import os
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver import ActionChains
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException

class TikTokBot:
    def __init__(self, driver):
        self.driver = driver
        # Tăng thời gian chờ lên 15s để ổn định
        self.wait = WebDriverWait(self.driver, 15)

    def random_sleep(self, min_s=2, max_s=5):
        time.sleep(random.uniform(min_s, max_s))

    # --- CÁC HÀM HỖ TRỢ (CORE HELPERS) ---
    def safe_find_element(self, by, value, timeout=10):
        """Tìm phần tử an toàn"""
        try:
            return WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, value))
            )
        except: return None

    def safe_click(self, element):
        """Click an toàn: Thử click thường -> thất bại thì dùng JS"""
        try:
            self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
            time.sleep(1)
            element.click()
            return True
        except:
            try:
                # Click cưỡng bức bằng JS nếu bị che
                self.driver.execute_script("arguments[0].click();", element)
                return True
            except: return False

    def is_browser_alive(self):
        """Kiểm tra trình duyệt còn sống không"""
        try:
            self.driver.title
            return True
        except: return False

    def get_random_media(self, media_input):
        if isinstance(media_input, list) and len(media_input) > 0:
            return random.choice(media_input)
        return media_input

    # ==========================================
    # 1. CHỨC NĂNG ĐĂNG VIDEO (UPLOAD) - CẬP NHẬT LOGIC RANDOM
    # ==========================================
    def upload_video(self, captions_list, media_pool, callback=None):
        try:
            # --- 1. Random 1 Video từ kho ---
            video_path = self.get_random_media(media_pool)
            if not video_path or not os.path.exists(video_path):
                if callback: callback("Lỗi: Không tìm thấy file video hoặc kho trống!")
                return

            # --- 2. Random 1 Caption từ list ---
            caption = ""
            if captions_list:
                caption = random.choice(captions_list)

            if callback: callback(f">> Bắt đầu Upload: {os.path.basename(video_path)}...")
            self.driver.get("https://www.tiktok.com/creator-center/upload?from=upload")
            self.random_sleep(5, 8)

            # --- 3. Upload File (Giữ nguyên Selector cũ) ---
            try:
                file_input = self.safe_find_element(By.XPATH, "//input[@type='file']")
                if file_input:
                    file_input.send_keys(video_path)
                    
                    if callback: callback(">> Đang xử lý video (Chờ 20s)...")
                    # Vòng lặp chờ thông minh
                    for _ in range(20):
                        if not self.is_browser_alive(): return
                        time.sleep(1)
                else:
                    if callback: callback("Lỗi: Không tìm thấy ô chọn file")
                    return
            except Exception as e:
                if callback: callback(f"Lỗi Upload: {e}")
                return

            # --- 4. Nhập Caption (Giữ nguyên Selector cũ) ---
            if caption:
                try:
                    if callback: callback(f">> Caption: {caption[:20]}...")
                    # Chờ ô nhập hiện ra
                    editor = self.safe_find_element(By.XPATH, "//div[contains(@class, 'public-DraftEditor-content')]")
                    if editor:
                        editor.click()
                        # Xóa text cũ (thường là tên file tự điền)
                        try:
                            act = ActionChains(self.driver)
                            act.key_down(Keys.CONTROL).send_keys('a').key_up(Keys.CONTROL).send_keys(Keys.BACKSPACE).perform()
                            time.sleep(1)
                        except: pass
                        
                        editor.send_keys(caption)
                        self.random_sleep(1, 2)
                except: pass

            self.random_sleep(3, 5)
            
            # Cuộn xuống cuối
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            
            # --- 5. Bấm Đăng (Giữ nguyên Selector cũ) ---
            if callback: callback(">> Bấm nút Đăng...")
            post_btn = self.safe_find_element(By.XPATH, "//button//div[text()='Post' or text()='Đăng']")
            if not post_btn:
                 post_btn = self.safe_find_element(By.XPATH, "//button[contains(@class, 'btn-post')]")

            if post_btn:
                self.safe_click(post_btn)
                time.sleep(10) # Chờ chuyển hướng
                if callback: callback(">> Đăng video thành công!")
            else:
                if callback: callback("Lỗi: Không thấy nút Đăng (có thể chưa tải xong)")

        except Exception as e:
            if callback: callback(f"Lỗi quá trình đăng: {str(e)[:50]}")

    # ==========================================
    # 2. NUÔI NICK (FARMING)
    # ==========================================
    
    def action_scroll_foryou(self, duration_minutes, callback=None):
        if callback: callback(f">> Lướt TikTok trong {duration_minutes} phút...")
        end_time = time.time() + (duration_minutes * 60)
        
        while time.time() < end_time:
            if not self.is_browser_alive(): break

            try: self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ARROW_DOWN)
            except: pass
            
            # Thời gian xem ngẫu nhiên
            watch_segment = random.randint(5, 15)
            remaining = end_time - time.time()
            if remaining <= 0: break
            
            for _ in range(int(min(watch_segment, remaining))):
                if not self.is_browser_alive(): break
                time.sleep(1)
            
            if random.random() < 0.2: 
                self.action_like_current(callback)

    def action_watch_video(self, duration_minutes, callback=None):
        if callback: callback(f">> Ngâm video (Deep Watch) {duration_minutes} phút...")
        end_time = time.time() + (duration_minutes * 60)
        
        while time.time() < end_time:
            if not self.is_browser_alive(): break
            try: self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ARROW_DOWN)
            except: pass

            watch_segment = random.randint(15, 30)
            remaining = end_time - time.time()
            if remaining <= 0: break
            
            for _ in range(int(min(watch_segment, remaining))):
                if not self.is_browser_alive(): break
                time.sleep(1)

    def action_like_current(self, callback=None):
        try:
            like_btn = self.safe_find_element(By.XPATH, "//span[@data-e2e='like-icon-display']")
            if like_btn:
                self.safe_click(like_btn)
                if callback: callback(">> Đã thả Tim ❤️")
        except: pass

    def action_follow_author(self, callback=None):
        try:
            if callback: callback(">> Đang Follow chủ kênh...")
            follow_btn = self.safe_find_element(By.XPATH, "//button[@data-e2e='feed-follow']")
            if follow_btn:
                self.safe_click(follow_btn)
                time.sleep(1)
        except: pass

    # ==========================================
    # 3. SEEDING (BUFF) - SỬA LẠI THEO LUỒNG TASK
    # ==========================================
    def run_seeding_scenario(self, config, update_callback=None):
        target_url = config.get('url')
        task_type = config.get('type') # 'follow', 'post', 'video'
        
        do_like = config.get('do_like')
        do_follow = config.get('do_follow')
        do_comment = config.get('do_comment')
        comments_list = config.get('comments_list', [])

        if update_callback: update_callback(f"Đang vào Link TikTok ({task_type})...")
        self.driver.get(target_url)
        self.random_sleep(5, 8)

        # === 1. LOGIC FOLLOW (CHẠY TRƯỚC) ===
        if task_type == 'follow':
            if do_follow:
                try:
                    if update_callback: update_callback("Tìm nút Follow...")
                    
                    # 1. Tìm nút Follow (Dùng Selector chuẩn TikTok)
                    # TikTok Web Video: button data-e2e='browse-follow'
                    # TikTok Profile: button data-e2e='follow-button'
                    follow_btn = self.safe_find_element(By.XPATH, "//button[@data-e2e='browse-follow']")
                    if not follow_btn:
                        follow_btn = self.safe_find_element(By.XPATH, "//button[@data-e2e='follow-button']")
                    
                    if follow_btn:
                        # Check text để xem đã follow chưa
                        txt = follow_btn.text.lower()
                        if "follow" in txt or "theo dõi" in txt:
                            if "following" not in txt and "đang" not in txt:
                                self.safe_click(follow_btn)
                                if update_callback: update_callback(">> Đã Follow kênh!")
                                self.random_sleep(2, 3)
                            else:
                                if update_callback: update_callback(">> Đã Follow từ trước.")
                        else:
                             # Trường hợp nút chỉ hiện icon, cứ bấm thử
                             self.safe_click(follow_btn)
                             if update_callback: update_callback(">> Đã bấm Follow")
                    else:
                        if update_callback: update_callback("Lỗi: Không tìm thấy nút Follow")
                except: pass
            
            # Xong nhiệm vụ Follow thì thoát
            if update_callback: update_callback("Hoàn thành Follow!")
            return True

        # === 2. LOGIC TƯƠNG TÁC (VIDEO) ===
        
        # A. Buff Tim
        if do_like:
            try:
                # Selector chuẩn TikTok: browse-like-icon
                like_icon = self.safe_find_element(By.XPATH, "//span[@data-e2e='browse-like-icon' or @data-e2e='like-icon-display']")
                if like_icon:
                    self.safe_click(like_icon)
                    if update_callback: update_callback(">> Đã Tim Video")
                    self.random_sleep(2, 4)
            except: 
                if update_callback: update_callback("Lỗi: Không tìm thấy nút tim")

        # B. Buff Comment
        if do_comment and comments_list:
            try:
                content = random.choice(comments_list)
                if update_callback: update_callback("Đang viết Comment...")
                
                # Selector chuẩn TikTok: comment-input
                comment_input = self.safe_find_element(By.XPATH, "//div[@data-e2e='comment-input']//div[@contenteditable='true' or @data-e2e='comment-text']")
                
                if comment_input:
                    comment_input.click()
                    time.sleep(1)
                    
                    # Human Typing
                    for char in content:
                        comment_input.send_keys(char)
                        time.sleep(random.uniform(0.05, 0.15))
                    
                    time.sleep(1)
                    comment_input.send_keys(Keys.ENTER)
                    
                    # Fallback nút Post
                    post_btn = self.safe_find_element(By.XPATH, "//div[@data-e2e='comment-post']")
                    if post_btn: self.safe_click(post_btn)

                    if update_callback: update_callback(f">> Đã Cmt: {content}")
                    time.sleep(5)
                else:
                    if update_callback: update_callback("Lỗi: Không thấy ô comment")

            except Exception as e:
                if update_callback: update_callback(f"Lỗi Cmt: {str(e)[:30]}")

        if update_callback: update_callback("Seeding Hoàn tất!")
        return True

    # ==========================================
    # QUY TRÌNH CHÍNH (MASTER FARM)
    # ==========================================
    def run_foryou_farm(self, config, update_callback=None):
        if update_callback: update_callback("Đang mở TikTok ForYou...")
        self.driver.get("https://www.tiktok.com/foryou")
        self.random_sleep(5, 7)

        # Check Login
        if self.safe_find_element(By.XPATH, "//button[@data-e2e='top-login-button']"):
             if update_callback: update_callback("Cảnh báo: Chưa đăng nhập!")

        # --- A. ĐĂNG VIDEO (CẬP NHẬT CONFIG MỚI) ---
        post_cfg = config.get('post', {})
        if post_cfg.get('enable'):
            # Lấy list caption và list media từ config mới
            captions = post_cfg.get('captions', [])
            media_pool = post_cfg.get('media_files', [])
            
            # TikTok thường chỉ đăng video (status/reels/story đều là video)
            if post_cfg.get('status') or post_cfg.get('reels') or post_cfg.get('story'):
                self.upload_video(captions, media_pool, update_callback)

        # --- B. NUÔI NICK (Giữ nguyên) ---
        farm_cfg = config.get('farm', {})
        if farm_cfg.get('enable'):
            if farm_cfg.get('feed'):
                min_t, max_t = farm_cfg.get('feed_range', (5, 10))
                self.action_scroll_foryou(random.randint(min_t, max_t), update_callback)
            
            if farm_cfg.get('watch'):
                min_t, max_t = farm_cfg.get('watch_range', (10, 20))
                self.action_watch_video(random.randint(min_t, max_t), update_callback)

            if farm_cfg.get('friend'):
                if random.random() < 0.15:
                    self.action_follow_author(update_callback)

        if update_callback: update_callback("Hoàn thành nhiệm vụ!")
        return True