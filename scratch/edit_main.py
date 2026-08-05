import re

file_path = "d:/29 LA SALLE/automatizacion_selenium_SALLE-frontend/main.py"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Add import
if "capture_debug_state" not in content:
    content = content.replace("from config.settings import Config", "from config.settings import Config\nfrom core.debug_utils import capture_debug_state")

# Define replacements for successes and errors
replacements = [
    (r"(set_custom_sections_format\(driver, course_id, wait_time=Config.EXPLICIT_WAIT_TIME\))", 
     r"\1\n                        capture_debug_state(driver, course_id, 'set_custom_sections_format', is_error=False)",
     r"logger.error\(f\"Error executing set_custom_sections_format for course {course_id}: {e}\"\)",
     r"capture_debug_state(driver, course_id, 'set_custom_sections_format_error', is_error=True)\n                        logger.error(f\"Error executing set_custom_sections_format for course {course_id}: {e}\")"),

    (r"(run_course_structure_creation_workflow\(driver, course_id, wait_time=Config.EXPLICIT_WAIT_TIME\))", 
     r"\1\n                        capture_debug_state(driver, course_id, 'course_structure_creation', is_error=False)",
     r"logger.error\(f\"Error executing run_course_structure_creation_workflow for course {course_id}: {e}\"\)",
     r"capture_debug_state(driver, course_id, 'course_structure_creation_error', is_error=True)\n                        logger.error(f\"Error executing run_course_structure_creation_workflow for course {course_id}: {e}\")"),
     
    (r"(run_docx_upload_workflow\(driver, course_id, wait_time=getattr\(Config, \"EXPLICIT_WAIT_TIME\", 10\)\))", 
     r"\1\n                        capture_debug_state(driver, course_id, 'docx_upload', is_error=False)",
     r"logger.error\(f\"Error executing run_docx_upload_workflow for course {course_id}: {e}\"\)",
     r"capture_debug_state(driver, course_id, 'docx_upload_error', is_error=True)\n                        logger.error(f\"Error executing run_docx_upload_workflow for course {course_id}: {e}\")"),

    (r"(run_materiales_estudio_workflow\(driver, course_id, wait_time=getattr\(Config, \"EXPLICIT_WAIT_TIME\", 10\)\))", 
     r"\1\n                        capture_debug_state(driver, course_id, 'materiales_estudio', is_error=False)",
     r"logger.error\(f\"Error executing run_materiales_estudio_workflow for course {course_id}: {e}\"\)",
     r"capture_debug_state(driver, course_id, 'materiales_estudio_error', is_error=True)\n                        logger.error(f\"Error executing run_materiales_estudio_workflow for course {course_id}: {e}\")"),

    (r"(run_cuestionario_export_workflow\(driver, course_id, wait_time=getattr\(Config, \"EXPLICIT_WAIT_TIME\", 10\)\))", 
     r"\1\n                        capture_debug_state(driver, course_id, 'cuestionario_export', is_error=False)",
     r"logger.error\(f\"Error executing run_cuestionario_export_workflow for course {course_id}: {e}\"\)",
     r"capture_debug_state(driver, course_id, 'cuestionario_export_error', is_error=True)\n                        logger.error(f\"Error executing run_cuestionario_export_workflow for course {course_id}: {e}\")"),

    (r"(upload_unidades_intro_for_course\(driver, course_id, wait_time=Config.EXPLICIT_WAIT_TIME\))", 
     r"\1\n                        capture_debug_state(driver, course_id, 'unidades_intro_upload', is_error=False)",
     r"logger.error\(f\"Error executing upload_unidades_intro_for_course for course {course_id}: {e}\"\)",
     r"capture_debug_state(driver, course_id, 'unidades_intro_upload_error', is_error=True)\n                        logger.error(f\"Error executing upload_unidades_intro_for_course for course {course_id}: {e}\")"),

    (r"(run_docx_rubrica_upload_workflow\(driver, course_id, wait_time=Config.EXPLICIT_WAIT_TIME\))", 
     r"\1\n                        capture_debug_state(driver, course_id, 'docx_rubrica_upload', is_error=False)",
     r"logger.error\(f\"Error executing run_docx_rubrica_upload_workflow for course {course_id}: {e}\"\)",
     r"capture_debug_state(driver, course_id, 'docx_rubrica_upload_error', is_error=True)\n                        logger.error(f\"Error executing run_docx_rubrica_upload_workflow for course {course_id}: {e}\")"),

    (r"(run_activity_completion_workflow\(\s*driver, course_id, wait_time=Config.EXPLICIT_WAIT_TIME\s*\))", 
     r"\1\n                    capture_debug_state(driver, course_id, 'activity_completion', is_error=False)",
     None, None),  # Activity completion doesn't have an explicit try-except block around it!

    (r"(set_buttons_format\(driver, course_id, wait_time=Config.EXPLICIT_WAIT_TIME\))", 
     r"\1\n                        capture_debug_state(driver, course_id, 'set_buttons_format', is_error=False)",
     r"logger.error\(f\"Error executing set_buttons_format for course {course_id}: {e}\"\)",
     r"capture_debug_state(driver, course_id, 'set_buttons_format_error', is_error=True)\n                        logger.error(f\"Error executing set_buttons_format for course {course_id}: {e}\")"),

    (r"(set_final_buttons_format\(driver, course_id, wait_time=Config.EXPLICIT_WAIT_TIME\))", 
     r"\1\n                        capture_debug_state(driver, course_id, 'set_final_buttons_format', is_error=False)",
     r"logger.error\(f\"Error executing set_final_buttons_format for course {course_id}: {e}\"\)",
     r"capture_debug_state(driver, course_id, 'set_final_buttons_format_error', is_error=True)\n                        logger.error(f\"Error executing set_final_buttons_format for course {course_id}: {e}\")"),
]

for succ_target, succ_repl, err_target, err_repl in replacements:
    content = re.sub(succ_target, succ_repl, content, count=1)
    if err_target:
        content = re.sub(err_target, err_repl, content, count=1)

# also add capture to the main exception block
content = re.sub(
    r"(logger.error\(f\"Error processing course \{course_id\}: \{e\}\"\))",
    r"capture_debug_state(driver, course_id, 'general_course_error', is_error=True)\n                \1",
    content
)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Updated main.py successfully!")
