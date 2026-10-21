"""
Keeps the "Formatos de preguntas" guide true: every example in
core/question_types/catalog.py must still be read by the parser as its type,
with the documented number of correct answers, and export to the documented
Moodle question type. If the parser changes, this fails until the example (or
the parser) is fixed — so the guide in the UI never shows a format that no
longer works.

    python -m unittest tests.test_question_formats -v
"""
import logging
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.question_types.catalog import QUESTION_FORMATS, render_catalog  # noqa: E402


class QuestionFormatTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        logging.disable(logging.CRITICAL)
        cls.rendered = render_catalog()["formatos"]

    @classmethod
    def tearDownClass(cls):
        logging.disable(logging.NOTSET)

    def test_every_example_reads_as_its_type(self):
        for fmt in self.rendered:
            for variant in fmt["variantes"]:
                with self.subTest(formato=fmt["id"], variante=variant["titulo"]):
                    questions = variant["preguntas"]
                    self.assertEqual(len(questions), 1, "the example must be exactly one question")
                    self.assertEqual(questions[0]["tipo"], variant["tipo"])
                    self.assertEqual(questions[0]["correctas"], variant["correctas"])
                    self.assertIn(f'<question type="{fmt["moodle"]}">', variant["xml"])

    def test_every_format_has_the_course_template_first(self):
        for fmt in QUESTION_FORMATS:
            self.assertEqual(fmt["variantes"][0]["titulo"], "Plantilla recomendada", fmt["id"])


class QuestionUrlTests(unittest.TestCase):
    """URLs in questions become "(Disponible aquí)" links, as in activity descriptions."""

    def setUp(self):
        logging.disable(logging.CRITICAL)
        self.addCleanup(logging.disable, logging.NOTSET)

    def test_url_in_question_becomes_disponible_aqui(self):
        from actions.html_transformer import parse_questions, question_handler
        html = ("<p>1. ¿A cuál elemento corresponde la imagen?</p>"
                "<p>Imagen tomada de: https://example.org/polymorphism.jpg</p>"
                "<p>a) Polimorfismo (respuesta correcta)</p><p>b) Herencia</p>")
        xml = question_handler(parse_questions(html)[0], 1)[0].to_moodle_xml()
        self.assertIn('href="https://example.org/polymorphism.jpg"', xml)
        self.assertIn(">(Disponible aquí)</a>", xml)
        self.assertIn("color: rgb(0, 0, 238)", xml)
        self.assertNotIn(">https://example.org", xml)

    def test_word_bookmark_is_not_a_link(self):
        from actions.html_transformer import format_urls_in_html
        out = format_urls_in_html('<p><a id="_Hlk239664928"></a>Pregunta 1</p>')
        self.assertNotIn("Disponible", out)

    def test_question_without_url_is_untouched(self):
        from actions.html_transformer import parse_questions, question_handler
        q = parse_questions("<p>1. ¿Capital?</p><p>a) Bogotá (respuesta correcta)</p><p>b) Cali</p>")[0]
        before = list(q["stem_html"])
        question_handler(q, 1)
        self.assertEqual(q["stem_html"], before)


if __name__ == "__main__":
    unittest.main()
