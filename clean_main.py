import re

keep_flags = {
    "ENABLE_DOCX_PARSING",
    "ENABLE_DOCX_SPLITTING_HTML",
    "ENABLE_UNIDADES_INTRO_SPLIT",
    "ENABLE_COURSE_FORMAT_CHANGE",
    "ENABLE_COURSE_STRUCTURE_CREATION",
    "ENABLE_UNIDADES_INTRO_UPLOAD",
    "ENABLE_DOCX_UPLOAD_HTML",
    "ENABLE_DOCX_RUBRICA_UPLOAD",
    "ENABLE_CUESTIONARIO_EXPORT",
    "ENABLE_CUESTIONARIO_GRADE_UPDATE",
    "ENABLE_ACTIVITY_COMPLETION_UPDATE",
    "ENABLE_FINAL_COURSE_FORMAT_BUTTONS",
}

with open("main.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
skip_mode = False
skip_indent = 0

i = 0
while i < len(lines):
    line = lines[i]

    # The large if condition
    if 'or getattr(Config, "ENABLE_' in line:
        m = re.search(r'ENABLE_[A-Z_]+', line)
        if m and m.group(0) not in keep_flags:
            i += 1
            continue

    m_if = re.search(r'^(\s*)if \(?getattr\(Config,\s*"([^"]+)"', line)
    m_elif = re.search(r'^(\s*)elif not \(?getattr\(Config,\s*"([^"]+)"', line)
    m_elif2 = re.search(r'^(\s*)elif not \(\s*getattr\(Config,\s*"([^"]+)"', line)
    
    match_if = None
    if m_if and m_if.group(2) not in keep_flags:
        match_if = m_if
    if m_elif and m_elif.group(2) not in keep_flags:
        match_if = m_elif
    if m_elif2 and m_elif2.group(2) not in keep_flags:
        match_if = m_elif2
        
    if match_if:
        skip_mode = True
        skip_indent = len(match_if.group(1))
        i += 1
        continue
    
    if skip_mode:
        current_indent = len(line) - len(line.lstrip())
        if line.strip() == "":
            i += 1
            continue
        if current_indent <= skip_indent and not line.strip().startswith("else:") and not line.strip().startswith("elif"):
            skip_mode = False
        else:
            i += 1
            continue
            
    new_lines.append(line)
    i += 1

with open("main.py", "w", encoding="utf-8") as f:
    f.writelines(new_lines)
