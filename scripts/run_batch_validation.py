import os
import json
import logging
from core.parser_validator import run_validation
from core.data_parser import run_docx_parsing_workflow, run_docx_splitting_workflow

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def generate_markdown_report(report_data: dict, out_path: str):
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"# Comparison Report: Course {report_data['course_id']}\n\n")
        f.write(f"**Legacy Activities Found:** {report_data['legacy_activities_count']}\n")
        f.write(f"**AI Activities Found:** {report_data['ai_activities_count']}\n\n")
        
        f.write("## DOM Integrity Warnings\n")
        if not report_data['warnings']:
            f.write("None. All extracted fragments passed strict DOM ordering and attribute preservation tests.\n\n")
        else:
            for w in report_data['warnings']:
                f.write(f"- {w}\n")
            f.write("\n")
            
        f.write("## Activity Classification\n\n")
        
        for comp in report_data.get('comparisons', []):
            f.write(f"### Classification: {comp['classification']}\n")
            f.write(f"**Reasoning**: {comp['reasoning']}\n\n")
            
            if comp['classification'] == "Present only in AI":
                ai_act = comp['ai_activity']
                f.write(f"#### {ai_act.get('title', 'Unknown')}\n")
                f.write("```html\n")
                f.write(f"<!-- Description -->\n{ai_act.get('description_html', '')}\n")
                f.write(f"<!-- Rubric -->\n{ai_act.get('rubric_html', '')}\n")
                f.write(f"<!-- Questionnaire -->\n{ai_act.get('questionnaire_html', '')}\n")
                f.write("```\n\n")
            elif comp['classification'] == "Present in both, but with differences":
                f.write(f"**AI Result**: {json.dumps(comp['ai_activity'], indent=2, ensure_ascii=False)}\n")
                f.write(f"**Legacy Result**: {json.dumps(comp['legacy_activity'], indent=2, ensure_ascii=False)}\n\n")

def run_batch():
    test_courses = ["99999", "70801", "66710", "66763"]
    
    for course_id in test_courses:
        logger.info(f"=== Starting validation for {course_id} ===")
        
        # Ensure we have the raw_docx_extracted.html for the course.
        # If missing, it means the legacy pipeline hasn't been run or the folder isn't populated.
        raw_html_path = os.path.join("workspace", course_id, "raw_docx_extracted.html")
        if not os.path.exists(raw_html_path):
            logger.warning(f"File missing for {course_id}: {raw_html_path}. Skipping.")
            continue
            
        report = run_validation(course_id)
        if report:
            md_path = os.path.join("workspace", course_id, "comparison_report.md")
            generate_markdown_report(report, md_path)
            logger.info(f"Markdown report generated at {md_path}")

if __name__ == "__main__":
    run_batch()
