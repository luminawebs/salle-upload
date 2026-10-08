"""
Tests for the AI quiz-question shadow mode (core/ai_question_shadow.py).
No real AI call: a fake client returns canned answers.

    python -m unittest tests.test_ai_question_shadow -v
"""
import json
import logging
import os
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from core import ai_question_shadow as shadow  # noqa: E402

QUIZ = """
<p>HERRAMIENTAS DE LA PLATAFORMA VIRTUAL: Cuestionario X</p>
<p>¿Cómo lo vamos a lograr?</p>
<ol>
<li>¿Cuál es la capital de Colombia?</li>
<li>Medellín</li>
<li>Bogotá</li>
<li>Cali</li>
</ol>
<p>Respuesta correcta: Bogotá</p>
<p>2. ¿Qué río atraviesa Bogotá?</p>
<p>a) El río Bogotá</p>
<p>b) El Amazonas</p>
<p>Respuesta correcta: a) El río Bogotá</p>
<p>3. ¿Cuántos departamentos tiene Colombia?</p>
<p>a) 32</p>
<p>b) 12</p>
<p>Respuesta correcta: a) 32</p>
"""


def q(stem, options, origin="ninguna", evidence=""):
    return {"enunciado": stem, "tipo": "opcion_multiple",
            "opciones": [{"texto": t, "correcta": c} for t, c in options],
            "origen_respuesta": origin, "evidencia": evidence}


class FakeResponse:
    def __init__(self, payload, finish="STOP"):
        self.text = json.dumps(payload)
        self.usage_metadata = mock.Mock(prompt_token_count=1000, candidates_token_count=200,
                                        total_token_count=1200, cached_content_token_count=0)
        self.candidates = [mock.Mock(finish_reason=finish)]


class FakeClient:
    """Answers every call with `payload`, or with each payload of a list in turn."""
    def __init__(self, payload, finish="STOP"):
        self.calls = 0
        self.prompts = []
        self.models = self
        self._payloads = payload if isinstance(payload, list) else None
        self._payload, self._finish = payload, finish

    def generate_content(self, **kwargs):
        payload = self._payloads[self.calls] if self._payloads else self._payload
        self.calls += 1
        self.last_prompt = kwargs["contents"]
        self.prompts.append(kwargs["contents"])
        return FakeResponse(payload, self._finish)


class VerifyTests(unittest.TestCase):
    def test_verbatim_text_passes(self):
        [r] = shadow.verify([q("¿Cuál es la capital de Colombia?", [("Medellín", False), ("Bogotá", True)],
                               "linea_respuesta", "Respuesta correcta: Bogotá")], QUIZ)
        self.assertTrue(r["verificacion"]["valida"])

    def test_leading_list_marker_is_tolerated(self):
        [r] = shadow.verify([q("1. ¿Cuál es la capital de Colombia?", [("a) Medellín", False)])], QUIZ)
        self.assertTrue(r["verificacion"]["valida"])

    def test_paraphrased_stem_is_rejected(self):
        [r] = shadow.verify([q("¿Cuál es la ciudad capital de Colombia?", [("Bogotá", False)])], QUIZ)
        self.assertFalse(r["verificacion"]["enunciado"])
        self.assertFalse(r["verificacion"]["valida"])

    def test_invented_option_is_rejected(self):
        [r] = shadow.verify([q("¿Cuál es la capital de Colombia?", [("Barranquilla", False)])], QUIZ)
        self.assertEqual(r["verificacion"]["opciones_no_encontradas"], ["Barranquilla"])

    def test_answer_needs_real_evidence(self):
        [r] = shadow.verify([q("¿Cuál es la capital de Colombia?", [("Bogotá", True)],
                               "linea_respuesta", "Respuesta correcta: Cali")], QUIZ)
        self.assertFalse(r["verificacion"]["respuesta"])

    def test_answer_without_origin_is_a_guess(self):
        [r] = shadow.verify([q("¿Cuál es la capital de Colombia?", [("Bogotá", True)], "ninguna")], QUIZ)
        self.assertFalse(r["verificacion"]["valida"])


