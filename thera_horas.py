"""Lançador de Horas Automático Thera.

Interface local, sem argumentos. Usuário e senha são solicitados a cada execução.
O roteiro do mês é um arquivo JSON escolhido na janela inicial.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
import json
from pathlib import Path
import re
import subprocess
import sys
import unicodedata
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
HOST = "thera.multidadosti.com.br"
HOME_URL = "https://thera.multidadosti.com.br/timesheet/multidados/module/calendario/index.php"
URL = HOME_URL + "?cmd=listar&SHOW=mes"
SERVER_TIMEOUT_MS = 180_000
CONTROL_TIMEOUT_MS = 30_000
FIXED_TIMES = {"hora": "08:00", "intervalo_hr_inicial": "12:00", "intervalo_hr_final": "13:00", "hora_fim": "17:00"}
MONTHS = {name: number for number, name in enumerate(("janeiro", "fevereiro", "marco", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"), start=1)}


class AutomationError(RuntimeError):
    pass


@dataclass(frozen=True)
class Entry:
    day: date
    narrative: str
    planned: bool = False


@dataclass(frozen=True)
class RunOptions:
    username: str
    password: str = field(repr=False)
    auto_save: bool = False
    browser_channel: str = "chrome"


def _iso_day(value, label):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise AutomationError(f"{label}: use uma data no formato AAAA-MM-DD.")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise AutomationError(f"{label}: data inexistente.") from None


def parse_plan(obj):
    """Valida um único mês. Não acessa rede, navegador ou arquivos de senhas."""
    allowed = {"referencia", "localidade", "codigo_projeto", "nome_projeto", "nome_cliente",
               "usuario", "feriados", "fontes_feriados", "lancamentos", "somente_exemplo"}
    if not isinstance(obj, dict) or set(obj) - allowed:
        raise AutomationError("JSON invalido: objeto esperado ou campos nao reconhecidos. Nao inclua senhas.")
    reference = obj.get("referencia")
    if not isinstance(reference, str) or not re.fullmatch(r"\d{4}-\d{2}", reference):
        raise AutomationError("referencia: use AAAA-MM.")
    first = _iso_day(reference + "-01", "referencia")
    for name in ("codigo_projeto", "nome_projeto", "nome_cliente"):
        if not isinstance(obj.get(name), str) or not obj[name].strip():
            raise AutomationError(f"Campo de configuracao invalido: {name}. Copie exatamente do sistema.")
    if "usuario" in obj and not isinstance(obj["usuario"], str):
        raise AutomationError("usuario deve ser texto, sem senha.")
    if not isinstance(obj.get("somente_exemplo", False), bool):
        raise AutomationError("somente_exemplo deve ser true ou false.")
    locality = obj.get("localidade")
    if (not isinstance(locality, dict) or set(locality) != {"pais", "uf", "municipio"}
            or any(not isinstance(v, str) or not v.strip() for v in locality.values())):
        raise AutomationError("localidade deve conter pais, uf e municipio preenchidos.")
    values = obj.get("feriados")
    if not isinstance(values, list):
        raise AutomationError("feriados deve ser uma lista de datas, mesmo quando vazia.")
    holidays = {_iso_day(value, "feriados") for value in values}
    sources = obj.get("fontes_feriados")
    if (not isinstance(sources, list) or not sources or
            any(not isinstance(v, str) or urlsplit(v).scheme not in ("https", "http")
                or not urlsplit(v).hostname for v in sources)):
        raise AutomationError("fontes_feriados: informe ao menos uma URL consultada para verificar o calendario.")
    rows = obj.get("lancamentos")
    if not isinstance(rows, list) or not rows:
        raise AutomationError("lancamentos deve ser uma lista nao vazia.")
    entries, seen = [], set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"data", "narrativa", "projecao"}:
            raise AutomationError("Cada lancamento deve conter somente data, narrativa e projecao.")
        day = _iso_day(row["data"], "data")
        if (day.year, day.month) != (first.year, first.month):
            raise AutomationError(f"Data fora do mes de referencia: {day}.")
        if day in seen:
            raise AutomationError(f"Data duplicada: {day}.")
        seen.add(day)
        narrative, planned = row["narrativa"], row["projecao"]
        if not isinstance(narrative, str) or not narrative.strip() or not isinstance(planned, bool):
            raise AutomationError(f"Narrativa/projecao invalida em {day}.")
        entries.append(Entry(day, narrative.strip(), planned))
    return obj, sorted(entries, key=lambda entry: entry.day), holidays


def read_plan(path):
    try:
        obj = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise AutomationError("Nao foi possivel ler o JSON. Use um arquivo UTF-8 valido, sem comentarios.") from None
    return parse_plan(obj)


def select_entries(entries, holidays, *, today):
    accepted, skipped = [], []
    for entry in entries:
        reason = None
        if entry.day.weekday() >= 5:
            reason = "fim de semana"
        elif entry.day in holidays:
            reason = "feriado"
        elif entry.day > today:
            reason = "data futura"
        elif entry.planned:
            reason = "projecao nao confirmada"
        if reason:
            skipped.append({"data": str(entry.day), "motivo": reason})
        else:
            accepted.append(entry)
    return accepted, skipped


def login_password(_username):
    raise AutomationError("Informe a senha na janela inicial. Ela nao e salva em arquivo.")


def choose_plan():
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
    try:
        return filedialog.askopenfilename(parent=root, title="Selecione o JSON com os lancamentos do mes",
                                          filetypes=[("Roteiro JSON", "*.json")], initialdir=str(ROOT))
    finally:
        root.destroy()



def parse_calendar_links(links: list[dict]) -> dict[date, dict]:
    """Distingue o link do dia (3 argumentos) dos links de registros existentes."""
    result: dict[date, dict] = {}
    for link in links:
        href = link.get("href") or ""
        if not re.match(r"^javascript:\s*editHora\s*\(", href, re.I):
            continue
        args = re.findall(r"'([^']*)'", href)
        if len(args) < 3:
            continue
        try:
            day = datetime.strptime(args[2], "%d/%m/%Y").date()
        except ValueError:
            continue
        record = result.setdefault(day, {"create_href": None, "has_entry": False})
        if len(args) == 3:
            record["create_href"] = href
        elif args[3].strip():
            record["has_entry"] = True
    return result


def read_calendar(page) -> dict[date, dict]:
    links = page.locator("a[href]").evaluate_all(
        "els => els.map(e => ({href: e.getAttribute('href')}))"
    )
    return parse_calendar_links(links)


def ensure_destination(page) -> None:
    if urlsplit(page.url).hostname != HOST:
        raise AutomationError("O navegador nao esta no dominio autorizado do Multidados.")


def ensure_logged_in(page, username: str, password_provider=None, *, timeout_ms=30_000) -> bool:
    """Retorna True se autenticou agora; nao solicita senha para sessao valida."""
    ensure_destination(page)
    ready = """() => ['#calendarCalendario','#login'].some(selector => {
        const e = document.querySelector(selector); return e && e.getClientRects().length;
    })"""
    try:
        page.wait_for_function(ready, timeout=timeout_ms)
    except Exception:
        raise AutomationError("Tela inicial nao reconhecida. Confira o site; CAPTCHA/MFA requer acao manual.") from None
    if page.locator("#calendarCalendario").is_visible():
        return False
    password = (password_provider or login_password)(username)
    try:
        page.locator("#login").fill(username)
        page.locator("#password_sem_md5").fill(password)
        page.get_by_role("button", name="Entrar", exact=True).click()
        page.locator("#calendarCalendario").wait_for(state="visible", timeout=timeout_ms)
        ensure_destination(page)
    except Exception:
        # Nao propagar o erro de fill: seu call log pode incluir o valor preenchido.
        raise AutomationError("Login nao confirmado. Revise usuario/senha ou conclua eventual verificacao manual no site.") from None
    finally:
        password = ""
    return True


def parse_month_title(title: str) -> tuple[int, int]:
    plain = "".join(c for c in unicodedata.normalize("NFKD", title.casefold()) if not unicodedata.combining(c))
    match = re.fullmatch(r"\s*([a-z]+)\s*,\s*(\d{4})\s*", plain)
    if not match or match[1] not in MONTHS:
        raise AutomationError(f"Titulo de calendario nao reconhecido: {title!r}")
    return int(match[2]), MONTHS[match[1]]


def wait_for_month_calendar(page, day: date, expected_days=None, *, timeout_ms=SERVER_TIMEOUT_MS) -> None:
    """Aguarda a pagina mensal e todas as datas do roteiro antes de le-la."""
    required = {day.replace(day=1), *(expected_days or ())}
    if any((value.year, value.month) != (day.year, day.month) for value in required):
        raise AutomationError("As datas esperadas devem pertencer ao mesmo mes do calendario.")
    page.wait_for_function(
        r"""days => {
            if (document.readyState !== 'complete') return false;
            if (!document.body.innerText.includes('VISUALIZAÇÃO MENSAL')) return false;
            const visible = e => e && e.getClientRects().length > 0 &&
                getComputedStyle(e).visibility !== 'hidden';
            const calendar = document.querySelector('#calendarCalendario');
            const selected = calendar && calendar.querySelector('td.day.selected:not(.wn)');
            if (!visible(calendar) || !selected || selected.textContent.trim() !== '1') return false;
            const available = new Set();
            for (const a of document.querySelectorAll('a[href]')) {
                if (!visible(a)) continue;
                const h = a.getAttribute('href') || '';
                if (!/^javascript:\s*editHora\s*\(/i.test(h)) continue;
                const args = Array.from(h.matchAll(/'([^']*)'/g), m => m[1]);
                if (args.length === 3) available.add(args[2]);
            }
            return days.every(value => available.has(value));
        }""",
        arg=[value.strftime("%d/%m/%Y") for value in sorted(required)],
        timeout=timeout_ms,
    )
    ensure_destination(page)
    if parse_month_title(page.locator("#calendarCalendario td.title").inner_text()) != (day.year, day.month):
        raise AutomationError("O periodo mudou ao abrir a visao mensal; interrompido.")


def prepare_month(page, day: date, expected_days=None, *, timeout_ms=SERVER_TIMEOUT_MS) -> None:
    """Seleciona o mes, clica no dia 1 lateral e no icone mensal, pela UI."""
    from playwright.sync_api import TimeoutError as BrowserTimeout, expect

    ensure_destination(page)
    stage = "carregamento do calendario lateral"
    try:
        calendar = page.locator("#calendarCalendario")
        expect(calendar).to_be_visible(timeout=timeout_ms)
        title = calendar.locator("td.title")
        current_year, current_month = parse_month_title(title.inner_text(timeout=timeout_ms))
        offset = (day.year - current_year) * 12 + day.month - current_month
        if abs(offset) > 120:
            raise AutomationError("Mes alvo distante demais do calendario atual; confira o ano no JSON.")
        for _ in range(abs(offset)):
            previous = title.inner_text(timeout=timeout_ms)
            calendar.get_by_text("‹" if offset < 0 else "›", exact=True).click(timeout=timeout_ms)
            expect(title).not_to_have_text(previous, timeout=timeout_ms)
        if parse_month_title(title.inner_text(timeout=timeout_ms)) != (day.year, day.month):
            raise AutomationError("A troca de mes nao chegou ao periodo esperado.")
        stage = "selecao do dia 1"
        calendar.locator("td.day:not(.wn)").filter(has_text=re.compile(r"^1$")).click(timeout=timeout_ms)
        # O clique lateral pode recarregar a pagina e voltar para a visao diaria.
        monthly = page.locator("a[href='?cmd=listar&SHOW=mes']")
        expect(monthly).to_be_visible(timeout=timeout_ms)
        expect(page.locator("#calendarCalendario td.day.selected:not(.wn)")).to_have_text("1", timeout=timeout_ms)
        stage = "abertura do calendario mensal"
        monthly.click(timeout=timeout_ms)
        stage = "carregamento das datas do calendario mensal"
        wait_for_month_calendar(page, day, expected_days, timeout_ms=timeout_ms)
    except (BrowserTimeout, AssertionError):
        raise AutomationError(
            f"O calendario nao ficou pronto durante {stage}, mesmo aguardando ate "
            f"{timeout_ms / 1000:g} segundos. O preenchimento nao foi iniciado. "
            "Aguarde a normalizacao do servidor e execute novamente."
        ) from None


def fill_form(page, entry: Entry, config: dict):
    from playwright.sync_api import expect

    ensure_destination(page)
    day = read_calendar(page).get(entry.day)
    if not day or not day["create_href"]:
        raise AutomationError(f"O dia {entry.day:%d/%m/%Y} nao esta no calendario visivel. Selecione o mes correto.")
    if day["has_entry"]:
        raise AutomationError(f"Ja existe lancamento em {entry.day:%d/%m/%Y}; nao sera alterado nem duplicado.")
    # O href foi lido do calendario; nao executamos funcoes internas do aplicativo.
    selector = "a[href=" + json.dumps(day["create_href"]) + "]"
    page.locator(selector).click()
    form = page.get_by_role("dialog", name="Realizando Lançamento", exact=True)
    expect(form).to_be_visible()
    expect(form.locator("#f_data_b")).to_have_value(entry.day.strftime("%d/%m/%Y"))
    form.locator("#nameprojeto_form_lanctos").click()
    lookup = page.get_by_role("dialog", name="Selecione o Projeto", exact=True)
    expect(lookup).to_be_visible()
    row = lookup.locator("tr[onclick*='setDadosCliProjeto_popup']").filter(
        has_text=config["nome_projeto"]
    ).filter(has_text=config["codigo_projeto"])
    expect(row).to_have_count(1)
    row.click()
    expect(lookup).not_to_be_visible()
    expect(form.locator("#codprojeto_form_lanctos")).to_have_value(config["codigo_projeto"])
    expect(form.locator("#nameprojeto_form_lanctos")).to_have_value(config["nome_projeto"])
    expect(form.locator("#namecliente_form_lanctos")).to_have_value(config["nome_cliente"])
    # Projeto preenche Classe/Fase/Atividade. Mantemos exatamente esses padroes.
    expect(form.locator("#idtarefa_utbms")).to_be_visible()
    expect(form.locator("#idatividade_utbms")).to_be_visible()
    for field in ("idtarefa_utbms", "idatividade_utbms"):
        if not form.locator("#" + field).input_value():
            raise AutomationError(f"O projeto nao definiu {field}; revise manualmente.")
    for field, value in FIXED_TIMES.items():
        form.locator("#" + field).fill(value)
    # O foco na narrativa dispara o blur/recálculo do último horário preenchido.
    form.locator("#narrativa_principal").click()
    form.locator("#narrativa_principal").fill(entry.narrative)
    for field, value in FIXED_TIMES.items():
        expect(form.locator("#" + field)).to_have_value(value)
    expect(form.locator("#tempo_digitado")).to_have_value("08:00")
    expect(form.locator("#f_data_b")).to_have_value(entry.day.strftime("%d/%m/%Y"))
    expect(form.locator("#narrativa_principal")).to_have_value(entry.narrative)
    return form


def save_and_verify(page, form, entry: Entry, config: dict) -> None:
    from playwright.sync_api import expect

    ensure_destination(page)
    # Uma unica tentativa. Se a resposta for incerta, paramos; nao repetimos o clique.
    form.get_by_role("button", name="Salvar", exact=True).click()
    expect(form).not_to_be_visible(timeout=30_000)
    page.wait_for_function(
        """({day, narrative, project}) => Array.from(document.querySelectorAll('a[href]')).some(a => {
            const h = a.getAttribute('href') || '';
            if (!/^javascript:\\s*editHora\\s*\\(/i.test(h)) return false;
            const args = Array.from(h.matchAll(/'([^']*)'/g), m => m[1]);
            if (args.length < 4 || args[2] !== day || !args[3]) return false;
            const text = a.closest('td')?.innerText || '';
            return text.includes(narrative) && text.includes(project) && text.includes('08:00 - 17:00');
        })""",
        arg={"day": entry.day.strftime("%d/%m/%Y"), "narrative": entry.narrative, "project": config["nome_projeto"]},
        timeout=30_000,
    )
    if not read_calendar(page).get(entry.day, {}).get("has_entry"):
        raise AutomationError("Nao foi possivel confirmar o registro; pare e confira o calendario antes de tentar novamente.")


def review_text(entries, skipped):
    parts = ["RASCUNHO PARA CONFERENCIA. Revise datas, narrativas e horas efetivamente trabalhadas.", ""]
    for entry in entries:
        parts.extend((f"{entry.day:%d/%m/%Y} - 8 horas", entry.narrative, ""))
    if skipped:
        parts.extend(("NAO SERAO LANCADOS:", ""))
        parts.extend(f"{row['data']}: {row['motivo']}" for row in skipped)
    return "\n".join(parts)


def collect_options(config, entries, skipped):
    import tkinter as tk
    from tkinter import messagebox, scrolledtext, ttk

    root = tk.Tk()
    root.title("Lançador de Horas Automático Thera - " + config["referencia"])
    root.geometry(f"980x{min(780, max(620, root.winfo_screenheight() - 120))}")
    root.minsize(820, 600)
    main = ttk.Frame(root, padding=18)
    main.grid(row=0, column=0, sticky="nsew")
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)
    main.columnconfigure(1, weight=1)
    main.rowconfigure(8, weight=1)
    username = tk.StringVar(value=config.get("usuario", ""))
    password = tk.StringVar()
    auto_save = tk.BooleanVar(value=False)
    browser_name = tk.StringVar(value="Chrome")
    result = []

    ttk.Label(main, text="Acesso ao Multidados", font=("Segoe UI", 15, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0,14))
    ttk.Label(main, text="Usuario:").grid(row=1, column=0, sticky="w", padx=(0,10))
    user_field = ttk.Entry(main, textvariable=username, width=35)
    user_field.grid(row=1, column=1, sticky="ew", pady=4)
    ttk.Label(main, text="Senha:").grid(row=2, column=0, sticky="w")
    pass_field = ttk.Entry(main, textvariable=password, show="*", width=35)
    pass_field.grid(row=2, column=1, sticky="ew", pady=4)
    ttk.Label(main, text="Navegador:").grid(row=3, column=0, sticky="w")
    ttk.Combobox(main, textvariable=browser_name, values=("Chrome", "Microsoft Edge"), state="readonly").grid(row=3, column=1, sticky="ew", pady=4)
    ttk.Label(main, text="08:00  |  12:00  |  13:00  |  17:00  =  8h/dia").grid(row=4, column=0, columnspan=2, sticky="w", pady=(12,6))
    ttk.Checkbutton(main, variable=auto_save, text="Salvar os lancamentos automaticamente (desmarcado: apenas uma previa)").grid(row=5, column=0, columnspan=2, sticky="w", pady=5)
    ttk.Label(main, text=f"{len(entries)} dias elegiveis. O programa pula feriados, finais de semana, projecoes e dias ja preenchidos.").grid(row=6, column=0, columnspan=2, sticky="w")
    ttk.Label(main, text="Confira as narrativas abaixo antes de escolher salvar:").grid(row=7, column=0, columnspan=2, sticky="w", pady=(12,4))
    review = scrolledtext.ScrolledText(main, wrap="word", height=17, font=("Segoe UI",10))
    review.grid(row=8, column=0, columnspan=2, sticky="nsew")
    review.insert("1.0", review_text(entries, skipped))
    review.configure(state="disabled")
    ttk.Label(main, text="A senha e usada somente nesta execucao. Nao fica no arquivo nem e armazenada no Windows.").grid(row=9, column=0, columnspan=2, sticky="w", pady=(10,4))
    buttons = ttk.Frame(main)
    buttons.grid(row=10, column=0, columnspan=2, sticky="e", pady=(8,0))

    def start():
        if not username.get().strip() or not password.get():
            messagebox.showwarning("Dados incompletos", "Informe usuario e senha.", parent=root)
            return
        result.append(RunOptions(username.get().strip(), password.get(), bool(auto_save.get()), "msedge" if browser_name.get() == "Microsoft Edge" else "chrome"))
        password.set("")
        root.destroy()

    ttk.Button(buttons, text="Cancelar", command=root.destroy).pack(side="right", padx=(8,0))
    ttk.Button(buttons, text="Iniciar", command=start).pack(side="right")
    root.bind("<Return>", lambda _event: start())
    pass_field.focus_set() if username.get() else user_field.focus_set()
    root.mainloop()
    return result[0] if result else None


def notice(title, message, *, question=False, error=False):
    import tkinter as tk
    from tkinter import messagebox
    root = tk.Tk()
    root.withdraw()
    try:
        if question:
            return bool(messagebox.askyesno(title, message, parent=root))
        if error:
            messagebox.showerror(title, message, parent=root)
        else:
            messagebox.showinfo(title, message, parent=root)
        return None
    finally:
        root.destroy()


def ensure_dependency():
    try:
        import playwright.sync_api
        return True
    except ImportError:
        if not notice("Dependencia necessaria", "Para funcionar, este Python precisa do Playwright 1.64.1.\n\nDeseja instalar agora pelo pip/PyPI? Isso e necessario apenas uma vez.", question=True):
            return False
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "playwright==1.64.1"], check=True, capture_output=True, timeout=180)
        except Exception:
            raise AutomationError("Nao foi possivel instalar a dependencia. Confira Python/pip e acesso ao PyPI.") from None
        return True


def append_log(path, data):
    with path.open("a", encoding="utf-8") as out:
        out.write(json.dumps(data, ensure_ascii=False) + "\n")


def execute(options, config, entries):
    from playwright.sync_api import expect, sync_playwright
    evidence = ROOT / "evidencias" / ("unico-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
    evidence.mkdir(parents=True, exist_ok=True)
    saved = 0
    with sync_playwright() as playwright:
        # Contexto temporario: nao reutiliza nem guarda sessao/senha do usuario.
        browser = playwright.chromium.launch(channel=options.browser_channel, headless=False)
        context = browser.new_context(no_viewport=True, accept_downloads=False)
        page = context.new_page()
        page.set_default_timeout(CONTROL_TIMEOUT_MS)
        page.set_default_navigation_timeout(SERVER_TIMEOUT_MS)
        expect.set_options(timeout=CONTROL_TIMEOUT_MS)
        unexpected = []

        def on_dialog(dialog):
            if dialog.type == "alert":
                dialog.accept()
            else:
                unexpected.append("confirmacao inesperada do site")
                dialog.dismiss()

        page.on("dialog", on_dialog)
        try:
            page.goto(HOME_URL, wait_until="domcontentloaded")
            ensure_logged_in(page, options.username, lambda _username: options.password, timeout_ms=SERVER_TIMEOUT_MS)
            prepare_month(page, entries[0].day, [entry.day for entry in entries])
            page.screenshot(path=str(evidence / "calendario.png"), full_page=False)
            calendar = read_calendar(page)
            missing = [entry.day for entry in entries if entry.day not in calendar]
            if missing:
                raise AutomationError("O calendario nao contem todas as datas do roteiro. Nao foi salvo nenhum novo registro nesta etapa.")
            pending = [entry for entry in entries if not calendar[entry.day]["has_entry"]]
            if not pending:
                notice("Tudo preenchido", "Todos os dias elegiveis ja possuem lancamentos. Nada foi alterado.")
                return 0
            if not options.auto_save:
                entry = pending[0]
                form = fill_form(page, entry, config)
                page.screenshot(path=str(evidence / "previa-sem-salvar.png"), full_page=False)
                notice("Previa pronta - sem salvar", f"Dia {entry.day:%d/%m/%Y} preenchido com total de 8 horas.\n\nConfira o formulario no navegador. Nenhum clique em Salvar foi feito.\nOK fecha a previa sem gravar.")
                if form.is_visible():
                    form.get_by_role("button", name="close", exact=True).click()
                return 0

            dates = ", ".join(f"{entry.day:%d/%m}" for entry in pending)
            if not notice("Confirmar lancamentos reais", f"Destino: {HOST}\nProjeto: {config['nome_projeto']}\n\nCriar {len(pending)} lancamentos, total {len(pending)*8} horas?\nDatas: {dates}\n\nConfirme apenas se revisou as narrativas e as 8 horas efetivamente trabalhadas por dia.\nDias ja preenchidos nao serao alterados.", question=True):
                return 0

            for entry in pending:
                # Reconfere o dia antes de cada formulario, inclusive contra duplicidades.
                form = fill_form(page, entry, config)
                if unexpected:
                    raise AutomationError("O site apresentou uma confirmacao nao prevista. Confira antes de continuar.")
                page.screenshot(path=str(evidence / f"{entry.day}-antes.png"), full_page=False)
                append_log(evidence / "execucao.jsonl", {"data":str(entry.day), "status":"antes_do_clique_salvar"})
                save_and_verify(page, form, entry, config)
                if unexpected:
                    raise AutomationError("O site apresentou uma confirmacao nao prevista. Confira o ultimo registro.")
                saved += 1
                append_log(evidence / "execucao.jsonl", {"data":str(entry.day), "status":"salvo_e_confirmado_no_calendario"})
            page.screenshot(path=str(evidence / "calendario-final.png"), full_page=False)
            notice("Concluido", f"{saved} lancamentos confirmados no calendario.\n\nEvidencias: {evidence}")
            return saved
        except Exception as exc:
            try:
                page.screenshot(path=str(evidence / "interrompido.png"), full_page=False)
            except Exception:
                pass
            safe_message = str(exc) if isinstance(exc, AutomationError) else "A interface nao respondeu como esperado. Nao repetimos o ultimo clique em Salvar."
            notice("Execucao interrompida", f"{safe_message}\n\nRegistros confirmados nesta execucao: {saved}.\nConfira o calendario antes de repetir.\n\nEvidencias: {evidence}\n\nOK fecha apenas a janela de automacao.", error=True)
            return saved
        finally:
            context.close()
            browser.close()


def main():
    try:
        path = choose_plan()
        if not path:
            return
        config, all_entries, holidays = read_plan(path)
        if config.get("somente_exemplo", False):
            notice("Arquivo de exemplo", "Este roteiro e ficticio e nao pode iniciar lancamentos.\n\nCrie seu proprio JSON usando o prompt do repositorio e defina somente_exemplo como false.")
            return
        entries, skipped = select_entries(all_entries, holidays, today=date.today())
        if not entries:
            notice("Sem datas elegiveis", "Nao ha dias realizados e elegiveis no roteiro. Confira feriados, datas futuras e projecoes.")
            return
        options = collect_options(config, entries, skipped)
        if options is None or not ensure_dependency():
            return
        execute(options, config, entries)
    except AutomationError as exc:
        notice("Nao foi possivel iniciar", str(exc), error=True)
    except Exception:
        notice("Nao foi possivel iniciar", "Confira Python 3.10+, o navegador selecionado instalado e o JSON do mes.", error=True)


if __name__ == "__main__":
    main()

