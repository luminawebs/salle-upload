import re
import csv

def process_citation(text):
    # Regex to find:
    # 1. Date in parentheses: \(\d{4}[^\)]*\)\.\s*
    # 2. Book name: Up to the next period (or question mark? let's stick to period first or typical sentence enders)
    # Actually, APA format: Author. (Date). Title. Publisher.
    
    # Let's try to match:
    # (Author part) (Date part) (Title part)
    # We want to make Title part bold.
    # Pattern: (.*? \(\d{4}[^\)]*\)\.\s*)([^\.]+?\.)(.*)
    # But some titles have periods inside them? Usually not. Or they end with `?` or `!`
    # Let's try matching up to the first period after the date.
    
    # We also need to be careful not to match multiple times in one line if there's only one citation, but there might be multiple? Usually one per line.
    
    # A robust regex for the "book name":
    # Lookbehind for `(YYYY...). ` is hard because lookbehinds must be fixed width in Python.
    # We can use groups:
    # Group 1: everything up to and including the `(Year...). `
    # Group 2: The book name, ending with a period.
    # Group 3: The rest of the line.
    
    pattern = r'(.*? \(\d{4}[^\)]*\)\.\s*)([^\.]+?\.)(.*)'
    match = re.search(pattern, text)
    if match:
        return f"{match.group(1)}<b>{match.group(2)}</b>{match.group(3)}"
    return text

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
