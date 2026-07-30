import os
import json
import logging
from google import genai
from google.genai import types
from dotenv import load_dotenv
from config.settings import Config

load_dotenv()

logger = logging.getLogger(__name__)

def parse_chunk_with_ai(chunk_html: str) -> dict:
    """
    Sends an HTML chunk to Gemini to extract activities, rubrics, etc.
    Requires the exact original HTML fragments to be returned.
    """
    if not getattr(Config, "ENABLE_AI_FEATURES", True):
        logger.info("AI features are disabled via configuration.")
        return {
            "metadata": {
                "confidence": 0.0,
                "warnings": ["AI disabled via configuration"],
                "parser_version": "1.0",
                "model": "gemini-3.5-flash",
                "schema_version": "1.0"
            },
            "activities": []
        }
        
    client = genai.Client()
    
    # We define the JSON schema dictionary manually for the new SDK
    schema = {
        "type": "OBJECT",
        "properties": {
            "metadata": {
                "type": "OBJECT",
                "properties": {
                    "confidence": {"type": "NUMBER"},
                    "warnings": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "parser_version": {"type": "STRING"},
                    "model": {"type": "STRING"},
                    "schema_version": {"type": "STRING"}
                }
            },
            "activities": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "title": {"type": "STRING"},
                        "type": {"type": "STRING"},
                        "description_html": {"type": "STRING"},
                        "rubric_html": {"type": "STRING"},
                        "questionnaire_html": {"type": "STRING"}
                    }
                }
            }
        }
    }

    prompt = f"""
You are an expert HTML parser. I will give you a chunk of an educational course HTML document.
Your task is to identify the activities, and extract the EXACT original HTML for their descriptions, rubrics, and questionnaires.

CRITICAL RULES:
1. DO NOT GENERATE NEW HTML. Only copy and paste the EXACT substrings from the original HTML provided. Preserving the exact tags, attributes, and contents is mandatory.
2. The description_html should contain the instructions for the activity.
3. The rubric_html should contain the "Criterios de evaluación" or "Rúbrica" table. If none exists, leave it empty.
4. The questionnaire_html should contain the "Preguntas" or "Cuestionario". If none exists, leave it empty.
5. Evaluate your confidence (0.0 to 1.0) based on how clearly you found the elements. If you are unsure or something is missing, add a warning to the warnings array and lower the confidence.
6. parser_version must be "1.0", model must be "gemini-3.5-flash", schema_version must be "1.0".

ORIGINAL HTML CHUNK:
{chunk_html}
    """
    
    import time
    
    max_retries = 3
    base_delay = 2
    
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model='gemini-3.5-flash',
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=schema,
                    temperature=0.0,
                ),
            )
            return json.loads(response.text)
        except Exception as e:
            error_str = str(e)
            if "503" in error_str and attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                logger.warning(f"AI parsing failed with 503, retrying in {delay}s (Attempt {attempt + 1}/{max_retries})...")
                time.sleep(delay)
            else:
                logger.error(f"AI parsing failed: {e}")
                return {
                    "metadata": {
                        "confidence": 0.0,
                        "warnings": [str(e)],
                        "parser_version": "1.0",
                        "model": "gemini-3.5-flash",
                        "schema_version": "1.0"
                    },
                    "activities": []
                }
