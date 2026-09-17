"""
Shared safety check for anything an LLM hands back as "extracted HTML".

An LLM's response is untrusted input, the same as any other external data —
its JSON shape can be schema-constrained, but nothing constrains whether the
HTML *content* inside it is actually real content from the source document
versus subtly reworded, reordered, or invented. This check verifies the
extracted HTML is really traceable back to the original, before any caller
treats it as trustworthy.

Originally lived only in core/parser_validator.py (used to verify the
"shadow" AI structure validator's output); pulled out here so
actions/html_transformer.py's AI question QA layer can apply the same check
to corrections/additions it's about to upload for real.
"""
from bs4 import BeautifulSoup


def check_dom_integrity(original_html: str, extracted_html: str) -> dict:
    """
    Stricter DOM consistency checks using BeautifulSoup.
    Verifies that the extracted HTML preserves ordering, attributes, and no unexpected elements.
    Returns {"valid": bool, "warnings": list}
    """
    if not extracted_html.strip():
        return {"valid": True, "warnings": []}

    warnings = []
    # If the exact string is a substring (ignoring outer whitespace), it's perfect.
    if extracted_html.strip() in original_html:
        return {"valid": True, "warnings": []}

    try:
        orig_soup = BeautifulSoup(original_html, "html.parser")
        ext_soup = BeautifulSoup(extracted_html, "html.parser")

        # 1. Check relative ordering of significant tags
        def get_signature(soup):
            sig = []
            for tag in soup.find_all(['p', 'ul', 'ol', 'img', 'table', 'a']):
                sig.append(tag.name)
            return sig

        orig_sig = get_signature(orig_soup)
        ext_sig = get_signature(ext_soup)

        # Extracted signature should be a contiguous sub-sequence of the original signature
        def is_sublist(sub, lst):
            if not sub: return True
            if not lst: return False
            for i in range(len(lst) - len(sub) + 1):
                if lst[i:i+len(sub)] == sub:
                    return True
            return False

        if not is_sublist(ext_sig, orig_sig):
            warnings.append(f"DOM Ordering mismatch. Extracted signature {ext_sig} not found contiguously in original.")

        # 2. Verify preservation of important attributes
        important_attrs = ['src', 'href', 'alt', 'colspan', 'rowspan']
        for ext_tag in ext_soup.find_all(True):
            for attr in important_attrs:
                if ext_tag.has_attr(attr):
                    attr_val = ext_tag[attr]
                    if isinstance(attr_val, list):
                        attr_val = " ".join(attr_val)
                    if attr_val not in original_html:
                        warnings.append(f"Unexpected attribute value found: {attr}={attr_val}")

        valid = len(warnings) == 0
        return {"valid": valid, "warnings": warnings}

    except Exception as e:
        return {"valid": False, "warnings": [f"BeautifulSoup parsing failed: {e}"]}


def check_text_integrity(original_html: str, extracted_html: str) -> dict:
    """
    Verifies the plain text of extracted_html is a verbatim (whitespace-
    normalized) substring of original_html's plain text.

    check_dom_integrity above only checks *structure* — tag ordering,
    preserved image/link attributes — it says nothing about whether the
    words themselves are real. An LLM can return HTML with perfectly
    preserved tag structure around completely fabricated or paraphrased
    text, and check_dom_integrity alone would call that "valid". This is
    the check that actually catches that: the more likely and more
    consequential failure mode for anything text-based, like quiz
    questions and answers.

    Returns {"valid": bool, "warnings": [...]}.
    """
    from bs4 import BeautifulSoup
    extracted_text = " ".join(BeautifulSoup(extracted_html, "html.parser").get_text(" ").split())
    if not extracted_text:
        return {"valid": True, "warnings": []}

    original_text = " ".join(BeautifulSoup(original_html, "html.parser").get_text(" ").split())
    if extracted_text in original_text:
        return {"valid": True, "warnings": []}

    preview = extracted_text[:120] + ("…" if len(extracted_text) > 120 else "")
    return {"valid": False, "warnings": [f'Text not found verbatim in source document: "{preview}"']}
