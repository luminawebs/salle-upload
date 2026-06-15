# Infografía Module Architecture

This folder contains the logic for extracting, parsing, and generating the Interactive Infographics for Moodle. The architecture is split into specific responsibilities to make it easy to maintain and edit.

## Main Workflow
- **`infografia_actions.py`**: The orchestrator. It uses Selenium to navigate Moodle, extract the raw HTML of the infographic, pass it to the parser, and then upload the generated final HTML back to Moodle.

## Parsing & Building
- **`infografia_extractor.py`**: The parser. Its sole responsibility is "HTML in, Data out." It reads the messy raw HTML from Moodle and converts it into a clean, structured Python dictionary containing the slides data.
- **`infografia_builder.py`**: The coordinator for generation. It takes the structured dictionary from the extractor and coordinates the creation of the final HTML, calling the specific slide generators.

## Templates & Utilities
- **`infografia_template_manager.py`**: Handles injecting dynamic content (like button titles, modal text, and tab content) into predefined HTML layout templates (e.g., layouts with 3 buttons vs 5 buttons).
- **`utils.py`**: Contains simple, shared utility functions used across multiple files (like text cleaning/formatting).

## Generators (`/generators` folder)
This folder isolates the HTML generation logic by slide type. Editing one slide type guarantees you won't accidentally break the design of another.

- **`info_slide.py`**: Generates the HTML for standard informative slides (text, images, and "leer más" modals).
- **`pregunta_slide.py`**: Generates the HTML layout for the interactive questions and handles the logic for options, correct answers, and feedback popups.
- **`referencias_slide.py`**: Generates the bibliography slides, handling the logic to split long lists of references across multiple paginated slides.
- **`common.py`**: Holds shared HTML components that apply to multiple slide types, such as the bottom navigation controls (home, previous, next) and button attachments.
