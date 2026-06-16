from bs4 import BeautifulSoup
import re

html_file = "d:\\29 LA SALLE\\automatizacion_selenium_SALLE-frontend\\assets\\example_course\\tableoutput_unedited.html"

with open(html_file, 'r', encoding='utf-8') as f:
    soup = BeautifulSoup(f.read(), 'html.parser')

def format_plan_de_formacion_table(table_soup):
    table_soup['class'] = "MsoTableGrid"
    table_soup['style'] = "width: 100%; border-collapse: collapse; border: 1px solid #000; font-family: Arial, sans-serif; font-size: 10pt; color: #000; text-align: center;"
    table_soup['border'] = "1"
    table_soup['cellspacing'] = "0"
    table_soup['cellpadding'] = "0"
    
    rows = table_soup.find_all('tr')
    col_widths_6 = ["9.78%", "14.2%", "19.62%", "31.74%", "15.18%", "9.48%"]
    col_widths_3 = ["31.74%", "15.18%", "9.48%"]
    
    for r_idx, row in enumerate(rows):
        cells = row.find_all(['td', 'th'])
        
        if r_idx == 0 and len(cells) == 1:
            cells[0]['style'] = "border: 1px solid #000; background: #f2a900; padding: 5px; font-weight: bold; font-size: 12pt;"
            # Center the header
            for p in cells[0].find_all('p'):
                p['style'] = "text-align: center;"
            continue
            
        if r_idx == 1 and len(cells) >= 5:
            for c_idx, cell in enumerate(cells):
                w = col_widths_6[c_idx] if c_idx < len(col_widths_6) else "auto"
                cell['style'] = f"border: 1px solid #000; background: #fac96a; font-weight: bold; padding: 5px; width: {w};"
            continue
            
        is_encuentro = "encuentro virtual" in row.get_text().lower()
        bg_color = "#fdfdec" if is_encuentro else "#fff"
        widths = col_widths_6 if len(cells) >= 5 else col_widths_3
        
        for c_idx, cell in enumerate(cells):
            w = widths[c_idx] if c_idx < len(widths) else "auto"
            is_activity_col = (len(cells) <= 3) or (c_idx >= 3)
            cell_bg = bg_color if is_activity_col else "#fff"
            
            align = "left" if (is_activity_col and c_idx == (0 if len(cells) <= 3 else 3)) else "center"
            if len(cell.get_text(strip=True)) > 20:
                align = "left"
                
            cell['style'] = f"border: 1px solid #000; background: {cell_bg}; padding: 5px; text-align: {align}; vertical-align: top; width: {w};"
            
            for heading in cell.find_all(['h1', 'h2', 'h3', 'h4']):
                new_p = table_soup.new_tag('p')
                strong = table_soup.new_tag('strong')
                strong.append(heading.get_text())
                new_p.append(strong)
                heading.replace_with(new_p)
                
            for p in cell.find_all('p'):
                if p.has_attr('style'): del p['style']
                if p.has_attr('align'): del p['align']
                if p.has_attr('class'): del p['class']

t = soup.find('table')
if t:
    format_plan_de_formacion_table(t)
    with open("test_output.html", "w", encoding="utf-8") as out:
        out.write(str(t))
