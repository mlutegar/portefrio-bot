"""Script de exploração para mapear os seletores reais do portal.
Uso: python explore_portal.py <email> <senha> [senha_secundaria] [cnpj]
Salva screenshots/HTML em ./diagnostics e imprime inputs/botões detectados.
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

PORTAL_URL = "https://portal.multiplike.com.br/"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
OUT = Path(__file__).parent / "diagnostics"
OUT.mkdir(exist_ok=True)


def dump(page, tag):
    try:
        page.screenshot(path=str(OUT / f"{tag}.png"), full_page=True)
        (OUT / f"{tag}.html").write_text(page.content(), encoding="utf-8", errors="ignore")
    except Exception as e:
        print(f"[dump {tag}] erro: {e}")
    print(f"\n===== {tag} | url={page.url} | title={page.title()!r} =====")
    inputs = page.eval_on_selector_all(
        "input",
        "els => els.map(e => ({type:e.type,name:e.name,id:e.id,ph:e.placeholder,vis:!!(e.offsetParent)}))",
    )
    print("INPUTS:")
    for i in inputs:
        print("  ", i)
    buttons = page.eval_on_selector_all(
        "button, input[type=submit], a[href]",
        "els => els.slice(0,40).map(e => ({tag:e.tagName,txt:(e.innerText||e.value||'').trim().slice(0,40),type:e.type,href:e.getAttribute&&e.getAttribute('href')}))",
    )
    print("BOTÕES/LINKS (até 40):")
    for b in buttons:
        if b.get("txt") or b.get("href"):
            print("  ", b)


def main():
    email = sys.argv[1]
    senha = sys.argv[2]
    senha2 = sys.argv[3] if len(sys.argv) > 3 else None
    cnpj = sys.argv[4] if len(sys.argv) > 4 else None

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent=UA, accept_downloads=True)
        ctx.set_default_timeout(45000)
        page = ctx.new_page()
        try:
            page.goto(PORTAL_URL, wait_until="domcontentloaded")
            try:
                page.wait_for_load_state("networkidle", timeout=20000)
            except Exception:
                pass
            dump(page, "01_login")

            # tentar preencher
            filled = False
            for sel in ["input[type=email]", "input[name*=email i]", "input[name*=user i]", "input[name*=login i]", "input[type=text]"]:
                loc = page.locator(sel).first
                if loc.count() and loc.is_visible():
                    loc.fill(email)
                    print(f"email -> {sel}")
                    filled = True
                    break
            for sel in ["input[type=password]"]:
                loc = page.locator(sel).first
                if loc.count() and loc.is_visible():
                    loc.fill(senha)
                    print(f"senha -> {sel}")
                    break
            # submit
            for sel in ["button[type=submit]", "input[type=submit]", "button:has-text('Entrar')", "button:has-text('Acessar')", "button:has-text('Login')"]:
                loc = page.locator(sel).first
                if loc.count() and loc.is_visible():
                    print(f"submit -> {sel}")
                    loc.click()
                    break
            try:
                page.wait_for_load_state("networkidle", timeout=25000)
            except Exception:
                pass
            dump(page, "02_pos_login")

            if senha2 and page.locator("input[type=password]").count():
                c2 = page.locator("input[type=password]").last
                if c2.is_visible():
                    c2.fill(senha2)
                    for sel in ["button[type=submit]", "button:has-text('Confirmar')", "button:has-text('Validar')", "button:has-text('Entrar')"]:
                        loc = page.locator(sel).first
                        if loc.count() and loc.is_visible():
                            loc.click()
                            break
                    try:
                        page.wait_for_load_state("networkidle", timeout=25000)
                    except Exception:
                        pass
                    dump(page, "03_pos_2fa")

            if cnpj:
                for sel in ["input[name*=cnpj i]", "input[id*=cnpj i]", "input[placeholder*=cnpj i]", "input[type=search]", "input[type=text]"]:
                    loc = page.locator(sel).first
                    if loc.count() and loc.is_visible():
                        loc.fill(cnpj)
                        print(f"cnpj -> {sel}")
                        break
                page.keyboard.press("Enter")
                try:
                    page.wait_for_load_state("networkidle", timeout=25000)
                except Exception:
                    pass
                dump(page, "04_busca_cnpj")
        finally:
            ctx.close()
            browser.close()


if __name__ == "__main__":
    main()
