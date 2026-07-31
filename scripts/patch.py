with open('main.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
in_loop = False
for i, line in enumerate(lines):
    if line.startswith('from actions.moodle_actions import MoodleAutomation'):
        new_lines.append('from actions.moodle_actions import MoodleAutomation, dismiss_moodle_error_overlays\n')
        new_lines.append('from actions.format_actions import set_custom_sections_format, set_buttons_format\n')
        continue

    if line.strip() == 'for course_id in courses_to_process:':
        new_lines.append(line)
        new_lines.append('            try:\n')
        in_loop = True
        continue
        
    if in_loop:
        if line.startswith('    except Exception as e:'):
            in_loop = False
            # add the inner except block
            new_lines.append('            except Exception as e:\n')
            new_lines.append('                import traceback\n')
            new_lines.append('                logger.error(f"Error processing course {course_id}: {e}")\n')
            new_lines.append('                logger.error(traceback.format_exc())\n')
            new_lines.append('                try:\n')
            new_lines.append('                    dismiss_moodle_error_overlays(driver)\n')
            new_lines.append('                    logger.info(f"Navigating back to course {course_id} home after error...")\n')
            new_lines.append('                    moodle.navigate_to_course(course_id)\n')
            new_lines.append('                except Exception:\n')
            new_lines.append('                    pass\n')
            new_lines.append('                finally:\n')
            new_lines.append('                    continue\n\n')
            new_lines.append(line)
            continue
            
        if line.strip() == 'if not edit_enabled:':
            if 'logger.warning' in lines[i+1]:
                # Insert the format change right after the edit_enabled block
                new_lines.append('    ' + line)
                new_lines.append('    ' + lines[i+1])
                new_lines.append('    ' + lines[i+2])
                new_lines.append('                if getattr(Config, "ENABLE_COURSE_FORMAT_CHANGE", False):\n')
                new_lines.append('                    logger.info("Switching course format to \'Secciones personalizadas\'...")\n')
                new_lines.append('                    set_custom_sections_format(driver, course_id, wait_time=Config.EXPLICIT_WAIT_TIME)\n')
                new_lines.append('                else:\n')
                new_lines.append('                    logger.info("Course format change workflow is disabled via config.")\n')
                lines[i+1] = '' # Clear so we don't process again
                lines[i+2] = ''
                continue

        if line.strip() == 'if getattr(Config, "ENABLE_DEPOSITPHOTOS_DOWNLOAD", False):':
            new_lines.append('                if getattr(Config, "ENABLE_COURSE_FORMAT_CHANGE", False):\n')
            new_lines.append('                    logger.info("Reverting course format back to \'Formato de botones\'...")\n')
            new_lines.append('                    set_buttons_format(driver, course_id, wait_time=Config.EXPLICIT_WAIT_TIME)\n')
            new_lines.append('                else:\n')
            new_lines.append('                    logger.info("Course format revert workflow is disabled via config.")\n')
            new_lines.append('                dismiss_moodle_error_overlays(driver)\n')
            
        # indent all lines inside the loop
        if line.strip() == '':
            new_lines.append(line)
        elif line.startswith('        '):
            new_lines.append('    ' + line)
        else:
            in_loop = False
            new_lines.append(line)
    else:
        if line == '':
            pass
        else:
            new_lines.append(line)

with open('main.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
