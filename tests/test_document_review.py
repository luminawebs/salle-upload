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

from bs4 import BeautifulSoup

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


class QuizQuestionTests(unittest.TestCase):
    """How many questions a Cuestionario has, as read vs. as the document shows."""

    # Word numbering often produces ONE flat list: questions and options side by
    # side (this is DP_ARIE's Actividad 6, which used to read as 1 question).
    FLAT_LIST = (
        "<p>Número de preguntas de la prueba: 3</p><ol>"
        "<li>¿Cuál es la capital de Colombia?</li><li>Lima</li><li>Bogotá (Respuesta)</li><li>Quito</li>"
        "<li>¿Cuánto es 2 + 2?</li><li>3</li><li>4 (Respuesta)</li><li>5</li>"
        "<li>¿Qué color tiene el cielo?</li><li>Azul (Respuesta)</li><li>Verde</li><li>Rojo</li>"
        "</ol>"
    )

    def test_flat_list_questions_are_read_separately(self):
        from actions.html_transformer import parse_questions, summarize_quiz
        questions = parse_questions(self.FLAT_LIST)
        self.assertEqual(len(questions), 3)
        self.assertEqual([len(q["options"]) for q in questions], [3, 3, 3])
        self.assertEqual([sum(o["is_correct"] for o in q["options"]) for q in questions], [1, 1, 1])
        summary = summarize_quiz(self.FLAT_LIST)
        self.assertEqual((summary["encontradas"], summary["declaradas"], summary["esperadas"], summary["no_leidas"]),
                         (3, 3, 3, []))

    def test_answer_line_format(self):
        # Question, unmarked options, then "Respuesta correcta: X" (Jesús Maestro, Procesos Psicológicos).
        from actions.html_transformer import parse_questions
        html = ("<p>Preguntas:</p><ul><li>¿En qué siglo vivió Jesús?</li><li>Siglo I</li><li>Siglo II</li><li>Siglo III</li></ul>"
                "<p>Respuesta correcta: Siglo I</p>"
                "<ul><li>Es un ejemplo de razonamiento deductivo:</li><li>Concluir algo general a partir de casos</li>"
                "<li>Concluir que un ave es un águila porque es un pájaro</li><li>Nada de lo anterior sirve aquí</li></ul>"
                "<p>Respuesta correcta: Concluir que un ave es un aguila porque es un pajaro.</p>"
                "<p>Retroalimentación incorrecta: Revisa el tema.</p>")
        questions = parse_questions(html)
        self.assertEqual(len(questions), 2)
        self.assertEqual([[o["is_correct"] for o in q["options"]] for q in questions],
                         [[True, False, False], [False, True, False]])
        self.assertTrue(questions[1]["feedback"]["incorrect"], "feedback after the answer line is kept")

    def test_answer_line_true_false(self):
        from actions.html_transformer import parse_questions, extract_questions_from_html_to_moodle_xml
        html = ("<p>Responda falso o verdadero según corresponda:</p>"
                "<ul><li>La afasia es siempre el resultado de un daño permanente</li></ul><p>Respuesta correcta: Falso.</p>"
                "<ul><li>La corteza cerebral participa en el procesamiento del lenguaje</li></ul><p>Respuesta correcta: Verdadero</p>")
        questions = parse_questions(html)
        self.assertEqual([(q["q_type"], q["tf_answer"]) for q in questions], [("truefalse", False), ("truefalse", True)])
        xml_path = os.path.join(ROOT, "workspace", "_test_tf.xml")
        try:
            logging.disable(logging.CRITICAL)
            self.assertEqual(extract_questions_from_html_to_moodle_xml(html, xml_path), 2)
            with open(xml_path, encoding="utf-8") as f:
                xml = f.read()
            self.assertIn('fraction="0" format="moodle_auto_format">\n      <text>true', xml)
            self.assertIn('fraction="100" format="moodle_auto_format">\n      <text>true', xml)
        finally:
            if os.path.exists(xml_path):
                os.remove(xml_path)

    def test_answer_line_with_lettered_paragraph_options(self):
        # Conflicto tierras: options as "A. …" paragraphs used to have no correct answer at all.
        from actions.html_transformer import parse_questions
        html = ("<p>Pregunta 1.</p><p>¿Qué tipo de conflicto es?</p><p>A. Un litigio civil</p><p>B. Un conflicto agrario</p>"
                "<p>C. Un trámite administrativo</p><p>Respuesta correcta: Un conflicto agrario</p>")
        [question] = parse_questions(html)
        self.assertEqual([o["is_correct"] for o in question["options"]], [False, True, False])

    def test_explanation_after_answer_line_is_feedback_not_a_question(self):
        # Conflicto tierras: long explanation paragraphs after the answer used
        # to be read as extra "questions" with no options.
        from actions.html_transformer import parse_questions
        html = ("<p>Pregunta 1.</p><p>¿Qué tipo de conflicto es?</p><p>A. Un litigio civil</p><p>B. Un conflicto agrario</p>"
                "<p>Respuesta correcta: Un conflicto agrario</p>"
                "<p>La lectura del conflicto de tierras exige superar una comprensión puramente jurídica del caso.</p>"
                "<p>Correcto. Los conflictos por la tierra deben leerse desde varias dimensiones a la vez.</p>"
                "<p>Pregunta 2.</p><p>¿Quién decide?</p><p>A. El juez</p><p>B. Nadie</p><p>Respuesta correcta: El juez</p>")
        questions = parse_questions(html)
        self.assertEqual(len(questions), 2)
        self.assertIn("comprensión puramente jurídica", "".join(questions[0]["feedback"]["general"]))
        self.assertEqual([[o["is_correct"] for o in q["options"]] for q in questions], [[False, True], [True, False]])

    def test_answer_line_that_matches_no_option_is_not_guessed(self):
        from actions.html_transformer import parse_questions, summarize_quiz
        html = ("<ul><li>¿Primera pregunta?</li><li>Uno</li><li>Dos</li></ul><p>Respuesta correcta: Tres</p>"
                "<ul><li>¿Segunda pregunta?</li><li>Cuatro</li><li>Cinco</li></ul><p>Respuesta correcta: Cuatro</p>")
        questions = parse_questions(html)
        self.assertFalse(any(o["is_correct"] for o in questions[0]["options"]),
                         "no option matches 'Tres': nothing may be marked correct")
        self.assertEqual(summarize_quiz(html)["esperadas"], 2)

    def test_activity_preview_sections_and_questions(self):
        from core.activity_preview import build_preview
        html = ("<p><b>¿Qué vamos a lograr?</b></p><p>Aprender algo.</p>"
                "<p><b>¿Cómo lo vamos a lograr?</b></p><p>Responde:</p>" + self.FLAT_LIST +
                "<p>¿Cómo lo vamos a evaluar?</p><p>Información para el equipo de producción de la DEE</p><p>Foro___</p>")
        preview = build_preview(html)
        self.assertEqual([s["titulo"] for s in preview["secciones"]],
                         ["¿Qué vamos a lograr?", "¿Cómo lo vamos a lograr?", "¿Cómo lo vamos a evaluar?",
                          "Información para el equipo de producción"])
        self.assertIn("Aprender algo", preview["secciones"][0]["html"])
        self.assertEqual([q["numero"] for q in preview["preguntas"]], [1, 2, 3])
        self.assertEqual([q["correctas"] for q in preview["preguntas"]], [1, 1, 1])
        self.assertEqual(preview["resumen_preguntas"]["esperadas"], 3)

    def test_quiz_description_loses_questions_and_answers_but_keeps_the_rest(self):
        # DP_ARIE Actividad 6 used to upload all 10 questions, each with "(Respuesta)", in the description.
        from actions.html_transformer import remove_questions_from_html, parse_questions
        html = ("<p>¿Qué vamos a lograr?</p><p>Presentar la evaluación.</p>"
                "<p>¿Cómo lo vamos a lograr?</p><p>Número de preguntas de la prueba: 3</p>"
                "<p>Luego proceda a responder la evaluación:</p><p>Preguntas:</p>"
                + self.FLAT_LIST.replace("<p>Número de preguntas de la prueba: 3</p>", "") +
                "<p>Entregable : Presentar la prueba en la fecha indicada.</p>"
                "<p>¿Cómo lo vamos a evaluar?</p><p>Criterios de desempeño</p>")
        cleaned = remove_questions_from_html(html, is_quiz=True)
        text = " ".join(BeautifulSoup(cleaned, "html.parser").get_text(" ").split())
        self.assertNotIn("(Respuesta)", text)
        self.assertNotIn("¿Cuál es la capital", text)
        self.assertNotIn("Preguntas:", text, "a heading left pointing at nothing is removed too")
        for kept in ("¿Qué vamos a lograr?", "Presentar la evaluación.", "proceda a responder", "Número de preguntas",
                     "Entregable : Presentar la prueba", "¿Cómo lo vamos a evaluar?", "Criterios de desempeño"):
            self.assertIn(kept, text)
        self.assertEqual(parse_questions(cleaned), [])

    def test_questions_inside_the_evaluation_section_are_read_and_removed(self):
        # Lenguaje de programación I: the questions sit under "¿Cómo lo vamos a evaluar?".
        from actions.html_transformer import remove_questions_from_html, parse_questions
        html = ("<p>¿Cómo lo vamos a lograr?</p><p>El cuestionario tiene diez preguntas.</p>"
                "<p>¿Cómo lo vamos a evaluar?</p><p>Estas son las preguntas que tiene el cuestionario:</p>"
                "<p>1. ¿Qué es una clase?</p><p>a. Un vector.</p><p>b. Una plantilla de objetos. (respuesta correcta)</p>"
                "<p>2. ¿Qué define a un objeto?</p><p>a. Su nombre.</p><p>b. Sus atributos y métodos. (respuesta correcta)</p>"
                "<p>Información para el equipo de producción de la DEE</p>")
        self.assertEqual(len(parse_questions(html)), 2)
        text = BeautifulSoup(remove_questions_from_html(html, is_quiz=True), "html.parser").get_text(" ")
        self.assertNotIn("respuesta correcta", text)
        self.assertIn("El cuestionario tiene diez preguntas.", text)
        self.assertIn("Información para el equipo", text)

    def test_non_quiz_description_keeps_its_questions(self):
        # A Tarea's "¿…?" lines are instructions for the student.
        from actions.html_transformer import remove_questions_from_html
        html = "<p>Responda en su ensayo:</p><ul><li>¿Qué es la ética?</li><li>¿Por qué importa?</li></ul>"
        self.assertEqual(remove_questions_from_html(html), str(BeautifulSoup(html, "html.parser")))

    def test_questions_merged_into_one_are_listed_as_unread(self):
        # Options with no answer marker at all: the parser merges these questions.
        html = ("<p>Preguntas:</p><ul><li>¿Primera pregunta?</li><li>Uno</li><li>Dos</li></ul>"
                "<ul><li>¿Segunda pregunta?</li><li>Tres</li><li>Cuatro</li></ul>")
        from actions.html_transformer import summarize_quiz
        summary = summarize_quiz(html)
        self.assertLess(summary["encontradas"], summary["esperadas"])
        self.assertEqual(summary["esperadas"], 2)
        self.assertIn("¿Segunda pregunta?", summary["no_leidas"])

    def test_review_reports_missing_questions_and_counts(self):
        course = "_test_quiz_counts"
        course_dir = os.path.join(ROOT, "workspace", course)
        quiz_tools = _row("Herramientas de la plataforma virtual (Marque con una X): Foro___ Tarea___ Cuestionario__X__")
        partial = ("<p>Número de preguntas de la prueba: 10</p>"
                   "<p>1. ¿Cuál es la capital de Colombia?</p><p>=a) Bogotá</p><p>b) Lima</p>")
        html = _doc(_row("UNIDAD DIDÁCTICA 1. Intro"), _row("Resumen", "Texto."), _row("Preguntas orientadoras", "¿Qué?"),
                    _row("ACTIVIDAD 1. Evaluación"), f"<tr><td>{partial}</td></tr>", quiz_tools)
        report = _review_html(html, course)
        act = report["unidades"]["1"]["actividades"]["1"]
        self.assertEqual((act["cantidad_preguntas"], act["preguntas_esperadas"]), (1, 10))
        issue = next(p for p in report["cobertura"]["problemas"] if p["tipo"] == "cuestionario_preguntas_incompletas")
        self.assertIn("1 de 10", issue["titulo"])
        self.assertTrue(issue["bloquea"])


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


