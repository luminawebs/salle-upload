"""
One shared definition of "what counts as a unit / intro heading" in a course
design document, used by every parser in the pipeline.

Why this exists: the splitter (core/data_parser.py), the Moodle structure
parser (actions/structure_actions.py), the review report
(core/document_reviewer.py) and the generalidades accordion
(actions/html_transformer.py) each used to hard-code their own copy of the
heading wording. A document that spelled a heading differently (a real one
did: "UNIDAD 1. ..." instead of "UNIDAD DIDÁCTICA 1", and
"PRESENTACIÓN DEL ESPACIO" without "ACADÉMICO") was parsed as having zero
units, and every step downstream of that silently found nothing to do.

Two heading spellings are supported for units:

1. "UNIDAD DIDÁCTICA N" — the original wording. Matching behavior is kept
   exactly as it always was (found anywhere in the text) so documents that
   already work are parsed identically.

2. A bare "UNIDAD N." — accepted ONLY when the row it sits in has exactly one
   non-empty cell. This structural condition is what keeps the course
   overview table safe: every design document starts with a summary table
   listing "Unidad 1. ...", "Unidad 2. ..." (and their activities) in a
   multi-column row (6 cells in all three documents checked), while the real
   section headings each sit alone in their own single-cell table. Matching on
   wording alone would treat the summary rows as real units and duplicate
   every unit and activity.
"""
import re

_LEGACY_UNIT_RE = re.compile(r"UNIDAD\s+DID[ÁA]CTICA\s*(\d+)")
_LEGACY_UNIT_PREFIX_RE = re.compile(r"^\s*UNIDAD\s+DID[ÁA]CTICA")
_BARE_UNIT_RE = re.compile(r"^\s*UNIDAD\s*(\d+)\b")
_INTRO_RE = re.compile(r"PRESENTACI[ÓO]N\s+DEL\s+ESPACIO")


def is_single_cell_row(tr) -> bool:
    """True if the table row has exactly one non-empty cell (a lone heading row)."""
    if tr is None:
        return False
    cells = tr.find_all(["td", "th"], recursive=False)
    return sum(1 for c in cells if c.get_text(strip=True)) == 1


def bare_unit_number(text_upper: str, row):
    """Unit number for a bare 'UNIDAD N.' heading row, else None (see module docstring)."""
    if not is_single_cell_row(row):
        return None
    m = _BARE_UNIT_RE.match(text_upper)
    if not m:
        return None
    # The row itself must also START with the heading. Callers that look at
    # individual paragraphs would otherwise accept a paragraph that merely
    # begins with "Unidad 2..." while sitting inside a large single-cell
    # wrapper row full of other content.
    if not _BARE_UNIT_RE.match(row.get_text(" ", strip=True).upper()):
        return None
    return int(m.group(1))


def find_unit_number(text_upper: str, row=None):
    """
    Returns (unit_number, match_end) if this text is a unit heading, else None.
    `text_upper` must already be upper-cased. `row` is the enclosing <tr>
    (or None if the text isn't inside a table).
    """
    m = _LEGACY_UNIT_RE.search(text_upper)
    if m:
        return int(m.group(1)), m.end()
    number = bare_unit_number(text_upper, row)
    if number is not None:
        return number, _BARE_UNIT_RE.match(text_upper).end()
    return None


def is_unit_heading_row(text_upper: str, row=None) -> bool:
    """
    True if a row STARTS a new unit — used to find where an activity's content
    ends. Anchored at the start of the row on purpose: unlike find_unit_number,
    a row that merely mentions "Unidad Didáctica 3" in prose doesn't end an
    activity (this is the same rule the splitter has always used here).
    """
    if _LEGACY_UNIT_PREFIX_RE.match(text_upper):
        return True
    return bare_unit_number(text_upper, row) is not None


def is_intro_heading(text_upper: str) -> bool:
    """'PRESENTACIÓN DEL ESPACIO ACADÉMICO', or the shorter 'PRESENTACIÓN DEL ESPACIO' some templates use."""
    return _INTRO_RE.search(text_upper) is not None
