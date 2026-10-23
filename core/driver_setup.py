import glob
import logging
import os
import shutil
import tempfile
import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from config.settings import Config

logger = logging.getLogger(__name__)

# Chrome's temporary profile folders (~160 MB each). Chrome deletes its own on
# a clean exit, but a run that is cancelled or replaced by a new upload is
# killed before it can, and the folders piled up until the server's disk was
# full ("No space left on device") and Chrome could no longer start.
_CHROME_TEMP_PATTERNS = ("org.chromium.Chromium.scoped_dir.*", ".org.chromium.Chromium.*", ".com.google.Chrome.*")
_STALE_AFTER_SECONDS = 30 * 60


def _last_change(path: str) -> float:
    """Newest modification time of a folder and its direct entries (a live Chrome keeps touching them)."""
    newest = os.path.getmtime(path)
    try:
        for entry in os.scandir(path):
            try:
                newest = max(newest, entry.stat(follow_symlinks=False).st_mtime)
            except OSError:
                pass
    except OSError:
        pass
    return newest


def clean_stale_chrome_temp() -> int:
    """Deletes Chrome temporary folders left by earlier runs (untouched for 30+ minutes). Returns MB freed."""
    freed = 0
    now = time.time()
    for pattern in _CHROME_TEMP_PATTERNS:
        for path in glob.glob(os.path.join(tempfile.gettempdir(), pattern)):
            try:
                if not os.path.isdir(path) or now - _last_change(path) < _STALE_AFTER_SECONDS:
                    continue
                size = sum(os.path.getsize(os.path.join(root, f)) for root, _, files in os.walk(path) for f in files)
                shutil.rmtree(path, ignore_errors=True)
                freed += size
            except OSError:
                continue
    if freed:
        logger.info(f"Deleted {freed // (1024 * 1024)} MB of Chrome temporary folders left by earlier runs.")
    return freed // (1024 * 1024)


def get_driver():
    """
    Initializes and returns a Chrome WebDriver instance with configured options.
    """
    chrome_options = Options()

    if Config.HEADLESS_MODE:
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")

    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    # Set a standard window size for consistent rendering
    chrome_options.add_argument("--window-size=1920,1080")

    # Disable unnecessary background network activity that can cause renderer hangs
    chrome_options.add_argument("--disable-background-networking")
    chrome_options.add_argument("--disable-extensions")

    if Config.CHROME_BINARY_LOCATION:
        chrome_options.binary_location = Config.CHROME_BINARY_LOCATION

    # Initialize the WebDriver.
    if Config.EXECUTE_REMOTE:
        # For Remote WebDriver (e.g., Selenium Grid or Docker)
        driver = webdriver.Remote(
            command_executor=Config.SELENIUM_REMOTE_URL,
            options=chrome_options
        )
    else:
        # With Selenium 4.6+, Selenium Manager handles the chromedriver executable automatically locally
        # Enable robust logging for ChromeDriver
        from selenium.webdriver.chrome.service import Service
        
        if Config.CHROMEDRIVER_PATH:
            service = Service(executable_path=Config.CHROMEDRIVER_PATH, log_output="chromedriver.log")
        else:
            service = Service(log_output="chromedriver.log")
            
        driver = webdriver.Chrome(options=chrome_options, service=service)

    # Allow up to 90s for heavy Moodle course pages to load
    # (the previous 30s was too short and caused "renderer timed out" errors)
    driver.set_page_load_timeout(90)
    _time_page_loads(driver)

    return driver


# Where one page's load time goes, from the browser's own Navigation/Resource
# Timing: Moodle generating the page (until its first byte), downloading the
# HTML, then the page's files (CSS/JS/images) and scripts. And how many of
# those files came from the browser cache: a fresh profile per run has none,
# which is what a persistent profile would change.
_BREAKDOWN_JS = """
const nav = performance.getEntriesByType('navigation')[0];
if (!nav) return null;
const res = performance.getEntriesByType('resource');
const cached = res.filter(r => r.transferSize === 0 && r.decodedBodySize > 0).length;
return {
  servidor: (nav.responseStart - nav.startTime) / 1000,
  pagina: (nav.responseEnd - nav.responseStart) / 1000,
  archivos: Math.max(0, (nav.loadEventEnd || nav.duration) - nav.responseEnd) / 1000,
  recursos: res.length,
  desde_cache: cached,
  kb: Math.round(res.reduce((s, r) => s + (r.transferSize || 0), 0) / 1024),
};
"""


def _load_breakdown(driver):
    """{servidor, pagina, archivos (s), recursos, desde_cache, kb} for the page just loaded, or None."""
    try:
        return driver.execute_script(_BREAKDOWN_JS)
    except Exception:
        return None


def _time_page_loads(driver) -> None:
    """Records how long every driver.get() takes (core/progress: the summary
    and the full log show where a run's time goes). Measuring only."""
    original_get = driver.get

    def timed_get(url):
        started = time.monotonic()
        try:
            return original_get(url)
        finally:
            try:
                from core import progress
                progress.record_page_load(url, time.monotonic() - started, _load_breakdown(driver))
            except Exception:
                pass

    driver.get = timed_get
