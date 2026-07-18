import re
from bs4 import BeautifulSoup


def split_paragraphs_by_limit(
    paragraphs, max_words=65, max_chars_nospace=525, max_chars_space=600
):
    """
    Splits a list of paragraph strings into (first_page, overflow) at a complete-paragraph
    boundary when adding the next paragraph would exceed ANY of the three thresholds:
      - max_words          : total word count across paragraphs on the slide
      - max_chars_nospace  : total character count excluding spaces
      - max_chars_space    : total character count including spaces

    At least one paragraph is always kept in first_page to avoid empty slides.
    Returns (first_page: list[str], overflow: list[str]).
    """
    if not paragraphs:
        return [], []

    first_page = []
    total_words = 0
    total_chars_nospace = 0
    total_chars_space = 0

    for i, para in enumerate(paragraphs):
        words = len(para.split())
        chars_nospace = len(para.replace(" ", ""))
        chars_space = len(para)

        # Always include the first paragraph regardless of length
        if i == 0:
            first_page.append(para)
            total_words += words
            total_chars_nospace += chars_nospace
            total_chars_space += chars_space
            continue

        # If adding this paragraph would breach any limit, stop here
        if (
            total_words + words > max_words
            or total_chars_nospace + chars_nospace > max_chars_nospace
            or total_chars_space + chars_space > max_chars_space
        ):
            return first_page, paragraphs[i:]

        first_page.append(para)
        total_words += words
        total_chars_nospace += chars_nospace
        total_chars_space += chars_space

    return first_page, []


def _build_biblio_slide(soup, refs, heading, base_url, is_last=True):
    """
    Builds a single Bibliografía carousel item.
    - refs    : list of plain-text reference strings (URLs will be auto-linked).
    - heading : displayed h2 title (e.g. 'Bibliografía' or 'Bibliografía (cont.)').
    - base_url: Parameter kept for compatibility (bibliography image uses fixed URL).
    - is_last : when False a Next button is added so the user can continue to the
                following overflow slide; when True only Prev/Home are shown.
    """
    ref_slide = soup.new_tag(
        "div", attrs={"class": "carousel-item v-info-item-biblio v-info-bkg-biblio"}
    )
    wr = soup.new_tag("div", attrs={"class": "virtual-txt v-info-slide-1-wr"})

    # Left column — heading + reference paragraphs
    col1 = soup.new_tag("div", attrs={"class": "v-info-slide-1-wr-izq"})
    h2 = soup.new_tag("h2")
    h2.string = heading
    col1.append(h2)
    col1.append(soup.new_tag("br"))

    for ref in refs:
        ref_with_links = re.sub(
            r"(https?://[^\s]+)",
            r'<a href="\1" target="_blank" style="display: none;"></a>',
            ref,
        )
        p = BeautifulSoup(f"<p>{ref_with_links}</p>", "html.parser").p
        col1.append(p)
    wr.append(col1)

    # Right column — decorative image (same on all Bibliografía slides)
    col2 = soup.new_tag("div", attrs={"class": "v-info-slide-1-wr-der"})
    img = soup.new_tag(
        "img",
        attrs={
            "class": "animate__animated animate__fadeInRight",
            "style": "animation-delay: 0.6s;",
        },
    )
    # Use the original bibliography image URL (not modified for ENABLE_INFOGRAFIA_EXPORT)
    img["src"] = (
        "https://contenidomoodle.s3.amazonaws.com/UNIMINUTO_VIRTUAL/estilos/img/infografia/virtual_info_5.png"
    )
    col2.append(img)
    wr.append(col2)

    ref_slide.append(wr)

    # Home button
    btn_home = soup.new_tag(
        "button",
        attrs={
            "type": "button",
            "data-bs-target": "#virtual-infografia",
            "data-bs-slide-to": "0",
            "class": "virtual-btn-info-home",
            "aria-label": "Home",
        },
    )
    btn_home.append(
        soup.new_tag("i", attrs={"class": "fa fa-home", "aria-hidden": "true"})
    )
    ref_slide.append(btn_home)

    # Prev button
    btn_prev = soup.new_tag(
        "button",
        attrs={
            "class": "carousel-control-prev virtual-info-control-prev",
            "type": "button",
            "data-bs-target": "#virtual-infografia",
            "data-bs-slide": "prev",
        },
    )
    btn_prev.append(
        soup.new_tag(
            "span",
            attrs={
                "class": "carousel-control-prev-icon virtual-info-control-prev-icon"
            },
        )
    )
    ref_slide.append(btn_prev)

    # Next button — only on non-final overflow slides
    if not is_last:
        btn_next = soup.new_tag(
            "button",
            attrs={
                "class": "carousel-control-next virtual-info-control-next",
                "type": "button",
                "data-bs-target": "#virtual-infografia",
                "data-bs-slide": "next",
            },
        )
        btn_next.append(
            soup.new_tag(
                "span",
                attrs={
                    "class": "carousel-control-next-icon virtual-info-control-next-icon bg-v-blue"
                },
            )
        )
        ref_slide.append(btn_next)

    return ref_slide
