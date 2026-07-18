import re
from bs4 import BeautifulSoup
from config.settings import Config
from actions.infografia.utils import _export_strip_colon

def parse_infografia_html(raw_html):
    """
    Parses the raw HTML of VIR - INFOGRAFRAFÍA INTERACTIVA and extracts slides.
    Returns a dictionary with 'slides' list and 'deposit_photos' list.

    Robustness notes
    ----------------
    * Slide boundaries are marked by <h2> elements whose text starts with
      "Slide N:" or "Pregunta slide N". The RAW source always has a *second*
      <h2> immediately after with the real slide subtitle — that is kept as
      slide meta, not treated as a new slide.
    * Reference list items (<li>) embed URLs as <a href="…"> whose visible
      text may be broken across multiple inline elements. We reconstruct each
      reference by combining visible text with the canonical href so the output
      is clean regardless of how Moodle rendered the link.
    * Deposit-photos URLs appear as highlighted <p> containing only an <a>
      tag; those are extracted as the slide image and excluded from content.
    """
    deposit_photos_urls = []
    if not raw_html:
        return {"slides": [], "deposit_photos": [], "infografia_subtitle": ""}

    soup = BeautifulSoup(raw_html, "html.parser")

    # ── Extract the document subtitle from the first docData <p> ─────────────
    # Moodle embeds the infografia name in the first <p class="docData;...">.
    # The visible text is "Infografía: <subtitle>"; we strip the prefix.
    infografia_subtitle = ""
    first_p = soup.find("p", class_=lambda c: c and c.startswith("docData"))
    if first_p:
        raw_sub = first_p.get_text(separator=" ", strip=True)
        # Strip the "Infografía: " label prefix
        infografia_subtitle = re.sub(r"(?i)^infograf[íi]a:\s*", "", raw_sub).strip()

    # Collect headings, p, and li — but skip <p> that live inside <li> (Moodle
    # wraps <li> content in <p> tags; we handle them via the <li> itself).
    raw_elements = soup.find_all(["h2", "h3", "h4", "h5", "h6", "p", "li"])
    elements = []
    for el in raw_elements:
        if el.name == "p" and el.find_parent("li"):
            continue
        if el.name == "li" and el.find_parent("p"):
            continue
        elements.append(el)

    def _extract_slide_number(text):
        match = re.search(r"(?i)^(?:Pregunta\s+)?Slide\s+(\d+)", text)
        return int(match.group(1)) if match else None

    slides = []
    current_slide = None
    # Flag: the very next heading-like element after a "Slide N:" trigger is the
    # subtitle, not a new slide boundary.
    _expect_subtitle_heading = False

    for el in elements:
        import copy
        el_copy = copy.copy(el)
        for br in el_copy.find_all("br"):
            br.replace_with("\n")
        raw_text = el_copy.get_text(separator=" ").replace("\xa0", " ")
        lines = [re.sub(r" +", " ", line).strip() for line in raw_text.split("\n")]
        lines = [line for line in lines if line]
        
        text = " ".join(lines)
        if not text:
            continue

        is_slide_trigger = re.search(r"(?i)^(Pregunta\s+)?Slide\s+\d+", text)
        is_button = re.search(r"(?i)^B\s*o\s*t\s*[óo]\s*n\.?", text)
        is_referencias = re.search(r"(?i)^(Referencias|Bibliograf[íi]a)\s*:?$", text)

        # ── Slide / Pregunta-slide boundary ─────────────────────
        if el.name in ("h2", "h3", "h4", "h5", "h6", "p") and not is_button and not is_referencias:
            if _expect_subtitle_heading:
                # Only info slides use a second heading as subtitle.
                # Pregunta slides start directly with the question paragraph,
                # so consuming that as subtitle causes empty question content.
                if (
                    not is_slide_trigger
                    and current_slide is not None
                    and current_slide.get("type") == "info"
                    and el.name in ("h2", "h3", "h4", "h5", "h6", "p")
                ):
                    _expect_subtitle_heading = False
                    current_slide["subtitle"] = text
                    continue
                # It IS a new slide trigger — reset the flag and fall through.
                _expect_subtitle_heading = False

            if is_slide_trigger:
                if current_slide:
                    slides.append(current_slide)
                is_pregunta = "pregunta" in text.lower()
                current_slide = {
                    "title": text,
                    "slide_number": _extract_slide_number(text),
                    "subtitle": "",
                    "type": "pregunta" if is_pregunta else "info",
                    "content": [],
                    "buttons": [],
                    "image": None,
                    "options": [],
                    "correct_answer": None,
                    "feedback": None,
                }
                _expect_subtitle_heading = True
                continue

            # Only treat an <h2>/<h3>/<h4>/<h5>/<h6> as a subtitle if no slide trigger was found.
            if current_slide is not None and el.name in ("h2", "h3", "h4", "h5", "h6"):
                current_slide["subtitle"] = text
                continue

        # ── Referencias / Bibliografía heading ────────────────────────────
        if is_referencias:
            if current_slide:
                slides.append(current_slide)
            current_slide = {
                "title": text,
                "type": "referencias",
                "content": [],
                "buttons": [],
                "image": None,
            }
            _expect_subtitle_h2 = False
            continue

        if current_slide is None:
            continue

        # ── Route content based on slide type ─────────────────────────────
        slide_type = current_slide["type"]

        if slide_type == "referencias":
            ref_text = _build_reference_text(el)
            if ref_text:
                current_slide["content"].append(ref_text)

        elif slide_type == "info":
            first_a = el.find("a")
            if first_a and "depositphotos.com" in first_a.get("href", ""):
                url = first_a.get("href")
                current_slide["image"] = url
                if url not in deposit_photos_urls:
                    deposit_photos_urls.append(url)
                for a_tag in el.find_all("a"):
                    a_tag.decompose()
                text = el.get_text(separator=" ", strip=True)
                if not text:
                    continue
            # Bug 1 fix: depositphotos URL may also appear as plain span text (no <a> tag).
            # Strip it from the text and record as the slide image.
            dp_match = re.search(r"https?://depositphotos\.com/\S+", text)
            if dp_match:
                url = dp_match.group(0).rstrip(".")
                if current_slide["image"] is None:
                    current_slide["image"] = url
                    if url not in deposit_photos_urls:
                        deposit_photos_urls.append(url)
                # Remove the URL from the text so it doesn't appear in content
                text = text.replace(dp_match.group(0), "").strip()
                if not text:
                    continue

            if re.search(r"(?i)^B\s*o\s*t\s*[óo]\s*n\s*\.?\s*", text):
                # We have a button. The first line might contain the title, the rest the content.
                title_seg = lines[0]
                # Remove the "Botón." prefix from the title segment
                title_seg = re.sub(r"(?i)^B\s*o\s*t\s*[óo]\s*n\s*\.?\s*", "", title_seg).strip()
                
                # Check for ':' in case they used a colon on the same line
                if len(lines) == 1 and ":" in title_seg:
                    parts = title_seg.split(":", 1)
                    btn_title = parts[0].strip() + ":"
                    btn_content = parts[1].strip()
                    btn_contents = [btn_content] if btn_content else []
                else:
                    btn_title = title_seg
                    btn_contents = lines[1:]

                if Config.ENABLE_INFOGRAFIA_EXPORT:
                    btn_title = _export_strip_colon(btn_title)
                    if btn_title.startswith("."):
                        btn_title = btn_title[1:].lstrip()

                btn_obj = {"title": btn_title, "content": btn_contents}
                current_slide["buttons"].append(btn_obj)
            else:
                if current_slide["buttons"]:
                    current_slide["buttons"][-1]["content"].append(text)
                else:
                    current_slide["content"].append(text)

        elif slide_type == "pregunta":
            # ── Options: split by <br> first, then by letter-) pattern ──────
            # Moodle can pack all options in a single <p> separated by <br>
            # e.g. "a) Objeto\nb) Consentimiento\nc) Causa"
            # We also handle the RAW paragraph where each option is a separate <p>.
            if el.name in ("p", "li"):
                # Use the pre-computed `lines` which already split by <br> safely.
                candidate_opts = [s for s in lines if re.match(r"^[a-eA-E]\)", s)]
                if len(candidate_opts) > 1:
                    for opt in candidate_opts:
                        current_slide["options"].append(opt)
                    non_opts = [s for s in lines if not re.match(r"^[a-eA-E]\)", s)]
                    for s in non_opts:
                        current_slide["content"].append(s)
                    continue  # skip the fallback logic below

                # --- Fallback: no <br> splits, use full text ---
                text_full = el.get_text(separator=" ", strip=True)
                text_full = re.sub(r"\s+", " ", text_full).strip()

                # Split a single string "a) Opt1 b) Opt2 c) Opt3" into parts
                split_opts = re.split(r"(?<=[^a-zA-Z])(?=[a-eA-E]\))", text_full)
                split_opts = [s.strip() for s in split_opts if s.strip()]
                real_opts = [s for s in split_opts if re.match(r"^[a-eA-E]\)", s)]

                if len(real_opts) > 1:
                    for opt in real_opts:
                        current_slide["options"].append(opt)
                elif re.match(r"^[a-eA-E]\)", text_full):
                    current_slide["options"].append(text_full)
                elif re.search(r"(?i)Respuesta\s+correcta:", text_full):
                    ans = re.sub(
                        r"(?i).*Respuesta\s+correcta:\s*", "", text_full
                    ).strip()
                    current_slide["correct_answer"] = ans
                elif re.search(r"(?i)Retroalimentaci[óo]n:", text_full):
                    fb = re.sub(
                        r"(?i).*Retroalimentaci[óo]n:\s*", "", text_full
                    ).strip()
                    if fb:
                        current_slide["feedback"] = fb
                else:
                    # Strip "Pregunta N" prefix from question text
                    text_full = re.sub(r"(?i)^Pregunta\s+\d+[:\s]*", "", text_full).strip()
                    if current_slide.get("correct_answer"):
                        if not current_slide.get("feedback"):
                            current_slide["feedback"] = text_full
                    else:
                        current_slide["content"].append(text_full)
            else:
                # h2 or other element inside pregunta — skip
                pass

    if current_slide:
        slides.append(current_slide)

    return {
        "infografia_subtitle": infografia_subtitle,
        "slides": slides,
        "deposit_photos": deposit_photos_urls,
    }


