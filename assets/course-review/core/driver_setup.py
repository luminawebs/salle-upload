from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from config.settings import Config

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

    # Initialize the WebDriver.
    # With Selenium 4.6+, Selenium Manager handles the chromedriver executable automatically.
    driver = webdriver.Chrome(options=chrome_options)

    # Allow up to 90s for heavy Moodle course pages to load
    # (the previous 30s was too short and caused "renderer timed out" errors)
    driver.set_page_load_timeout(90)

    return driver
