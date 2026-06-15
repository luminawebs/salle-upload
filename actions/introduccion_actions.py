import os
import json
import csv
import logging
import time
import re
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from html_generator.generate_html import TEMPLATE, clean_html
from actions.moodle_actions import navigate_to_course
from bs4 import BeautifulSoup
from config.settings import Config
from core.wysiwyg_handler import inject_html_into_wysiwyg, extract_html_from_wysiwyg

logger = logging.getLogger(__name__)


def aggressive_clean_html(raw_html):
    """Strips all classes, styles, scripts, and attributes from the HTML."""
    if not raw_html:
        return ""
    soup = BeautifulSoup(raw_html, "html.parser")

    # Remove scripts completely
    for script in soup.find_all("script"):
        script.decompose()

    # Strip all attributes from all tags
    for tag in soup.find_all(True):
        tag.attrs = {}

    return str(soup)


def load_week_config(course_id):
    """Load week configuration from JSON file, create default if not exists."""
    config_path = os.path.join("assets", str(course_id), "week_config.json")

    # Default configuration - all weeks enabled
    default_config = {
        "weeks": {
            "1": {"enabled": True, "name": "Semana 1"},
            "2": {"enabled": True, "name": "Semana 2"},
            "3": {"enabled": True, "name": "Semana 3"},
            "4": {"enabled": True, "name": "Semana 4"},
            "5": {"enabled": True, "name": "Semana 5"},
            "6": {"enabled": True, "name": "Semana 6"},
            "7": {"enabled": True, "name": "Semana 7"},
            "8": {"enabled": True, "name": "Semana 8"},
        },
        "auto_save": True,  # Automatically save changes to Moodle when generating
    }

    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
                # Merge with default to ensure all weeks exist
                for week_num in default_config["weeks"]:
                    if week_num not in config["weeks"]:
                        config["weeks"][week_num] = default_config["weeks"][week_num]
                return config
        except Exception as e:
            logger.error(f"Error loading week config: {e}")
            return default_config
    else:
        # Create default config file
        try:
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(default_config, f, indent=2, ensure_ascii=False)
            logger.info(f"Created default week configuration at {config_path}")
        except Exception as e:
            logger.error(f"Error creating week config: {e}")
        return default_config


def save_week_config(course_id, config):
    """Save week configuration to JSON file."""
    config_path = os.path.join("assets", str(course_id), "week_config.json")
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved week configuration to {config_path}")
        return True
    except Exception as e:
        logger.error(f"Error saving week config: {e}")
        return False


def display_week_menu(config):
    """Display interactive menu for toggling weeks."""
    print("\n" + "=" * 50)
    print("WEEK CONFIGURATION MENU")
    print("=" * 50)

    weeks = config["weeks"]
    for week_num in sorted(weeks.keys(), key=int):
        status = "✅ ENABLED" if weeks[week_num]["enabled"] else "❌ DISABLED"
        name = weeks[week_num].get("name", f"Semana {week_num}")
        print(f"{week_num}. {name:20} [{status}]")

    print("\n" + "-" * 50)
    print("Commands:")
    print("  <number>     - Toggle specific week (e.g., '3')")
    print("  all          - Enable all weeks")
    print("  none         - Disable all weeks")
    print("  range X-Y    - Enable range of weeks (e.g., 'range 1-4')")
    print("  status       - Show current configuration")
    print("  save         - Save and continue")
    print("  cancel       - Cancel and exit")
    print("=" * 50)

    return weeks


