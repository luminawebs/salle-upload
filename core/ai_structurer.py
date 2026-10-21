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
