def process_multichoice_option(text, p_tag):
    """
    Processes a multiple choice option.
    Returns a tuple of (option_text, is_correct, formatted_answer).
    """
    from .utils import clean_whitespace
    
    opt_text = clean_whitespace(text)
    is_correct = False
    bold_tag = p_tag.find(['strong', 'b'])
    
    if bold_tag and bold_tag.get_text(strip=True):
        bold_text = bold_tag.get_text(strip=True)
        # If a significant portion of the option is bold, it's correct
        if len(bold_text) >= len(text) * 0.5:
            is_correct = True
            
    # For multiple choice, the formatted answer is the option text itself
    return opt_text, is_correct, opt_text