def _build_reference_text(el):
    """
    Build a clean, single-line reference string from a <p> or <li> element.

    For each <a> tag, uses the href attribute as the canonical URL to avoid
    broken URLs caused by Moodle splitting anchor text across inline elements.
    """
    parts = []

    def _visit(node):
        if getattr(node, "name", None) is None:
            t = str(node).strip()
            if t:
                parts.append(t)
            return
        if node.name == "a":
            href = node.get("href", "").strip()
            if href:
                parts.append(href)
            return
        if Config.ENABLE_INFOGRAFIA_EXPORT and node.name in ("i", "em", "b", "strong"):
            t = node.get_text(separator=" ", strip=True)
            if t:
                parts.append(f"<b><i>{t}</i></b>")
            return

        for child in node.children:
            _visit(child)

    _visit(el)

    result = re.sub(r"\s+", " ", " ".join(parts)).strip()
    result = result.replace("\xa0", " ").strip()
    
    if Config.ENABLE_INFOGRAFIA_EXPORT:
        result = re.sub(r"</b></i>\s*\.", ".</b></i>", result)
        result = re.sub(r"</b></i>\s*,", ",</b></i>", result)
        result = re.sub(r"\s+\.", ".", result)
        result = re.sub(r"\s+,", ",", result)
        
    return result if result else None


