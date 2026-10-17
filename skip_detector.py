"""
Modul deteksi tombol Skip: mencari & mengklik tombol Skip/lewati
di berbagai bahasa (EN, AR, ID, dll).
"""
import time

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from config import SKIP_KEYWORDS


def cari_dan_klik_skip(driver: webdriver.Chrome, timeout: int = 10) -> bool:
    """
    Mencari tombol Skip di halaman saat ini dan mengkliknya jika ditemukan.
    Mendukung berbagai bahasa. Mengembalikan True jika berhasil.
    """
    print("[SKIP] Mencari tombol Skip...")
    batas_waktu = time.time() + timeout

    while time.time() < batas_waktu:
        # Cari semua tombol & link di halaman
        elemen = driver.find_elements(By.XPATH, "//button | //a | //span[@role='button'] | //div[@role='button']")
        for el in elemen:
            try:
                teks = (el.text or "").strip().lower()
                if not teks:
                    continue
                for kata in SKIP_KEYWORDS:
                    if kata.lower() in teks and len(teks) < 40:
                        # Pastikan elemen terlihat & bisa diklik
                        if el.is_displayed() and el.is_enabled():
                            print(f"[SKIP] Menemukan tombol: '{el.text.strip()}' -> Mengklik...")
                            try:
                                el.click()
                            except Exception:
                                driver.execute_script("arguments[0].click();", el)
                            time.sleep(1.5)
                            return True
            except Exception:
                continue
        time.sleep(0.5)

    print("[SKIP] Tombol Skip tidak ditemukan.")
    return False


def cek_halaman_verifikasi_telepon(driver: webdriver.Chrome) -> bool:
    """
    Mengecek apakah halaman saat ini adalah halaman verifikasi telepon.
    Termasuk halaman QR code (Google sekarang menampilkan QR dulu sebelum
    opsi input nomor telepon).
    """
    # Cek URL: mophoneverification = mobile phone verification (QR / SMS)
    try:
        url = driver.current_url.lower()
        if "mophneverification" in url or "phoneverification" in url:
            return True
    except Exception:
        pass

    # Cari input phone number
    try:
        driver.find_element(By.XPATH, "//input[@type='tel']")
        return True
    except Exception:
        pass

    # Cek teks "phone", "telepon", atau QR di halaman
    try:
        body = driver.find_element(By.TAG_NAME, "body").text.lower()
        kata_kunci = [
            "phone", "telepon", "nomor ponsel", "mobile", "verification",
            "qr code", "scan the qr", "verify some info",
        ]
        return any(k in body for k in kata_kunci)
    except Exception:
        return False


def cek_halaman_qr(driver: webdriver.Chrome) -> bool:
    """
    Mengecek apakah halaman saat ini adalah halaman QR code verifikasi
    (belum ada input nomor telepon). Mengembalikan True jika QR terdeteksi
    dan tidak ada input tel yang terlihat.

    Deteksi memakai tiga sumber: teks QR, elemen gambar/kanvas QR, dan
    konteks URL challenge. Jika ada input nomor telepon yang terlihat,
    halaman dianggap BUKAN halaman QR.
    """
    # Jika ada input nomor telepon yang terlihat -> bukan halaman QR
    try:
        for inp in driver.find_elements(By.XPATH, "//input[@type='tel']"):
            if inp.is_displayed():
                return False
    except Exception:
        pass

    # 1. Cek teks QR di body
    ada_qr_teks = False
    try:
        body = driver.find_element(By.TAG_NAME, "body").text.lower()
        qr_keywords = [
            "qr code", "scan the qr", "scan the code", "scan this qr",
            "scan to verify", "pindai kode qr", "pindai qr", "verify some info",
        ]
        ada_qr_teks = any(k in body for k in qr_keywords)
    except Exception:
        pass

    # 2. Cek elemen gambar/kanvas QR
    ada_qr_gambar = False
    try:
        imgs = driver.find_elements(
            By.XPATH,
            "//img[contains(@src,'qr') or contains(@alt,'QR') or contains(@alt,'qr')] | //canvas",
        )
        for im in imgs:
            if im.is_displayed():
                ada_qr_gambar = True
                break
    except Exception:
        pass

    # 3. Konteks URL halaman challenge/verifikasi Google
    url_hint = False
    try:
        url = driver.current_url.lower()
        url_hint = (
            "mophneverification" in url
            or "phoneverification" in url
            or "challenge" in url
        )
    except Exception:
        pass

    return ada_qr_teks or (ada_qr_gambar and url_hint)


def cek_halaman_error(driver: webdriver.Chrome) -> bool:
    """
    Mengecek apakah halaman saat ini adalah halaman error Google
    (mis. "Sorry, we could not create your Google Account").
    """
    try:
        url = driver.current_url.lower()
        if "/error" in url or "signup/error" in url:
            return True
    except Exception:
        pass

    try:
        body = driver.find_element(By.TAG_NAME, "body").text.lower()
        error_keywords = [
            "sorry, we could not create",
            "could not create your google account",
            "we couldn't create",
            "tidak dapat membuat",
            "gagal membuat",
            "something went wrong",
            "ada yang salah",
            "couldn't find this account",
            "could not find your account",
            "isn't signed in",
            "choose an account",
            "sign in to chrome",
        ]
        # Cek heading/h1 yang mengandung "Error"
        try:
            h1 = driver.find_element(By.TAG_NAME, "h1").text.lower()
            if "error" in h1:
                return True
        except Exception:
            pass
        return any(kw in body for kw in error_keywords)
    except Exception:
        return False


def cek_halaman_sukses(driver: webdriver.Chrome) -> bool:
    """
    Mengecek apakah halaman saat ini menunjukkan pendaftaran berhasil
    (welcome page, myaccount, atau halaman selamat datang).

    PENTING: Harus memastikan BUKAN halaman verifikasi telepon, signin, atau error.
    Halaman signin (accounts.google.com/signin) BUKAN halaman sukses — itu hanya
    halaman login yang muncul saat akun tidak ada / belum dibuat.
    """
    try:
        url = driver.current_url.lower()
        # Pastikan BUKAN halaman verifikasi telepon
        if "mophneverification" in url or "phoneverification" in url:
            return False
        # Pastikan BUKAN halaman signin/login (bukan indikator sukses)
        if "signin" in url or "identifier" in url or "challenge" in url:
            return False
    except Exception:
        pass

    # Pastikan BUKAN halaman error
    if cek_halaman_error(driver):
        return False

    try:
        url = driver.current_url.lower()
        success_url_keywords = [
            "myaccount.google.com",
            "accounts.google.com/manageaccount",
            "welcome",
        ]
        if any(kw in url for kw in success_url_keywords) and "error" not in url:
            # Pastikan bukan halaman signup yang masih berjalan
            if "signup" not in url and "challenge" not in url and "signin" not in url:
                return True
    except Exception:
        pass

    try:
        body = driver.find_element(By.TAG_NAME, "body").text.lower()
        success_keywords = [
            "welcome to your google account",
            "your google account is ready",
            "account created",
            "akun berhasil dibuat",
            "selamat datang",
        ]
        return any(kw in body for kw in success_keywords)
    except Exception:
        return False
