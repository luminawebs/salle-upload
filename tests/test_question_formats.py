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


if __name__ == "__main__":
    unittest.main()
