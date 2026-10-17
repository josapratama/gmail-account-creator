from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time

STEALTH = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
window.chrome = { runtime: {} };
"""

o = webdriver.ChromeOptions()
o.add_argument("--start-maximized")
o.add_argument("--disable-blink-features=AutomationControlled")
o.add_argument("--no-sandbox")
o.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
o.add_experimental_option("excludeSwitches", ["enable-automation"])
o.add_experimental_option("useAutomationExtension", False)

d = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=o)
d.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": STEALTH})
d.set_page_load_timeout(45)

for u in ["https://news.ycombinator.com", "https://www.google.com"]:
    try:
        d.get(u)
        print("OK", u, d.title)
    except Exception as e:
        print("ERR", u, repr(e))
    time.sleep(2)

d.quit()
print("DONE")