class RubricChoiceTests(unittest.TestCase):
    """An activity with two rubric tables: the one under "¿Cómo lo vamos a evaluar?" is the grading rubric."""

    @staticmethod
    def _table(rows):
        body = "".join(f"<tr><td>{c}</td><td>{p}</td></tr>" for c, p in rows)
        return f"<table><tr><td>Criterios de desempeño</td><td>Puntos</td></tr>{body}<tr><td>Total</td><td>5.0</td></tr></table>"

    def test_grading_rubric_wins_over_coevaluation_table(self):
        from core.docx_rubrica_parser import parse_rubricas_from_html, parse_rubrica_from_fragment
        coeval = self._table([("Soluciona el problema", "2.0"), ("Comentado", "1.0"), ("Funcionalidad", "2.0")])
        grading = self._table([("Soluciona", "1.0"), ("Comentado", "0.5"), ("Funcionalidad", "1.0"),
                               ("Evalúa a otro grupo", "1.0"), ("Pregunta", "0.5"), ("Responde", "1.0")])
        body = (f"<p>Fase 2: Coevaluación</p>{coeval}<p>Deben compartir en el foro esta rúbrica.</p>"
                f"<p>¿Cómo lo vamos a evaluar?</p>{grading}")
        html = f"<table><tr><td>ACTIVIDAD 2: Foro</td></tr><tr><td>{body}</td></tr></table>"
        self.assertEqual(len(parse_rubricas_from_html(html)[2]), 6)
        self.assertEqual(len(parse_rubrica_from_fragment(body)), 6)

    def test_single_table_unchanged(self):
        from core.docx_rubrica_parser import parse_rubricas_from_html
        html = f"<table><tr><td>ACTIVIDAD 1</td></tr><tr><td>{self._table([('A', '2.0'), ('B', '3.0')])}</td></tr></table>"
        self.assertEqual(len(parse_rubricas_from_html(html)[1]), 2)


