"""
configuracion_final_actions.py
------------------------------
Automates the deletion of specific template items containing "VIR" 
from the Moodle course main page.
"""

import logging
import time

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException

from actions.moodle_actions import navigate_to_course
from config.settings import Config

logger = logging.getLogger(__name__)

def delete_activity_by_element(driver, wait, activity_element, activity_name) -> bool:
    """
    Given an activity element, clicks its action menu, clicks 'Borrar', and confirms.
    Returns True if successfully deleted.
    """
    try:
        # Find the action menu toggle inside this activity
        # Moodle 4 usually uses data-toggle="dropdown" or class "dropdown-toggle"
        dropdown_toggle = activity_element.find_element(By.CSS_SELECTOR, "a.dropdown-toggle, button.dropdown-toggle")
        
        # Scroll into view
        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", dropdown_toggle)
        time.sleep(1)
        
        # Click the dropdown toggle
        logger.info(f"  [{activity_name}] Clicking action menu...")
        driver.execute_script("arguments[0].click();", dropdown_toggle)
        time.sleep(1)
        
        # Wait for the dropdown menu to be visible and find the 'Borrar' / 'Delete' option
        # Moodle classes: .editing_delete or .text-danger
        delete_btn = None
        
        # We search inside the activity_element's dropdown menu (which might be appended to the body or inside the item)
        # Often it's safer to just search the whole DOM for the visible 'Borrar' link that has data-action="delete"
        delete_links = driver.find_elements(By.XPATH, "//a[contains(@data-action, 'delete') or contains(@class, 'editing_delete') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'borrar') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'delete')]")
        
        for link in delete_links:
            if link.is_displayed():
                delete_btn = link
                break
                
        if not delete_btn:
            logger.warning(f"  [{activity_name}] Could not find 'Borrar' option in the menu.")
            return False
            
        logger.info(f"  [{activity_name}] Clicking 'Borrar'...")
        driver.execute_script("arguments[0].click();", delete_btn)
        
        # Wait for the confirmation modal and click the confirm button
        logger.info(f"  [{activity_name}] Waiting for confirmation modal...")
        confirm_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//div[contains(@class, 'modal-footer')]//button[@data-action='delete' or @data-action='confirm' or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'borrar') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'sí') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'yes')]")))
        
        logger.info(f"  [{activity_name}] Confirming deletion...")
        try:
            confirm_btn.click()
        except:
            driver.execute_script("arguments[0].click();", confirm_btn)
        
        # Wait a bit for the deletion ajax to complete, then reload the page
        # Reloading guarantees the DOM is clean of leftover hidden modals and stale elements
        time.sleep(3)
        driver.refresh()
        
        # Wait for page to be ready again
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "li.activity, div.activity-item")))
        return True
        
    except Exception as e:
        logger.error(f"  [{activity_name}] Error during deletion: {e}")
        return False


def run_configuracion_final_workflow(driver, course_id: int, wait_time: int = 10):
    """
    Main entry point for the Configuracion Final workflow.
    Finds and deletes all activities containing "VIR".
    """
    wait = WebDriverWait(driver, wait_time)
    
    logger.info(f"Starting CONFIGURACION FINAL workflow for course {course_id}...")
    
    # 1. Navigate to course
    navigate_to_course(driver, Config.MOODLE_URL, course_id, wait_time)
    
    # Let the page fully load
    time.sleep(3)
    
    deleted_count = 0
    
    # We will loop because the DOM might change after each deletion
    while True:
        # Find all activities on the page
        # Moodle 4 usually has div.activity-item or li.activity
        activities = driver.find_elements(By.CSS_SELECTOR, "li.activity, div.activity-item")
        
        target_activity = None
        target_name = ""
        
        for activity in activities:
            try:
                # Find the name of the activity
                name_elem = activity.find_element(By.CSS_SELECTOR, "a.aalink, span.instancename, a.instancename")
                name_text = name_elem.text.strip()
                
                # Check if it contains "VIR"
                if "VIR" in name_text:
                    target_activity = activity
                    target_name = name_text
                    break
            except StaleElementReferenceException:
                # DOM changed, break to re-query
                break
            except Exception:
                # Some activities might not have names formatted this way (e.g., labels)
                # Try fallback: get raw text of the whole activity wrapper
                if "VIR" in activity.text:
                    target_activity = activity
                    target_name = "Unknown VIR item"
                    break
                    
        if target_activity:
            logger.info(f"Found item to delete: {target_name}")
            success = delete_activity_by_element(driver, wait, target_activity, target_name)
            if success:
                deleted_count += 1
            else:
                logger.error(f"Failed to delete {target_name}. Stopping to prevent infinite loop.")
                break
        else:
            # No more VIR items found
            break

    logger.info(f"CONFIGURACION FINAL workflow completed. Total items deleted: {deleted_count}")
