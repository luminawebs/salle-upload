"""
actividad_actions.py
--------------------
Parses local Plantilla_Taller_SX.html files (S2, S4, S6, S8) and:
  1. Fills the actividad.html template with the extracted data.
  2. Saves the result to assets/<course_id>/actividades/SX_actividad.html
  3. Uploads the generated HTML to the corresponding Moodle activity
     named "SX | Actividad".

Sections in the template are included only when found in the raw source.
Sections not present (Juzgar, Actuar, Devolución) are removed from output.
"""

import copy
import logging
import os
import re
import time

from bs4 import BeautifulSoup, NavigableString
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

from config.settings import Config
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from html_generator.generate_html import wrap_bibliographic_title_in_bold
from core.wysiwyg_handler import inject_html_into_wysiwyg

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Weeks configuration
# ---------------------------------------------------------------------------
ACTIVIDAD_WEEKS = ["S2", "S4", "S6", "S8"]


# ---------------------------------------------------------------------------
# HTML cleaning helpers
# ---------------------------------------------------------------------------


def _decode_html_entities(text: str) -> str:
    """Replace common HTML entities with their UTF-8 equivalents."""
    entities = {
        "&aacute;": "á",
        "&eacute;": "é",
        "&iacute;": "í",
        "&oacute;": "ó",
        "&uacute;": "ú",
        "&ntilde;": "ñ",
        "&Aacute;": "Á",
        "&Eacute;": "É",
        "&Iacute;": "Í",
        "&Oacute;": "Ó",
        "&Uacute;": "Ú",
        "&Ntilde;": "Ñ",
        "&uuml;": "ü",
        "&Uuml;": "Ü",
        "&amp;": "&",
        "&lt;": "<",
        "&gt;": ">",
        "&quot;": '"',
        "&nbsp;": " ",
        "&ordm;": "º",
        "&ordf;": "ª",
        "&ndash;": "–",
        "&mdash;": "—",
        "&ldquo;": "\u201c",
        "&rdquo;": "\u201d",
        "&lsquo;": "\u2018",
        "&rsquo;": "\u2019",
        "&#279;": "ę",
    }
    for entity, char in entities.items():
        text = text.replace(entity, char)
    return text


def _read_raw_html(filepath: str) -> str:
    """Read raw Plantilla file, trying windows-1252 then utf-8."""
    for encoding in ("windows-1252", "utf-8", "latin-1"):
        try:
            with open(filepath, "r", encoding=encoding) as f:
                return f.read()
        except (UnicodeDecodeError, LookupError):
            continue
    with open(filepath, "rb") as f:
        return f.read().decode("utf-8", errors="replace")


def _fix_list_nesting(soup: BeautifulSoup):
    """
    Fixes improperly nested <li> tags caused by unclosed tags in the source HTML.
    Moves <li> tags that are incorrectly children of other <li> tags to become siblings.
    """
    while True:
        lis = soup.find_all("li")
        moved = False
        for li in lis:
            if li.parent and li.parent.name not in ["ul", "ol"]:
                closest_li = li.find_parent("li")
                if closest_li:
                    closest_li.insert_after(li)
                    moved = True
                    break
        if not moved:
            break


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


def _remove_section_header(html_str: str) -> str:
    if not html_str:
        return html_str
    soup = BeautifulSoup(html_str, "html.parser")
    header_pattern = re.compile(
        r"(?i)^\s*(Descripci[oó]n|Juzgar|Ver|Actuar|Devoluci[oó]n(?:\s*creativa-metacognici[oó]n)?|Recurso\(?s?\)?\s*b[aá]sico\(?s?\)?|Recurso\(?s?\)?\s*complementario\(?s?\)?|Indicaciones\s+del\s+desarrollo|Forma\s+de\s+entrega(?:\s*\(.*?\))?)\s*:?\s*$"
    )

    single_words = {
        "descripción",
        "descripcion",
        "juzgar",
        "ver",
        "actuar",
        "devolución",
        "creativa-metacognición",
        "devolución creativa-metacognición",
        "recurso(s)",
        "básico(s)",
        "complementario(s)",
        "recursos",
        "básicos",
        "complementarios",
        "recurso(s) básico(s)",
        "recurso(s) complementario(s)",
        "recursos básicos",
        "recursos complementarios",
        "indicaciones",
        "del",
        "desarrollo",
        "indicaciones del desarrollo",
        "forma",
        "de",
        "entrega",
        "forma de entrega",
        "sólo",
        "editar",
        "ser",
        "necesario",
        ":",
    }

    from bs4 import NavigableString, Comment, Doctype
    for text_node in soup.find_all(string=True):
        if isinstance(text_node, (Comment, Doctype)):
            continue
        if not isinstance(text_node, NavigableString):
            continue
        val = text_node.strip().lower()
        if not val:
            continue

        if header_pattern.match(val) or val in single_words:
            text_node.replace_with("")
        else:
            new_val = re.sub(
                r"(?i)^\s*(Descripci[oó]n|Juzgar|Ver|Actuar|Devoluci[oó]n(?:\s*creativa-metacognici[oó]n)?|Recurso\(?s?\)?\s*b[aá]sico\(?s?\)?|Recurso\(?s?\)?\s*complementario\(?s?\)?|Indicaciones\s+del\s+desarrollo|Forma\s+de\s+entrega(?:\s*\(.*?\))?)\s*:\s*",
                "",
                text_node,
            )
            if new_val != text_node:
                text_node.replace_with(new_val)
            break

    for tag in soup.find_all(["strong", "b", "span", "font"]):
        if not tag.get_text(strip=True) and not tag.find("img"):
            tag.decompose()

    return str(soup)


