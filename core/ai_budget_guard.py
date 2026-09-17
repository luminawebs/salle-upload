"""
A hard spending cap for AI calls, plus a per-call audit ledger.

This exists to answer two questions directly:
- "How do I validate the usage/cost of each task?" -> every call appends one
  entry to ai_usage_ledger.json with its exact token counts and estimated
  cost, timestamped and tagged with which of the three AI integrations made
  the call.
- "How do I avoid overcosts?" -> is_budget_exceeded() is checked BEFORE any
  AI call is attempted (not after), so once Config.AI_BUDGET_USD is reached,
  every further call is refused at the source — independent of anyone
  remembering to flip ENABLE_AI_FEATURES off. Google Cloud billing
  alerts/quotas are still the real safety net (this can't stop a bill that's
  already been charged), but this stops *this application* from generating
  more of it once you've decided you're done spending.

Cost is only ever an estimate: it's computed from Config.AI_COST_PER_1M_*
rates, which you must fill in yourself from Google's current pricing page
for whichever model you're actually using — this module never guesses a
price. Left at 0 (the default), estimated cost is always $0.00 and the
ledger becomes token-count tracking only, with no dollar figure and no
enforced cap regardless of AI_BUDGET_USD.
"""
import os
import json
import logging
import time
from config.settings import Config

logger = logging.getLogger(__name__)

LEDGER_PATH = os.path.join(Config.BASE_DIR, "ai_usage_ledger.json")


def _load_ledger() -> list:
    if not os.path.exists(LEDGER_PATH):
        return []
    try:
        with open(LEDGER_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Could not read {LEDGER_PATH}: {e}. Treating usage history as empty.")
        return []


def _estimate_cost_usd(token_usage: dict) -> float:
    input_tokens = token_usage.get("input", 0) or 0
    output_tokens = token_usage.get("output", 0) or 0
    input_cost = (input_tokens / 1_000_000) * Config.AI_COST_PER_1M_INPUT_TOKENS_USD
    output_cost = (output_tokens / 1_000_000) * Config.AI_COST_PER_1M_OUTPUT_TOKENS_USD
    return round(input_cost + output_cost, 6)


def total_spent_usd() -> float:
    """Sum of every estimated_cost_usd entry ever recorded."""
    return round(sum(entry.get("estimated_cost_usd", 0) for entry in _load_ledger()), 6)


def is_budget_exceeded() -> bool:
    """
    Pre-flight check — call this BEFORE attempting an AI call, not after.
    Always False if AI_BUDGET_USD is 0 (no cap configured).
    """
    if Config.AI_BUDGET_USD <= 0:
        return False
    exceeded = total_spent_usd() >= Config.AI_BUDGET_USD
    if exceeded:
        logger.warning(
            f"AI budget guard: ${total_spent_usd():.4f} spent >= "
            f"${Config.AI_BUDGET_USD:.4f} budget. Refusing further AI calls "
            f"until AI_BUDGET_USD is raised or ai_usage_ledger.json is reset."
        )
    return exceeded


def record_usage(integration: str, token_usage: dict, course_id=None, context: str = "") -> dict:
    """
    Appends one ledger entry for a completed AI call and returns it.

    integration: short tag for which of the three AI features made this
    call, e.g. "shadow_structure_validator", "quiz_qa", "selenium_error_diagnosis".
    """
    entry = {
        "timestamp": time.time(),
        "integration": integration,
        "course_id": course_id,
        "context": context,
        "model": token_usage.get("model", "unknown"),
        "input_tokens": token_usage.get("input", 0),
        "output_tokens": token_usage.get("output", 0),
        "cached_tokens": token_usage.get("cached", 0),
        "total_tokens": token_usage.get("total", 0),
        "estimated_cost_usd": _estimate_cost_usd(token_usage),
    }

    ledger = _load_ledger()
    ledger.append(entry)
    try:
        with open(LEDGER_PATH, "w", encoding="utf-8") as f:
            json.dump(ledger, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Could not write {LEDGER_PATH}: {e}")

    running_total = total_spent_usd()
    if Config.AI_COST_PER_1M_INPUT_TOKENS_USD == 0 and Config.AI_COST_PER_1M_OUTPUT_TOKENS_USD == 0:
        logger.info(
            f"AI usage [{integration}]: {entry['total_tokens']} tokens "
            f"(cost unknown — set AI_COST_PER_1M_INPUT_TOKENS_USD / "
            f"AI_COST_PER_1M_OUTPUT_TOKENS_USD in .env to estimate $)"
        )
    else:
        logger.info(
            f"AI usage [{integration}]: {entry['total_tokens']} tokens, "
            f"~${entry['estimated_cost_usd']:.4f} this call, "
            f"~${running_total:.4f} total logged in ai_usage_ledger.json"
        )
        if Config.AI_BUDGET_USD > 0 and running_total >= Config.AI_BUDGET_USD * 0.8:
            logger.warning(
                f"AI budget guard: ${running_total:.4f} of ${Config.AI_BUDGET_USD:.4f} "
                f"budget used ({running_total / Config.AI_BUDGET_USD:.0%})."
            )

    return entry
