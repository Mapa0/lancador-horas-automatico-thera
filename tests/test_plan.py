"""Validação do roteiro e elegibilidade, sem navegador ou conta real."""
import copy
from datetime import date
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import thera_horas as app


def valid_plan():
    return {
        "referencia": "2026-10",
        "localidade": {"pais": "BR", "uf": "SP", "municipio": "São Paulo"},
        "codigo_projeto": "000001",
        "nome_projeto": "PROJETO FICTICIO",
        "nome_cliente": "CLIENTE FICTICIO",
        "usuario": "",
        "somente_exemplo": False,
        "feriados": ["2026-10-12"],
        "fontes_feriados": ["https://example.org/calendario-ficticio"],
        "lancamentos": [{"data": "2026-10-01", "narrativa": "Cenário fictício.", "projecao": False}],
    }


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.obj = valid_plan()

    def invalid(self):
        with self.assertRaises(app.AutomationError):
            app.parse_plan(self.obj)

    def test_valid_plan_preserves_project_leading_zeroes(self):
        config, entries, holidays = app.parse_plan(self.obj)
        self.assertEqual(config["codigo_projeto"], "000001")
        self.assertEqual(entries[0].day, date(2026, 10, 1))
        self.assertEqual(holidays, {date(2026, 10, 12)})

    def test_public_example_is_valid_but_cannot_launch(self):
        config, entries, _ = app.read_plan(ROOT / "exemplos/lancamentos.exemplo.json")
        self.assertTrue(config["somente_exemplo"])
        self.assertTrue(all(e.planned for e in entries))
        with mock.patch.object(app, "choose_plan", return_value=str(ROOT / "exemplos/lancamentos.exemplo.json")), \
             mock.patch.object(app, "notice") as notice, mock.patch.object(app, "execute") as execute, \
             mock.patch.object(app, "collect_options") as options:
            app.main()
            notice.assert_called_once()
            execute.assert_not_called()
            options.assert_not_called()

    def test_cancel_does_not_request_credentials(self):
        with mock.patch.object(app, "choose_plan", return_value=""), mock.patch.object(app, "collect_options") as options:
            app.main()
            options.assert_not_called()

    def test_non_object_is_rejected(self):
        with self.assertRaises(app.AutomationError):
            app.parse_plan([])

    def test_numeric_project_code_rejected(self):
        self.obj["codigo_projeto"] = 1
        self.invalid()

    def test_missing_project_rejected(self):
        del self.obj["nome_projeto"]
        self.invalid()

    def test_password_field_rejected(self):
        self.obj["password"] = "apenas-ficticio"
        self.invalid()

    def test_unknown_entry_field_rejected(self):
        self.obj["lancamentos"][0]["horas"] = 8
        self.invalid()

    def test_duplicate_day_rejected(self):
        self.obj["lancamentos"].append(dict(self.obj["lancamentos"][0]))
        self.invalid()

    def test_other_month_rejected(self):
        self.obj["lancamentos"][0]["data"] = "2026-11-01"
        self.invalid()

    def test_non_iso_day_rejected(self):
        self.obj["lancamentos"][0]["data"] = "01/10/2026"
        self.invalid()

    def test_impossible_day_rejected(self):
        self.obj["lancamentos"][0]["data"] = "2026-10-32"
        self.invalid()

    def test_bad_reference_rejected(self):
        for value in ("2026-1", "2026-13", None):
            with self.subTest(value=value):
                self.obj["referencia"] = value
                self.invalid()

    def test_empty_narrative_rejected(self):
        self.obj["lancamentos"][0]["narrativa"] = "  "
        self.invalid()

    def test_string_boolean_rejected(self):
        self.obj["lancamentos"][0]["projecao"] = "false"
        self.invalid()

    def test_missing_projection_rejected(self):
        del self.obj["lancamentos"][0]["projecao"]
        self.invalid()

    def test_empty_entries_rejected(self):
        self.obj["lancamentos"] = []
        self.invalid()

    def test_locality_required(self):
        del self.obj["localidade"]["municipio"]
        self.invalid()

    def test_holiday_list_required(self):
        self.obj["feriados"] = "2026-10-12"
        self.invalid()

    def test_sources_required_and_urls_valid(self):
        for values in ([], ["nao-e-url"], ["file:///arquivo"]):
            with self.subTest(values=values):
                self.obj["fontes_feriados"] = values
                self.invalid()

    def test_sorted_entries_and_leap_year(self):
        self.obj["referencia"] = "2024-02"
        self.obj["lancamentos"] = [
            {"data": "2024-02-29", "narrativa": "Fictício.", "projecao": False},
            {"data": "2024-02-01", "narrativa": "Fictício.", "projecao": False},
        ]
        self.assertEqual(app.parse_plan(self.obj)[1][0].day, date(2024, 2, 1))

    def test_weekend_holiday_future_and_projection_skipped(self):
        entries = [
            app.Entry(date(2026, 10, 1), "Realizado fictício."),
            app.Entry(date(2026, 10, 3), "Sábado."),
            app.Entry(date(2026, 10, 4), "Domingo."),
            app.Entry(date(2026, 10, 12), "Feriado."),
            app.Entry(date(2026, 10, 30), "Futuro."),
            app.Entry(date(2026, 10, 2), "Projeção.", True),
        ]
        accepted, skipped = app.select_entries(entries, {date(2026, 10, 12)}, today=date(2026, 10, 27))
        self.assertEqual([e.day for e in accepted], [date(2026, 10, 1)])
        self.assertEqual(len(skipped), 5)

    def test_projection_remains_skipped_after_date_passes(self):
        accepted, _ = app.select_entries([app.Entry(date(2026, 10, 1), "Planejado.", True)], set(), today=date(2026, 11, 1))
        self.assertEqual(accepted, [])

    def test_utf8_bom_json_supported(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "plano.json"
            path.write_text(json.dumps(self.obj), encoding="utf-8-sig")
            self.assertEqual(len(app.read_plan(path)[1]), 1)

    def test_invalid_json_has_clear_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "invalido.json"
            path.write_text("{invalido}", encoding="utf-8")
            with self.assertRaisesRegex(app.AutomationError, "JSON"):
                app.read_plan(path)

    def test_password_not_in_repr_and_preview_is_default(self):
        options = app.RunOptions("conta.ficticia", "segredo-ficticio")
        self.assertNotIn("segredo-ficticio", repr(options))
        self.assertFalse(options.auto_save)
        self.assertEqual(options.browser_channel, "chrome")
        self.assertEqual(app.RunOptions("conta", "ficticio", browser_channel="msedge").browser_channel, "msedge")

    def test_existing_records_detected_without_confusing_empty_day(self):
        links = [
            {"href": "javascript:editHora('08:00','','01/10/2026')"},
            {"href": "javascript:editHora('08:00','','01/10/2026','123','T')"},
            {"href": "javascript:editHora('08:00','','02/10/2026')"},
        ]
        days = app.parse_calendar_links(links)
        self.assertTrue(days[date(2026, 10, 1)]["has_entry"])
        self.assertFalse(days[date(2026, 10, 2)]["has_entry"])

    def test_review_includes_skipped_days(self):
        text = app.review_text([app.Entry(date(2026, 10, 1), "Fictício.")],
                               [{"data": "2026-10-12", "motivo": "feriado"}])
        self.assertIn("RASCUNHO", text)
        self.assertIn("feriado", text)

    def test_unapproved_host_rejected(self):
        with self.assertRaises(app.AutomationError):
            app.ensure_destination(type("Page", (), {"url": "https://example.org"})())


if __name__ == "__main__":
    unittest.main()

