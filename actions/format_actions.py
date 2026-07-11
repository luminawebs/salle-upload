import logging
import time

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import TimeoutException

from config.settingsSALLE import ConfigSALLE as Config

logger = logging.getLogger(__name__)

def _change_course_format(driver, course_id, wait_time, target_format_value, format_name):
    """
    Helper function to change the course format.
    """
    wait = WebDriverWait(driver, wait_time)
    # The Moodle course settings URL
    edit_url = f"{Config.MOODLE_URL}/course/edit.php?id={course_id}"
    logger.info(f"Navigating to course settings to set format to '{format_name}' (course {course_id})...")
    
    driver.get(edit_url)
    
    try:
        # 1. Wait for page to load
        wait.until(EC.presence_of_element_located((By.ID, "id_courseformathdrcontainer")))
        
        # 2. Check if the 'Formato de curso' section is expanded. If not, expand it.
        wait.until(EC.presence_of_element_located((By.ID, "id_courseformathdrcontainer")))
        # Check aria-expanded on the toggle link
        toggle_link = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "a[aria-controls='id_courseformathdrcontainer']")))
        if str(toggle_link.get_attribute("aria-expanded")).lower() == "false":
            logger.info("Expanding 'Formato de curso' section...")
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", toggle_link)
            time.sleep(0.5)
            driver.execute_script("arguments[0].click();", toggle_link)
            time.sleep(1) # wait for animation
            
        # 3. Select the target format from the dropdown
        format_select_element = wait.until(EC.presence_of_element_located((By.ID, "id_format")))
        select = Select(format_select_element)
        
        # First, try to see if the current selected option matches either the value or the text
        current_option = select.first_selected_option
        current_text = current_option.get_attribute("textContent") or ""
        already_selected = (current_option.get_attribute("value") == target_format_value) or \
                           (format_name.lower() in current_text.lower())
        
        if not already_selected:
            # Check for Moodle 4.x custom dropdown elements first
            custom_option_css = f"a[data-form-controls='id_format'][data-value='{target_format_value}']"
            custom_options = driver.find_elements(By.CSS_SELECTOR, custom_option_css)
            if custom_options:
                logger.info(f"Found Moodle custom dropdown for '{target_format_value}'. Clicking via JS...")
                driver.execute_script("arguments[0].click();", custom_options[0])
            else:
                try:
                    # Try selecting by value first
                    select.select_by_value(target_format_value)
                except Exception:
                    logger.info(f"Could not select by value '{target_format_value}'. Falling back to visible text '{format_name}'...")
                    matched = False
                    for option in select.options:
                        opt_text = option.get_attribute("textContent") or ""
                        if format_name.lower() in opt_text.lower():
                            opt_value = option.get_attribute("value")
                            try:
                                select.select_by_value(opt_value)
                            except Exception:
                                # Standard Select fails if select is hidden; force via JS
                                logger.info(f"Select native failed for hidden option '{opt_value}', forcing via JS...")
                                driver.execute_script("""
                                    arguments[0].value = arguments[1];
                                    arguments[0].dispatchEvent(new Event('change'));
                                """, format_select_element, opt_value)
                            matched = True
                            break
                    if not matched:
                        raise Exception(f"Could not find any format option matching value '{target_format_value}' or text '{format_name}'")
            # Wait for the select element to become stale (Moodle reloads the page/form when format changes)
            try:
                logger.info("Waiting for page/form reload after format change...")
                WebDriverWait(driver, 10).until(EC.staleness_of(format_select_element))
                
                # Wait for the new form to be ready by checking for the format select again
                wait.until(EC.presence_of_element_located((By.ID, "id_format")))
                time.sleep(1) # small buffer just in case
            except TimeoutException:
                logger.warning("No staleness detected after format change. Proceeding anyway.")
                time.sleep(3)
        else:
            logger.info(f"Format is already '{format_name}'.")
        
        # 4. Save changes
        # Add a hard sleep to allow all Moodle form AJAX to completely settle
        time.sleep(3)
        
        # Helper function to fetch the correct button
        def get_save_btn():
            if already_selected:
                logger.info("[FORMAT_SAVE] Format already selected, finding 'Guardar cambios y mostrar' (id_saveanddisplay)...")
                return wait.until(EC.element_to_be_clickable((By.ID, "id_saveanddisplay")))
            else:
                try:
                    logger.info("[FORMAT_SAVE] Finding 'Guardar y volver' (id_saveandreturn)...")
                    return WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.ID, "id_saveandreturn")))
                except TimeoutException:
                    logger.info("[FORMAT_SAVE] 'Guardar y volver' not found within 5s, falling back to 'Guardar cambios y mostrar'...")
                    return wait.until(EC.element_to_be_clickable((By.ID, "id_saveanddisplay")))
        
        try:
            logger.info("[FORMAT_SAVE] Attempting to fetch save button...")
            save_btn = get_save_btn()
            logger.info(f"[FORMAT_SAVE] Successfully found save button. ID: {save_btn.get_attribute('id')}, Value: {save_btn.get_attribute('value')}")
            
            logger.info("[FORMAT_SAVE] Scrolling button into view...")
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", save_btn)
            time.sleep(1)
            
            logger.info("[FORMAT_SAVE] Executing native click()...")
            save_btn.click()
            logger.info("[FORMAT_SAVE] Native click() executed without throwing an exception.")
        except Exception as click_err:
            logger.warning(f"[FORMAT_SAVE] Normal click failed: {type(click_err).__name__} - {click_err}")
            logger.info("[FORMAT_SAVE] Re-fetching button and trying JS click...")
            try:
                save_btn = get_save_btn()
                logger.info(f"[FORMAT_SAVE] Re-fetched save button. ID: {save_btn.get_attribute('id')}")
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", save_btn)
                time.sleep(0.5)
                logger.info("[FORMAT_SAVE] Executing JavaScript click...")
                driver.execute_script("arguments[0].click();", save_btn)
                logger.info("[FORMAT_SAVE] JavaScript click executed.")
            except Exception as js_err:
                logger.error(f"[FORMAT_SAVE] JavaScript click fallback also failed: {type(js_err).__name__} - {js_err}")
                raise js_err
            
        # Wait for the save button to become stale, which means the page is navigating away
        try:
            logger.info("[FORMAT_SAVE] Waiting up to 15s for form submission to process (staleness of button)...")
            WebDriverWait(driver, 15).until(EC.staleness_of(save_btn))
            logger.info("[FORMAT_SAVE] Button is now stale! Navigation has started.")
        except TimeoutException:
            logger.warning("[FORMAT_SAVE] Save button did NOT become stale after 15s. Either form validation failed, or Moodle uses AJAX for saving without reloading.")
            
        # Wait until we are redirected back to the course view
        try:
            logger.info("[FORMAT_SAVE] Waiting for body.path-course-view to confirm redirect to course page...")
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "body.path-course-view")))
            logger.info("[FORMAT_SAVE] Redirect confirmed. Successfully on course view.")
        except TimeoutException:
            logger.warning("[FORMAT_SAVE] Did not find body.path-course-view within explicit wait time. Proceeding anyway.")
            
        logger.info(f"Successfully changed format to '{format_name}'.")
        return True
        
    except TimeoutException:
        logger.error(f"Timeout while trying to change course format to '{format_name}'")
        return False
    except Exception as e:
        logger.error(f"Error changing course format: {e}")
        return False

def set_custom_sections_format(driver, course_id, wait_time=5):
    """
    Changes the course format to 'Secciones personalizadas' (customsections).
    """
    # Assuming the value in the select is 'customsections'.
    # If it's something else, we will need to verify the actual value.
    return _change_course_format(driver, course_id, wait_time, "customsections", "Secciones personalizadas")

def set_buttons_format(driver, course_id, wait_time=5):
    """
    Changes the course format to 'Formato de botones' (buttons).
    """
    # Assuming the value in the select is 'buttons'.
    return _change_course_format(driver, course_id, wait_time, "buttons", "Formato de botones")
