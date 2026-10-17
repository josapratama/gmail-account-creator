"""
Modul manajemen proxy: rotasi proxy otomatis.
- Jika MANUAL_PROXY diisi, gunakan itu.
- Jika tidak, ambil proxy gratis dari FreeProxy (free-proxy library).

Catatan: Chrome tidak mendukung autentikasi proxy via --proxy-server=user:pass@host:port.
Untuk proxy dengan autentikasi, modul ini membuat Chrome extension sementara
yang meng-inject credential secara otomatis.
"""
import os
import random
import shutil
import tempfile
import zipfile
from typing import Optional, Tuple

import config


def _parse_proxy(proxy_str: str) -> Tuple[str, str, str, str]:
    """
    Parse proxy string ke komponen (host, port, user, password).
    Format yang didukung:
      - host:port                        (tanpa auth)
      - user:pass@host:port              (dengan auth)
      - http://user:pass@host:port       (dengan scheme)
    """
    # Hapus scheme
    proxy_str = proxy_str.replace("http://", "").replace("https://", "").replace("socks5://", "")

    user, password = "", ""
    if "@" in proxy_str:
        auth, hostport = proxy_str.rsplit("@", 1)
        if ":" in auth:
            user, password = auth.split(":", 1)
        else:
            user = auth
    else:
        hostport = proxy_str

    if ":" in hostport:
        host, port = hostport.rsplit(":", 1)
    else:
        host, port = hostport, "8080"

    return host.strip(), port.strip(), user.strip(), password.strip()


def buat_proxy_extension(proxy_str: str) -> Optional[str]:
    """
    Membuat Chrome extension sementara untuk autentikasi proxy.
    Diperlukan karena Chrome tidak mendukung user:pass di --proxy-server.

    Mengembalikan path ke direktori extension, atau None jika tidak perlu
    (proxy tanpa autentikasi).
    """
    host, port, user, password = _parse_proxy(proxy_str)

    if not user or not password:
        # Tidak perlu extension jika tidak ada autentikasi
        return None

    # Background script untuk intercept auth challenge
    background_js = f"""
var config = {{
    mode: "fixed_servers",
    rules: {{
        singleProxy: {{
            scheme: "http",
            host: "{host}",
            port: parseInt("{port}")
        }},
        bypassList: ["localhost", "127.0.0.1"]
    }}
}};

chrome.proxy.settings.set({{value: config, scope: "regular"}}, function() {{}});

function callbackFn(details) {{
    return {{
        authCredentials: {{
            username: "{user}",
            password: "{password}"
        }}
    }};
}}

chrome.webRequest.onAuthRequired.addListener(
    callbackFn,
    {{urls: ["<all_urls>"]}},
    ["blocking"]
);
"""

    manifest_json = """{
    "version": "1.0.0",
    "manifest_version": 2,
    "name": "Chrome Proxy Auth",
    "permissions": [
        "proxy",
        "tabs",
        "unlimitedStorage",
        "storage",
        "<all_urls>",
        "webRequest",
        "webRequestBlocking"
    ],
    "background": {
        "scripts": ["background.js"]
    },
    "minimum_chrome_version": "76.0.0"
}"""

    # Buat direktori temp untuk extension
    ext_dir = tempfile.mkdtemp(prefix="chrome_proxy_ext_")
    with open(os.path.join(ext_dir, "background.js"), "w") as f:
        f.write(background_js)
    with open(os.path.join(ext_dir, "manifest.json"), "w") as f:
        f.write(manifest_json)

    print(f"[PROXY] Extension autentikasi dibuat: {ext_dir}")
    return ext_dir


def ambil_proxy() -> Optional[str]:
    """
    Mengembalikan string proxy dalam format "user:pass@host:port".
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