def parse_actividad_data(raw_html: str) -> dict:
    """
    Parse a Plantilla_Taller_SX.html file and return a dict with the
    extracted fields needed to fill the actividad.html template.

    All fields default to None (meaning: skip / remove that section).
    """
    data = {
        "nombre_actividad": None,
        "descripcion": None,
        # "indicaciones_del_desarrollo" — kept only if the heading is present
        "indicaciones_html": None,
        "juzgar_html": None,
        "actuar_html": None,
        "devolucion_html": None,
        "tipo_actividad": None,
        "desarrollo_actividad": None,
        "consulta_materiales": None,
        "recursos_basicos_html": None,
        "recursos_complementarios_html": None,
        "rol_profesor": None,
    }

    if not raw_html:
        return data

    soup = BeautifulSoup(raw_html, "html.parser")
    full_text = soup.get_text(separator=" ")
    norm = re.sub(r"\s+", " ", full_text).strip()

    # ── 1. Nombre actividad ──────────────────────────────────────────────────
    # Pattern: "Taller. <Title>" before "Descripción:" or just start to "Descripción:"
    m = re.search(r"Taller\.\s*(.+?)\s+Descripci[oó]n\s*:", norm, re.IGNORECASE)
    if m:
        data["nombre_actividad"] = re.sub(r" {2,}", " ", _decode_html_entities(m.group(1).strip()))
        logger.info(f"  → nombre_actividad: {data['nombre_actividad']}")
    else:
        m = re.match(r"^\s*(.+?)\s+Descripci[oó]n\s*:", norm, re.IGNORECASE)
        if m:
            data["nombre_actividad"] = re.sub(r" {2,}", " ", _decode_html_entities(m.group(1).strip()))
            logger.info(f"  → nombre_actividad: {data['nombre_actividad']}")

    # ── 2. Descripción ───────────────────────────────────────────────────────
    data["descripcion_html"] = _extract_section_between_headings(
        soup,
        r"Descripci[oó]n\s*:",
        [r"Ver\s*:", r"Indicaciones\s+del\s+desarrollo"],
        keep_lists=True,
    )
    if data.get("descripcion_html"):
        data["descripcion_html"] = _remove_section_header(data["descripcion_html"])
        logger.info("  → descripcion_html extracted successfully")

    # ── 3. Indicaciones / Ver / Juzgar / Actuar / Devolución ─────────────────
    data["indicaciones_html"] = _extract_section_between_headings(
        soup,
        r"(?:Ver\s*:|Indicaciones\s+del\s+desarrollo)",
        [r"Juzgar\s*:", r"Actuar\s*:", r"Devoluci[oó]n", r"Tiempos\s+y\s+recursos"],
        keep_lists=True,
        keep_tables=True,
    )
    if not data["indicaciones_html"]:
        data["indicaciones_html"] = _extract_indicaciones_html(soup)

    data["juzgar_html"] = _extract_section_between_headings(
        soup,
        r"Juzgar\s*:",
        [r"Actuar\s*:", r"Devoluci[oó]n", r"Tiempos\s+y\s+recursos"],
    )

    data["actuar_html"] = _extract_section_between_headings(
        soup,
        r"Actuar\s*:",
        [r"Devoluci[oó]n", r"Tiempos\s+y\s+recursos"],
        keep_lists=True,
    )

    data["devolucion_html"] = _extract_section_between_headings(
        soup, r"Devoluci[oó]n", [r"Tiempos\s+y\s+recursos", r"Recurso\(?s?\)?"]
    )

    # ── 4. Tiempos ───────────────────────────────────────────────────────────
    m = re.search(
        r"Tipo\s+de\s+actividad\s+([A-ZÁÉÍÓÚa-záéíóúüñÑ][^\n]{1,40}?)"
        r"(?:\s{2,}|\s+Tiempos|\s+Recursos)",
        norm,
        re.IGNORECASE,
    )
    if m:
        data["tipo_actividad"] = re.sub(r" {2,}", " ", _decode_html_entities(m.group(1).strip()))

    m = re.search(
        r"Desarrollo\s+de\s+la\s+actividad\s*:\s*(\d+)[º°]?\s*(horas?)",
        norm,
        re.IGNORECASE,
    )
    if m:
        data["desarrollo_actividad"] = f"{m.group(1)} {m.group(2)}"

    m = re.search(
        r"Consulta\s+de\s+materiales\s*:\s*(\d+)[º°]?\s*(horas?)", norm, re.IGNORECASE
    )
    if m:
        data["consulta_materiales"] = f"{m.group(1)} {m.group(2)}"

    # ── 5. Recursos básicos / complementarios (HTML) ─────────────────────────
    data["recursos_basicos_html"] = _extract_section_between_headings(
        soup,
        r"Recurso\(?s?\)?\s*b[aá]sico\(?s?\)?\s*:",
        [
            r"Recurso\(?s?\)?\s*complementario\(?s?\)?\s*:",
            r"Rol\s+del\s+(?:profesor|tutor)\s*:",
            r"^\s*R[uú]brica",
        ],
    )

    data["recursos_complementarios_html"] = _extract_section_between_headings(
        soup,
        r"Recurso\(?s?\)?\s*complementario\(?s?\)?\s*:",
        [r"Rol\s+del\s+(?:profesor|tutor)\s*:", r"Forma\s+de\s+entrega", r"^\s*R[uú]brica"],
    )

    data["forma_entrega_html"] = _extract_section_between_headings(
        soup, r"Forma\s+de\s+entrega", [r"^\s*R[uú]brica"], keep_lists=True
    )

    # ── 6. Rol del profesor ──────────────────────────────────────────────────
    # Match "Rol del profesor: <text>" up to "Forma de entrega"
    m = re.search(
        r"Rol\s+del\s+(?:profesor|tutor)\s*:\s*(?:Rol\s+del\s+(?:profesor|tutor)\s*:)?\s*(.+?)"
        r"\s*(?:Forma\s+de\s+entrega|R[uú]brica\s*(?::|\.\s+(?:An[aá]lisis|Trabajo|Foro|Taller)|\s+(?:An[aá]lisis|Trabajo|Foro|Taller)))",
        norm,
        re.IGNORECASE,
    )
    if m:
        data["rol_profesor"] = re.sub(r" {2,}", " ", _decode_html_entities(m.group(1).strip()))

    for key in [
        "indicaciones_html",
        "juzgar_html",
        "actuar_html",
        "devolucion_html",
        "recursos_basicos_html",
        "recursos_complementarios_html",
        "forma_entrega_html",
    ]:
        if data.get(key):
            data[key] = _remove_section_header(data[key])
            if key in ["recursos_basicos_html", "recursos_complementarios_html"]:
                data[key] = wrap_bibliographic_title_in_bold(data[key])

    return data


