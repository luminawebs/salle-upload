import os
import json
import logging
from google import genai
from google.genai import types
from dotenv import load_dotenv
from config.settings import Config

load_dotenv()

logger = logging.getLogger(__name__)

def get_gemini_client(require_feature_flag=True):
    """require_feature_flag=False: for a caller with its own switch (the quiz
    shadow mode, AI_QUESTIONS_SHADOW), so it runs without ENABLE_AI_FEATURES
    turning on the other AI integrations too. Budget and key still apply."""
    if require_feature_flag and not getattr(Config, "ENABLE_AI_FEATURES", True):
        logger.info("AI features are disabled via configuration.")
        return None

    from core.ai_budget_guard import is_budget_exceeded
    if is_budget_exceeded():
        return None

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logger.error("GEMINI_API_KEY environment variable not found. AI fallback disabled.")
        return None
    return genai.Client(api_key=api_key)

import time
import random
from google.genai.errors import APIError

def get_ai_config():
    return {
        "model_name": os.environ.get("GEMINI_MODEL_NAME", "gemini-3.5-flash"),
        "retry_count": int(os.environ.get("AI_RETRY_COUNT", "5")),
        "initial_delay": float(os.environ.get("AI_RETRY_INITIAL_DELAY", "2")),
        "max_delay": float(os.environ.get("AI_RETRY_MAX_DELAY", "32")),
        "temperature": float(os.environ.get("AI_TEMPERATURE", "0.0")),
        "top_p": float(os.environ.get("AI_TOP_P", "0.95")),
        "top_k": int(os.environ.get("AI_TOP_K", "40"))
    }

