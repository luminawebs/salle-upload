import logging
import os
import time
import json
import glob
import shutil
import urllib.request
from PIL import Image
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

from config.settings import Config

logger = logging.getLogger(__name__)


def login_depositphotos(driver, wait_time=15):
    """
    Navigates to Depositphotos login page and authenticates.
    """
    login_url = "https://depositphotos.com/login.html"
    driver.get(login_url)
    logger.info("Navigated to Depositphotos login page.")

    wait = WebDriverWait(driver, wait_time)

    try:
        # User requested to click "login with email" first
        logger.info("Looking for 'login with email' button...")
        email_btn_xpath = "//*[(self::button or self::a or self::div or self::span) and contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'email')]"
        try:
            email_btn = wait.until(
                EC.element_to_be_clickable((By.XPATH, email_btn_xpath))
            )
            email_btn.click()
            logger.info("Clicked 'login with email' button.")
            time.sleep(1)
        except TimeoutException:
            logger.info("No 'login with email' button found. Proceeding to inputs.")

        # Wait for the login form
        email_input = wait.until(
            EC.presence_of_element_located(
                (
                    By.CSS_SELECTOR,
                    "input[name='login'], input[name='username'], input[type='email']",
                )
            )
        )
        password_input = driver.find_element(
            By.CSS_SELECTOR, "input[name='password'], input[type='password']"
        )

        email_input.clear()
        email_input.send_keys(Config.DEPOSITPHOTOS_USER)

        password_input.clear()
        password_input.send_keys(Config.DEPOSITPHOTOS_PASS)

        # Find and click the login button
        submit_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        submit_btn.click()

        # Wait for login to complete (e.g. navigation away from login page, or presence of user profile)
        logger.info(
            "Waiting for login to complete... (If CAPTCHA appears, please solve it manually)"
        )

        # We'll wait up to 60 seconds to allow manual CAPTCHA solving if needed
        long_wait = WebDriverWait(driver, 60)
        long_wait.until_not(EC.url_contains("login.html"))

        logger.info("Successfully logged into Depositphotos.")
        return True

    except Exception as e:
        logger.error(f"Failed to log into Depositphotos: {e}")
        return False


def configure_download_directory(driver, download_path):
    """
    Configures Chrome to download files to the specified path without prompting.
    """
    # Create the directory if it doesn't exist
    os.makedirs(download_path, exist_ok=True)

    # Use CDP to set the download behavior dynamically
    driver.execute_cdp_cmd(
        "Page.setDownloadBehavior",
        {"behavior": "allow", "downloadPath": os.path.abspath(download_path)},
    )
    logger.info(f"Set Chrome download directory to {download_path}")