# ---------------------------------------------------------------------------
# BeautifulSoup extraction helpers
# ---------------------------------------------------------------------------


def _extract_indicaciones_html(soup: BeautifulSoup):
    """
    Extract the HTML block for 'Indicaciones del desarrollo' maintaining
    list structure (ul/ol/li). Returns None if the heading is not found.
    """
    text_node = soup.find(
        string=re.compile(r"Indicaciones\s+del\s+desarrollo", re.IGNORECASE)
    )
    if not text_node:
        logger.info(
            "  → 'Indicaciones del desarrollo' heading NOT found — section will be removed."
        )
        return None

    title_tag = text_node.parent
    while title_tag and title_tag.name not in ["p", "div", "h1", "h2", "h3", "h4"]:
        title_tag = title_tag.parent
    if not title_tag:
        return None

    fragments = []
    for sibling in title_tag.next_siblings:
        if isinstance(sibling, NavigableString):
            if sibling.strip():
                fragments.append(str(sibling))
            continue

        text = sibling.get_text(" ", strip=True).lower()
        # Stop at the next major section
        if re.search(
            r"(tiempos\s+y\s+recursos|rol\s+del\s+(?:profesor|tutor)|r[uú]brica)",
            text,
            re.IGNORECASE,
        ):
            break

        fragments.append(str(sibling))

    extracted = "".join(fragments).strip()
    if not extracted:
        return None

    # Clean: remove <p> inside <li> and clean list attributes
    ind_soup = BeautifulSoup(extracted, "html.parser")
    _fix_list_nesting(ind_soup)
    for tag in ind_soup.find_all(["ul", "ol", "li"]):
        tag.attrs = {k: v for k, v in tag.attrs.items() if k in ["start", "type"]}
    for li in ind_soup.find_all("li"):
        for p in li.find_all("p"):
            p.unwrap()

    # Unwrap <font> and <span> tags for cleaner HTML
    for tag in ind_soup.find_all(["font", "span"]):
        tag.unwrap()

    # Remove empty lists/list items
    for tag in ind_soup.find_all(["li", "ul", "ol"]):
        if not tag.get_text(strip=True) and not tag.find("img"):
            tag.decompose()

    # Clean tables if any
    for table in ind_soup.find_all("table"):
        table.attrs = {"class": ["virtual-tables"]}
        for col in table.find_all(["col", "colgroup"]):
            col.decompose()
        for t_tag in table.find_all(["tr", "td", "th", "tbody", "thead"]):
            t_tag.attrs = {}
        for p in table.find_all("p"):
            p.attrs = {}

    return str(ind_soup)


