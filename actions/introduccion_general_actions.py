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


def load_template():
    """Load the guia curso HTML template."""
    template_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "templates", "introduccion-guiacurso.html"
    )
    try:
        with open(template_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        logger.error(f"Template file not found at {template_path}")
        raise


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
        "auto_save": True,
    }

    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
                for week_num in default_config["weeks"]:
                    if week_num not in config["weeks"]:
                        config["weeks"][week_num] = default_config["weeks"][week_num]
                return config
        except Exception as e:
            logger.error(f"Error loading week config: {e}")
            return default_config
    else:
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


def extract_course_introduction(driver, wait_time=10):
    """
    Extract the introduction content from 'VIR - INTRODUCCIÓN AL CURSO' activity.
    This is a SINGLE course-level introduction, different from weekly introductions.
    """
    wait = WebDriverWait(driver, wait_time)
    introduccion_raw = ""

    try:
        # Look for VIR - INTRODUCCIÓN AL CURSO activity
        intro_xpath = "//li[contains(@class, 'activity')]//*[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'vir - introducci') and contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'curso')]"

        try:
            intro_element = driver.find_element(By.XPATH, intro_xpath)
        except:
            # Fallback: look for any introduction that mentions "curso" or doesn't have a week number
            intro_xpath = "//li[contains(@class, 'activity')]//*[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'introducci') and not(contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'semana'))]"
            intro_element = driver.find_element(By.XPATH, intro_xpath)

        activity_li = intro_element.find_element(
            By.XPATH, "./ancestor::li[contains(@class, 'activity')]"
        )

        # Open edit menu
        dropdown_toggle = activity_li.find_element(
            By.CSS_SELECTOR, "a.dropdown-toggle[title='Editar'], a[aria-label='Editar']"
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

        # Extract the content using the unified handler
        try:
            introduccion_raw = extract_html_from_wysiwyg(driver, target_section="contenido")
            if not introduccion_raw:
                introduccion_raw = extract_html_from_wysiwyg(driver, target_section="descripcion")
        except Exception as e:
            logger.error(f"Failed to extract HTML using unified handler: {e}")
            introduccion_raw = ""

        # Cancel and go back
        cancel_btn = driver.find_element(By.CSS_SELECTOR, "input[name='cancel']")
        driver.execute_script("arguments[0].click();", cancel_btn)
        wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "body.path-course-view"))
        )

        return aggressive_clean_html(introduccion_raw)

    except Exception as e:
        logger.error(f"Error extracting course introduction: {e}")
        return ""


