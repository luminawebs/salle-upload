import re
from bs4 import BeautifulSoup
from config.settings import Config
from actions.infografia.utils import _export_strip_colon
from actions.infografia.generators.common import _add_controls, _add_buttons
from actions.infografia.generators.pregunta_slide import _add_pregunta_content

def _process_text_for_leer_mas(content_paragraphs):
    total_len = sum(len(p) for p in content_paragraphs)
    if total_len <= 500:
        return content_paragraphs, [], False

    slide_paragraphs = []
    modal_paragraphs = []
    current_len = 0

    for i, p in enumerate(content_paragraphs):
        # Always keep the first paragraph on the slide
        if i == 0:
            slide_paragraphs.append(p)
            current_len += len(p)
        else:
            if current_len + len(p) > 500:
                modal_paragraphs.append(p)
            else:
                slide_paragraphs.append(p)
                current_len += len(p)

    needs_leer_mas = len(modal_paragraphs) > 0
    return slide_paragraphs, modal_paragraphs, needs_leer_mas


def _add_leer_mas(soup, container, content_paragraphs, slide_idx):
    slide_paragraphs, modal_paragraphs, needs_leer_mas = _process_text_for_leer_mas(
        content_paragraphs
    )

    for p_text in slide_paragraphs:
        p = soup.new_tag("p")
        p.string = p_text
        container.append(p)

    if needs_leer_mas:
        container.append(soup.new_tag("br"))
        btn = soup.new_tag(
            "button",
            attrs={
                "class": "virtual-btn-leer-mas bg-v-blue animate__animated animate__fadeInUp",
                "data-bs-toggle": "modal",
                "data-bs-target": f"#modal-leer-mas-sl{slide_idx}",
                "style": "animation-delay: 0.4s",
            },
        )
        i_icon = soup.new_tag("i", attrs={"class": "fa fa-plus", "aria-hidden": "true"})
        btn.append(i_icon)
        btn.append(" Leer más")
        container.append(btn)

        modal = soup.new_tag(
            "div",
            attrs={
                "class": "modal fade",
                "id": f"modal-leer-mas-sl{slide_idx}",
                "tabindex": "-1",
                "aria-labelledby": "ModalLabel",
                "aria-hidden": "true",
            },
        )
        dialog = soup.new_tag(
            "div", attrs={"class": "modal-dialog modal-dialog-centered"}
        )
        content = soup.new_tag("div", attrs={"class": "modal-content"})

        header = soup.new_tag("div", attrs={"class": "modal-header bg-v-blue"})
        h3 = soup.new_tag("h3", attrs={"class": "modal-title fs-5 txt-white"})
        if not Config.ENABLE_INFOGRAFIA_EXPORT:
            h3.string = "Leer más"
        header.append(h3)
        close_btn = soup.new_tag(
            "button",
            attrs={
                "type": "button",
                "class": "btn-close bg-white",
                "data-bs-dismiss": "modal",
                "aria-label": "Close",
            },
        )
        header.append(close_btn)

        body = soup.new_tag("div", attrs={"class": "modal-body"})
        for mp in modal_paragraphs:
            p_tag = soup.new_tag("p")
            p_tag.string = mp
            body.append(p_tag)

        content.append(header)
        content.append(body)
        dialog.append(content)
        modal.append(dialog)

        container.append(modal)


