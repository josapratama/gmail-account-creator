"""
Konfigurasi untuk Gmail Account Creator.
Edit nilai di bawah sesuai kebutuhan, atau gunakan environment variable.
"""
import os

from dotenv import load_dotenv

# Load environment variables dari file .env di direktori yang sama dengan script ini
# (bukan dari current working directory, agar tetap berfungsi walau dijalankan dari folder lain)
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# ─── 5SIM API (untuk verifikasi telepon virtual) ───────────────────────
# Dapatkan API key di https://5sim.net
# Opsional: jika kosong, tool hanya akan mengandalkan tombol Skip.
FIVESTIM_API_KEY = os.getenv("FIVESTIM_API_KEY", "")

# Negara & layanan untuk 5sim
FIVESTIM_COUNTRY = os.getenv("FIVESTIM_COUNTRY", "indonesia")  # atau "usa", dll
FIVESTIM_OPERATOR = os.getenv("FIVESTIM_OPERATOR", "any")
FIVESTIM_PRODUCT = os.getenv("FIVESTIM_PRODUCT", "google")

# Batas waktu menunggu SMS (detik)
SMS_TIMEOUT = int(os.getenv("SMS_TIMEOUT", "120"))

# ─── PROXY ─────────────────────────────────────────────────────────────
# Gunakan proxy otomatis dari FreeProxy (gratis) atau daftar proxy manual.
# Set USE_PROXY = True untuk mengaktifkan rotasi proxy.
USE_PROXY = os.getenv("USE_PROXY", "false").lower() == "true"

# Proxy manual (opsional). Format: "host:port" atau "user:pass@host:port"
# Jika diisi, proxy ini yang dipakai (bukan FreeProxy).
MANUAL_PROXY = os.getenv("MANUAL_PROXY", "")

# ─── BROWSER ───────────────────────────────────────────────────────────
HEADLESS = os.getenv("HEADLESS", "false").lower() == "true"
# Apakah mode anti-detection diaktifkan (stealth JS, dll)
ANTI_DETECTION = os.getenv("ANTI_DETECTION", "true").lower() == "true"

# ─── BROWSER BEHAVIOR ──────────────────────────────────────────────────
# Apakah browser dibiarkan terbuka setelah akun selesai dibuat.
# False (default) = browser langsung ditutup, cocok untuk bulk mode.
# True = browser tetap terbuka sampai Ctrl+C, cocok untuk debugging.
KEEP_BROWSER_OPEN = os.getenv("KEEP_BROWSER_OPEN", "false").lower() == "true"

# ─── SESSION WARMING ───────────────────────────────────────────────────
# Jumlah halaman acak yang dikunjungi sebelum pendaftaran (untuk pemanasan)
WARMUP_PAGES = int(os.getenv("WARMUP_PAGES", "3"))

# ─── SKIP BUTTON ────────────────────────────────────────────────────────
# Kata kunci untuk mendeteksi tombol Skip di berbagai bahasa
SKIP_KEYWORDS = [
    "skip", "skip for now", "not now", "later",
    "تخطي", "Lewati", "lewati", "nanti saja",
    "跳过", "跳過", "saltar", "omitir",
    "ignorar", "passar", "pular", "Überspringen",
]

# ─── DATA DEFAULT ──────────────────────────────────────────────────────
# Tanggal lahir default (bisa di-override saat runtime)
DEFAULT_BIRTH_DAY = 15
DEFAULT_BIRTH_MONTH = 6  # Juni
DEFAULT_BIRTH_YEAR = 2000
DEFAULT_GENDER = 1  # 1 = Laki-laki, 2 = Perempuan, 3 = Tidak ingin menyebutkan, 4 = Kustom

# ─── FILE OUTPUT ────────────────────────────────────────────────────────
ACCOUNTS_FILE = os.path.join(os.path.dirname(__file__), "accounts.json")

# File log teks (append). Aman meski terminal ditutup / history hilang.
ACCOUNTS_LOG_FILE = os.path.join(os.path.dirname(__file__), "accounts.log")