def parse_csv_data(csv_path):
    """
    Parse the CSV file and organize data by week.
    Returns a dictionary with week numbers as keys and structured content.
    """
    data_by_week = {}

    if not os.path.exists(csv_path):
        logger.error(f"CSV file not found at {csv_path}")
        return None

    try:
        with open(csv_path, "r", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            headers = next(reader)

            # Find column indices
            idx_semana = next(
                (i for i, h in enumerate(headers) if "# SEMANA DE ESTUDIO" in h), None
            )
            idx_unidad = next(
                (i for i, h in enumerate(headers) if "# UNIDAD (ES)" in h), None
            )
            idx_tema = next((i for i, h in enumerate(headers) if "TEMA (S)" in h), None)
            idx_subtemas = next(
                (i for i, h in enumerate(headers) if "SUBTEMAS" in h), None
            )
            idx_nombre = next(
                (i for i, h in enumerate(headers) if "NOMBRE DE LA SEMANA" in h), None
            )
            idx_rac = next((i for i, h in enumerate(headers) if "RAC" in h), None)
            idx_criterios = next(
                (
                    i
                    for i, h in enumerate(headers)
                    if "APRENDIZAJES ESPECÍFICOS / CRITERIOS DE EVALUACIÓN" in h
                ),
                None,
            )

            if None in [
                idx_semana,
                idx_tema,
                idx_subtemas,
                idx_nombre,
                idx_rac,
                idx_criterios,
            ]:
                logger.error(
                    f"Required columns not found in CSV. Found headers: {headers}"
                )
                return None

            for row in reader:
                if len(row) <= max(
                    idx_semana,
                    idx_tema,
                    idx_subtemas,
                    idx_nombre,
                    idx_rac,
                    idx_criterios,
                ):
                    continue

                semana = row[idx_semana].strip()
                if not semana.isdigit():
                    continue

                semana_num = int(semana)
                unidad = (
                    row[idx_unidad].strip()
                    if idx_unidad is not None and len(row) > idx_unidad
                    else ""
                )
                tema = row[idx_tema].strip()

                # Parse subtemas
                subtemas_raw = row[idx_subtemas].strip()
                subtemas = []
                for s in subtemas_raw.split("\n"):
                    s = s.strip()
                    if s:
                        s = re.sub(r"^\d+\.\d+\s*", "", s)
                        subtemas.append(s)

                nombre_semana = row[idx_nombre].strip()
                rac = row[idx_rac].strip()

                # Parse criterios
                criterios_raw = row[idx_criterios].strip()
                criterios = [c.strip() for c in criterios_raw.split("\n") if c.strip()]

                data_by_week[semana_num] = {
                    "unidad": unidad,
                    "tema": tema,
                    "subtemas": subtemas,
                    "nombre_semana": nombre_semana,
                    "rac": rac,
                    "criterios": criterios,
                    "semana_num": semana_num,
                }

    except Exception as e:
        logger.error(f"Error parsing CSV: {e}")
        return None

    return data_by_week


def group_by_unidad(data_by_week):
    """
    Group weeks by unidad (unit) and organize thematic content.
    Returns a dictionary with unidad numbers as keys.
    """
    unidades = {}
    temas_seen = {}
    unidad_counter = 1

    for week_num, week_data in data_by_week.items():
        unidad = week_data.get("unidad", "")
        tema = week_data.get("tema", "")

        if tema and tema not in temas_seen:
            temas_seen[tema] = unidad_counter
            unidad_counter += 1

        if unidad not in unidades:
            unidades[unidad] = {
                "unidad_num": temas_seen.get(tema, unidad_counter - 1),
                "tema": tema,
                "subtemas": [],
                "weeks": [],
            }

        for subtema in week_data.get("subtemas", []):
            if subtema not in unidades[unidad]["subtemas"]:
                unidades[unidad]["subtemas"].append(subtema)

        unidades[unidad]["weeks"].append(week_num)

    return unidades


def generate_complete_introduccion_html(course_introduction, course_data, output_path):
    """
    Generate the complete introduccion_general.html file using the template.

    Args:
        course_introduction: The HTML content extracted from 'VIR - INTRODUCCIÓN AL CURSO'
        course_data: Dictionary with week data from CSV
        output_path: Path where to save the generated HTML
    """
    template = load_template()
    soup = BeautifulSoup(template, "html.parser")

    # Collect all RACs and criterios from all weeks
    all_racs = []
    all_criterios = []
    for week_num, week_data in course_data.items():
        rac = week_data.get("rac", "")
        if rac and rac not in all_racs:
            all_racs.append(rac)

        for criterio in week_data.get("criterios", []):
            if criterio and criterio not in all_criterios:
                all_criterios.append(criterio)

    # Group weeks by unidad
    unidades = group_by_unidad(course_data)

    # 1. POPULATE INTRODUCCIÓN TAB (pills-virtual-1) with the extracted course introduction
    introduccion_div = soup.find("div", {"id": "pills-virtual-1"})
    if introduccion_div:
        introduccion_content = introduccion_div.find("div", class_="virtual-txt")
        if introduccion_content:
            introduccion_content.clear()
            # Use the extracted course introduction
            intro_html = f"""
            <h3>Introducción</h3>
            {course_introduction if course_introduction else "<p>Bienvenido al curso. Aquí encontrará una guía completa de los contenidos y actividades.</p>"}
            """
            introduccion_content.append(BeautifulSoup(intro_html, "html.parser"))

    # 2. POPULATE TEMÁTICAS TAB (pills-virtual-2) with grouped unidad content
    tematicas_div = soup.find("div", {"id": "pills-virtual-2"})
    if tematicas_div:
        tematicas_content = tematicas_div.find("div", class_="virtual-txt")
        if tematicas_content:
            tematicas_content.clear()
            tematicas_content.append(BeautifulSoup("<h3>Temáticas</h3>", "html.parser"))

            # Group by unidad number
            unidades_list = sorted(unidades.items(), key=lambda x: x[1]["unidad_num"])

            for unidad_key, unidad_data in unidades_list:
                tema_html = f"<p><b>{unidad_data['tema']}</b></p>\n"
                tema_html += f'<ul class="virtual-ul">\n'
                for subtema in unidad_data["subtemas"]:
                    tema_html += f"    <li>{subtema}</li>\n"
                tema_html += f"</ul>\n"
                tematicas_content.append(BeautifulSoup(tema_html, "html.parser"))

    # 3. POPULATE RAC TAB (pills-virtual-3)
    rac_div = soup.find("div", {"id": "pills-virtual-3"})
    if rac_div:
        rac_div.clear()
        rac_content = soup.new_tag("div", class_="virtual-txt")

        # Add RACs
        rac_title = soup.new_tag("h3")
        rac_title.string = "Resultados de Aprendizaje del Curso"
        rac_content.append(rac_title)

        rac_list = soup.new_tag("ul", class_="virtual-ul")
        for rac in all_racs:
            li = soup.new_tag("li")
            li.string = rac
            rac_list.append(li)
        rac_content.append(rac_list)

        rac_content.append(soup.new_tag("br"))

        # Add Criterios
        criterios_title = soup.new_tag("h3")
        criterios_title.string = "Criterios de evaluación"
        rac_content.append(criterios_title)

        criterios_list = soup.new_tag("ul", class_="virtual-ul")
        for criterio in all_criterios:
            li = soup.new_tag("li")
            li.string = criterio
            criterios_list.append(li)
        rac_content.append(criterios_list)

        rac_div.append(rac_content)

    # Write the updated HTML to file
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(str(soup))

    logger.info(f"Generated complete introducción HTML at {output_path}")
    return True


def upload_to_guia_del_curso(driver, course_id, html_path, wait_time=10):
    """
    Upload the generated general introduction HTML to the 'Guía del curso' activity.
    This is the DESTINATION activity, different from the source 'VIR - INTRODUCCIÓN AL CURSO'.
    """
    from actions.moodle_actions import navigate_to_course

    try:
        navigate_to_course(driver, Config.MOODLE_URL, course_id, wait_time)
        wait = WebDriverWait(driver, wait_time)

        # Look for "Guía del curso" activity (destination)
        guia_xpath = "//li[contains(@class, 'activity')]//*[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'guía del curso') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'guia del curso')]"

        try:
            guia_element = driver.find_element(By.XPATH, guia_xpath)
        except:
            # Fallback: look for any page that might be the course guide
            guia_xpath = "//li[contains(@class, 'activity')]//*[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'curso guía')]"
            try:
                guia_element = driver.find_element(By.XPATH, guia_xpath)
            except:
                logger.warning("'Guía del curso' activity not found. Skipping upload.")
                return False

        activity_li = guia_element.find_element(
            By.XPATH, "./ancestor::li[contains(@class, 'activity')]"
        )

        # Open edit menu
        dropdown_toggle = activity_li.find_element(
            By.CSS_SELECTOR, "a.dropdown-toggle[title='Editar'], a[aria-label='Editar']"
        )
        driver.execute_script("arguments[0].click();", dropdown_toggle)

        edit_option_xpath = ".//a[contains(@class, 'dropdown-item') and (contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'editar ajustes') or contains(@href, 'modedit.php'))]"
        edit_option = wait.until(
            lambda d: activity_li.find_element(By.XPATH, edit_option_xpath)
        )
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

        # Read the generated HTML
        with open(html_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        # Inject HTML into editor using unified handler
        success_inject = inject_html_into_wysiwyg(driver, html_content, wait_time, target_section="contenido")
        if not success_inject:
            logger.error("Failed to inject HTML into Guía del curso.")
            return False

        wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "body.path-course-view"))
        )

        logger.info(f"Successfully uploaded to 'Guía del curso' activity")
        return True

    except Exception as e:
        logger.error(f"Error uploading to 'Guía del curso': {e}")
        return False