def _extract_section_between_headings(
    soup: BeautifulSoup,
    start_re: str,
    stop_res: list,
    keep_lists: bool = False,
    keep_tables: bool = False,
):
    """
    Extract HTML between the element matching start_re and the first
    element matching any of stop_res (exclusive). Returns None if not found.
    Operates at the paragraph / list level; skips table ancestors.
    """
    # Walk ALL paragraphs, lists and headings in document order
    all_nodes = []
    root = soup.body if soup.body else soup
    for el in root.descendants:
        if getattr(el, "name", None) in [
            "p",
            "ul",
            "ol",
            "li",
            "table",
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
        ]:
            all_nodes.append(el)

    start_idx = None
    for i, node in enumerate(all_nodes):
        if re.search(start_re, node.get_text(" ", strip=True), re.IGNORECASE):
            start_idx = i
            break

    if start_idx is None:
        return None

    fragments = []
    added_nodes = set()
    for i, node in enumerate(all_nodes[start_idx:]):
        text = node.get_text(" ", strip=True)
        if i > 0 and any(re.search(sr, text, re.IGNORECASE) for sr in stop_res):
            break

        # Is this node a descendant of an already added node?
        is_descendant = False
        parent = node.parent
        while parent:
            if parent in added_nodes:
                is_descendant = True
                break
            parent = parent.parent

        allowed_tags = ["li", "p", "ul", "ol"]
        if keep_tables:
            allowed_tags.append("table")

        if not is_descendant and node.name in allowed_tags:
            fragments.append(str(node))
            added_nodes.add(node)

    result = "".join(fragments).strip()
    return _sanitize_resource_html(result, keep_lists, keep_tables) if result else None


def _sanitize_resource_html(
    html_text: str, keep_lists: bool = False, keep_tables: bool = False
) -> str:
    """Strip noisy heading-like paragraphs from resource HTML."""
    if not html_text:
        return html_text

    soup = BeautifulSoup(html_text, "html.parser")
    _fix_list_nesting(soup)

    noise_re = re.compile(
        r"^(tipo\s+de\s+actividad.*|tiempos|desarrollo\s+de\s+la\s+actividad.*|"
        r"consulta\s+de\s+materiales.*|recurso\(?s?\)?\s*b[aá]sico\(?s?\)?\s*:?|recurso\(?s?\)?\s*complementario\(?s?\)?\s*:?|"
        r"individual|colaborativa|individual/grupal|recursos?)$",
        re.IGNORECASE,
    )
    seen = set()
    for tag in soup.find_all(["p", "li", "div"]):
        # Do not process nested paragraphs/lists (they share text with their parents)
        if tag.find_parent(["p", "li", "div"]):
            continue

        text = " ".join(tag.get_text(" ", strip=True).split())
        if not text:
            tag.decompose()
            continue
        if noise_re.match(text):
            tag.decompose()
            continue
        key = text.lower()
        if key in seen:
            tag.decompose()
            continue
        seen.add(key)

    # Remove <font> / <span> wrapper noise but keep links and <b>/<i>
    # Also unwrap <ul> / <ol> / <li> tags so items are not inside lists if keep_lists is False
    unwrap_tags = ["font", "span"]
    if not keep_lists:
        unwrap_tags.extend(["ul", "ol", "li"])
    else:
        for tag in soup.find_all(["ul", "ol", "li"]):
            tag.attrs = {k: v for k, v in tag.attrs.items() if k in ["start", "type"]}
        for li in soup.find_all("li"):
            for p in li.find_all("p"):
                p.unwrap()

    for tag in soup.find_all(unwrap_tags):
        tag.unwrap()

    if keep_tables:
        for table in soup.find_all("table"):
            table.attrs = {"class": ["virtual-tables"]}
            for col in table.find_all(["col", "colgroup"]):
                col.decompose()
            for t_tag in table.find_all(["tr", "td", "th", "tbody", "thead"]):
                t_tag.attrs = {}
            for p in table.find_all("p"):
                p.attrs = {}

    # Collapse multiple/double spaces inside every text node so that
    # Moodle "Recursos de apoyo" exact-string matching works correctly.
    for text_node in soup.find_all(string=True):
        if isinstance(text_node, NavigableString):
            cleaned = re.sub(r" {2,}", " ", text_node)
            if cleaned != text_node:
                text_node.replace_with(cleaned)

    return str(soup).strip() or None


