import re

# Section names
SECTION_DIAGNOSTICO = "diagnostico"
SECTION_AFIANZAMIENTO = "afianzamiento"
SECTION_EXAMEN = "examen"

# Regular Expressions
REGEX_QUESTION_START = re.compile(r'^\s*\d+[\.\)]\s*')
REGEX_OPTION_START = re.compile(r'^\s*[A-Ea-e][\)\.]\s*')
REGEX_FEEDBACK_PREFIX = re.compile(r'^\s*retroalimentaci[oó]n\s*:\s*', flags=re.IGNORECASE)
REGEX_WHITESPACE = re.compile(r'\s+')
