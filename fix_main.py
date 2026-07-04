with open('main.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
in_loop = False
for i, line in enumerate(lines):
    if line.strip() == 'for course_id in courses_to_process:':
        new_lines.append(line)
        new_lines.append('            try:\n')
        in_loop = True
        continue
        
    if in_loop:
        if line.startswith('    except Exception as e:'):
            in_loop = False
            
            # Now we add the loop exception handler BEFORE this outer exception handler
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
            new_lines.append('                    continue\n')
            new_lines.append('\n')
            new_lines.append(line)
            continue
            
        if line.strip() == '' or line.startswith('            #') or line.startswith('        #') or line.strip() == 'continue':
            new_lines.append('    ' + line if line.startswith('        ') else line)
        elif line.startswith('        '):
            new_lines.append('    ' + line)
        else:
            # this shouldn't happen unless loop ended
            in_loop = False
            new_lines.append(line)
    else:
        # We need to remove the broken syntax at the end we accidentally appended
        if line.startswith('        continue') and lines[i-1].strip() == 'finally:':
            # Skip this block from our previous bad powershell edit
            pass
        elif line.startswith('    except Exception as e:') and lines[i+1].strip() == 'import traceback':
            # if we encounter the broken block
            if 'Error processing course' in ''.join(lines[i:i+15]):
                # this is the bad block, skip the next 12 lines
                pass
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)

with open('main.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