def download_image(driver, url, download_dir, wait_time=15):
    """
    Downloads an image from the given URL.
    Returns the path to the downloaded file, or None if failed.
    """
    if url.endswith((".jpg", ".jpeg", ".png", ".gif", ".webp")):
        # Direct image link, we can just download it using urllib
        # Sometimes direct links require headers
        logger.info(f"Direct image link detected. Downloading using urllib: {url}")
        try:
            filename = url.split("/")[-1]
            # Strip query params if any
            filename = filename.split("?")[0]
            filepath = os.path.join(download_dir, filename)

            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with (
                urllib.request.urlopen(req) as response,
                open(filepath, "wb") as out_file,
            ):
                shutil.copyfileobj(response, out_file)
            return filepath
        except Exception as e:
            logger.error(f"Failed to download direct image {url}: {e}")
            return None

    current_url = url
    max_attempts = 10

    for attempt in range(max_attempts):
        logger.info(
            f"Navigating to image page: {current_url} (Attempt {attempt + 1}/{max_attempts})"
        )
        driver.get(current_url)
        wait = WebDriverWait(driver, wait_time)
        time.sleep(2)  # Give it a moment to fully render

        # Check if 'Extra plan required' or 'plan adicional' is present
        page_text = driver.find_element(By.TAG_NAME, "body").text.lower()
        if "extra plan required" in page_text or "plan adicional" in page_text:
            logger.info(
                "Image requires an extra plan. Looking for 'Similar Images' button..."
            )
            try:
                similar_xpath = "//*[(self::button or self::a) and (contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'similar') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'similares'))]"
                similar_btn = wait.until(
                    EC.element_to_be_clickable((By.XPATH, similar_xpath))
                )
                driver.execute_script("arguments[0].click();", similar_btn)

                # Wait for similar images to load
                logger.info("Waiting for similar images grid...")
                time.sleep(3)

                # Try to click the first image link in the grid
                first_img_xpath = "//*[@data-qa='RelatedFilesGrid']//a[contains(@href, '/photo/') or contains(@href, '/vector/') or contains(@href, '/stock-photo-')]"
                first_img = wait.until(
                    EC.element_to_be_clickable((By.XPATH, first_img_xpath))
                )
                next_url = first_img.get_attribute("href")

                if next_url:
                    current_url = next_url
                    logger.info(f"Found similar image. Retrying with: {current_url}")
                    continue
            except Exception as e:
                logger.warning(f"Failed to find or click similar images: {e}")
                # We will fall through and attempt to download anyway, though it may fail

        # New Step: Select size 'S' before downloading
        logger.info("Attempting to select size 'S'...")
        try:
            # Look for a label that contains a span with 'S' and is part of the price table
            size_s_xpath = "//label[contains(@class, '_VuX60') and .//span[text()='S']]"
            size_s_btn = wait.until(
                EC.element_to_be_clickable((By.XPATH, size_s_xpath))
            )
            driver.execute_script("arguments[0].click();", size_s_btn)
            logger.info("Selected size 'S'.")
            time.sleep(1)
        except Exception as e:
            logger.info(
                f"Could not select size 'S' (it might be already selected or not available): {e}"
            )

        # Check current files in download dir
        existing_files = set(glob.glob(os.path.join(download_dir, "*")))

        try:
            # Find the download or re-download button
            download_xpath = "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'download') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'descargar')]"

            try:
                btn = wait.until(EC.element_to_be_clickable((By.XPATH, download_xpath)))
                driver.execute_script("arguments[0].click();", btn)
                logger.info("Clicked download button.")
            except TimeoutException:
                # Maybe it's a link instead of a button
                link_xpath = "//a[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'download') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'descargar')]"
                btn = wait.until(EC.element_to_be_clickable((By.XPATH, link_xpath)))
                driver.execute_script("arguments[0].click();", btn)
                logger.info("Clicked download link.")

            # Wait for the file to appear in the directory
            logger.info("Waiting for file download to complete...")
            downloaded_file = None
            needs_retry_with_similar = False
            for _ in range(60):  # Wait up to 60 seconds for larger files
                time.sleep(1)

                try:
                    # Check if redirected to a plans page
                    page_text = driver.find_element(By.TAG_NAME, "body").text.lower()
                    if "choose a plan" in page_text or "elige un plan" in page_text:
                        logger.info("Redirected to 'choose a plan' page. Going back...")
                        driver.back()
                        time.sleep(2)
                        needs_retry_with_similar = True
                        break
                except Exception:
                    pass

                current_files = set(glob.glob(os.path.join(download_dir, "*")))
                new_files = current_files - existing_files

                valid_files = [
                    f
                    for f in new_files
                    if not f.endswith(".crdownload") and not f.endswith(".tmp")
                ]

                if valid_files:
                    downloaded_file = valid_files[0]
                    break

            if needs_retry_with_similar:
                logger.info("Looking for 'Similar Images' button after going back...")
                try:
                    similar_xpath = "//*[(self::button or self::a) and (contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'similar') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'similares'))]"
                    similar_btn = wait.until(
                        EC.element_to_be_clickable((By.XPATH, similar_xpath))
                    )
                    driver.execute_script("arguments[0].click();", similar_btn)

                    logger.info("Waiting for similar images grid...")
                    time.sleep(3)

                    first_img_xpath = "//*[@data-qa='RelatedFilesGrid']//a[contains(@href, '/photo/') or contains(@href, '/vector/') or contains(@href, '/stock-photo-')]"
                    first_img = wait.until(
                        EC.element_to_be_clickable((By.XPATH, first_img_xpath))
                    )
                    next_url = first_img.get_attribute("href")

                    if next_url:
                        current_url = next_url
                        logger.info(
                            f"Found similar image. Retrying with: {current_url}"
                        )
                        continue
                except Exception as e:
                    logger.warning(
                        f"Failed to find or click similar images after going back: {e}"
                    )
                    return None

            if downloaded_file:
                logger.info(
                    f"Successfully downloaded: {os.path.basename(downloaded_file)}"
                )
                return downloaded_file
            else:
                logger.error("Download timed out.")
                # We do not retry if download timed out; assume failure.
                return None

        except Exception as e:
            logger.error(f"Failed to trigger download on {current_url}: {e}")
            return None

    logger.error("Exceeded max attempts for finding a downloadable similar image.")
    return None


