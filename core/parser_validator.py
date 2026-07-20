import os
import json
import logging
from bs4 import BeautifulSoup
from core.document_splitter import DocumentSplitter
from core.ai_document_parser import parse_chunk_with_ai
from actions.structure_actions import parse_raw_document

logger = logging.getLogger(__name__)

def check_dom_integrity(original_html: str, extracted_html: str) -> dict:
    """
    Stricter DOM consistency checks using BeautifulSoup.
    Verifies that the extracted HTML preserves ordering, attributes, and no unexpected elements.
    Returns {"valid": bool, "warnings": list}
    """
    if not extracted_html.strip():
        return {"valid": True, "warnings": []}
    
    warnings = []
    # If the exact string is a substring (ignoring outer whitespace), it's perfect.
    if extracted_html.strip() in original_html:
        return {"valid": True, "warnings": []}
    
    try:
        orig_soup = BeautifulSoup(original_html, "html.parser")
        ext_soup = BeautifulSoup(extracted_html, "html.parser")
        
        # 1. Check relative ordering of significant tags
        def get_signature(soup):
            sig = []
            for tag in soup.find_all(['p', 'ul', 'ol', 'img', 'table', 'a']):
                sig.append(tag.name)
            return sig
            
        orig_sig = get_signature(orig_soup)
        ext_sig = get_signature(ext_soup)
        
        # Extracted signature should be a contiguous sub-sequence of the original signature
        def is_sublist(sub, lst):
            if not sub: return True
            if not lst: return False
            for i in range(len(lst) - len(sub) + 1):
                if lst[i:i+len(sub)] == sub:
                    return True
            return False
            
        if not is_sublist(ext_sig, orig_sig):
            warnings.append(f"DOM Ordering mismatch. Extracted signature {ext_sig} not found contiguously in original.")
            
        # 2. Verify preservation of important attributes
        important_attrs = ['src', 'href', 'alt', 'colspan', 'rowspan']
        for ext_tag in ext_soup.find_all(True):
            for attr in important_attrs:
                if ext_tag.has_attr(attr):
                    attr_val = ext_tag[attr]
                    if isinstance(attr_val, list):
                        attr_val = " ".join(attr_val)
                    if attr_val not in original_html:
                        warnings.append(f"Unexpected attribute value found: {attr}={attr_val}")
                        
        valid = len(warnings) == 0
        return {"valid": valid, "warnings": warnings}
        
    except Exception as e:
        return {"valid": False, "warnings": [f"BeautifulSoup parsing failed: {e}"]}

def classify_activities(legacy_activities: list, ai_activities: list) -> list:
    """
    Classifies matched activities.
    """
    results = []
    
    # Map legacy names
    leg_map = {act["name"].strip().lower(): act for act in legacy_activities}
    ai_map = {act["title"].strip().lower(): act for act in ai_activities}
    
    for ai_title, ai_act in ai_map.items():
        if ai_title in leg_map:
            leg_act = leg_map[ai_title]
            if leg_act["type"] != ai_act["type"]:
                results.append({
                    "classification": "Present in both, but with differences",
                    "ai_activity": ai_act,
                    "legacy_activity": leg_act,
                    "reasoning": f"Type mismatch: Legacy({leg_act['type']}) vs AI({ai_act['type']})"
                })
            else:
                results.append({
                    "classification": "Present in both",
                    "ai_activity": ai_act,
                    "legacy_activity": leg_act,
                    "reasoning": "Exact title and type match"
                })
        else:
            results.append({
                "classification": "Present only in AI",
                "ai_activity": ai_act,
                "legacy_activity": None,
                "reasoning": f"Title '{ai_act['title']}' not found in Legacy parser output. This is an extra activity caught by AI."
            })
            
    for leg_title, leg_act in leg_map.items():
        if leg_title not in ai_map:
            results.append({
                "classification": "Present only in legacy",
                "ai_activity": None,
                "legacy_activity": leg_act,
                "reasoning": f"Title '{leg_act['name']}' not found in AI extraction."
            })
            
    return results

def run_validation(course_id: str) -> dict:
    raw_html_path = os.path.join("workspace", str(course_id), "raw_docx_extracted.html")
    if not os.path.exists(raw_html_path):
        logger.error(f"Cannot find {raw_html_path}")
        return {}

    with open(raw_html_path, "r", encoding="utf-8") as f:
        raw_html = f.read()

    logger.info(f"[{course_id}] Running Legacy Parser...")
    legacy_sections = parse_raw_document(raw_html_path)
    legacy_activities = []
    for sec in legacy_sections:
        legacy_activities.extend(sec.get("activities", []))

    logger.info(f"[{course_id}] Running Semantic Splitter...")
    splitter = DocumentSplitter(raw_html)
    tree = splitter.split()

    ai_activities = []
    all_warnings = []
    
    logger.info(f"[{course_id}] Running AI Extraction Layer on Semantic Chunks...")
    for child in tree.children:
        if child.chunk_type in ["UNIT", "GENERALIDADES"]:
            logger.info(f"  -> AI Parsing: {child.title}")
            ai_result = parse_chunk_with_ai(child.html)
            
            for act in ai_result.get("activities", []):
                ai_activities.append(act)
                for html_field in ["description_html", "rubric_html", "questionnaire_html"]:
                    extracted = act.get(html_field, "")
                    if extracted:
                        integrity_res = check_dom_integrity(child.html, extracted)
                        if not integrity_res["valid"]:
                            msg = f"Integrity Check Failed in {child.title} - {act['title']} for {html_field}: {integrity_res['warnings']}"
                            logger.warning(msg)
                            all_warnings.append(msg)
                            ai_result["metadata"]["confidence"] -= 0.1

    comparisons = classify_activities(legacy_activities, ai_activities)

    report = {
        "course_id": course_id,
        "legacy_activities_count": len(legacy_activities),
        "ai_activities_count": len(ai_activities),
        "warnings": all_warnings,
        "comparisons": comparisons
    }
    
    report_path = os.path.join("workspace", str(course_id), "validation_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
        
    logger.info(f"[{course_id}] Validation complete. JSON saved to {report_path}")
    return report

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        logging.basicConfig(level=logging.INFO)
        run_validation(sys.argv[1])
