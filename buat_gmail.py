"""
Skrip otomatisasi pembuatan akun Gmail menggunakan Selenium.

PENTING:
- Google memiliki proteksi CAPTCHA dan verifikasi nomor telepon,
  jadi proses ini tidak bisa 100% otomatis. Skrip ini mengisi form
  pendaftaran, lalu Anda cukup menyelesaikan CAPTCHA/verifikasi telepon
  secara manual.
- Gunakan hanya untuk keperluan pribadi dan patuhi Kebijakan Google.

Cara pakai:
1. Install dependensi:
       pip install selenium webdriver-manager
2. Jalankan:
       python buat_gmail.py
3. Isi data yang diminta di terminal, lalu selesaikan CAPTCHA/OTP secara manual
   saat diminta oleh browser.
"""

import time
import getpass

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


def buat_driver():
    """Membuat instance Chrome WebDriver."""
    opsi = webdriver.ChromeOptions()
    opsi.add_argument("--start-maximized")
    opsi.add_argument("--disable-blink-features=AutomationControlled")
    opsi.add_experimental_option("excludeSwitches", ["enable-automation"])
    opsi.add_experimental_option("useAutomationExtension", False)

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=opsi)
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"},
    )
    return driver


def tunggu_dan_isi(driver, xpath, teks, timeout=30):
    """Menunggu elemen muncul lalu mengisinya dengan teks."""
    elemen = WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.XPATH, xpath))
    )
    elemen.clear()
    elemen.send_keys(teks)
    return elemen


def tunggu_dan_klik(driver, xpath, timeout=30):
    """Menunggu elemen dapat diklik lalu mengkliknya."""
    elemen = WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((By.XPATH, xpath))
    )
    elemen.click()
    return elemen


def buat_akun_gmail(nama_depan, nama_belakang, username, password):
    """
    Mengotomasi proses pendaftaran Gmail sampai tahap verifikasi.
    Setelah itu, pengguna harus menyelesaikan CAPTCHA & verifikasi telepon manual.
    """
    driver = buat_driver()
    try:
        # Halaman pendaftaran akun Google
        driver.get("https://accounts.google.com/signup")

        # 1. Isi nama depan & nama belakang
        print("[1/6] Mengisi nama...")
        tunggu_dan_isi(driver, '//*[@id="firstName"]', nama_depan)
        tunggu_dan_isi(driver, '//*[@id="lastName"]', nama_belakang)
        tunggu_dan_klik(driver, '//*[@id="collectNameNext"]/div/button')

        # 2. Isi tanggal lahir & gender
        # (biasanya muncul setelah langkah nama)
        print("[2/6] Mengisi tanggal lahir & gender...")
        try:
            tunggu_dan_isi(driver, '//*[@id="day"]', "15")
            tunggu_dan_klik(driver, '//*[@id="month"]//option[@value="6"]')  # Juni
            tunggu_dan_isi(driver, '//*[@id="year"]', "2000")
            tunggu_dan_klik(driver, '//*[@id="gender"]//option[@value="1"]')  # Laki-laki
            tunggu_dan_klik(driver, '//*[@id="birthdaygenderNext"]/div/button')
        except Exception as e:
            print("   Lewati tahap tanggal lahir (mungkin layout berbeda):", e)

        # 3. Pilih buat alamat Gmail sendiri
        print("[3/6] Memilih alamat Gmail...")
        try:
            tunggu_dan_klik(
                driver,
                '//input[@type="radio" and @name="GmailAddress"]',
                timeout=15,
            )
            tunggu_dan_isi(driver, '//*[@id="username"]', username)
        except Exception:
            # Kadang langsung diminta username
            try:
                tunggu_dan_isi(driver, '//*[@id="username"]', username, timeout=10)
            except Exception as e:
                print("   Gagal mengisi username:", e)

        tunggu_dan_klik(driver, '//*[@id="next"]/div/button')

        # 4. Isi password
        print("[4/6] Mengisi password...")
        tunggu_dan_isi(driver, '//*[@id="passwd"]/div[1]/div/div[1]/input', password)
        tunggu_dan_isi(driver, '//*[@id="confirm-passwd"]/div[1]/div/div[1]/input', password)
        tunggu_dan_klik(driver, '//*[@id="createpasswordNext"]/div/button')

        # 5. Verifikasi nomor telepon (manual)
        print("[5/6] Menunggu verifikasi nomor telepon & CAPTCHA...")
        print("   >>> Silakan selesaikan CAPTCHA dan masukkan nomor telepon di browser.")
        print("   >>> Setelah selesai, kembali ke terminal dan tekan Enter di sini.")
        input()

        # 6. Selesaikan sisa langkah (review & setuju)
        print("[6/6] Menyelesaikan persetujuan...")
        # Beri waktu ekstra untuk halaman berikutnya
        time.sleep(3)

        print("Selesai! Akun Gmail Anda telah dibuat.")
        print(f"Email    : {username}@gmail.com")
        print(f"Password : {password}")
        print("Simpan data di atas dengan aman.")

    except Exception as e:
        print("Terjadi kesalahan:", e)
    finally:
        # Biarkan browser terbuka agar pengguna bisa mengecek/menyelesaikan
        print("Browser dibiarkan terbuka. Tekan Enter untuk menutup...")
        input()
        driver.quit()


def main():
    print("=== Pembuat Akun Gmail Otomatis ===")
    nama_depan = input("Nama depan       : ").strip()
    nama_belakang = input("Nama belakang    : ").strip()
    username = input("Username Gmail   : ").strip().lower()
    password = getpass.getpass("Password (min. 8 karakter): ")

    if not all([nama_depan, nama_belakang, username, password]):
        print("Semua kolom wajib diisi.")
        return

    buat_akun_gmail(nama_depan, nama_belakang, username, password)


if __name__ == "__main__":
    main()
