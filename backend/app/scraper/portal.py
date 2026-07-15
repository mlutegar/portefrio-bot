"""
Scraper do Portal Multiplike usando Playwright.

IMPORTANTE — pontos de ajuste (marcados com AJUSTAR):
O portal é autenticado e bloqueia acessos simples (HTTP 403), então os seletores
exatos de login, do campo de CNPJ e dos links de PDF só podem ser confirmados
rodando o navegador de verdade. Rode com HEADLESS=false para validar/ajustar os
seletores destacados. Em qualquer falha, um screenshot + HTML da página são
salvos em DIAG_DIR para diagnóstico.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Callable, List, Optional

from playwright.sync_api import Page, TimeoutError as PWTimeout, sync_playwright

from ..config import (
    DIAG_DIR,
    HEADLESS,
    MAX_RETRIES,
    NAV_TIMEOUT,
    PORTAL_URL,
    SESSION_DIR,
    SESSION_TTL_SECONDS,
)
from ..logging_config import get_logger
from .selectors import SELECTORS


log = get_logger("scraper.portal")

ProgressCb = Callable[[str, int], None]


class ScraperError(Exception):
    """Erro de negócio esperado (login falhou, CNPJ não encontrado, etc.)."""


class CnpjNaoEncontrado(ScraperError):
    """CNPJ pesquisado não retornou resultados no portal."""


class LoginError(ScraperError):
    """Credenciais rejeitadas pelo portal."""


class SeletorError(ScraperError):
    """Um elemento esperado não foi encontrado — provável ajuste de seletor."""


class NavigationError(ScraperError):
    """Erro durante a navegação no portal."""
    def __init__(self, message: str, step: str, diagnostics_base: Optional[str] = None):
        super().__init__(message)
        self.step = step
        self.diagnostics_base = diagnostics_base



USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def _so_digitos(cnpj: str) -> str:
    return re.sub(r"\D", "", cnpj)


def _session_path(email: str) -> Path:
    h = hashlib.sha256(email.strip().lower().encode()).hexdigest()[:16]
    return SESSION_DIR / f"{h}.json"


def _cookie_expiry_epoch(path: Path) -> Optional[float]:
    """Menor ``expires`` (epoch, em segundos) entre os cookies persistidos.

    Cookies de sessão têm ``expires == -1`` (sem validade fixa) e são ignorados.
    Retorna None se não houver nenhum cookie com validade explícita.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    exps = [
        c["expires"]
        for c in data.get("cookies", [])
        if isinstance(c.get("expires"), (int, float)) and c["expires"] > 0
    ]
    return min(exps) if exps else None


def _session_seconds_left(path: Path) -> Optional[float]:
    """Segundos restantes da sessão, considerando o TTL (mtime) E a expiração
    real dos cookies do Keycloak — o que vencer primeiro.

    Retorna None se não há sessão salva; valor <= 0 se expirada.
    """
    try:
        stat = path.stat()  # um único stat (evita corrida entre exists()+stat()).
    except (FileNotFoundError, OSError):
        return None
    now = time.time()
    ttl_left = SESSION_TTL_SECONDS - (now - stat.st_mtime)
    cookie_epoch = _cookie_expiry_epoch(path)
    if cookie_epoch is not None:
        return min(ttl_left, cookie_epoch - now)
    return ttl_left


def _session_fresh(path: Path) -> bool:
    left = _session_seconds_left(path)
    return left is not None and left > 0


def _save_diagnostics(page: Page, prefix: str) -> Optional[str]:
    """Salva screenshot + HTML da página. Retorna o nome base do arquivo."""
    try:
        stamp = str(int(time.time() * 1000))
        base = f"{prefix}_{stamp}"
        png = DIAG_DIR / f"{base}.png"
        html = DIAG_DIR / f"{base}.html"
        page.screenshot(path=str(png), full_page=True)
        html.write_text(page.content(), encoding="utf-8", errors="ignore")
        log.warning("Diagnóstico salvo: %s(.png/.html)", base)
        return base
    except Exception as e:  # nunca deixar o diagnóstico quebrar o fluxo
        log.error("Falha ao salvar diagnóstico: %s", e)
        return None


