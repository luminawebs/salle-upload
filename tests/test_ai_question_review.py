"""
Tests for the review of the AI's quiz proposals (core/ai_question_review.py):
items built from a verified AI reading, accept/discard decisions, and what an
accepted proposal changes in the upload (questions and quiz description).
No real AI call: a fake client answers.

    python -m unittest tests.test_ai_question_review -v
"""
import logging
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import ai_question_review as review  # noqa: E402
from core import ai_question_shadow as shadow  # noqa: E402
from tests.test_ai_question_shadow import FakeClient, q  # noqa: E402

# Question 2 has no answer marked, and the parser swallows question 3 ("Una
# pila…", no number, no "¿") as extra options of question 2.
QUIZ = ("<p>HERRAMIENTAS DE LA PLATAFORMA VIRTUAL: Cuestionario X</p>"
        "<p>1. ¿Cuál es la capital de Colombia?</p><p>a) Medellín</p><p>b) Bogotá (respuesta correcta)</p>"
        "<p>2. ¿Qué río atraviesa Bogotá?</p><p>a) El río Bogotá</p><p>b) El Amazonas</p>"
        "<p>Una pila sigue el principio:</p><p>LIFO</p><p>FIFO</p><p>Respuesta: LIFO</p>"
        "<p>Clave de respuestas: 2-a</p>"
        "<p>Información para el equipo de producción</p>")
FILE = "actividad3.html"

AI_ANSWER = {"preguntas": [
    q("¿Qué río atraviesa Bogotá?", [("El río Bogotá", True), ("El Amazonas", False)], "clave", "Clave de respuestas: 2-a"),
    q("Una pila sigue el principio:", [("LIFO", True), ("FIFO", False)], "linea_respuesta", "Respuesta: LIFO"),
]}


class ReviewTests(unittest.TestCase):
    def setUp(self):
        logging.disable(logging.CRITICAL)
        self.tmp = tempfile.TemporaryDirectory()
        for p in (mock.patch.object(shadow, "SHADOW_DIR", os.path.join(self.tmp.name, "ai_shadow")),
                  mock.patch.object(review, "PROJECT_ROOT", self.tmp.name),
                  mock.patch("core.ai_budget_guard.LEDGER_PATH", os.path.join(self.tmp.name, "ledger.json"))):
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(logging.disable, logging.NOTSET)
        self.client = FakeClient(AI_ANSWER)
        shadow.run_shadow("c1", review.activity_key(FILE), QUIZ, FILE, client=self.client)
        self.proposal = review.build_proposal("c1", FILE, QUIZ)

    def items(self, kind):
        return [it for it in self.proposal["items"] if it["tipo"] == kind]

    def test_proposals_come_from_the_question_in_doubt(self):
        self.assertEqual(self.client.calls, 1)
        self.assertEqual(self.proposal["nivel"], "pregunta")
        self.assertEqual(len(self.items("respuesta")), 1)
        self.assertEqual(len(self.items("nueva")), 1)
        self.assertFalse(self.proposal["completa"])

    def test_nothing_changes_until_accepted(self):
        self.assertIsNone(review.final_questions("c1", FILE, QUIZ))
        review.set_decisions("c1", FILE, QUIZ, {it["id"]: "descartar" for it in self.proposal["items"]})
        self.assertIsNone(review.final_questions("c1", FILE, QUIZ))
        self.assertTrue(review.build_proposal("c1", FILE, QUIZ)["completa"])

    def test_accepted_proposals_change_the_upload(self):
        review.set_decisions("c1", FILE, QUIZ, {it["id"]: "aceptar" for it in self.proposal["items"]})
        final = review.final_questions("c1", FILE, QUIZ)
        self.assertEqual(len(final), 3)
        river = final[1]
        # The AI's version replaces the parser's, whose options included question 3.
        self.assertEqual([o["is_correct"] for o in river["options"]], [True, False])
        self.assertEqual(final[2]["origen"], "ia")
        from actions.html_transformer import extract_questions_from_html_to_moodle_xml
        path = os.path.join(self.tmp.name, "quiz.xml")
        self.assertEqual(extract_questions_from_html_to_moodle_xml(QUIZ, path, questions=final), 3)
        with open(path, encoding="utf-8") as f:
            self.assertIn("LIFO", f.read())

    def test_answer_marked_on_the_parsers_own_options_when_they_match(self):
        parsed = {"stem_html": ["<p>¿Río?</p>"], "q_type": "multichoice", "feedback": {"general": ["fb"], "correct": [], "incorrect": []},
                  "options": [{"html": "<p>a) El río Bogotá</p>", "is_correct": False}, {"html": "<p>b) El Amazonas</p>", "is_correct": False}]}
        result = review._apply_answer(parsed, AI_ANSWER["preguntas"][0])
        self.assertEqual([o["html"] for o in result["options"]], [o["html"] for o in parsed["options"]])
        self.assertEqual([o["is_correct"] for o in result["options"]], [True, False])
        self.assertEqual(result["feedback"]["general"], ["fb"])

    def test_found_questions_leave_the_description_unless_discarded(self):
        description = "<p>Instrucciones</p><p>Una pila sigue el principio:</p><p>LIFO</p><p>FIFO</p><p>Respuesta: LIFO</p>"
        stripped = review.strip_accepted_questions("c1", FILE, QUIZ, description)
        self.assertEqual(stripped, "<p>Instrucciones</p>")
        new = self.items("nueva")[0]
        review.set_decisions("c1", FILE, QUIZ, {new["id"]: "descartar"})
        self.assertIn("LIFO", review.strip_accepted_questions("c1", FILE, QUIZ, description))

    def test_nested_list_questions_and_their_explanation_leave_the_description(self):
        # Lógica II layout: "(Opción múltiple) …" with its options as a nested
        # list, then a justification paragraph that gives the answer away.
        description = ("<p>Instrucciones</p><ol><li>(Opción múltiple) Una <strong>pila</strong> sigue el principio:"
                       "<ol><li>LIFO</li><li>FIFO</li></ol></li></ol>"
                       "<p><em>Justificación: el último en entrar es el primero en salir.</em></p><p>Fin</p>")
        stripped = review.strip_accepted_questions("c1", FILE, QUIZ, description)
        self.assertNotIn("pila", stripped)
        self.assertNotIn("Justificación", stripped)
        self.assertIn("Instrucciones", stripped)
        self.assertIn("Fin", stripped)

    def test_decisions_belong_to_this_version_of_the_activity(self):
        review.set_decisions("c1", FILE, QUIZ, {it["id"]: "aceptar" for it in self.proposal["items"]})
        changed = QUIZ.replace("Medellín", "Cali")
        self.assertEqual(review.get_decisions("c1", FILE, changed), {})
        self.assertIsNone(review.final_questions("c1", FILE, changed))


if __name__ == "__main__":
    unittest.main()