class CompareTests(unittest.TestCase):
    def test_pairs_new_and_completed(self):
        parsed = [
            {"enunciado": "¿Cuál es la capital de Colombia?", "tipo": "multichoice",
             "opciones": [{"texto": "Medellín", "correcta": False}, {"texto": "Bogotá", "correcta": False}]},
            {"enunciado": "Texto que no es pregunta", "tipo": "multichoice", "opciones": []},
        ]
        ai = shadow.verify([
            q("1. ¿Cuál es la capital de Colombia?", [("Medellín", False), ("Bogotá", True)],
              "linea_respuesta", "Respuesta correcta: Bogotá"),
            q("¿Qué río atraviesa Bogotá?", [("El río Bogotá", True), ("El Amazonas", False)],
              "linea_respuesta", "Respuesta correcta: a) El río Bogotá"),
        ], QUIZ)
        comparison = shadow.compare(parsed, ai)
        self.assertEqual(comparison["emparejadas"][0]["respuesta"], "ia_completa")
        self.assertEqual(comparison["solo_ia"], [1])
        self.assertEqual(comparison["solo_parser"], [1])
        m = shadow.metrics(parsed, ai, comparison, {"esperadas": 3})
        self.assertEqual((m["nuevas_validas"], m["respuestas_completadas"], m["solo_parser"]), (1, 1, 1))
        self.assertFalse(m["cierra_brecha"])  # 1 confirmed + 1 new < 3 expected


