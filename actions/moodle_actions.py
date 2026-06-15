import os
import time
import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from config.settings import Config

logger = logging.getLogger(__name__)


def login(driver, username, password, login_url, wait_time=10):
    """
    Reusable Selenium function to log into a Moodle platform.
    Returns: bool (True if successful, False otherwise)

    SELECTOR ADAPTATION:
    - Robust selectors: We use By.ID ('username', 'password', 'loginbtn') because they are
      the most stable and natively used in Moodle. Avoid long brittle XPaths.
    - If a custom Moodle theme breaks this, adapt by targeting 'name' attributes
      (e.g., By.NAME, "username") or unique placeholders (By.CSS_SELECTOR, "input[type='password']").

    STRATEGY TO DEBUG IF LOGIN FAILS:
    1. Screenshots: Take a picture right when it fails: `driver.save_screenshot('debug_error.png')`.
       This immediately reveals CAPTCHAs, maintenance pages, or SSO redirects (Microsoft/Google).
    2. Check Page Source: Log `driver.page_source` to verify if the IDs genuinely changed.
    3. Network Latency: Temporarily increase `wait_time` in case the redirect is just very slow.
    """
    wait = WebDriverWait(driver, wait_time)
    logger.info("Navigating to Moodle login page...")

    # Retry mechanism for network issues like ERR_NETWORK_CHANGED
    login_page_ready = False
    for attempt in range(4):
        try:
            logger.info(f"  Loading login page (attempt {attempt + 1})...")
            driver.get(login_url)

            # Wait up to wait_time seconds for DOM to be at least interactive
            try:
                WebDriverWait(driver, wait_time).until(
                    lambda d: d.execute_script("return document.readyState") in ["interactive", "complete"]
                )
            except TimeoutException:
                logger.warning(f"  readyState timeout on attempt {attempt + 1}, current URL: {driver.current_url}")
                take_screenshot(driver, f"login_load_timeout_{attempt + 1}")
                time.sleep(3)
                continue

            page_source = driver.page_source or ""
            current_url = driver.current_url

            # Check for Chrome network error pages
            if any(err in page_source for err in ["ERR_NETWORK_CHANGED", "ERR_CONNECTION", "ERR_NAME_NOT_RESOLVED"]):
                logger.warning(f"  Chrome network error on attempt {attempt + 1} (URL: {current_url}), retrying in 5s...")
                take_screenshot(driver, f"login_network_err_{attempt + 1}")
                time.sleep(5)
                continue

            # Check that we're actually on the login page
            if "username" not in page_source and "loginbtn" not in page_source:
                logger.warning(f"  Login form not found on attempt {attempt + 1} (URL: {current_url}), retrying...")
                take_screenshot(driver, f"login_no_form_{attempt + 1}")
                time.sleep(3)
                continue

            login_page_ready = True
            logger.info(f"  Login page loaded successfully (URL: {current_url})")
            break

        except Exception as e:
            logger.warning(f"  Exception loading login page on attempt {attempt + 1}: {e}")
            if attempt >= 3:
                raise
            time.sleep(4)

    if not login_page_ready:
        logger.error("  Could not load the Moodle login page after 4 attempts.")
        driver.save_screenshot("login_error.png")
        return False

    try:
        # Interact with the elements securely
        # Moodle attaches JS to the login form. If we type immediately,
        # the inputs can be cleared or become stale midway (StaleElementReferenceException)
        time.sleep(1.5)

        # Re-fetch the elements right before interaction to bypass StaleElement exceptions
        username_input = wait.until(EC.presence_of_element_located((By.ID, "username")))
        username_input.clear()
        username_input.send_keys(username)

        time.sleep(0.5)
        password_input = wait.until(EC.presence_of_element_located((By.ID, "password")))
        password_input.clear()
        password_input.send_keys(password)

        # Wait for login button to be clickable, then click
        login_button = wait.until(EC.element_to_be_clickable((By.ID, "loginbtn")))
        login_button.click()

        # Wait a bit for response (either success or error)
        time.sleep(2)

        # Detect Moodle login error message
        error_elements = driver.find_elements(
            By.CSS_SELECTOR, ".alert-danger, .loginerrors"
        )

        if any(el.is_displayed() for el in error_elements):
            logger.error("Login failed: Moodle returned 'Acceso inválido'")
            take_screenshot(driver, "login_invalid")
            return False

        # Verify login success by checking for a post-login authenticated element
        # Wait for URL change OR dashboard-like page
        wait.until(lambda d: "/login" not in d.current_url)

        if "login/index.php" in driver.current_url:
            logger.error("Still on login page → credentials likely rejected")
            take_screenshot(driver, "login_failed")
            return False

        logger.info("Successfully logged into Moodle.")
        return True

    except TimeoutException:
        logger.error(
            f"Failed to login to Moodle. Selectors not found or page took too long. Current URL: {driver.current_url}"
        )
        driver.save_screenshot("login_error.png")
        return False
    except Exception as e:
        logger.error(f"Unexpected error during Moodle login: {e}")
        return False


