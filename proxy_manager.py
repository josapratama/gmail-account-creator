"""
Modul manajemen proxy: rotasi proxy otomatis.

Chrome 137+ tidak mendukung autentikasi proxy via extension maupun flag
--proxy-server=user:pass@host:port. Solusi: jalankan local HTTP proxy
(Python stdlib, zero extra dependencies) di localhost yang inject header
Proxy-Authorization ke upstream proxy secara transparan.

Alur:
  Chrome -> 127.0.0.1:LOCAL_PORT (local forwarder, tanpa auth)
                -> v2.proxyempire.io:5000 (upstream, inject Proxy-Authorization)
"""
import os
import socket
import subprocess
import sys
import tempfile
import time
from typing import Optional, Tuple

import config


# ─── Proses local proxy yang sedang berjalan ─────────────────────────────────
_local_proxy_proc = None
_local_proxy_port = None


def _parse_proxy(proxy_str: str) -> Tuple[str, str, str, str]:
    """
    Parse proxy string ke (host, port, user, password).
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


def mulai_local_proxy(proxy_str: str) -> Optional[str]:
    """
    Menjalankan local HTTP proxy di localhost yang mem-forward ke upstream proxy
    dengan autentikasi. Menggunakan threading + socket Python stdlib.

    Mengembalikan "127.0.0.1:port" jika berhasil, None jika gagal.
    Chrome connect ke local proxy ini tanpa perlu credential.
    """
    global _local_proxy_proc, _local_proxy_port

    host, port, user, password = _parse_proxy(proxy_str)
    if not user or not password:
        return None

    hentikan_local_proxy()

    local_port = _cari_port_bebas()

    import base64
    auth_b64 = base64.b64encode(f"{user}:{password}".encode()).decode()

    script = f"""
import socket, threading, base64

UPSTREAM_HOST = "{host}"
UPSTREAM_PORT = {port}
PROXY_AUTH = "{auth_b64}"
LOCAL_PORT = {local_port}

def handle(conn):
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

        lines = data.split(b"\\r\\n")
        new_lines = []
        has_auth = False
        for line in lines:
            if line.lower().startswith(b"proxy-authorization:"):
                has_auth = True
            new_lines.append(line)
        if not has_auth and len(new_lines) > 1:
            new_lines.insert(1, ("Proxy-Authorization: Basic " + PROXY_AUTH).encode())
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
    except:
        try: conn.close()
        except: pass

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind(("127.0.0.1", LOCAL_PORT))
server.listen(100)
while True:
    try:
        conn, addr = server.accept()
        threading.Thread(target=handle, args=(conn,), daemon=True).start()
    except:
        break
"""

    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, prefix="proxy_fwd_"
    )
    tmp.write(script)
    tmp.flush()
    tmp.close()

    try:
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        proc = subprocess.Popen(
            [sys.executable, tmp.name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=flags,
        )

        # Tunggu proxy siap (maks 5 detik)
        for _ in range(10):
            time.sleep(0.5)
            try:
                with socket.create_connection(("127.0.0.1", local_port), timeout=1):
                    _local_proxy_proc = proc
                    _local_proxy_proc._tmp_script = tmp.name
                    _local_proxy_port = local_port
                    print(f"[PROXY] Local forwarder 127.0.0.1:{local_port} -> {host}:{port}")
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
        try:
            tmp = getattr(_local_proxy_proc, "_tmp_script", None)
            if tmp and os.path.exists(tmp):
                os.unlink(tmp)
        except Exception:
            pass
        _local_proxy_proc = None
        _local_proxy_port = None


def ambil_proxy() -> Optional[str]:
    """
    Mengembalikan string proxy yang siap dipakai Chrome (tanpa credential).
    - Proxy dengan auth  -> start local forwarder, return 127.0.0.1:port
    - Proxy tanpa auth   -> return host:port langsung
    - Tidak ada proxy    -> return None
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

    # Proxy dengan auth -> pakai local forwarder
    if "@" in raw_proxy:
        local = mulai_local_proxy(raw_proxy)
        if local:
            return local
        # Fallback jika local proxy gagal start
        print("[PROXY] Local forwarder gagal, fallback ke host:port (dialog auth mungkin muncul)")
        return raw_proxy.rsplit("@", 1)[1]

    return raw_proxy


def acak_proxy_berikutnya() -> Optional[str]:
    """Mengambil proxy baru untuk rotasi per akun."""
    hentikan_local_proxy()
    return ambil_proxy()
