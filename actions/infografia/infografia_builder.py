import os
import re
from bs4 import BeautifulSoup
from config.settings import Config
from actions.infografia.generators.info_slide import _create_info_slide
from actions.infografia.generators.pregunta_slide import _create_pregunta_slide
from actions.infografia.generators.referencias_slide import _build_biblio_slide, split_paragraphs_by_limit
from actions.infografia.infografia_template_manager import reset_used_templates

def generate_infografia_html(
    parsed_data,
    base_url,
    week_num,
    course_title="Nombre del curso",
    presentation_title="Título presentación",
    infografia_subtitle="",
):
    reset_used_templates()
    """
    Generates the HTML for the infografia using templates.
    infografia_subtitle: the document-level title extracted from the RAW docData
    paragraph (e.g. "Acuerdos que mueven el mundo"). When present it is used as
    the cover <h1>; presentation_title (week name) is shown as a secondary label.
    """
    general_template_path = os.path.join(
        "assets", "templates", "infografias", "general.html"
    )

    with open(general_template_path, "r", encoding="utf-8") as f:
        general_html = f.read()

    # The general_html has the structure we need to build upon.
    soup = BeautifulSoup(general_html, "html.parser")
    carousel_inner = soup.find("div", class_="carousel-inner")

    if not carousel_inner:
        return ""

    # Clear out all items except the cover
    cover_item = carousel_inner.find("div", class_="v-info-item-cover")
    carousel_inner.clear()

    # Customize cover
    if cover_item:
        if cover_item.find("h3"):
            cover_item.find("h3").string = course_title
        if cover_item.find("h1"):
            # Use the Moodle docData subtitle (e.g. "Acuerdos que mueven el mundo")
            # as the main h1. If not available, fall back to the week name.
            cover_item.find("h1").string = (
                infografia_subtitle if infografia_subtitle else presentation_title
            )
        carousel_inner.append(cover_item)

    image_seq = 1

    def get_image_url(image_url):
        nonlocal image_seq
        if image_url:
            ext = os.path.splitext(image_url.split("?")[0])[-1].lower()
            if ext not in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".bmp"}:
                ext = ".jpg"
            img_filename = f"s{week_num}_info_{image_seq:02d}{ext}"
            image_seq += 1
            return base_url + img_filename
        return ""

    # Generate slides
    # Build pregunta_slides keyed by the explicit slide number embedded in the
    # pregunta title: "Pregunta Slide N" → key N, so it is always paired with
    # the info slide whose title says "Slide N".
    pregunta_slides = {}
    negative_counter = -1
    for slide in parsed_data.get("slides", []):
        if slide["type"] == "pregunta":
            num = slide.get("slide_number")
            if num is not None:
                pregunta_slides[num] = slide
            else:
                pregunta_slides[negative_counter] = slide
                negative_counter -= 1

    info_slide_count = 0
    for slide_idx, slide in enumerate(parsed_data.get("slides", [])):
        if slide["type"] == "info":
            info_slide_count += 1
            _create_info_slide(
                soup,
                slide,
                slide_idx,
                carousel_inner,
                base_url,
                week_num,
                None,  # No embedded preguntas
                info_slide_count,
                get_image_url,
            )
            # Append paired pregunta slide right after the info slide
            info_slide_number = slide.get("slide_number")
            if info_slide_number is not None and info_slide_number in pregunta_slides:
                q_slide = _create_pregunta_slide(soup, pregunta_slides[info_slide_number], slide_idx + 1000)
                carousel_inner.append(q_slide)
                del pregunta_slides[info_slide_number]

        elif slide["type"] == "referencias":
            # Paginate references: split into pages at whole-paragraph boundaries
            # so that no page exceeds 65 words / 525 chars (no spaces) / 600 chars (with spaces).
            pages = []
            remaining = list(slide["content"])
            while remaining:
                first_page, remaining = split_paragraphs_by_limit(
                    remaining, max_words=65, max_chars_nospace=525, max_chars_space=600
                )
                pages.append(first_page)

            for page_idx, page_refs in enumerate(pages):
                is_last = page_idx == len(pages) - 1
                heading = "Bibliografía" if page_idx == 0 else "Bibliografía"
                ref_slide = _build_biblio_slide(
                    soup, page_refs, heading, base_url, is_last=is_last
                )
                carousel_inner.append(ref_slide)

    # Append any remaining preguntas that weren't paired
    for p_slide in pregunta_slides.values():
        q_slide = _create_pregunta_slide(soup, p_slide, 9999)
        carousel_inner.append(q_slide)

    if Config.ENABLE_INFOGRAFIA_EXPORT:
        # Final validation: remove starting dots from any header
        for header in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
            for text_node in header.find_all(string=True):
                if text_node.strip():
                    if text_node.lstrip().startswith('.'):
                        text_node.replace_with(text_node.lstrip()[1:].lstrip())
                    break  # Only check the first non-empty text node
                    
    formatter = "minimal" if Config.ENABLE_INFOGRAFIA_EXPORT else "html"
    final_html = soup.prettify(formatter=formatter)
    
    if Config.ENABLE_INFOGRAFIA_EXPORT:
        # Fix spaces before dots, e.g., "word ." -> "word."
        final_html = re.sub(r'([a-zA-ZáéíóúÁÉÍÓÚñÑ])\s+\.', r'\1.', final_html)
        
    return final_html


