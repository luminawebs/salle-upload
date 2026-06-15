import sys
import os
import json

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from actions.infografia.infografia_parser import parse_infografia_html

def test_parser():
    raw_file = r"d:\28 Uniminuto\automatizacion_selenium_fase02\assets\4735\infografias\raw\RAW_s1_infografia.html"
    if not os.path.exists(raw_file):
        print(f"File not found: {raw_file}")
        return

    with open(raw_file, "r", encoding="utf-8") as f:
        raw_html = f.read()

    parsed_data = parse_infografia_html(raw_html)
    
    for slide in parsed_data["slides"]:
        if slide["type"] == "pregunta":
            print(f"Slide Title: {slide['title']}")
            print(f"Question Content: {slide['content']}")
            print("-" * 20)

if __name__ == "__main__":
    test_parser()
