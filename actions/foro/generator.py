import os
import copy
import re
import logging
from bs4 import BeautifulSoup

from .cleaner import _convert_lists_to_paragraphs, _hide_plain_urls_in_html, _wrap_book_title_in_italics, URL_PATTERN
from .parser import _resource_html_has_reference_content

logger = logging.getLogger(__name__)

def _insert_resource_html(insert_after, resource_html):
    """Insert normalized resource HTML nodes after a reference tag."""
    normalized_html = _convert_lists_to_paragraphs(
        _hide_plain_urls_in_html(
            _wrap_book_title_in_italics(resource_html)
        )
    )
    resource_soup = BeautifulSoup(normalized_html, "html.parser")
    for node in list(resource_soup.contents):
        clone = copy.deepcopy(node)
        insert_after.insert_after(clone)
        insert_after = clone
    return insert_after

def _append_text_with_links(soup, parent_tag, text, hide_urls=False):
    """
    Appends plain text to a tag and converts detected URLs into self-linking anchors.
    """
    if not text:
        return

    last_index = 0
    for match in URL_PATTERN.finditer(text):
        start, end = match.span()
        if start > last_index:
            parent_tag.append(text[last_index:start])

        raw_url = match.group(0)
        clean_url = raw_url.rstrip('.,;:')
        trailing_text = raw_url[len(clean_url):]

        link_tag = soup.new_tag("a", href=clean_url)
        if hide_urls:
            link_tag.string = "Enlace"
            link_tag["title"] = clean_url
        else:
            link_tag.string = clean_url
        parent_tag.append(link_tag)

        if trailing_text:
            parent_tag.append(trailing_text)

        last_index = end

    if last_index < len(text):
        parent_tag.append(text[last_index:])

def _build_paragraph_tag(soup, text, hide_urls=False):
    """
    Creates a <p> tag for parsed foro content and linkifies any plain-text URLs.
    """
    paragraph = soup.new_tag("p")
    # Clean up spaces before punctuation
    text = re.sub(r'\s+([.,;:?])', r'\1', text)
    _append_text_with_links(soup, paragraph, text.strip(), hide_urls=hide_urls)
    return paragraph

def _build_resource_paragraph_tags(soup, text):
    """
    Creates one <p> per resource entry, closing each paragraph after a detected URL.
    """
    cleaned_text = text.strip()
    if not cleaned_text:
        return []

    paragraphs = []
    segment_start = 0

    for match in URL_PATTERN.finditer(cleaned_text):
        raw_url = match.group(0)
        clean_url = raw_url.rstrip('.,;:')
        match_end = match.start() + len(clean_url)
        paragraph_text = cleaned_text[segment_start:match_end].strip()
        if paragraph_text:
            paragraphs.append(_build_paragraph_tag(soup, paragraph_text, hide_urls=True))
        segment_start = match.end()

    remaining_text = cleaned_text[segment_start:].strip()
    if remaining_text:
        paragraphs.append(_build_paragraph_tag(soup, remaining_text, hide_urls=True))

    if not paragraphs:
        paragraphs.append(_build_paragraph_tag(soup, cleaned_text, hide_urls=True))

    return paragraphs

def generate_foro_html_file(parsed_data, template_path, output_path):
    """
    Reads the foro.html template, replaces dummy content with the parsed data, and saves it.
    """
    with open(template_path, 'r', encoding='utf-8') as f:
        template_html = f.read()
        
    soup = BeautifulSoup(template_html, "html.parser")
    
    # 1. Nombre del foro
    title_header = soup.find(lambda tag: tag.name == "h3" and "Foro de discusión" in tag.text)
    if title_header and parsed_data.get("nombre_del_foro"):
        title_header.clear()
        i_tag = soup.new_tag("i")
        i_tag.string = "Foro de discusión"
        title_header.append(i_tag)
        title_header.append(f". {parsed_data['nombre_del_foro']}")
        
    # 2. Descripción
    desc_header = soup.find(lambda tag: tag.name == "h3" and "Descripción" in tag.text)
    if desc_header and parsed_data.get("descripcion"):
        sibling = desc_header.find_next_sibling()
        while sibling and sibling.name != "h3":
            next_sib = sibling.find_next_sibling()
            sibling.extract()
            sibling = next_sib
        desc_header.insert_after(_build_paragraph_tag(soup, parsed_data["descripcion"]))
        
    # 3. Indicaciones
    ind_header = soup.find(lambda tag: tag.name == "h3" and "Indicaciones para el desarrollo" in tag.text)
    if ind_header:
        sibling = ind_header.find_next_sibling()
        while sibling and sibling.name not in ["h3", "table", "br"]:
            next_sib = sibling.find_next_sibling()
            sibling.extract()
            sibling = next_sib
            
        # Si extrajimos con éxito el HTML de las indicaciones, lo insertamos completo
        if parsed_data.get("indicaciones_html"):
            ind_soup = BeautifulSoup(parsed_data["indicaciones_html"], "html.parser")
            
            # Ensure lists are properly formatted and no extra <p> inside <li>
            for li in ind_soup.find_all("li"):
                for p in li.find_all("p"):
                    p.unwrap()
            
            # Insert after the header
            insert_after = ind_header
            for node in list(ind_soup.contents):
                if node.name == "p" and not node.get_text(strip=True):
                    continue  # Skip empty paragraphs
                clone = copy.deepcopy(node)
                insert_after.insert_after(clone)
                insert_after = clone
        elif parsed_data.get("indicaciones"):
            ind_header.insert_after(_build_paragraph_tag(soup, parsed_data["indicaciones"]))
        
    # 4. Tiempos y recursos table
    # Desarrollo
    td_desarrollo = soup.find(lambda tag: tag.name == "td" and "Desarrollo de la actividad:" in tag.text)
    if td_desarrollo:
        td_desarrollo.find('p').clear()
        strong = soup.new_tag("strong")
        strong.string = "Desarrollo de la actividad: "
        td_desarrollo.find('p').append(strong)
        td_desarrollo.find('p').append(parsed_data.get("desarrollo_actividad", "XX horas"))

    # Consulta
    td_consulta = soup.find(lambda tag: tag.name == "td" and "Consulta de materiales:" in tag.text)
    if td_consulta:
        td_consulta.find('p').clear()
        strong = soup.new_tag("strong")
        strong.string = "Consulta de materiales: "
        td_consulta.find('p').append(strong)
        td_consulta.find('p').append(parsed_data.get("consulta_materiales", "XX horas"))

    # Tipo
    td_tipo = soup.find(lambda tag: tag.name == "td" and "Tipo de actividad:" in tag.text)
    if td_tipo:
        td_tipo.find('p').clear()
        strong = soup.new_tag("strong")
        strong.string = "Tipo de actividad: "
        td_tipo.find('p').append(strong)
        td_tipo.find('p').append(parsed_data.get("tipo_actividad", "Colaborativa"))
        
    # 5. Recursos básicos