# ---------------------------------------------------------------------------
# HTML file generation
# ---------------------------------------------------------------------------


def generate_actividad_html_file(
    parsed_data: dict,
    template_path: str,
    output_path: str,
) -> None:
    """
    Reads actividad.html template, replaces placeholder content with
    parsed data, removes sections that have no data, and writes the result.
    """
    with open(template_path, "r", encoding="utf-8") as f:
        template_html = f.read()

    soup = BeautifulSoup(template_html, "html.parser")

    # Helper: find <h3> by partial text (whitespace-normalized)
    def find_h3(text_fragment):
        return soup.find(
            lambda tag: (
                tag.name == "h3" and text_fragment in " ".join(tag.get_text().split())
            )
        )

    # Helper: remove section (h3 + following siblings up to next h3/table/end)
    def remove_section(header_tag):
        if not header_tag:
            return
        to_remove = []
        sib = header_tag.next_sibling
        while sib:
            nxt = sib.next_sibling
            if getattr(sib, "name", None) in ["h3", "h4"]:
                break
            to_remove.append(sib)
            sib = nxt
        for el in to_remove:
            el.extract()
        header_tag.extract()

    # Helper: replace paragraph content after a header
    def replace_paragraph_after(header_tag, new_text):
        if not header_tag or not new_text:
            return
        sib = header_tag.find_next_sibling()
        while sib and sib.name not in ["h3", "h4", "table"]:
            nxt = sib.find_next_sibling()
            sib.extract()
            sib = nxt
        new_p = soup.new_tag("p")
        new_p.string = new_text
        header_tag.insert_after(new_p)

    # Helper: inject raw HTML after a header (replaces existing siblings up to next h3/h4/table/br)
    def replace_html_after(header_tag, html_string):
        if not header_tag or not html_string:
            return
        sib = header_tag.find_next_sibling()
        while sib and getattr(sib, "name", None) not in ["h3", "h4", "table"]:
            nxt = sib.find_next_sibling()
            sib.extract()
            sib = nxt
        frag = BeautifulSoup(html_string, "html.parser")
        insert_after = header_tag
        for node in list(frag.contents):
            if isinstance(node, NavigableString) and not node.strip():
                continue
            clone = copy.deepcopy(node)
            insert_after.insert_after(clone)
            insert_after = clone

    # ── Header (virtual-header h3) ───────────────────────────────────────────
    header_h3 = soup.find("div", class_="virtual-header")
    if header_h3:
        h3 = header_h3.find("h3")
        if h3 and parsed_data.get("nombre_actividad"):
            nombre = parsed_data["nombre_actividad"]
            if "." in nombre:
                parts = nombre.split(".", 1)
                new_html = f"<i>{parts[0]}.</i>{parts[1]}"
                h3.clear()
                h3.append(BeautifulSoup(new_html, "html.parser"))
            else:
                h3.string = nombre

    # ── Descripción ──────────────────────────────────────────────────────────
    desc_h3 = find_h3("Descripción")
    if parsed_data.get("descripcion_html"):
        replace_html_after(desc_h3, parsed_data["descripcion_html"])
    elif parsed_data.get("descripcion"):
        replace_paragraph_after(desc_h3, parsed_data["descripcion"])
    else:
        remove_section(desc_h3)

    # ── Ver (Indicaciones del desarrollo) ────────────────────────────────────
    # In taller template it's "Ver", in trabajo template it's "Indicaciones..."
    ver_h3 = find_h3("Ver") or find_h3("Indicaciones")
    if parsed_data.get("indicaciones_html"):
        replace_html_after(ver_h3, parsed_data["indicaciones_html"])
    else:
        remove_section(ver_h3)

    # ── Juzgar ───────────────────────────────────────────────────────────────
    juzgar_h3 = find_h3("Juzgar")
    if parsed_data.get("juzgar_html"):
        replace_html_after(juzgar_h3, parsed_data["juzgar_html"])
    else:
        remove_section(juzgar_h3)

    # ── Actuar ───────────────────────────────────────────────────────────────
    actuar_h3 = find_h3("Actuar")
    if parsed_data.get("actuar_html"):
        replace_html_after(actuar_h3, parsed_data["actuar_html"])
    else:
        remove_section(actuar_h3)

    # ── Devolución metacognición ─────────────────────────────────────────────
    devolucion_h3 = find_h3("Devolución")
    if parsed_data.get("devolucion_html"):
        replace_html_after(devolucion_h3, parsed_data["devolucion_html"])
    else:
        remove_section(devolucion_h3)

    # ── Tiempos y recursos table ─────────────────────────────────────────────
    def set_td_text(search_text, label, value):
        td = soup.find(lambda t: t.name == "td" and search_text in t.get_text())
        if td and value:
            p = td.find("p") or td
            p.clear()
            strong = soup.new_tag("b")
            strong.string = label
            p.append(strong)
            p.append(value)

    if parsed_data.get("tipo_actividad"):
        set_td_text("Individual", "Tipo de actividad: ", parsed_data["tipo_actividad"])
        # Also try the Colaborativa variant
        set_td_text(
            "Colaborativa", "Tipo de actividad: ", parsed_data["tipo_actividad"]
        )
        # Generic fallback
        set_td_text(
            "Individual/Grupal", "Tipo de actividad: ", parsed_data["tipo_actividad"]
        )

    if parsed_data.get("desarrollo_actividad"):
        set_td_text(
            "Desarrollo de la actividad:",
            "Desarrollo de la actividad: ",
            parsed_data["desarrollo_actividad"],
        )

    if parsed_data.get("consulta_materiales"):
        set_td_text(
            "Consulta de materiales:",
            "Consulta de materiales: ",
            parsed_data["consulta_materiales"],
        )

    # ── Recursos básicos ─────────────────────────────────────────────────────
    rb_h4 = soup.find(lambda t: t.name == "h4" and "Recursos básicos" in t.get_text())
    if parsed_data.get("recursos_basicos_html"):
        replace_html_after(rb_h4, parsed_data["recursos_basicos_html"])
    else:
        remove_section(rb_h4)

    # ── Recursos complementarios ─────────────────────────────────────────────
    rc_h4 = soup.find(
        lambda t: t.name == "h4" and "Recursos complementarios" in t.get_text()
    )
    if parsed_data.get("recursos_complementarios_html"):
        replace_html_after(rc_h4, parsed_data["recursos_complementarios_html"])
    else:
        remove_section(rc_h4)

    # ── Rol del tutor ────────────────────────────────────────────────────────
    rol_h3 = find_h3("Rol del tutor")
    if parsed_data.get("rol_profesor"):
        replace_paragraph_after(rol_h3, parsed_data["rol_profesor"])
    else:
        remove_section(rol_h3)

    # ── Forma de entrega ─────────────────────────────────────────────────────
    forma_entrega_h3 = find_h3("Forma de entrega")
    if forma_entrega_h3 and parsed_data.get("forma_entrega_html"):
        replace_html_after(forma_entrega_h3, parsed_data["forma_entrega_html"])

    # ── Strip all URLs from the output ───────────────────────────────────────
    for a_tag in soup.find_all("a"):
        a_tag.unwrap()

    # Strip all <u> tags
    for u_tag in soup.find_all("u"):
        u_tag.unwrap()

    # ── Apply WHITESPACE NORMALIZATION ───────────────────────────────────────
    from bs4 import Comment, Doctype
    for text_node in soup.find_all(string=True):
        if isinstance(text_node, (Comment, Doctype)):
            continue
        if isinstance(text_node, NavigableString):
            text = str(text_node)
            
            # 1. Remove all tab characters (\t).
            # 2. Remove all carriage returns (\r).
            # 5. Convert non-breaking spaces (&nbsp;, \xa0) into regular spaces.
            text = text.replace('\t', ' ').replace('\r', '').replace('\xa0', ' ').replace('&nbsp;', ' ')
            
            # 3. Replace multiple consecutive spaces with a single space.
            # 4. Replace multiple line breaks with a single line break unless paragraph separation is semantically required.
            text = re.sub(r'\s+', ' ', text)
            
            # Strip URLs as before
            text = re.sub(
                r'(?i)(?:recuperado\s+de|consultado\s+en|disponible\s+en)?\s*https?://[^\s<>"]+|www\.[^\s<>"]+',
                "",
                text,
            )
            text = text.replace("()", "").replace("( )", "").replace(" .", ".")
            
            # 6. Trim leading and trailing whitespace from every text node.
            # 7. Remove indentation inherited from source HTML.
            if text.strip() == "":
                text = ""
            else:
                text = text.strip()

            if text != str(text_node):
                text_node.replace_with(text)

    # ── Write output ─────────────────────────────────────────────────────────
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    final_html = soup.prettify(formatter="minimal")
    
    # Wrap 'evaluación' in <span class="nolink">, avoiding double wrapping or modifying tag attributes
    final_html = re.sub(r'(?i)<span class="nolink">\s*(evaluaci[oó]n)\s*</span>', r'\1', final_html)
    final_html = re.sub(r'(?i)\b(evaluaci[oó]n)\b(?![^<]*>)', r'<span class="nolink">\1</span>', final_html)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(final_html)

    logger.info(f"  → Output saved: {output_path}")


