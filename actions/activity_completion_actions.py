import time
import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from actions.moodle_actions import navigate_to_course
from config.settingsSALLE import ConfigSALLE as Config

logger = logging.getLogger(__name__)

def update_activity_completion(driver, course_id: int, wait_time: int = 10):
    """
    Iterates over all 'Actividad' resources in the course and sets their Activity Completion
    conditions to:
    - Add requirements
    - Must receive a grade -> Any grade
    """
    wait = WebDriverWait(driver, wait_time)
    
    logger.info(f"Navigating to course {course_id} to update Activity Completion conditions...")
    if not navigate_to_course(driver, Config.MOODLE_URL, course_id, wait_time):
        logger.error(f"Failed to navigate to course {course_id}.")
        return False
        
    try:
        # Find all activity blocks
        activities = driver.find_elements(By.CSS_SELECTOR, "li.activity")
        activities_to_edit = []
        
        for idx, act in enumerate(activities):
            try:
                name_element = act.find_element(By.CSS_SELECTOR, ".instancename")
                name_text = name_element.text.lower()
                
                # Check if it matches "actividad" (you can adjust the matching logic if needed)
                if "actividad" in name_text and "recurso" not in name_text:
                    activities_to_edit.append(idx)
            except NoSuchElementException:
                continue
        
        if not activities_to_edit:
            logger.info("No 'Actividad' elements found to update completion conditions.")
            return True
            
        logger.info(f"Found {len(activities_to_edit)} 'Actividad' elements to update.")
        
        for act_idx in activities_to_edit:
            # Refresh activities list as DOM might be stale after navigation
            activities = driver.find_elements(By.CSS_SELECTOR, "li.activity")
            if act_idx >= len(activities):
                continue
                
            activity_li = activities[act_idx]
            
            try:
                name_element = activity_li.find_element(By.CSS_SELECTOR, ".instancename")
                activity_name = name_element.text
                logger.info(f"Updating completion conditions for: {activity_name}")
                
                # Click the Edit dropdown
                dropdown_css = "a.dropdown-toggle[title='Editar'], a[aria-label='Editar'], .dropdown-toggle[title='Editar'], .activity-actions .dropdown-toggle, [data-region='action-menu'] .dropdown-toggle, button.dropdown-toggle"
                dropdown_toggle = wait.until(lambda d: activity_li.find_element(By.CSS_SELECTOR, dropdown_css))
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", dropdown_toggle)
                time.sleep(1)
                
                try:
                    dropdown_toggle.click()
                except:
                    driver.execute_script("arguments[0].click();", dropdown_toggle)
                    
                # Click 'Editar ajustes'
                edit_option_xpath = ".//a[contains(@class, 'dropdown-item') and (contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'editar ajustes') or contains(@href, 'modedit.php'))]"
                edit_option = wait.until(lambda d: activity_li.find_element(By.XPATH, edit_option_xpath))
                
                try:
                    wait.until(EC.element_to_be_clickable(edit_option)).click()
                except:
                    driver.execute_script("arguments[0].click();", edit_option)
                    
                # Wait for the settings page to load
                wait.until(EC.presence_of_element_located((By.ID, "region-main")))
                time.sleep(1)
                
                # Expand "Condiciones de finalización de actividad" section if collapsed
                try:
                    completion_header = driver.find_element(By.ID, "id_activitycompletionheader")
                    if "collapsed" in completion_header.get_attribute("class"):
                        completion_header.click()
                        time.sleep(0.5)
                except NoSuchElementException:
                    logger.warning("Activity completion header not found.")
                    
                # 1. Select "Añadir requisitos" (usually value '2') from the completion tracking dropdown or radio button
                try:
                    radio_req = driver.find_elements(By.ID, "id_completion_2")
                    if radio_req:
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", radio_req[0])
                        if not radio_req[0].is_selected():
                            driver.execute_script("arguments[0].click();", radio_req[0])
                        time.sleep(1)
                    else:
                        completion_dropdown = wait.until(EC.presence_of_element_located((By.ID, "id_completion")))
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", completion_dropdown)
                        select = Select(completion_dropdown)
                        select.select_by_value("2")
                        time.sleep(1) # Wait for ajax/DOM update revealing checkboxes
                except Exception as ex:
                    logger.warning(f"Completion dropdown/radio not found or error occurred: {ex}")
                
                # 2. Check "Recibir una calificación" (id_completionusegrade)
                try:
                    use_grade_cb = wait.until(EC.presence_of_element_located((By.ID, "id_completionusegrade")))
                    if not use_grade_cb.is_selected():
                        driver.execute_script("arguments[0].click();", use_grade_cb)
                        time.sleep(0.5)
                except (NoSuchElementException, TimeoutException):
                    logger.warning("Checkbox 'id_completionusegrade' not found.")
                    
                # 3. Select "Cualquier calificación" (id_completionpassgrade_0)
                try:
                    any_grade_radio = driver.find_element(By.ID, "id_completionpassgrade_0")
                    if not any_grade_radio.is_selected():
                        driver.execute_script("arguments[0].click();", any_grade_radio)
                except NoSuchElementException:
                    pass # Might not exist depending on Moodle version
                    
                # Click Save and return to course
                save_btn_css = "#id_submitbutton2, input[name='submitbutton2'], button[name='submitbutton2']"
                save_btn = driver.find_element(By.CSS_SELECTOR, save_btn_css)
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", save_btn)
                time.sleep(0.5)
                driver.execute_script("arguments[0].click();", save_btn)
                
                # Wait to return to the course page
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "body.path-course-view")))
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Error updating completion for activity at index {act_idx}: {e}")
                # Ensure we navigate back to course if something failed in settings page
                if "course/view.php" not in driver.current_url:
                    navigate_to_course(driver, Config.MOODLE_URL, course_id, wait_time)
                continue
                
        logger.info("Successfully finished updating activity completion conditions.")
        return True
        
    except Exception as e:
        logger.error(f"Critical error in update_activity_completion workflow: {e}")
        return False

def run_activity_completion_workflow(driver, course_id: int, wait_time: int = 10):
    return update_activity_completion(driver, course_id, wait_time)
