"""
'Complementos multimedia' off once for the whole course
(actions/docx_upload_actions.disable_multimedia_filter_for_course), verified
by reloading; when it can't be done, per activity and per Lecturas
complementarias page instead. Uses a fake driver, no Moodle needed.

    python -m unittest tests.test_multimedia_filter -v
"""
import os
import sys
import tempfile
import unittest
from unittest import mock

from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from actions import docx_upload_actions as docx  # noqa: E402
from actions import materiales_estudio_actions as materiales  # noqa: E402


class FakeElement:
    def __init__(self, value="", enabled=True, href="", text=""):
        self.value, self.enabled, self.href, self.text = value, enabled, href, text
        self.stale = False

    def is_enabled(self):
        if self.stale:
            raise StaleElementReferenceException("stale")
        return self.enabled

    def is_displayed(self):
        return True

    def get_attribute(self, name):
        return {"value": self.value, "href": self.href}.get(name, "")


class FiltersDriver:
    """The course page and its 'Filtros' page; the select's saved value lives in `saved`."""

    def __init__(self, context_id="123", has_row=True, locked=False, has_off_option=True, save_sticks=True, links=()):
        self.context_id, self.has_row, self.locked = context_id, has_row, locked
        self.has_off_option, self.save_sticks, self.links = has_off_option, save_sticks, list(links)
        self.saved, self.pending = "0", None
        self.urls = []
        self._load()

    def _load(self):
        self.select = FakeElement(self.saved, enabled=not self.locked)
        self.save_btn = FakeElement()

    def get(self, url):
        self.urls.append(url)
        self._load()

    def execute_script(self, script, *args):
        if script == docx._CONTEXT_ID_JS:
            return self.context_id
        if script == docx._SELECT_OFF_JS:
            if not self.has_off_option:
                return False
            self.pending = "-1"
            return True
        if script == docx._CLICK_JS:
            args[0].stale = True
            if self.save_sticks and self.pending is not None:
                self.saved = self.pending
            return None
        raise AssertionError(f"unexpected script: {script[:40]}")

    def find_element(self, by, selector):
        if selector == docx._MEDIA_SELECT_CSS:
            if not self.has_row:
                raise NoSuchElementException(selector)
            return self.select
        if selector == docx._FILTER_SAVE_XPATH:
            return self.save_btn
        raise NoSuchElementException(selector)

    def find_elements(self, by, selector):
        return [FakeElement(href=h) for h in self.links]


