"""
Tests for the document review's "what was read / what wasn't" analysis
(core/document_coverage.py) and a regression suite over the real course
documents in assets/doc-course-test/.

Run from the project root:
    python -m unittest tests.test_document_review -v

The real-document suite compares against tests/fixtures/document_review_expected.json:
for each document, what the splitter produced (units, activities, types, and
a fingerprint of every fragment file) and which problems the review reports.
It's skipped for documents that aren't on disk (assets/ is git-ignored).
After an intentional change, regenerate the fixture and review the diff:
    python -m tests.test_document_review --update
"""
import glob
import hashlib
import json
import logging
import os
import shutil
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from core.document_coverage import analyze_document, get_ignored_issues, set_ignored_issues  # noqa: E402

DOCS_DIR = os.path.join(ROOT, "assets", "doc-course-test")
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "document_review_expected.json")


def setUpModule():
    logging.disable(logging.CRITICAL)


def tearDownModule():
    logging.disable(logging.NOTSET)


def _review_html(html: str, course_id: str) -> dict:
    """Runs the real review (splitter + report + coverage) on an HTML string."""
    from core.document_reviewer import review_document
    course_dir = os.path.join(ROOT, "workspace", course_id)
    os.makedirs(course_dir, exist_ok=True)
    try:
        with open(os.path.join(course_dir, "raw_docx_extracted.html"), "w", encoding="utf-8") as f:
            f.write(html)
        cwd = os.getcwd()
        os.chdir(ROOT)  # the splitter writes to the relative "workspace/" folder
        try:
            report = review_document(course_id, generate_json=False, generate_text=False, cleanup_fragments=False)
        finally:
            os.chdir(cwd)
        fragments = {}
        for sub in ("actividades", "material", "introduccion", "glosario"):
            for path in sorted(glob.glob(os.path.join(course_dir, sub, "*"))):
                with open(path, "rb") as f:
                    fragments[f"{sub}/{os.path.basename(path)}"] = hashlib.sha256(f.read()).hexdigest()[:16]
        report["_fragments"] = fragments
        return report
    finally:
        shutil.rmtree(course_dir, ignore_errors=True)


def _row(*cells, th=False):
    tag = "th" if th else "td"
    return "<tr>" + "".join(f"<{tag}><p>{c}</p></{tag}>" for c in cells) + "</tr>"


def _doc(*rows):
    return "<table>" + "".join(rows) + "</table>"


ACTIVITY_BODY = [
    _row("¿Qué vamos a lograr? Algo."),
    _row("¿Cómo lo vamos a lograr? Así."),
    _row("Herramientas de la plataforma virtual (Marque con una X): Foro___ Tarea__X__ Cuestionario___"),
]
PLAN = [
    _row("Plan de formación del espacio académico"),
    _row("Unidad", "Resultados", "Actividades"),
    _row("Unidad 1. Intro", "RA1", "Actividad 1: Ensayo. Retoma lo de la actividad 2."),
    _row("Unidad 2. Cierre", "RA2", "Actividad 2: Foro"),
]