# 5. Recursos básicos
    rb_header = soup.find(lambda tag: tag.name == "h4" and "Recursos básicos:" in tag.text)
    if rb_header and parsed_data.get("recursos_basicos"):
        sibling = rb_header.find_next_sibling()
        while sibling and sibling.name not in ["h4", "h3", "br"]:
            next_sib = sibling.find_next_sibling()
            sibling.extract()
            sibling = next_sib
        insert_after = rb_header
        resource_html = parsed_data.get("recursos_basicos_html")
        
        # Debug: Log what we found
        logger.info(f"Recursos básicos - raw text length: {len(parsed_data.get('recursos_basicos', ''))}")
        logger.info(f"Recursos básicos - HTML length: {len(resource_html) if resource_html else 0}")
        if resource_html:
            logger.debug(f"Recursos básicos HTML: {resource_html[:300]}...")
        
        if resource_html and _resource_html_has_reference_content(resource_html):
            insert_after = _insert_resource_html(insert_after, resource_html)
        else:
            logger.warning("No resource_html found for Recursos básicos, falling back to plain text")
            for paragraph in _build_resource_paragraph_tags(soup, parsed_data["recursos_basicos"]):
                insert_after.insert_after(paragraph)
                insert_after = paragraph
        
    # 6. Recursos complementarios
    rc_header = soup.find(lambda tag: tag.name == "h4" and "Recursos complementarios:" in tag.text)
    if rc_header and parsed_data.get("recursos_complementarios"):
        sibling = rc_header.find_next_sibling()
        while sibling and sibling.name not in ["h4", "h3", "br"]:
            next_sib = sibling.find_next_sibling()
            sibling.extract()
            sibling = next_sib
        insert_after = rc_header
        resource_html = parsed_data.get("recursos_complementarios_html")
        logger.info(f"Recursos básicos HTML length: {len(resource_html) if resource_html else 0}")
        if resource_html and _resource_html_has_reference_content(resource_html):
            insert_after = _insert_resource_html(insert_after, resource_html)
        else:
            for paragraph in _build_resource_paragraph_tags(soup, parsed_data["recursos_complementarios"]):
                insert_after.insert_after(paragraph)
                insert_after = paragraph
        
    # 7. Rol del profesor & Instrucciones
    rol_header = soup.find(lambda tag: tag.name == "h3" and "Rol del profesor" in tag.text)
    if rol_header:
        sibling = rol_header.find_next_sibling()
        while sibling:
            next_sib = sibling.find_next_sibling()
            sibling.extract()
            sibling = next_sib
            
        if parsed_data.get("rol_profesor"):
            rol_header.insert_after(_build_paragraph_tag(soup, parsed_data["rol_profesor"]))
            
        if parsed_data.get("instrucciones_participacion"):
            inst_p = soup.new_tag("p")
            inst_strong = soup.new_tag("strong")
            inst_strong.string = "Para participar siga las instrucciones que se muestran a continuación."
            inst_p.append(inst_strong)
            virtual_txt = soup.find("div", class_="virtual-txt")
            if virtual_txt:
                virtual_txt.append(inst_p)
            else:
                logger.warning("virtual-txt div not found in template")

            if parsed_data.get("instrucciones_participacion_html"):
                instructions_soup = BeautifulSoup(
                    parsed_data["instrucciones_participacion_html"], "html.parser")
                for node in list(instructions_soup.contents):
                    virtual_txt.append(copy.deepcopy(node))
            else:
                virtual_txt.append(
                    _build_paragraph_tag(soup, parsed_data["instrucciones_participacion"])
                )

    # Format the generated HTML nicely
    final_html = soup.prettify(formatter="minimal")
    final_html = final_html.replace("\xa0", "&nbsp;")
    final_html = re.sub(r'(?i)\b(evaluaci[oó]n)\b(?![^<]*>)', r'<span class="nolink">\1</span>', final_html)
    
    # Fix spaces or newlines before punctuation, especially after closing tags
    final_html = re.sub(r'>\s+([.,;:?])', r'>\1', final_html)
    # And fix spaces before punctuation within text
    final_html = re.sub(r'(?<!<)\s+([.,;:?])', r'\1', final_html)
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(final_html)
