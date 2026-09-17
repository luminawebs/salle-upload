import os
import json
import logging
from core.document_splitter import DocumentSplitter
from core.ai_document_parser import parse_chunk_with_ai
from core.html_integrity import check_dom_integrity
from actions.structure_actions import parse_raw_document

logger = logging.getLogger(__name__)

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
            ai_result = parse_chunk_with_ai(child.html, course_id=course_id)
            
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
