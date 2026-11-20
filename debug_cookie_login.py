#!/usr/bin/env python
"""Debug script - Tìm lỗi tại sao cookie login không hoạt động"""
import sys
import os
sys.path.insert(0, '.')

print("=" * 80)
print("  🔍 COOKIE LOGIN DEBUG SCRIPT")
print("=" * 80)

# Test data từ file
test_account = {
    "id": "61577444580525",
    "name": "61577444580525",
    "cookie": "c_user=61577444580525;xs=32:zfPBr1ZnMO7mCg:2:1750195500:-1:-1;fr=0KvRGepkpCnH7kkTO.AWeZ7u1RnFF537-eJogtkc1KvZr-dmTqhh4D3gqF5bjpzMpbc-8.BoUd0v..AAA.0.0.BoUd0v.AWesXn5SjG3bRavxk4Gq6GpIwbo;datr=K91RaLxA76pAcGR7Iv_9fIDs;",
    "token": "EAAAAUaZA8jlABO9eySgsSPoipfLxZBy8BFQlui3Utbhl958pr2rjrfdLjH6EcuyGprKfbP3hRI5ZAqiomyRoWkgUZAZCT9M0ZAzl2ru3udyVsnB5mc5vcssKGyXyJ4yyhQY1XV9owpyQrzZCq3uJxLgcB9WwJRxGMdNSnFOl14DIdv0X5FusfrWppZCWtbZAVMp2hwvGW1jnbSgZDZD",
    "email": "georgiaflower11@outlook.com",
    "email_password": "un7cpgbacd",
    "2fa_code": "3NNXDL2MW243PHNDXW7TZGKUL3Z26VMY",
    "password": "Vip@tn9dvanjQ",
    "proxy": ""
}

print("\n[STEP 1] Kiểm Tra Cookie Format")
print("-" * 80)

cookie_str = test_account.get('cookie', '')
print(f"Cookie string: {cookie_str[:100]}...")
print(f"Cookie length: {len(cookie_str)} chars")

if not cookie_str:
    print("❌ ERROR: Không có cookie!")
    sys.exit(1)

# Tách cookies
cookies = [c.strip() for c in cookie_str.split(';') if '=' in c]
print(f"\n✅ Found {len(cookies)} cookie parts after splitting:")

for i, cookie in enumerate(cookies, 1):
    parts = cookie.split('=', 1)
    if len(parts) == 2:
        name, value = parts
        print(f"  {i}. Name: {name:15} | Value: {value[:40]}{'...' if len(value) > 40 else ''}")
    else:
        print(f"  {i}. ⚠️ INVALID: {cookie}")

print("\n[STEP 2] Kiểm Tra Cookie Expiry")
print("-" * 80)

import time
cookie_expiry = int(time.time()) + (90 * 24 * 60 * 60)
current_time = int(time.time())

print(f"Current timestamp: {current_time}")
print(f"Cookie expiry will be set to: {cookie_expiry}")
print(f"Days from now: {(cookie_expiry - current_time) / (24 * 60 * 60):.1f} days")

# Check if xs cookie has expiry info
xs_cookie = [c for c in cookies if c.startswith('xs=')]
if xs_cookie:
    xs_parts = xs_cookie[0].split('=', 1)
    if len(xs_parts) == 2:
        xs_value = xs_parts[1]
        print(f"\n✅ xs cookie found: {xs_value}")
        # xs format: 32:zfPBr1ZnMO7mCg:2:1750195500:-1:-1
        xs_tokens = xs_value.split(':')
        if len(xs_tokens) >= 4:
            try:
                xs_expiry = int(xs_tokens[3])
                time_left = xs_expiry - current_time
                print(f"  └─ xs expiry timestamp: {xs_expiry}")
                print(f"  └─ Time left: {time_left / (24 * 60 * 60):.1f} days")
                if time_left > 0:
                    print(f"  ✅ Cookie is VALID (not expired)")
                else:
                    print(f"  ❌ Cookie is EXPIRED!")
            except:
                print(f"  ⚠️ Could not parse xs expiry")

print("\n[STEP 3] Kiểm Tra Các Vấn Đề Thường Gặp")
print("-" * 80)

issues = []

# Issue 1: Cookie không có dấu chấm phẩy ở cuối
if not cookie_str.endswith(';'):
    issues.append("⚠️ Cookie không kết thúc bằng ';' (có thể không ảnh hưởng)")
    print(issues[-1])
else:
    print("✅ Cookie kết thúc bằng ';'")

# Issue 2: c_user không match với ID
if 'c_user=' in cookie_str:
    c_user_start = cookie_str.find('c_user=') + 7
    c_user_end = cookie_str.find(';', c_user_start)
    c_user_value = cookie_str[c_user_start:c_user_end]
    account_id = test_account['id']
    
    if c_user_value == account_id:
        print(f"✅ c_user ({c_user_value}) matches account ID ({account_id})")
    else:
        issues.append(f"❌ c_user ({c_user_value}) KHÔNG MATCH account ID ({account_id})")
        print(issues[-1])

# Issue 3: Kiểm tra các cookie bắt buộc
required_cookies = ['c_user', 'xs', 'datr', 'fr']
missing = []
for req in required_cookies:
    if not any(c.startswith(req + '=') for c in cookies):
        missing.append(req)

if missing:
    issues.append(f"⚠️ Missing cookies: {', '.join(missing)}")
    print(f"❌ Missing: {', '.join(missing)}")
