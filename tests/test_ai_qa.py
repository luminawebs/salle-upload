import os
import sys

# Ensure correct path for imports
sys.path.insert(0, os.path.abspath('.'))

from actions.html_transformer import extract_questions_from_html_to_moodle_xml
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')

def run_test():
    with open("assets/66764/raw_docx_extracted.html", "r", encoding="utf-8") as f:
        html_content = f.read()

    print("Running QA extraction...")
    extract_questions_from_html_to_moodle_xml(html_content, course_id=66764, document_name="TEST")
    print("Test finished.")

if __name__ == "__main__":
    run_test()