def run_depositphotos_workflow(driver, course_id):
    """
    Main workflow to read contenidos.json, log into Depositphotos,
    download images, and rename/move them.
    """
    logger.info(f"Starting Depositphotos download workflow for course {course_id}...")

    json_path = os.path.join("assets", str(course_id), "contenidos.json")
    if not os.path.exists(json_path):
        logger.warning(f"File {json_path} not found. Skipping Depositphotos workflow.")
        return False

    with open(json_path, "r", encoding="utf-8") as f:
        try:
            contenidos_data = json.load(f)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse JSON in {json_path}")
            return False

    # Check if there are any deposit photos to download
    has_photos = False
    for week_data in contenidos_data.values():
        if "infografia" in week_data and "deposit_photos" in week_data["infografia"]:
            if len(week_data["infografia"]["deposit_photos"]) > 0:
                has_photos = True
                break

    if not has_photos:
        logger.info("No deposit photos found in contenidos.json.")
        return True

    # Log in
    if not login_depositphotos(driver):
        logger.error("Aborting Depositphotos workflow due to login failure.")
        return False

    # Setup temporary download directory
    target_dir = os.path.abspath(os.path.join("assets", str(course_id)))
    temp_download_dir = os.path.join(target_dir, "temp_downloads")
    configure_download_directory(driver, temp_download_dir)

    # Process each week
    for i in range(1, 9):
        week_name = f"Semana {i}"

        if week_name not in contenidos_data:
            continue

        week_data = contenidos_data[week_name]
        if (
            "infografia" not in week_data
            or "deposit_photos" not in week_data["infografia"]
        ):
            continue

        urls = week_data["infografia"]["deposit_photos"]
        if not urls:
            continue

        logger.info(f"Processing {len(urls)} images for {week_name}...")

        # Track sequence number for renaming
        seq_num = 1

        for url in urls:
            downloaded_path = download_image(driver, url, temp_download_dir)

            if downloaded_path and os.path.exists(downloaded_path):
                # Rename and move the file
                # Extract extension from the downloaded file
                _, ext = os.path.splitext(downloaded_path)
                if not ext:
                    # Default to jpg if no extension (rare but possible)
                    ext = ".jpg"

                # Format: s1_info_01.jpg
                new_filename = f"s{i}_info_{seq_num:02d}{ext}"
                imgs_dir = os.path.join(target_dir, "imgs")
                os.makedirs(imgs_dir, exist_ok=True)
                final_path = os.path.join(imgs_dir, new_filename)

                # Move and overwrite if exists
                shutil.move(downloaded_path, final_path)
                logger.info(f"Moved and renamed to: {new_filename}")

                # Downsize to 500px width (keep proportional) and crop height to 450px if needed
                try:
                    with Image.open(final_path) as img:
                        modified = False
                        orig_width, orig_height = img.size

                        # 1. Proportional resize to 500px width if wider
                        if orig_width > 500:
                            new_height = int(orig_height * 500 / orig_width)
                            img = img.resize((500, new_height), Image.LANCZOS)
                            logger.info(
                                f"Resized {new_filename} from {orig_width}x{orig_height} to 500x{new_height}"
                            )
                            modified = True

                        # 2. Crop height to 450px if still too tall
                        curr_width, curr_height = img.size
                        if curr_height > 380:
                            # Center crop vertically
                            top = (curr_height - 380) // 2
                            bottom = top + 380
                            img = img.crop((0, top, curr_width, bottom))
                            logger.info(
                                f"Cropped {new_filename} to 380px height (from {curr_height}px)"
                            )
                            modified = True

                        if modified:
                            img.save(final_path)
                        else:
                            logger.info(
                                f"Image {new_filename} ({orig_width}x{orig_height}) already fits within 500x450."
                            )
                except Exception as err:
                    logger.warning(f"Could not resize/crop {new_filename}: {err}")

                seq_num += 1
                time.sleep(2)  # Pause between downloads

    # Cleanup temp directory
    try:
        shutil.rmtree(temp_download_dir)
    except Exception as e:
        logger.warning(f"Failed to remove temp directory {temp_download_dir}: {e}")

    logger.info("Completed Depositphotos download workflow.")
    return True