def configure_weeks_interactive(course_id):
    """Interactive function to configure which weeks to process."""
    config = load_week_config(course_id)

    while True:
        weeks = display_week_menu(config)
        choice = input("\nEnter command: ").strip().lower()

        if choice == "save":
            save_week_config(course_id, config)
            print("\n✅ Configuration saved!")
            return config

        elif choice == "cancel":
            print("\n❌ Operation cancelled.")
            return None

        elif choice == "status":
            print("\nCurrent Configuration:")
            for week_num in sorted(weeks.keys(), key=int):
                status = "ENABLED" if weeks[week_num]["enabled"] else "DISABLED"
                print(f"  Week {week_num}: {status}")
            input("\nPress Enter to continue...")

        elif choice == "all":
            for week_num in weeks:
                weeks[week_num]["enabled"] = True
            print("\n✅ All weeks enabled!")

        elif choice == "none":
            for week_num in weeks:
                weeks[week_num]["enabled"] = False
            print("\n✅ All weeks disabled!")

        elif choice.startswith("range"):
            try:
                parts = choice.split()
                if len(parts) == 2:
                    range_parts = parts[1].split("-")
                    if len(range_parts) == 2:
                        start = int(range_parts[0])
                        end = int(range_parts[1])
                        for week_num in range(start, end + 1):
                            if str(week_num) in weeks:
                                weeks[str(week_num)]["enabled"] = True
                        print(f"\n✅ Weeks {start}-{end} enabled!")
                    else:
                        print("\n❌ Invalid range format. Use: range 1-4")
                else:
                    print("\n❌ Invalid range command. Use: range 1-4")
            except ValueError:
                print("\n❌ Invalid range values. Use numbers.")

        elif choice.isdigit():
            week_num = choice
            if week_num in weeks:
                weeks[week_num]["enabled"] = not weeks[week_num]["enabled"]
                status = "enabled" if weeks[week_num]["enabled"] else "disabled"
                print(f"\n✅ Week {week_num} {status}!")
            else:
                print(f"\n❌ Week {week_num} not found (valid weeks: 1-8)")
        else:
            print("\n❌ Invalid command. Please try again.")


