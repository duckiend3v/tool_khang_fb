# Social Farm Tool (Tool Kháng & Nuôi Facebook / TikTok)

Phần mềm tự động hóa quản lý tài khoản, nuôi nick, kháng nghị, seeding và quản lý Fanpage đa nền tảng (Facebook, TikTok) với giao diện PyQt5.

## Tính năng chính

- **Quản lý tài khoản đa luồng**: Thêm, sửa, xóa, tìm kiếm theo UID, quản lý proxy riêng cho từng tài khoản.
- **Đăng nhập tự động & thông minh**:
  - Hỗ trợ đăng nhập siêu tốc bằng **Cookie** (tự động phân tích và nạp c_user, xs, datr, fr qua CDP & Selenium).
  - Tự động fallback sang **UID / Password + 2FA** nếu cookie hết hạn.
  - Tự động tính mã TOTP 2FA cục bộ chuẩn xác.
- **Nuôi nick & tương tác (Farming)**:
  - Lướt Newsfeed, xem Watch, thả tim/reaction dạo.
  - Tự động kết bạn theo gợi ý, tham gia nhóm theo từ khóa.
  - Kiểm tra thông báo định kỳ.
- **Đăng bài tự động (Posting)**:
  - Đăng status kèm ảnh/video ngẫu nhiên từ kho media.
  - Đăng Facebook Reels, Story.
  - Đăng bài lên Fanpage với nội dung spin / scraped.
- **Seeding đa nhiệm (Buff tương tác)**:
  - Tăng Follow/Like Page hoặc Profile.
  - Buff like, comment bài viết, reels, story theo kịch bản.
- **Hỗ trợ Proxy đa dạng**: HTTP, HTTPS, Proxy có xác thực username/password thông qua Proxy Bridge tích hợp.
- **Quản lý Fanpage**: Tự động cào bài viết (Scrape posts), tạo trang mới, đổi context Profile <-> Page mượt mà.

## Yêu cầu hệ thống

- Windows 10/11
- Python 3.10+
- Google Chrome phiên bản mới nhất

## Cài đặt

1. Clone repository:
```bash
git clone https://github.com/duckiend3v/tool_khang_fb.git
cd tool_khang_fb
```

2. Tạo môi trường ảo và cài đặt thư viện:
```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

3. Khởi chạy tool:
```bash
python main.py
```

## Định dạng Import Tài Khoản

Cấu trúc mỗi dòng khi Import:
```text
UID|Name|Cookie|Token|Email|EmailPassword|2FACode|FacebookPassword
```

Cấu trúc Proxy:
```text
IP:Port:Username:Password hoặc IP:Port
```

## Đóng gói ứng dụng (Build Executable)

```bash
pyinstaller --noconfirm --onedir --windowed --name "SocialFarmTool" --add-data "data_name_page.txt;." main.py
```
File thực thi sẽ nằm trong thư mục `dist/SocialFarmTool/`.

## License
MIT License
