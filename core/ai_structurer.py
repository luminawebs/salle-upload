import os
import json
import logging
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

def get_gemini_client():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logger.error("GEMINI_API_KEY environment variable not found. AI fallback disabled.")
        return None
    return genai.Client(api_key=api_key)

def extract_missing_questions(html_content: str) -> dict:
    """
    Uses Gemini to extract questions from HTML when regex parsing fails.
    Returns a dictionary with 'extracted_questions' and 'code_improvement_feedback'.
    """
    client = get_gemini_client()
    if not client:
        return {"extracted_questions": [], "code_improvement_feedback": "AI disabled due to missing API key."}
        
    prompt = f"""
You are an expert software developer and data parser.
The following HTML contains quiz questions, but our regex/DOM parser failed to extract them.
Your task is twofold:
1. Extract the questions, options, and identify the correct option into the provided JSON schema.
2. Analyze the raw HTML and provide a short, actionable explanation of why standard regex might have failed (e.g. "The correct answer has no marker, it's just bolded" or "The question number uses Roman numerals"). Suggest a specific Python Regex pattern or BeautifulSoup logic to fix our pre-LLM parser.

Raw HTML to parse:
```html
{html_content}
```
"""
    try:
        response = client.models.generate_content(
            model='gemini-3.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema={
                    "type": "OBJECT",
                    "properties": {
                        "extracted_questions": {
                            "type": "ARRAY",
                            "items": {
                                "type": "OBJECT",
                                "properties": {
                                    "stem_html": {"type": "STRING"},
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
                        "code_improvement_feedback": {"type": "STRING"}
                    },
                    "required": ["extracted_questions", "code_improvement_feedback"]
                }
            )
        )
        return json.loads(response.text)
    except Exception as e:
        logger.error(f"Gemini API error during question extraction: {e}")
        return {"extracted_questions": [], "code_improvement_feedback": f"Gemini API failed: {e}"}

def analyze_selenium_error(error_traceback: str, current_url: str = "", context: str = "") -> str:
    """
    Uses Gemini to analyze a Selenium failure and suggest code improvements.
    """
    client = get_gemini_client()
    if not client:
        return "AI disabled due to missing API key."
        
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
    try:
        response = client.models.generate_content(
            model='gemini-3.5-flash',
            contents=prompt
        )
        return response.text.strip()
    except Exception as e:
        logger.error(f"Gemini API error during Selenium analysis: {e}")
        return f"Gemini API failed: {e}"