def run_generar_introduccion_general_workflow(
    driver, course_id, wait_time=10, interactive_config=True
):
    """
    Main workflow to generate the general introduction HTML.

    This function:
    1. Extracts the course-level introduction from 'VIR - INTRODUCCIÓN AL CURSO' (SOURCE)
    2. Parses CSV data for weeks, subtemas, RACs, and criterios
    3. Generates a complete HTML page combining all information
    4. Uploads the result to 'Guía del curso' (DESTINATION)
    """
    logger.info(f"Starting General Introducción generation for course {course_id}...")

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

    # Step 1: Extract course-level introduction from SOURCE (VIR - INTRODUCCIÓN AL CURSO)
    logger.info(
        "Extracting course introduction from 'VIR - INTRODUCCIÓN AL CURSO' (SOURCE)..."
    )

    # Navigate to course if needed
    if "course/view.php" not in driver.current_url:
        navigate_to_course(driver, Config.MOODLE_URL, course_id, wait_time)

    course_introduction = extract_course_introduction(driver, wait_time)

    if not course_introduction:
        logger.warning("Could not extract course introduction. Using default text.")

    # Step 2: Parse CSV data
    csv_path = os.path.join("assets", str(course_id), "Propuesta_Metodológica.csv")
    out_dir = os.path.join("assets", str(course_id), "introduccion")
    os.makedirs(out_dir, exist_ok=True)
    output_path = os.path.join(out_dir, "introduccion_general.html")

    course_data = parse_csv_data(csv_path)

    if not course_data:
        logger.error("Failed to parse CSV data. Cannot generate HTML.")
        return False

    # Filter only enabled weeks
    filtered_data = {
        week: data for week, data in course_data.items() if week in enabled_weeks
    }

    if not filtered_data:
        logger.warning("No data found for enabled weeks.")
        return False

    # Step 3: Generate complete HTML
    success = generate_complete_introduccion_html(
        course_introduction, filtered_data, output_path
    )

    if success:
        logger.info(
            f"Workflow completed. Generated introducción general for {len(filtered_data)} weeks."
        )

        # Step 4: Upload to DESTINATION (Guía del curso) if auto_save is enabled
        if config.get("auto_save", True):
            logger.info("Attempting to upload to 'Guía del curso' (DESTINATION)...")
            upload_success = upload_to_guia_del_curso(
                driver, course_id, output_path, wait_time
            )
            if upload_success:
                logger.info("Successfully uploaded to 'Guía del curso'.")
            else:
                logger.warning("Failed to upload to 'Guía del curso'.")

    return success


