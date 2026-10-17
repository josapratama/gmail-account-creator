"""
Modul session warming: melakukan browsing acak sebelum pendaftaran
agar sesi terlihat seperti manusia asli (bukan bot langsung daftar).
"""
import random
import time

from selenium import webdriver

from anti_detection import tunggu_acak

# Daftar situs "biasa" untuk pemanasan sesi
WARMUP_URLS = [
    "https://www.google.com",
    "https://www.youtube.com",
    "https://www.wikipedia.org",
    "https://www.reddit.com",
    "https://news.ycombinator.com",
    "https://github.com",
    "https://stackoverflow.com",
    "https://medium.com",
    "https://www.bbc.com",
    "https://www.quora.com",
]


def panaskan_sesi(driver: webdriver.Chrome, jumlah_halaman: int = 3):
    """
    Mengunjungi beberapa situs acak dengan jeda acak
    untuk membangun riwayat sesi yang natural.
    """
    print(f"[WARMUP] Memanaskan sesi dengan {jumlah_halaman} halaman acak...")
    
    # Prioritaskan Google Search sebagai halaman pertama untuk membangun trust
    print(f"  [1/{jumlah_halaman+1}] Mengunjungi https://www.google.com dan melakukan pencarian...")
    try:
        driver.get("https://www.google.com")
        tunggu_acak(1, 2)
        try:
            # Cari input pencarian Google
            search_box = driver.find_element("name", "q")
            search_box.send_keys("berita hari ini")
            search_box.send_keys("\n")
            tunggu_acak(2, 4)
            # Klik link acak (opsional)
        except Exception:
            pass
    except Exception:
        pass

    pilihan = random.sample(WARMUP_URLS, min(jumlah_halaman, len(WARMUP_URLS)))

    for i, url in enumerate(pilihan, 2):
        try:
            # Cek apakah jendela masih hidup sebelum navigasi
            try:
                _ = driver.current_window_handle
            except Exception:
                print(f"  [!] Jendela browser tertutup, hentikan warmup.")
                break

            print(f"  [{i}/{len(pilihan)+1}] Mengunjungi {url}")
            driver.get(url)
            # Scroll sedikit agar terlihat seperti manusia
            driver.execute_script(f"window.scrollTo(0, document.body.scrollHeight * {random.uniform(0.1, 0.5)});")
            tunggu_acak(2.0, 5.0)
        except Exception as e:
            print(f"  [!] Gagal membuka {url}: {str(e).splitlines()[0]}")
            continue

    print("[WARMUP] Sesi selesai dipanaskan.")