def run_generar_introduccion_workflow(
    driver, course_id, wait_time=10, interactive_config=True
):
    logger.info(
        f"Starting HTML Introducción extraction and generation for course {course_id}..."
    )

    # Load or configure weeks
    if interactive_config:
        config = configure_weeks_interactive(course_id)
        if config is None:
            logger.info("Workflow cancelled by user.")
            return False
    else:
        config = load_week_config(course_id)

    # Get enabled weeks
    enabled_weeks = [int(w) for w, data in config["weeks"].items() if data["enabled"]]

    if not enabled_weeks:
        logger.warning("No weeks are enabled. Please enable at least one week.")
        return False

    logger.info(f"Enabled weeks: {', '.join(map(str, enabled_weeks))}")

    csv_path = os.path.join("assets", str(course_id), "Propuesta_Metodológica.csv")
    json_path = os.path.join("assets", str(course_id), "contenidos.json")
    out_dir = os.path.join("assets", str(course_id), "introduccion")
    os.makedirs(out_dir, exist_ok=True)

    data_mapping = {}

    if os.path.exists(csv_path):
        try:
            try:
                f = open(csv_path, "r", encoding="utf-8-sig")
                headers = next(csv.reader(f))
            except UnicodeDecodeError:
                f = open(csv_path, "r", encoding="cp1252")
                headers = next(csv.reader(f))

            f.seek(0)
            reader = csv.reader(f)
            headers = next(reader)

            idx_semana = next(
                (i for i, h in enumerate(headers) if "# SEMANA DE ESTUDIO" in h), None
            )
            idx_nombre = next(
                (i for i, h in enumerate(headers) if "NOMBRE DE LA SEMANA" in h), None
            )
            idx_tema = next((i for i, h in enumerate(headers) if "TEMA (S)" in h), None)
            idx_subtemas = next(
                (i for i, h in enumerate(headers) if "SUBTEMAS" in h), None
            )
            idx_rac = next((i for i, h in enumerate(headers) if "RAC" in h), None)
            idx_crit = next(
                (
                    i
                    for i, h in enumerate(headers)
                    if "CRITERIOS DE EVALUACIÓN" in h or "APRENDIZAJES ESPECÍFICOS" in h
                ),
                None,
            )

            if None not in [
                idx_semana,
                idx_nombre,
                idx_tema,
                idx_subtemas,
                idx_rac,
                idx_crit,
            ]:
                for row in reader:
                    if len(row) > max(
                        idx_semana,
                        idx_nombre,
                        idx_tema,
                        idx_subtemas,
                        idx_rac,
                        idx_crit,
                    ):
                        semana = row[idx_semana].strip()
                        if semana.isdigit():
                            data_mapping[f"Semana {semana}"] = {
                                "nombre": row[idx_nombre].strip(),
                                "tema": row[idx_tema].strip(),
                                "subtemas": [
                                    s.strip()
                                    for s in row[idx_subtemas].split("\n")
                                    if s.strip()
                                ],
                                "rac": row[idx_rac].strip(),
                                "criterios": [
                                    c.strip()
                                    for c in row[idx_crit].split("\n")
                                    if c.strip()
                                ],
                            }
            f.close()
        except Exception as e:
            logger.error(f"Error parsing CSV: {e}")

    if not data_mapping and os.path.exists(json_path):
        logger.info("Falling back to contenidos.json")
        with open(json_path, "r", encoding="utf-8") as f:
            data_mapping = json.load(f)

    if not data_mapping:
        logger.error("No data mapping found. Cannot generate HTML.")
        return False

    wait = WebDriverWait(driver, wait_time)
    temas_seen = {}
    unidad_counter = 1

    # Process only enabled weeks
    for i in enabled_weeks:
        semana_key = f"Semana {i}"
        if semana_key not in data_mapping:
            logger.warning(f"{semana_key} not found in data mapping, skipping...")
            continue

        semana_data = data_mapping[semana_key]
        semana_num = i
        introduccion_raw = ""

        logger.info(f"Extracting introduction for {semana_key}...")
        try:
            if "course/view.php" not in driver.current_url:
                navigate_to_course(driver, Config.MOODLE_URL, course_id, wait_time)

            # Intento de encontrar la sección, incluyendo variaciones como 'Semana 1' o 'Unidad 1'
            section_xpath = f"//li[contains(@class, 'section') and .//*[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'semana {i}') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'unidad {i}')]]"

            try:
                section_element = driver.find_element(By.XPATH, section_xpath)
                # First try specifically VIR - INTRODUCCIÓN
                activity_xpath = ".//li[contains(@class, 'activity')]//*[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'vir - introducc')]"
                try:
                    activity_title = section_element.find_element(
                        By.XPATH, activity_xpath
                    )
                except:
                    # Fallback to any 'introducci' that is NOT S{i} | Introducción
                    activity_xpath = f".//li[contains(@class, 'activity')]//*[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'introducci') and not(contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 's{i} | introducc'))]"
                    activity_title = section_element.find_element(
                        By.XPATH, activity_xpath
                    )
            except:
                logger.warning(
                    f"Extraction source activity not found for {semana_key}."
                )
                raise Exception("Activity 'VIR - INTRODUCCIÓN' not found.")

            activity_li = activity_title.find_element(
                By.XPATH, "./ancestor::li[contains(@class, 'activity')]"
            )

            dropdown_toggle = activity_li.find_element(
                By.CSS_SELECTOR,
                "a.dropdown-toggle[title='Editar'], a[aria-label='Editar']",
            )
            try:
                wait.until(EC.element_to_be_clickable(dropdown_toggle)).click()
            except:
                driver.execute_script("arguments[0].click();", dropdown_toggle)

            edit_option_xpath = ".//a[contains(@class, 'dropdown-item') and (contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'editar ajustes') or contains(@href, 'modedit.php'))]"
            edit_option = wait.until(
                lambda d: activity_li.find_element(By.XPATH, edit_option_xpath)
            )
            try:
                wait.until(EC.element_to_be_clickable(edit_option)).click()
            except:
                driver.execute_script("arguments[0].click();", edit_option)

            wait.until(
                EC.presence_of_element_located(
                    (
                        By.CSS_SELECTOR,
                        "#id_submitbutton, input[name='submitbutton'], button[name='submitbutton']",
                    )
                )
            )
            time.sleep(2)

            try:
                introduccion_raw = extract_html_from_wysiwyg(driver, target_section="contenido")
                if not introduccion_raw:
                    introduccion_raw = extract_html_from_wysiwyg(driver, target_section="descripcion")
            except Exception as e:
                logger.error(f"Failed to extract HTML using unified handler: {e}")
                introduccion_raw = ""

            # Extracted! Now cancel and go back to course to inject into the other activity.
            cancel_btn = driver.find_element(By.CSS_SELECTOR, "input[name='cancel']")
            driver.execute_script("arguments[0].click();", cancel_btn)
            wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "body.path-course-view")
                )
            )

            # Clean aggressively
            introduccion_raw = aggressive_clean_html(introduccion_raw)

            nombre = semana_data.get("nombre", "")
            if not introduccion_raw or not introduccion_raw.strip():
                introduccion_raw = f"<p><b>Semana {semana_num}. {nombre}</b></p>"

            introduccion_html = clean_html(introduccion_raw)

            criterios = semana_data.get("criterios", [])
            resultados_msg = (
                "<p>El resultado de aprendizaje de la semana es:</p>"
                if len(criterios) <= 1
                else "<p>Los resultados de aprendizaje de la semana son:</p>"
            )
            criterios_li = "\n".join(f"                <li>{c}</li>" for c in criterios)
            rac = semana_data.get("rac", "")

            subtemas = semana_data.get("subtemas", [])
            subtemas_msg = (
                "<p>En el siguiente apartado encontrará el contenido temático de esta semana.</p>"
                if len(subtemas) <= 1
                else "<p>En el siguiente apartado encontrará los contenidos temáticos de esta semana.</p>"
            )

            cleaned_subtemas = [re.sub(r"^\d+\.\d+\s*", "", s) for s in subtemas]
            subtemas_li = "\n".join(
                f"                <li>{s}</li>" for s in cleaned_subtemas
            )

            tema = semana_data.get("tema", "")
            if tema not in temas_seen:
                temas_seen[tema] = unidad_counter
                unidad_counter += 1
            unidad_num = temas_seen[tema]

            html_output = TEMPLATE.format(
                introduccion_html=introduccion_html,
                resultados_msg=resultados_msg,
                rac=rac,
                criterios_li=criterios_li,
                subtemas_msg=subtemas_msg,
                unidad_num=unidad_num,
                tema=tema,
                subtemas_li=subtemas_li,
            )

            out_filename = f"semana_introduccion_{semana_num:02d}.html"
            out_path = os.path.join(out_dir, out_filename)

            with open(out_path, "w", encoding="utf-8") as out_f:
                out_f.write(html_output)

            logger.info(f"Generated {out_filename}")

            # Inject generated HTML back to Moodle (only if auto_save is enabled)
            if config.get("auto_save", True):
                logger.info(
                    f"Navigating to S{i} | Introducción to upload generated HTML..."
                )
                try:
                    section_element = driver.find_element(By.XPATH, section_xpath)
                    target_activity_xpath = f".//li[contains(@class, 'activity')]//*[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 's{i} | introducc')]"
                    target_activity_title = section_element.find_element(
                        By.XPATH, target_activity_xpath
                    )
                except Exception as ex:
                    logger.warning(
                        f"Target activity S{i} | Introducción not found in section. Aborting upload for this week."
                    )
                    raise Exception(f"Target activity S{i} | Introducción not found.")

                target_li = target_activity_title.find_element(
                    By.XPATH, "./ancestor::li[contains(@class, 'activity')]"
                )
                dropdown_toggle = target_li.find_element(
                    By.CSS_SELECTOR,
                    "a.dropdown-toggle[title='Editar'], a[aria-label='Editar']",
                )
                try:
                    wait.until(EC.element_to_be_clickable(dropdown_toggle)).click()
                except:
                    driver.execute_script("arguments[0].click();", dropdown_toggle)

                edit_option = wait.until(
                    lambda d: target_li.find_element(By.XPATH, edit_option_xpath)
                )
                try:
                    wait.until(EC.element_to_be_clickable(edit_option)).click()
                except:
                    driver.execute_script("arguments[0].click();", edit_option)

                wait.until(
                    EC.presence_of_element_located(
                        (
                            By.CSS_SELECTOR,
                            "#id_submitbutton, input[name='submitbutton'], button[name='submitbutton']",
                        )
                    )
                )

                # Inject generated HTML using the unified handler
                success_inject = inject_html_into_wysiwyg(driver, html_output, wait_time, target_section="contenido")
                if not success_inject:
                    logger.error(f"Failed to inject generated introduction for {semana_key}.")
                    raise Exception("WYSIWYG injection failed.")
                    
                wait.until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, "body.path-course-view")
                    )
                )
                logger.info(f"Successfully uploaded {out_filename} to Moodle.")
            else:
                logger.info(f"Generated {out_filename} locally (auto-save disabled)")

        except Exception as e:
            logger.error(f"Failed to extract/upload introduction for {semana_key}: {e}")
            if "course/view.php" not in driver.current_url:
                navigate_to_course(driver, Config.MOODLE_URL, course_id, wait_time)

    logger.info(f"Workflow completed. Processed {len(enabled_weeks)} weeks.")
    return True