else:
    print(f"✅ All required cookies present: {', '.join(required_cookies)}")

print("\n[STEP 4] Possible Reasons Why Login Fails")
print("-" * 80)

print("""
Có thể lý do tại sao cookie không hoạt động:

1️⃣ Cookie HẾT HẠN
   └─ Vì cookie được lấy từ lâu (> 90 ngày)
   └─ Hoặc account bị checkpoint/lock
   └─ Hoặc account password đã bị thay đổi
   
   FIX: Lấy cookie mới từ browser

2️⃣ Cookie domain sai
   └─ Cookie phải được inject vào .facebook.com
   └─ Nếu inject sai domain → không hoạt động
   
   FIX: Check code xem domain có đúng không

3️⃣ Browser không navigate đến facebook.com trước
   └─ Must navigate BEFORE injecting cookies
   └─ Nếu không → cookies sẽ bị reject
   
   FIX: Kiểm tra code logic

4️⃣ Session check XPath sai
   └─ Facebook thay đổi structure → XPath không match
   └─ Nên thêm fallback checks
   
   FIX: Update XPath selectors

5️⃣ Proxy issue
   └─ Nếu account bị detect VPN/proxy → checkpoint
   └─ Hoặc proxy IP bị block
   
   FIX: Dùng residential proxy hoặc không dùng proxy

6️⃣ Account bị checkpoint/2FA required
   └─ Cần verify email hoặc SMS
   └─ Cookie không thể vượt qua
   
   FIX: Verify account trước hoặc dùng email login

7️⃣ Chrome version không match
   └─ undetected-chromedriver mismatch
   └─ Browser bị block
   
   FIX: Update Chrome version hoặc dùng version mới nhất

8️⃣ Headless mode issue
   └─ Nếu chạy headless → Facebook có thể detect
   └─ Headless browser hoạt động khác
   
   FIX: Dùng visible mode (có window)

9️⃣ Cookie được stolen/logged out
   └─ Account logout từ browser khác
   └─ Cookie bị invalidate
   
   FIX: Lấy cookie mới khi account online

🔟 Session persistence issue
   └─ Profile không lưu cookie đúng cách
   └─ Selenium add_cookie có bug
   
   FIX: Dùng JavaScript fallback để inject cookies
""")

print("\n[STEP 5] Các Dấu Hiệu Để Xác Định Vấn Đề")
print("-" * 80)

print("""
✅ Cookie sống (according to test) BUT login fails:

Điều này có thể xảy ra vì:
   1. Check "sống" chỉ kiểm tra timestamp, không kiểm tra actual validity
   2. Cookie có thể expired nhưng timestamp vẫn OK
   3. Account bị checkpoint → cookie không thể dùng
   4. Browser detection → Facebook block headless browser
   5. Cookie bị revoke ở phía Facebook

🧪 Để xác định:
   1. Mở account trong browser bình thường
   2. Nếu account bình thường login được → cookie sống
   3. Nếu account show login page → cookie chết
   
   4. Nếu browser trong tool show login page nhưng account online ở browser khác
      → Vấn đề là browser detection hoặc cookie injection
      
   5. Nếu account offline ở tất cả browser
      → Vấn đề là account (checkpoint/lock/password changed)
""")

print("\n[STEP 6] Giải Pháp")
print("-" * 80)

print("""
Quick fixes (thứ tự ưu tiên):

1️⃣ LẤY COOKIE MỚI
   Steps:
   1. Mở account trong Chrome bình thường
   2. F12 → Application → Cookies
   3. Right-click → Copy all
   4. Paste vào import
   5. Re-import & test
   
   ⏱️ Time: 2 minutes

2️⃣ KIỂM TRA PROXY
   1. Thử không dùng proxy
   2. Hoặc thử residential proxy khác
   3. Hoặc thử mobile proxy
   
   ⏱️ Time: 5 minutes

3️⃣ KIỂM TRA ACCOUNT
   1. Mở browser Chrome bình thường
   2. Manual login với UID + password
   3. Check có checkpoint không
   4. Nếu checkpoint → solve trước
   
   ⏱️ Time: 5 minutes

4️⃣ UPDATE CODE (nâng cao)
   1. Cải thiện XPath selectors
   2. Thêm fallback checks
   3. Dùng JavaScript inject fallback
   4. Thêm delay giữa các steps
   
   ⏱️ Time: 30 minutes

5️⃣ ENABLE DEBUG LOGGING
   1. Capture screenshot khi login fail
   2. Log current_url
   3. Log XPath match results
   4. Analyze error
   
   ⏱️ Time: 10 minutes
""")

print("\n[SUMMARY]")
print("=" * 80)

if not issues:
    print("✅ Cookie format looks OK")
    print("\n❓ But you say login fails?")
    print("\nThen the issue is likely:")
    print("  1. Cookie actually expired (timestamp OK but Facebook rejected it)")
    print("  2. Account checkpoint/locked")
    print("  3. Browser detection issue")
    print("  4. Proxy blocking")
    print("  5. Code XPath selectors not matching new Facebook layout")
else:
    print(f"⚠️ Found {len(issues)} potential issues:")
    for issue in issues:
        print(f"  - {issue}")

print("\n" + "=" * 80)
print("Recommendation: Thử các bước trong 'Giải Pháp' ở trên, bắt đầu từ 1️⃣")
print("=" * 80)
