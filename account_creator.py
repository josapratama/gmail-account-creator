"""
Modul inti: logika pembuatan akun Gmail dengan anti-detection,
auto-skip, dan integrasi nomor virtual.
"""
import calendar
import json
import os
import random
import re
import string
import time
from dataclasses import dataclass, asdict

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

import config
from anti_detection import buat_chrome_options, terapkan_stealth, ketik_manusia, tunggu_acak
from session_warming import panaskan_sesi
from skip_detector import (
    cari_dan_klik_skip,
    cek_halaman_verifikasi_telepon,
    cek_halaman_error,
    cek_halaman_sukses,
    cek_halaman_qr,
)
from proxy_manager import ambil_proxy


@dataclass
class Akun:
    nama_depan: str
    nama_belakang: str
    email: str
    password: str
    nomor_telepon: str = ""
    sukses: bool = False


class GmailCreator:
    def __init__(self):
        self.driver = None

    def _bersihkan_proses_lama(self):
        """Membersihkan proses chromedriver yang tertinggal dari run sebelumnya."""
        try:
            import subprocess
            # Hanya kill chromedriver, JANGAN kill chrome (user mungkin punya browser terbuka)
            subprocess.run(
                ["taskkill", "/F", "/IM", "chromedriver.exe"],
                capture_output=True, timeout=5,
            )
        except Exception:
            pass

    def _buat_driver(self):
        proxy = ambil_proxy()
        opsi = buat_chrome_options(proxy)

        # Bersihkan chromedriver lama agar tidak konflik
        self._bersihkan_proses_lama()

        # Gunakan undetected-chromedriver untuk bypass deteksi bot Google
        try:
            import undetected_chromedriver as uc
            print("[*] Menggunakan undetected-chromedriver (anti-detection)...")

            driver = None
            for percobaan in range(3):
                try:
                    # Buat uc_options FRESH setiap percobaan (tidak bisa reuse)
                    uc_options = uc.ChromeOptions()
                    for arg in opsi.arguments:
                        uc_options.add_argument(arg)

                    if config.HEADLESS:
                        uc_options.add_argument("--headless=new")

                    # Argumen anti-detection tambahan
                    uc_options.add_argument("--disable-blink-features=AutomationControlled")
                    uc_options.add_argument("--no-sandbox")
                    uc_options.add_argument("--disable-dev-shm-usage")

                    driver = uc.Chrome(options=uc_options, version_main=None)
                    # Verifikasi jendela benar-benar terbuka
                    _ = driver.current_window_handle
                    break
                except Exception as e:
                    print(f"[!] Percobaan buat driver ke-{percobaan+1} gagal: {str(e).splitlines()[0]}")
                    if driver:
                        try:
                            driver.quit()
                        except Exception:
                            pass
                    driver = None
                    self._bersihkan_proses_lama()
                    time.sleep(2)

            if driver is None:
                raise Exception("Gagal membuat driver setelah 3 percobaan")

        except Exception as e:
            print(f"[!] undetected-chromedriver gagal ({e}), fallback ke Selenium biasa...")
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=opsi)
            if config.ANTI_DETECTION:
                terapkan_stealth(driver)

        # Timeout agar tidak menggantung selamanya
        driver.set_page_load_timeout(60)
        driver.set_script_timeout(30)

        self.driver = driver
        return driver

    def _tunggu_input(self, xpath, timeout=30):
        """Tunggu elemen muncul. Bisa menerima string tunggal atau list XPATH."""
        if isinstance(xpath, str):
            return WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.XPATH, xpath))
            )
        
        # Jika list, coba satu per satu
        elemen = None
        batas_waktu = time.time() + timeout
        while time.time() < batas_waktu:
            for xp in xpath:
                try:
                    el = self.driver.find_element(By.XPATH, xp)
                    if el.is_displayed():
                        return el
                except Exception:
                    continue
            time.sleep(0.5)
        
        raise Exception(f"Elemen dengan XPATH {xpath} tidak ditemukan setelah {timeout} detik")

    def _isi(self, target, teks, human_like=True, timeout=30):
        """Mengisi field teks. target bisa berupa WebElement, string XPATH, atau list XPATH."""
        el = None
        
        if hasattr(target, 'send_keys'):
            el = target
        elif isinstance(target, str):
            el = self._tunggu_input(target, timeout)
        elif isinstance(target, list):
            # Cari elemen dari list xpath
            for xp in target:
                try:
                    temp_el = self.driver.find_element(By.XPATH, xp)
                    if temp_el.is_displayed():
                        el = temp_el
                        break
                except Exception:
                    continue
            if not el:
                el = self._tunggu_input(target, timeout)
        else:
            raise Exception(f"Target pengisian tidak valid: {type(target)}")

        # Pastikan elemen terlihat dan scroll ke sana
        try:
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", el)
        except Exception:
            pass
        tunggu_acak(0.2, 0.4)
        
        # Klik dulu untuk fokus, lalu select all + hapus, baru ketik
        try:
            el.click()
        except Exception:
            self.driver.execute_script("arguments[0].click();", el)
        tunggu_acak(0.1, 0.3)
        
        # Select all dan hapus dengan berbagai cara agar bersih
        try:
            el.send_keys(Keys.CONTROL, "a")
            el.send_keys(Keys.BACKSPACE)
            el.send_keys(Keys.DELETE)
        except Exception:
            try:
                el.clear()
            except Exception:
                self.driver.execute_script("arguments[0].value = '';", el)
        
        tunggu_acak(0.1, 0.2)
        
        if human_like:
            ketik_manusia(el, teks)
        else:
            el.send_keys(teks)
        
        # Trigger event agar Google mendeteksi perubahan
        try:
            self.driver.execute_script(
                "arguments[0].dispatchEvent(new Event('input', {bubbles:true}));"
                "arguments[0].dispatchEvent(new Event('change', {bubbles:true}));"
                "arguments[0].dispatchEvent(new Event('blur', {bubbles:true}));",
                el,
            )
        except Exception:
            pass
        return el

    def _klik(self, xpath, timeout=30):
        """Klik elemen. Bisa menerima string tunggal atau list XPATH."""
        el = None
        if isinstance(xpath, str):
            el = WebDriverWait(self.driver, timeout).until(
                EC.element_to_be_clickable((By.XPATH, xpath))
            )
        else:
            # Jika list, coba satu per satu
            batas_waktu = time.time() + timeout
            while time.time() < batas_waktu:
                for xp in xpath:
                    try:
                        temp_el = self.driver.find_element(By.XPATH, xp)
                        if temp_el.is_displayed() and temp_el.is_enabled():
                            el = temp_el
                            break
                    except Exception:
                        continue
                if el:
                    break
                time.sleep(0.5)
            
            if not el:
                raise Exception(f"Tombol dengan XPATH {xpath} tidak ditemukan/tidak bisa diklik")

        try:
            el.click()
        except Exception:
            self.driver.execute_script("arguments[0].click();", el)
        return el

    def _klik_next_dan_tunggu(self, xpath, timeout=30):
        """Klik tombol Next lalu tunggu URL berubah (indikator halaman berpindah)."""
        url_awal = self.driver.current_url
        el = self._klik(xpath, timeout)
        # Tunggu URL berubah atau timeout
        try:
            WebDriverWait(self.driver, 15).until(
                lambda d: d.current_url != url_awal
            )
        except Exception:
            pass
        return el

    def _interaksi_manusia(self):
        """Meniru perilaku manusia: scroll acak + gerak mouse."""
        try:
            # Scroll acak
            scroll_y = random.randint(100, 400)
            self.driver.execute_script(f"window.scrollBy(0, {scroll_y});")
            tunggu_acak(0.2, 0.5)
            # Scroll kembali sedikit
            self.driver.execute_script(f"window.scrollBy(0, -{scroll_y // 2});")
            tunggu_acak(0.2, 0.5)
        except Exception:
            pass

    def _pilih_dropdown_google(self, container_xpath, nilai, opsi_teks=None):
        """
        Memilih dropdown Google yang bisa berupa native <select> atau custom <div>.
        Strategi:
          1. Coba native <select> di dalam container.
          2. Jika gagal, klik container (buka dropdown), lalu klik option yang cocok
             berdasarkan data-value / text / index.
          3. Fallback JS: set value langsung jika masih gagal.
        """
        opsi_teks = opsi_teks or []

        # 1. Coba native <select> di dalam container
        try:
            select_el = self._tunggu_input(f"{container_xpath}//select", timeout=5)
            # Coba beberapa format nilai (angka, string, case variations)
            nilai_str = str(nilai)
            kandidat = [nilai_str]
            if opsi_teks:
                kandidat += [t.lower() for t in opsi_teks] + [t.upper() for t in opsi_teks] + opsi_teks
            for val in kandidat:
                try:
                    Select(select_el).select_by_value(val)
                    tunggu_acak(0.2, 0.4)
                    return True
                except Exception:
                    continue
            # Fallback select by visible text
            for teks in opsi_teks:
                try:
                    Select(select_el).select_by_visible_text(teks)
                    tunggu_acak(0.2, 0.4)
                    return True
                except Exception:
                    continue
        except Exception:
            pass

        # 2. Fallback: custom div dropdown
        try:
            container = self._tunggu_input(container_xpath, timeout=10)

            # Cari elemen yang bisa diklik di dalam container
            klik_target = None
            for child_xpath in [
                ".//div[@role='button']",
                ".//*[@role='button']",
                ".//*[@tabindex]",
                ".//*[contains(@class,'VfPpkd')]",
                ".//span[contains(@class,'VfPpkd')]",
                "./*[1]",
            ]:
                try:
                    child = container.find_element(By.XPATH, child_xpath)
                    if child.is_displayed():
                        klik_target = child
                        break
                except Exception:
                    continue
            if klik_target is None:
                klik_target = container

            # Klik target (pakai JS jika normal click gagal)
            try:
                klik_target.click()
            except Exception:
                self.driver.execute_script("arguments[0].click();", klik_target)
            tunggu_acak(0.6, 1.2)

            def _klik_dengan_js(el):
                try:
                    el.click()
                except Exception:
                    self.driver.execute_script("arguments[0].click();", el)

            # Tunggu opsi muncul lalu cari semua opsi (coba beberapa selector)
            option_xpath_candidates = [
                "//div[@role='option' or @role='listitem']",
                "//li[@role='option' or @role='listitem']",
                "//*[@role='option']",
                "//div[contains(@class,'option')]",
                "//span[contains(@class,'option')]",
                "//div[contains(@class,'VfPpkd-StrnGf')]",
                "//li[contains(@class,'VfPpkd-StrnGf')]",
            ]

            options = []
            for oxp in option_xpath_candidates:
                try:
                    found = self.driver.find_elements(By.XPATH, oxp)
                    # Filter hanya yang terlihat
                    found = [o for o in found if o.is_displayed()]
                    if found:
                        options = found
                        break
                except Exception:
                    continue

            if not options:
                # Fallback: cari semua elemen yang bisa jadi opsi di halaman
                try:
                    WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.XPATH, "//*[@role='option']"))
                    )
                    options = self.driver.find_elements(By.XPATH, "//*[@role='option']")
                except Exception:
                    pass

            # 2a. Cocokkan berdasarkan data-value / value attribute
            for opt in options:
                val = opt.get_attribute("data-value") or opt.get_attribute("value") or ""
                if val and str(nilai) == val:
                    _klik_dengan_js(opt)
                    tunggu_acak(0.3, 0.5)
                    return True

            # 2b. Cocokkan berdasarkan teks (lebih longgar)
            if opsi_teks:
                for opt in options:
                    txt = (opt.text or "").strip().lower()
                    if not txt:
                        # Coba ambil teks dari child elements
                        try:
                            txt = (opt.find_element(By.XPATH, ".//span").text or "").strip().lower()
                        except Exception:
                            pass
                    for keyword in opsi_teks:
                        if txt and keyword.lower() in txt:
                            _klik_dengan_js(opt)
                            tunggu_acak(0.3, 0.5)
                            return True

            # 2c. Fallback: pakai index (sesuaikan jika ada placeholder di awal)
            try:
                idx = int(nilai)
            except (ValueError, TypeError):
                idx = 0
            if 0 <= idx < len(options):
                _klik_dengan_js(options[idx])
                tunggu_acak(0.3, 0.5)
                return True
        except Exception as e:
            print(f"   [!] Gagal memilih dropdown: {e}")

        # 3. Ultimate fallback: JS direct click on option by text
        try:
            if opsi_teks:
                js_text = opsi_teks[0]
                # Klik dropdown lagi untuk memastikan terbuka
                try:
                    container = self._tunggu_input(container_xpath, timeout=5)
                    self.driver.execute_script("arguments[0].click();", container)
                    tunggu_acak(0.5, 0.8)
                except Exception:
                    pass
                result = self.driver.execute_script(f"""
                    var opts = document.querySelectorAll('[role="option"], [role="listitem"], .VfPpkd-StrnGf');
                    for (var i = 0; i < opts.length; i++) {{
                        var t = (opts[i].textContent || '').trim().toLowerCase();
                        if (t.indexOf('{js_text.lower()}') !== -1) {{
                            opts[i].click();
                            return true;
                        }}
                    }}
                    return false;
                """)
                if result:
                    tunggu_acak(0.3, 0.5)
                    return True
        except Exception as e:
            print(f"   [!] JS fallback dropdown gagal: {e}")

        return False

    def _cek_gender_terpilih(self) -> bool:
        """Cek apakah gender sudah terpilih (tidak kosong/placeholder)."""
        try:
            # Cek native select value
            select_el = self.driver.find_elements(By.XPATH, '//*[@id="gender"]//select')
            if select_el:
                val = select_el[0].get_attribute("value")
                if val and val != "" and val.lower() not in ("", "placeholder", "select"):
                    return True
            # Cek teks pada custom dropdown (jangan kosong atau "Gender")
            gender_container = self.driver.find_elements(By.XPATH, '//*[@id="gender"]')
            if gender_container:
                txt = (gender_container[0].text or "").strip()
                # Placeholder biasanya "Gender" atau kosong
                if txt and txt.lower() not in ("gender", "select gender", "pilih gender", ""):
                    return True
        except Exception:
            pass
        return False

    def _pilih_gender_js(self, gender_val: int):
        """
        Fallback terakhir: pilih gender via JavaScript langsung.
        Mendukung native <select> dan custom dropdown.
        """
        gender_target = {
            1: ["male", "laki-laki", "laki laki"],
            2: ["female", "perempuan"],
            3: ["rather not say", "tidak ingin menyebutkan", "rather"],
            4: ["custom", "kustom"],
        }
        keywords = gender_target.get(gender_val, ["male"])

        try:
            result = self.driver.execute_script(f"""
                var keywords = {json.dumps(keywords)};
                // 1. Coba native select
                var sel = document.querySelector('#gender select');
                if (sel) {{
                    var opts = sel.options;
                    for (var i = 0; i < opts.length; i++) {{
                        var v = (opts[i].value || '').toLowerCase();
                        var t = (opts[i].text || '').toLowerCase();
                        for (var k = 0; k < keywords.length; k++) {{
                            if (v.indexOf(keywords[k]) !== -1 || t.indexOf(keywords[k]) !== -1) {{
                                sel.selectedIndex = i;
                                sel.dispatchEvent(new Event('change', {{bubbles: true}}));
                                sel.dispatchEvent(new Event('input', {{bubbles: true}}));
                                return 'select:' + opts[i].value;
                            }}
                        }}
                    }}
                }}
                // 2. Coba custom dropdown: klik trigger lalu klik option
                var trigger = document.querySelector('#gender [role="button"], #gender [tabindex], #gender .VfPpkd');
                if (trigger) trigger.click();
                return 'trigger-clicked';
            """)
            print(f"   [i] JS gender result: {result}")

            # Jika trigger diklik, tunggu opsi lalu klik
            if result == "trigger-clicked":
                tunggu_acak(0.6, 1.0)
                clicked = self.driver.execute_script(f"""
                    var keywords = {json.dumps(keywords)};
                    var opts = document.querySelectorAll('[role="option"], [role="listitem"], .VfPpkd-StrnGf');
                    for (var i = 0; i < opts.length; i++) {{
                        var t = (opts[i].textContent || '').trim().toLowerCase();
                        for (var k = 0; k < keywords.length; k++) {{
                            if (t.indexOf(keywords[k]) !== -1) {{
                                opts[i].click();
                                return 'option-clicked:' + t;
                            }}
                        }}
                    }}
                    return 'not-found';
                """)
                print(f"   [i] JS gender option: {clicked}")
        except Exception as e:
            print(f"   [!] JS gender error: {e}")

    def _input_username_dengan_retry(self, username_awal: str) -> str:
        """
        Mengisi username dengan retry jika username sudah diambil.
        Menangani juga pilihan radio button Google (Create your own Gmail address).
        """
        username = username_awal
        percobaan = 0
        maks_percobaan = 8

        while percobaan < maks_percobaan:
            percobaan += 1
            
            # 1. Cek apakah ada pilihan radio button "Create your own Gmail address"
            try:
                radio_keywords = ["create your own", "buat alamat gmail sendiri", "create a gmail address"]
                labels = self.driver.find_elements(By.TAG_NAME, "label")
                for label in labels:
                    txt = (label.text or "").lower()
                    if any(k in txt for k in radio_keywords):
                        print(f"   [i] Memilih opsi: '{label.text.strip()}'")
                        try:
                            label.click()
                        except Exception:
                            self.driver.execute_script("arguments[0].click();", label)
                        tunggu_acak(0.5, 1.0)
                        break
            except Exception:
                pass

            # 2. Cari field username
            el = None
            for user_xpath in [
                '//input[@name="Username"]',
                '//input[@aria-label="Username"]',
                '//input[@aria-label="Buat alamat Gmail"]',
                '//*[@id="username"]',
            ]:
                try:
                    el = WebDriverWait(self.driver, 8).until(
                        EC.presence_of_element_located((By.XPATH, user_xpath))
                    )
                    if el.is_displayed():
                        # Coba scroll dan klik untuk memastikan interaktif
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", el)
                        try:
                            el.click()
                        except Exception:
                            self.driver.execute_script("arguments[0].click();", el)
                        break
                except Exception:
                    continue
            
            if el is None:
                # Jika tidak ada field username, mungkin Google hanya memberi pilihan radio
                # Coba klik salah satu radio button saran sebagai fallback
                print("   [!] Field username tidak ditemukan, mencoba pilih saran Google...")
                try:
                    radios = self.driver.find_elements(By.XPATH, "//input[@type='radio']")
                    if radios:
                        # Pilih radio pertama yang bukan "Create your own" jika mungkin
                        for r in radios:
                            if r.is_displayed():
                                self.driver.execute_script("arguments[0].click();", r)
                                break
                        # Klik Next dan anggap berhasil
                        self._klik_next_username()
                        return "saran_google"
                except Exception:
                    pass
                raise Exception("Field username tidak ditemukan dan gagal pilih saran")

            # 3. Isi username menggunakan fungsi _isi yang sudah ditingkatkan
            self._isi(el, username, human_like=True)
            # Karena el sudah didapat, kita bisa pakai direct send_keys jika _isi gagal mendapatkan xpath
            try:
                # Clear ulang untuk memastikan
                el.send_keys(Keys.CONTROL, "a")
                el.send_keys(Keys.BACKSPACE)
                ketik_manusia(el, username)
            except Exception:
                pass
            
            tunggu_acak(0.5, 1.0)

            # 4. Klik Next
            if not self._klik_next_username():
                raise Exception("Tombol Next username tidak ditemukan")

            tunggu_acak(2.0, 3.5)

            # 5. Cek apakah username diterima
            if not self._cek_username_diambil():
                print(f"   [✓] Username diterima: {username}")
                return username

            print(f"   [!] Username '{username}' sudah diambil (percobaan {percobaan}/{maks_percobaan})")

            # 6. Coba ambil saran Google
            saran = self._ambil_saran_username()
            if saran:
                username = saran
                print(f"   [i] Pakai saran Google: {username}")
                continue

            # 7. Generate baru
            suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=random.randint(4, 8)))
            base = username_awal[:10] if len(username_awal) > 10 else username_awal
            username = f"{base}{suffix}"
            print(f"   [i] Generate username baru: {username}")

        raise Exception(f"Gagal mendapatkan username setelah {maks_percobaan} percobaan")

    def _klik_next_username(self) -> bool:
        """Helper untuk klik tombol Next di tahap username."""
        for next_xpath in [
            '//button[contains(.,"Next")]',
            '//button[contains(.,"Berikutnya")]',
            '//*[@id="next"]/div/button',
            '//div[@id="next"]//button',
            '//*[@id="birthdaygenderNext"]//button', # Terkadang ID masih terbawa dari langkah sebelumnya
        ]:
            try:
                self._klik(next_xpath, timeout=5)
                return True
            except Exception:
                continue
        return False

    def _cek_username_diambil(self) -> bool:
        """Cek apakah muncul pesan error 'username is taken'."""
        error_keywords = [
            "username is taken",
            "that username is taken",
            "username sudah",
            "sudah digunakan",
            "taken",
            "try another",
            "coba yang lain",
        ]
        try:
            # Cek elemen error (biasanya ada aria-live atau class error)
            error_candidates = self.driver.find_elements(
                By.XPATH,
                "//*[contains(@class,'error') or contains(@aria-live,'assertive') "
                "or contains(@role,'alert')]"
            )
            for el in error_candidates:
                txt = (el.text or "").strip().lower()
                if txt and any(kw in txt for kw in error_keywords):
                    return True
            # Cek seluruh body teks
            body_text = (self.driver.find_element(By.TAG_NAME, "body").text or "").lower()
            if any(kw in body_text for kw in error_keywords):
                # Pastikan masih di halaman username (URL belum pindah)
                current_url = self.driver.current_url.lower()
                if "username" in current_url or "signup" in current_url:
                    return True
        except Exception:
            pass
        return False

    def _ambil_saran_username(self) -> str:
        """Ambil username saran dari Google (link 'Available: ...')."""
        try:
            # Saran biasanya berupa link/anchor di dekat pesan error
            # Cari elemen yang mengandung pola username (huruf+angka, tanpa spasi)
            saran_candidates = self.driver.find_elements(
                By.XPATH,
                "//a[contains(@href,'#') or contains(@role,'link')] | "
                "//*[contains(@class,'VfPpkd') and string-length(text()) > 3]"
            )
            for el in saran_candidates:
                try:
                    txt = (el.text or "").strip()
                    # Validasi: harus alfanumerik, panjang 6-30, bukan "Available" label
                    if txt and txt.replace(".", "").replace("_", "").isalnum() and 6 <= len(txt) <= 30:
                        if not txt.lower().startswith("available") and not txt.lower().startswith("@"):
                            # Klik saran
                            try:
                                el.click()
                            except Exception:
                                self.driver.execute_script("arguments[0].click();", el)
                            tunggu_acak(0.5, 1.0)
                            return txt
                except Exception:
                    continue

            # Fallback: cari semua teks yang mirip username di halaman
            body_text = self.driver.find_element(By.TAG_NAME, "body").text or ""
            # Pola: username alfanumerik 6-30 karakter
            matches = re.findall(r'\b[a-z][a-z0-9]{5,29}\b', body_text.lower())
            # Filter yang bukan kata umum
            exclude = {"available", "username", "gmail", "email", "password", "next", "create"}
            for m in matches:
                if m not in exclude and any(c.isdigit() for c in m):
                    return m
        except Exception:
            pass
        return ""

    def buat_akun(self, akun: Akun) -> bool:
        """
        Proses lengkap pembuatan 1 akun Gmail.
        Mengembalikan True jika berhasil.
        """
        driver = self._buat_driver()
        try:
            # ── Session Warming ──
            if config.WARMUP_PAGES > 0:
                panaskan_sesi(driver, config.WARMUP_PAGES)

            # Pastikan jendela masih hidup setelah warmup
            try:
                _ = driver.current_window_handle
            except Exception:
                print("[!] Jendela browser tertutup setelah warmup, membuat driver baru...")
                driver.quit()
                driver = self._buat_driver()

            # ── Buka halaman pendaftaran ──
            print("[*] Membuka halaman pendaftaran Google...")
            driver.get("https://accounts.google.com/signup")
            tunggu_acak(2, 3)

            # ── Langkah 1: Nama ──
            print("[1/6] Mengisi nama...")
            # Tunggu halaman benar-benar stabil
            tunggu_acak(1, 2)
            
            # Gunakan list XPATH untuk ketahanan
            first_name_xpaths = [
                '//*[@id="firstName"]',
                '//input[@name="firstName"]',
                '//input[@aria-label="First name"]',
                '//input[@aria-label="Nama depan"]',
            ]
            last_name_xpaths = [
                '//*[@id="lastName"]',
                '//input[@name="lastName"]',
                '//input[@aria-label="Last name (optional)"]',
                '//input[@aria-label="Nama belakang (opsional)"]',
            ]
            
            self._isi(first_name_xpaths, akun.nama_depan)
            tunggu_acak(0.5, 1.0)
            self._isi(last_name_xpaths, akun.nama_belakang)
            tunggu_acak(0.8, 1.5)
            
            # Klik Next dan tunggu URL berubah
            url_sebelum = self.driver.current_url
            next_diklik = False
            next_xpaths = [
                '//*[@id="collectNameNext"]/div/button',
                '//button[contains(.,"Next")]',
                '//button[contains(.,"Berikutnya")]',
                '//span[contains(.,"Next")]/ancestor::button',
            ]
            
            try:
                self._klik(next_xpaths, timeout=10)
                tunggu_acak(2, 3)
                if self.driver.current_url != url_sebelum:
                    next_diklik = True
            except Exception:
                pass
                
            if not next_diklik:
                print("   [!] Tombol Next nama tidak merespon, coba klik via JS...")
                try:
                    self.driver.execute_script(
                        "document.querySelector('#collectNameNext button')?.click();"
                    )
                    tunggu_acak(2, 3)
                except Exception:
                    pass
            tunggu_acak(1, 2)

            # ── Langkah 2: Tanggal lahir & gender ──
            print("[2/6] Mengisi tanggal lahir & gender...")
            self._interaksi_manusia()
            try:
                # Day & Year: isi langsung tanpa clear (mirip Google input)
                day_el = WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.XPATH, '//*[@id="day"]'))
                )
                day_el.send_keys(str(config.DEFAULT_BIRTH_DAY))
                tunggu_acak(0.3, 0.6)

                # Month: native <select> di dalam #month (coba berbagai format nilai)
                month_berhasil = False
                try:
                    month_select = Select(WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.XPATH, '//*[@id="month"]//select'))
                    ))
                    # Google bisa pakai nilai angka (1-12), nama bulan, atau singkatan
                    month_num = config.DEFAULT_BIRTH_MONTH
                    month_kandidat = [
                        str(month_num),
                        str(month_num - 1),  # beberapa versi pakai 0-indexed
                        calendar.month_name[month_num],
                        calendar.month_abbr[month_num],
                        calendar.month_name[month_num].lower(),
                    ]
                    for val in month_kandidat:
                        try:
                            month_select.select_by_value(val)
                            month_berhasil = True
                            break
                        except Exception:
                            continue
                    if not month_berhasil:
                        # Coba visible text
                        for txt in [calendar.month_name[month_num]]:
                            try:
                                month_select.select_by_visible_text(txt)
                                month_berhasil = True
                                break
                            except Exception:
                                continue
                except Exception:
                    pass

                if not month_berhasil:
                    self._pilih_dropdown_google(
                        '//*[@id="month"]',
                        config.DEFAULT_BIRTH_MONTH,
                        opsi_teks=[calendar.month_name[config.DEFAULT_BIRTH_MONTH]],
                    )
                tunggu_acak(0.3, 0.6)

                year_el = WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.XPATH, '//*[@id="year"]'))
                )
                year_el.send_keys(str(config.DEFAULT_BIRTH_YEAR))
                tunggu_acak(0.3, 0.6)

                # Gender: native <select> di dalam #gender (coba berbagai format nilai)
                gender_berhasil = False
                try:
                    gender_select = Select(WebDriverWait(self.driver, 8).until(
                        EC.presence_of_element_located((By.XPATH, '//*[@id="gender"]//select'))
                    ))
                    # Google bisa pakai nilai angka (1,2,3,4) atau string (male/female/...)
                    gender_values = {
                        1: ["1", "male", "MALE", "Male"],
                        2: ["2", "female", "FEMALE", "Female"],
                        3: ["3", "rather_not_say", "RATHER_NOT_SAY", "Rather not say", "rather"],
                        4: ["4", "custom", "CUSTOM", "Custom"],
                    }
                    for val in gender_values.get(config.DEFAULT_GENDER, [str(config.DEFAULT_GENDER)]):
                        try:
                            gender_select.select_by_value(val)
                            gender_berhasil = True
                            print(f"   [i] Gender dipilih via native select (value={val})")
                            break
                        except Exception:
                            continue
                    if not gender_berhasil:
                        # Coba select by visible text
                        gender_texts = {
                            1: ["Male", "Laki-laki", "Laki laki"],
                            2: ["Female", "Perempuan"],
                            3: ["Rather not say", "Tidak ingin menyebutkan"],
                            4: ["Custom", "Kustom"],
                        }
                        for txt in gender_texts.get(config.DEFAULT_GENDER, []):
                            try:
                                gender_select.select_by_visible_text(txt)
                                gender_berhasil = True
                                print(f"   [i] Gender dipilih via visible text ({txt})")
                                break
                            except Exception:
                                continue
                except Exception:
                    pass

                if not gender_berhasil:
                    print("   [i] Native select gender tidak ada, coba custom dropdown...")
                    gender_map = {
                        1: ["male", "laki"],
                        2: ["female", "perempuan"],
                        3: ["rather", "tidak ingin"],
                        4: ["custom", "kustom"],
                    }
                    gender_berhasil = self._pilih_dropdown_google(
                        '//*[@id="gender"]',
                        config.DEFAULT_GENDER,
                        opsi_teks=gender_map.get(config.DEFAULT_GENDER, []),
                    )
                    if gender_berhasil:
                        print("   [i] Gender dipilih via custom dropdown")

                # Verifikasi gender sudah terpilih, jika belum coba JS direct
                if not self._cek_gender_terpilih():
                    print("   [!] Gender belum terpilih, coba JS direct selector...")
                    self._pilih_gender_js(config.DEFAULT_GENDER)
                    tunggu_acak(0.3, 0.6)
                tunggu_acak(0.5, 1)

                # Klik Next
                next_btn = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, '//*[@id="birthdaygenderNext"]/div/button'))
                )
                next_btn.click()
                tunggu_acak(2, 3)
            except Exception as e:
                print(f"   [!] Lewati tahap tanggal lahir: {e}")

            # ── Langkah 3: Username Gmail ──
            print("[3/6] Mengisi username Gmail...")
            print(f"   [DEBUG] URL: {self.driver.current_url}")
            try:
                username_awal = akun.email.replace("@gmail.com", "")
                username_terpilih = self._input_username_dengan_retry(username_awal)
                # Update email akun dengan username yang berhasil
                akun.email = f"{username_terpilih}@gmail.com"
                tunggu_acak(1.0, 2.0)
            except Exception as e:
                print(f"   [!] Error mengisi username: {e}")
                return False

            # ── Langkah 4: Password ──
            print("[4/6] Mengisi password...")
            self._interaksi_manusia()
            try:
                self._isi('//*[@id="passwd"]/div[1]/div/div[1]/input', akun.password)
                tunggu_acak(0.8, 1.5)
                self._isi('//*[@id="confirm-passwd"]/div[1]/div/div[1]/input', akun.password)
                tunggu_acak(0.8, 1.5)
                self._klik('//*[@id="createpasswordNext"]/div/button')
                tunggu_acak(3, 5)
            except Exception as e:
                print(f"   [!] Error mengisi password: {e}")
                return False

            # Cek apakah setelah password Google menampilkan error page
            if cek_halaman_error(self.driver):
                print("   [✗] Google menolak membuat akun setelah langkah password.")
                print("   [i] Kemungkinan: deteksi bot, perlu verifikasi telepon, atau pembatasan Google.")
                akun.sukses = False
                return False

            # ── Langkah 5: Verifikasi telepon (Skip atau 5sim) ──
            print("[5/6] Menangani verifikasi telepon...")
            hasil_verif = self._tangani_verifikasi(akun)
            if hasil_verif == "skip":
                print("   [✓] Verifikasi telepon di-Skip!")
            elif hasil_verif == "5sim":
                print("   [✓] Verifikasi telepon selesai via 5sim!")
            else:
                print("   [✗] Tidak bisa melewati verifikasi telepon.")
                return False

            # ── Langkah 6: Selesaikan ──
            print("[6/6] Menyelesaikan pendaftaran...")
            time.sleep(2)

            # VERIFIKASI SUKSES: pastikan bukan halaman error, cek halaman sukses
            if cek_halaman_error(self.driver):
                print("   [✗] Pendaftaran GAGAL: Google menampilkan halaman error.")
                print("   [i] Kemungkinan penyebab: deteksi bot, proxy bermasalah, atau pembatasan Google.")
                akun.sukses = False
                return False

            # Jika masih di halaman verifikasi telepon, berarti verifikasi belum selesai
            if cek_halaman_verifikasi_telepon(self.driver):
                print("   [✗] Pendaftaran GAGAL: masih di halaman verifikasi telepon.")
                print("   [i] Verifikasi telepon belum diselesaikan, akun tidak jadi dibuat.")
                akun.sukses = False
                return False

            if not cek_halaman_sukses(self.driver):
                print("   [!] Belum sampai halaman sukses, tunggu sebentar lagi...")
                time.sleep(4)

                if cek_halaman_error(self.driver):
                    print("   [✗] Pendaftaran GAGAL setelah pengecekan ulang.")
                    akun.sukses = False
                    return False

                if cek_halaman_verifikasi_telepon(self.driver):
                    print("   [✗] Pendaftaran GAGAL: kembali terdeteksi di halaman verifikasi telepon.")
                    akun.sukses = False
                    return False

                # Jika masih belum jelas sukses, coba klik tombol Next yang mungkin masih ada
                if not cek_halaman_sukses(self.driver):
                    try:
                        for next_xpath in [
                            '//button[contains(.,"Next")]',
                            '//button[contains(.,"Berikutnya")]',
                        ]:
                            try:
                                self._klik(next_xpath, timeout=5)
                                time.sleep(3)
                                break
                            except Exception:
                                continue
                    except Exception:
                        pass

            # Final check: HARUS benar-benar sukses
            if cek_halaman_error(self.driver):
                print("   [✗] Pendaftaran GAGAL: halaman error di langkah akhir.")
                akun.sukses = False
                return False

            # Pertahanan: pastikan bukan halaman signin (akun tidak benar-benar dibuat)
            try:
                url_final = self.driver.current_url.lower()
                if "signin" in url_final or "identifier" in url_final or "challenge" in url_final:
                    print("   [✗] Pendaftaran GAGAL: berakhir di halaman signin (akun tidak dibuat).")
                    print(f"   [i] URL: {url_final[:120]}")
                    akun.sukses = False
                    return False
            except Exception:
                pass

            if cek_halaman_verifikasi_telepon(self.driver):
                print("   [✗] Pendaftaran GAGAL: verifikasi telepon belum selesai.")
                akun.sukses = False
                return False

            if not cek_halaman_sukses(self.driver):
                print("   [✗] Pendaftaran GAGAL: tidak sampai ke halaman sukses.")
                print(f"   [i] URL saat ini: {self.driver.current_url[:120]}")
                akun.sukses = False
                return False

            akun.sukses = True
            self._simpan_akun(akun)
            print(f"\n[✓✓✓] AKUN BERHASIL DIBUAT!")
            print(f"    Email    : {akun.email}")
            print(f"    Password : {akun.password}")
            if akun.nomor_telepon:
                print(f"    Nomor HP : {akun.nomor_telepon}")
            return True

        except Exception as e:
            print(f"[✗] Terjadi kesalahan: {e}")
            return False
        finally:
            if not config.HEADLESS:
                print("\nBrowser dibiarkan terbuka. Tekan Ctrl+C untuk menutup.")
                try:
                    while True:
                        time.sleep(1)
                except KeyboardInterrupt:
                    pass
            driver.quit()

    def _alihkan_qr_ke_sms(self) -> bool:
        """
        Google sekarang menampilkan halaman QR code terlebih dahulu
        sebelum input nomor telepon. Metode ini mencari tombol toggle
        (ikon bulat di pojok kanan bawah) atau link 'Try another way'
        untuk beralih ke verifikasi SMS.
        """
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

        print("   [i] Terdeteksi halaman QR code, mencoba beralih ke SMS...")

        # 1. Coba cari link "Try another way" atau "Verifikasi dengan cara lain" secara eksplisit
        try:
            keywords_lain = ["another way", "another method", "cara lain", "lainnya", "other way"]
            links = self.driver.find_elements(By.XPATH, "//button | //a | //div[@role='button'] | //span[@role='button']")
            for link in links:
                txt = (link.text or "").lower()
                aria = (link.get_attribute("aria-label") or "").lower()
                if any(k in txt or k in aria for k in keywords_lain):
                    print(f"   [✓] Menemukan link toggle: '{txt or aria}'")
                    try:
                        link.click()
                    except Exception:
                        self.driver.execute_script("arguments[0].click();", link)
                    tunggu_acak(2, 4)
                    if not cek_halaman_qr(self.driver):
                        return True
        except Exception:
            pass

        viewport_h = self.driver.execute_script("return window.innerHeight;") or 800
        viewport_w = self.driver.execute_script("return window.innerWidth;") or 1280

        # 2. Kumpulkan semua kandidat tombol toggle (ikon tanpa teks)
        kandidat = []
        try:
            # Cari SEMUA elemen yang mungkin diklik (lebih agresif)
            all_elems = self.driver.find_elements(
                By.XPATH,
                "//button | //div[@role='button'] | //span[@role='button'] | //a | //div[contains(@class, 'button')] | //div[contains(@class, 'icon')]"
            )
            for el in all_elems:
                try:
                    if not el.is_displayed():
                        continue
                    rect = el.rect
                    w = rect.get("width", 0) or 0
                    h = rect.get("height", 0) or 0
                    # Ikon toggle biasanya kecil (lingkaran di pojok) atau tombol sedang
                    if w < 10 or h < 10 or w > 500 or h > 150:
                        continue
                    
                    txt = (el.text or "").strip()
                    aria = (el.get_attribute("aria-label") or "").strip()
                    
                    # Daftar kata yang BUKAN tombol toggle
                    forbidden = [
                        "next", "berikutnya", "help", "bantuan", "back",
                        "kembali", "privacy", "terms", "english", "language",
                        "sign in", "masuk", "skip", "lewati", "learn more",
                        "kebijakan", "persyaratan", "bantuan", "privasi",
                    ]
                    combined = f"{txt} {aria}".lower()
                    if any(f in combined for f in forbidden):
                        continue
                        
                    # Prioritaskan tombol ikon (tanpa teks / ada SVG)
                    punya_svg = False
                    try:
                        el.find_element(By.TAG_NAME, "svg")
                        punya_svg = True
                    except Exception:
                        pass
                        
                    skor = 0
                    if not txt:
                        skor += 10
                    if punya_svg:
                        skor += 10
                    if any(k in combined for k in ["sms", "phone", "text", "mobile", "another"]):
                        skor += 25
                    
                    # Bonus posisi: Ikon toggle Google biasanya di kanan bawah
                    dist_x = rect["x"] / viewport_w
                    dist_y = rect["y"] / viewport_h
                    skor += dist_x * 15
                    skor += dist_y * 15
                    
                    kandidat.append((skor, el, aria, txt, rect))
                except Exception:
                    continue
        except Exception:
            pass

        kandidat.sort(key=lambda t: t[0], reverse=True)

        if not kandidat:
            print("   [!] Tombol toggle otomatis tidak ditemukan.")
            
            # Cek apakah ini 'Hard Lock' (tidak ada link bantuan sama sekali)
            try:
                body_text = self.driver.find_element(By.TAG_NAME, "body").text.lower()
                if "scan the qr code" in body_text and "another way" not in body_text:
                    print("   [✗] Google menerapkan 'Hard Lock' (hanya QR Code tersedia).")
                    print("   [i] SARAN: Ganti IP Anda (Gunakan Hotspot HP + Mode Pesawat reset).")
                    return False
            except Exception:
                pass

            # Fallback intervensi manual jika tidak headless
            if not config.HEADLESS:
                print("\n   [?] SILAHKAN KLIK manual tombol 'Try another way' atau ikon pesan di browser Anda...")
                print("   [?] Script akan menunggu 30 detik untuk Anda bertindak.")
                for i in range(30):
                    if not cek_halaman_qr(self.driver):
                        print("   [✓] Deteksi halaman berubah! Melanjutkan...")
                        return True
                    if (i+1) % 10 == 0: print(f"   [i] Menunggu... ({30-i-1}s)")
                    time.sleep(1)
            return False

        # Coba klik kandidat satu per satu
        for skor, el, aria, txt, rect in kandidat[:10]:
            print(f"   [i] Mencoba klik (skor={skor:.1f}): aria='{aria[:30]}' text='{txt[:20]}' pos=({int(rect['x'])},{int(rect['y'])})")
            try:
                try:
                    el.click()
                except Exception:
                    self.driver.execute_script("arguments[0].click();", el)
            except Exception:
                continue

            tunggu_acak(2, 4)
            if not cek_halaman_qr(self.driver):
                # Cek apakah input telepon muncul
                try:
                    self.driver.find_element(By.XPATH, "//input[@type='tel']")
                    print("   [✓] Berhasil beralih ke halaman input nomor telepon (SMS).")
                    return True
                except Exception:
                    # Mungkin halaman berubah ke sukses atau lainnya
                    if not cek_halaman_qr(self.driver):
                        return True
        
        # Jika otomatis gagal, coba Refresh satu kali (terkadang Google ganti challenge)
        print("   [i] Mencoba merefresh halaman (Google terkadang mengganti challenge QR setelah refresh)...")
        self.driver.refresh()
        tunggu_acak(3, 5)
        if not cek_halaman_qr(self.driver):
            print("   [✓] Halaman berubah setelah refresh!")
            return True

        # 4. Jika semua otomatis gagal, coba intervensi manual terakhir
        if not config.HEADLESS:
            print("\n   [?] Percobaan otomatis gagal. Silahkan klik manual di browser...")
            print("   [?] Jika tidak ada tombol, coba klik ikon 'Back' di browser atau refresh manual.")
            for i in range(20):
                if not cek_halaman_qr(self.driver):
                    return True
                time.sleep(1)

        return False

    def _tangani_verifikasi(self, akun: Akun) -> str:
        """
        Menangani halaman verifikasi telepon.
        Strategi:
          0. Cek apakah halaman error (Google menolak membuat akun).
          1. Jika 5SIM dikonfigurasi -> gunakan 5SIM (prioritas utama).
          2. Jika tidak ada 5SIM -> coba klik tombol Skip.
          3. Jika tidak ada Skip & tidak ada 5SIM -> intervensi manual.
        Mengembalikan "skip", "5sim", atau "gagal".
        """
        time.sleep(2)

        # 0. Cek apakah halaman error (Google gagal membuat akun)
        if cek_halaman_error(self.driver):
            print("   [✗] Google menolak membuat akun (halaman error).")
            print("   [i] Biasanya karena deteksi bot, proxy, atau pembatasan Google.")
            return "gagal"

        # Cek apakah ini halaman verifikasi telepon
        is_phone_page = cek_halaman_verifikasi_telepon(self.driver)
        if not is_phone_page:
            # Bukan halaman telepon, cek apakah error atau sukses
            if cek_halaman_error(self.driver):
                print("   [✗] Halaman error terdeteksi.")
                return "gagal"
            if cek_halaman_sukses(self.driver):
                print("   [i] Langsung ke halaman sukses (tanpa verifikasi telepon).")
                return "skip"
            # Tunggu sebentar, mungkin halaman masih loading (transisi ke halaman telepon)
            print("   [i] Bukan halaman telepon, tunggu transisi halaman...")
            time.sleep(3)
            if cek_halaman_verifikasi_telepon(self.driver):
                # Ternyata halaman telepon muncul setelah loading
                is_phone_page = True
            elif cek_halaman_sukses(self.driver):
                print("   [i] Langsung ke halaman sukses (tanpa verifikasi telepon).")
                return "skip"
            elif cek_halaman_error(self.driver):
                print("   [✗] Halaman error terdeteksi.")
                return "gagal"
            else:
                # Bukan telepon, bukan error, bukan sukses.
                # JANGAN asumsikan lolos — bisa jadi halaman signin (akun tidak dibuat)
                # atau halaman lain yang tidak terduga.
                print("   [!] Halaman tidak teridentifikasi (bukan telepon/error/sukses).")
                print(f"   [i] URL saat ini: {self.driver.current_url[:120]}")
                # Hanya anggap lolos jika benar-benar di halaman sukses
                if cek_halaman_sukses(self.driver):
                    return "skip"
                return "gagal"

        if is_phone_page:
            print("   [i] Halaman verifikasi telepon terdeteksi.")

        # Jika masih halaman QR, coba alihkan ke SMS dulu (agar field telepon muncul)
        if cek_halaman_qr(self.driver):
            if not self._alihkan_qr_ke_sms():
                print("   [!] Gagal beralih dari QR ke SMS.")
                # Jika masih di halaman QR setelah gagal toggle, verifikasi tidak bisa dilanjutkan
                if cek_halaman_qr(self.driver):
                    print("   [✗] Masih terjebak di halaman QR, verifikasi telepon tidak mungkin.")
                    return "gagal"

        # 1. PRIORITAS 5SIM: jika API key tersedia, gunakan 5SIM
        if config.FIVESTIM_API_KEY:
            hasil_5sim = self._verifikasi_dengan_5sim(akun)
            if hasil_5sim == "5sim":
                return "5sim"
            elif hasil_5sim == "gagal":
                return "gagal"
            # Jika 5sim gagal, lanjut ke skip/manual

        # 2. Coba Skip (jika ada)
        if cari_dan_klik_skip(self.driver):
            return "skip"

        # 3. Fallback: intervensi manual
        print("   [i] Silakan selesaikan verifikasi telepon secara manual di browser.")
        print("       Setelah selesai, kembali ke terminal dan tekan Enter.")
        try:
            input()
        except EOFError:
            # Non-interactive: tidak bisa manual, anggap gagal
            print("   [!] Mode non-interaktif: intervensi manual tidak memungkinkan.")
            return "gagal"

        # Cek lagi setelah intervensi manual: harus keluar dari halaman telepon
        time.sleep(2)
        if cek_halaman_error(self.driver):
            return "gagal"
        if cek_halaman_verifikasi_telepon(self.driver):
            print("   [✗] Verifikasi telepon belum diselesaikan (masih di halaman telepon).")
            return "gagal"
        # Pastikan benar-benar di halaman sukses, bukan signin atau halaman lain
        if not cek_halaman_sukses(self.driver):
            print("   [✗] Setelah intervensi manual, halaman bukan halaman sukses.")
            print(f"   [i] URL saat ini: {self.driver.current_url[:120]}")
            return "gagal"
        return "skip"

    def _verifikasi_dengan_5sim(self, akun: Akun) -> str:
        """
        Melakukan verifikasi telepon menggunakan 5SIM.
        Mengembalikan "5sim" jika berhasil, "gagal" jika error, "skip" jika harus fallback.
        """
        try:
            from sms_provider import FiveSimProvider
            provider = FiveSimProvider()

            # Cek saldo dulu
            try:
                saldo = provider.cek_balance()
                print(f"   [5SIM] Saldo: ${saldo:.2f}")
                if saldo < 0.1:
                    print("   [!] Saldo 5SIM terlalu rendah, skip 5SIM.")
                    return "skip"
            except Exception as e:
                print(f"   [!] Gagal cek saldo 5SIM: {e}")
                return "skip"

            # Jika halaman masih QR code, alihkan ke SMS dulu sebelum beli nomor
            if cek_halaman_qr(self.driver):
                if not self._alihkan_qr_ke_sms():
                    print("   [!] Gagal beralih dari QR ke SMS, fallback ke skip/manual.")
                    return "skip"

            # Beli nomor
            order = provider.beli_nomor()
            nomor = order.get("phone")
            order_id = order.get("id")
            if not nomor or not order_id:
                print("   [!] Gagal mendapatkan nomor dari 5SIM.")
                return "skip"

            # Simpan nomor ke akun
            akun.nomor_telepon = str(nomor)
            print(f"   [5SIM] Nomor: {nomor}")

            # Tunggu field telepon muncul
            time.sleep(2)

            # Masukkan nomor ke field telepon (coba beberapa selector)
            input_telp = None
            for telp_xpath in [
                "//input[@name='phoneNumber']",
                "//input[@type='tel']",
                "//input[@aria-label*='phone' or @aria-label*='Phone' or @aria-label*='telepon' or @aria-label*='Telepon']",
                "//input[contains(@id,'phone')]",
                "//input[contains(@class,'phone')]",
                "//input[@autocomplete='tel']",
            ]:
                try:
                    input_telp = self._tunggu_input(telp_xpath, timeout=5)
                    if input_telp.is_displayed():
                        print(f"   [i] Field telepon ditemukan: {telp_xpath}")
                        break
                    input_telp = None
                except Exception:
                    continue

            # Fallback: cari semua input yang terlihat dan pilih yang cocok
            if input_telp is None:
                print("   [i] Field telepon tidak ditemukan via selector, scan semua input...")
                try:
                    all_inputs = self.driver.find_elements(By.TAG_NAME, "input")
                    for inp in all_inputs:
                        try:
                            if not inp.is_displayed():
                                continue
                            inp_type = inp.get_attribute("type") or ""
                            inp_name = inp.get_attribute("name") or ""
                            inp_id = inp.get_attribute("id") or ""
                            inp_aria = inp.get_attribute("aria-label") or ""
                            combined = f"{inp_type} {inp_name} {inp_id} {inp_aria}".lower()
                            if any(kw in combined for kw in ["tel", "phone", "nomor", "number"]):
                                input_telp = inp
                                print(f"   [i] Field telepon ditemukan via scan: name={inp_name}, type={inp_type}")
                                break
                        except Exception:
                            continue
                except Exception:
                    pass

            if input_telp is None:
                print("   [!] Field telepon tidak ditemukan sama sekali.")
                provider.batalkan_order(order_id)
                return "skip"

            # Bersihkan field
            try:
                input_telp.click()
                input_telp.clear()
            except Exception:
                pass

            # Tentukan kode negara dan nomor tanpa kode
            nomor_str = str(nomor)
            # 5SIM nomor Indonesia biasanya +62xxxxxxxxxx
            kode_negara = "+62"
            nomor_tanpa_kode = nomor_str
            if nomor_str.startswith("+62"):
                nomor_tanpa_kode = nomor_str[3:]  # hilangkan +62
            elif nomor_str.startswith("62"):
                nomor_tanpa_kode = nomor_str[2:]

            # Cek apakah ada dropdown kode negara
            # Google biasanya punya dropdown kode negara di sebelah field telepon
            kode_negara_diubah = False
            try:
                # Cari elemen yang menunjukkan kode negara (biasanya ada +1 default)
                country_selectors = [
                    "//div[contains(@class,'country')]//div[contains(@role,'button')]",
                    "//div[contains(@jsname,'country')]",
                    "//div[contains(text(),'+1')]",
                    "//span[contains(text(),'+1')]",
                ]
                for sel in country_selectors:
                    try:
                        el = self.driver.find_element(By.XPATH, sel)
                        if el.is_displayed():
                            el.click()
                            tunggu_acak(0.5, 1.0)
                            # Cari opsi Indonesia (+62)
                            for opt_sel in [
                                "//div[contains(text(),'+62')]",
                                "//span[contains(text(),'+62')]",
                                "//div[contains(text(),'Indonesia')]",
                            ]:
                                try:
                                    opt = self.driver.find_element(By.XPATH, opt_sel)
                                    if opt.is_displayed():
                                        opt.click()
                                        kode_negara_diubah = True
                                        print(f"   [i] Kode negara diubah ke +62 via {opt_sel}")
                                        break
                                except Exception:
                                    continue
                            if kode_negara_diubah:
                                break
                            # Klik lagi untuk tutup dropdown jika tidak ditemukan
                            try:
                                el.click()
                            except Exception:
                                pass
                    except Exception:
                        continue
            except Exception:
                pass

            tunggu_acak(0.3, 0.6)

            # Masukkan nomor (tanpa kode negara jika kode negara sudah +62)
            if kode_negara_diubah:
                nomor_untuk_input = nomor_tanpa_kode
            else:
                # Coba masukkan nomor lengkap dengan kode negara
                nomor_untuk_input = nomor_str

            print(f"   [i] Memasukkan nomor: {nomor_untuk_input}")
            try:
                input_telp.send_keys(nomor_untuk_input)
            except Exception:
                self.driver.execute_script(
                    "arguments[0].value = arguments[1];"
                    "arguments[0].dispatchEvent(new Event('input', {bubbles:true}));"
                    "arguments[0].dispatchEvent(new Event('change', {bubbles:true}));",
                    input_telp, nomor_untuk_input,
                )
            tunggu_acak(0.5, 1.0)

            # Klik Next/Send kode
            next_diklik = False
            for next_xpath in [
                "//div[@id='phoneNumberNext']//button",
                "//button[contains(.,'Next')]",
                "//button[contains(.,'Berikutnya')]",
                "//button[contains(.,'Send')]",
                "//button[contains(.,'Kirim')]",
            ]:
                try:
                    self._klik(next_xpath, timeout=8)
                    next_diklik = True
                    break
                except Exception:
                    continue

            if not next_diklik:
                print("   [!] Tombol Next/Send tidak ditemukan.")
                provider.batalkan_order(order_id)
                return "skip"

            tunggu_acak(2, 3)

            # Cek apakah ada error setelah memasukkan nomor
            if cek_halaman_error(self.driver):
                print("   [✗] Google menolak nomor telepon (halaman error).")
                provider.batalkan_order(order_id)
                return "gagal"

            # Tunggu kode SMS
            kode = provider.tunggu_sms(order_id)
            if not kode:
                print("   [!] Tidak menerima kode SMS dari 5SIM.")
                provider.batalkan_order(order_id)
                return "skip"

            print(f"   [5SIM] Kode verifikasi: {kode}")

            # Masukkan kode verifikasi (coba beberapa selector)
            kode_terisi = False
            for kode_xpath in [
                "//input[@name='code']",
                "//input[@aria-label*='code' or @aria-label*='Code' or @aria-label*='verifikasi' or @aria-label*='Verification']",
                "//input[contains(@id,'code')]",
                "//input[@type='tel']",
                "//input[@type='text']",
            ]:
                try:
                    input_kode = self._tunggu_input(kode_xpath, timeout=8)
                    if input_kode.is_displayed():
                        input_kode.clear()
                        try:
                            input_kode.send_keys(str(kode))
                        except Exception:
                            self.driver.execute_script(
                                "arguments[0].value = arguments[1];"
                                "arguments[0].dispatchEvent(new Event('input', {bubbles:true}));"
                                "arguments[0].dispatchEvent(new Event('change', {bubbles:true}));",
                                input_kode, str(kode),
                            )
                        kode_terisi = True
                        break
                except Exception:
                    continue

            if not kode_terisi:
                print("   [!] Field kode verifikasi tidak ditemukan.")
                provider.batalkan_order(order_id)
                return "skip"

            tunggu_acak(0.5, 1.0)

            # Klik Verify/Next
            for verify_xpath in [
                "//button[contains(.,'Verify')]",
                "//button[contains(.,'Verifikasi')]",
                "//button[contains(.,'Next')]",
                "//button[contains(.,'Berikutnya')]",
            ]:
                try:
                    self._klik(verify_xpath, timeout=8)
                    break
                except Exception:
                    continue

            tunggu_acak(2, 3)

            # Cek hasil
            if cek_halaman_error(self.driver):
                print("   [✗] Verifikasi kode gagal (halaman error).")
                provider.batalkan_order(order_id)
                return "gagal"

            provider.selesaikan_order(order_id)
            print("   [✓] Verifikasi telepon via 5SIM berhasil!")
            return "5sim"

        except Exception as e:
            print(f"   [!] 5SIM error: {e}")
            return "skip"

    @staticmethod
    def _simpan_akun(akun: Akun):
        """Menyimpan akun ke file JSON dan mencatat ke log teks (agar data aman jika terminal ditutup)."""
        data = []
        if os.path.exists(config.ACCOUNTS_FILE):
            try:
                with open(config.ACCOUNTS_FILE, "r") as f:
                    data = json.load(f)
            except Exception:
                data = []

        data.append(asdict(akun))
        with open(config.ACCOUNTS_FILE, "w") as f:
            json.dump(data, f, indent=2)
        print(f"   [i] Akun disimpan ke {config.ACCOUNTS_FILE}")

        # Catat ke log teks agar data tetap aman meski terminal/log hilang
        try:
            waktu = time.strftime("%Y-%m-%d %H:%M:%S")
            with open(config.ACCOUNTS_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(
                    f"[{waktu}] {akun.email} | password: {akun.password} | "
                    f"nama: {akun.nama_depan} {akun.nama_belakang} | "
                    f"telepon: {akun.nomor_telepon or '-'}\n"
                )
            print(f"   [i] Log akun ditambahkan ke {config.ACCOUNTS_LOG_FILE}")
        except Exception as e:
            print(f"   [!] Gagal menulis log: {e}")