def _create_info_slide(
    soup,
    slide,
    slide_idx,
    carousel_inner,
    base_url,
    week_num,
    pregunta_slides,
    info_slide_count,
    get_image_url,
):
    has_image = slide.get("image") is not None
    has_buttons = len(slide["buttons"]) > 0

    # Heading priority (fixes wrong-h2 bug):
    # 1. Strip the structural prefix "Slide N:" from the raw title to get the
    #    meaningful part, e.g. "Slide 1: Elementos del contrato..." → "Elementos del contrato..."
    # 2. If the slide also has a subtitle h2 (the centered h2 after the trigger),
    #    prefer that over the stripped title.
    # 3. NEVER use content[0] as a heading — content is always body text → <p>.
    raw_title = slide.get("title", "")
    stripped = re.sub(r"(?i)^(Pregunta\s+)?Slide\s+\d+:\s*", "", raw_title).strip()
    sub = slide.get("subtitle", "").strip()
    heading = sub if sub else (stripped if stripped else raw_title)
    heading = _export_strip_colon(heading)
    content_paragraphs = slide["content"]  # all content → body <p> tags, never <h2>

    # Check if we should append a pregunta to this info slide.
    # pregunta_slides is keyed by slide_number (N from "Pregunta Slide N").
    # We look up using this info slide's own slide_number so that
    # "Pregunta Slide 1" always lands after "Slide 1", etc.
    pregunta_to_append = None
    if Config.ENABLE_INFOGRAFIA_EXPORT and pregunta_slides:
        info_slide_number = slide.get("slide_number")
        if info_slide_number is not None:
            pregunta_to_append = pregunta_slides.get(info_slide_number)

    if has_image and has_buttons:
        # SPLIT into two carousel slides
        # Slide A: Subtitle heading + body text + image
        slide_a = soup.new_tag(
            "div", attrs={"class": "carousel-item v-info-item-slide-1 v-info-bkg-sl1"}
        )
        wr = soup.new_tag("div", attrs={"class": "virtual-txt v-info-slide-1-wr"})

        col1 = soup.new_tag("div", attrs={"class": "v-info-slide-1-wr-izq"})
        h2 = soup.new_tag("h2")
        h2.string = heading
        col1.append(h2)
        col1.append(soup.new_tag("br"))
        _add_leer_mas(soup, col1, content_paragraphs, slide_idx)

        # Append pregunta if available
        if pregunta_to_append:
            col1.append(soup.new_tag("br"))
            h2_pregunta = soup.new_tag("h2")
            h2_pregunta.string = f"Pregunta {info_slide_count}"
            col1.append(h2_pregunta)
            _add_pregunta_content(soup, col1, pregunta_to_append, slide_idx)

        wr.append(col1)

        col2 = soup.new_tag("div", attrs={"class": "v-info-slide-1-wr-der"})
        img = soup.new_tag(
            "img",
            attrs={
                "class": "virtual-img-2 br-v-blue animate__animated animate__fadeInRight",
                "style": "animation-delay: 0.6s; width: 500px",
            },
        )
        img["src"] = get_image_url(slide["image"])
        col2.append(img)
        wr.append(col2)

        slide_a.append(wr)
        _add_controls(soup, slide_a)
        carousel_inner.append(slide_a)

        # Slide B: Buttons
        slide_b = soup.new_tag(
            "div", attrs={"class": "carousel-item v-info-item-slide-1 v-info-bkg-sl1"}
        )
        wr_b = soup.new_tag("div", attrs={"class": "virtual-txt v-info-slide-2-wr"})
        wr_b.append(soup.new_tag("br"))
        h2_b = soup.new_tag("h2")
        h2_b.string = heading + (
            " (Continuación)" if not Config.ENABLE_INFOGRAFIA_EXPORT else ""
        )
        wr_b.append(h2_b)
        wr_b.append(soup.new_tag("br"))
        _add_buttons(
            soup, wr_b, slide["buttons"], slide_idx
        )
        slide_b.append(wr_b)
        _add_controls(soup, slide_b)
        carousel_inner.append(slide_b)

    elif has_buttons:
        # Subtitle heading + body text + buttons (no image)
        slide_b = soup.new_tag(
            "div", attrs={"class": "carousel-item v-info-item-slide-1 v-info-bkg-sl1"}
        )
        wr_b = soup.new_tag("div", attrs={"class": "virtual-txt v-info-slide-2-wr"})
        wr_b.append(soup.new_tag("br"))
        h2_b = soup.new_tag("h2")
        h2_b.string = heading
        wr_b.append(h2_b)
        wr_b.append(soup.new_tag("br"))
        _add_leer_mas(soup, wr_b, content_paragraphs, slide_idx)

        # Append pregunta if available
        if pregunta_to_append:
            wr_b.append(soup.new_tag("br"))
            h2_pregunta = soup.new_tag("h2")
            h2_pregunta.string = f"Pregunta {info_slide_count}"
            wr_b.append(h2_pregunta)
            _add_pregunta_content(soup, wr_b, pregunta_to_append, slide_idx)

        _add_buttons(
            soup, wr_b, slide["buttons"], slide_idx
        )
        slide_b.append(wr_b)
        _add_controls(soup, slide_b)
        carousel_inner.append(slide_b)

    else:
        # Text + Image (or just text)
        slide_a = soup.new_tag(
            "div", attrs={"class": "carousel-item v-info-item-slide-1 v-info-bkg-sl1"}
        )
        wr = soup.new_tag("div", attrs={"class": "virtual-txt v-info-slide-1-wr"})

        col1 = soup.new_tag("div", attrs={"class": "v-info-slide-1-wr-izq"})
        h2 = soup.new_tag("h2")
        h2.string = heading
        col1.append(h2)
        col1.append(soup.new_tag("br"))
        _add_leer_mas(soup, col1, content_paragraphs, slide_idx)

        # Append pregunta if available
        if pregunta_to_append:
            col1.append(soup.new_tag("br"))
            h2_pregunta = soup.new_tag("h2")
            h2_pregunta.string = f"Pregunta {info_slide_count}"
            col1.append(h2_pregunta)
            _add_pregunta_content(soup, col1, pregunta_to_append, slide_idx)

        wr.append(col1)

        if has_image:
            col2 = soup.new_tag("div", attrs={"class": "v-info-slide-1-wr-der"})
            img = soup.new_tag(
                "img",
                attrs={
                    "class": "virtual-img-2 br-v-blue animate__animated animate__fadeInRight",
                    "style": "animation-delay: 0.6s; width: 500px",
                },
            )
            img["src"] = get_image_url(slide["image"])
            col2.append(img)
            wr.append(col2)

        slide_a.append(wr)
        _add_controls(soup, slide_a)
        carousel_inner.append(slide_a)