def validate_and_extract_questions(html_content: str, standard_parser_output: str = "[]", parsed_q_count: int = 0, course_id=None) -> dict:
    """
    Uses Gemini to validate and extract questions from HTML, acting as a QA layer.
    Returns a dictionary with 'is_perfect', 'corrections', 'additions', 'removals', 'metadata', and 'token_usage'.
    """
    client = get_gemini_client()
    if not client:
        return {"error": "AI disabled due to missing API key."}
        
    prompt = f"""
You are an expert QA Automation Engineer and Data Parser.
Your task is to validate a set of questions extracted by our standard parser against the raw HTML source.

We found {parsed_q_count} questions. Below is a JSON representation of those extracted questions:
```json
{standard_parser_output}
```

Raw HTML source:
```html
{html_content}
```

Validation Rules:
1. Verify no questions were missed.
2. Verify all question numbering and answer options are correct.
3. CRITICAL: Verify that images (`<img>` tags) and tables (`<table>` tags) belonging to the question stem or options were preserved. The standard parser might strip them; you MUST restore them from the HTML.
4. Verify mathematical expressions and formatting are intact.

Instructions:
- If the standard parser output is 100% correct and nothing is missing, set `is_perfect` to true.
- If you need to make changes, set `is_perfect` to false. 
- In `corrections`, provide the index (0-based) of the parser output you are fixing, and the fully corrected question object.
- In `additions`, provide any completely new questions that were missed.
- In `removals`, provide the indices (0-based) of items that are not actually questions and should be deleted.
- CRITICAL: For "Tipo: completar" questions, ensure the gap markers like `[respuesta]` are preserved in the stem_html.
- CRITICAL: For "Tipo: arrastrar_soltar" questions, ensure the gap markers like `[[1]]` are preserved in the stem_html, and options are extracted correctly.
- For questions that truly have no standard multiple-choice options, leave their `options` array empty.
"""

    schema = {
        "type": "OBJECT",
        "properties": {
            "is_perfect": {"type": "BOOLEAN"},
            "metadata": {
                "type": "OBJECT",
                "properties": {
                    "images_detected": {"type": "BOOLEAN"},
                    "images_preserved": {"type": "BOOLEAN"},
                    "tables_detected": {"type": "BOOLEAN"},
                    "tables_preserved": {"type": "BOOLEAN"},
                    "warnings": {"type": "STRING"}
                }
            },
            "corrections": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "index": {"type": "INTEGER"},
                        "corrected_question": {
                            "type": "OBJECT",
                            "properties": {
                                "stem_html": {"type": "STRING"},
                                "correct_feedback_html": {"type": "STRING"},
                                "incorrect_feedback_html": {"type": "STRING"},
                                "options": {
                                    "type": "ARRAY",
                                    "items": {
                                        "type": "OBJECT",
                                        "properties": {
                                            "text_html": {"type": "STRING"},
                                            "is_correct": {"type": "BOOLEAN"}
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "additions": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "stem_html": {"type": "STRING"},
                        "correct_feedback_html": {"type": "STRING"},
                        "incorrect_feedback_html": {"type": "STRING"},
                        "options": {
                            "type": "ARRAY",
                            "items": {
                                "type": "OBJECT",
                                "properties": {
                                    "text_html": {"type": "STRING"},
                                    "is_correct": {"type": "BOOLEAN"}
                                }
                            }
                        }
                    }
                }
            },
            "removals": {
                "type": "ARRAY",
                "items": {"type": "INTEGER"}
            }
        },
        "required": ["is_perfect", "metadata", "corrections", "additions", "removals"]
    }

    return generate_json(client, prompt, schema, "quiz_qa", course_id=course_id)


def _token_usage(response, model_name):
    usage = {"input": 0, "output": 0, "total": 0, "cached": 0, "model": model_name, "finish_reason": "UNKNOWN"}
    meta = getattr(response, "usage_metadata", None)
    if meta:
        usage["input"] = getattr(meta, "prompt_token_count", 0) or 0
        usage["output"] = getattr(meta, "candidates_token_count", 0) or 0
        usage["total"] = getattr(meta, "total_token_count", 0) or 0
        usage["cached"] = getattr(meta, "cached_content_token_count", 0) or 0
    if getattr(response, "candidates", None):
        usage["finish_reason"] = str(getattr(response.candidates[0], "finish_reason", "UNKNOWN"))
    return usage


def generate_json(client, prompt: str, schema: dict, integration: str, course_id=None, context: str = "") -> dict:
    """
    One structured-output call with exponential backoff on transient errors
    (429/5xx). Returns the parsed JSON plus "token_usage", or {"error": ...}.
    Every completed call is recorded in the usage ledger under `integration`.
    """
    config = get_ai_config()
    for attempt in range(config["retry_count"]):
        try:
            response = client.models.generate_content(
                model=config["model_name"],
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=schema,
                    temperature=config["temperature"],
                    top_p=config["top_p"],
                    top_k=config["top_k"]
                )
            )
            token_usage = _token_usage(response, config["model_name"])
            from core.ai_budget_guard import record_usage
            record_usage(integration, token_usage, course_id=course_id, context=context)
            if token_usage["finish_reason"].endswith("MAX_TOKENS"):
                return {"error": "Respuesta cortada (MAX_TOKENS).", "token_usage": token_usage}
            result = json.loads(response.text)
            result["token_usage"] = token_usage
            return result

        except Exception as e:
            is_transient = isinstance(e, APIError) and e.code in [429, 500, 502, 503, 504]
            if is_transient and attempt < config["retry_count"] - 1:
                delay = min(config["initial_delay"] * (2 ** attempt) + random.uniform(0, 1), config["max_delay"])
                logger.warning(f"AI transient error ({e}). Retrying in {delay:.2f}s... (Attempt {attempt+1}/{config['retry_count']})")
                time.sleep(delay)
            else:
                logger.error(f"Gemini API error exhausted retries or encountered fatal error: {e}")
                return {"error": str(e), "token_usage": {}}

    return {"error": "Retry logic failed unexpectedly.", "token_usage": {}}

def analyze_selenium_error(error_traceback: str, current_url: str = "", context: str = "", course_id=None) -> str:
    """
    Uses Gemini to analyze a Selenium failure and suggest code improvements.
    """
    client = get_gemini_client()
    if not client:
        return "AI disabled (feature flag off, budget exceeded, or no API key)."

    prompt = f"""
You are an expert QA Automation Engineer.
Our Selenium script failed during execution in Moodle.

Context/Action being performed: {context}
Current URL: {current_url}

Traceback:
```
{error_traceback}
```

Please provide a brief, actionable "Code Improvement Prompt" for the developer.
Focus strictly on how to improve the Selenium code (e.g., "Add an Explicit Wait for the button with ID 'id_submit'", or "The selector might be stale, catch StaleElementReferenceException"). Do not write the full script, just the actionable advice.
"""
    model_name = get_ai_config()["model_name"]
    try:
        response = client.models.generate_content(
            model=model_name,
            contents=prompt
        )

        token_usage = {"input": 0, "output": 0, "total": 0, "cached": 0, "model": model_name}
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            token_usage["input"] = getattr(response.usage_metadata, 'prompt_token_count', 0)
            token_usage["output"] = getattr(response.usage_metadata, 'candidates_token_count', 0)
            token_usage["total"] = getattr(response.usage_metadata, 'total_token_count', 0)
            token_usage["cached"] = getattr(response.usage_metadata, 'cached_content_token_count', 0)

        from core.ai_budget_guard import record_usage
        record_usage("selenium_error_diagnosis", token_usage, course_id=course_id, context=context)

        return response.text.strip()
    except Exception as e:
        logger.error(f"Gemini API error during Selenium analysis: {e}")
        return f"Gemini API failed: {e}"
