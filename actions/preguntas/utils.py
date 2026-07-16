from .constants import REGEX_WHITESPACE, REGEX_QUESTION_START, REGEX_FEEDBACK_PREFIX

def clean_whitespace(text):
    """Removes extra whitespace and normalizes it."""
    return REGEX_WHITESPACE.sub(' ', text)

def clean_question_text(text):
    """Removes leading numbering from question text."""
    cleaned = clean_whitespace(text)
    return REGEX_QUESTION_START.sub('', cleaned)

def clean_feedback_text(text):
    """Removes the 'Retroalimentacion:' prefix."""
    feed = REGEX_FEEDBACK_PREFIX.sub('', text)
    return clean_whitespace(feed)
