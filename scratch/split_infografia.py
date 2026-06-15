import ast
import os
import shutil

parser_path = "actions/infografia/infografia_parser.py"
with open(parser_path, "r", encoding="utf-8") as f:
    source_code = f.read()

tree = ast.parse(source_code)

functions = {}
for node in tree.body:
    if isinstance(node, ast.FunctionDef):
        # ast.get_source_segment is available in Python 3.8+
        functions[node.name] = ast.get_source_segment(source_code, node)

# Define the new files and the functions they should contain
files_mapping = {
    "actions/infografia/utils.py": {
        "imports": "from config.settings import Config\n\n",
        "functions": ["_export_strip_colon"]
    },
    "actions/infografia/infografia_extractor.py": {
        "imports": (
            "import re\n"
            "from bs4 import BeautifulSoup\n"
            "from config.settings import Config\n"
            "from actions.infografia.utils import _export_strip_colon\n\n"
        ),
        "functions": ["parse_infografia_html", "_build_reference_text"]
    },
    "actions/infografia/generators/__init__.py": {
        "imports": "",
        "functions": []
    },
    "actions/infografia/generators/common.py": {
        "imports": (
            "from bs4 import BeautifulSoup\n"
            "from actions.infografia.infografia_template_manager import apply_template_to_wrapper\n\n"
        ),
        "functions": ["_add_controls", "_add_buttons"]
    },
    "actions/infografia/generators/referencias_slide.py": {
        "imports": (
            "import re\n"
            "from bs4 import BeautifulSoup\n\n"
        ),
        "functions": ["split_paragraphs_by_limit", "_build_biblio_slide"]
    },
    "actions/infografia/generators/pregunta_slide.py": {
        "imports": (
            "import os\n"
            "import re\n"
            "from bs4 import BeautifulSoup\n"
            "from config.settings import Config\n"
            "from actions.infografia.generators.common import _add_controls\n\n"
        ),
        "functions": [
            "_normalize_pregunta_options", 
            "_normalize_correct_answer", 
            "_normalize_feedback_message", 
            "_build_pregunta_layout_from_template", 
            "_create_pregunta_slide", 
            "_add_pregunta_content"
        ]
    },
    "actions/infografia/generators/info_slide.py": {
        "imports": (
            "import re\n"
            "from bs4 import BeautifulSoup\n"
            "from config.settings import Config\n"
            "from actions.infografia.utils import _export_strip_colon\n"
            "from actions.infografia.generators.common import _add_controls, _add_buttons\n"
            "from actions.infografia.generators.pregunta_slide import _add_pregunta_content\n\n"
        ),
        "functions": [
            "_process_text_for_leer_mas", 
            "_add_leer_mas", 
            "_create_info_slide"
        ]
    },
    "actions/infografia/infografia_builder.py": {
        "imports": (
            "import os\n"
            "import re\n"
            "from bs4 import BeautifulSoup\n"
            "from config.settings import Config\n"
            "from actions.infografia.generators.info_slide import _create_info_slide\n"
            "from actions.infografia.generators.pregunta_slide import _create_pregunta_slide\n"
            "from actions.infografia.generators.referencias_slide import _build_biblio_slide, split_paragraphs_by_limit\n\n"
        ),
        "functions": ["generate_infografia_html"]
    }
}

os.makedirs("actions/infografia/generators", exist_ok=True)

for file_path, data in files_mapping.items():
    print(f"Writing {file_path}...")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(data["imports"])
        for func_name in data["functions"]:
            if func_name in functions:
                f.write(functions[func_name] + "\n\n\n")
            else:
                print(f"WARNING: Function {func_name} not found!")

print("Done generating new files.")
