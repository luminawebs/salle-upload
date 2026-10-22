"""
Word's automatic numbering ("1.", "2." on questions, "A.", "B." on options)
is not text: it's drawn by Word from word/numbering.xml. The DOCX → HTML
conversion (mammoth) keeps only the text, and puts consecutive numbered
paragraphs into one <ol>, so a quiz written with automatic numbering reached
the question reader as one flat list — questions and options mixed, no way
to tell where one question ends (11 questions read as 1).

materialize_quiz_numbering() writes the number or letter Word shows into
the paragraph as text, and drops the automatic numbering, only for the lists
that hold questions and lose their structure: a run of consecutive numbered
paragraphs mixing two lists at the same level, with an answer marked
"(respuesta)" inside it, in a part of the document that is a quiz (a
stretch between two "ACTIVIDAD …" headings with an answer marked). Every
other list — instructions in a quiz's description, "Verdadero / Falso"
options answered on a separate line, any list in another activity — is left
as a Word list: those were already read right, and still upload as HTML
lists.
"""
import io
import logging
import re
import zipfile

from lxml import etree

logger = logging.getLogger(__name__)

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_NS = {"w": W}
_XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"

# Formats turned into text; bullets and anything else stay Word lists.
_FORMATS = ("decimal", "upperLetter", "lowerLetter", "upperRoman", "lowerRoman")

_HEADING_RE = re.compile(r"^\s*ACTIVIDAD\s*(\d|#|[IVXLC]+\b)", re.IGNORECASE)
_ANSWER_RE = re.compile(r"\(\s*respuesta|respuesta\s+correcta", re.IGNORECASE)
_MARKED_ANSWER_RE = re.compile(r"\(\s*respuesta", re.IGNORECASE)


def _w(tag):
    return f"{{{W}}}{tag}"


