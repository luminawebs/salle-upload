"""
Filling a Moodle rubric (actions/deprecated/actividad_rubrica_actions.py):
every field in one block, read back before saving, and field by field as a
fallback; a rubric that does not read back as expected is never saved.
Uses a fake driver, no Moodle needed.

    python -m unittest tests.test_rubric_fill -v
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from actions.deprecated import actividad_rubrica_actions as rubric  # noqa: E402


PLAN = [
    {"crit_id": "NEWID1", "level_ids": ["NEWID1", "NEWID2"], "name": "Diagnóstico\r\ncorrecto",
     "levels": ["Lo evidencia", "No lo evidencia"], "scores": ["2", "0"]},
    {"crit_id": "NEWID2", "level_ids": ["NEWID3", "NEWID4"], "name": "Reflexión",
     "levels": ["Lo evidencia", "No lo evidencia"], "scores": ["1.5", "0"]},
]


class FakeRow:
    def __init__(self, row_id):
        self.row_id = row_id

    def get_attribute(self, name):
        return self.row_id if name == "id" else None


class FakeDriver:
    """The rubric editor's fields as a dict; the batch and read-back scripts act on it."""

    def __init__(self, plan, batch_error=None, ignore=()):
        self.rows = [FakeRow(f"rubric-criteria-{p['crit_id']}") for p in plan]
        self.values = {}
        for f in rubric._rubric_fields(plan):
            self.values[f["id"] or f["name"]] = ""
        self.batch_error = batch_error
        self.ignore = set(ignore)  # fields the batch script fails to change

    def find_elements(self, by, selector):
        return list(self.rows)

    def execute_script(self, script, fields):
        if script is rubric._BATCH_FILL_JS:
            if self.batch_error:
                raise self.batch_error
            missing = []
            for f in fields:
                key = f["id"] or f["name"]
                if key not in self.values:
                    missing.append(f["label"])
                elif key not in self.ignore:
                    self.values[key] = f["value"].replace("\r\n", "\n")
            return missing
        if script is rubric._READ_BACK_JS:
            return [self.values.get(f["id"] or f["name"]) for f in fields]
        raise AssertionError("unexpected script")

    def fill_all(self, *args):
        for f in rubric._rubric_fields(PLAN):
            self.values[f["id"] or f["name"]] = f["value"]


class FieldsTests(unittest.TestCase):
    def test_fields_use_moodle_ids_and_names(self):
        fields = rubric._rubric_fields(PLAN)
        self.assertEqual(len(fields), 2 * (1 + 2 * 2))
        self.assertEqual(fields[0]["id"], "rubric-criteria-NEWID1-description")
        self.assertEqual(fields[1]["id"], "rubric-criteria-NEWID1-levels-NEWID1-definition")
        self.assertEqual(fields[2]["name"], "rubric[criteria][NEWID1][levels][NEWID1][score]")
        self.assertEqual(fields[2]["value"], "2")


class MismatchTests(unittest.TestCase):
    def setUp(self):
        self.fields = rubric._rubric_fields(PLAN)
        self.good = [f["value"] for f in self.fields]

    def test_identical_values_match(self):
        self.assertIsNone(rubric._first_rubric_mismatch(self.fields, self.good))

    def test_line_breaks_read_back_as_lf_still_match(self):
        actual = [v.replace("\r\n", "\n") for v in self.good]
        self.assertIsNone(rubric._first_rubric_mismatch(self.fields, actual))

    def test_reports_first_wrong_field(self):
        actual = list(self.good)
        actual[2] = "1"     # criterion 1, level 1 score
        actual[6] = "otro"  # later field, not reported
        msg = rubric._first_rubric_mismatch(self.fields, actual)
        self.assertIn("criterio 1, nivel 1, puntaje", msg)
        self.assertIn("'2'", msg)

    def test_missing_field(self):
        actual = list(self.good)
        actual[0] = None
        self.assertIn("criterio 1, descripción: el campo no existe", rubric._first_rubric_mismatch(self.fields, actual))

    def test_wrong_count_or_no_answer(self):
        self.assertIsNotNone(rubric._first_rubric_mismatch(self.fields, self.good[:-1]))
        self.assertIsNotNone(rubric._first_rubric_mismatch(self.fields, None))

    def test_empty_text_is_not_a_match(self):
        actual = list(self.good)
        actual[1] = ""
        self.assertIn("criterio 1, nivel 1, texto", rubric._first_rubric_mismatch(self.fields, actual))

    def test_verify_checks_the_rows(self):
        driver = FakeDriver(PLAN)
        driver.fill_all()
        self.assertIsNone(rubric._verify_rubric(driver, PLAN))
        driver.rows.append(FakeRow("rubric-criteria-NEWID3"))
        self.assertIn("3 criterios", rubric._verify_rubric(driver, PLAN))