# Convenience function for offline generation
def generate_introduccion_general_from_csv(
    course_id, course_introduction_html="", enabled_weeks=None
):
    """
    Generate the general introduction HTML from CSV without Moodle interaction.

    Args:
        course_id: The course ID
        course_introduction_html: HTML content for the introduction (or leave empty for default)
        enabled_weeks: List of week numbers to include (None for all weeks)
    """
    csv_path = os.path.join("assets", str(course_id), "Propuesta_Metodológica.csv")
    out_dir = os.path.join("assets", str(course_id), "introduccion")
    os.makedirs(out_dir, exist_ok=True)
    output_path = os.path.join(out_dir, "introduccion_general.html")

    course_data = parse_csv_data(csv_path)

    if not course_data:
        logger.error("Failed to parse CSV data.")
        return False

    if enabled_weeks is not None:
        course_data = {
            week: data for week, data in course_data.items() if week in enabled_weeks
        }

    if not course_data:
        logger.warning("No data available for the specified weeks.")
        return False

    return generate_complete_introduccion_html(
        course_introduction_html, course_data, output_path
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate general introduction HTML from CSV"
    )
    parser.add_argument("course_id", type=int, help="Course ID")
    parser.add_argument(
        "--weeks",
        type=str,
        help="Comma-separated list of weeks to include (e.g., '1,2,3')",
    )

    args = parser.parse_args()

    enabled_weeks = None
    if args.weeks:
        enabled_weeks = [int(w.strip()) for w in args.weeks.split(",")]

    generate_introduccion_general_from_csv(args.course_id, "", enabled_weeks)
