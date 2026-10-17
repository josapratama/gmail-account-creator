#!/usr/bin/env python3
"""
Gmail Account Creator - Entry Point CLI.

Fitur:
  - Anti-detection (stealth JS, random UA, human-like typing)
  - Session warming
  - Auto-detect tombol Skip (multi-bahasa)
  - Integrasi 5sim API untuk nomor virtual
  - Proxy rotation otomatis

Cara pakai:
  python main.py

Environment variables opsional:
  FIVESTIM_API_KEY   - API key 5sim.net (untuk verifikasi telepon otomatis)
  USE_PROXY=true     - Aktifkan proxy gratis dari FreeProxy
  MANUAL_PROXY=host:port - Proxy manual
  HEADLESS=true      - Mode headless (tanpa jendela browser)
  KEEP_BROWSER_OPEN=true - Biarkan browser terbuka setelah akun selesai (debugging)
  WARMUP_PAGES=3     - Jumlah halaman pemanasan sesi
"""
import sys
import getpass
import random
import string

from account_creator import GmailCreator, Akun


def generate_username(panjang: int = 12) -> str:
    """Membuat username acak yang realistis."""
    nama_awal = random.choice([
        "john", "alex", "maria", "david", "sarah", "michael", "emma",
        "daniel", "olivia", "james", "sofia", "andrew", "isabella",
        "budi", "siti", "andi", "dewi", "rani", "agus", "wati",
    ])
    angka = "".join(random.choices(string.digits, k=random.randint(3, 6)))
    return f"{nama_awal}{angka}"


def generate_password(panjang: int = 16) -> str:
    """Membuat password kuat acak."""
    chars = string.ascii_letters + string.digits + "!@#$%&"
    # Pastikan ada minimal 1 huruf besar, kecil, angka, dan simbol
    pw = [
        random.choice(string.ascii_uppercase),
        random.choice(string.ascii_lowercase),
        random.choice(string.digits),
        random.choice("!@#$%&"),
    ]
    pw += random.choices(chars, k=panjang - 4)
    random.shuffle(pw)
    return "".join(pw)


def banner():
    print("=" * 60)
    print("        GMAIL ACCOUNT CREATOR (Auto + Anti-Detect)")
    print("=" * 60)
    print("Fitur: Stealth | Human Typing | Auto-Skip | 5SIM | Proxy")
    print("=" * 60)
    print()


def main():
    banner()

    print("Pilih mode:")
    print("  1. Buat 1 akun (input manual)")
    print("  2. Buat 1 akun (data acak otomatis)")
    print("  3. Buat beberapa akun otomatis (bulk)")
    pilihan = input("Masukkan pilihan [1/2/3]: ").strip()

    creator = GmailCreator()

    if pilihan == "1":
        nama_depan = input("Nama depan      : ").strip()
        nama_belakang = input("Nama belakang   : ").strip()
        username = input("Username Gmail  : ").strip().lower().replace("@gmail.com", "")
        password = getpass.getpass("Password        : ")
        akun = Akun(
            nama_depan=nama_depan,
            nama_belakang=nama_belakang,
            email=f"{username}@gmail.com",
            password=password,
        )
        creator.buat_akun(akun)

    elif pilihan == "2":
        nama_depan_list = ["John", "Alex", "David", "Michael", "Daniel", "Budi", "Andi", "Agus"]
        nama_belakang_list = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Santoso", "Wijaya", "Putra"]
        akun = Akun(
            nama_depan=random.choice(nama_depan_list),
            nama_belakang=random.choice(nama_belakang_list),
            email=f"{generate_username()}@gmail.com",
            password=generate_password(),
        )
        print(f"\nData akun yang akan dibuat:")
        print(f"  Nama     : {akun.nama_depan} {akun.nama_belakang}")
        print(f"  Email    : {akun.email}")
        print(f"  Password : {akun.password}")
        print()
        input("Tekan Enter untuk memulai...")
        creator.buat_akun(akun)

    elif pilihan == "3":
        jumlah = int(input("Jumlah akun yang ingin dibuat: ").strip())
        for i in range(jumlah):
            print(f"\n{'=' * 50}")
            print(f"Membuat akun ke-{i + 1}/{jumlah}")
            print(f"{'=' * 50}")
            nama_depan_list = ["John", "Alex", "David", "Michael", "Daniel", "Budi", "Andi"]
            nama_belakang_list = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Santoso"]
            akun = Akun(
                nama_depan=random.choice(nama_depan_list),
                nama_belakang=random.choice(nama_belakang_list),
                email=f"{generate_username()}@gmail.com",
                password=generate_password(),
            )
            print(f"  Email    : {akun.email}")
            print(f"  Password : {akun.password}")
            sukses = creator.buat_akun(akun)
            if not sukses:
                print(f"  [!] Akun ke-{i + 1} gagal. Lanjut ke akun berikutnya...")
            # Jeda antar akun agar tidak terdeteksi
            import time
            waktu_tunggu = random.randint(10, 30)
            print(f"  Menunggu {waktu_tunggu} detik sebelum akun berikutnya...")
            time.sleep(waktu_tunggu)
    else:
        print("Pilihan tidak valid.")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nDibatalkan oleh pengguna.")
        sys.exit(0)
