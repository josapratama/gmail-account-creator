"""
Modul manajemen proxy: rotasi proxy otomatis.
- Jika MANUAL_PROXY diisi, gunakan itu.
- Jika tidak, ambil proxy gratis dari FreeProxy (free-proxy library).

Catatan: Chrome 137+ tidak mendukung autentikasi proxy via extension maupun
flag --proxy-server=user:pass@host:port. Solusi: jalankan local proxy (proxy.py)
di localhost yang forward ke upstream proxy dengan credential. Chrome connect ke
localhost tanpa auth, local proxy yang handle autentikasi ke upstream.
"""
import os
import random
import socket
import subprocess
import sys
import time
from typing import Optional, Tuple

import config


def _parse_proxy(proxy_str: str) -> Tuple[str, str, str, str]:
    """
    Parse proxy string ke komponen (host, port, user, password).
    Format yang didukung:
      - host:port
      - user:pass@host:port
      - http://user:pass@host:port
    """
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


def _cari_port_bebas() -> int:
    """Mencari port localhost yang bebas."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# Process local proxy yang sedang berjalan
_local_proxy_proc = None
_local_proxy_port = None


def mulai_local_proxy(proxy_str: str) -> Optional[str]:
    """
    Menjalankan local HTTP proxy di localhost yang mem-forward ke upstream proxy
    dengan autentikasi. Menggunakan threading + http.server Python stdlib.

    Mengembalikan "127.0.0.1:port" jika berhasil, None jika gagal.
    """
    global _local_proxy_proc, _local_proxy_port

    host, port, user, password = _parse_proxy(proxy_str)
    if not user or not password:
        return None

    hentikan_local_proxy()

    local_port = _cari_port_bebas()

    # Buat script proxy forwarder sebagai file temp
    import base64
    import tempfile

    auth_b64 = base64.b64encode(f"{user}:{password}".encode()).decode()

    script = f"""
import socket, threading, base64, sys

UPSTREAM_HOST = "{host}"
UPSTREAM_PORT = {port}
PROXY_AUTH = "{auth_b64}"
LOCAL_PORT = {local_port}

def handle(conn, addr):
    try:
        data = b""
        while True:
            chunk = conn.recv(4096)
            if not chunk:
                break
            data += chunk
            if b"\\r\\n\\r\\n" in data:
                break

        if not data:
            conn.close()
            return

        upstream = socket.create_connection((UPSTREAM_HOST, UPSTREAM_PORT), timeout=30)

        # Inject Proxy-Authorization header
        lines = data.split(b"\\r\\n")
        new_lines = []
        for line in lines:
            if line.lower().startswith(b"proxy-authorization:"):
                continue
            new_lines.append(line)
        # Insert auth header setelah baris pertama (request line)
        if len(new_lines) > 1:
            new_lines.insert(1, f"Proxy-Authorization: Basic {{PROXY_AUTH}}".encode())
        data = b"\\r\\n".join(new_lines)

        upstream.sendall(data)

        def relay(src, dst):
            try:
                while True:
                    d = src.recv(8192)
                    if not d:
                        break
                    dst.sendall(d)
            except:
                pass
            finally:
                try: src.close()
                except: pass
                try: dst.close()
                except: pass

        t = threading.Thread(target=relay, args=(upstream, conn), daemon=True)
        t.start()
        relay(conn, upstream)
    except Exception as e:
        try: conn.close()
        except: pass

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind(("127.0.0.1", LOCAL_PORT))
server.listen(50)

while True:
    try:
        conn, addr = server.accept()
        t = threading.Thread(target=handle, args=(conn, addr), daemon=True)
        t.start()
    except:
        break
"""

    # Tulis script ke file temp
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, prefix="proxy_fwd_"
    )
    tmp.write(script)
    tmp.flush()
    tmp.close()

    try:
        proc = subprocess.Popen(
            [sys.executable, tmp.name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )

        # Tunggu proxy siap (maks 5 detik)
        for _ in range(10):
            time.sleep(0.5)
            try:
                with socket.create_connection(("127.0.0.1", local_port), timeout=1):
                    _local_proxy_proc = proc
                    _local_proxy_port = local_port
                    # Simpan path file temp untuk cleanup
                    _local_proxy_proc._tmp_script = tmp.name
                    print(f"[PROXY] Local forwarder berjalan di 127.0.0.1:{local_port} -> {host}:{port}")
                    return f"127.0.0.1:{local_port}"
            except Exception:
                continue

        proc.kill()
        os.unlink(tmp.name)
        print("[PROXY] Local proxy gagal start (timeout)")
        return None

    except Exception as e:
        print(f"[PROXY] Gagal menjalankan local proxy: {e}")
        try:
            os.unlink(tmp.name)
        except Exception:
            pass
        return None


def hentikan_local_proxy():
    """Menghentikan local proxy subprocess jika berjalan."""
    global _local_proxy_proc, _local_proxy_port
    if _local_proxy_proc:
        try:
            _local_proxy_proc.terminate()
            _local_proxy_proc.wait(timeout=3)
        except Exception:
            try:
                _local_proxy_proc.kill()
            except Exception:
                pass
        # Hapus script temp jika ada
        try:
            tmp = getattr(_local_proxy_proc, "_tmp_script", None)
            if tmp and os.path.exists(tmp):
                os.unlink(tmp)
        except Exception:
            pass
        _local_proxy_proc = None
        _local_proxy_port = None
        print("[PROXY] Local proxy dihentikan.")


def ambil_proxy() -> Optional[str]:
    """
    Mengembalikan string proxy yang siap dipakai Chrome.
    - Jika proxy punya auth, jalankan local proxy dan return 127.0.0.1:port
    - Jika tidak ada auth, return host:port langsung
    - Return None jika proxy tidak dikonfigurasi
    """
    raw_proxy = None

    if config.MANUAL_PROXY:
        raw_proxy = config.MANUAL_PROXY
        print(f"[PROXY] Proxy manual: {raw_proxy}")
    elif config.USE_PROXY:
        try:
            from fp.fp import FreeProxy
            print("[PROXY] Mengambil proxy dari FreeProxy...")
            raw_proxy = FreeProxy(timeout=1).get()
            raw_proxy = raw_proxy.replace("http://", "").replace("https://", "")
            print(f"[PROXY] Proxy didapat: {raw_proxy}")
        except ImportError:
            print("[PROXY] Library 'free-proxy' belum terinstal.")
            return None
        except Exception as e:
            print(f"[PROXY] Gagal mengambil proxy: {e}")
            return None

    if not raw_proxy:
        return None

    # Jika proxy punya autentikasi, jalankan local proxy forwarder
    if "@" in raw_proxy:
        local = mulai_local_proxy(raw_proxy)
        if local:
            return local
        # Fallback: return raw proxy (akan muncul dialog auth)
        print("[PROXY] Fallback ke raw proxy (mungkin muncul dialog auth)")
        _, port, _, _ = _parse_proxy(raw_proxy)
        host_only = raw_proxy.rsplit("@", 1)[1]
        return host_only

    return raw_proxy


def acak_proxy_berikutnya() -> Optional[str]:
    """Mengambil proxy baru untuk rotasi per akun."""
    hentikan_local_proxy()
    return ambil_proxy()



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
