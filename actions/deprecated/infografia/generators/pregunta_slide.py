import os
import re
from bs4 import BeautifulSoup
from config.settings import Config
from actions.infografia.generators.common import _add_controls

def _normalize_pregunta_options(raw_options):
    options = []
    for opt in raw_options:
        parts = re.split(r"(?<=[^a-zA-Z])(?=[a-eA-E]\))", opt)
        parts = [p.strip() for p in parts if p.strip()]
        if len(parts) > 1:
            options.extend(parts)
        else:
            options.append(opt.strip())

    normalized = []
    for opt in options:
        opt = opt.strip()
        opt_match = re.match(r"^([a-eA-E])\)\s*(.*)$", opt)
        if opt_match:
            normalized.append(
                f"{opt_match.group(1).upper()}. {opt_match.group(2).strip()}"
            )
        else:
            normalized.append(opt)
    return normalized


def _normalize_correct_answer(raw_answer):
    answer = (raw_answer or "").strip()
    match = re.match(r"^([a-eA-E])\)?\.?\s*(.*)$", answer)
    if match:
        letter = match.group(1).upper()
        suffix = match.group(2).strip()
        return letter, f"{letter}. {suffix}" if suffix else f"{letter}."
    return "A", "A."


def _normalize_feedback_message(feedback, prefix_word):
    text = (feedback or "").strip()
    if not text:
        return f"{prefix_word}."
    if re.search(rf"(?i)^({prefix_word})\b", text):
        return text
    return f"{prefix_word}. {text}"


def _build_pregunta_layout_from_template(soup, compact_mode):
    """
    Loads pregunta layout from a dedicated template file.
    Returns (wrapper_tag, quiz_slot_tag) or (None, None) when unavailable.
    """
    template_path = os.path.join(
        "assets", "templates", "infografias", "pregunta_afianzamiento.html"
    )
    if not os.path.exists(template_path):
        return None, None

    with open(template_path, "r", encoding="utf-8") as f:
        template_html = f.read()

    template_soup = BeautifulSoup(template_html, "html.parser")
    selector = (
        "#pregunta-layout-compact"
        if compact_mode
        else "#pregunta-layout-two-column"
    )
    layout = template_soup.select_one(selector)
    if not layout:
        return None, None

    layout_copy = BeautifulSoup(str(layout), "html.parser").find("div")
    if not layout_copy:
        return None, None

    quiz_slot = layout_copy.select_one("[data-slot='quiz']")
    return layout_copy, quiz_slot