class CoverageSyntheticTests(unittest.TestCase):
    """Small hand-built documents: fast, no real files, one behavior each."""

    def issues(self, html, course_id):
        report = _review_html(html, course_id)
        return report, {p["tipo"]: p for p in report["cobertura"]["problemas"]}

    def test_clean_document_has_no_problems(self):
        html = _doc(*PLAN,
                    _row("UNIDAD DIDÁCTICA 1. Intro"), _row("Resumen", "Texto."), _row("Preguntas orientadoras", "¿Qué?"),
                    _row("ACTIVIDAD 1. Ensayo"), *ACTIVITY_BODY,
                    _row("Criterios de desempeño Puntos"),
                    _row("UNIDAD DIDÁCTICA 2. Cierre"), _row("Resumen", "Texto."), _row("Preguntas orientadoras", "¿Qué?"),
                    _row("ACTIVIDAD 2. Foro"), _row("¿Qué vamos a lograr? Algo."),
                    _row("Herramientas de la plataforma virtual (Marque con una X): Foro__X__ Tarea___"))
        report, issues = self.issues(html, "_test_cov_clean")
        # the Tarea has no real rubric table here, so only that is expected
        self.assertEqual(set(issues), {"rubrica_faltante"})
        self.assertEqual(report["cobertura"]["plan"], {"1": [1], "2": [2]},
                         "an activity mentioned in prose must not count as listed in the plan")

    def test_activity_with_unrecognized_heading_is_flagged(self):
        html = _doc(_row("UNIDAD DIDÁCTICA 1. Intro"), _row("Resumen", "Texto."), _row("Preguntas orientadoras", "¿Qué?"),
                    _row("FORO 1. Debate inicial"), *ACTIVITY_BODY)
        report, issues = self.issues(html, "_test_cov_foro")
        issue = issues["actividad_no_reconocida"]
        self.assertTrue(issue["bloquea"])
        self.assertIn("FORO 1. Debate inicial", issue["titulo"])
        block = next(b for b in report["cobertura"]["bloques"] if b["id"] == issue["bloque"])
        self.assertEqual(block["n_filas"], 4)
        self.assertIn("Debate inicial", block["html"])

    def test_plain_unassigned_content_is_flagged(self):
        html = _doc(_row("UNIDAD DIDÁCTICA 1. Intro"), _row("Resumen", "Texto."), _row("Preguntas orientadoras", "¿Qué?"),
                    _row("Una nota suelta que no pertenece a nada"))
        _, issues = self.issues(html, "_test_cov_loose")
        self.assertIn("contenido_sin_asignar", issues)

    def test_header_cell_resumen_is_read(self):
        # Some templates use <th> for these rows; both the review and the step
        # that uploads unit introductions must read them.
        html = _doc(_row("UNIDAD DIDÁCTICA 1. Intro"), _row("Resumen", "Texto del resumen.", th=True),
                    _row("Preguntas orientadoras", "¿Qué?", th=True), _row("ACTIVIDAD 1. Ensayo"), *ACTIVITY_BODY)
        report, issues = self.issues(html, "_test_cov_th")
        self.assertNotIn("unidad_sin_resumen", issues)
        self.assertNotIn("unidad_sin_preguntas_orientadoras", issues)

        from core.unidades_intro_parser import run_unidades_intro_splitting_workflow
        course_dir = os.path.join(ROOT, "workspace", "_test_cov_th_intro")
        os.makedirs(course_dir, exist_ok=True)
        try:
            with open(os.path.join(course_dir, "raw_docx_extracted.html"), "w", encoding="utf-8") as f:
                f.write(html)
            run_unidades_intro_splitting_workflow("_test_cov_th_intro")
            written = ""
            for p in glob.glob(os.path.join(course_dir, "introduccion", "*")):
                with open(p, encoding="utf-8") as f:
                    written += f.read()
            self.assertIn("Texto del resumen.", written)
        finally:
            shutil.rmtree(course_dir, ignore_errors=True)

    def test_unknown_type_and_missing_plan_unit(self):
        html = _doc(*PLAN, _row("UNIDAD DIDÁCTICA 1. Intro"), _row("Resumen", "Texto."),
                    _row("Preguntas orientadoras", "¿Qué?"), _row("ACTIVIDAD 1. Ensayo"), _row("¿Qué vamos a lograr? Algo."))
        _, issues = self.issues(html, "_test_cov_plan")
        self.assertIn("tipo_desconocido", issues)
        self.assertIn("unidad_no_encontrada", issues)
        self.assertIn("actividad_no_encontrada", issues)

    def test_mismatched_row_roles_is_a_problem_not_a_clean_result(self):
        result = analyze_document(_doc(_row("x")), {}, [], {"unidades": {}}, {})
        self.assertEqual([p["tipo"] for p in result["problemas"]], ["analisis_fallido"])
        self.assertTrue(result["problemas"][0]["bloquea"])

    def test_ignored_issues_roundtrip(self):
        course_id = "_test_cov_ignore"
        course_dir = os.path.join(ROOT, "workspace", course_id)
        cwd = os.getcwd()
        os.chdir(ROOT)
        try:
            self.assertEqual(get_ignored_issues(course_id), set())
            set_ignored_issues(course_id, ["tipo_desconocido:a1", "tipo_desconocido:a1", "x:y"])
            self.assertEqual(get_ignored_issues(course_id), {"tipo_desconocido:a1", "x:y"})
        finally:
            os.chdir(cwd)
            shutil.rmtree(course_dir, ignore_errors=True)


