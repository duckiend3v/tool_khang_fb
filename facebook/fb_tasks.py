# facebook/fb_tasks.py
import time
import random
import os
import json
import re
import base64
import hashlib
import hmac
import struct
from urllib.parse import parse_qs, urlparse
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver import ActionChains
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException

class FacebookBot:
    def __init__(self, driver):
        self.driver = driver
        # Tăng thời gian chờ mặc định lên 10s để mạng lag vẫn sống
        self.wait = WebDriverWait(self.driver, 10)
        self.login_button_clicked = False
        self.login_button_clicked_at = None
        self.twofa_challenge_detected = False
        self.twofa_continue_submitted = False

    def random_sleep(self, min_s=2, max_s=5):
        time.sleep(random.uniform(min_s, max_s))

    # --- CÁC HÀM HELPER GIÚP ỔN ĐỊNH (CORE) ---
    def safe_find_element(self, by, value, timeout=5):
        """Tìm phần tử an toàn, không crash nếu không thấy"""
        try:
            return WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, value))
            )
        except:
            return None

    def safe_click(self, element):
        """Click bất chấp: Thử click thường -> thất bại thì click bằng JS"""
        try:
            # Scroll tức thời; smooth-scroll + sleep 1s làm luồng login bị chậm rõ rệt.
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
            element.click()
            return True
        except ElementClickInterceptedException:
            # Bị che? Dùng JS click xuyên táo
            try:
                self.driver.execute_script("arguments[0].click();", element)
                return True
            except: 
                return False
        except:
            return False

    def is_browser_alive(self):
        """Kiểm tra trình duyệt còn mở không"""
        try: 
            self.driver.title
            return True
        except: 
            return False

    def _clean_scrape_text(self, text):
        if not text:
            return ""

        blocked_phrases = [
            "Quyền riêng tư", "Điều khoản", "Quảng cáo", "Lựa chọn quảng cáo",
            "Cookie", "Điều khoản dịch vụ", "Chính sách", "Chính sách quyền riêng tư"
        ]

        lines = []
        for raw_line in text.splitlines():
            line = " ".join(raw_line.split()).strip()
            if not line or len(line) < 3:
                continue
            if any(phrase in line for phrase in blocked_phrases):
                continue
            lines.append(line)

        deduped = []
        for line in lines:
            if line not in deduped:
                deduped.append(line)
        return "\n".join(deduped).strip()

    def _normalize_post_url(self, url):
        if not url:
            return ""
        cleaned = url.strip()
        if cleaned.startswith("/"):
            cleaned = f"https://www.facebook.com{cleaned}"
        if "facebook.com" not in cleaned:
            return ""

        blocked_tokens = (
            "/privacy/", "/policies/", "/ads/", "/help/", "/settings/",
            "/login/", "/messages/", "/friends/", "/watch/", "/reel/?",
            "/reels/", "/photos_by", "/likes", "/followers", "/following",
        )
        if any(token in cleaned for token in blocked_tokens):
            return ""

        valid_tokens = (
            "/posts/", "/photos/", "/videos/", "/reel/", "permalink.php",
            "story_fbid=", "fbid=", "id=", "/share/p/", "/share/v/", "pfbid"
        )
        if not any(token in cleaned for token in valid_tokens):
            return ""
        if "/reel" in cleaned and cleaned.rstrip("/").endswith("/reel"):
            return ""
        return cleaned

    def _canonicalize_post_url(self, url):
        normalized = self._normalize_post_url(url)
        if not normalized:
            return ""

        base = normalized.split("&__")[0]
        if "?" not in base:
            return base

        head, query = base.split("?", 1)
        kept = []
        for part in query.split("&"):
            if part.startswith(("story_fbid=", "fbid=", "id=")):
                kept.append(part)
        return f"{head}?{'&'.join(kept)}" if kept else head

    def _extract_post_text(self, post):
        selectors = [
            ".//div[@data-ad-preview='message']",
            ".//div[contains(@class, 'userContent')]",
            ".//div[@dir='auto'][.//span[@dir='auto']]",
        ]
        text_parts = []
        for selector in selectors:
            for elem in post.find_elements(By.XPATH, selector):
                text = self._clean_scrape_text(elem.text or "")
                if text and text not in text_parts:
                    text_parts.append(text)

        if not text_parts:
            for elem in post.find_elements(By.XPATH, ".//span[@dir='auto']"):
                text = self._clean_scrape_text(elem.text or "")
                if text and text not in text_parts:
                    text_parts.append(text)

        return "\n".join(text_parts).strip()

    def _extract_post_media(self, post):
        media_urls = []
        blocked_tokens = (
            "static.xx.fbcdn.net",
            "/rsrc.php/",
            "scontent.xx.fbcdn.net",
            "safe_image.php",
            "emoji.php",
            "profile_pic",
            "s160x160",
            "p50x50",
            "c0.",
        )

        for img in post.find_elements(By.XPATH, ".//img[@src]"):
            src = (img.get_attribute("src") or "").strip()
            if not src or "fbcdn" not in src:
                continue
            if any(token in src for token in blocked_tokens):
                continue
            if src not in media_urls:
                media_urls.append(src)

        for video in post.find_elements(By.XPATH, ".//video[@src]"):
            src = (video.get_attribute("src") or "").strip()
            if src and src not in media_urls:
                media_urls.append(src)

        return media_urls

    def _scrape_post_detail(self, post_url):
        self.driver.get(post_url)
        self.random_sleep(4, 6)

        article = self.safe_find_element(By.XPATH, "//div[@role='article']", timeout=6)
        if article is None:
            return "", []

        text_blocks = []
        for selector in (
            ".//div[@data-ad-preview='message']",
            ".//div[contains(@class, 'userContent')]",
        ):
            for elem in article.find_elements(By.XPATH, selector):
                text = self._clean_scrape_text(elem.text or "")
                if text and text not in text_blocks:
                    text_blocks.append(text)

        if not text_blocks:
            for elem in article.find_elements(By.XPATH, ".//span[@dir='auto']"):
                text = self._clean_scrape_text(elem.text or "")
                if text and len(text) > 20 and text not in text_blocks:
                    text_blocks.append(text)

        return "\n".join(text_blocks).strip(), self._extract_post_media(article)

    def _collect_candidate_links_from_post(self, post):
        candidates = []
        for link in post.find_elements(By.XPATH, ".//a[@href]"):
            href = (link.get_attribute("href") or "").strip()
            canonical = self._canonicalize_post_url(href)
            if canonical and canonical not in candidates:
                candidates.append(canonical)
        return candidates

    def _to_posts_tab_url(self, page_url):
        if not page_url:
            return page_url
        if "sk=posts" in page_url:
            return page_url
        if "profile.php" in page_url:
            separator = "&" if "?" in page_url else "?"
            return f"{page_url}{separator}sk=posts"
        separator = "&" if "?" in page_url else "?"
        return f"{page_url}{separator}sk=posts"

    def _ensure_posts_tab_open(self):
        tab = self.safe_find_element(
            By.XPATH,
            "//a[@role='link' and (.//span[normalize-space()='Bài viết'] or .//span[normalize-space()='Posts'])]",
            timeout=3
        )
        if tab:
            self.safe_click(tab)
            self.random_sleep(3, 5)

    def scrape_posts_from_page(self, page_url, page_id, max_posts=10, callback=None, folder_name=None):
        try:
            target_url = self._to_posts_tab_url(page_url)
            if callback:
                callback(f">> Cào bài từ trang: {target_url}")
            self.driver.get(target_url)
            self.random_sleep(5, 8)
            self._ensure_posts_tab_open()

            if folder_name:
                posts_dir = os.path.join("data", "pages", folder_name, "posts")
            else:
                posts_dir = os.path.join("data", "pages", page_id, "posts")
            os.makedirs(posts_dir, exist_ok=True)

            posts_data = []
            seen_posts = set()
            candidate_links = []
            scroll_count = 0
            max_scrolls = 20
            debug_stats = {
                "articles_seen": 0,
                "candidate_links": 0,
                "detail_empty_content": 0,
                "duplicates": 0,
            }
            debug_href_samples = []

            while len(candidate_links) < max_posts and scroll_count < max_scrolls:
                post_elements = self.driver.find_elements(
                    By.XPATH,
                    "//div[@role='article' or contains(@class, 'userContentWrapper')]"
                )
                if callback:
                    callback(f">> Lần quét {scroll_count + 1}: thấy {len(post_elements)} khối bài")

                for post in post_elements:
                    try:
                        debug_stats["articles_seen"] += 1
                        raw_hrefs = []
                        for link in post.find_elements(By.XPATH, ".//a[contains(@href, '/posts/') or contains(@href, 'pfbid') or contains(@href, 'fbid=')]"):
                            href = (link.get_attribute("href") or "").strip()
                            if href and href not in raw_hrefs:
                                raw_hrefs.append(href)
                            canonical = self._canonicalize_post_url(href)
                            if canonical and canonical not in candidate_links:
                                candidate_links.append(canonical)
                                debug_stats["candidate_links"] += 1
                            break # Only 1 per post
                        if len(debug_href_samples) < 5:
                            debug_href_samples.append(raw_hrefs[:10])
                    except Exception:
                        continue

                self.human_scroll(800, 1200)
                scroll_count += 1
                self.random_sleep(3, 5)

            for post_link in candidate_links[:max_posts]:
                if post_link in seen_posts:
                    debug_stats["duplicates"] += 1
                    continue

                try:
                    post_text, media_urls = self._scrape_post_detail(post_link)
                    if len(post_text.strip()) < 10 and not media_urls:
                        debug_stats["detail_empty_content"] += 1
                        continue

                    seen_posts.add(post_link)
                    post_data = {
                        "post_url": post_link,
                        "text": post_text,
                        "media": media_urls[:10],
                        "timestamp": time.time(),
                        "page_url": target_url
                    }
                    post_file = os.path.join(posts_dir, f"post_{len(posts_data)}.json")
                    with open(post_file, 'w', encoding='utf-8') as f:
                        json.dump(post_data, f, ensure_ascii=False, indent=2)

                    posts_data.append(post_data)
                    preview = post_text[:50] if post_text else "[media-only post]"
                    if callback:
                        callback(f">> Đã cào bài {len(posts_data)}: {preview}")
                except Exception:
                    continue

            if not posts_data:
                debug_file = os.path.join(posts_dir, "_debug.json")
                with open(debug_file, 'w', encoding='utf-8') as f:
                    json.dump({
                        "page_url_requested": page_url,
                        "page_url_posts_tab": target_url,
                        "page_url_actual": self.driver.current_url,
                        "page_title": self.driver.title,
                        "scroll_count": scroll_count,
                        "detected_articles": len(self.driver.find_elements(By.XPATH, "//div[@role='article']")),
                        "stats": debug_stats,
                        "candidates": candidate_links[:10],
                        "href_samples": debug_href_samples,
                    }, f, ensure_ascii=False, indent=2)
                if callback:
                    callback(f">> Không lấy được bài nào. Đã ghi debug vào {debug_file}")

            if callback:
                callback(f">> Hoàn thành cào {len(posts_data)} bài vào {posts_dir}")
            return posts_dir

        except Exception as e:
            if callback:
                callback(f"Lỗi cào bài: {str(e)[:50]}")
            return None

    def is_browser_alive(self):
        try: self.driver.title; return True
        except: return False

    def get_random_media(self, media_input):
        if isinstance(media_input, list) and len(media_input) > 0:
            return random.choice(media_input)
        return media_input

    def human_scroll(self, min_dist=400, max_dist=700):
        target_distance = random.randint(min_dist, max_dist)
        scrolled = 0
        while scrolled < target_distance:
            step = random.randint(10, 50)
            if scrolled + step > target_distance: step = target_distance - scrolled
            self.driver.execute_script(f"window.scrollBy(0, {step});")
            scrolled += step
            time.sleep(random.uniform(0.01, 0.05))
            if not self.is_browser_alive(): break

    # ==========================
    # PHẦN 2: NUÔI NICK
    # ==========================
    def action_feed_and_like(self, duration_minutes, callback=None):
        if callback: callback(f">> Lướt Feed {duration_minutes} phút...")
        end_time = time.time() + (duration_minutes * 60)
        while time.time() < end_time:
            if not self.is_browser_alive(): break
            # Scroll tự nhiên
            if random.choice(['js', 'key']) == 'js': self.human_scroll(600, 900)
            else: 
                try: ActionChains(self.driver).send_keys(Keys.PAGE_DOWN).perform()
                except: pass
            self.random_sleep(3, 8)
            
            # Like dạo
            if random.random() < 0.3:
                try:
                    btns = self.driver.find_elements(By.XPATH, "//div[@aria-label='Like' or @aria-label='Thích']")
                    if btns:
                        target = random.choice(btns[:3])
                        if self.safe_click(target):
                            if callback: callback(">> Đã Like dạo"); self.random_sleep(2, 4)
                except: pass

    def action_watch_video(self, duration_minutes, callback=None):
        try:
            if callback: callback(f">> Xem Watch ({duration_minutes} phút)...")
            self.driver.get("https://www.facebook.com/watch")
            self.random_sleep(5, 7)
            try: self.driver.find_element(By.TAG_NAME, 'body').click()
            except: pass
            
            end_time = time.time() + (duration_minutes * 60)
            while time.time() < end_time:
                if not self.is_browser_alive(): break
                try:
                    body = self.driver.find_element(By.TAG_NAME, 'body')
                    if random.choice([True, False]): body.send_keys(Keys.PAGE_DOWN)
                    else: body.send_keys(Keys.SPACE)
                except: pass
                watch_segment = random.randint(15, 45) 
                remaining = end_time - time.time()
                if remaining <= 0: break
                for _ in range(int(min(watch_segment, remaining))):
                    if not self.is_browser_alive(): break;
                    time.sleep(1)
        except: pass

    def action_add_friend(self, count, callback=None):
        try:
            if callback: callback(f">> Kết bạn ({count} người)...")
            self.driver.get("https://www.facebook.com/friends/suggestions")
            self.random_sleep(4, 6)
            btns = self.driver.find_elements(By.XPATH, "//div[@aria-label='Thêm bạn bè' or @aria-label='Add Friend']")
            if not btns: btns = self.driver.find_elements(By.XPATH, "//span[text()='Thêm bạn bè' or text()='Add Friend']")
            
            processed = 0
            for btn in btns:
                if processed >= count: break
                if self.safe_click(btn):
                    processed += 1
                    if callback: callback(f">> Đã gửi lời mời ({processed})"); self.random_sleep(3, 6)
        except: pass

    def action_join_group(self, count, callback=None):
        try:
            if callback: callback(f">> Vào ({count} nhóm)...")
            self.driver.get("https://www.facebook.com/groups/discover/")
            self.random_sleep(5, 7)
            btns = self.driver.find_elements(By.XPATH, "//div[@aria-label='Tham gia nhóm' or @aria-label='Join group']")
            processed = 0
            for btn in btns:
                if processed >= count: break
                if self.safe_click(btn):
                    processed += 1
                    if callback: callback(f">> Đã xin vào nhóm ({processed})"); self.random_sleep(3, 5)
        except: pass

    def action_check_notify(self, callback=None):
        try:
            if callback: callback(">> Check Thông báo")
            btn = self.safe_find_element(By.XPATH, "//div[@aria-label='Thông báo' or @aria-label='Notifications']")
            if btn: self.safe_click(btn); self.random_sleep(2, 4); self.driver.find_element(By.TAG_NAME, 'body').click()
        except: pass

    # ==========================
    # PHẦN 1: ĐĂNG BÀI (LOGIC MỚI - SELECTOR CŨ)
    # ==========================
    
    # Cập nhật tham số để nhận List và Range
    def post_status(self, captions_list, media_pool, media_range, callback=None):
        try:
            # --- 0. CHUẨN BỊ DỮ LIỆU RANDOM ---
            # Random Caption
            content = ""
            if captions_list:
                content = random.choice(captions_list)
            
            # Random Media (Lấy nhiều ảnh)
            selected_media = []
            if media_pool:
                min_f, max_f = media_range
                count = random.randint(min_f, max_f)
                count = min(count, len(media_pool)) # Không lấy quá số file đang có
                if count > 0:
                    selected_media = random.sample(media_pool, count)

            if callback: callback(f">> Post Status: {len(selected_media)} file | Cap: {content[:15]}...")
            
            self.driver.get("https://www.facebook.com/")
            self.random_sleep(4, 6)

            # --- 1. MỞ POPUP (Code cũ giữ nguyên) ---
            create_post = self.safe_find_element(By.XPATH, "//span[contains(text(), 'bạn đang nghĩ gì')]")
            if not create_post: create_post = self.safe_find_element(By.XPATH, "//span[contains(text(), 'on your mind')]")
            if not create_post: create_post = self.safe_find_element(By.XPATH, "//div[contains(@aria-label, 'tạo bài viết') or contains(@aria-label, 'Create a post')]")
            
            if create_post:
                self.safe_click(create_post)
            else:
                if callback: callback("Lỗi: Không thấy nút đăng bài")
                return

            self.random_sleep(3, 5)

            # Chờ Modal (Code cũ giữ nguyên)
            try:
                WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.XPATH, "//div[@role='dialog']")))
            except: pass

            # --- 2. NHẬP CAPTION (Code cũ giữ nguyên) ---
            if content:
                txt_box_xpath = "//div[@role='dialog']//div[@role='textbox']"
                txt_box = self.safe_find_element(By.XPATH, txt_box_xpath)
                
                if txt_box:
                    self.driver.execute_script("arguments[0].click();", txt_box)
                    self.random_sleep(1, 2)
                    try:
                        actions = ActionChains(self.driver)
                        actions.move_to_element(txt_box).click().send_keys(content).perform()
                    except:
                        txt_box.send_keys(content)
                    self.random_sleep(1, 2)

            # --- 3. UPLOAD NHIỀU MEDIA (Logic Mới) ---
            if selected_media:
                # Tìm input file trong dialog (Code cũ)
                file_input = self.safe_find_element(By.XPATH, "//div[@role='dialog']//input[@type='file']")
                if not file_input: file_input = self.safe_find_element(By.XPATH, "//input[@type='file']")

                if file_input:
                    # KỸ THUẬT MỚI: Nối đường dẫn bằng \n để up nhiều ảnh 1 lúc
                    all_paths = "\n".join(selected_media)
                    file_input.send_keys(all_paths)
                    
                    if callback: callback(">> Đang tải media lên...")
                    
                    # Chờ loading lâu hơn vì nhiều ảnh
                    time.sleep(5 + len(selected_media) * 3)
                    
                    try: # Chờ thanh progress biến mất
                        WebDriverWait(self.driver, 20).until_not(EC.presence_of_element_located((By.XPATH, "//div[@role='progressbar']")))
                    except: pass

            # --- 4. BẤM ĐĂNG (Code cũ giữ nguyên) ---
            post_btn = self.safe_find_element(By.XPATH, "//div[@role='dialog']//div[@aria-label='Đăng' or @aria-label='Post']")
            if post_btn:
                for _ in range(10): 
                    if post_btn.get_attribute('aria-disabled') == 'true': time.sleep(1)
                    else: break
                
                self.driver.execute_script("arguments[0].click();", post_btn)
                time.sleep(10)
                if callback: callback(">> Đã đăng Status thành công!")
            else:
                if callback: callback("Lỗi: Không tìm thấy nút Đăng")
            
        except Exception as e:
            if callback: callback(f"Lỗi Status: {str(e)[:50]}")

    def post_story(self, media_list, callback=None):
        try:
            # Story chỉ lấy 1 ảnh random
            media_path = self.get_random_media(media_list)
            if not media_path: return
            if callback: callback(">> Đăng Story...")
            self.driver.get("https://www.facebook.com/stories/create")
            self.random_sleep(5, 7)
            
            fi = self.safe_find_element(By.XPATH, "//input[@type='file']")
            if fi: fi.send_keys(media_path)
            self.random_sleep(5, 8)
            btn = self.safe_find_element(By.XPATH, "//div[@aria-label='Chia sẻ lên tin' or @aria-label='Share to Story']")
            if btn: self.safe_click(btn); time.sleep(5); 
            if callback: callback(">> Xong Story")
        except: pass

    def post_reels(self, content, media_list, callback=None):
        try:
            # Reels chỉ lấy 1 video random
            media_path = self.get_random_media(media_list)
            if not media_path: return
            if callback: callback(">> Đăng Reels...")
            self.driver.get("https://www.facebook.com/reels/create")
            self.random_sleep(5, 7)
            
            fi = self.safe_find_element(By.XPATH, "//div[@role='dialog']//input[@type='file']")
            if not fi: fi = self.safe_find_element(By.XPATH, "//input[@type='file']")
            if fi: fi.send_keys(media_path)
            else: return

            if callback: callback(">> Đang xử lý video...")
            max_steps = 5; step_count = 0
            while step_count < max_steps:
                time.sleep(3)
                btn_post = self.safe_find_element(By.XPATH, "//div[@aria-label='Đăng' or @aria-label='Post']")
                if btn_post:
                    if btn_post.get_attribute('aria-disabled') == 'true':
                        if callback: callback("Wait loading..."); time.sleep(2); continue
                    
                    if content: # Nhập caption bước cuối
                        box = self.safe_find_element(By.XPATH, "//div[@role='dialog']//div[@role='textbox']")
                        if box:
                            try: self.driver.execute_script("arguments[0].click();", box); box.send_keys(content); time.sleep(1)
                            except: pass
                    
                    self.driver.execute_script("arguments[0].click();", btn_post)
                    if callback: callback(">> Đã bấm Đăng Reels!"); time.sleep(15); break

                btn_next = self.safe_find_element(By.XPATH, "//div[@aria-label='Tiếp' or @aria-label='Next']")
                if btn_next:
                    if btn_next.get_attribute('aria-disabled') == 'true': time.sleep(2); continue
                    self.driver.execute_script("arguments[0].click();", btn_next)
                    step_count += 1
                else: time.sleep(2)
        except Exception as e:
            if callback: callback(f"Lỗi Reels: {str(e)[:50]}")

    def post_to_page(self, page_id, page_name, captions_list=None, media_pool=None, media_range=(1,1), use_scraped_data=False, callback=None):
        try:
            # --- 0. CHUYỂN SANG PAGE CONTEXT ---
            if callback: callback(f">> Chuyển sang Page: {page_name}")
            if not self.switch_to_page_context(page_name, page_id):
                if callback: callback("Lỗi: Không thể chuyển sang Page context")
                return

            self.random_sleep(3, 5)

            # --- 1. LẤY DỮ LIỆU TỪ SCRAPED HOẶC CONFIG ---
            if use_scraped_data:
                posts_dir = os.path.join("data", "pages", page_id, "posts")
                if os.path.exists(posts_dir):
                    post_files = [f for f in os.listdir(posts_dir) if f.endswith('.json')]
                    if post_files:
                        # Random chọn một post
                        selected_file = random.choice(post_files)
                        with open(os.path.join(posts_dir, selected_file), 'r', encoding='utf-8') as f:
                            post_data = json.load(f)
                        
                        content = post_data.get('text', '')
                        selected_media = post_data.get('media', [])[:media_range[1]]  # Giới hạn theo max
                        if callback: callback(f">> Sử dụng dữ liệu scraped: {content[:30]}...")
                    else:
                        if callback: callback("Lỗi: Không có dữ liệu scraped trong thư mục")
                        return
                else:
                    if callback: callback("Lỗi: Thư mục scraped không tồn tại")
                    return
            else:
                # Dùng dữ liệu từ config như cũ
                content = ""
                if captions_list:
                    content = random.choice(captions_list)
                
                selected_media = []
                if media_pool:
                    min_f, max_f = media_range
                    count = random.randint(min_f, max_f)
                    count = min(count, len(media_pool))
                    if count > 0:
                        selected_media = random.sample(media_pool, count)

            # --- 2. MỞ POPUP TẠO BÀI VIẾT TRÊN PAGE ---
            # Trên Page, nút "Tạo bài viết" có thể khác
            create_post_selectors = [
                "//span[contains(text(), 'bạn đang nghĩ gì')]",
                "//span[contains(text(), 'on your mind')]",
                "//div[contains(@aria-label, 'tạo bài viết') or contains(@aria-label, 'Create a post')]",
                "//div[contains(@aria-label, 'Viết gì đó') or contains(@aria-label, 'Write something')]",
                "//div[@role='button' and contains(., 'Tạo bài viết')]",
                "//div[@role='button' and contains(., 'Create post')]"
            ]
            
            create_post = None
            for selector in create_post_selectors:
                create_post = self.safe_find_element(By.XPATH, selector)
                if create_post:
                    break
            
            if create_post:
                self.safe_click(create_post)
            else:
                if callback: callback("Lỗi: Không thấy nút tạo bài viết trên Page")
                return

            self.random_sleep(3, 5)

            # Chờ Modal
            try:
                WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.XPATH, "//div[@role='dialog']")))
            except: pass

            # --- 3. NHẬP CAPTION ---
            if content:
                txt_box_xpath = "//div[@role='dialog']//div[@role='textbox']"
                txt_box = self.safe_find_element(By.XPATH, txt_box_xpath)
                
                if txt_box:
                    self.driver.execute_script("arguments[0].click();", txt_box)
                    self.random_sleep(1, 2)
                    try:
                        actions = ActionChains(self.driver)
                        actions.move_to_element(txt_box).click().send_keys(content).perform()
                    except:
                        txt_box.send_keys(content)
                    self.random_sleep(1, 2)

            # --- 4. UPLOAD MEDIA ---
            if selected_media:
                file_input = self.safe_find_element(By.XPATH, "//div[@role='dialog']//input[@type='file']")
                if not file_input: file_input = self.safe_find_element(By.XPATH, "//input[@type='file']")

                if file_input:
                    # Nếu là URL từ scraped, cần download trước
                    local_paths = []
                    for media in selected_media:
                        if media.startswith('http'):
                            # Download và lưu tạm
                            import requests
                            try:
                                response = requests.get(media, timeout=10)
                                if response.status_code == 200:
                                    ext = '.jpg' if 'jpg' in media or 'jpeg' in media else '.png'
                                    temp_file = f"temp_media_{random.randint(1000,9999)}{ext}"
                                    with open(temp_file, 'wb') as f:
                                        f.write(response.content)
                                    local_paths.append(os.path.abspath(temp_file))
                            except:
                                continue
                        else:
                            local_paths.append(media)
                    
                    if local_paths:
                        all_paths = "\n".join(local_paths)
                        file_input.send_keys(all_paths)
                        
                        if callback: callback(">> Đang tải media lên Page...")
                        
                        time.sleep(5 + len(local_paths) * 3)
                        
                        try:
                            WebDriverWait(self.driver, 20).until_not(EC.presence_of_element_located((By.XPATH, "//div[@role='progressbar']")))
                        except: pass
                        
                        # Xóa file tạm
                        for path in local_paths:
                            if path.startswith(os.getcwd()) and 'temp_media' in path:
                                try: os.remove(path)
                                except: pass

            # --- 5. BẤM ĐĂNG ---
            post_btn = self.safe_find_element(By.XPATH, "//div[@role='dialog']//div[@aria-label='Đăng' or @aria-label='Post']")
            if post_btn:
                for _ in range(10): 
                    if post_btn.get_attribute('aria-disabled') == 'true': time.sleep(1)
                    else: break
                
                self.driver.execute_script("arguments[0].click();", post_btn)
                time.sleep(10)
                if callback: callback(">> Đã đăng bài lên Page thành công!")
            else:
                if callback: callback("Lỗi: Không tìm thấy nút Đăng trên Page")
            
        except Exception as e:
            if callback: callback(f"Lỗi Post to Page: {str(e)[:50]}")

    # ==========================
    # PHẦN 2: NUÔI NICK
    # ==========================
    def action_feed_and_like(self, duration_minutes, callback=None):
        if callback: callback(f">> Lướt Feed {duration_minutes} phút...")
        end_time = time.time() + (duration_minutes * 60)
        while time.time() < end_time:
            if not self.is_browser_alive(): break
            # Scroll tự nhiên
            if random.choice(['js', 'key']) == 'js': self.human_scroll(600, 900)
            else: 
                try: ActionChains(self.driver).send_keys(Keys.PAGE_DOWN).perform()
                except: pass
            self.random_sleep(3, 8)
            
            # Like dạo
            if random.random() < 0.3:
                try:
                    btns = self.driver.find_elements(By.XPATH, "//div[@aria-label='Like' or @aria-label='Thích']")
                    if btns:
                        target = random.choice(btns[:3])
                        if self.safe_click(target):
                            if callback: callback(">> Đã Like dạo"); self.random_sleep(2, 4)
                except: pass

    def action_watch_video(self, duration_minutes, callback=None):
        try:
            if callback: callback(f">> Xem Watch ({duration_minutes} phút)...")
            self.driver.get("https://www.facebook.com/watch")
            self.random_sleep(5, 7)
            try: self.driver.find_element(By.TAG_NAME, 'body').click()
            except: pass
            
            end_time = time.time() + (duration_minutes * 60)
            while time.time() < end_time:
                if not self.is_browser_alive(): break
                try:
                    body = self.driver.find_element(By.TAG_NAME, 'body')
                    if random.choice([True, False]): body.send_keys(Keys.PAGE_DOWN)
                    else: body.send_keys(Keys.SPACE)
                except: pass

                watch_segment = random.randint(15, 45) 
                remaining = end_time - time.time()
                if remaining <= 0: break
                for _ in range(int(min(watch_segment, remaining))):
                    if not self.is_browser_alive(): break;
                    time.sleep(1)
        except: pass

    def action_add_friend(self, count, callback=None):
        try:
            if callback: callback(f">> Kết bạn ({count} người)...")
            self.driver.get("https://www.facebook.com/friends/suggestions")
            self.random_sleep(4, 6)
            btns = self.driver.find_elements(By.XPATH, "//div[@aria-label='Thêm bạn bè' or @aria-label='Add Friend']")
            if not btns: btns = self.driver.find_elements(By.XPATH, "//span[text()='Thêm bạn bè' or text()='Add Friend']")
            
            processed = 0
            for btn in btns:
                if processed >= count: break
                if self.safe_click(btn):
                    processed += 1
                    if callback: callback(f">> Đã gửi lời mời ({processed})"); self.random_sleep(3, 6)
        except: pass

    def action_join_group(self, count, callback=None):
        try:
            if callback: callback(f">> Vào ({count} nhóm)...")
            self.driver.get("https://www.facebook.com/groups/discover/")
            self.random_sleep(5, 7)
            btns = self.driver.find_elements(By.XPATH, "//div[@aria-label='Tham gia nhóm' or @aria-label='Join group']")
            processed = 0
            for btn in btns:
                if processed >= count: break
                if self.safe_click(btn):
                    processed += 1
                    if callback: callback(f">> Đã xin vào nhóm ({processed})"); self.random_sleep(3, 5)
        except: pass

    def action_check_notify(self, callback=None):
        try:
            if callback: callback(">> Check Thông báo")
            btn = self.safe_find_element(By.XPATH, "//div[@aria-label='Thông báo' or @aria-label='Notifications']")
            if btn: self.safe_click(btn); self.random_sleep(2, 4); self.driver.find_element(By.TAG_NAME, 'body').click()
        except: pass

    # ==========================
    # PHẦN 3: SEEDING (BUFF)
    # ==========================
    def run_seeding_scenario(self, config, update_callback=None):
        target_url = config.get('url')
        post_type = config.get('type') # 'follow', 'post', 'reels', 'story'
        
        do_follow = config.get('do_follow')
        do_like = config.get('do_like')
        do_comment = config.get('do_comment')
        comments_list = config.get('comments_list', [])

        if update_callback: update_callback(f"Đang chạy task: {post_type.upper()}...")
        self.driver.get(target_url)
        self.random_sleep(6, 9)

        # === 1. LOGIC FOLLOW (Ưu tiên) ===
        if post_type == 'follow':
            if do_follow:
                try:
                    if update_callback: update_callback("Đang tìm nút Follow...")
                    is_followed = False
                    keywords = ["//div[@aria-label='Đang theo dõi']", "//div[@aria-label='Đã thích']", "//span[text()='Đang theo dõi']"]
                    for xp in keywords:
                        if self.safe_find_element(By.XPATH, xp, timeout=2): is_followed = True; break
                    
                    if is_followed:
                        if update_callback: update_callback(">> Đã Follow từ trước.")
                    else:
                        target_btn = self.safe_find_element(By.XPATH, "//div[@aria-label='Theo dõi' or @aria-label='Follow']")
                        if not target_btn: target_btn = self.safe_find_element(By.XPATH, "//span[text()='Theo dõi' or text()='Follow']")
                        if not target_btn: # Fallback Like Page
                            likes = self.driver.find_elements(By.XPATH, "//div[@aria-label='Thích' or @aria-label='Like']")
                            if likes: target_btn = likes[0]

                        if target_btn:
                            self.safe_click(target_btn)
                            if update_callback: update_callback(">> Đã bấm Follow/Thích Page!"); self.random_sleep(3, 5)
                        else:
                            if update_callback: update_callback("Lỗi: Không thấy nút Follow")
                except: pass
            if update_callback: update_callback("Hoàn thành Follow!"); return True

        # === 2. LOGIC LIKE BÀI ===
        if do_like:
            try:
                if post_type == 'story':
                    btn = self.safe_find_element(By.XPATH, "//div[@aria-label='Thích' or @aria-label='Like']")
                    if btn: self.safe_click(btn)
                else:
                    like_btn = self.safe_find_element(By.XPATH, "//div[@aria-label='Thích' or @aria-label='Like']")
                    if like_btn:
                        ActionChains(self.driver).move_to_element(like_btn).perform(); time.sleep(2)
                        reactions = self.driver.find_elements(By.XPATH, "//div[@aria-label='Yêu thích' or @aria-label='Haha' or @aria-label='Thương thương' or @aria-label='Care' or @aria-label='Love']")
                        if reactions and random.random() > 0.2:
                            random.choice(reactions).click()
                            if update_callback: update_callback(">> Đã thả Tim/Haha")
                        else:
                            self.safe_click(like_btn)
                            if update_callback: update_callback(">> Đã Like thường")
            except: pass
        self.random_sleep(2, 4)
        
        # === 3. LOGIC COMMENT (Cải tiến) ===
        if do_comment and comments_list:
            try:
                content = random.choice(comments_list)
                if post_type == 'story':
                    inp = self.safe_find_element(By.XPATH, "//textarea[contains(@placeholder, 'Trả lời') or contains(@placeholder, 'Reply')]")
                    if inp:
                        inp.send_keys(content); time.sleep(1); inp.send_keys(Keys.ENTER)
                        if update_callback: update_callback(f">> Đã Cmt Story: {content}")
                else:
                    if update_callback: update_callback("Chuẩn bị Comment...")
                    comment_box = self.safe_find_element(By.XPATH, "//div[@role='textbox' and contains(@aria-label, 'Bình luận')]", timeout=2)
                    if not comment_box: comment_box = self.safe_find_element(By.XPATH, "//div[@role='textbox' and contains(@aria-label, 'comment')]", timeout=1)

                    if not comment_box: # Mở nút
                        if update_callback: update_callback("Đang tìm nút mở comment...")
                        open_btn = self.safe_find_element(By.XPATH, "//div[@role='button' and (@aria-label='Bình luận' or @aria-label='Comment')]")
                        if open_btn:
                            self.safe_click(open_btn); time.sleep(2) 
                            comment_box = self.safe_find_element(By.XPATH, "//div[@role='textbox' and contains(@aria-label, 'Bình luận')]")
                            if not comment_box: comment_box = self.safe_find_element(By.XPATH, "//div[@role='textbox' and @contenteditable='true']")

                    if comment_box:
                        self.safe_click(comment_box); time.sleep(1)
                        actions = ActionChains(self.driver)
                        actions.move_to_element(comment_box).click().send_keys(content).perform()
                        self.random_sleep(1, 2)
                        actions.send_keys(Keys.ENTER).perform()
                        if update_callback: update_callback(f">> Đã Cmt: {content}"); time.sleep(5)
                    else:
                        if update_callback: update_callback("Lỗi: Không thể mở ô bình luận!")
            except Exception as e:
                if update_callback: update_callback(f"Lỗi Cmt: {str(e)[:40]}")

        if update_callback: update_callback("Seeding Hoàn tất!")
        return True

    # ==========================
    # LOGIC CHÍNH (MASTER RUNNER)
    # ==========================
    def run_custom_scenario(self, config, update_callback=None):
        if update_callback: update_callback("Mở Facebook...")
        self.driver.get("https://www.facebook.com")
        self.random_sleep(3, 5)

        if "login" in self.driver.current_url:
            if update_callback: update_callback("Lỗi: Chưa login!"); return False

        # --- A. ĐĂNG BÀI (LOGIC MỚI - RANDOM NHIỀU ẢNH) ---
        post_cfg = config.get('post', {})
        if post_cfg.get('enable'):
            p_type = post_cfg.get('type') # 'status', 'reels', 'story'
            captions = post_cfg.get('captions', [])
            media_pool = post_cfg.get('media_files', [])
            media_range = post_cfg.get('media_range', (1, 1))

            if p_type == 'status':
                # Chuyển list caption và list ảnh vào để hàm tự random
                self.post_status(captions, media_pool, media_range, update_callback)
                self.random_sleep(5, 8)
            
            elif p_type == 'story':
                self.post_story(media_pool, update_callback)
                self.random_sleep(5, 8)
                
            elif p_type == 'reels':
                # Reels chọn 1 caption ngẫu nhiên
                cap = random.choice(captions) if captions else ""
                self.post_reels(cap, media_pool, update_callback)
                self.random_sleep(5, 8)

        # --- C. ĐĂNG LÊN PAGE ---
        page_cfg = config.get('page', {})
        if page_cfg.get('enable'):
            page_id = page_cfg.get('page_id')
            page_name = page_cfg.get('page_name')
            use_scraped = page_cfg.get('use_scraped_data', False)
            
            if use_scraped:
                # Dùng dữ liệu scraped
                self.post_to_page(page_id, page_name, use_scraped_data=True, callback=update_callback)
            else:
                # Dùng config như cũ
                captions = page_cfg.get('captions', [])
                media_pool = page_cfg.get('media_files', [])
                media_range = page_cfg.get('media_range', (1, 1))
                self.post_to_page(page_id, page_name, captions, media_pool, media_range, callback=update_callback)
            
            self.random_sleep(5, 8)

        # --- B. NUÔI NICK (Giữ nguyên) ---
        farm_cfg = config.get('farm', {})
        if farm_cfg.get('enable'):
            if farm_cfg.get('notify'): self.action_check_notify(update_callback)
            if farm_cfg.get('feed'):
                r_min, r_max = farm_cfg.get('feed_range', (3, 5))
                self.action_feed_and_like(random.randint(r_min, r_max), update_callback)
            if farm_cfg.get('watch'):
                t_min, t_max = farm_cfg.get('watch_range', (5, 10))
                self.action_watch_video(random.randint(t_min, t_max), update_callback)
            if farm_cfg.get('friend'):
                f_min, f_max = farm_cfg.get('friend_range', (1, 2))
                self.action_add_friend(random.randint(f_min, f_max), update_callback)
            if farm_cfg.get('group'):
                g_min, g_max = farm_cfg.get('group_range', (0, 1))
                self.action_join_group(random.randint(g_min, g_max), update_callback)

        if update_callback: update_callback("Nhiệm vụ hoàn tất!")
        return True

    # === ACCOUNT SUPPORT METHODS ===


    def apply_email_login(self, email, password):
        """Auto-login to email account for 2FA support (optional)"""
        try:
            # Skip if no email provided
            if not email or not password:
                return False
            
            # Prioritize Outlook/Hotmail - most common for 2FA
            outlook_success = self._login_outlook(email, password)
            
            if outlook_success:
                return True
            
            # Fallback to Gmail only if Outlook fails
            gmail_success = self._login_gmail(email, password)
            
            if gmail_success:
                return True
            
            return False

        except Exception as e:
            return False
        finally:
            # Switch back to main tab
            try:
                if len(self.driver.window_handles) > 1:
                    self.driver.switch_to.window(self.driver.window_handles[0])
            except:
                pass

    def _login_outlook(self, email, password):
        """Login to Outlook/Hotmail email"""
        try:
            # Open new tab for email login
            self.driver.execute_script("window.open('https://outlook.live.com', '_blank');")
            time.sleep(2)

            # Switch to email tab
            self.driver.switch_to.window(self.driver.window_handles[-1])
            time.sleep(3)
            
            # Wait for page to fully load
            try:
                WebDriverWait(self.driver, 15).until(
                    lambda driver: driver.execute_script("return document.readyState") == "complete"
                )
                time.sleep(2)
            except:
                pass

            email_field = None
            
            # Try multiple selector approaches
            selectors = [
                (By.ID, "i0116"),  # Outlook email input ID
                (By.NAME, "loginfmt"),  # Outlook email input name
                (By.XPATH, "//input[contains(@aria-label, 'Email')]"),
                (By.XPATH, "//input[@type='email' or @type='text'][not(@hidden)]"),
                (By.XPATH, "//input"),  # Any input as last resort
            ]
            
            for by, selector in selectors:
                try:
                    email_field = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((by, selector))
                    )
                    if email_field and email_field.is_displayed():
                        break
                except:
                    email_field = None
                    continue
            
            if not email_field:
                return False
            
            # Clear using JavaScript instead of .clear() to avoid element state error
            try:
                self.driver.execute_script("arguments[0].value = '';", email_field)
                time.sleep(0.5)
                email_field.send_keys(email)
                time.sleep(1)
            except Exception as e:
                return False
            
            # Click Next button
            next_selectors = [
                (By.ID, "idSIButton9"),  # Outlook Next button ID
                (By.XPATH, "//input[@type='submit']"),
                (By.XPATH, "//button[contains(text(), 'Next')]"),
            ]
            
            next_btn = None
            for by, selector in next_selectors:
                try:
                    next_btn = WebDriverWait(self.driver, 3).until(
                        EC.element_to_be_clickable((by, selector))
                    )
                    break
                except:
                    continue
            
            if not next_btn:
                return False
            
            try:
                next_btn.click()
            except:
                self.driver.execute_script("arguments[0].click();", next_btn)
            time.sleep(4)

            # Wait for password field to appear
            pass_field = None
            pass_selectors = [
                (By.ID, "i0118"),  # Outlook password input ID
                (By.NAME, "passwd"),
                (By.XPATH, "//input[@type='password']"),
            ]
            
            for by, selector in pass_selectors:
                try:
                    pass_field = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((by, selector))
                    )
                    if pass_field and pass_field.is_displayed():
                        break
                except:
                    pass_field = None
                    continue
            
            if not pass_field:
                return False

            # Enter password using JavaScript
            try:
                self.driver.execute_script("arguments[0].value = '';", pass_field)
                time.sleep(0.5)
                pass_field.send_keys(password)
                time.sleep(1)
            except Exception as e:
                return False

            # Click Sign in button
            signin_selectors = [
                (By.ID, "idSIButton9"),
                (By.XPATH, "//input[@type='submit']"),
                (By.XPATH, "//button[contains(text(), 'Sign in')]"),
            ]
            
            signin_btn = None
            for by, selector in signin_selectors:
                try:
                    signin_btn = WebDriverWait(self.driver, 3).until(
                        EC.element_to_be_clickable((by, selector))
                    )
                    break
                except:
                    continue
            
            if not signin_btn:
                return False
            
            try:
                signin_btn.click()
            except:
                self.driver.execute_script("arguments[0].click();", signin_btn)
            time.sleep(6)
            
            # Check if login successful by checking URL
            if "login" not in self.driver.current_url.lower():
                return True
            return False

        except Exception as e:
            return False
        finally:
            try:
                if len(self.driver.window_handles) > 1:
                    self.driver.switch_to.window(self.driver.window_handles[0])
            except:
                pass

    def _login_gmail(self, email, password):
        """Fallback: Login to Gmail email"""
        try:
            # Close previous tab if any
            try:
                if len(self.driver.window_handles) > 1:
                    self.driver.close()
                    self.driver.switch_to.window(self.driver.window_handles[0])
            except:
                pass
            
            self.driver.execute_script("window.open('https://accounts.google.com/signin', '_blank');")
            time.sleep(2)
            
            # Switch to new tab
            self.driver.switch_to.window(self.driver.window_handles[-1])
            time.sleep(3)
            
            # Wait for page to fully load
            try:
                WebDriverWait(self.driver, 15).until(
                    lambda driver: driver.execute_script("return document.readyState") == "complete"
                )
                time.sleep(2)
            except:
                pass

            gmail_field = None
            
            # Try multiple selector approaches for Gmail
            selectors = [
                (By.ID, "identifierId"),  # Gmail email input ID
                (By.NAME, "identifier"),
                (By.XPATH, "//input[@type='email'][@aria-label]"),
                (By.XPATH, "//input[@type='email' or @type='text'][not(@hidden)]"),
                (By.XPATH, "//input"),  # Any input as last resort
            ]
            
            for by, selector in selectors:
                try:
                    gmail_field = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((by, selector))
                    )
                    if gmail_field and gmail_field.is_displayed():
                        break
                except:
                    gmail_field = None
                    continue
            
            if not gmail_field:
                return False
            
            # Clear using JavaScript and fill email
            try:
                self.driver.execute_script("arguments[0].value = '';", gmail_field)
                time.sleep(0.5)
                gmail_field.send_keys(email)
                time.sleep(1)
            except Exception as e:
                return False

            # Click Next for email
            next_selectors = [
                (By.ID, "identifierNext"),  # Gmail Next button ID
                (By.XPATH, "//div[@role='button'][contains(., 'Next')]"),
                (By.XPATH, "//button[contains(., 'Next')]"),
            ]
            
            next_btn = None
            for by, selector in next_selectors:
                try:
                    next_btn = WebDriverWait(self.driver, 3).until(
                        EC.element_to_be_clickable((by, selector))
                    )
                    break
                except:
                    continue
            
            if not next_btn:
                return False
            
            try:
                next_btn.click()
            except:
                self.driver.execute_script("arguments[0].click();", next_btn)
            time.sleep(4)

            # Wait for password field
            pass_field = None
            pass_selectors = [
                (By.NAME, "password"),  # Gmail password input name
                (By.XPATH, "//input[@type='password'][@aria-label]"),
                (By.XPATH, "//input[@type='password']"),
            ]
            
            for by, selector in pass_selectors:
                try:
                    pass_field = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((by, selector))
                    )
                    if pass_field and pass_field.is_displayed():
                        break
                except:
                    pass_field = None
                    continue
            
            if not pass_field:
                return False

            # Enter password using JavaScript
            try:
                self.driver.execute_script("arguments[0].value = '';", pass_field)
                time.sleep(0.5)
                pass_field.send_keys(password)
                time.sleep(1)
            except Exception as e:
                return False

            # Click Next to submit password
            submit_selectors = [
                (By.ID, "passwordNext"),  # Gmail password submit button ID
                (By.XPATH, "//div[@role='button'][contains(., 'Next')]"),
                (By.XPATH, "//button[contains(., 'Next')]"),
            ]
            
            submit_btn = None
            for by, selector in submit_selectors:
                try:
                    submit_btn = WebDriverWait(self.driver, 3).until(
                        EC.element_to_be_clickable((by, selector))
                    )
                    break
                except:
                    continue
            
            if not submit_btn:
                return False
            
            try:
                submit_btn.click()
            except:
                self.driver.execute_script("arguments[0].click();", submit_btn)
            time.sleep(6)
            
            # Check if login successful
            if "signin" not in self.driver.current_url.lower():
                return True
            return False

        except Exception as e:
            return False
        finally:
            try:
                if len(self.driver.window_handles) > 1:
                    self.driver.switch_to.window(self.driver.window_handles[0])
            except:
                pass

    def extract_2fa_code_from_2fa_live(self, twofa_seed):
        """
        Generate the current TOTP code locally from the assigned 2FA seed.

        The previous implementation called several 2fa.live endpoints and then
        fell back to returning the seed itself. That could take 10-30 seconds and
        produced the exact error shown by Facebook when the remote request failed.
        
        Args:
            twofa_seed: The 2FA seed/code from account data
            
        Returns:
            6-digit 2FA code or None if extraction fails
        """
        if not twofa_seed or len(str(twofa_seed).strip()) == 0:
            print("2FA seed is empty")
            return None
        
        try:
            raw_seed = str(twofa_seed).strip()
            if raw_seed.lower().startswith("otpauth://"):
                raw_seed = parse_qs(urlparse(raw_seed).query).get("secret", [""])[0]

            secret = re.sub(r"[\s-]", "", raw_seed).upper()
            if not re.fullmatch(r"[A-Z2-7]+=*", secret):
                print("2FA seed is not a valid Base32 secret")
                return None

            secret += "=" * ((8 - len(secret) % 8) % 8)
            key = base64.b32decode(secret, casefold=True)
            counter = int(time.time() // 30)
            digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
            offset = digest[-1] & 0x0F
            value = (
                ((digest[offset] & 0x7F) << 24)
                | (digest[offset + 1] << 16)
                | (digest[offset + 2] << 8)
                | digest[offset + 3]
            ) % 1_000_000
            code = f"{value:06d}"
            print("2FA code generated locally")
            return code
        except Exception as e:
            print(f"Error generating 2FA code: {e}")
            return None

    def apply_2fa_code(self, twofa_code):
        """Auto-fill 2FA code when prompted"""
        self.twofa_continue_clicked_at = None
        self.twofa_continue_submitted = False
        self.twofa_result = "pending"
        try:
            code_xpath = (
                "//input[not(@type='hidden') and ("
                "@autocomplete='one-time-code' or @inputmode='numeric' or "
                "contains(translate(@placeholder, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'code') or "
                "contains(translate(@aria-label, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'code') or "
                "contains(translate(@name, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'code'))]"
            )

            def visible_code_field(driver):
                for field in driver.find_elements(By.XPATH, code_xpath):
                    try:
                        if field.is_displayed() and field.is_enabled():
                            return field
                    except Exception:
                        continue
                # Facebook sometimes renders only a generic text input on this page.
                for field in driver.find_elements(By.XPATH, "//input[@type='text']"):
                    try:
                        if field.is_displayed() and field.is_enabled():
                            return field
                    except Exception:
                        continue
                return False

            code_field = WebDriverWait(self.driver, 8, poll_frequency=0.2).until(visible_code_field)

            if code_field:
                # Try to extract fresh code from 2fa.live if seed is provided
                extracted_code = self.extract_2fa_code_from_2fa_live(twofa_code)
                # A raw seed must never be sent to Facebook. It is only valid to
                # use the original value when it is already a six-digit code.
                code_to_use = extracted_code or (
                    str(twofa_code).strip() if re.fullmatch(r"\d{6}", str(twofa_code).strip()) else None
                )
                if not code_to_use:
                    print("2FA seed could not be converted to a 6-digit code")
                    return False
                
                try:
                    code_field.click()
                except Exception:
                    pass
                code_field.clear()
                code_field.send_keys(code_to_use)

                def code_value_matches(driver):
                    try:
                        value = code_field.get_attribute("value") or ""
                        if hasattr(code_field, "get_dom_property"):
                            value = code_field.get_dom_property("value") or value
                        if not value:
                            value = driver.execute_script("return arguments[0].value || '';", code_field) or ""
                        return str(value).strip() == code_to_use
                    except Exception:
                        return False

                try:
                    code_received = WebDriverWait(
                        self.driver, 3, poll_frequency=0.1
                    ).until(code_value_matches)
                    if not code_received:
                        raise TimeoutException("2FA field did not receive the code")
                except Exception:
                    self.twofa_result = "fill_failed"
                    print("2FA input did not receive the complete six-digit code")
                    return False
                # Let Facebook process the input event before locating Continue.
                time.sleep(0.25)

                initial_url = self.driver.current_url
                if not self._submit_twofa_continue(timeout=12):
                    self.twofa_result = "submit_failed"
                    print("Could not click Continue after entering 2FA")
                    return False

                # Do not close the profile immediately after dispatching the click.
                # Wait for Facebook to navigate or render a validation result.
                submit_deadline = time.monotonic() + 15
                while time.monotonic() < submit_deadline:
                    if getattr(self, "login_cancelled", lambda: False)():
                        return False
                    current_url = self.driver.current_url
                    if current_url != initial_url and not current_url.startswith(("about:", "chrome:")):
                        self.twofa_result = "next_page"
                        return True

                    try:
                        error_nodes = self.driver.find_elements(
                            By.XPATH,
                            "//*[not(*) and (contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'this code isn') or contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'incorrect') or contains(., 'mã không đúng'))]",
                        )
                        if any(node.is_displayed() for node in error_nodes):
                            self.twofa_result = "rejected"
                            return False
                        # Facebook can replace the content without changing URL.
                        if not visible_code_field(self.driver) and self.driver.execute_script(
                            "return document.readyState !== 'loading' && !!document.body && document.body.innerText.trim().length > 40;"
                        ):
                            self.twofa_result = "next_page"
                            return True
                    except Exception:
                        pass

                    time.sleep(0.2)

                print("Continue was clicked but Facebook did not respond within the timeout")
                self.twofa_result = "response_timeout"
                return False

            return False

        except Exception as e:
            print(f"2FA auto-fill failed: {e}")
            return False

    def _submit_twofa_continue(self, timeout=12):
        """Wait for the actual enabled Continue action and submit it once."""
        lower = "translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')"
        xpath = (
            "//*[self::button or @role='button' or self::input]["
            f"{lower}='continue' or {lower}='submit' or normalize-space(.)='Tiếp tục' or "
            "normalize-space(.)='Gửi' or @value='Continue' or @value='Tiếp tục']"
        )
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if getattr(self, "login_cancelled", lambda: False)():
                return False
            for button in self.driver.find_elements(By.XPATH, xpath):
                try:
                    if not button.is_displayed() or not button.is_enabled():
                        continue
                    # Selenium is_enabled() alone does not cover Facebook's div buttons.
                    if button.get_attribute("aria-disabled") == "true" or button.get_attribute("disabled") is not None:
                        continue
                    if self.safe_click(button):
                        self.twofa_continue_clicked_at = time.monotonic()
                        self.twofa_continue_submitted = True
                        return True
                except Exception:
                    continue
            time.sleep(0.2)
        return False

    def _click_text_fast(self, texts, timeout=1.5):
        """Click a visible Facebook action without fixed multi-second sleeps."""
        if not texts:
            return False

        predicates = " or ".join(
            "contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), %s)"
            % json.dumps(str(text).lower())
            for text in texts
            if text
        )
        if not predicates:
            return False

        xpath = (
            "//*[self::button or self::a or @role='button' or @role='radio' or self::label or self::div or self::span]["
            + predicates
            + "]"
        )
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                elements = self.driver.find_elements(By.XPATH, xpath)
                elements = sorted(
                    elements,
                    key=lambda element: len((element.text or "").strip())
                    if hasattr(element, "text") else 10**9,
                )
                for element in elements:
                    try:
                        if not element.is_displayed() or not element.is_enabled():
                            continue
                        if self.safe_click(element):
                            return True
                    except Exception:
                        continue
            except Exception:
                pass
            time.sleep(0.15)
        return False

    def wait_for_2fa_and_fill(self, twofa_code, timeout=60):
        """Wait for Facebook's 2FA UI, choose Authentication app, then fill the code."""
        try:
            if not twofa_code:
                return False

            code_xpath = (
                "//input[not(@type='hidden') and ("
                "@autocomplete='one-time-code' or @inputmode='numeric' or "
                "contains(translate(@placeholder, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'code') or "
                "contains(translate(@aria-label, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'code') or "
                "contains(translate(@name, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'code'))]"
            )

            def has_visible_code_field():
                try:
                    for field in self.driver.find_elements(By.XPATH, code_xpath):
                        if field.is_displayed() and field.is_enabled():
                            return True
                    # The current Facebook screen can expose a plain text input
                    # with only the visual label "Code".
                    for field in self.driver.find_elements(By.XPATH, "//input[@type='text']"):
                        if field.is_displayed() and field.is_enabled():
                            return True
                except Exception:
                    pass
                return False

            start_time = time.time()
            tried_another_way = False
            selected_auth_app = False
            continued_to_code = False

            while time.time() - start_time < timeout:
                if getattr(self, "login_cancelled", lambda: False)():
                    return False
                if has_visible_code_field():
                    print("2FA code field detected, auto-filling...")
                    result = self.apply_2fa_code(twofa_code)
                    if result or getattr(self, "twofa_result", "") != "fill_failed":
                        return result
                    # A React controlled field can briefly reject the first
                    # send_keys while it is mounting. Retry only that case.
                    time.sleep(0.5)
                    return self.apply_2fa_code(twofa_code)

                # Stop quickly on a real bad-password result instead of waiting
                # through the complete 2FA timeout.
                if time.time() - start_time > 2 and "login" in self.driver.current_url.lower():
                    try:
                        error_nodes = self.driver.find_elements(
                            By.XPATH,
                            "//*[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'incorrect') or contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'wrong password') or contains(., 'mật khẩu không đúng')]",
                        )
                        if any(node.is_displayed() for node in error_nodes):
                            return False
                    except Exception:
                        pass

                # Notification approval screen: open the alternate methods dialog once.
                if not tried_another_way and self._click_text_fast(
                    ["Try another way", "Use another way", "Thử cách khác"],
                    timeout=0.35,
                ):
                    tried_another_way = True
                    continue

                # Alternate methods dialog: choose the authenticator app row.
                if tried_another_way and not selected_auth_app and self._click_text_fast(
                    ["Authentication app", "Authenticator app", "Ứng dụng xác thực"],
                    timeout=0.35,
                ):
                    selected_auth_app = True
                    continue

                # After selecting Authentication app, continue to the code screen.
                if selected_auth_app and not continued_to_code and self._click_text_fast(
                    ["Continue", "Tiếp tục"],
                    timeout=0.35,
                ):
                    continued_to_code = True
                    continue

                time.sleep(0.2)

            self.twofa_result = "code_field_timeout"
            print("2FA code field not found within timeout")
            return False

        except Exception as e:
            self.twofa_result = "handler_error"
            print(f"2FA wait and fill failed: {e}")
            return False

    def login_with_cookie(self, cookie_string):
        """Login to Facebook by injecting cookies into the browser.
        
        Cookie string format: "c_user=123456;xs=abc123;datr=xyz;fr=..."
        Returns True if cookie login succeeded (session is alive).
        """
        if not cookie_string or not cookie_string.strip():
            return False

        try:
            # Navigate to Facebook domain first so we can set cookies
            self.driver.get('https://www.facebook.com/')
            time.sleep(2)

            # Clear existing cookies for a clean slate
            self.driver.delete_all_cookies()

            # Parse the cookie string into individual cookies
            cookie_pairs = [c.strip() for c in cookie_string.split(';') if c.strip()]
            essential_found = {'c_user': False, 'xs': False}

            for pair in cookie_pairs:
                if '=' not in pair:
                    continue
                name, _, value = pair.partition('=')
                name = name.strip()
                value = value.strip()
                if not name or not value:
                    continue

                if name in essential_found:
                    essential_found[name] = True

                # Method 1: Inject via CDP (handles HttpOnly, Secure, SameSite reliably)
                try:
                    self.driver.execute_cdp_cmd('Network.setCookie', {
                        'name': name,
                        'value': value,
                        'domain': '.facebook.com',
                        'path': '/',
                        'secure': True
                    })
                except Exception:
                    pass

                # Method 2: Fallback via Selenium add_cookie
                cookie_dict = {
                    'name': name,
                    'value': value,
                    'domain': '.facebook.com',
                    'path': '/',
                }
                try:
                    self.driver.add_cookie(cookie_dict)
                except Exception:
                    try:
                        del cookie_dict['domain']
                        self.driver.add_cookie(cookie_dict)
                    except Exception:
                        pass

            # Must have at least c_user and xs to form a valid session
            if not essential_found['c_user'] or not essential_found['xs']:
                print("Cookie login: missing essential cookies (c_user or xs)")
                return False

            # Reload Facebook to apply the cookies
            self.driver.get('https://www.facebook.com/')

            # Wait for page to fully load (DOM + React render)
            try:
                WebDriverWait(self.driver, 10).until(
                    lambda d: d.execute_script("return document.readyState") == "complete"
                )
            except:
                pass
            time.sleep(3)

            # --- VERIFY: Check if actually logged in ---
            current_url = self.driver.current_url.lower()

            # 1. URL-based rejection
            if any(marker in current_url for marker in (
                '/login', 'checkpoint', 'two_step_verification', 'two_factor'
            )):
                print("Cookie login: redirected to login/checkpoint page")
                return False

            # 2. Login form detection (wait for DOM to settle)
            login_form_markers = [
                (By.ID, "email"),
                (By.ID, "pass"),
                (By.NAME, "email"),
                (By.NAME, "pass"),
                (By.XPATH, "//input[@name='email' or @name='pass']"),
                (By.XPATH, "//form[contains(@action, 'login')]"),
            ]
            for by, selector in login_form_markers:
                try:
                    field = self.driver.find_element(by, selector)
                    if field.is_displayed():
                        print(f"Cookie login: login form detected ({selector})")
                        return False
                except:
                    continue

            # 3. Positive check: must find at least one logged-in indicator
            logged_in_indicators = [
                (By.XPATH, "//a[@aria-label='Your profile']"),
                (By.XPATH, "//a[contains(@href, '/me/')]"),
                (By.XPATH, "//div[@role='feed']"),
                (By.XPATH, "//a[@aria-label='Notifications' or @aria-label='Thông báo']"),
                (By.XPATH, "//a[@aria-label='Messenger']"),
                (By.XPATH, "//nav[@aria-label='Navigation']"),
                (By.XPATH, "//div[@aria-label='Facebook' and @role='navigation']"),
            ]
            for by, selector in logged_in_indicators:
                try:
                    el = WebDriverWait(self.driver, 3).until(
                        EC.presence_of_element_located((by, selector))
                    )
                    if el:
                        print(f"Cookie login: session confirmed ({selector})")
                        return True
                except:
                    continue

            print("Cookie login: no session indicators found - cookie likely expired")
            return False

        except Exception as e:
            print(f"Cookie login error: {e}")
            return False

    def login_account_with_credentials(self, account):
        """Use only UID/password for new logins, followed by the existing 2FA step."""
        uid = account.get('id', '')
        password = account.get('password', '')
        if not uid or not password:
            return False

        success = self.login_with_credentials(uid, password)
        twofa_code = account.get('2fa_code', '')
        current_url = self.driver.current_url.lower()
        is_2fa_challenge = any(
            marker in current_url for marker in ('two_step_verification', 'two_factor', 'checkpoint')
        )
        self.twofa_challenge_detected = is_2fa_challenge
        if twofa_code and is_2fa_challenge:
            # login_with_credentials waits for this URL/state, so only enter the
            # 2FA handler when Facebook actually opened the challenge.
            twofa_success = self.wait_for_2fa_and_fill(twofa_code, timeout=45)
            if twofa_success:
                return True
            return False

        # A checkpoint/2FA URL is never a successful login result. Returning
        # success here used to make the batch worker close Chrome immediately
        # after the first Log in click, before Continue was processed.
        if is_2fa_challenge:
            self.twofa_result = "missing_code" if not twofa_code else "pending"
            return False

        # Do not navigate back to login.php or trigger Chrome Password Manager here.
        # The login session/profile is the result; credentials are intentionally not
        # saved by this UID/password-only flow.
        return success

    def login_with_credentials(self, uid, password):
        """Login to Facebook with the assigned UID and password."""
        try:
            if not uid or not password:
                return False

            if not self._login_form_present():
                self.driver.get('https://www.facebook.com/login.php')

            def visible_field(driver, selectors):
                for by, selector in selectors:
                    try:
                        for field in driver.find_elements(by, selector):
                            if field.is_displayed() and field.is_enabled():
                                return field
                    except Exception:
                        continue
                return False

            user_selectors = [
                (By.ID, "email"),
                (By.NAME, "email"),
                (By.CSS_SELECTOR, "input[type='email'], input[autocomplete='username']"),
            ]
            pass_selectors = [
                (By.ID, "pass"),
                (By.NAME, "pass"),
                (By.CSS_SELECTOR, "input[type='password'], input[autocomplete='current-password']"),
            ]

            # Poll quickly instead of waiting 15s for a NAME-only match. The current
            # Facebook form commonly exposes the fields by ID/autocomplete first.
            user_field = WebDriverWait(self.driver, 8, poll_frequency=0.2).until(
                lambda driver: visible_field(driver, user_selectors)
            )
            pass_field = WebDriverWait(self.driver, 8, poll_frequency=0.2).until(
                lambda driver: visible_field(driver, pass_selectors)
            )

            if not user_field or not pass_field:
                return False

            try:
                user_field.clear()
            except:
                pass
            user_field.send_keys(uid)

            try:
                pass_field.clear()
            except:
                pass
            pass_field.send_keys(password)

            login_btn = next(
                (
                    element for element in self.driver.find_elements(
                        By.CSS_SELECTOR,
                        "button[name='login'], button[type='submit'], input[type='submit'], [role='button'][data-testid*='login']"
                    )
                    if element.is_displayed() and element.is_enabled()
                ),
                None,
            )
            if not login_btn:
                login_btn = next(
                    (
                        element for element in self.driver.find_elements(
                            By.XPATH,
                            "//button[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'log in') or contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'login') or contains(normalize-space(.), 'Đăng nhập')]"
                        )
                        if element.is_displayed() and element.is_enabled()
                    ),
                    None,
                )

            clicked = False
            if login_btn:
                clicked = self.safe_click(login_btn)
                if not clicked:
                    try:
                        self.driver.execute_script("arguments[0].click();", login_btn)
                        clicked = True
                    except:
                        clicked = False
                if not clicked:
                    try:
                        login_btn.submit()
                        clicked = True
                    except:
                        clicked = False

            if not clicked:
                pass_field.send_keys(Keys.ENTER)
                clicked = True

            if clicked:
                self.login_button_clicked = True
                clock = getattr(time, "monotonic", time.time)
                self.login_button_clicked_at = clock()

            # Wait only for a real navigation/state change, not a fixed 5–15 seconds.
            deadline = time.time() + 12
            while time.time() < deadline:
                current_url = self.driver.current_url.lower()
                if any(marker in current_url for marker in (
                    "two_step_verification", "two_factor", "checkpoint", "home.php"
                )):
                    return True
                if not self._login_form_present() and "login" not in current_url:
                    return True
                time.sleep(0.2)

            current_url = self.driver.current_url.lower()
            return not self._login_form_present() and "login" not in current_url
        except Exception as e:
            print(f"login_with_credentials error: {e}")
            return False

    def _login_form_present(self):
        try:
            return bool(self.driver.execute_script("""
                return !!document.querySelector('#email, #pass, form[action*="login"]');
            """))
        except Exception:
            return False

    def _click_visible_text_action(self, texts, timeout=4):
        if not texts:
            return False

        xpath = "//*[self::a or self::button or self::div or self::span][%s]" % " or ".join(
            f"contains(normalize-space(.), {json.dumps(text)})" for text in texts
        )
        deadline = time.time() + timeout

        while time.time() < deadline:
            try:
                elements = self.driver.find_elements(By.XPATH, xpath)
                for element in elements:
                    try:
                        if not element.is_displayed():
                            continue
                        if self.safe_click(element):
                            time.sleep(3)
                            return True
                    except Exception:
                        continue
            except Exception:
                pass
            time.sleep(0.5)
        return False

    def switch_to_personal_context(self):
        """Best-effort: bring the browser back to the personal profile context."""
        try:
            self.driver.get("https://www.facebook.com/me")
            time.sleep(4)

            if "login" in self.driver.current_url.lower() or self._login_form_present():
                return False

            if any(token in self.driver.current_url.lower() for token in ("/me", "profile.php", "facebook.com/")):
                return True

            self._click_visible_text_action([
                "Switch into this profile",
                "Switch to profile",
                "Use Facebook as your profile",
                "Chuyển sang trang cá nhân",
                "Dùng Facebook với tư cách trang cá nhân",
                "Xem trang cá nhân",
                "See your profile",
            ], timeout=5)

            self.driver.get("https://www.facebook.com/me")
            time.sleep(3)
            return not self._login_form_present()
        except Exception:
            return False

    def switch_to_page_context(self, page_name="", page_id=""):
        """Best-effort: switch from personal profile context into the selected Page context."""
        try:
            if "login" in self.driver.current_url.lower() or self._login_form_present():
                return False

            clicked = self._click_visible_text_action([
                "Switch now",
                "Switch",
                "Use Facebook as",
                "View as Page",
                "Manage Page",
                "Chuyển ngay",
                "Chuyển sang",
                "Dùng Facebook với tư cách",
                "Quản lý Trang",
            ], timeout=6)

            if not clicked:
                self._click_visible_text_action([
                    page_name,
                    page_id,
                ], timeout=3)
                clicked = self._click_visible_text_action([
                    "Switch now",
                    "Switch",
                    "Chuyển ngay",
                    "Chuyển sang",
                ], timeout=4)

            time.sleep(3)

            try:
                current_url = self.driver.current_url.lower()
                if page_id and page_id in current_url:
                    return True
                if page_name and page_name.lower() in self.driver.title.lower():
                    return True
            except Exception:
                pass

            return clicked
        except Exception:
            return False

    def change_password(self, current_password, new_password):
        """Best-effort password change flow for a logged-in Facebook account."""
        try:
            if not current_password or not new_password:
                return False

            candidate_urls = [
                "https://www.facebook.com/settings?tab=security",
                "https://www.facebook.com/settings/?tab=account&section=password",
                "https://accountscenter.facebook.com/password_and_security/password_change/",
            ]

            for url in candidate_urls:
                try:
                    self.driver.get(url)
                    time.sleep(4)

                    fields = [field for field in self.driver.find_elements(By.XPATH, "//input[@type='password']") if field.is_displayed()]
                    if len(fields) < 3:
                        action_buttons = self.driver.find_elements(
                            By.XPATH,
                            "//*[self::span or self::div or self::a or self::button][contains(., 'Change password') or contains(., 'Đổi mật khẩu') or contains(., 'Password and security') or contains(., 'Mật khẩu và bảo mật')]"
                        )
                        for btn in action_buttons:
                            if btn.is_displayed():
                                self.safe_click(btn)
                                time.sleep(3)
                                fields = [field for field in self.driver.find_elements(By.XPATH, "//input[@type='password']") if field.is_displayed()]
                                if len(fields) >= 3:
                                    break

                    if len(fields) >= 3:
                        current_field, new_field, confirm_field = fields[:3]
                        for field, value in (
                            (current_field, current_password),
                            (new_field, new_password),
                            (confirm_field, new_password),
                        ):
                            try:
                                field.clear()
                            except:
                                pass
                            field.send_keys(value)
                            time.sleep(0.5)

                        submit_btn = self.safe_find_element(
                            By.XPATH,
                            "//button[@type='submit' or contains(., 'Save changes') or contains(., 'Đổi mật khẩu') or contains(., 'Change password') or contains(., 'Lưu thay đổi')]",
                            timeout=5
                        )
                        if submit_btn:
                            self.safe_click(submit_btn)
                        else:
                            confirm_field.send_keys(Keys.ENTER)

                        time.sleep(5)
                        visible_fields = [field for field in self.driver.find_elements(By.XPATH, "//input[@type='password']") if field.is_displayed()]
                        if len(visible_fields) < 3:
                            return True
                except:
                    continue

            return False
        except Exception:
            return False

    def save_credentials_to_browser(self, username, password):
        """Save username/password to Chrome browser for future auto-login"""
        try:
            print(f"💾 Saving credentials to Chrome for user: {username}")
            
            # Method 1: Inject into localStorage as backup
            self.driver.get('https://www.facebook.com')
            time.sleep(2)
            
            # Save credentials to localStorage (for manual retrieval if needed)
            js_code = f"""
            // Save credentials to localStorage for reference
            localStorage.setItem('fb_saved_username', JSON.stringify('{username}'));
            localStorage.setItem('fb_saved_password_hint', 'Credentials saved in Chrome Password Manager');
            
            // Log to console
            console.log('Facebook credentials saved to Chrome Profile');
            console.log('Next visit will show password suggestion');
            
            true;  // Return true to confirm
            """
            try:
                result = self.driver.execute_script(js_code)
                print("✅ Saved to localStorage as backup")
            except Exception as e:
                print(f"⚠️ LocalStorage save failed: {e}")
            
            # Method 2: Navigate to login form to trigger Chrome's password save mechanism
            print("🔐 Navigating to login form to set up Chrome autofill...")
            self.driver.get('https://www.facebook.com/login.php')
            time.sleep(3)
            
            try:
                # Find login form fields
                email_field = self.safe_find_element(By.ID, "email") or \
                             self.safe_find_element(By.NAME, "email") or \
                             self.safe_find_element(By.XPATH, "//input[@type='text' or @type='email'][@name='email']", timeout=5)
                
                password_field = self.safe_find_element(By.ID, "pass") or \
                                self.safe_find_element(By.NAME, "pass") or \
                                self.safe_find_element(By.XPATH, "//input[@type='password'][@name='pass']", timeout=5)
                
                if email_field and password_field:
                    print("📝 Filling login form with credentials...")
                    
                    # Clear and fill email
                    email_field.clear()
                    email_field.send_keys(username)
                    time.sleep(0.5)
                    
                    # Clear and fill password
                    password_field.clear()
                    password_field.send_keys(password)
                    time.sleep(0.5)
                    
                    # Trigger Chrome's password save prompt by focusing out
                    self.driver.execute_script("arguments[0].blur();", password_field)
                    time.sleep(1)
                    
                    print("✅ Credentials filled in login form")
                    print("💡 Chrome will ask to save password on next login attempt")
                    print("💾 Credentials are ready for Chrome's autofill on next visit")
                    
                    return True
                else:
                    print("⚠️ Login form fields not found, trying alternative method...")
                    
                    # Alternative: Try to find and interact with form
                    login_form = self.safe_find_element(By.ID, "login_form", timeout=5)
                    if login_form:
                        # Try generic email/password inputs
                        inputs = self.driver.find_elements(By.XPATH, "//input[@type='text' or @type='email' or @type='password']")
                        if len(inputs) >= 2:
                            inputs[0].clear()
                            inputs[0].send_keys(username)
                            time.sleep(0.5)
                            inputs[-1].clear()
                            inputs[-1].send_keys(password)
                            time.sleep(0.5)
                            print("✅ Credentials filled using generic selectors")
                            return True
                    
                    print("❌ Could not find login form fields")
                    return False
                    
            except Exception as e:
                print(f"⚠️ Form fill error: {e}")
                return False
            
        except Exception as e:
            print(f"Error saving credentials: {e}")
            return False
    
    def enable_chrome_autofill(self, username, password):
        """Enable Chrome's autofill/password manager for credentials"""
        try:
            print(f"🔏 Enabling Chrome autofill for: {username}")
            
            # Inject JavaScript to help Chrome recognize the credentials
            js_code = f"""
            // Mark form fields for Chrome to recognize
            const emailInputs = document.querySelectorAll('input[type="email"], input[type="text"][name*="email"], input[name="email"]');
            const passInputs = document.querySelectorAll('input[type="password"][name*="pass"], input[type="password"][name="pass"]');
            
            if (emailInputs.length > 0) {{
                emailInputs[0].setAttribute('autocomplete', 'username');
                emailInputs[0].setAttribute('aria-label', 'Username or email');
            }}
            
            if (passInputs.length > 0) {{
                passInputs[0].setAttribute('autocomplete', 'current-password');
                passInputs[0].setAttribute('aria-label', 'Password');
            }}
            
            console.log('Chrome autofill hints applied');
            true;
            """
            
            self.driver.execute_script(js_code)
            print("✅ Chrome autofill hints applied")
            return True
            
        except Exception as e:
            print(f"⚠️ Autofill setup failed: {e}")
            return False
