#!/usr/bin/env python3
"""
Debug script to test Chrome launch with proxy
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from browser.chrome_launcher import ChromeLauncher
import time

def test_chrome_with_proxy(proxy_string, profile_path=None):
    """Test launching Chrome with a proxy"""
    print(f"\n{'='*60}")
    print(f"Testing Chrome launch with proxy: {proxy_string}")
    print(f"{'='*60}")

    # Use a test profile if not specified
    if not profile_path:
        profile_path = os.path.join(os.getcwd(), 'data', 'profiles', 'facebook', 'debug_test_profile')
        os.makedirs(profile_path, exist_ok=True)

    try:
        print(f"Launching Chrome with profile: {profile_path}")
        driver = ChromeLauncher.launch(profile_path, proxy=proxy_string, headless=True)

        if driver:
            print("✅ Chrome launched successfully!")

            # Test navigation to Google
            print("Testing navigation to Google...")
            try:
                driver.get('https://www.google.com')
                time.sleep(3)

                title = driver.title
                url = driver.current_url

                if 'Google' in title or 'google' in url:
                    print("✅ Successfully navigated to Google!")
                    print(f"   Title: {title}")
                    print(f"   URL: {url}")
                else:
                    print("⚠️  Navigation completed but page may not have loaded correctly")
                    print(f"   Title: {title}")
                    print(f"   URL: {url}")

            except Exception as e:
                print(f"❌ Navigation failed: {str(e)}")

            # Close browser
            driver.quit()
            print("✅ Browser closed successfully")
            return True
        else:
            print("❌ Chrome launch failed")
            return False

    except Exception as e:
        print(f"❌ Error during Chrome launch: {str(e)}")
        return False

def main():
    print("SocialFarmTool Chrome Proxy Debug Tool")
    print("This tool tests Chrome launch with proxy configuration")
    print()

    if len(sys.argv) > 1:
        proxy = sys.argv[1]
        test_chrome_with_proxy(proxy)
    else:
        print("Usage: python debug_chrome_proxy.py \"host:port:user:pass\"")
        print("Example: python debug_chrome_proxy.py \"103.166.184.186:31541:ac4931541:1774837920\"")

if __name__ == "__main__":
    main()