def _preencher_primeiro(page: Page, seletores: List[str], valor: str) -> bool:
    for sel in seletores:
        try:
            loc = page.locator(sel).first
            if loc.count() > 0 and loc.is_visible():
                loc.fill(valor)
                return True
        except Exception:
            continue
    return False


def _clicar_primeiro(page: Page, seletores: List[str]) -> bool:
    for sel in seletores:
        try:
            loc = page.locator(sel).first
            if loc.count() > 0 and loc.is_visible():
                loc.click()
                return True
        except Exception:
            continue
    return False


def _precisa_login(page: Page) -> bool:
    """Se há campo de senha visível, ainda estamos na tela de login."""
    try:
        return page.locator("input[type=password]").first.is_visible()
    except Exception:
        return False


def _tem_erro_login(page: Page) -> bool:
    texto = page.content().lower()
    return any(
        t in texto
        for t in ("senha inv", "credenc", "inválid", "incorret", "usuário ou senha")
    )


# Host do provedor de identidade (Keycloak). Enquanto a URL estiver nesse host,
# o login ainda não foi concluído.
AUTH_HOST = "auth.multiplike.app"


def _login(page: Page, email: str, senha: str, senha_secundaria: Optional[str]) -> None:
    page.goto(PORTAL_URL, wait_until="domcontentloaded")
    try:
        page.wait_for_load_state("networkidle", timeout=NAV_TIMEOUT)
    except PWTimeout:
        pass

    if AUTH_HOST not in page.url and not _precisa_login(page):
        log.info("Sessão reutilizada — login não necessário.")
        return

    # Portal usa Keycloak. Seletores confirmados via diagnóstico real
    # (data-testid do formulário de login).
    ok_email = _preencher_primeiro(page, SELECTORS["login"]["email"], email)
    ok_senha = _preencher_primeiro(page, SELECTORS["login"]["senha"], senha)
    if not (ok_email and ok_senha):
        _save_diagnostics(page, "login_campos")
        raise SeletorError(
            "Não foi possível localizar os campos de login. "
            "Ajuste os seletores em selectors.py."
        )

    _clicar_primeiro(page, SELECTORS["login"]["submit"])
    try:
        page.wait_for_load_state("networkidle", timeout=NAV_TIMEOUT)
    except PWTimeout:
        pass

    # Senha secundária / 2FA (opcional).
    if senha_secundaria and _precisa_login(page):
        campo2 = page.locator("input[type=password]").last
        try:
            if campo2.is_visible():
                campo2.fill(senha_secundaria)
                _clicar_primeiro(page, SELECTORS["login"]["confirmar_2fa"])
                page.wait_for_load_state("networkidle", timeout=NAV_TIMEOUT)
        except Exception:
            pass

    # Sucesso = saiu do host do Keycloak e voltou para o portal.
    if AUTH_HOST not in page.url and not _precisa_login(page):
        return

    _save_diagnostics(page, "login_falha")
    if _tem_erro_login(page):
        raise LoginError(
            "Login rejeitado pelo portal: usuário ou senha inválidos."
        )
    raise LoginError(
        "Login não concluído. Pode exigir 2FA/senha secundária ou etapa adicional."
    )


def status_sessao(email: str) -> dict:
    """Retorna o estado da sessão salva para o e-mail.

    {"ativa": bool, "expira_em_seg": int|None, "existe": bool}

    - existe=True + ativa=False  -> sessão EXPIRADA (arquivo presente, porém velho).
    - existe=False               -> nunca autenticou / logout.
    """
    path = _session_path(email)
    left = _session_seconds_left(path)
    if left is None or left <= 0:
        return {
            "ativa": False,
            "expira_em_seg": None,
            "existe": path.exists(),
        }
    return {"ativa": True, "expira_em_seg": int(left), "existe": True}


