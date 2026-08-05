import os
import time
from config.settings import Config
import logging

logger = logging.getLogger("debug_utils")

def capture_debug_state(driver, course_id, context, is_error=True):
    """
    Captures a screenshot and HTML source if TESTING_MODE is enabled.
    Saves to workspace/<CourseID>/logs/
    """
    if not getattr(Config, "TESTING_MODE", False):
        return

    try:
        # Prepare directory
        log_dir = os.path.join(Config.WORKSPACE_DIR, str(course_id), "logs")
        os.makedirs(log_dir, exist_ok=True)

        timestamp = time.strftime("%Y%m%d-%H%M%S")
        prefix = "error" if is_error else "success"
        
        # Save screenshot
        screenshot_path = os.path.join(log_dir, f"{prefix}_{context}_{timestamp}.png")
        driver.save_screenshot(screenshot_path)
        
        # Save HTML source
        html_path = os.path.join(log_dir, f"{prefix}_{context}_{timestamp}.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(driver.page_source)
            
        logger.info(f"Saved debug state ({prefix}) to {log_dir} for context: {context}")
    except Exception as e:
        logger.error(f"Failed to capture debug state for {context}: {e}")
