import os
from bs4 import BeautifulSoup
import sys
import re
sys.path.append(os.getcwd())
from actions.infografia.infografia_extractor import parse_infografia_html

with open(r'd:\28 Uniminuto\automatizacion_selenium_fase02\assets\4856\infografias\raw\RAW_s1_infografia.html', 'r', encoding='utf-8') as f:
    raw_html = f.read()

soup = BeautifulSoup(raw_html, 'html.parser')
raw_elements = soup.find_all(["h2", "h3", "h4", "h5", "h6", "p", "li"])
elements = []
for el in raw_elements:
    if el.name == "p" and el.find_parent("li"):
        continue
    if el.name == "li" and el.find_parent("p"):
        continue
    elements.append(el)

print("--- RAW TEXT ELEMENTS ---")
for el in elements:
    text = el.get_text(separator=" ", strip=True)
    if text:
        btn_match = re.search(r"(?i)^B\s*o\s*t\s*[óo]\s*n\.?\s*", text)
        if btn_match:
            br_segments = []
            if el.name in ("p", "li"):
                buf = []
                for child in el.children:
                    if hasattr(child, "name") and child.name == "br":
                        seg = " ".join(
                            x.get_text(strip=True) if hasattr(x, "name") else str(x).strip() for x in buf
                        ).strip()
                        seg = re.sub(r"\s+", " ", seg).replace("\xa0", "").strip()
                        if seg:
                            br_segments.append(seg)
                        buf = []
                    else:
                        buf.append(child)
                seg = " ".join(
                    x.get_text(strip=True) if hasattr(x, "name") else str(x).strip() for x in buf
                ).strip()
                seg = re.sub(r"\s+", " ", seg).replace("\xa0", "").strip()
                if seg:
                    br_segments.append(seg)
            else:
                br_segments = [text]

            title_seg = br_segments[0]
            title_seg = re.sub(r"(?i)^B\s*o\s*t\s*[óo]\s*n\.?\s*", "", title_seg).strip()
            
            if len(br_segments) == 1 and ":" in title_seg:
                parts = title_seg.split(":", 1)
                btn_title = parts[0].strip() + ":"
                btn_content = parts[1].strip()
                btn_contents = [btn_content] if btn_content else []
            else:
                btn_title = title_seg
                btn_contents = br_segments[1:]
            
            print(f"BUTTON TITLE: {btn_title}")
            print(f"BUTTON CONTENT: {btn_contents}")
        else:
            print(f"TEXT: {text[:80]}")

