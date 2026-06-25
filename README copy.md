# Moodle Selenium Automation & HTML Generator

This project is a Python-based utility designed to automate course management tasks in Moodle using Selenium, as well as generate structured HTML content for course weeks based on JSON data.

## Project Structure

- `main.py`: The entry point for the Moodle Selenium automation script.
- `core/`: Contains the WebDriver setup (`driver_setup.py`).
- `actions/`: Contains action modules for interacting with Moodle (`moodle_actions.py`, `section_actions.py`).
- `config/`: Contains configuration settings (`settings.py`) driven by environment variables.
- `html_generator/`: Contains `generate_html.py`, a script to process JSON files and output HTML files.
- `assets/`: A directory where course-specific assets are stored, organized by Course ID (e.g., `assets/4729/`).

## 1. Moodle Automation (`main.py`)

The automation script uses Selenium WebDriver to log into Moodle and perform actions on specified courses.

### Setup and Configuration

1. **Environment Variables**: Create a `.env` file based on `.env.example`. You must provide:
   - `MOODLE_USERNAME`
   - `MOODLE_PASSWORD`
   - Other optional configurations like explicit wait times and toggles for specific workflows.

2. **Course Configuration**:
   - In `main.py`, the `courses_to_process` list determines which Moodle course IDs will be processed.
   - For section description updates, the automation uses the `contenidos.json` file in the corresponding `assets/<course_id>/` directory, specifically extracting the `"nombre"` data to map the sections to their new descriptions.

### Features
- **Toggleable Workflows**: Workflows like renaming sections or updating section descriptions can be enabled or disabled via configuration (`Config.ENABLE_SECTION_RENAME`, `Config.ENABLE_SECTION_DESCRIPTION_UPDATE`).
- **Resilient Selectors**: Uses explicit waits to handle dynamic DOM changes in Moodle.

### Running the Automation
```bash
python main.py
python server.py
```

## 2. HTML Content Generator (`html_generator/generate_html.py`)

This script processes course content defined in JSON files and generates structured, tabbed HTML files for each week (semana) of the course.

### Usage

1. **Input Data**: Ensure your course content is structured in a `contenidos.json` file located in `assets/<course_id>/contenidos.json`. The JSON should contain entries for each week (e.g., "Semana 1", "Semana 2") with fields for `introduccion`, `nombre`, `criterios`, `rac`, `subtemas`, and `tema`.
2. **Execution**: Run the generator script.
   ```bash
   cd html_generator
   python generate_html.py
   ```
3. **Output**: The script will create `semana_introduccion_XX.html` files alongside the `contenidos.json` file in the respective asset folder.

### Features
- **Dynamic Grammar**: The script automatically adjusts pluralization (e.g., "El resultado" vs "Los resultados") based on whether there are single or multiple criteria/subtopics.
- **HTML Cleanup**: Uses BeautifulSoup to ensure the raw HTML provided in the JSON is properly formatted and closed before injecting it into the template.
- **Batch Processing**: Automatically finds and processes all `contenidos.json` files within the `assets/` subdirectories.

## Requirements

The project dependencies are managed via pip. Ensure you have the necessary packages installed:

```bash
pip install -r html_generator/requirements.txt
# Additionally, ensure selenium and python-dotenv are installed for the main automation script.
```
Restart after code changes

If you update server.py or other backend code:

sudo systemctl restart salle-automate

Follow logs live
sudo journalctl -u salle-automate -f

Typical development workflow

If you modify backend code:

 systemctl status salle-automate