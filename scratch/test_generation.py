import sys
import os

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from actions.infografia.infografia_parser import parse_infografia_html, generate_infografia_html

def test_generation():
    raw_file = r"d:\28 Uniminuto\automatizacion_selenium_fase02\assets\4735\infografias\raw\RAW_s1_infografia.html"
    if not os.path.exists(raw_file):
        print(f"File not found: {raw_file}")
        return

    with open(raw_file, "r", encoding="utf-8") as f:
        raw_html = f.read()

    parsed_data = parse_infografia_html(raw_html)
    
    # Check if there are buttons in any slide
    has_buttons = any(slide.get("buttons") for slide in parsed_data["slides"])
    print(f"Has buttons: {has_buttons}")
    
    base_url = "https://example.com/images/"
    week_num = 1
    
    try:
        final_html = generate_infografia_html(parsed_data, base_url, week_num)
        print("Successfully generated HTML")
        # Save to a temp file to inspect
        with open("temp_test_output.html", "w", encoding="utf-8") as f:
            f.write(final_html)
        print("Output saved to temp_test_output.html")
    except Exception as e:
        print(f"Error during generation: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_generation()
