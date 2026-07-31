import re

with open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# We want to replace each run_* call with a try-except block
# But this might be too complex with regex if they span multiple lines.

# Let's write the helper function at the top of main()
helper_func = '''
def run_safely(driver, course_id, moodle, func_name, func, *args, **kwargs):
    try:
        return func(*args, **kwargs)
    except Exception as e:
        import traceback
        logger.error(f"Error executing {func_name} for course {course_id}: {e}")
        logger.error(traceback.format_exc())
        try:
            from actions.moodle_actions import dismiss_moodle_error_overlays
            dismiss_moodle_error_overlays(driver)
            logger.info(f"Navigating back to course {course_id} home after error...")
            moodle.navigate_to_course(course_id)
        except Exception:
            pass
'''

print(len(content))
