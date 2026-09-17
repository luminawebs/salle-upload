import os
import json
import logging
from google.genai import types
from dotenv import load_dotenv
from config.settings import Config
from core.ai_structurer import get_gemini_client, get_ai_config

load_dotenv()

logger = logging.getLogger(__name__)

def parse_chunk_with_ai(chunk_html: str, course_id=None) -> dict:
    """
    Sends an HTML chunk to Gemini to extract activities, rubrics, etc.
    Requires the exact original HTML fragments to be returned.
    """
    model_name = get_ai_config()["model_name"]
    empty_result = lambda warnings: {
        "metadata": {
            "confidence": 0.0,
            "warnings": warnings,
            "parser_version": "1.0",
            "model": model_name,
            "schema_version": "1.0"
        },
        "activities": []
    }

    # get_gemini_client() is the single shared gate for all three AI
    # integrations: checks ENABLE_AI_FEATURES, the spending cap
    # (core/ai_budget_guard.py), and that an API key is actually present —
    # this used to build its own bare genai.Client() with none of those
    # checks.
    client = get_gemini_client()
    if not client:
        return empty_result(["AI disabled (feature flag off, budget exceeded, or no API key)"])

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
6. parser_version must be "1.0", model must be "{model_name}", schema_version must be "1.0".

ORIGINAL HTML CHUNK:
{chunk_html}
    """

    import time

    max_retries = 3
    base_delay = 2

    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=schema,
                    temperature=0.0,
                ),
            )

            token_usage = {"input": 0, "output": 0, "total": 0, "cached": 0, "model": model_name}
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                token_usage["input"] = getattr(response.usage_metadata, 'prompt_token_count', 0)
                token_usage["output"] = getattr(response.usage_metadata, 'candidates_token_count', 0)
                token_usage["total"] = getattr(response.usage_metadata, 'total_token_count', 0)
                token_usage["cached"] = getattr(response.usage_metadata, 'cached_content_token_count', 0)

            from core.ai_budget_guard import record_usage
            record_usage("shadow_structure_validator", token_usage, course_id=course_id)

            return json.loads(response.text)
        except Exception as e:
            error_str = str(e)
            if "503" in error_str and attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                logger.warning(f"AI parsing failed with 503, retrying in {delay}s (Attempt {attempt + 1}/{max_retries})...")
                time.sleep(delay)
            else:
                logger.error(f"AI parsing failed: {e}")
                return empty_result([str(e)])