class TemplateVariantTests(unittest.TestCase):
    """Variants seen in the v11 documents (assets/doc-course-test/v11)."""

    def test_activity_heading_with_number_sign(self):
        from core.data_parser import normalize_activity_headings
        self.assertEqual(normalize_activity_headings("<p>ACTIVIDAD #3: Caso</p><p>ACTIVIDAD # 4: Sim</p>"),
                         "<p>ACTIVIDAD 3: Caso</p><p>ACTIVIDAD 4: Sim</p>")
        self.assertIn("Actividad #. Evaluación final", normalize_activity_headings("<p>Actividad #. Evaluación final</p>"))

    def test_tool_mark_with_question_mark_and_foro_de_dudas(self):
        from core.data_parser import detect_activity_type
        head = "HERRAMIENTAS DE LA PLATAFORMA VIRTUAL (MARQUE CON UNA X): "
        self.assertEqual(detect_activity_type(head + "FORO_DE DUDAS __ TAREA__?X__ CUESTIONARIO___"), "Tarea")
        self.assertEqual(detect_activity_type(head + "FORO_DE DUDAS X TAREA___"), "Foro")
        self.assertEqual(detect_activity_type(head + "FORO_DUDAS _?_ TAREA__?__ CUESTIONARIO___"), "Desconocido")

    def test_rubric_with_label_column(self):
        from core.docx_rubrica_parser import criteria_from_table
        table = BeautifulSoup(
            "<table><tr><td>Criterios</td><td>Criterios de desempeño</td><td>Puntos</td></tr>"
            "<tr><td>Criterio 1</td><td>Aplica las pruebas</td><td>1</td></tr>"
            "<tr><td>Criterio 2</td><td>Organiza el producto</td><td>2</td></tr>"
            "<tr><td></td><td>Total</td><td>3</td></tr></table>", "html.parser").table
        criteria = criteria_from_table(table)
        self.assertEqual([c["name"] for c in criteria], ["Aplica las pruebas", "Organiza el producto"])
        self.assertEqual([c["scores"][0] for c in criteria], ["1", "2"])

    def test_rubric_in_the_next_table(self):
        from core.docx_rubrica_parser import parse_rubricas_from_html
        rubric = RubricChoiceTests._table([("A", "2.0"), ("B", "3.0")])
        html = (_doc(_row("ACTIVIDAD 4: Simulación"), _row("¿Qué vamos a lograr? Algo."))
                + "<p></p>" + _doc(_row(f"¿Cómo lo vamos a evaluar? {rubric}"))
                + _doc(_row("ACTIVIDAD 5: Otra"), _row(f"¿Cómo lo vamos a evaluar? {RubricChoiceTests._table([('C', '5.0')])}")))
        rubricas = parse_rubricas_from_html(html)
        self.assertEqual([c["name"] for c in rubricas[4]], ["A", "B"])
        self.assertEqual([c["name"] for c in rubricas[5]], ["C"])

    def test_plan_units_named_without_number(self):
        plan = [_row("Plan de formación del espacio académico"),
                _row("Unidad", "Resultados", "Actividades"),
                _row("Fundamentos", "RA1", "Actividad 1: Video"),
                _row("Actividad 2: Podcast"),
                _row("Procesamiento", "RA2", "Actividad 3: Campo")]
        html = _doc(*plan, _row("UNIDAD DIDÁCTICA 1. Intro"), _row("Resumen", "Texto."))
        report = _review_html(html, "_test_plan_unnamed")
        self.assertEqual(report["cobertura"]["plan"], {"1": [1, 2], "2": [3]})

    def test_final_evaluation_without_number_is_not_glued_to_the_previous_activity(self):
        html = _doc(_row("UNIDAD DIDÁCTICA 1. Intro"), _row("Resumen", "Texto."), _row("Preguntas orientadoras", "¿Qué?"),
                    _row("ACTIVIDAD 1. Ensayo"), *ACTIVITY_BODY,
                    _row("Actividad #. Evaluación final del curso"),
                    _row("1. ¿Capital? a. Bogotá (respuesta) b. Cali"))
        report = _review_html(html, "_test_final_eval")
        issues = {p["tipo"] for p in report["cobertura"]["problemas"]}
        self.assertIn("contenido_sin_asignar", issues)
        self.assertEqual(report["unidades"]["1"]["actividades"]["1"]["tipo"], "Tarea")

    SAMPLE_QUESTIONS = [_row("Ejemplo estructura de pregunta"),
                        _row("1. Enunciado Pregunta 1"), _row("a. Opción 1"), _row("b. Opción 2 (respuesta)"),
                        _row("2. Enunciado Pregunta 2 incluyendo opción ____ para completar"), _row("a. (incluir respuesta)")]
    UNIT = [_row("UNIDAD DIDÁCTICA 1. Intro"), _row("Resumen", "Texto."), _row("Preguntas orientadoras", "¿Qué?")]

    def test_unfilled_template_section_is_a_notice_not_a_blocker(self):
        html = _doc(*self.UNIT, _row("Actividad #. Evaluación final [nombre según plan de curso]"), *self.SAMPLE_QUESTIONS)
        report = _review_html(html, "_test_template_empty")
        issues = {p["tipo"]: p for p in report["cobertura"]["problemas"]}
        self.assertNotIn("contenido_sin_asignar", issues)
        issue = issues["plantilla_sin_diligenciar"]
        self.assertFalse(issue["bloquea"])
        self.assertIn("[nombre según plan de curso]", issue["textos_plantilla"])
        block = next(b for b in report["cobertura"]["bloques"] if b["id"] == issue["bloque"])
        self.assertEqual(block["estado"], "plantilla")

    def test_filled_section_that_kept_a_template_line_is_still_content(self):
        html = _doc(*self.UNIT, _row("Actividad #. Evaluación final [nombre según plan de curso]"),
                    _row("1. ¿Capital de Colombia?"), _row("a. Bogotá (respuesta)"), _row("b. Cali"))
        issues = {p["tipo"] for p in _review_html(html, "_test_template_filled")["cobertura"]["problemas"]}
        self.assertIn("contenido_sin_asignar", issues)
        self.assertNotIn("plantilla_sin_diligenciar", issues)

    def test_activity_with_the_sample_questions_is_flagged(self):
        html = _doc(*self.UNIT, _row("ACTIVIDAD 1. Cuestionario"), _row("¿Qué vamos a lograr? Algo."),
                    _row("Herramientas de la plataforma virtual (Marque con una X): Cuestionario__X__"),
                    *self.SAMPLE_QUESTIONS)
        issues = {p["tipo"]: p for p in _review_html(html, "_test_template_act")["cobertura"]["problemas"]}
        self.assertTrue(issues["texto_de_plantilla"]["bloquea"])
        self.assertIn("Enunciado Pregunta 1", issues["texto_de_plantilla"]["textos_plantilla"])

    def test_template_texts_that_stay_in_filled_documents_are_not_placeholders(self):
        from core.template_placeholders import find_placeholders
        self.assertEqual(find_placeholders("Indique si utilizará alguna____ Otra ¿Cuál?_______ "
                                           "(obligatorio solo en cursos de pregrado) a. Opción correcta"), [])

    def test_numbered_final_evaluation_without_tools_table_is_a_quiz(self):
        html = _doc(_row("UNIDAD DIDÁCTICA 1. Intro"), _row("Resumen", "Texto."), _row("Preguntas orientadoras", "¿Qué?"),
                    _row("ACTIVIDAD 8. Evaluación final"), _row("1. ¿Capital?"), _row("a. Bogotá (respuesta)"), _row("b. Cali"))
        report = _review_html(html, "_test_final_eval_num")
        self.assertEqual(report["unidades"]["1"]["actividades"]["8"]["tipo"], "Cuestionario")


