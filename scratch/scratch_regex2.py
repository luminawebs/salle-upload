import re
import csv

def process_citation(text):
    # Match the date part: (Year...).
    # Then match everything until a period that is either at the end of the line,
    # or followed by a space and an uppercase letter (or a http link?)
    # A more reliable way:
    # After the date and dot + space:
    # Match lazily until we see a period followed by space or end of string,
    # AND we are not stopping at "pp."
    
    # Let's write a regex that matches:
    # 1: (.*? \(\d{4}[^\)]*\)\.\s*)  <- Up to the space after date
    # 2: (.*?) <- The title
    # 3: (\.(?:\s+|$).*) <- The period and the rest
    
    # But we want to avoid matching the period in "(pp. "
    # We can do this by using a custom function with re.sub
    
    pattern = r'(^.*?\(\d{4}[^\)]*\)\.\s+)(.*?)(?=\.\s+|\.$|$)(.*)'
    
    # We can split the text and find the first period that is not inside parentheses?
    # Better: let's use a regex that matches the first period that is followed by space and NOT preceded by "pp" or "ed"
    
    pattern = r'(^.*?\(\d{4}[^\)]*\)\.\s+)(.*?\S)\.(?:\s+|$)'
    
    # Let's iterate over the string to find the correct period.
    match = re.search(r'(^.*?\(\d{4}[^\)]*\)\.\s+)', text)
    if not match:
        return text
    
    start_part = match.group(1)
    rest = text[len(start_part):]
    
    # Find the end of the title in `rest`
    # We look for a period. If the period is inside parentheses, we ignore it.
    # If the period is preceded by a lowercase abbreviation like 'pp' or 'ed', we ignore it?
    # Let's count parentheses.
    
    paren_depth = 0
    title_end = -1
    for i, char in enumerate(rest):
        if char == '(':
            paren_depth += 1
        elif char == ')':
            paren_depth = max(0, paren_depth - 1)
        elif char == '.' and paren_depth == 0:
            # Check if it's "pp."
            if i >= 2 and rest[i-2:i] == 'pp':
                continue
            title_end = i
            break
            
    if title_end != -1:
        title = rest[:title_end]
        after_title = rest[title_end:]
        return f"{start_part}<b>{title}</b>{after_title}"
    else:
        # no period found outside parens
        return f"{start_part}<b>{rest}</b>"

with open('d:\\28 Uniminuto\\automatizacion_selenium_fase02\\assets\\4735\\recursos\\recursos.csv', 'r', encoding='utf-8') as f:
    reader = csv.reader(f)
    next(reader)
    for row in reader:
        if len(row) >= 3:
            for text in [row[1], row[2]]:
                lines = text.split('\n')
                for line in lines:
                    line = line.strip()
                    if line:
                        print("ORIGINAL:", line)
                        print("BOLDED:  ", process_citation(line))
                        print("-")