class RunShadowTests(unittest.TestCase):
    def setUp(self):
        logging.disable(logging.CRITICAL)
        self.tmp = tempfile.TemporaryDirectory()
        patches = [
            mock.patch.object(shadow, "SHADOW_DIR", self.tmp.name),
            mock.patch("core.ai_budget_guard.LEDGER_PATH", os.path.join(self.tmp.name, "ledger.json")),
            # A quiz with a gap: the parser "reads" 1 of 3 questions.
            mock.patch.object(shadow, "find_gaps", return_value=(
                ["faltan_preguntas"],
                [{"enunciado": "¿Cuál es la capital de Colombia?", "tipo": "multichoice",
                  "opciones": [{"texto": "Bogotá", "correcta": True}]}],
                {"encontradas": 1, "declaradas": None, "esperadas": 3})),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(logging.disable, logging.NOTSET)

    def payload(self):
        return {"preguntas": [
            q("¿Cuál es la capital de Colombia?", [("Bogotá", True)], "linea_respuesta", "Respuesta correcta: Bogotá"),
            q("¿Qué río atraviesa Bogotá?", [("El río Bogotá", True)], "linea_respuesta", "Respuesta correcta: a) El río Bogotá"),
            q("¿Cuántos departamentos tiene Colombia?", [("32", True)], "linea_respuesta", "Respuesta correcta: a) 32"),
        ]}

    def test_records_and_closes_gap(self):
        client = FakeClient(self.payload())
        record = shadow.run_shadow("c1", "a1", QUIZ, "actividad1.html", client=client)
        self.assertEqual(client.calls, 1)
        self.assertNotIn("style=", client.last_prompt)
        self.assertTrue(os.path.exists(shadow.record_path("c1", "a1", QUIZ)))
        self.assertEqual(record["metricas"]["nuevas_validas"], 2)
        self.assertTrue(record["metricas"]["cierra_brecha"])

    def test_same_text_is_not_sent_twice(self):
        client = FakeClient(self.payload())
        shadow.run_shadow("c1", "a1", QUIZ, client=client)
        self.assertIsNone(shadow.run_shadow("c1", "a1", QUIZ, client=client))
        self.assertEqual(client.calls, 1)

    def test_failed_call_stops_and_is_not_saved(self):
        client = FakeClient(self.payload(), finish="FinishReason.MAX_TOKENS")
        record = shadow.run_shadow("c1", "a1", QUIZ, client=client)
        self.assertIn("error", record)
        self.assertEqual(client.calls, 1)  # no escalation after a failed call
        self.assertFalse(os.path.exists(shadow.record_path("c1", "a1", QUIZ)))  # retried next time

    def test_no_gap_no_call(self):
        client = FakeClient(self.payload())
        with mock.patch.object(shadow, "find_gaps", return_value=([], [], {"encontradas": 3, "declaradas": None, "esperadas": 3})):
            self.assertIsNone(shadow.run_shadow("c1", "a2", QUIZ, client=client))
        self.assertEqual(client.calls, 0)


class EscalationTests(unittest.TestCase):
    """Question → block → activity: the AI sees the smallest part that settles the gap."""

    def setUp(self):
        logging.disable(logging.CRITICAL)
        self.tmp = tempfile.TemporaryDirectory()
        parsed = [
            {"enunciado": "1. ¿Cuál es la capital de Colombia?", "tipo": "multichoice",
             "opciones": [{"texto": "Medellín", "correcta": False}, {"texto": "Bogotá", "correcta": True}]},
            {"enunciado": "2. ¿Qué río atraviesa Bogotá?", "tipo": "multichoice",
             "opciones": [{"texto": "a) El río Bogotá", "correcta": False}, {"texto": "b) El Amazonas", "correcta": False}]},
            {"enunciado": "3. ¿Cuántos departamentos tiene Colombia?", "tipo": "multichoice",
             "opciones": [{"texto": "a) 32", "correcta": True}, {"texto": "b) 12", "correcta": False}]},
        ]
        patches = [
            mock.patch.object(shadow, "SHADOW_DIR", self.tmp.name),
            mock.patch("core.ai_budget_guard.LEDGER_PATH", os.path.join(self.tmp.name, "ledger.json")),
            # Question 2 has no correct answer marked; nothing is missing.
            mock.patch.object(shadow, "find_gaps", return_value=(
                ["sin_correcta"], parsed, {"encontradas": 3, "declaradas": None, "esperadas": 3})),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(logging.disable, logging.NOTSET)

    RIVER = q("¿Qué río atraviesa Bogotá?", [("El río Bogotá", True), ("El Amazonas", False)],
              "linea_respuesta", "Respuesta correcta: a) El río Bogotá")

    def test_settled_with_just_that_question(self):
        client = FakeClient({"preguntas": [self.RIVER]})
        record = shadow.run_shadow("c1", "a1", QUIZ, client=client)
        self.assertEqual(client.calls, 1)
        self.assertIn("¿Qué río atraviesa Bogotá?", client.last_prompt)
        self.assertNotIn("capital de Colombia", client.last_prompt)  # only the question in doubt
        self.assertEqual((record["nivel_final"], record["resuelta"]), ("pregunta", True))
        self.assertEqual(record["metricas"]["respuestas_completadas"], 1)

    def test_unclear_question_moves_up_to_the_block(self):
        unanswered = q("¿Qué río atraviesa Bogotá?", [("El río Bogotá", False), ("El Amazonas", False)])
        block = {"preguntas": [
            q("¿Cuál es la capital de Colombia?", [("Medellín", False), ("Bogotá", True)],
              "linea_respuesta", "Respuesta correcta: Bogotá"),
            self.RIVER,
            q("¿Cuántos departamentos tiene Colombia?", [("32", True), ("12", False)],
              "linea_respuesta", "Respuesta correcta: a) 32"),
        ]}
        client = FakeClient([{"preguntas": [unanswered]}, block])
        record = shadow.run_shadow("c1", "a1", QUIZ, client=client)
        self.assertEqual(client.calls, 2)
        self.assertEqual([a["nivel"] for a in record["intentos"]], ["pregunta", "bloque"])
        self.assertIn("capital de Colombia", client.prompts[1])
        self.assertNotIn("HERRAMIENTAS", client.prompts[1])  # the block, not the whole activity
        self.assertEqual((record["nivel_final"], record["resuelta"]), ("bloque", True))

    def test_prompt_lists_the_catalog_types(self):
        prompt = shadow.build_prompt("bloque", QUIZ)
        for ai_type in ("opcion_multiple", "verdadero_falso", "completar", "arrastrar_soltar", "abierta", "otra"):
            self.assertIn(f'"{ai_type}"', prompt)


class ReadyTests(unittest.TestCase):
    def test_refuses_without_spending_cap(self):
        with mock.patch.multiple(shadow.Config, AI_QUESTIONS_SHADOW=True, AI_BUDGET_USD=0,
                                 AI_COST_PER_1M_INPUT_TOKENS_USD=1.5, AI_COST_PER_1M_OUTPUT_TOKENS_USD=9):
            ok, reason = shadow.shadow_ready()
        self.assertFalse(ok)
        self.assertIn("AI_BUDGET_USD", reason)

    def test_off_by_default_schedules_nothing(self):
        with mock.patch.object(shadow.Config, "AI_QUESTIONS_SHADOW", False), \
                mock.patch.object(shadow.threading, "Thread") as thread:
            shadow.schedule_shadow("c1", [("a1", "x", QUIZ)])
        thread.assert_not_called()


if __name__ == "__main__":
    unittest.main()