class ActivityTypeChoiceTests(unittest.TestCase):
    """An activity with no X marked: a suggested type, and the type the user chooses in the review."""

    UNMARKED = [_row("UNIDAD DIDÁCTICA 1. Intro"), _row("Resumen", "Texto."), _row("Preguntas orientadoras", "¿Qué?"),
                _row("ACTIVIDAD 4: Gimnasio perceptual"),
                _row("¿Qué vamos a lograr? Grabar una sesión. ¿Cómo lo vamos a lograr? Sube el video a la plataforma."),
                _row("Herramientas de la plataforma virtual (Marque con una X): Foro___ Tarea____ Cuestionario___ Otra ¿Cuál?___")]

    def test_suggestions(self):
        from core.activity_type_hint import suggest_activity_type
        tools = " Herramientas de la plataforma virtual (Marque con una X): Foro___ Tarea___ Cuestionario___ Otra ¿Cuál?___"
        self.assertEqual(suggest_activity_type("Graba un video y súbelo." + tools)["tipo"], "Tarea")
        self.assertEqual(suggest_activity_type("Participarás en un foro de discusión con tus compañeros." + tools)["tipo"], "Foro")
        self.assertEqual(suggest_activity_type("Se debe resolver el siguiente cuestionario de selección múltiple." + tools)["tipo"],
                         "Cuestionario")
        self.assertEqual(suggest_activity_type("1. ¿Capital? a. Bogotá (respuesta) b. Cali. Entrega tu resumen.")["tipo"],
                         "Cuestionario")
        self.assertIsNone(suggest_activity_type("Lee el capítulo 3." + tools), "the tools table alone is no clue")
        self.assertIsNone(suggest_activity_type("Consulta el foro de dudas y lee el capítulo."))

    def _review(self, course_id, choice=None):
        if choice:
            from core.document_corrections import set_block_choice
            cwd = os.getcwd()
            os.chdir(ROOT)
            try:
                set_block_choice(course_id, "tipo_desconocido:a4", choice)
            finally:
                os.chdir(cwd)
        report = _review_html(_doc(*self.UNMARKED), course_id)
        return report, next(p for p in report["cobertura"]["problemas"] if p["tipo"] == "tipo_desconocido")

    def test_unmarked_activity_gets_a_suggestion(self):
        report, issue = self._review("_test_type_hint")
        self.assertEqual(issue["tipo_sugerido"], "Tarea")
        self.assertTrue(issue["razones"])
        self.assertNotIn("resuelto", issue)
        self.assertEqual(report["unidades"]["1"]["actividades"]["4"]["tipo"], "Desconocido")

    def test_chosen_type_settles_the_problem_and_is_what_uploads(self):
        report, issue = self._review("_test_type_choice", {"tipo": "Tarea"})
        self.assertEqual(issue["resuelto"]["tipo"], "Tarea")
        self.assertEqual(report["unidades"]["1"]["actividades"]["4"]["tipo"], "Tarea")
        # now a Tarea, so its missing rubric is reported like any other
        self.assertIn("rubrica_faltante", {p["tipo"] for p in report["cobertura"]["problemas"]})

    MARKED_QUIZ = [_row("UNIDAD DIDÁCTICA 1. Intro"), _row("Resumen", "Texto."), _row("Preguntas orientadoras", "¿Qué?"),
                   _row("ACTIVIDAD 4: Taller de casos"),
                   _row("¿Qué vamos a lograr? Analizar dos casos. ¿Cómo lo vamos a lograr? Entregue el análisis completo."),
                   _row("Herramientas de la plataforma virtual (Marque con una X): Foro___ Tarea____ Cuestionario_X__ Otra ¿Cuál?___")]

    def _review_doc(self, rows, course_id, issue_id=None, choice=None):
        if choice:
            from core.document_corrections import set_block_choice
            cwd = os.getcwd()
            os.chdir(ROOT)
            try:
                set_block_choice(course_id, issue_id, choice)
            finally:
                os.chdir(cwd)
        report = _review_html(_doc(*rows), course_id)
        return report, {p["tipo"]: p for p in report["cobertura"]["problemas"]}

    def test_marked_type_that_contradicts_the_content_is_a_notice(self):
        report, issues = self._review_doc(self.MARKED_QUIZ, "_test_type_mismatch")
        issue = issues["tipo_no_coincide"]
        self.assertFalse(issue["bloquea"])
        self.assertEqual((issue["tipo_documento"], issue["tipo_sugerido"]), ("Cuestionario", "Tarea"))
        self.assertEqual(report["unidades"]["1"]["actividades"]["4"]["tipo"], "Cuestionario", "the X wins by default")

    def test_choosing_the_suggested_type_over_the_x(self):
        report, issues = self._review_doc(self.MARKED_QUIZ, "_test_type_mismatch_choice", "tipo_no_coincide:a4", {"tipo": "Tarea"})
        self.assertEqual(issues["tipo_no_coincide"]["resuelto"]["tipo"], "Tarea")
        self.assertEqual(report["unidades"]["1"]["actividades"]["4"]["tipo"], "Tarea")
        self.assertNotIn("cuestionario_sin_preguntas", issues)

    def test_matching_x_has_no_notice(self):
        rows = self.MARKED_QUIZ[:-1] + [_row("Herramientas de la plataforma virtual (Marque con una X): "
                                             "Foro___ Tarea__X__ Cuestionario___ Otra ¿Cuál?___")]
        _, issues = self._review_doc(rows, "_test_type_match")
        self.assertNotIn("tipo_no_coincide", issues)

    def test_type_choice_only_accepts_a_type(self):
        from core.document_corrections import set_block_choice
        with self.assertRaises(ValueError):
            set_block_choice("_test_type_bad", "tipo_desconocido:a4", {"agregar_a": 2})

    def test_moodle_structure_uses_the_split_types(self):
        from actions.structure_actions import apply_split_activity_types
        sections = [{"unit_number": 2, "section_name": "UNIDAD 1", "activities": [
            {"name": "ACTIVIDAD 7: Quiz", "type": "Tarea"},
            {"name": "ACTIVIDAD 7. Repetida", "type": "Cuestionario"},
            {"name": "ACTIVIDAD 8. Sin X", "type": None},
            {"name": "Actividad #. Evaluación final [nombre según plan de curso]", "type": "Cuestionario"}]}]
        apply_split_activity_types(sections, {"actividad7.html": "Cuestionario", "actividad7_1.html": "Tarea",
                                              "actividad8.html": "Foro"})
        self.assertEqual([(a["name"][:13], a["type"]) for a in sections[0]["activities"]],
                         [("ACTIVIDAD 7: ", "Cuestionario"), ("ACTIVIDAD 7. ", "Tarea"), ("ACTIVIDAD 8. ", "Foro")])


