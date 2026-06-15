import os

base_dir = r"d:\28 Uniminuto\automatizacion_selenium_fase02\actions"
source = os.path.join(base_dir, "foro_actions.py")
out_dir = os.path.join(base_dir, "foro")

with open(source, 'r', encoding='utf-8') as f:
    lines = f.readlines()

def get_lines(start, end):
    return "".join(lines[start-1:end])

os.makedirs(out_dir, exist_ok=True)

# 1. __init__.py
with open(os.path.join(out_dir, "__init__.py"), "w", encoding="utf-8") as f:
    f.write("from .workflow import run_foro_export_workflow\n")

# 2. cleaner.py
with open(os.path.join(out_dir, "cleaner.py"), "w", encoding="utf-8") as f:
    f.write(
"""import re
from bs4 import BeautifulSoup
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from html_generator.generate_html import clean_html

URL_PATTERN = re.compile(r'https?://[^\\s<>"\\']+', re.IGNORECASE)

""" + get_lines(24, 57) + "\n" + get_lines(385, 421) + "\n" + get_lines(504, 526) + "\n" + get_lines(529, 560) + "\n" + get_lines(563, 595)
    )

# 3. parser.py
with open(os.path.join(out_dir, "parser.py"), "w", encoding="utf-8") as f:
    f.write(
"""import re
import logging
from bs4 import BeautifulSoup

from .cleaner import _sanitize_resource_section_html

logger = logging.getLogger(__name__)

""" + get_lines(59, 237) + "\n" + get_lines(240, 280) + "\n" + get_lines(283, 337) + "\n" + get_lines(340, 382) + "\n" + get_lines(424, 443) + "\n" + get_lines(446, 501)
    )

# 4. generator.py
with open(os.path.join(out_dir, "generator.py"), "w", encoding="utf-8") as f:
    f.write(
"""import os
import copy
import re
import logging
from bs4 import BeautifulSoup

from .cleaner import _convert_lists_to_paragraphs, _hide_plain_urls_in_html, _wrap_book_title_in_italics, URL_PATTERN
from .parser import _resource_html_has_reference_content

logger = logging.getLogger(__name__)

""" + get_lines(598, 610) + "\n" + get_lines(613, 644) + "\n" + get_lines(647, 653) + "\n" + get_lines(656, 683) + "\n" + get_lines(686, 857)
    )

# 5. extractor.py
with open(os.path.join(out_dir, "extractor.py"), "w", encoding="utf-8") as f:
    f.write(
"""import time
import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

from config.settings import Config

logger = logging.getLogger(__name__)

""" + get_lines(859, 991)
    )

# 6. uploader.py
with open(os.path.join(out_dir, "uploader.py"), "w", encoding="utf-8") as f:
    f.write(
"""import time
import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

from actions.moodle_actions import navigate_to_course
from config.settings import Config

logger = logging.getLogger(__name__)

""" + get_lines(1082, 1229)
    )

# 7. workflow.py
with open(os.path.join(out_dir, "workflow.py"), "w", encoding="utf-8") as f:
    f.write(
"""import os
import json
import logging
import time

from .extractor import extract_foro_content
from .cleaner import clean_foro_html
from .parser import parse_foro_data
from .generator import generate_foro_html_file
from .uploader import upload_foro_content

logger = logging.getLogger(__name__)

""" + get_lines(993, 1080)
    )

print("Split completed successfully.")