def take_screenshot(driver, name_prefix):
    """
    Safely captures a screenshot for debugging purposes.
    """
    os.makedirs("screenshots", exist_ok=True)
    timestamp = int(time.time())
    filename = f"screenshots/{name_prefix}_{timestamp}.png"
    try:
        driver.save_screenshot(filename)
        logger.info(f"Screenshot saved to {filename}")
    except Exception as e:
        logger.error(f"Failed to save screenshot {filename}: {e}")


def build_course_url(base_url, course_id):
    """
    Helper function to dynamically construct the Moodle course URL.
    Ensures safe joining of the base URL and course endpoint.
    """
    clean_base = base_url.rstrip("/")
    return f"{clean_base}/course/view.php?id={course_id}"


def navigate_to_course(driver, base_url, course_id, wait_time=10):
    wait = WebDriverWait(driver, wait_time)
    target_url = build_course_url(base_url, course_id)

    logger.info(f"Navigating to course ID {course_id}")

    # Retry the navigation up to 3 times in case of renderer or network timeouts
    for attempt in range(3):
        try:
            driver.get(target_url)
        except Exception as nav_err:
            # A TimeoutException or renderer timeout from driver.get() is NOT always fatal:
            # with page_load_timeout, Chrome may still have loaded the DOM.
            err_str = str(nav_err)
            if "timeout" in err_str.lower() or "renderer" in err_str.lower():
                logger.warning(
                    f"  Page load timeout on attempt {attempt + 1} for course {course_id} "
                    f"(URL: {target_url}) — checking if DOM is usable..."
                )
            else:
                logger.warning(f"  Navigation error on attempt {attempt + 1}: {nav_err}")

        try:
            # 1. Detect redirect to login
            current_url = driver.current_url
            if "login/index.php" in current_url:
                logger.error(f"Redirected to login. Session invalid for course {course_id}")
                take_screenshot(driver, f"login_redirect_{course_id}")
                return False

            # 2. Wait for main structure (shorter wait — page may already be loaded)
            try:
                WebDriverWait(driver, min(wait_time, 15)).until(
                    EC.presence_of_element_located((By.ID, "region-main"))
                )
            except TimeoutException:
                # region-main not found — check if we at least have some course content
                page_source = driver.page_source or ""
                if "course-view" not in page_source and "region-main" not in page_source:
                    logger.warning(f"  region-main not found on attempt {attempt + 1}, retrying...")
                    take_screenshot(driver, f"course_load_fail_{course_id}_{attempt + 1}")
                    time.sleep(3)
                    continue
                logger.warning(f"  region-main wait timed out but page source looks valid, proceeding...")

            # 3. Confirm it's actually a course page
            try:
                body = driver.find_element(By.TAG_NAME, "body")
                body_classes = body.get_attribute("class") or ""
            except Exception:
                body_classes = ""

            if "course-view" not in body_classes:
                logger.warning(f"  Not a valid course-view page on attempt {attempt + 1} (classes: '{body_classes[:80]}')")
                if attempt < 2:
                    time.sleep(3)
                    continue
                logger.error(f"Not a valid course view page for {course_id} after {attempt + 1} attempts")
                take_screenshot(driver, f"invalid_course_{course_id}")
                return False

            # 4. Detect Moodle error messages
            error_elements = driver.find_elements(
                By.CSS_SELECTOR, ".alert-danger, .errormessage"
            )
            if any(el.is_displayed() for el in error_elements):
                logger.error(f"Moodle error message detected in course {course_id}")
                take_screenshot(driver, f"moodle_error_{course_id}")
                return False

            logger.info(f"Course {course_id} loaded successfully")
            return True

        except Exception as e:
            err_str = str(e)
            logger.error(f"  Unexpected error navigating to course {course_id} (attempt {attempt + 1}): {err_str[:200]}")
            try:
                _ = driver.window_handles
                take_screenshot(driver, f"exception_{course_id}_{attempt + 1}")
            except Exception:
                logger.error(f"  Browser window no longer accessible.")
                return False
            if attempt < 2:
                time.sleep(3)
                continue

    logger.error(f"Failed to navigate to course {course_id} after 3 attempts.")
    return False