class WordNumberingTests(unittest.TestCase):
    """Questions numbered with Word's automatic numbering (core/docx_numbering.py)."""

    W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

    def _docx(self, paragraphs):
        """paragraphs: (text, numId or None, ilvl). numIds 1 = decimal "%1.", 2 and 3 = upperLetter "%1."."""
        import io
        import zipfile

        def para(text, num, lvl):
            num_pr = f'<w:numPr><w:ilvl w:val="{lvl}"/><w:numId w:val="{num}"/></w:numPr>' if num else ""
            return f'<w:p><w:pPr>{num_pr}</w:pPr><w:r><w:t xml:space="preserve">{text}</w:t></w:r></w:p>'

        body = "".join(para(*p) for p in paragraphs)
        document = f'<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="{self.W}"><w:body>{body}</w:body></w:document>'
        abstracts = "".join(
            f'<w:abstractNum w:abstractNumId="{a}"><w:lvl w:ilvl="0"><w:start w:val="1"/>'
            f'<w:numFmt w:val="{fmt}"/><w:lvlText w:val="%1."/></w:lvl></w:abstractNum>'
            for a, fmt in ((10, "decimal"), (20, "upperLetter"), (30, "upperLetter")))
        nums = '<w:num w:numId="1"><w:abstractNumId w:val="10"/></w:num>' \
               '<w:num w:numId="2"><w:abstractNumId w:val="20"/></w:num>' \
               '<w:num w:numId="3"><w:abstractNumId w:val="30"/></w:num>'
        numbering = f'<?xml version="1.0" encoding="UTF-8"?><w:numbering xmlns:w="{self.W}">{abstracts}{nums}</w:numbering>'
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w") as z:
            z.writestr("word/document.xml", document)
            z.writestr("word/numbering.xml", numbering)
        return out.getvalue()

    def _texts(self, docx_bytes):
        import io
        import zipfile
        from lxml import etree
        root = etree.fromstring(zipfile.ZipFile(io.BytesIO(docx_bytes)).read("word/document.xml"))
        return ["".join(p.itertext()) for p in root.iter(f"{{{self.W}}}p")]

    def test_flattened_quiz_lists_get_their_numbers_as_text(self):
        from core.docx_numbering import materialize_quiz_numbering
        docx = self._docx([("ACTIVIDAD 8. Evaluación final", None, 0),
                           ("¿Capital?", 1, 0), ("Bogotá (respuesta)", 2, 0), ("Cali", 2, 0),
                           ("¿Río?", 1, 0), ("Magdalena (respuesta)", 3, 0), ("Cauca", 3, 0)])
        self.assertEqual(self._texts(materialize_quiz_numbering(docx))[1:],
                         ["1. ¿Capital?", "A. Bogotá (respuesta)", "B. Cali",
                          "2. ¿Río?", "A. Magdalena (respuesta)", "B. Cauca"])

    def test_lists_outside_quizzes_stay_word_lists(self):
        from core.docx_numbering import materialize_quiz_numbering
        docx = self._docx([("ACTIVIDAD 2. Ensayo", None, 0), ("Lee el texto", 1, 0), ("Escribe", 2, 0)])
        self.assertEqual(materialize_quiz_numbering(docx), docx)

    def test_quiz_instructions_without_answers_stay_word_lists(self):
        from core.docx_numbering import materialize_quiz_numbering
        docx = self._docx([("ACTIVIDAD 8. Evaluación final", None, 0),
                           ("Mira el video", 1, 0), ("Lee la guía", 2, 0),
                           ("1. ¿Capital?", None, 0), ("a. Bogotá (respuesta)", None, 0)])
        self.assertEqual(materialize_quiz_numbering(docx), docx)

    def test_question_number_is_not_part_of_the_moodle_question_text(self):
        from actions.html_transformer import parse_questions, question_handler
        q = parse_questions("<p>1. ¿Capital?</p><p>A. Bogotá (respuesta)</p><p>B. Cali</p>")[0]
        self.assertIn("<![CDATA[<p>¿Capital?</p>]]>", question_handler(q, 1)[0].to_moodle_xml())


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