class CourseLevelTest(unittest.TestCase):
    def setUp(self):
        patches = [
            mock.patch.object(docx, "navigate_to_course", return_value=True),
            mock.patch.object(docx.time, "sleep"),
            mock.patch.object(docx.Config, "MOODLE_URL", "https://moodle.test/", create=True),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.ok = mock.patch.object(docx.progress, "ok").start()
        self.addCleanup(mock.patch.stopall)

    def run_it(self, driver):
        with self.assertLogs(docx.logger, level="INFO") as logs:
            result = docx.disable_multimedia_filter_for_course(driver, 71326, 0.1)
        return result, "\n".join(logs.output)

    def test_saved_and_verified(self):
        driver = FiltersDriver()
        result, logs = self.run_it(driver)
        self.assertTrue(result)
        self.assertEqual(driver.saved, "-1")
        # Opened twice: to save, then reloaded to verify.
        self.assertEqual(driver.urls, ["https://moodle.test/filter/manage.php?contextid=123"] * 2)
        self.ok.assert_called_once_with("Complementos multimedia desconectados en todo el curso")
        self.assertNotIn("WARNING", logs)

    def test_context_from_filtros_link(self):
        driver = FiltersDriver(context_id=None, links=["https://moodle.test/filter/manage.php?contextid=987"])
        result, _ = self.run_it(driver)
        self.assertTrue(result)
        self.assertIn("contextid=987", driver.urls[0])

    def test_no_context(self):
        result, logs = self.run_it(FiltersDriver(context_id=None))
        self.assertFalse(result)
        self.assertIn("contexto del curso", logs)

    def test_row_missing_at_site_level(self):
        result, logs = self.run_it(FiltersDriver(has_row=False))
        self.assertFalse(result)
        self.assertIn("no aparece", logs)
        self.assertIn("en cada actividad", logs)
        self.ok.assert_not_called()

    def test_select_locked(self):
        result, logs = self.run_it(FiltersDriver(locked=True))
        self.assertFalse(result)
        self.assertIn("bloqueada", logs)

    def test_no_off_option(self):
        driver = FiltersDriver(has_off_option=False)
        result, _ = self.run_it(driver)
        self.assertFalse(result)
        self.assertEqual(len(driver.urls), 1)  # never saved

    def test_save_does_not_stick(self):
        result, logs = self.run_it(FiltersDriver(save_sticks=False))
        self.assertFalse(result)
        self.assertIn("no quedó en 'Desconectado'", logs)
        self.ok.assert_not_called()

    def test_course_not_loaded(self):
        with mock.patch.object(docx, "navigate_to_course", return_value=False):
            result, _ = self.run_it(FiltersDriver())
        self.assertFalse(result)


class UploadDriver:
    """Just enough of the activity edit tab for upload_activity_fragment."""
    current_window_handle = "main"
    window_handles = ["main", "edit"]

    def __init__(self):
        self.switch_to = mock.Mock()

    def execute_script(self, *args):
        return None

    def find_element(self, by, selector):
        return FakeElement()

    def close(self):
        pass


class PerActivityTest(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".html")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write("<p>Actividad</p>")
        self.addCleanup(os.remove, self.path)
        for target, kwargs in [
            ((docx, "get_edit_url_for_activity"), {"return_value": "https://moodle.test/edit"}),
            ((docx, "inject_html_into_wysiwyg"), {"return_value": True}),
            ((docx.time, "sleep"), {}),
            ((docx.progress, "ok"), {}),
            (("actions.html_transformer.remove_questions_from_html",), {"side_effect": lambda html, is_quiz: html}),
            (("actions.html_transformer.transform_activity_html",), {"side_effect": lambda html, course_id: html}),
        ]:
            p = mock.patch.object(*target, **kwargs) if len(target) == 2 else mock.patch(target[0], **kwargs)
            p.start()
        self.per_activity = mock.patch.object(docx, "disable_multimedia_filter_for_activity").start()
        self.addCleanup(mock.patch.stopall)

    def test_course_level_ok_skips_per_activity(self):
        docx.upload_activity_fragment(UploadDriver(), 1, self.path, "ACTIVIDAD 1", 0.1, activity_type="Tarea", disable_filter=False)
        self.per_activity.assert_not_called()

    def test_fallback_disables_per_activity(self):
        docx.upload_activity_fragment(UploadDriver(), 1, self.path, "ACTIVIDAD 1", 0.1, activity_type="Tarea", disable_filter=True)
        self.per_activity.assert_called_once_with(mock.ANY, "ACTIVIDAD 1", 0.1)

    def test_workflow_passes_the_decision(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "workspace", "5", "actividades"))
            for n in (1, 2):
                open(os.path.join(tmp, "workspace", "5", "actividades", f"actividad{n}.html"), "w").close()
            cwd = os.getcwd()
            os.chdir(tmp)
            try:
                with mock.patch.object(docx, "navigate_to_course", return_value=True), \
                        mock.patch.object(docx, "get_skipped_activities", return_value=set()), \
                        mock.patch("core.document_corrections.get_extra_activities", return_value=[]), \
                        mock.patch.object(docx, "upload_activity_fragment") as upload:
                    for per_activity in (False, True):
                        upload.reset_mock()
                        docx.run_docx_upload_workflow(object(), 5, 0.1, per_activity_filter=per_activity)
                        self.assertEqual(upload.call_count, 2)
                        for call in upload.call_args_list:
                            self.assertIs(call.kwargs["disable_filter"], per_activity)
            finally:
                os.chdir(cwd)


class SectionElement:
    def __init__(self, title):
        self.text = title

    def find_element(self, by, selector):
        return self


class MaterialesDriver:
    def find_elements(self, by, selector):
        return [SectionElement("UNIDAD 1"), SectionElement("UNIDAD 2")]


class LecturasPagesTest(unittest.TestCase):
    def setUp(self):
        mock.patch.object(materiales, "navigate_to_course", return_value=True).start()
        mock.patch.object(materiales, "add_etiqueta_materiales").start()
        mock.patch.object(materiales, "add_pagina_materiales", return_value=True).start()
        mock.patch.object(materiales.time, "sleep").start()
        mock.patch.object(materiales.Config, "ENABLE_LECTURAS_COMPLEMENTARIAS_UPLOAD", True, create=True).start()
        self.per_page = mock.patch.object(materiales, "disable_multimedia_filter_for_activity").start()
        self.addCleanup(mock.patch.stopall)

    def test_course_level_ok_no_per_page(self):
        materiales.run_materiales_estudio_workflow(MaterialesDriver(), 1, 0.1, per_page_filter=False)
        self.per_page.assert_not_called()

    def test_fallback_each_lecturas_page(self):
        materiales.run_materiales_estudio_workflow(MaterialesDriver(), 1, 0.1, per_page_filter=True)
        self.assertEqual([c.args[1] for c in self.per_page.call_args_list],
                         ["Lecturas complementarias unidad 1", "Lecturas complementarias unidad 2"])

    def test_page_not_created_not_touched(self):
        with mock.patch.object(materiales, "add_pagina_materiales", return_value=False):
            materiales.run_materiales_estudio_workflow(MaterialesDriver(), 1, 0.1, per_page_filter=True)
        self.per_page.assert_not_called()


if __name__ == "__main__":
    unittest.main()
