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

    return driver
