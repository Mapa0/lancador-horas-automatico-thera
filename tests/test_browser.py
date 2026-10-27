"""Navegador com pagina ficticia e TODAS as requisicoes interceptadas."""
from datetime import date
import os
from pathlib import Path
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import thera_horas as app

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None


@unittest.skipUnless(os.getenv("THERA_RUN_BROWSER_TESTS") == "1" and sync_playwright,
                     "Ative THERA_RUN_BROWSER_TESTS=1 e instale Playwright")
class BrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch(channel=os.getenv("THERA_TEST_BROWSER") or None, headless=True)
        cls.html = (ROOT / "tests/fixtures/multidados_mock.html").read_text(encoding="utf-8")
        cls.config = app.read_plan(ROOT / "exemplos/lancamentos.exemplo.json")[0]

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()

    def setUp(self):
        self.context = self.browser.new_context()
        self.page = self.context.new_page()
        self.page.set_default_timeout(3000)
        self.context.route("**/*", lambda route: route.fulfill(status=200, content_type="text/html", body=self.html) if route.request.url in (app.HOME_URL, app.URL) else route.abort())
        self.page.goto(app.HOME_URL)

    def tearDown(self):
        self.context.close()

    def test_login_calendar_and_preview_without_save(self):
        self.page.evaluate("() => {document.querySelector('#calendarCalendario').style.display='none'; document.querySelector('#login_portal').style.display='block';}")
        self.assertTrue(app.ensure_logged_in(self.page, "usuario.mock", lambda _: "senha-ficticia"))
        app.prepare_month(self.page, date(2026, 10, 1))
        entry = app.Entry(date(2026, 10, 1), "Previa somente no HTML sintetico")
        form = app.fill_form(self.page, entry, self.config)
        self.assertEqual(form.locator("#tempo_digitado").input_value(), "08:00")
        self.assertFalse(app.read_calendar(self.page)[entry.day]["has_entry"])

    def test_mock_save_and_duplicate_guard(self):
        app.prepare_month(self.page, date(2026, 10, 1))
        entry = app.Entry(date(2026, 10, 1), "Gravacao exclusivamente simulada")
        form = app.fill_form(self.page, entry, self.config)
        app.save_and_verify(self.page, form, entry, self.config)
        self.assertTrue(app.read_calendar(self.page)[entry.day]["has_entry"])
        with self.assertRaises(app.AutomationError):
            app.fill_form(self.page, entry, self.config)

    def test_slow_month_label_uses_calendar_timeout(self):
        self.page.set_default_timeout(100)
        self.page.evaluate("""() => {
            const original = showMonth;
            window.monthClicks = 0;
            showMonth = event => {
                event.preventDefault(); window.monthClicks++;
                setTimeout(() => original(event), 450);
            };
        }""")
        app.prepare_month(self.page, date(2026, 10, 1), [date(2026, 10, 1), date(2026, 10, 2)], timeout_ms=2000)
        self.assertEqual(self.page.locator('#viewLabel').inner_text(), 'VISUALIZAÇÃO MENSAL')
        self.assertEqual(self.page.evaluate('monthClicks'), 1)
        self.assertEqual(self.page.evaluate('saveCount'), 0)

    def test_waits_for_all_requested_dates_not_only_first(self):
        self.page.set_default_timeout(100)
        self.page.evaluate("""() => {
            const original = showMonth;
            window.calendarComplete = false;
            showMonth = event => {
                original(event);
                const last = document.querySelector('#day-02 > a'); last.remove();
                setTimeout(() => {
                    document.querySelector('#day-02').append(last);
                    window.calendarComplete = true;
                }, 450);
            };
        }""")
        app.prepare_month(self.page, date(2026, 10, 1), [date(2026, 10, 1), date(2026, 10, 2)], timeout_ms=2000)
        self.assertTrue(self.page.evaluate('calendarComplete'))
        self.assertEqual(self.page.evaluate('saveCount'), 0)

    def test_waits_for_slow_http_month_response(self):
        self.page.set_default_timeout(100)
        self.page.locator("a[href='?cmd=listar&SHOW=mes']").evaluate("a => a.removeAttribute('onclick')")
        responses = []

        def delayed_response(route):
            # Resposta HTTP sintetica atrasada; nenhuma conexao ao site real.
            time.sleep(0.45)
            responses.append(route.request.url)
            route.fulfill(status=200, content_type='text/html', body=self.html.replace('selectedDay = 27', 'selectedDay = 1'))

        self.page.route(app.URL, delayed_response)
        app.prepare_month(self.page, date(2026, 10, 1), [date(2026, 10, 1), date(2026, 10, 2)], timeout_ms=3000)
        self.assertEqual(responses, [app.URL])
        self.assertEqual(self.page.url, app.URL)
        self.assertEqual(self.page.evaluate('saveCount'), 0)

    def test_incomplete_calendar_stops_without_opening_form(self):
        with self.assertRaisesRegex(app.AutomationError, 'carregamento das datas do calendario mensal'):
            app.prepare_month(self.page, date(2026, 10, 1), [date(2026, 10, 3)], timeout_ms=350)
        self.assertFalse(self.page.locator('#form').is_visible())
        self.assertEqual(self.page.evaluate('saveCount'), 0)

    def test_rejects_calendar_month_changed_by_server(self):
        self.page.evaluate("""() => {
            const original = showMonth;
            showMonth = event => {
                original(event);
                document.querySelector('#calendarCalendario td.title').textContent = 'Novembro, 2026';
            };
        }""")
        with self.assertRaisesRegex(app.AutomationError, 'O periodo mudou'):
            app.prepare_month(self.page, date(2026, 10, 1), timeout_ms=1000)
        self.assertEqual(self.page.evaluate('saveCount'), 0)