def _roman(n: int) -> str:
    out = ""
    for value, letters in ((1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"),
                           (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")):
        while n >= value:
            out += letters
            n -= value
    return out


def _letters(n: int) -> str:
    # Word: A..Z, then AA..ZZ, AAA… (the letter repeated)
    return chr(ord("A") + (n - 1) % 26) * ((n - 1) // 26 + 1)


def _format(n: int, fmt: str) -> str:
    if fmt == "decimal":
        return str(n)
    if fmt == "upperLetter":
        return _letters(n)
    if fmt == "lowerLetter":
        return _letters(n).lower()
    if fmt == "upperRoman":
        return _roman(n)
    if fmt == "lowerRoman":
        return _roman(n).lower()
    return ""


def _val(el, path):
    found = el.find(path, _NS)
    return found.get(_w("val")) if found is not None else None


class _Numbering:
    """The list definitions in word/numbering.xml and the running counters."""

    def __init__(self, numbering_xml: bytes):
        root = etree.fromstring(numbering_xml)
        self.levels = {}  # abstractNumId -> {ilvl: (fmt, lvlText, start)}
        for abstract in root.findall("w:abstractNum", _NS):
            levels = {}
            for lvl in abstract.findall("w:lvl", _NS):
                levels[lvl.get(_w("ilvl"))] = (
                    _val(lvl, "w:numFmt") or "decimal",
                    _val(lvl, "w:lvlText") or "",
                    int(_val(lvl, "w:start") or 1),
                )
            self.levels[abstract.get(_w("abstractNumId"))] = levels
        self.nums = {}  # numId -> (abstractNumId, {ilvl: startOverride})
        for num in root.findall("w:num", _NS):
            overrides = {}
            for override in num.findall("w:lvlOverride", _NS):
                start = _val(override, "w:startOverride")
                if start is not None:
                    overrides[override.get(_w("ilvl"))] = int(start)
            self.nums[num.get(_w("numId"))] = (_val(num, "w:abstractNumId"), overrides)
        # Word continues a list across numIds that share an abstract
        # definition, unless the numId restarts it (startOverride).
        self.counters = {}  # abstractNumId -> {ilvl(int): count}
        self.started = set()

    def label(self, num_id: str, ilvl: str):
        """The text Word shows for the next paragraph of this list ("3.", "B)"), or None."""
        if num_id not in self.nums or num_id == "0":
            return None
        abstract_id, overrides = self.nums[num_id]
        levels = self.levels.get(abstract_id, {})
        if ilvl not in levels:
            return None
        counters = self.counters.setdefault(abstract_id, {})
        level = int(ilvl)
        if num_id not in self.started:
            self.started.add(num_id)
            for lvl, start in overrides.items():
                counters[int(lvl)] = start - 1
        fmt, text, start = levels[ilvl]
        counters[level] = counters.get(level, start - 1) + 1
        for deeper in [k for k in counters if k > level]:
            del counters[deeper]  # a new item restarts its sub-levels
        if fmt not in _FORMATS:
            return None

        def placeholder(m):
            k = int(m.group(1)) - 1
            k_fmt, _, k_start = levels.get(str(k), ("decimal", "", 1))
            return _format(counters.get(k, k_start), k_fmt)

        return re.sub(r"%(\d)", placeholder, text).strip() or None


def _paragraph_text(p) -> str:
    return "".join(t.text or "" for t in p.iter(_w("t")))


def _quiz_paragraphs(paragraphs) -> set:
    """Indexes of the paragraphs that sit in a quiz: between two activity headings, with an answer marked."""
    segments, current = [], []
    for i, p in enumerate(paragraphs):
        if _HEADING_RE.match(_paragraph_text(p)) and current:
            segments.append(current)
            current = []
        current.append(i)
    segments.append(current)
    quiz = set()
    for segment in segments:
        if any(_ANSWER_RE.search(_paragraph_text(paragraphs[i])) for i in segment):
            quiz.update(segment)
    return quiz


def materialize_quiz_numbering(docx_bytes: bytes) -> bytes:
    """
    The same .docx with the automatic numbers/letters of quiz lists written as
    text. Returns the input unchanged when there's nothing to do or the file
    can't be read this way (the conversion then works as before).
    """
    try:
        with zipfile.ZipFile(io.BytesIO(docx_bytes)) as src:
            if "word/numbering.xml" not in src.namelist():
                return docx_bytes
            numbering = _Numbering(src.read("word/numbering.xml"))
            document = etree.fromstring(src.read("word/document.xml"))
            paragraphs = list(document.iter(_w("p")))
            quiz = _quiz_paragraphs(paragraphs)
            # Every numbered paragraph's label, in document order (counters
            # run across the whole document), and the runs of consecutive
            # numbered paragraphs (empty paragraphs don't break a run).
            labels, lists, runs, run = {}, {}, [], []
            for i, p in enumerate(paragraphs):
                num_pr = p.find("w:pPr/w:numPr", _NS)
                if num_pr is not None:
                    num_id, ilvl = _val(num_pr, "w:numId"), _val(num_pr, "w:ilvl") or "0"
                    labels[i] = numbering.label(num_id, ilvl)
                    lists[i] = (num_id, ilvl)
                    run.append(i)
                elif _paragraph_text(p).strip():
                    if run:
                        runs.append(run)
                    run = []
            if run:
                runs.append(run)
            targets = set()
            for run in runs:
                # Only where the conversion flattens it: two different lists
                # at the same level (questions "1." and options "A." side by
                # side). Options indented one level below their question stay
                # a nested list, which the question reader already reads.
                by_level = {}
                for i in run:
                    by_level.setdefault(lists[i][1], set()).add(lists[i][0])
                flattened = any(len(ids) > 1 for ids in by_level.values())
                if (flattened and any(i in quiz for i in run)
                        and any(_MARKED_ANSWER_RE.search(_paragraph_text(paragraphs[i])) for i in run)):
                    targets.update(run)
            # A list written as text is written whole (in the quiz): the
            # questions of one list sit in other runs too ("10. Complete…"
            # with no options), and left as a Word list they'd be read as
            # options of the question before.
            target_lists = {lists[i][0] for i in targets}
            targets.update(i for i, (num_id, _) in lists.items() if num_id in target_lists and i in quiz)
            changed = 0
            for i, p in enumerate(paragraphs):
                label = labels.get(i)
                if label is None or i not in targets:
                    continue
                num_pr = p.find("w:pPr/w:numPr", _NS)
                num_pr.getparent().remove(num_pr)
                run = etree.Element(_w("r"))
                t = etree.SubElement(run, _w("t"))
                t.text = label + " "
                t.set(_XML_SPACE, "preserve")
                ppr = p.find("w:pPr", _NS)
                p.insert(p.index(ppr) + 1 if ppr is not None else 0, run)
                changed += 1
            if not changed:
                return docx_bytes
            out = io.BytesIO()
            with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as dst:
                for item in src.infolist():
                    data = src.read(item.filename)
                    if item.filename == "word/document.xml":
                        data = etree.tostring(document, xml_declaration=True, encoding="UTF-8", standalone=True)
                    dst.writestr(item, data)
            logger.debug(f"Numeración automática escrita como texto en {changed} párrafo(s) de cuestionarios.")
            return out.getvalue()
    except Exception as e:
        logger.warning(f"No se pudo leer la numeración automática del documento ({e}); se convierte sin ella.")
        return docx_bytes
