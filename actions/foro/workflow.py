import os
import json
import logging
import time

from .extractor import extract_foro_content
from .cleaner import clean_foro_html
from .parser import parse_foro_data
from .generator import generate_foro_html_file
from .uploader import upload_foro_content

logger = logging.getLogger(__name__)

def run_foro_export_workflow(driver, course_id, wait_time=10):
    """
    Iterates through weeks 1-8, extracts the foro content, parses it,
    updates contenidos.json, and generates templated HTML files.
    """
    logger.info(f"Starting Foro export workflow for course {course_id}...")
    
    json_path = os.path.join("assets", str(course_id), "contenidos.json")
    if not os.path.exists(json_path):
        logger.warning(f"Mapping file {json_path} not found. Skipping foro export.")
        return False
        
    with open(json_path, "r", encoding="utf-8") as f:
        try:
            contenidos_data = json.load(f)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse JSON in {json_path}")
            return False
            
    template_path = os.path.join("assets", "templates", "foro.html")
    if not os.path.exists(template_path):
        logger.error(f"Foro template not found at {template_path}. Cannot generate HTML files.")
        return False
        
    updated = False
    for i in range(1, 9):
        week_name = f"Semana {i}"
        
        if week_name not in contenidos_data:
            logger.info(f"{week_name} not found in json data, skipping.")
            continue
            
        raw_html = extract_foro_content(driver, week_name, wait_time)
        if raw_html is not None:
            # Save the raw HTML to a /raw folder
            raw_output_filename = f"RAW_s{i}_foro.html"
            raw_output_path = os.path.join("assets", str(course_id), "foro", "raw", raw_output_filename)
            os.makedirs(os.path.dirname(raw_output_path), exist_ok=True)
            with open(raw_output_path, "w", encoding="utf-8") as f:
                f.write(raw_html)
            logger.info(f"Saved raw foro HTML to {raw_output_path}")

            clean_html_str = clean_foro_html(raw_html)
            parsed_data = parse_foro_data(clean_html_str)
            
            # Update the json data structure
            contenidos_data[week_name]["foro"] = parsed_data
            updated = True
            logger.info(f"Successfully processed foro for {week_name}")
            
            # Generate the HTML file
            output_filename = f"s{i}_foro.html"
            output_path = os.path.join("assets", str(course_id), "foro", output_filename)
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            generate_foro_html_file(parsed_data, template_path, output_path)
            logger.info(f"Generated Foro HTML at {output_path}")
            
            time.sleep(1)
            
    if updated:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(contenidos_data, f, ensure_ascii=False, indent=4)
        logger.info(f"Successfully updated {json_path} with foro content.")
        
        # --- NEW STEP: Upload generated HTML back to Moodle ---
        logger.info("Starting upload of generated Foro HTML files to Moodle...")
        for i in range(1, 9):
            output_filename = f"s{i}_foro.html"
            output_path = os.path.join("assets", str(course_id), "foro", output_filename)
            
            if os.path.exists(output_path):
                with open(output_path, "r", encoding="utf-8") as f:
                    html_to_upload = f.read()
                
                week_name = f"Semana {i}"
                # For week i, the forum is called "Si | Foro" (e.g., "S3 | Foro")
                foro_resource_name = f"S{i} | Foro"
                success = upload_foro_content(driver, course_id, week_name, foro_resource_name, html_to_upload, wait_time)
                if success:
                    logger.info(f"Successfully uploaded {output_filename} to {week_name}")
                else:
                    logger.error(f"Failed to upload {output_filename} to {week_name}")
            else:
                logger.debug(f"File {output_path} not found, skipping upload for Week {i}.")
    else:
        logger.info("No foro content was extracted or updated.")
        
    return True
