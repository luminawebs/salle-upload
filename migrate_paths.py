import os
import re

def replace_in_file(filepath, replacements):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    new_content = content
    for old, new in replacements:
        new_content = new_content.replace(old, new)
        
    if new_content != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Updated {filepath}")

# server.py replacements
replace_in_file("server.py", [
    ('os.makedirs("assets", exist_ok=True)', 'os.makedirs("workspace", exist_ok=True)'),
    ('os.path.join("assets", course_id)', 'os.path.join("workspace", course_id)'),
    ('os.path.join("assets", TEMP_COURSE_ID)', 'os.path.join("workspace", TEMP_COURSE_ID)'),
    ('os.path.join("assets", cid', 'os.path.join("workspace", cid'),
    ('os.listdir("assets")', 'os.listdir("workspace")'),
    ('os.path.join("assets", filename)', 'os.path.join("workspace", filename)')
])

# core/data_parser.py
replace_in_file("core/data_parser.py", [
    ('os.path.join("assets", str(course_id))', 'os.path.join("workspace", str(course_id))'),
    ('os.path.join("assets", str(course_id), "imgs")', 'os.path.join("workspace", str(course_id), "imgs")'),
    ('saved to assets/', 'saved to workspace/'),
    ('Reads assets/', 'Reads workspace/')
])

# core/unidades_intro_parser.py
replace_in_file("core/unidades_intro_parser.py", [
    ('os.path.join(base_dir, "assets", str(course_id))', 'os.path.join(base_dir, "workspace", str(course_id))')
])

# core/docx_rubrica_parser.py
replace_in_file("core/docx_rubrica_parser.py", [
    ('os.path.join(base_dir, "assets", str(course_id),', 'os.path.join(base_dir, "workspace", str(course_id),')
])

# core/document_reviewer.py
replace_in_file("core/document_reviewer.py", [
    ('os.path.join(PROJECT_ROOT, "assets", str(course_id))', 'os.path.join(PROJECT_ROOT, "workspace", str(course_id))')
])

# html_generator/generate_html.py
replace_in_file("html_generator/generate_html.py", [
    ('os.path.join(os.path.dirname(current_dir), "assets")', 'os.path.join(os.path.dirname(current_dir), "workspace")')
])

# check config/settings.py and config/settingsSALLE.py comments
replace_in_file("config/settingsSALLE.py", [
    ('assets/', 'workspace/')
])
replace_in_file("config/settings.py", [
    ('assets/', 'workspace/')
])

