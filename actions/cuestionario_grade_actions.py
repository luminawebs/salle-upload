import time
import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys

logger = logging.getLogger(__name__)

def update_quiz_grades(driver, activity_name_prefix: str, wait_time: int = 10) -> bool:
    wait = WebDriverWait(driver, wait_time)
    
    try:
        logger.info(f"[{activity_name_prefix}] Updating quiz grades (Max: 5.00)...")
        
        # 1. Update the max grade to 5
        max_grade_input = wait.until(EC.presence_of_element_located((By.ID, "inputmaxgrade")))
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", max_grade_input)
        
        # Clear the input
        max_grade_input.clear()
        # In some cases clear() doesn't trigger events, so we use backspaces as fallback
        max_grade_input.send_keys(Keys.CONTROL + "a")
        max_grade_input.send_keys(Keys.DELETE)
        
        max_grade_input.send_keys("5")
        time.sleep(0.5)
        
        save_btn = driver.find_element(By.CSS_SELECTOR, "input[name='savechanges']")
        try:
            save_btn.click()
        except:
            driver.execute_script("arguments[0].click();", save_btn)
        time.sleep(2)
        
        # 2. Find all questions and update their weights
        edit_icons = driver.find_elements(By.CSS_SELECTOR, "a.editing_maxmark")
        num_questions = len(edit_icons)
        
        if num_questions == 0:
            logger.warning(f"[{activity_name_prefix}] No questions found to update weights.")
            return False
            
        logger.info(f"[{activity_name_prefix}] Found {num_questions} questions. Calculating weights...")
        
        # Calculate weights to ensure they sum exactly to 5.00
        # e.g., 5.00 / 3 = 1.666... -> [1.67, 1.67, 1.66]
        base_weight = round(5.00 / num_questions, 2)
        weights = [base_weight] * num_questions
        
        # Adjust the last one if the sum doesn't perfectly match 5.00
        diff = round(5.00 - sum(weights), 2)
        weights[-1] = round(weights[-1] + diff, 2)
        
        def get_visible_inline_input(d):
            inputs = d.find_elements(By.CSS_SELECTOR, "span.instancemaxmarkcontainer input:not([type='hidden'])")
            for inp in inputs:
                if inp.is_displayed():
                    return inp
            return None
        
        # Now apply the weights
        for idx, weight in enumerate(weights):
            logger.info(f"[{activity_name_prefix}] Updating question {idx+1} weight to {weight}...")
            
            # Refetch because DOM updates after each save (ajax)
            edit_icons_fresh = driver.find_elements(By.CSS_SELECTOR, "a.editing_maxmark")
            if idx >= len(edit_icons_fresh):
                logger.error(f"[{activity_name_prefix}] Could not find edit icon for question {idx+1}.")
                continue
                
            current_edit = edit_icons_fresh[idx]
            
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", current_edit)
            time.sleep(0.5)
            try:
                current_edit.click()
            except:
                driver.execute_script("arguments[0].click();", current_edit)
                
            # Wait for inline input to appear and handle StaleElementReferenceException
            success = False
            for attempt in range(3):
                try:
                    inline_input = WebDriverWait(driver, 5).until(get_visible_inline_input)
                    
                    # Try to clear first using JS to be more robust
                    driver.execute_script("arguments[0].value = '';", inline_input)
                    inline_input.clear()
                    
                    # Also use backspaces as fallback just in case
                    inline_input.send_keys(Keys.CONTROL + "a")
                    inline_input.send_keys(Keys.DELETE)
                    
                    inline_input.send_keys(str(weight))
                    time.sleep(0.5)
                    inline_input.send_keys(Keys.ENTER)
                    
                    # Wait for ajax save (the input should disappear)
                    WebDriverWait(driver, 5).until(
                        EC.invisibility_of_element(inline_input)
                    )
                    time.sleep(1) # Give it an extra second to fully save before next iteration
                    success = True
                    break
                except Exception as ex:
                    if "stale" in str(ex).lower():
                        logger.warning(f"[{activity_name_prefix}] Stale element while editing question {idx+1}. Retrying...")
                        time.sleep(1)
                    else:
                        if attempt == 2:
                            logger.error(f"[{activity_name_prefix}] Failed to update weight for question {idx+1}: {ex}")
                        time.sleep(1)
            
            if not success:
                logger.error(f"[{activity_name_prefix}] Could not successfully update weight for question {idx+1} after retries.")
                
        logger.info(f"[{activity_name_prefix}] Successfully updated all question weights.")
        return True
    except Exception as e:
        logger.error(f"Failed to update quiz grades for {activity_name_prefix}: {e}")
        return False
