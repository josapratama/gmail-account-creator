"""
Modul integrasi SMS provider untuk verifikasi telepon virtual.

Provider yang didukung:
  1. 5sim.net      — dikonfigurasi via FIVESTIM_API_KEY
  2. sms-activate.org — dikonfigurasi via SMSACTIVATE_API_KEY

Urutan prioritas (bisa diatur via SMS_PROVIDER di .env):
  "5sim"        → hanya pakai 5SIM
  "smsactivate" → hanya pakai sms-activate
  "auto"        → coba 5SIM dulu, fallback ke sms-activate jika gagal/saldo habis
"""
import re
import time
from typing import Optional

import requests

import config


# ─────────────────────────────────────────────────────────────────────────────
# Helper bersama
# ─────────────────────────────────────────────────────────────────────────────

def _ekstrak_kode(teks_sms: str) -> str:
    """Mengekstrak kode angka 4–6 digit dari teks SMS."""
    cocok = re.search(r"\b(\d{4,6})\b", teks_sms)
    return cocok.group(1) if cocok else teks_sms


# ─────────────────────────────────────────────────────────────────────────────
# 5SIM Provider
# ─────────────────────────────────────────────────────────────────────────────

class FiveSimProvider:
    """Klien untuk layanan 5sim.net — menyewa nomor virtual & menerima SMS."""

    BASE_URL = "https://5sim.net/v1/user"

    def __init__(self, api_key: str = None):
        self.api_key = api_key or config.FIVESTIM_API_KEY
        if not self.api_key:
            raise ValueError("API key 5sim tidak ditemukan. Set FIVESTIM_API_KEY.")
        self.headers = {"Authorization": f"Bearer {self.api_key}"}

    def cek_balance(self) -> float:
        """Mengecek saldo akun 5sim."""
        resp = requests.get(f"{self.BASE_URL}/profile", headers=self.headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return float(data.get("balance", 0))

    def beli_nomor(self) -> dict:
        """
        Membeli nomor virtual untuk layanan Google.
        Mengembalikan dict dengan 'id' dan 'phone'.
        """
        negara = config.FIVESTIM_COUNTRY
        operator = config.FIVESTIM_OPERATOR
        produk = config.FIVESTIM_PRODUCT

        url = f"{self.BASE_URL}/buy/activation/{negara}/{operator}/{produk}"
        print(f"[5SIM] Membeli nomor ({negara}/{operator}/{produk})...")
        resp = requests.get(url, headers=self.headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        print(f"[5SIM] Nomor didapat: {data.get('phone')} (ID: {data.get('id')})")
        return data

    def tunggu_sms(self, order_id: int, timeout: int = None) -> Optional[str]:
        """
        Menunggu SMS masuk untuk order tertentu.
        Mengembalikan kode verifikasi atau None jika timeout.
        """
        timeout = timeout or config.SMS_TIMEOUT
        batas = time.time() + timeout
        print(f"[5SIM] Menunggu SMS (timeout {timeout}s)...")

        while time.time() < batas:
            resp = requests.get(
                f"{self.BASE_URL}/check/{order_id}",
                headers=self.headers,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            status = data.get("status")

            if status == "RECEIVED":
                sms = data.get("sms", [])
                if sms:
                    kode = _ekstrak_kode(sms[0].get("text", ""))
                    print(f"[5SIM] SMS diterima! Kode: {kode}")
                    return kode
            elif status in ("CANCELED", "TIMEOUT", "BANNED"):
                print(f"[5SIM] Order dibatalkan: {status}")
                return None

            time.sleep(3)

        print("[5SIM] Timeout menunggu SMS.")
        return None

    def selesaikan_order(self, order_id: int):
        """Menandai order selesai (FINISH) setelah kode dipakai."""
        try:
            requests.get(
                f"{self.BASE_URL}/finish/{order_id}",
                headers=self.headers,
                timeout=10,
            )
        except Exception:
            pass

    def batalkan_order(self, order_id: int):
        """Membatalkan order jika gagal."""
        try:
            requests.get(
                f"{self.BASE_URL}/cancel/{order_id}",
                headers=self.headers,
                timeout=10,
            )
        except Exception:
            pass

    @staticmethod
    def _ekstrak_kode(teks_sms: str) -> str:
        return _ekstrak_kode(teks_sms)


# ─────────────────────────────────────────────────────────────────────────────
# sms-activate.org Provider
# ─────────────────────────────────────────────────────────────────────────────

class SmsActivateProvider:
    """
    Klien untuk layanan sms-activate.org.
    Dokumentasi API: https://sms-activate.org/en/api2

    Nomor bersifat sekali pakai (1 nomor = 1 verifikasi), sama seperti 5SIM.
    """

    BASE_URL = "https://api.sms-activate.org/stubs/handler_api.php"

    # Kode layanan Google di sms-activate
    # Lihat daftar lengkap: https://sms-activate.org/en/api2#getServices
    SERVICE_CODE = "go"   # "go" = Google / Gmail

    def __init__(self, api_key: str = None):
        self.api_key = api_key or config.SMSACTIVATE_API_KEY
        if not self.api_key:
            raise ValueError(
                "API key sms-activate tidak ditemukan. Set SMSACTIVATE_API_KEY di .env"
            )

    def _get(self, params: dict) -> str:
        """Melakukan GET request ke API sms-activate dan mengembalikan teks respons."""
        params["api_key"] = self.api_key
        resp = requests.get(self.BASE_URL, params=params, timeout=20)
        resp.raise_for_status()
        return resp.text.strip()

    def cek_balance(self) -> float:
        """Mengecek saldo akun sms-activate (dalam USD)."""
        hasil = self._get({"action": "getBalance"})
        # Respons: "ACCESS_BALANCE:12.50"
        if "ACCESS_BALANCE:" in hasil:
            try:
                return float(hasil.split(":")[1])
            except Exception:
                pass
        raise ValueError(f"Respons saldo tidak valid: {hasil}")

    def beli_nomor(self) -> dict:
        """
        Menyewa nomor virtual untuk Google.
        Mengembalikan dict dengan 'id' dan 'phone'.

        Negara diambil dari SMSACTIVATE_COUNTRY di .env.
        Kode negara: https://sms-activate.org/en/api2#getNumberV2
          0  = Rusia, 6  = Indonesia, 12 = USA, 16 = UK, dll
        """
        negara_kode = config.SMSACTIVATE_COUNTRY_CODE
        print(f"[SMSACT] Membeli nomor (negara={negara_kode}, service={self.SERVICE_CODE})...")
        hasil = self._get({
            "action": "getNumber",
            "service": self.SERVICE_CODE,
            "country": negara_kode,
        })
        # Respons sukses: "ACCESS_NUMBER:12345678:628123456789"
        # id_order = 12345678, nomor = 628123456789
        if hasil.startswith("ACCESS_NUMBER:"):
            bagian = hasil.split(":")
            order_id = int(bagian[1])
            nomor = "+" + bagian[2]
            print(f"[SMSACT] Nomor didapat: {nomor} (ID: {order_id})")
            return {"id": order_id, "phone": nomor}

        # Penanganan error umum
        pesan_error = {
            "NO_NUMBERS":       "Tidak ada nomor tersedia untuk layanan/negara ini.",
            "NO_BALANCE":       "Saldo sms-activate tidak cukup.",
            "BAD_SERVICE":      f"Kode layanan tidak valid: {self.SERVICE_CODE}",
            "BAD_KEY":          "API key sms-activate tidak valid.",
            "ERROR_SQL":        "Error internal sms-activate.",
            "BAD_ACTION":       "Aksi API tidak dikenal.",
        }
        raise RuntimeError(
            f"sms-activate getNumber gagal: {hasil} — "
            f"{pesan_error.get(hasil, 'Error tidak dikenal')}"
        )

    def tunggu_sms(self, order_id: int, timeout: int = None) -> Optional[str]:
        """
        Polling status order hingga SMS diterima atau timeout.
        Mengembalikan kode verifikasi atau None.
        """
        timeout = timeout or config.SMS_TIMEOUT
        batas = time.time() + timeout
        print(f"[SMSACT] Menunggu SMS (timeout {timeout}s)...")

        # Set status = 1 (menunggu SMS) agar nomor tidak expire
        try:
            self._get({"action": "setStatus", "id": order_id, "status": "1"})
        except Exception:
            pass

        while time.time() < batas:
            hasil = self._get({"action": "getStatus", "id": order_id})

            if hasil.startswith("STATUS_OK:"):
                # SMS diterima
                teks_sms = hasil.split(":", 1)[1]
                kode = _ekstrak_kode(teks_sms)
                print(f"[SMSACT] SMS diterima! Kode: {kode}")
                return kode

            elif hasil == "STATUS_WAIT_CODE":
                # Masih menunggu SMS
                pass

            elif hasil == "STATUS_WAIT_RETRY":
                # SMS masuk tapi kode salah, minta kirim ulang
                print("[SMSACT] Minta kirim ulang SMS...")
                try:
                    self._get({"action": "setStatus", "id": order_id, "status": "3"})
                except Exception:
                    pass

            elif hasil in ("STATUS_CANCEL", "STATUS_WAIT_RESEND"):
                print(f"[SMSACT] Order selesai/dibatalkan: {hasil}")
                return None

            time.sleep(3)

        print("[SMSACT] Timeout menunggu SMS.")
        return None

    def selesaikan_order(self, order_id: int):
        """Tandai order selesai (status=6) setelah kode berhasil dipakai."""
        try:
            self._get({"action": "setStatus", "id": order_id, "status": "6"})
        except Exception:
            pass

    def batalkan_order(self, order_id: int):
        """Batalkan order (status=8) jika nomor tidak terpakai."""
        try:
            self._get({"action": "setStatus", "id": order_id, "status": "8"})
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────────────────────
# Factory — pilih provider berdasarkan konfigurasi
# ─────────────────────────────────────────────────────────────────────────────

def buat_sms_provider():
    """
    Mengembalikan provider SMS yang siap dipakai berdasarkan SMS_PROVIDER di .env.

    Nilai SMS_PROVIDER:
      "5sim"        → FiveSimProvider (wajib FIVESTIM_API_KEY)
      "smsactivate" → SmsActivateProvider (wajib SMSACTIVATE_API_KEY)
      "auto"        → coba 5SIM dulu; jika tidak ada key/saldo, pakai sms-activate
    """
    pilihan = config.SMS_PROVIDER.lower().strip()

    if pilihan == "5sim":
        return FiveSimProvider()

    if pilihan == "smsactivate":
        return SmsActivateProvider()

    # Mode "auto": coba 5SIM → fallback sms-activate
    if config.FIVESTIM_API_KEY:
        try:
            p = FiveSimProvider()
            saldo = p.cek_balance()
            if saldo >= 0.10:
                print(f"[SMS] Pakai 5SIM (saldo: ${saldo:.2f})")
                return p
            print(f"[SMS] Saldo 5SIM terlalu rendah (${saldo:.2f}), coba sms-activate...")
        except Exception as e:
            print(f"[SMS] 5SIM tidak tersedia ({e}), coba sms-activate...")

    if config.SMSACTIVATE_API_KEY:
        try:
            p = SmsActivateProvider()
            saldo = p.cek_balance()
            if saldo >= 0.10:
                print(f"[SMS] Pakai sms-activate (saldo: ${saldo:.2f})")
                return p
            print(f"[SMS] Saldo sms-activate terlalu rendah (${saldo:.2f})")
        except Exception as e:
            print(f"[SMS] sms-activate tidak tersedia ({e})")

    raise RuntimeError(
        "Tidak ada provider SMS yang tersedia. "
        "Set FIVESTIM_API_KEY atau SMSACTIVATE_API_KEY di .env"
    )