class CorrectionsTests(unittest.TestCase):
    """Step 2: turning an unrecognized block into an activity (core/document_corrections.py)."""

    COURSE = "_test_corrections"

    def setUp(self):
        from core.document_reviewer import review_document
        self.review_document = review_document
        self.course_dir = os.path.join(ROOT, "workspace", self.COURSE)
        self.cwd = os.getcwd()
        os.chdir(ROOT)  # everything here uses the relative "workspace/" folder
        os.makedirs(self.course_dir, exist_ok=True)

    def tearDown(self):
        os.chdir(self.cwd)
        shutil.rmtree(self.course_dir, ignore_errors=True)

    def review(self, html):
        with open(os.path.join(self.course_dir, "raw_docx_extracted.html"), "w", encoding="utf-8") as f:
            f.write(html)
        return self.review_document(self.COURSE, generate_json=False, generate_text=False, cleanup_fragments=False)

    def block_issue(self, report):
        return next(p for p in report["cobertura"]["problemas"] if p["tipo"] == "actividad_no_reconocida")

    RUBRIC = (
        "<table><tr><td>Criterios de desempeño</td><td>Puntos</td></tr>"
        "<tr><td>Diseña el diagrama</td><td>2</td></tr><tr><td>Implementa la solución</td><td>1</td></tr></table>"
    )

    def doc(self, heading, *extra_rows):
        # Same layout as the real documents: the unrecognized block sits
        # between the unit's sections and its first "ACTIVIDAD N".
        return _doc(_row("UNIDAD DIDÁCTICA 1. Intro"), _row("Resumen", "Texto."), _row("Preguntas orientadoras", "¿Qué?"),
                    _row(heading), _row("¿Qué vamos a lograr? Debatir."), *extra_rows,
                    _row("Herramientas de la plataforma virtual (Marque con una X): Foro__X__ Tarea___"),
                    _row("ACTIVIDAD 1. Ensayo"), *ACTIVITY_BODY, _row("Criterios de desempeño Puntos"))

    def test_foro_heading_right_after_an_activity_ends_it(self):
        html = _doc(_row("UNIDAD DIDÁCTICA 1. Intro"), _row("Resumen", "Texto."), _row("Preguntas orientadoras", "¿Qué?"),
                    _row("ACTIVIDAD 1. Ensayo"), *ACTIVITY_BODY,
                    _row("FORO 2. Debate final"), _row("¿Qué vamos a lograr? Debatir."))
        issues = {p["tipo"]: p for p in self.review(html)["cobertura"]["problemas"]}
        self.assertNotIn("actividad_fusionada", issues)
        self.assertIn("FORO 2. Debate final", issues["actividad_no_reconocida"]["titulo"])
        with open(os.path.join(self.course_dir, "actividades", "actividad1.html"), encoding="utf-8") as f:
            self.assertNotIn("Debatir", f.read())

    def test_other_heading_right_after_an_activity_is_reported_as_merged(self):
        html = _doc(_row("UNIDAD DIDÁCTICA 1. Intro"), _row("Resumen", "Texto."), _row("Preguntas orientadoras", "¿Qué?"),
                    _row("ACTIVIDAD 1. Ensayo"), *ACTIVITY_BODY,
                    _row("TALLER 2. Debate final"), _row("¿Qué vamos a lograr? Debatir."))
        issues = {p["tipo"]: p for p in self.review(html)["cobertura"]["problemas"]}
        self.assertIn("TALLER 2. Debate final", issues["actividad_fusionada"]["titulo"])
        self.assertTrue(issues["actividad_fusionada"]["bloquea"])

    QUESTIONS = ("<p>1. ¿Cuál es la capital de Colombia?</p><p>=a) Bogotá</p><p>b) Lima</p>")
    QUIZ_TOOLS = _row("Herramientas de la plataforma virtual (Marque con una X): Foro___ Tarea___ Cuestionario__X__")

    def test_quiz_without_questions_is_flagged_and_appending_questions_fixes_it(self):
        from core.document_corrections import set_block_choice, get_appended_blocks
        html = _doc(_row("UNIDAD DIDÁCTICA 1. Intro"), _row("Resumen", "Texto."), _row("Preguntas orientadoras", "¿Qué?"),
                    _row("ACTIVIDAD 1. Evaluación"), _row("¿Qué vamos a lograr? Evaluar."), self.QUIZ_TOOLS,
                    _row("Cuestionario de la unidad"), _row(self.QUESTIONS))
        report = self.review(html)
        issues = {p["tipo"]: p for p in report["cobertura"]["problemas"]}
        self.assertIn("cuestionario_sin_preguntas", issues)
        block = issues["contenido_sin_asignar"]

        set_block_choice(self.COURSE, block["id"], {"agregar_a": 1})
        report = self.review(html)
        issues = {p["tipo"]: p for p in report["cobertura"]["problemas"]}
        self.assertNotIn("cuestionario_sin_preguntas", issues)
        self.assertEqual(issues["contenido_sin_asignar"]["resuelto"]["accion"], "agregar")
        self.assertEqual(issues["contenido_sin_asignar"]["resuelto"]["actividad"], 1)
        self.assertEqual([a["actividad"] for a in get_appended_blocks(self.COURSE)], [1])
        with open(os.path.join(self.course_dir, "actividades", "actividad1.html"), encoding="utf-8") as f:
            self.assertIn("Bogotá", f.read())

    def test_append_to_missing_activity_is_rejected_or_skipped(self):
        from core.document_corrections import set_block_choice, get_appended_blocks
        with self.assertRaises(ValueError):
            set_block_choice(self.COURSE, "contenido_sin_asignar:abc", {"agregar_a": 0})
        html = _doc(_row("UNIDAD DIDÁCTICA 1. Intro"), _row("Resumen", "Texto."),
                    _row("Preguntas orientadoras", "¿Qué?"), _row("Nota suelta"),
                    _row("ACTIVIDAD 1. Ensayo"), *ACTIVITY_BODY)
        report = self.review(html)
        block = next(p for p in report["cobertura"]["problemas"] if p["tipo"] == "contenido_sin_asignar")
        set_block_choice(self.COURSE, block["id"], {"agregar_a": 99})  # there is no Actividad 99
        report = self.review(html)
        self.assertEqual(get_appended_blocks(self.COURSE), [])
        still_open = next(p for p in report["cobertura"]["problemas"] if p["id"] == block["id"])
        self.assertNotIn("resuelto", still_open)

    def test_new_activity_readings_go_to_material_de_referencia(self):
        from core.document_corrections import set_block_activity
        html = self.doc("FORO 1. Debate inicial",
                        _row("<p>Lecturas complementarias</p><ul><li>Lozano, R. (2020). Tierras.</li></ul>"))
        set_block_activity(self.COURSE, self.block_issue(self.review(html))["id"], "Foro")
        self.review(html)
        with open(os.path.join(self.course_dir, "material", "Material_de_referencia_U1.html"), encoding="utf-8") as f:
            self.assertIn("Lozano, R. (2020)", f.read())

    def test_block_becomes_activity_and_undo_removes_it(self):
        from core.document_corrections import set_block_activity, get_extra_activities
        report = self.review(self.doc("FORO 1. Debate inicial"))
        issue = self.block_issue(report)
        self.assertEqual(issue["tipo_sugerido"], "Foro", "type pre-selected from the block's own X")

        set_block_activity(self.COURSE, issue["id"], "Foro")
        report = self.review(self.doc("FORO 1. Debate inicial"))
        [extra] = get_extra_activities(self.COURSE)
        self.assertEqual((extra["nombre"], extra["tipo"], extra["unidad"]), ("FORO 1. Debate inicial", "Foro", 1))
        with open(os.path.join(self.course_dir, "actividades_extra", extra["archivo"]), encoding="utf-8") as f:
            fragment = f.read()
        self.assertIn("Debatir", fragment)
        self.assertNotIn("FORO 1. Debate inicial", fragment, "the heading becomes the Moodle name, not body text")
        resolved = self.block_issue(report)
        self.assertEqual(resolved["resuelto"]["tipo"], "Foro")
        self.assertEqual(report["actividades_extra"][0]["nombre"], "FORO 1. Debate inicial")
        self.assertIn("corregido", {b["estado"] for b in report["cobertura"]["bloques"]})

        set_block_activity(self.COURSE, issue["id"], None)
        report = self.review(self.doc("FORO 1. Debate inicial"))
        self.assertEqual(get_extra_activities(self.COURSE), [])
        self.assertNotIn("resuelto", self.block_issue(report))

    def test_tarea_block_gets_its_rubric(self):
        from core.document_corrections import set_block_activity, get_extra_activities
        html = self.doc("Proyecto de Clase (Final): Solución", _row("¿Cómo lo vamos a evaluar?" + self.RUBRIC))
        set_block_activity(self.COURSE, self.block_issue(self.review(html))["id"], "Tarea")
        report = self.review(html)
        [extra] = get_extra_activities(self.COURSE)
        self.assertEqual([c["name"] for c in extra["rubrica"]], ["Diseña el diagrama", "Implementa la solución"])
        self.assertEqual(extra["rubrica"][0]["scores"], ["2", "1.5", "1", "0.5", "0"])
        self.assertFalse(any(p["tipo"] == "rubrica_faltante" and p["id"].startswith("rubrica_faltante:x")
                             for p in report["cobertura"]["problemas"]))

    def test_tarea_block_without_rubric_is_flagged(self):
        from core.document_corrections import set_block_activity
        html = self.doc("Proyecto de Clase (Final): Solución")
        set_block_activity(self.COURSE, self.block_issue(self.review(html))["id"], "Tarea")
        report = self.review(html)
        self.assertTrue(any(p["id"].startswith("rubrica_faltante:x") for p in report["cobertura"]["problemas"]))

    def test_invalid_type_is_rejected(self):
        from core.document_corrections import set_block_activity
        with self.assertRaises(ValueError):
            set_block_activity(self.COURSE, "actividad_no_reconocida:abc", "Wiki")

    def test_rerunning_the_splitter_does_not_duplicate_fragments(self):
        html = self.doc("FORO 1. Debate inicial")
        self.review(html)
        self.review(html)
        self.assertEqual(sorted(os.listdir(os.path.join(self.course_dir, "actividades"))), ["actividad1.html"])

    def test_extra_activities_go_to_their_unit_section_in_document_order(self):
        from core.document_corrections import add_extra_activities_to_sections
        acts = [{"name": "ACTIVIDAD 4: Algo", "type": "Tarea"}, {"name": "ACTIVIDAD 5. Otra", "type": "Foro"}]
        sections = [{"unit_number": 1, "activities": []}, {"unit_number": 2, "activities": list(acts)}]
        extras = [
            {"nombre": "Proyecto (Avance 1)", "tipo": "Tarea", "unidad": 1, "antes_de_actividad": 5},
            {"nombre": "Foro final", "tipo": "Foro", "unidad": 1, "antes_de_actividad": None},
            {"nombre": "Suelto", "tipo": "Tarea", "unidad": None},
        ]
        unplaced = add_extra_activities_to_sections(sections, extras)
        self.assertEqual([a["name"] for a in sections[1]["activities"]],
                         ["ACTIVIDAD 4: Algo", "Proyecto (Avance 1)", "ACTIVIDAD 5. Otra", "Foro final"])
        self.assertEqual(sections[0]["activities"], [], "section 1 is Generalidades, never a unit")
        self.assertEqual([e["nombre"] for e in unplaced], ["Suelto"])

    def test_new_activity_records_the_activity_that_follows_it(self):
        from core.document_corrections import set_block_activity, get_extra_activities
        html = self.doc("FORO 1. Debate inicial")
        set_block_activity(self.COURSE, self.block_issue(self.review(html))["id"], "Foro")
        self.review(html)
        self.assertEqual(get_extra_activities(self.COURSE)[0]["antes_de_actividad"], 1)


