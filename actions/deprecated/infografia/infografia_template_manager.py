import os
import re
import random
from bs4 import BeautifulSoup

USED_TEMPLATES = set()

def reset_used_templates():
    USED_TEMPLATES.clear()

def _export_strip_colon(text):
    if text:
        return text.rstrip(":").strip()
    return text

def select_random_template(num_btns):
    """
    Selects a random template based on the number of buttons.
    """
    folder_num = max(2, min(6, num_btns))
    template_dir = os.path.join("assets", "templates", "infografias", f"btns-{folder_num}")
    
    if not os.path.exists(template_dir):
        template_dir = os.path.join("assets", "templates", "infografias", "btns-2")

    templates = [f for f in os.listdir(template_dir) if f.endswith(".html")]
    if not templates:
        return os.path.join("assets", "templates", "infografias", "lightbox_cuadrados.html")
    
    available = [t for t in templates if t not in USED_TEMPLATES]
    if not available:
        USED_TEMPLATES.difference_update(templates)
        available = templates
        
    selected_template = random.choice(available)
    USED_TEMPLATES.add(selected_template)
    
    return os.path.join(template_dir, selected_template)

def inject_button_data(soup, wrapper_div, buttons, slide_idx):
    """
    Injects button titles and modal/tab content into the template.
    """
    if not buttons:
        return

    # Find all triggers (modals, tabs, or clickable divs)
    # Support button, a, and div tags with data-bs-toggle
    triggers = wrapper_div.find_all(
        lambda tag: tag.has_attr("data-bs-toggle")
    )

    # Find all targets (modals or tab-panes)
    targets = wrapper_div.find_all(
        lambda tag: tag.name == "div"
        and (
            "modal" in tag.get("class", [])
            or "tab-pane" in tag.get("class", [])
        )
    )

    for i, trigger in enumerate(triggers):
        if i < len(buttons):
            btn_obj = buttons[i]
            b_title = _export_strip_colon(btn_obj["title"])
            toggle_type = trigger.get("data-bs-toggle")

            # Update IDs to avoid conflict
            new_id = f"v-sl{slide_idx}-target-{i + 1}"
            trigger["data-bs-target"] = f"#{new_id}"

            # For Tabs/Pills, we also need aria-controls and id for the trigger
            if toggle_type in ["pill", "tab"]:
                trigger_id = f"v-sl{slide_idx}-trigger-{i + 1}"
                trigger["id"] = trigger_id
                trigger["aria-controls"] = new_id

            if i < len(targets):
                target = targets[i]
                target["id"] = new_id

                if toggle_type in ["pill", "tab"]:
                    target["aria-labelledby"] = f"v-sl{slide_idx}-trigger-{i + 1}"

                # ── Injection logic based on target type ──────────────────
                if "modal" in target.get("class", []):
                    # Modal pattern: h3.modal-title + .modal-body
                    if target.find("h3", class_="modal-title"):
                        target.find("h3", class_="modal-title").string = b_title
                    modal_body = target.find("div", class_="modal-body")
                    if modal_body:
                        modal_body.clear()
                        if btn_obj["content"]:
                            for p_text in btn_obj["content"]:
                                p_tag = soup.new_tag("p")
                                p_tag.string = p_text
                                modal_body.append(p_tag)
                        else:
                            p_tag = soup.new_tag("p")
                            p_tag.string = "Contenido del botón"
                            modal_body.append(p_tag)

                elif "tab-pane" in target.get("class", []):
                    # Tab pattern: h3 + p tags inside .virtual-txt (or direct)
                    vtxt = target.find("div", class_="virtual-txt") or target
                    h3 = vtxt.find("h3")
                    if h3:
                        h3.string = b_title
                    
                    # Clear existing content paragraphs
                    for p in vtxt.find_all("p"):
                        p.decompose()
                    
                    if btn_obj["content"]:
                        for p_text in btn_obj["content"]:
                            p_tag = soup.new_tag("p")
                            p_tag.string = p_text
                            vtxt.append(p_tag)
                    else:
                        p_tag = soup.new_tag("p")
                        p_tag.string = "Contenido del botón"
                        vtxt.append(p_tag)

            # ── Trigger label update ──────────────────────────────────
            replaced_text = False

            # 1. Look for explicit placeholder text inside the trigger itself
            # (e.g. nested div or span like "Título de ítem 1")
            for tag in trigger.find_all(True):
                if tag.string:
                    tag_text = tag.string.strip()
                    if any(x in tag_text for x in ["Título", "Nombre", "ítem"]):
                        tag.string = b_title
                        replaced_text = True
                        break

            # 2. Look for headings/paragraphs in the same container (parent)
            if not replaced_text:
                parent = trigger.parent
                heading = parent.find(["h4", "h3", "p"], recursive=False)
                
                # If the trigger is a div itself, look inside it just in case
                if not heading and trigger.name == "div":
                    heading = trigger.find(["h4", "h3", "p"])
    
                if heading:
                    h_text = heading.get_text(strip=True)
                    if any(x in h_text for x in ["Título", "Nombre", "ítem"]):
                        heading.string = b_title
                        replaced_text = True
                    elif not h_text or h_text == b_title:
                        heading.string = b_title
                        replaced_text = True
            
            # 3. Update trigger text itself ONLY if it's a simple button/link
            if not replaced_text and not trigger.find("i"):
                current_text = trigger.get_text(strip=True)
                if current_text and not current_text.isdigit():
                    trigger.string = b_title
                elif not current_text:
                    pass

        else:
            # Hide unused triggers and targets
            trigger.decompose()
            if i < len(targets):
                targets[i].decompose()

def apply_template_to_wrapper(soup, wrapper_div, buttons, slide_idx):
    """
    Selects a template, loads it, and injects data.
    """
    if not buttons:
        return

    template_path = select_random_template(len(buttons))
    with open(template_path, "r", encoding="utf-8") as f:
        template_html = f.read()

    template_soup = BeautifulSoup(template_html, "html.parser")
    wrapper_div.append(template_soup)
    
    inject_button_data(soup, wrapper_div, buttons, slide_idx)
