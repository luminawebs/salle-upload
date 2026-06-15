from bs4 import BeautifulSoup

html = """
<ol>
	<li><p>Item 1</p>
	<li><p>Item 2</p>
        <ul><li>Subitem 1</li></ul>
    </li>
    <li>Item 3</li>
</ol>
"""
soup = BeautifulSoup(html, "html.parser")

def fix_nested_li(soup):
    lis = soup.find_all("li")
    for li in reversed(lis):
        if li.parent and li.parent.name not in ['ul', 'ol']:
            closest_li = li.find_parent('li')
            if closest_li:
                closest_li.insert_after(li)

fix_nested_li(soup)
print("After fix:")
print(soup.prettify())
