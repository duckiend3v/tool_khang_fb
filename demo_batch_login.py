#!/usr/bin/env python3
"""
Demo script for Batch Login functionality
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def demo_batch_login():
    """Demo batch login with sample accounts"""
    print("🔐 SocialFarmTool - Batch Login Demo")
    print("=" * 50)

    # Sample accounts with proxies
    sample_accounts = [
        {
            "id": "demo_fb_001",
            "name": "Demo Account 1",
            "proxy": "103.166.184.186:12335:ue1412335:1774837915"
        },
        {
            "id": "demo_fb_002",
            "name": "Demo Account 2",
            "proxy": "103.166.184.186:12335:ue1412335:1774837915"  # Same proxy for demo
        }
    ]

    print(f"📋 Sẽ đăng nhập {len(sample_accounts)} tài khoản demo")
    print("\n🔧 Các tính năng:")
    print("✅ Tự động parse proxy format host:port:user:pass")
    print("✅ Test proxy connectivity trước khi dùng")
    print("✅ Mở Chrome với profile riêng cho mỗi account")
    print("✅ Navigate tới Facebook/TikTok tự động")
    print("✅ Xử lý lỗi và báo cáo chi tiết")
    print("✅ Không block UI (chạy trong background thread)")

    print("\n📝 Cách sử dụng trong ứng dụng:")
    print("1. Mở SocialFarmTool")
    print("2. Chọn Facebook hoặc TikTok")
    print("3. Thêm accounts với proxy (format: host:port:user:pass)")
    print("4. Click nút '🔐 Batch Login'")
    print("5. Xem progress trong cột 'Trạng Thái'")

    print("\n⚠️  Lưu ý:")
    print("- Proxy phải hoạt động và support HTTPS")
    print("- Mỗi account cần có proxy riêng")
    print("- Chrome profiles sẽ được tạo tự động")
    print("- Các trình duyệt sẽ giữ mở sau khi login")

    print("\n🎯 Demo hoàn thành! Chạy main.py để test thực tế.")

if __name__ == "__main__":
    demo_batch_login()