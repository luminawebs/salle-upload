import logging
import os
import json
import time
from bs4 import BeautifulSoup
import re
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import Config
from actions.moodle_actions import navigate_to_course

# Re-export from the new modular package to maintain backward compatibility
from actions.preguntas import (
    parse_preguntas_data,
    generate_afianzamiento_html,
    run_preguntas_workflow,
    build_moodle_xml
)

logger = logging.getLogger(__name__)

# All core logic has been moved to actions/preguntas/
