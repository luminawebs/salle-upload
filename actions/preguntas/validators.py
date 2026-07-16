from .constants import (
    SECTION_DIAGNOSTICO,
    SECTION_AFIANZAMIENTO,
    SECTION_EXAMEN,
    REGEX_QUESTION_START,
    REGEX_OPTION_START
)

def identify_section(text):
    """
    Identifies the section based on text content.
    Returns the section name or None if not a section header.
    """
    if len(text) > 100:
        return None
    t = text.upper()
    if "DIAGNÓSTICO" in t or "DIAGNOSTICO" in t:
        return SECTION_DIAGNOSTICO
    if "AFIANZAMIENTO" in t:
        return SECTION_AFIANZAMIENTO
    if "EXÁMEN" in t or "EXAMEN" in t:
        if "DIAGN" not in t:
            return SECTION_EXAMEN
    return None

def is_question_start(text):
    """Checks if the text indicates the start of a new question."""
    return REGEX_QUESTION_START.match(text) is not None

def is_option(text):
    """Checks if the text is a multiple choice or true/false option."""
    if REGEX_OPTION_START.match(text):
        return True
    t = text.strip().lower()
    if t in ["verdadero", "falso"]:
        return True
    return False

def is_feedback(text):
    """Checks if the text is a feedback statement."""
    return "RETROALIMENTACI" in text.upper()