def _docx_paths():
    return sorted(glob.glob(os.path.join(DOCS_DIR, "**", "*.docx"), recursive=True))


def _summarize_docx(path: str, index: int) -> dict:
    from core.data_parser import parse_docx_to_html
    course_id = f"_test_review_{index}"
    cwd = os.getcwd()
    os.chdir(ROOT)  # parse_docx_to_html writes images to the relative "workspace/"
    try:
        html = parse_docx_to_html(path, course_id)
    finally:
        os.chdir(cwd)
        shutil.rmtree(os.path.join(ROOT, "workspace", course_id), ignore_errors=True)
    report = _review_html(html, course_id)
    return {
        "unidades": {u: {a: act["tipo"] for a, act in data["actividades"].items()} for u, data in report["unidades"].items()},
        "fragmentos": report["_fragments"],
        "problemas": sorted(p["id"] for p in report["cobertura"]["problemas"]),
        "bloqueantes": sorted(p["id"] for p in report["cobertura"]["problemas"] if p["bloquea"]),
    }


class RealDocumentRegressionTests(unittest.TestCase):
    """The real course documents must keep producing exactly the recorded result."""

    @classmethod
    def setUpClass(cls):
        if not os.path.exists(FIXTURE):
            raise unittest.SkipTest("No fixture yet — run: python -m tests.test_document_review --update")
        with open(FIXTURE, encoding="utf-8") as f:
            cls.expected = json.load(f)

    def test_real_documents(self):
        checked = 0
        for i, path in enumerate(_docx_paths()):
            rel = os.path.relpath(path, DOCS_DIR).replace("\\", "/")
            if rel not in self.expected:
                continue
            with self.subTest(document=rel):
                self.assertEqual(_summarize_docx(path, i), self.expected[rel])
            checked += 1
        if checked == 0:
            self.skipTest(f"None of the recorded documents are present in {DOCS_DIR}")


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    if "--update" in sys.argv:
        result = {}
        for i, path in enumerate(_docx_paths()):
            rel = os.path.relpath(path, DOCS_DIR).replace("\\", "/")
            result[rel] = _summarize_docx(path, i)
            print(f"{rel}: {len(result[rel]['bloqueantes'])} bloqueante(s), {len(result[rel]['problemas'])} total")
        os.makedirs(os.path.dirname(FIXTURE), exist_ok=True)
        with open(FIXTURE, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=1, sort_keys=True)
        print(f"Fixture written: {FIXTURE}")
    else:
        unittest.main()
