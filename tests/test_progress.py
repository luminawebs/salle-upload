"""
The two audiences of a run's log (core/progress.py): the web terminal gets
step markers, results, warnings, errors and the summary; the run file gets
every line at DEBUG level.

    python -m unittest tests.test_progress -v
"""
import io
import logging
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import progress  # noqa: E402


class ProgressLogTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = logging.getLogger()
        self.saved = (self.root.level, list(self.root.handlers))
        self.addCleanup(self.restore)
        p = mock.patch.object(progress, "LOGS_DIR", self.tmp.name)
        p.start()
        self.addCleanup(p.stop)
        self.screen = io.StringIO()
        progress.configure_root()
        self.root.handlers[0].setStream(self.screen)
        self.file = progress.file_handler("c1")
        self.root.addHandler(self.file)

    def restore(self):
        for h in list(self.root.handlers):
            self.root.removeHandler(h)
            if h is getattr(self, "file", None):
                h.close()
        level, handlers = self.saved
        self.root.setLevel(level)
        for h in handlers:
            self.root.addHandler(h)

    def run_course(self):
        progress.begin_course(["documento", "estructura", "rubricas"])
        progress.step("estructura")
        logging.getLogger("actions.x").info("Step 4a: Opening file picker...")
        logging.getLogger("actions.x").debug("Links found on page (3999)")
        progress.ok("Creada: ACTIVIDAD 1")
        logging.getLogger("actions.x").warning("Could not find 'Preguntas' tab")
        logging.getLogger("actions.x").error("Could not extract edit URL")
        logging.getLogger("main").info("[RESUMEN] Curso c1 | estado=ok")
        self.file.flush()

    def test_terminal_shows_only_what_the_user_needs(self):
        self.run_course()
        lines = self.screen.getvalue().splitlines()
        self.assertEqual(lines, [
            "[PASO 2/3 F1] Creando secciones y actividades",
            "✓ Creada: ACTIVIDAD 1",
            "Aviso: Could not find 'Preguntas' tab",
            "Error: Could not extract edit URL",
            "[RESUMEN] Curso c1 | estado=ok",
        ])

    def test_file_keeps_every_line(self):
        self.run_course()
        with open(progress.latest_run_log("c1"), encoding="utf-8") as f:
            text = f.read()
        for expected in ("Step 4a: Opening file picker", "Links found on page (3999)", "Creada: ACTIVIDAD 1", "Could not extract edit URL"):
            self.assertIn(expected, text)

    def test_noisy_libraries_stay_out(self):
        logging.getLogger("selenium.webdriver.remote.remote_connection").debug("POST http://localhost/session")
        self.file.flush()
        with open(progress.latest_run_log("c1"), encoding="utf-8") as f:
            self.assertNotIn("POST http://localhost/session", f.read())

    def test_step_times_for_the_summary(self):
        progress.begin_course(["documento", "estructura"])
        progress.step("documento")
        progress.step("estructura")
        lines = progress.summary_lines()
        self.assertEqual([line.split(":")[0] for line in lines], ["Leyendo el documento", "Creando secciones y actividades"])

    def test_page_time_split_server_vs_files(self):
        progress.begin_course(["documento"])
        progress.record_page_load("https://m/course/view.php", 10.0,
                                  {"servidor": 7.0, "pagina": 0.5, "archivos": 2.5, "recursos": 40, "desde_cache": 0, "kb": 2048})
        progress.record_page_load("https://m/course/edit.php", 20.0,
                                  {"servidor": 17.0, "pagina": 0.5, "archivos": 2.5, "recursos": 30, "desde_cache": 5, "kb": 1024})
        progress.record_page_load("https://m/mod/x", 3.0, None)  # breakdown not readable: still counted as a load
        lines = progress.summary_lines()
        self.assertIn("Cargas de página: 3", lines[-2])
        self.assertEqual(lines[-1], "Tiempo de las páginas: 80 % servidor de Moodle · 3 % descarga de la página · "
                                    "17 % archivos y scripts (70 archivos, 5 desde caché, 3.0 MB descargados)")

    def test_no_split_without_breakdowns(self):
        self.assertIsNone(progress.page_time_split([]))


if __name__ == "__main__":
    unittest.main()
