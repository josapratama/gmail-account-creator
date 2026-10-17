"""
Modul integrasi 5sim API untuk verifikasi telepon virtual.
Dokumentasi: https://5sim.net/docs/
"""
import time
from typing import Optional

import requests

import config


class FiveSimProvider:
    """Klien untuk layanan 5sim.net - menyewa nomor virtual & menerima SMS."""

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
                    kode = self._ekstrak_kode(sms[0].get("text", ""))
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
        """Mengekstrak kode angka dari teks SMS (biasanya 4-6 digit)."""
        import re
        # Cari angka 4-6 digit
        cocok = re.search(r"\b(\d{4,6})\b", teks_sms)
        return cocok.group(1) if cocok else teks_sms
