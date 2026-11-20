# browser/chrome_launcher.py
import time
import random
import os
import shutil
import subprocess
import re
import winreg
import undetected_chromedriver as uc
import urllib.request
import urllib.error
import json
from urllib.parse import urlparse, quote, unquote
from .proxy_bridge import AuthenticatedProxyBridge

class ChromeLauncher:
    # Class variable to track if we've cleaned cache this session
    _cache_cleaned = False
    _detected_version = None  # Cache detected version
    _direct_public_ip = None
    
    @staticmethod
    def parse_proxy(proxy_str):
        """Parse proxy string in format: host:port:user:pass, socks5://user:pass@host:port, or http://user:pass@host:port"""
        if not proxy_str or len(proxy_str.strip()) < 5:
            return None
        
        proxy_str = proxy_str.strip()
        
        # If already in full URL format, return as-is
        if proxy_str.startswith(('http://', 'https://', 'socks4://', 'socks5://')):
            if proxy_str.startswith('socks'):
                print(f"--> Warning: SOCKS proxies ({proxy_str}) are not supported by Chrome's --proxy-server option")
                print("    --> Chrome only supports HTTP/HTTPS proxies. Use http:// format instead.")
                return None
            return proxy_str
        
        # Parse host:port:user:pass format (assume HTTP)
        parts = proxy_str.split(':')
        if len(parts) == 4:
            host, port, user, password = parts
            return f"http://{quote(user, safe='')}:{quote(password, safe='')}@{host}:{port}"
        
        # If only host:port, return as-is (no auth)
        elif len(parts) == 2:
            return f"http://{proxy_str}"
        
        # Invalid format
        print(f"--> Warning: Invalid proxy format '{proxy_str}'")
        print("    --> Supported formats: host:port:user:pass or http://user:pass@host:port")
        print("    --> Note: SOCKS proxies are not supported by Chrome")
        return None

    @staticmethod
    def parse_proxy_components(proxy_str):
        """Return structured proxy parts for Chrome launch logic."""
        proxy_url = ChromeLauncher.parse_proxy(proxy_str)
        if not proxy_url:
            return None

        parsed = urlparse(proxy_url)
        if parsed.scheme not in ("http", "https"):
            return None

        if not parsed.hostname or not parsed.port:
            return None

        return {
            "scheme": parsed.scheme,
            "host": parsed.hostname,
            "port": parsed.port,
            "username": unquote(parsed.username) if parsed.username else None,
            "password": unquote(parsed.password) if parsed.password else None,
            "url": proxy_url,
            "server": f"{parsed.scheme}://{parsed.hostname}:{parsed.port}",
        }

    @staticmethod
    def test_proxy_connectivity(proxy_url, timeout=10):
        """Test if proxy is working by making HTTP and HTTPS requests"""
        try:
            # Parse proxy URL to create proxy handler
            if proxy_url.startswith('http://'):
                proxy_handler = urllib.request.ProxyHandler({'http': proxy_url, 'https': proxy_url})
            else:
                print(f"--> Unsupported proxy protocol for testing: {proxy_url}")
                return False
            
            opener = urllib.request.build_opener(proxy_handler)
            opener.addheaders = [('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')]
            
            # Test HTTP first
            print("    --> Testing HTTP connectivity...")
            try:
                response = opener.open('http://httpbin.org/ip', timeout=timeout)
                if response.status == 200:
                    import json
                    data = json.loads(response.read().decode('utf-8'))
                    proxy_ip = data.get('origin', 'Unknown')
                    print(f"    --> HTTP test successful! Your IP appears as: {proxy_ip}")
                else:
                    print(f"    --> HTTP test failed: Status {response.status}")
                    return False
            except Exception as e:
                print(f"    --> HTTP test failed: {str(e)}")
                return False
            
            # Test HTTPS
            print("    --> Testing HTTPS connectivity...")
            try:
                response = opener.open('https://httpbin.org/ip', timeout=timeout)
                if response.status == 200:
                    import json
                    data = json.loads(response.read().decode('utf-8'))
                    proxy_ip = data.get('origin', 'Unknown')
                    print(f"    --> HTTPS test successful! Your IP appears as: {proxy_ip}")
                else:
                    print(f"    --> HTTPS test failed: Status {response.status}")
                    print("    --> Note: Proxy may not support HTTPS, which could cause ERR_NO_SUPPORTED_PROXIES in Chrome")
                    return False
            except Exception as e:
                print(f"    --> HTTPS test failed: {str(e)}")
                print("    --> Note: Proxy may not support HTTPS, which could cause ERR_NO_SUPPORTED_PROXIES in Chrome")
                return False
            
            print("    --> All tests passed! Proxy supports both HTTP and HTTPS")
            return True
                
        except Exception as e:
            print(f"--> Proxy test error: {str(e)}")
            return False

    @staticmethod
    def _read_ip_response(body):
        """Extract the first public IP from common IP-check responses."""
        try:
            data = json.loads(body)
        except (TypeError, ValueError):
            data = None

        if isinstance(data, dict):
            value = data.get('origin') or data.get('ip')
            if value:
                return str(value).split(',')[0].strip()

        match = re.search(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', body or '')
        return match.group(0) if match else None

    @staticmethod
    def get_direct_public_ip(timeout=12):
        """Get the machine's public IP without environment proxies."""
        if ChromeLauncher._direct_public_ip:
            return ChromeLauncher._direct_public_ip
        try:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            opener.addheaders = [('User-Agent', 'Mozilla/5.0')]
            with opener.open('https://httpbin.org/ip', timeout=min(timeout, 8)) as response:
                ip = ChromeLauncher._read_ip_response(response.read().decode('utf-8', 'replace'))
                ChromeLauncher._direct_public_ip = ip
                return ip
        except Exception as exc:
            print(f"--> Direct IP check unavailable: {str(exc)[:160]}")
            return None

    @staticmethod
    def get_browser_public_ip(driver, timeout=20):
        """Read the egress IP from the same Chrome instance being launched."""
        original_handle = driver.current_window_handle
        check_handle = None
        try:
            driver.execute_script("window.open('about:blank', '_proxy_check');")
            handles = driver.window_handles
            check_handle = handles[-1]
            driver.switch_to.window(check_handle)
            driver.set_page_load_timeout(min(timeout, 10))
            driver.get('https://httpbin.org/ip')
            body = driver.find_element('tag name', 'body').text
            ip = ChromeLauncher._read_ip_response(body)
            if not ip:
                raise RuntimeError('IP response did not contain an address')
            return ip
        finally:
            if check_handle and check_handle in driver.window_handles:
                driver.close()
            if original_handle in driver.window_handles:
                driver.switch_to.window(original_handle)

    @staticmethod
    def verify_browser_proxy(driver, timeout=20):
        """Fail closed when Chrome is using the machine IP."""
        direct_ip = ChromeLauncher.get_direct_public_ip(timeout=min(timeout, 8))
        browser_ip = ChromeLauncher.get_browser_public_ip(driver, timeout=min(timeout, 10))
        print(f"--> Chrome egress IP: {browser_ip}")

        if direct_ip and browser_ip == direct_ip:
            raise RuntimeError(
                f"Chrome is using the direct machine IP ({browser_ip}); proxy was not applied"
            )
        return browser_ip
    
    @staticmethod
    def cleanup_cache_aggressive():
        """Aggressively clean undetected_chromedriver cache"""
        cache_dir = os.path.expanduser("~\\appdata\\roaming\\undetected_chromedriver")
        if os.path.exists(cache_dir):
            try:
                # Try multiple times to remove directory
                last_error = None
                for attempt in range(3):
                    try:
                        shutil.rmtree(cache_dir)
                        time.sleep(0.5)
                        if not os.path.exists(cache_dir):
                            print("--> Cache directory cleaned successfully")
                            return True
                    except Exception as e:
                        if attempt < 2:
                            time.sleep(1)
                        last_error = e
                print(f"--> Cache cleanup skipped: {last_error}")
                return False
            except Exception as e:
                print(f"--> Warning: {e}")
                return False
        return True
    
    @staticmethod
    def get_chrome_version():
        """Phát hiện phiên bản Chrome - Multiple methods with fallbacks"""
        
        # Return cached version if already detected
        if ChromeLauncher._detected_version:
            return ChromeLauncher._detected_version
        
        # Method 1: Windows Registry (Most Reliable)
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Google\Chrome\Binaries") as key:
                version_str, _ = winreg.QueryValueEx(key, "pv")
                match = re.search(r'(\d+)', version_str)
                if match:
                    version = int(match.group(1))
                    print(f"--> Chrome version detected (Registry): {version}")
                    ChromeLauncher._detected_version = version
                    return version
        except Exception:
            pass
        
        # Method 2: File version from chrome.exe
        chrome_paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ]
        
        for path in chrome_paths:
            if os.path.exists(path):
                try:
                    # Try PowerShell with timeout
                    cmd = f'powershell -NoProfile -Command "try {{ (Get-Item \'{path}\').VersionInfo.ProductVersion }} catch {{ exit 1 }}"'
                    result = subprocess.run(cmd, capture_output=True, text=True, shell=True, timeout=5)
                    
                    if result.stdout and result.returncode == 0:
                        version_str = result.stdout.strip()
                        match = re.search(r'(\d+)', version_str)
                        if match:
                            version = int(match.group(1))
                            print(f"--> Chrome version detected (File): {version}")
                            ChromeLauncher._detected_version = version
                            return version
                except Exception:
                    pass
        
        # Method 3: Let undetected_chromedriver auto-detect instead of hardcoding
        print("--> Could not detect Chrome version, falling back to auto-detect")
        return None

    @staticmethod
    def launch(profile_path, proxy=None, headless=False, force_proxy=False, verify_proxy=False):
        absolute_path = os.path.abspath(profile_path)
        
        # Clean cache on first launch only
        if not ChromeLauncher._cache_cleaned:
            ChromeLauncher.cleanup_cache_aggressive()
            ChromeLauncher._cache_cleaned = True
            time.sleep(2)  # Wait for cleanup
        
        # Xóa lock files
        lock_files = ["Lockfile", "SingletonLock", "SingletonSocket"]
        for file_name in lock_files:
            lock_path = os.path.join(absolute_path, file_name)
            if os.path.exists(lock_path):
                try:
                    os.remove(lock_path)
                    print(f"--> Removed lock file: {file_name}")
                except Exception:
                    pass 
        
        # Thêm delay ngẫu nhiên để tránh xung đột khi khởi động nhiều trình duyệt cùng lúc
        time.sleep(random.uniform(0.5, 1.5))

        options = uc.ChromeOptions()
        options.add_argument(f'--user-data-dir={absolute_path}')
        options.add_argument('--homepage=about:blank')
        options.add_argument('--no-first-run')
        options.add_argument('--no-default-browser-check')
        options.add_argument('--disable-background-networking')
        options.add_argument('--disable-sync')
        options.add_argument('--metrics-recording-only')
        options.add_argument('--disable-component-update')
        options.add_argument("--disable-notifications")
        options.add_argument("--password-store=basic")
        # UID/password login should not open Chrome's native save-password bubble.
        options.add_experimental_option("prefs", {
            "credentials_enable_service": False,
            "profile.password_manager_enabled": False,
            "profile.password_manager_leak_detection": False,
        })
        options.add_argument("--disable-save-password-bubble")
        options.add_argument("--disable-features=PasswordManagerOnboarding,PasswordLeakDetection")
        
        # Only disable proxy auto-detection when we are not explicitly using a proxy
        options.add_argument('--proxy-bypass-list=<-loopback>')
        
        # Optimization to reduce memory
        options.add_argument("--no-service-autorun") 
        options.add_argument("--password-store=basic")
        
        # Additional options to prevent proxy conflicts
        options.add_argument('--disable-plugins')
        options.add_argument('--disable-default-apps')
        
        # Parse and configure proxy
        proxy_configured = False
        proxy_bridge = None
        if proxy and len(proxy.strip()) > 5:
            proxy_config = ChromeLauncher.parse_proxy_components(proxy)
            if not proxy_config:
                raise ValueError(f"Invalid or unsupported proxy format: {proxy}")

            # The old urllib HTTP+HTTPS preflight could block 15–30 seconds while
            # Chrome remained on New Tab. The browser-level verification below is
            # the authoritative check, so do not run a duplicate preflight here.
            print(f"--> Using proxy: {proxy_config['server']}")

            # Chrome 137+ branded builds reject --load-extension for unpacked
            # extensions. Use a loopback bridge for authenticated proxies so
            # Chrome only needs a normal unauthenticated proxy endpoint.
            if proxy_config["username"] is not None or proxy_config["password"] is not None:
                proxy_bridge = AuthenticatedProxyBridge(proxy_config).start()
                bridge_host, bridge_port = proxy_bridge.address
                options.add_argument(f'--proxy-server=http://{bridge_host}:{bridge_port}')
            else:
                options.add_argument(f'--proxy-server={proxy_config["server"]}')
            proxy_configured = True

        if not proxy_configured:
            options.add_argument('--no-proxy-server')
        else:
            options.add_argument('--proxy-bypass-list=<-loopback>')
        
        # Retry mechanism
        max_retries = 3
        for i in range(max_retries):
            try:
                # Detect Chrome version
                chrome_version = ChromeLauncher.get_chrome_version()
                if chrome_version:
                    print(f"--> Detected Chrome version: {chrome_version}")
                    driver = uc.Chrome(options=options, use_subprocess=True, headless=headless, version_main=chrome_version)
                else:
                    print("--> Could not detect Chrome version, auto-detecting...")
                    driver = uc.Chrome(options=options, use_subprocess=True, headless=headless)
                
                print(f"--> Driver initialized successfully")
                print(f"--> Chrome/Driver: {driver.capabilities.get('browserVersion', 'Unknown')[:15]} / {driver.capabilities.get('chrome', {}).get('chromedriverVersion', 'Unknown')[:15]}")
                
                # Setup window size
                driver.set_window_size(1000, 800)

                if proxy_configured and verify_proxy:
                    try:
                        ChromeLauncher.verify_browser_proxy(driver, timeout=10)
                    except Exception:
                        try:
                            driver.quit()
                        except Exception:
                            pass
                        raise

                if proxy_bridge:
                    original_quit = driver.quit

                    def quit_with_proxy_bridge(*args, **kwargs):
                        try:
                            return original_quit(*args, **kwargs)
                        finally:
                            proxy_bridge.close()

                    driver.quit = quit_with_proxy_bridge
                
                return driver
            
            except Exception as e:
                print(f"--> Error initializing Chrome (Attempt {i+1}/{max_retries}): {str(e)[:100]}")
                
                if i < max_retries - 1:
                    time.sleep(2)
                else:
                    if proxy_bridge:
                        proxy_bridge.close()
                    raise e

        return None
