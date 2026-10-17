"""
Modul manajemen proxy: rotasi proxy otomatis.
- Jika MANUAL_PROXY diisi, gunakan itu.
- Jika tidak, ambil proxy gratis dari FreeProxy (free-proxy library).
"""
import random
from typing import Optional

import config


def ambil_proxy() -> Optional[str]:
    """
    Mengembalikan string proxy dalam format "host:port".
    Mengembalikan None jika proxy tidak digunakan atau tidak tersedia.
    """
    # 1. Cek proxy manual
    if config.MANUAL_PROXY:
        print(f"[PROXY] Menggunakan proxy manual: {config.MANUAL_PROXY}")
        return config.MANUAL_PROXY

    # 2. Jika USE_PROXY aktif, ambil dari FreeProxy
    if config.USE_PROXY:
        try:
            from fp.fp import FreeProxy
            print("[PROXY] Mengambil proxy dari FreeProxy...")
            proxy = FreeProxy(timeout=1).get()
            # FreeProxy mengembalikan "http://host:port"
            proxy = proxy.replace("http://", "").replace("https://", "")
            print(f"[PROXY] Proxy didapat: {proxy}")
            return proxy
        except ImportError:
            print("[PROXY] Library 'free-proxy' belum terinstal. Jalankan: pip install free-proxy")
            return None
        except Exception as e:
            print(f"[PROXY] Gagal mengambil proxy: {e}")
            return None

    return None


def acak_proxy_berikutnya() -> Optional[str]:
    """Mengambil proxy baru untuk rotasi per akun."""
    return ambil_proxy()
