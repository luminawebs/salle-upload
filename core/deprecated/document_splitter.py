import logging
import re
from bs4 import BeautifulSoup
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)

@dataclass
class SemanticChunk:
    chunk_type: str  # "UNIT", "ACTIVITY", "GENERALIDADES", "UNKNOWN"
    title: str
    html: str
    children: List['SemanticChunk']
    
    def to_dict(self):
        return {
            "type": self.chunk_type,
            "title": self.title,
            "html": self.html,
            "children": [c.to_dict() for c in self.children]
        }

class DocumentSplitter:
    """
    Splits a raw HTML document into semantic chunks (Units -> Activities)
    to feed into the AI extractor. This uses best-effort heuristics.
    If it fails to find granular chunks, it returns larger chunks, relying
    on the AI to figure out the exact details.
    """
    def __init__(self, raw_html: str):
        self.raw_html = raw_html
        self.soup = BeautifulSoup(raw_html, "html.parser")
        
    def split(self) -> SemanticChunk:
        root = SemanticChunk("DOCUMENT", "Course Document", "", [])
        
        current_unit = None
        current_activity = None
        
        # A list to accumulate HTML that belongs to the current context
        current_context_html = []
        
        def save_context():
            # Helper to save accumulated HTML to the deepest active node
            if not current_context_html:
                return
            html_str = "".join(current_context_html)
            if current_activity:
                current_activity.html += html_str
            elif current_unit:
                current_unit.html += html_str
            else:
                root.html += html_str
            current_context_html.clear()

        # We will iterate through block-level elements
        for element in self.soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'table', 'ul', 'ol', 'div']):
            # Skip nested elements to avoid processing things twice
            if element.find_parent(['table', 'ul', 'ol', 'div']) and element.name not in ['table', 'ul', 'ol', 'div']:
                continue
                
            text = element.get_text(separator=" ").strip().upper()
            
            # Detect Unit boundary
            if "UNIDAD DIDÁCTICA" in text or "UNIDAD DIDACTICA" in text:
                m = re.search(r'UNIDAD DID\u00c1CTICA\s*(\d+)', text)
                if not m:
                    m = re.search(r'UNIDAD DIDACTICA\s*(\d+)', text)
                if m:
                    save_context()
                    unit_num = m.group(1)
                    current_unit = SemanticChunk("UNIT", f"UNIDAD {unit_num}", "", [])
                    current_activity = None
                    root.children.append(current_unit)
                    current_context_html.append(str(element))
                    continue
            
            # Detect Activity boundary
            if "ACTIVIDAD" in text and not text.startswith("ACTIVIDADES"):
                m = re.match(r'^ACTIVIDAD\s*[\dIVXLCDM]+\s*[:.-]?', text)
                if m:
                    save_context()
                    current_activity = SemanticChunk("ACTIVITY", text[:50], "", [])
                    if current_unit:
                        current_unit.children.append(current_activity)
                    else:
                        root.children.append(current_activity)
                    current_context_html.append(str(element))
                    continue

            # Detect Generalidades (Plan de formación, etc.)
            if "PLAN DE FORMACIÓN" in text or "PLAN DE FORMACION" in text:
                if not current_unit and not current_activity:
                    save_context()
                    gen_chunk = SemanticChunk("GENERALIDADES", "Generalidades del curso", "", [])
                    root.children.append(gen_chunk)
                    current_unit = gen_chunk
                    current_context_html.append(str(element))
                    continue

            # Otherwise, append to current context
            current_context_html.append(str(element))
            
        save_context()
        return root

if __name__ == "__main__":
    # Simple test
    import sys
    if len(sys.argv) > 1:
        with open(sys.argv[1], "r", encoding="utf-8") as f:
            html = f.read()
        splitter = DocumentSplitter(html)
        tree = splitter.split()
        import json
        print(json.dumps(tree.to_dict(), indent=2, ensure_ascii=False))