# ---------------------------------------------------------------------------
# Selenium uploader
# ---------------------------------------------------------------------------


def _get_edit_url_global(driver, activity_name: str) -> str:
    """
    Finds the first activity matching `activity_name` on the course page
    and returns its edit URL.
    """
    try:
        activity_links = driver.find_elements(
            By.CSS_SELECTOR, "a.aalink, a.instancename"
        )
        for link in activity_links:
            text = link.text or link.get_attribute("textContent") or ""
            if activity_name.lower() in text.lower():
                href = link.get_attribute("href")
                if href:
                    m = re.search(r"id=(\d+)", href)
                    if m:
                        return f"{Config.MOODLE_URL}/course/modedit.php?update={m.group(1)}&return=1"
    except Exception as e:
        logger.error(f"  Error finding activity '{activity_name}': {e}")
    return None


def _get_edit_url_in_section(driver, week_name: str, resource_name: str) -> str:
    """
    Finds a resource matching `resource_name` inside `week_name` section
    and returns its edit URL.
    """
    try:
        section_xpath = f"//li[contains(@class, 'section')][descendant::*[contains(@class, 'sectionname') or self::h3 or self::h4][contains(translate(., 'SEMANA', 'semana'), '{week_name.lower()}')]]"
        section_li = driver.find_element(By.XPATH, section_xpath)

        activity_xpath = f".//li[contains(@class, 'activity')]//*[contains(@class, 'instancename') and contains(text(), '{resource_name}')]"
        activity_title = section_li.find_element(By.XPATH, activity_xpath)

        a_link = activity_title.find_element(By.XPATH, "./ancestor-or-self::a[@href]")
        href = a_link.get_attribute("href")
        m = re.search(r"id=(\d+)", href)
        if m:
            return (
                f"{Config.MOODLE_URL}/course/modedit.php?update={m.group(1)}&return=1"
            )
    except Exception as e:
        pass
    return None