class FillChoiceTests(unittest.TestCase):
    def fill(self, driver, fallback=None):
        with mock.patch.object(rubric, "_fill_fields_one_by_one", side_effect=fallback) as one_by_one, \
                self.assertLogs(rubric.logger, level="INFO") as logs:
            method = rubric._fill_rubric_values(driver, PLAN, 5, "ACTIVIDAD 1")
        return method, one_by_one, "\n".join(logs.output)

    def test_batch_verified_needs_no_fallback(self):
        driver = FakeDriver(PLAN)
        method, one_by_one, log = self.fill(driver)
        self.assertEqual(method, "bloque")
        one_by_one.assert_not_called()
        self.assertIn("llenado en bloque", log)
        self.assertIsNone(rubric._verify_rubric(driver, PLAN))

    def test_batch_error_falls_back(self):
        driver = FakeDriver(PLAN, batch_error=RuntimeError("javascript error"))
        method, one_by_one, log = self.fill(driver, fallback=driver.fill_all)
        self.assertEqual(method, "campo por campo")
        one_by_one.assert_called_once()
        self.assertIn("llenado campo por campo (respaldo)", log)

    def test_batch_mismatch_falls_back(self):
        driver = FakeDriver(PLAN, ignore=["rubric[criteria][NEWID2][levels][NEWID3][score]"])
        method, one_by_one, log = self.fill(driver, fallback=driver.fill_all)
        self.assertEqual(method, "campo por campo")
        self.assertIn("criterio 2, nivel 1, puntaje", log)

    def test_missing_field_in_batch_falls_back(self):
        driver = FakeDriver(PLAN)
        del driver.values["rubric-criteria-NEWID2-description"]
        method, one_by_one, log = self.fill(driver)
        self.assertIsNone(method)
        one_by_one.assert_called_once()

    def test_both_methods_failing_means_do_not_save(self):
        driver = FakeDriver(PLAN, batch_error=RuntimeError("javascript error"))
        method, one_by_one, log = self.fill(driver)  # fallback writes nothing
        self.assertIsNone(method)
        self.assertIn("No se guarda", log)

    def test_fallback_error_means_do_not_save(self):
        driver = FakeDriver(PLAN, batch_error=RuntimeError("javascript error"))
        method, _, log = self.fill(driver, fallback=RuntimeError("stale element"))
        self.assertIsNone(method)
        self.assertIn("stale element", log)

    def test_fill_rubric_does_not_save_an_unverified_rubric(self):
        driver = mock.Mock()
        with mock.patch.object(rubric, "_get_criteria_rows", return_value=[1, 2]), \
                mock.patch.object(rubric, "_build_rubric_plan", return_value=PLAN), \
                mock.patch.object(rubric, "_fill_rubric_values", return_value=None):
            crits = [{"name": "a", "levels": [], "scores": []}] * 2
            self.assertFalse(rubric.fill_rubric(driver, crits, 5))
        driver.find_elements.assert_not_called()  # never looked for the save button


if __name__ == "__main__":
    unittest.main()
