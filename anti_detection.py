"""
Modul anti-detection: stealth JS injection, random user-agent, human-like typing.
Bertujuan agar sesi browser tidak terdeteksi sebagai bot oleh Google.
"""
import random
import time

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement

# Daftar user-agent realistis (Chrome di Windows) - disesuaikan dgn Chrome 155
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36",
]

# Daftar user-agent mobile (Android Chrome). Dipakai saat mode mobile:
# di jalur mobile Google umumnya menawarkan verifikasi SMS (nomor telepon),
# bukan halaman QR code.
MOBILE_USER_AGENTS = [
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 12; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Mobile Safari/537.36",
]

# Viewport mobile (lebar x tinggi) untuk mode mobile
MOBILE_WIDTH = 412
MOBILE_HEIGHT = 915

# Stealth script: menghilangkan jejak webdriver & memalsukan properti navigator
STEALTH_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
window.chrome = { runtime: {} };
Object.defineProperty(navigator, 'permissions', {
    get: () => ({ query: () => Promise.resolve({ state: 'granted' }) })
});

// Tambahkan hardware concurrency & memory palsu agar terlihat seperti PC asli
Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });

const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) => (
    parameters.name === 'notifications'
        ? Promise.resolve({ state: Notification.permission })
        : originalQuery(parameters)
);
"""

def buat_chrome_options(proxy: str = "", mobile: bool = False) -> webdriver.ChromeOptions:
    """Membuat ChromeOptions dengan konfigurasi anti-detection.

    Jika mobile=True, gunakan User-Agent & viewport mobile sehingga Google
    cenderung menawarkan verifikasi SMS (bukan halaman QR code).
    """
    opsi = webdriver.ChromeOptions()
    opsi.add_argument("--disable-blink-features=AutomationControlled")
    opsi.add_argument("--no-sandbox")
    opsi.add_argument("--disable-extensions")
    opsi.add_argument("--disable-dev-shm-usage")
    # Jaga jendela tetap dianggap "visible" walau tertutup jendela lain.
    # Tanpa ini, Chrome menandai halaman sebagai hidden (document.visibilityState
    # = 'hidden') sehingga aplikasi SPA Google (Wiz) tidak me-render step baru
    # dan field-nya tetap berukuran 0x0 / tidak bisa diisi.
    opsi.add_argument("--disable-backgrounding-occluded-windows")
    opsi.add_argument("--disable-renderer-backgrounding")
    opsi.add_argument("--disable-background-timer-throttling")

    if mobile:
        opsi.add_argument(f"--user-agent={random.choice(MOBILE_USER_AGENTS)}")
        opsi.add_argument(f"--window-size={MOBILE_WIDTH},{MOBILE_HEIGHT}")
    else:
        # Gunakan ukuran jendela yang cukup besar agar konten tidak terpotong
        # namun tidak full screen agar tetap terlihat stabil di mode otomatis.
        opsi.add_argument("--window-size=1280,1024")
        opsi.add_argument(f"--user-agent={random.choice(USER_AGENTS)}")

    opsi.add_argument("--disable-infobars")
    
    opsi.add_experimental_option("excludeSwitches", ["enable-automation"])
    opsi.add_experimental_option("useAutomationExtension", False)

    # Preferensi agar tidak ada prompt "Chrome dikontrol otomatis"
    prefs = {
        "credentials_enable_service": False,
        "profile.password_manager_enabled": False,
        "intl.accept_languages": "en-US,en",
        "profile.default_content_setting_values.notifications": 2, # Blokir notifikasi
    }
    opsi.add_experimental_option("prefs", prefs)

    if proxy:
        opsi.add_argument(f"--proxy-server={proxy}")

    return opsi

def terapkan_stealth(driver: webdriver.Chrome):
    """Menyuntikkan script stealth & emulasi sensor untuk menyembunyikan jejak bot."""
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": STEALTH_SCRIPT},
    )
    
    # Emulasi Timezone agar cocok dengan proxy/lokasi (opsional jika proxy terdeteksi)
    try:
        driver.execute_cdp_cmd("Emulation.setTimezoneOverride", {"timezoneId": "Asia/Jakarta"})
    except Exception:
        pass
        
    # Emulasi Geolocation
    try:
        driver.execute_cdp_cmd("Emulation.setGeolocationOverride", {
            "latitude": -6.2088,
            "longitude": 106.8456,
            "accuracy": 100
        })
    except Exception:
        pass


def ketik_manusia(elemen: WebElement, teks: str, delay_min: float = 0.05, delay_max: float = 0.18):
    """Mengetik seperti manusia: jeda acak antar karakter."""
    for karakter in teks:
        elemen.send_keys(karakter)
        time.sleep(random.uniform(delay_min, delay_max))


def gerak_mouse_acak(driver: webdriver.Chrome):
    """Menggerakkan mouse secara acak untuk meniru perilaku manusia."""
    lebar = driver.execute_script("return window.innerWidth")
    tinggi = driver.execute_script("return window.innerHeight")
    for _ in range(random.randint(3, 7)):
        x = random.randint(0, lebar)
        y = random.randint(0, tinggi)
        driver.execute_script(
            f"document.elementFromPoint({x}, {y})?.dispatchEvent("
            f"new MouseEvent('mousemove', {{clientX: {x}, clientY: {y}, bubbles: true}}))"
        )
        time.sleep(random.uniform(0.1, 0.3))


def tunggu_acak(min_detik: float = 1.0, max_detik: float = 2.5):
    """Jeda waktu acak untuk meniru perilaku manusia."""
    time.sleep(random.uniform(min_detik, max_detik))