def _extract_html_from_editor(driver, wait_time: int) -> str:
    """
    Extracts HTML from the Moodle editor on the current page.
    """
    wait = WebDriverWait(driver, wait_time)
    html_content = ""
    try:
        try:
            source_btn = WebDriverWait(driver, 3).until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, "button[data-handler='html']")
                )
            )
            source_btn.click()
            time.sleep(0.5)
        except:
            pass

        try:
            textarea = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "textarea[name='page[text]']")
                )
            )
            html_content = driver.execute_script("return arguments[0].value;", textarea)
        except TimeoutException:
            textarea = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "textarea[name='introeditor[text]']")
                )
            )
            html_content = driver.execute_script("return arguments[0].value;", textarea)

        if not html_content:
            div = driver.find_element(By.CSS_SELECTOR, "div.editor_atto_content")
            html_content = driver.execute_script("return arguments[0].innerHTML;", div)
    except Exception as e:
        logger.error(f"  Failed to extract HTML: {e}")
    return html_content


# The local _upload_html_to_editor was removed and replaced by core.wysiwyg_handler.inject_html_into_wysiwyg


# ---------------------------------------------------------------------------
# Main workflow
# ---------------------------------------------------------------------------


from selenium.webdriver.support.ui import Select

def _configure_actividad_availability(driver):
    """Configures the Availability section in the Moodle activity form."""
    try:
        # Expand Availability section if needed
        availability_header = driver.find_elements(By.CSS_SELECTOR, "fieldset#id_availability a[data-toggle='collapse']")
        if availability_header:
            is_expanded = availability_header[0].get_attribute("aria-expanded")
            if is_expanded == "false":
                driver.execute_script("arguments[0].click();", availability_header[0])
                time.sleep(0.5)

        # Allow submissions from - UNCHECK
        allow_enabled = driver.find_elements(By.ID, "id_allowsubmissionsfromdate_enabled")
        if allow_enabled:
            if allow_enabled[0].is_selected():
                driver.execute_script("arguments[0].click();", allow_enabled[0])
                time.sleep(0.2)

        # Due date - UNCHECK
        due_enabled = driver.find_elements(By.ID, "id_duedate_enabled")
        if due_enabled:
            if due_enabled[0].is_selected():
                driver.execute_script("arguments[0].click();", due_enabled[0])
                time.sleep(0.2)

        # Cut-off date - UNCHECK
        cutoff_enabled = driver.find_elements(By.ID, "id_cutoffdate_enabled")
        if cutoff_enabled:
            if cutoff_enabled[0].is_selected():
                driver.execute_script("arguments[0].click();", cutoff_enabled[0])
                time.sleep(0.2)

        # Remind me to grade by - UNCHECK
        grading_due_enabled = driver.find_elements(By.ID, "id_gradingduedate_enabled")
        if grading_due_enabled:
            if grading_due_enabled[0].is_selected():
                driver.execute_script("arguments[0].click();", grading_due_enabled[0])
                time.sleep(0.2)
    except Exception as e:
        logger.error(f"  Error configuring availability: {e}")


