"""
Legacy AI integrations, kept for reference only — nothing calls them.

- validate_and_extract_questions: the quiz "QA layer" that rewrote a quiz's
  questions with the AI's version without the user seeing it (removed from
  the export after it left a quiz with no questions).
- analyze_selenium_error: an AI suggestion for each failed quiz step.

The only active AI is the reviewed quiz proposals (core/ai_question_shadow.py,
core/ai_question_review.py). The document-structure validator that used to
run during "Creando secciones y actividades" is next to this file
(parser_validator.py, ai_document_parser.py, document_splitter.py).
"""
import json
import logging

from google.genai import types  # noqa: F401  (used by the code below as it was)

from core.ai_structurer import generate_json, get_ai_config, get_gemini_client  # noqa: F401

logger = logging.getLogger(__name__)


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
