from bs4 import BeautifulSoup
from actions.infografia.infografia_template_manager import apply_template_to_wrapper


def _add_controls(soup, slide_div):
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
    i_home = soup.new_tag("i", attrs={"class": "fa fa-home", "aria-hidden": "true"})
    btn_home.append(i_home)
    slide_div.append(btn_home)

    btn_prev = soup.new_tag(
        "button",
        attrs={
            "class": "carousel-control-prev virtual-info-control-prev",
            "type": "button",
            "data-bs-target": "#virtual-infografia",
            "data-bs-slide": "prev",
        },
    )
    span_prev = soup.new_tag(
        "span",
        attrs={
            "class": "carousel-control-prev-icon virtual-info-control-prev-icon bg-v-blue"
        },
    )
    btn_prev.append(span_prev)
    slide_div.append(btn_prev)

    btn_next = soup.new_tag(
        "button",
        attrs={
            "class": "carousel-control-next virtual-info-control-next",
            "type": "button",
            "data-bs-target": "#virtual-infografia",
            "data-bs-slide": "next",
        },
    )
    span_next = soup.new_tag(
        "span",
        attrs={
            "class": "carousel-control-next-icon virtual-info-control-next-icon bg-v-blue"
        },
    )
    btn_next.append(span_next)
    slide_div.append(btn_next)


def _add_buttons(soup, wrapper_div, buttons, slide_idx):
    apply_template_to_wrapper(soup, wrapper_div, buttons, slide_idx)
