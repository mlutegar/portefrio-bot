"""Testa os helpers de seleção do scraper contra DOM real (Playwright).

Não acessa o portal: usa page.set_content() com HTML fixture. Serve de rede de
segurança para regressões nos seletores de login/erro.
"""
from __future__ import annotations

import pytest

playwright_sync = pytest.importorskip("playwright.sync_api")
from playwright.sync_api import sync_playwright  # noqa: E402

from app.scraper import portal  # noqa: E402

LOGIN_HTML = """
<!doctype html><html><body>
  <form>
    <input id="username" name="username" type="text" />
    <input id="password" name="password" type="password" />
    <button type="submit">Entrar</button>
  </form>
</body></html>
"""

ERRO_HTML = """
<!doctype html><html><body>
  <div class="alert">Usuário ou senha inválidos.</div>
</body></html>
"""


@pytest.fixture(scope="module")
def page():
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            pg = browser.new_page()
            yield pg
            browser.close()
    except Exception as e:  # chromium não instalado no ambiente
        pytest.skip(f"Playwright/Chromium indisponível: {e}")


def test_preenche_campos_login(page):
    page.set_content(LOGIN_HTML)
    assert portal._preencher_primeiro(
        page, ["#username", "input[type=email]"], "joao@x.com"
    )
    assert portal._preencher_primeiro(page, ["#password"], "segredo")
    assert page.input_value("#username") == "joao@x.com"
    assert page.input_value("#password") == "segredo"


def test_clica_submit(page):
    page.set_content(LOGIN_HTML)
    assert portal._clicar_primeiro(
        page, ["button[type=submit]", "button:has-text('Entrar')"]
    )


def test_detecta_erro_login(page):
    page.set_content(ERRO_HTML)
    assert portal._tem_erro_login(page) is True
    page.set_content(LOGIN_HTML)
    assert portal._tem_erro_login(page) is False


def test_precisa_login(page):
    page.set_content(LOGIN_HTML)
    assert portal._precisa_login(page) is True
    page.set_content("<html><body>Bem-vindo</body></html>")
    assert portal._precisa_login(page) is False