def run_actividad_export_workflow(
    driver, course_id: int, mode: str, wait_time: int = 10
):
    """
    Main entry point called from main.py.
    Iterates over ACTIVIDAD_WEEKS, parses, generates, and uploads each taller.
    """
    base_dir = os.path.join("assets", str(course_id), "actividades")
    template_path = os.path.join("assets", "templates", "actividad.html")

    if not os.path.exists(template_path):
        logger.error(f"Template not found: {template_path}")
        return

    from actions.moodle_actions import navigate_to_course

    # Ensure we are on the course page once
    navigate_to_course(driver, Config.MOODLE_URL, course_id, wait_time)
    main_window = driver.current_window_handle

    # Wait for the footer to be visible to ensure the course page is fully loaded
    try:
        WebDriverWait(driver, 90).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "footer, #page-footer"))
        )
        logger.info("  Course page fully loaded (footer is visible).")
    except TimeoutException:
        logger.warning("  Footer not visible during initial load, proceeding anyway...")
    except WebDriverException as e:
        logger.error(
            f"  WebDriver error while waiting for footer (browser closed or reloading?): {e}"
        )
        return
    except Exception as e:
        logger.error(f"  Unexpected error waiting for footer: {e}")
        return

    for week in ACTIVIDAD_WEEKS:
        logger.info(f"--- Processing Actividad {week} ---")
        week_name = f"Semana {week[1:]}"

        raw_path = os.path.join(base_dir, f"Plantilla_Taller_{week}.html")
        output_path = os.path.join(base_dir, f"{week}_actividad.html")
        moodle_activity_name = f"{week} | Actividad"

        # ── 1. Get raw file ────────────────────────────────────────────────
        try:
            if mode == "remote":
                edit_url = _get_edit_url_in_section(
                    driver, week_name, "VIR - ACTIVIDAD"
                )
                if not edit_url:
                    logger.warning(f"  VIR - ACTIVIDAD not found for {week}, skipping.")
                    continue

                driver.execute_script(f"window.open('{edit_url}', '_blank');")
                driver.switch_to.window(driver.window_handles[-1])

                # Wait for editor page to load
                WebDriverWait(driver, wait_time).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
                )
                html_content = _extract_html_from_editor(driver, wait_time)

                driver.close()
                driver.switch_to.window(main_window)

                if html_content:
                    os.makedirs(os.path.dirname(raw_path), exist_ok=True)
                    with open(raw_path, "w", encoding="utf-8") as f:
                        f.write(html_content)
                    logger.info(
                        f"  ✓ Downloaded raw HTML for VIR - ACTIVIDAD in {week}"
                    )
                else:
                    logger.warning(
                        f"  Failed to download raw info for {week}, skipping."
                    )
                    continue

            if not os.path.exists(raw_path):
                logger.warning(f"  Raw file not found, skipping: {raw_path}")
                continue

            raw_html = _read_raw_html(raw_path)
            parsed_data = parse_actividad_data(raw_html)
            logger.info(
                f"  Parsed data keys with content: "
                f"{[k for k, v in parsed_data.items() if v]}"
            )

            # ── 2. Generate output HTML ──────────────────────────────────────────
            try:
                generate_actividad_html_file(parsed_data, template_path, output_path)
            except Exception as e:
                logger.error(f"  Failed to generate HTML for {week}: {e}")
                continue

            # ── 3. Upload to Moodle ──────────────────────────────────────────────
            try:
                upload_url = _get_edit_url_global(driver, moodle_activity_name)
                if not upload_url:
                    logger.warning(
                        f"  Moodle activity '{moodle_activity_name}' not found. Skipping upload."
                    )
                    continue

                driver.execute_script(f"window.open('{upload_url}', '_blank');")
                driver.switch_to.window(driver.window_handles[-1])

                with open(output_path, "r", encoding="utf-8") as f:
                    html_content = f.read()

                # Wait for editor page to load
                WebDriverWait(driver, wait_time).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
                )
                
                # Configure the availability dates before saving
                _configure_actividad_availability(driver)
                
                success = inject_html_into_wysiwyg(driver, html_content, wait_time)

                if success:
                    logger.info(
                        f"  ✓ Successfully uploaded {week} actividad to Moodle."
                    )
                else:
                    logger.error(f"  ✗ Upload failed for {week} actividad.")

                driver.close()
                driver.switch_to.window(main_window)

            except WebDriverException as e:
                logger.error(
                    f"  WebDriver error during upload of {week} (browser closed?): {e}"
                )
                # Ensure we switch back to main window if possible
                try:
                    driver.switch_to.window(main_window)
                except:
                    pass
            except Exception as e:
                logger.error(f"  Unexpected error during upload of {week}: {e}")

        except WebDriverException as e:
            logger.error(
                f"  WebDriver error processing {week} (browser closed or lost connection?): {e}"
            )
            try:
                driver.switch_to.window(main_window)
            except:
                pass
            break  # Break out of loop if browser is dead
        except Exception as e:
            logger.error(f"  Unexpected error processing {week}: {e}")
            try:
                driver.close()
                driver.switch_to.window(main_window)
            except:
                pass