class MoodleAutomation:
    def __init__(self, driver):
        self.driver = driver
        # Explicit wait setup to be used across all actions
        self.wait = WebDriverWait(self.driver, Config.EXPLICIT_WAIT_TIME)

    def login(self, username, password):
        """
        Class wrapper for the robust standalone login function.
        """
        login_url = f"{Config.MOODLE_URL}/login/index.php"
        return login(
            self.driver, username, password, login_url, Config.EXPLICIT_WAIT_TIME
        )

    def navigate_to_course(self, course_id):
        """
        Class wrapper for the standalone navigate_to_course function.
        """
        return navigate_to_course(
            self.driver, Config.MOODLE_URL, course_id, Config.EXPLICIT_WAIT_TIME
        )

def upload_moodle_wysiwyg(driver, course_id, week_name, resource_name, html_content, wait_time=10):
    """
    Uploads the provided HTML content to the specified resource's WYSIWYG editor.
    """
    wait = WebDriverWait(driver, wait_time)
    logger.info(f"Uploading content to '{resource_name}' in '{week_name}'")
    
    try:
        if "course/view.php" not in driver.current_url:
            navigate_to_course(driver, Config.MOODLE_URL, course_id, wait_time)

        try:
            try:
                alert = driver.switch_to.alert
                logger.warning(f"Unexpected alert found: {alert.text}. Dismissing.")
                alert.dismiss()
            except:
                pass

            quick_wait = WebDriverWait(driver, 5)
            section_xpath = f"//li[contains(@class, 'section')][descendant::*[contains(@class, 'sectionname') or self::h3 or self::h4][contains(., '{week_name}')]]"
            section_li = quick_wait.until(EC.presence_of_element_located((By.XPATH, section_xpath)))
        except TimeoutException:
            logger.warning(f"Section '{week_name}' not found. Verify if sections were renamed correctly.")
            return False

        activity_xpath = f".//li[contains(@class, 'activity')]//*[contains(@class, 'instancename') and contains(text(), '{resource_name}')]"
        try:
            activity_title = section_li.find_element(By.XPATH, activity_xpath)
        except Exception:
            logger.warning(f"Resource '{resource_name}' not found in '{week_name}'.")
            return False
            
        activity_li = activity_title.find_element(By.XPATH, "./ancestor::li[contains(@class, 'activity')]")
        
        dropdown_toggle = activity_li.find_element(By.CSS_SELECTOR, "a.dropdown-toggle[title='Editar'], a[aria-label='Editar']")
        try:
            wait.until(EC.element_to_be_clickable(dropdown_toggle)).click()
        except:
            driver.execute_script("arguments[0].click();", dropdown_toggle)
            
        edit_option_xpath = ".//a[contains(@class, 'dropdown-item') and (contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'editar ajustes') or contains(@href, 'modedit.php'))]"
        edit_option = wait.until(lambda d: activity_li.find_element(By.XPATH, edit_option_xpath))
        edit_href = edit_option.get_attribute("href")
        
        original_window = driver.current_window_handle
        use_new_tab = (Config.ENABLE_INFOGRAFIA_EXPORT or Config.ENABLE_FORO_EXPORT) and edit_href
        
        if use_new_tab:
            driver.execute_script("window.open(arguments[0], '_blank');", edit_href)
            for window_handle in driver.window_handles:
                if window_handle != original_window:
                    driver.switch_to.window(window_handle)
                    break
        else:
            try:
                wait.until(EC.element_to_be_clickable(edit_option)).click()
            except:
                driver.execute_script("arguments[0].click();", edit_option)
            
        logger.info("Waiting for resource settings page to load...")
        submit_btn_css = "#id_submitbutton, input[name='submitbutton'], button[name='submitbutton']"
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, submit_btn_css)))
        
        try:
            textarea = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, "textarea[name='page[text]']")))
            textarea_css = "textarea[name='page[text]']"
            logger.info("Found 'Contenido de la página' (page[text]) field.")
        except TimeoutException:
            textarea = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, "textarea[name='introeditor[text]']")))
            textarea_css = "textarea[name='introeditor[text]']"
            logger.info("Found 'Descripción' (introeditor[text]) field.")
            
        try:
            driver.execute_script("arguments[0].value = arguments[1];", textarea, html_content)
            
            try:
                editor_script = """
                    var textarea = arguments[0];
                    var container = textarea.closest('.form-group, .felement, .fitem, div');
                    if (container) {
                        var atto = container.querySelector('.editor_atto_content');
                        if (atto) return {element: atto, type: 'atto'};
                        var tiny = container.querySelector('.tox-edit-area__iframe');
                        if (tiny) return {element: tiny, type: 'tiny'};
                    }
                    return null;
                """
                editor_info = driver.execute_script(editor_script, textarea)
                
                if editor_info:
                    editor_el = editor_info['element']
                    if editor_info['type'] == 'tiny':
                        driver.execute_script("arguments[0].contentDocument.body.innerHTML = arguments[1];", editor_el, html_content)
                        logger.info("Content set in TinyMCE editor for specific textarea.")
                    else:
                        driver.execute_script("arguments[0].innerHTML = arguments[1];", editor_el, html_content)
                        logger.info("Content set in Atto editor for specific textarea.")
                else:
                    logger.info("Specific visual editor not found for textarea, updated textarea directly.")
                    
            except Exception as e:
                logger.info(f"Could not interact with visual editor: {e}")
                
            driver.execute_script(
                "var event = new Event('change', { bubbles: true });"
                "arguments[0].dispatchEvent(event);"
                "var inputEvent = new Event('input', { bubbles: true });"
                "arguments[0].dispatchEvent(inputEvent);"
                "if (typeof M !== 'undefined' && M.editor_atto) { "
                "  var container = arguments[0].closest('.form-group, .felement, .fitem, div');"
                "  if (container) {"
                "    var atto = container.querySelector('.editor_atto_content');"
                "    if (atto && M.editor_atto.getEditor) { "
                "      var editor = M.editor_atto.getEditor(atto.id); "
                "      if (editor) { editor.updateFromTextArea(); } "
                "    }"
                "  }"
                "} ",
                textarea
            )
            time.sleep(2)
        except Exception as e:
            logger.error(f"Failed to set editor content: {e}")
            return False
            
        logger.info("Saving changes...")
        try:
            submit_btn = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, submit_btn_css)))
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", submit_btn)
            time.sleep(1)
            driver.execute_script("arguments[0].click();", submit_btn)
        except Exception as e:
            logger.error(f"Could not find or click save button: {e}")
            if use_new_tab:
                driver.close()
                driver.switch_to.window(original_window)
            return False
            
        if use_new_tab:
            try:
                save_wait = WebDriverWait(driver, 30)
                save_wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "body.path-course-view, #region-main")))
            except TimeoutException:
                pass
            driver.close()
            driver.switch_to.window(original_window)
            logger.info(f"Successfully uploaded content to '{week_name}'.")
            return True
        else:
            try:
                save_wait = WebDriverWait(driver, 40)
                save_wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "body.path-course-view, #region-main")))
                logger.info(f"Successfully uploaded content to '{week_name}'.")
                return True
            except TimeoutException:
                if "course/view.php" in driver.current_url:
                    logger.info(f"Redirection detected via URL for '{week_name}'.")
                    return True
                logger.error(f"Timeout waiting for redirection after saving '{week_name}'.")
                return False

    except Exception as e:
        logger.error(f"Error during upload to '{week_name}': {e}")
        try:
            if "original_window" in locals() and "use_new_tab" in locals() and use_new_tab:
                if driver.current_window_handle != original_window:
                    driver.close()
                    driver.switch_to.window(original_window)
        except Exception:
            pass
        return False