def _create_pregunta_slide(soup, slide, slide_idx):
    q_slide = soup.new_tag(
        "div", attrs={"class": "carousel-item v-info-item-slide-1 v-info-bkg-sl1"}
    )

    # Calculate total length to select compact or two-column layout
    q_text = slide["content"][0] if slide["content"] else "¿Pregunta?"
    options = _normalize_pregunta_options(slide.get("options") or [])

    # ── Derive correct answer letter from correct_answer string ─────────––
    # correct_answer may be "b) Consentimiento", "B.", "b", or "b)"
    correct_letter, correct_display = _normalize_correct_answer(
        slide.get("correct_answer")
    )

    options_text = "".join(options)
    feedback_text = slide.get("feedback") or ""
    total_len = len(q_text) + len(options_text) + len(feedback_text)
    compact_mode = total_len > 500

    if Config.ENABLE_INFOGRAFIA_EXPORT:
        compact_mode = False

    wr, quiz_slot = _build_pregunta_layout_from_template(soup, compact_mode)
    
    if wr and Config.ENABLE_INFOGRAFIA_EXPORT and not compact_mode:
        left_col = wr.find(class_="v-info-slide-1-wr-izq")
        if left_col:
            existing_style = left_col.get("style", "")
            left_col["style"] = (existing_style + " width: 70% !important;").strip()

    if wr is None or quiz_slot is None:
        # Fallback to previous structure if template file is missing.
        wr = soup.new_tag(
            "div",
            attrs={
                "class": "virtual-txt v-info-slide-2-wr"
                if compact_mode
                else "virtual-txt v-info-slide-1-wr"
            },
        )
        if compact_mode:
            wr.append(soup.new_tag("br"))
            h2 = soup.new_tag("h2")
            h2.string = "Pregunta de afianzamiento"
            wr.append(h2)
            quiz_slot = wr
        else:
            col1 = soup.new_tag("div", attrs={"class": "v-info-slide-1-wr-izq"})
            if Config.ENABLE_INFOGRAFIA_EXPORT:
                col1["style"] = "width: 70% !important;"
            h2 = soup.new_tag("h2")
            h2.string = "Pregunta de afianzamiento"
            col1.append(h2)
            wr.append(col1)
            quiz_slot = col1

    quiz_div = soup.new_tag("div", attrs={"class": "virtual-info-quiz"})
    q_div = soup.new_tag(
        "div", attrs={"class": "v-info-question", "data-correct": correct_letter}
    )

    q_p = soup.new_tag("p")
    q_p.string = q_text
    q_div.append(q_p)

    for opt in options:
        opt_letter_m = re.match(r"^([a-eA-E])", opt)
        opt_letter = opt_letter_m.group(1).upper() if opt_letter_m else opt[0].upper()
        lbl = soup.new_tag("label", attrs={"class": "v-info-q-btn"})
        inp = soup.new_tag(
            "input",
            attrs={"type": "radio", "name": f"q{slide_idx}", "value": opt_letter},
        )
        lbl.append(inp)
        lbl.append(f" {opt}")
        q_div.append(lbl)

    feedback_correct = soup.new_tag(
        "div",
        attrs={
            "class": "v-info-feedback",
            "id": f"v-feedback-q{slide_idx}-correct",
        },
    )
    feedback_correct.string = _normalize_feedback_message(
        slide.get("feedback"), "Correcto"
    )
    q_div.append(feedback_correct)

    feedback_incorrect = soup.new_tag(
        "div",
        attrs={
            "class": "v-info-feedback",
            "id": f"v-feedback-q{slide_idx}-incorrect",
        },
    )
    feedback_incorrect.string = _normalize_feedback_message(
        slide.get("feedback"), "Incorrecto"
    )
    q_div.append(feedback_incorrect)

    quiz_div.append(q_div)
    quiz_slot.attrs.pop("data-slot", None)
    quiz_slot.append(quiz_div)

    q_slide.append(wr)
    _add_controls(soup, q_slide)
    return q_slide


def _add_pregunta_content(soup, container, pregunta_slide, slide_idx):
    q_text = pregunta_slide["content"][0] if pregunta_slide["content"] else "¿Pregunta?"

    options = _normalize_pregunta_options(pregunta_slide.get("options") or [])

    # ── Derive correct answer letter from correct_answer string ─────────––
    correct_letter, correct_display = _normalize_correct_answer(
        pregunta_slide.get("correct_answer")
    )

    quiz_div = soup.new_tag("div", attrs={"class": "virtual-info-quiz"})
    q_div = soup.new_tag(
        "div", attrs={"class": "v-info-question", "data-correct": correct_letter}
    )

    q_p = soup.new_tag("p")
    q_p.string = q_text
    q_div.append(q_p)

    for opt in options:
        opt_letter_m = re.match(r"^([a-eA-E])", opt)
        opt_letter = opt_letter_m.group(1).upper() if opt_letter_m else opt[0].upper()
        lbl = soup.new_tag("label", attrs={"class": "v-info-q-btn"})
        inp = soup.new_tag(
            "input",
            attrs={"type": "radio", "name": f"q{slide_idx}", "value": opt_letter},
        )
        lbl.append(inp)
        lbl.append(f" {opt}")
        q_div.append(lbl)

    feedback_correct = soup.new_tag(
        "div",
        attrs={"class": "v-info-feedback", "id": f"v-feedback-q{slide_idx}-correct"},
    )
    feedback_correct.string = _normalize_feedback_message(
        pregunta_slide.get("feedback"), "Correcto"
    )
    q_div.append(feedback_correct)

    feedback_incorrect = soup.new_tag(
        "div",
        attrs={"class": "v-info-feedback", "id": f"v-feedback-q{slide_idx}-incorrect"},
    )
    feedback_incorrect.string = _normalize_feedback_message(
        pregunta_slide.get("feedback"), "Incorrecto"
    )
    q_div.append(feedback_incorrect)

    quiz_div.append(q_div)
    container.append(quiz_div)


