import re

with open('main.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

out_lines = []
helper_added = False

for i, line in enumerate(lines):
    if line.startswith('def main():') and not helper_added:
        # Add helper function right before main
        out_lines.append('''
def run_workflow_safely(driver, course_id, moodle, workflow_name, workflow_func, *args, **kwargs):
    try:
        workflow_func(*args, **kwargs)
    except Exception as e:
        import traceback
        logger.error(f"Error executing {workflow_name} for course {course_id}: {e}")
        logger.error(traceback.format_exc())
        try:
            from actions.moodle_actions import dismiss_moodle_error_overlays
            dismiss_moodle_error_overlays(driver)
            logger.info(f"Navigating back to course {course_id} home after {workflow_name} error...")
            moodle.navigate_to_course(course_id)
        except Exception as inner_e:
            logger.warning(f"Failed to recover after {workflow_name} error: {inner_e}")
''')
        helper_added = True
    
    # We will look for lines like:
    # run_docx_upload_workflow(driver, course_id, wait_time=getattr(Config, "EXPLICIT_WAIT_TIME", 10))
    # and replace them with:
    # run_workflow_safely(driver, course_id, moodle, "run_docx_upload_workflow", run_docx_upload_workflow, driver, course_id, wait_time=getattr(Config, "EXPLICIT_WAIT_TIME", 10))
    
    match = re.match(r'^(\s+)(run_[a-zA-Z0-9_]+|upload_[a-zA-Z0-9_]+|rename_[a-zA-Z0-9_]+|update_[a-zA-Z0-9_]+|set_[a-zA-Z0-9_]+|clear_[a-zA-Z0-9_]+)\((.*)\)\s*$', line)
    
    if match and "run_workflow_safely" not in line and "run_generar" not in line and not line.strip().startswith('def '):
        indent = match.group(1)
        func_name = match.group(2)
        args = match.group(3)
        
        if func_name in ['run_docx_parsing_workflow', 'run_docx_splitting_workflow', 'run_unidades_intro_splitting_workflow']:
            # These don't take driver/moodle, they just take course_id usually
            # But let's just use try/except block instead of helper for these to be safe, or just skip them?
            # They don't interact with Moodle UI directly (they parse local files), so they won't need navigation recovery.
            out_lines.append(line)
            continue
            
        # The helper expects driver, course_id, moodle.
        # But wait, not all functions have driver and course_id in the exact same way. 
        # So wrapping the line in try-except is MUCH safer.
        
        out_lines.append(f"{indent}try:\n")
        out_lines.append(f"{indent}    {func_name}({args})\n")
        out_lines.append(f"{indent}except Exception as e:\n")
        out_lines.append(f"{indent}    import traceback\n")
        out_lines.append(f"{indent}    logger.error(f\"Error executing {func_name} for course {{course_id}}: {{e}}\")\n")
        out_lines.append(f"{indent}    logger.error(traceback.format_exc())\n")
        out_lines.append(f"{indent}    try:\n")
        out_lines.append(f"{indent}        dismiss_moodle_error_overlays(driver)\n")
        out_lines.append(f"{indent}        logger.info(f\"Navigating back to course {{course_id}} home after error...\")\n")
        out_lines.append(f"{indent}        moodle.navigate_to_course(course_id)\n")
        out_lines.append(f"{indent}    except Exception:\n")
        out_lines.append(f"{indent}        pass\n")
    else:
        out_lines.append(line)

with open('main_patched.py', 'w', encoding='utf-8') as f:
    f.writelines(out_lines)