# Contador de reautenticações automáticas (observabilidade — item de métrica).
_reauth_count = 0


def garantir_sessao(
    email: str, senha: str, senha_secundaria: Optional[str] = None
) -> dict:
    """Detecta expiração e reautentica de forma transparente, se necessário.

    Se a sessão salva ainda estiver fresca, não faz nada e devolve o status atual.
    Caso contrário, refaz o login (via ``testar_login``, que persiste o novo
    ``storage_state``) e devolve o status atualizado.

    Levanta LoginError/SeletorError se a reautenticação falhar.
    """
    global _reauth_count
    path = _session_path(email)
    if _session_fresh(path):
        return status_sessao(email)
    _reauth_count += 1
    log.info(
        "Sessão expirada/ausente — reautenticando automaticamente "
        "(reauth #%s nesta execução).",
        _reauth_count,
    )
    testar_login(email, senha, senha_secundaria)
    return status_sessao(email)


def logout(email: str) -> None:
    """Apaga o storageState salvo, encerrando a sessão reutilizável."""
    path = _session_path(email)
    try:
        if path.exists():
            path.unlink()
            log.info("Sessão removida para o e-mail (hash) %s", path.stem)
    except Exception as e:
        log.error("Falha ao remover sessão: %s", e)


def testar_login(
    email: str, senha: str, senha_secundaria: Optional[str] = None
) -> None:
    """Testa apenas a autenticação no portal (sem buscar CNPJ).

    Levanta LoginError/SeletorError em caso de falha; retorna None em sucesso.
    Ignora a sessão salva para validar as credenciais de verdade.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        context = browser.new_context(
            user_agent=USER_AGENT, accept_downloads=True
        )
        context.set_default_timeout(NAV_TIMEOUT)
        page = context.new_page()
        try:
            _login(page, email, senha, senha_secundaria)
            # Persistir a sessão para reuso futuro nas buscas.
            try:
                context.storage_state(path=str(_session_path(email)))
            except Exception:
                pass
        finally:
            context.close()
            browser.close()


def _buscar_cnpj(page: Page, cnpj: str) -> None:
    # AJUSTAR: campo de busca de CNPJ
    ok = _preencher_primeiro(page, SELECTORS["busca_cnpj"]["input_cnpj"], cnpj)
    if not ok:
        ok = _preencher_primeiro(
            page, SELECTORS["busca_cnpj"]["input_cnpj_fallback"], _so_digitos(cnpj)
        )
    if not ok:
        _save_diagnostics(page, "busca_campo")
        raise SeletorError(
            "Campo de busca de CNPJ não encontrado. Ajuste os seletores em selectors.py."
        )

    _clicar_primeiro(page, SELECTORS["busca_cnpj"]["submit"])
    try:
        page.keyboard.press("Enter")
    except Exception:
        pass
    try:
        page.wait_for_load_state("networkidle", timeout=NAV_TIMEOUT)
    except PWTimeout:
        pass


def _resultado_vazio(page: Page, cnpj: str) -> bool:
    texto = page.content().lower()
    marcadores = (
        "nenhum resultado",
        "não encontrado",
        "nao encontrado",
        "sem registros",
        "nada encontrado",
        "0 resultados",
    )
    return any(m in texto for m in marcadores)


def _extrair_empresa(page: Page) -> Optional[str]:
    for sel in ["h1", "h2", "[class*=razao i]", "[class*=empresa i]"]:
        try:
            loc = page.locator(sel).first
            if loc.count() > 0:
                txt = (loc.inner_text() or "").strip()
                if txt:
                    return txt
        except Exception:
            continue
    return None


def _baixar_pdfs(page: Page, destino: Path) -> List[Path]:
    baixados: List[Path] = []
    seletores_doc = [
        "a[href$='.pdf']",
        "a[href*='.pdf']",
        "a:has-text('PDF')",
        "a:has-text('Baixar')",
        "button:has-text('Baixar')",
        "a:has-text('Download')",
        "[download]",
    ]
    elementos = []
    for sel in seletores_doc:
        loc = page.locator(sel)
        for i in range(loc.count()):
            elementos.append(loc.nth(i))
        if elementos:
            break

    for idx, el in enumerate(elementos):
        try:
            with page.expect_download(timeout=NAV_TIMEOUT) as di:
                el.click()
            download = di.value
            nome = download.suggested_filename or f"documento_{idx + 1}.pdf"
            caminho = destino / nome
            download.save_as(str(caminho))
            baixados.append(caminho)
            log.info("PDF baixado: %s", nome)
        except Exception:
            try:
                href = el.get_attribute("href")
                if href and ".pdf" in href.lower():
                    resp = page.request.get(href)
                    if resp.ok:
                        nome = href.split("/")[-1].split("?")[0] or f"documento_{idx + 1}.pdf"
                        caminho = destino / nome
                        caminho.write_bytes(resp.body())
                        baixados.append(caminho)
                        log.info("PDF baixado (href): %s", nome)
            except Exception as e:
                log.debug("Falha ao baixar elemento %s: %s", idx, e)
                continue
    return baixados


def _attempt(
    email: str,
    senha: str,
    senha_secundaria: Optional[str],
    cnpj: str,
    destino: Path,
    progress: ProgressCb,
) -> dict:
    session_file = _session_path(email)
    use_session = _session_fresh(session_file)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        ctx_kwargs = {"user_agent": USER_AGENT, "accept_downloads": True}
        if use_session:
            ctx_kwargs["storage_state"] = str(session_file)
        context = browser.new_context(**ctx_kwargs)
        context.set_default_timeout(NAV_TIMEOUT)
        page = context.new_page()
        try:
            progress("Acessando o portal e autenticando", 20)
            _login(page, email, senha, senha_secundaria)

            # Persistir a sessão para reuso futuro.
            try:
                context.storage_state(path=str(session_file))
            except Exception:
                pass

            progress("Buscando o CNPJ", 50)
            _buscar_cnpj(page, cnpj)

            if _resultado_vazio(page, cnpj):
                raise CnpjNaoEncontrado(
                    f"Nenhum resultado para o CNPJ {cnpj} no portal."
                )

            empresa = _extrair_empresa(page)
            progress("Baixando documentos", 75)
            arquivos = _baixar_pdfs(page, destino)
            if not arquivos:
                _save_diagnostics(page, "sem_pdfs")
                raise CnpjNaoEncontrado(
                    "Nenhum documento PDF encontrado para este CNPJ."
                )
            progress("Finalizando", 95)
            return {"empresa": empresa, "arquivos": [a.name for a in arquivos]}
        finally:
            context.close()
            browser.close()


def buscar_documentos_cnpj(
    email: str,
    senha: str,
    senha_secundaria: Optional[str],
    cnpj: str,
    destino: Path,
    progress: Optional[ProgressCb] = None,
) -> dict:
    """Fluxo completo com retry/backoff em erros transitórios."""
    progress = progress or (lambda step, pct: None)
    ultimo_erro: Optional[Exception] = None

    for tentativa in range(1, MAX_RETRIES + 2):
        try:
            log.info("Tentativa %s para CNPJ %s", tentativa, cnpj)
            return _attempt(email, senha, senha_secundaria, cnpj, destino, progress)
        except ScraperError:
            # Erros de negócio não devem ser repetidos (credenciais, CNPJ, seletor).
            raise
        except Exception as e:
            ultimo_erro = e
            log.warning("Erro transitório (tentativa %s): %s", tentativa, e)
            if tentativa <= MAX_RETRIES:
                time.sleep(2 ** tentativa)  # backoff exponencial: 2s, 4s...
                continue
            break

    raise ScraperError(f"Falha ao acessar o portal após retries: {ultimo_erro}")


def navegar_score_multiplike(
    email: str,
    senha: str,
    senha_secundaria: Optional[str],
    progress_cb: Optional[ProgressCb] = None,
    preview_cb: Optional[Callable[[Page], None]] = None,
) -> dict:
    """Navega pelo portal até a tela do Score Multiplike.

    Retorna um dicionário com o resultado e informações de diagnóstico.
    """
    progress = progress_cb or (lambda step, pct: None)

    current_step = "Iniciando"
    def set_step(step: str, pct: int):
        nonlocal current_step
        current_step = step
        progress(step, pct)

    session_file = _session_path(email)
    use_session = _session_fresh(session_file)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        ctx_kwargs = {"user_agent": USER_AGENT, "accept_downloads": True}
        if use_session:
            ctx_kwargs["storage_state"] = str(session_file)
        context = browser.new_context(**ctx_kwargs)
        context.set_default_timeout(NAV_TIMEOUT)
        page = context.new_page()
        try:
            set_step("Acessando o portal e verificando sessão", 20)
            _login(page, email, senha, senha_secundaria)
            if preview_cb:
                preview_cb(page)

            # Persistir a sessão para reuso futuro.
            try:
                context.storage_state(path=str(session_file))
            except Exception:
                pass

            set_step("Clicando em 'Ir para portal do cedente'", 60)
            try:
                page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass

            ok_cedente = _clicar_primeiro(page, SELECTORS["score_navigation"]["ir_para_cedente"])
            if preview_cb:
                preview_cb(page)

            if not ok_cedente:
                diag = _save_diagnostics(page, "perfil_cedente_erro")
                raise SeletorError(
                    "Botão 'Ir para portal do cedente' não encontrado na tela de seleção de perfil."
                )

            try:
                page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass

            set_step("Localizando card 'Score Multiplike'", 80)
            card_encontrado = False
            for selector in SELECTORS["score_navigation"]["card_containers"]:
                try:
                    locators = page.locator(selector).filter(has_text="Score Multiplike")
                    if locators.count() > 0:
                        card = locators.first
                        clique_aqui = card.locator("text='Clique aqui'").first
                        if clique_aqui.count() > 0 and clique_aqui.is_visible():
                            clique_aqui.click()
                            card_encontrado = True
                            if preview_cb:
                                preview_cb(page)
                            break
                        clique_aqui = card.locator("a, button").filter(has_text=re.compile("clique|aqui|acessar|ver", re.IGNORECASE)).first
                        if clique_aqui.count() > 0 and clique_aqui.is_visible():
                            clique_aqui.click()
                            card_encontrado = True
                            if preview_cb:
                                preview_cb(page)
                            break
                except Exception:
                    continue

            if not card_encontrado:
                ok_clique = _clicar_primeiro(page, SELECTORS["score_navigation"]["clique_aqui_fallback"])
                if preview_cb:
                    preview_cb(page)
                if not ok_clique:
                    diag = _save_diagnostics(page, "card_score_erro")
                    raise SeletorError(
                        "Card 'Score Multiplike' ou link 'Clique aqui' não encontrado no portal."
                    )

            try:
                page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass

            set_step("Tela de consulta alcançada", 100)
            if preview_cb:
                preview_cb(page)
            diag_sucesso = _save_diagnostics(page, "consulta_score_sucesso")
            return {"sucesso": True, "diagnostics_base": diag_sucesso}

        except Exception as e:
            if preview_cb:
                try:
                    preview_cb(page)
                except Exception:
                    pass
            diag = _save_diagnostics(page, "nav_score_falha")
            if isinstance(e, NavigationError):
                raise
            raise NavigationError(str(e), step=current_step, diagnostics_base=diag) from e
        finally:
            context.close()
            browser.close()

