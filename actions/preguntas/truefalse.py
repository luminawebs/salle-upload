def process_truefalse_option(text, p_tag):
    """
    Processes a true/false option.
    Returns a tuple of (option_text, is_correct, formatted_answer).
    """
    from .utils import clean_whitespace
    
    opt_text = clean_whitespace(text)
    is_correct = False
    bold_tag = p_tag.find(['strong', 'b'])
    
    if bold_tag and bold_tag.get_text(strip=True):
        bold_text = bold_tag.get_text(strip=True)
        if len(bold_text) >= len(text) * 0.5:
            is_correct = True
            
    val = opt_text.strip()
    formatted_answer = "true" if "VERDADERO" in val.upper() else "false"
    
    return opt_text, is_correct, formatted_answer
