from __future__ import annotations

import asyncio
import time
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .. import db, secrets_store
from ..concurrency import BusyError, browser_slot
from ..logging_config import get_logger
from ..models import LoginResponse, ScoreHistoryItem, SessaoStatus
from ..scraper.portal import (
    NavigationError,
    ScraperError,
    garantir_sessao,
    logout,
    navegar_score_multiplike,
    status_sessao,
    testar_login,
)



log = get_logger("routes.portal")

router = APIRouter()


def _status_para(email: str) -> SessaoStatus:
    s = status_sessao(email)
    return SessaoStatus(
        ativa=s["ativa"],
        expira_em_seg=s["expira_em_seg"],
        existe=s.get("existe", False),
        email_mascarado=secrets_store.mascarar_email(email),
    )


@router.get("/portal/session", response_model=SessaoStatus)
def sessao() -> SessaoStatus:
    creds = secrets_store.carregar()
    if creds is None:
        return SessaoStatus(ativa=False)
    return _status_para(creds["email"])


@router.post("/portal/login", response_model=LoginResponse)
async def login() -> LoginResponse:
    creds = secrets_store.carregar()
    if creds is None:
        raise HTTPException(
            status_code=400,
            detail="Credenciais do portal não configuradas. Cadastre em Credenciais.",
        )

    loop = asyncio.get_running_loop()
    try:
        # wait=False: se já há uma autenticação em andamento, não enfileira
        # (evita duplo-clique disparar vários navegadores).
        async with browser_slot(wait=False):
            await loop.run_in_executor(
                None,
                lambda: testar_login(
                    creds["email"], creds["senha"], creds.get("senha_secundaria")
                ),
            )
    except BusyError as e:
        return LoginResponse(
            ok=False, mensagem=str(e), sessao=_status_para(creds["email"])
        )
    except ScraperError as e:
        log.info("Login no portal falhou: %s", e)
        return LoginResponse(
            ok=False, mensagem=str(e), sessao=_status_para(creds["email"])
        )
    except Exception as e:
        log.exception("Erro inesperado no login do portal")
        return LoginResponse(
            ok=False,
            mensagem=f"Falha ao autenticar: {e}",
            sessao=_status_para(creds["email"]),
        )

    return LoginResponse(
        ok=True, mensagem="Sessão ativa", sessao=_status_para(creds["email"])
    )


@router.post("/portal/session/ensure", response_model=LoginResponse)
async def ensure() -> LoginResponse:
    """Reautentica apenas se a sessão estiver expirada/ausente.

    Diferente de ``/portal/login`` (que sempre força novo login), este endpoint é
    idempotente: se a sessão ainda estiver ativa, não abre navegador — apenas
    devolve o status atual. Usado pelo badge do front para reautenticar sozinho.
    """
    creds = secrets_store.carregar()
    if creds is None:
        raise HTTPException(
            status_code=400,
            detail="Credenciais do portal não configuradas. Cadastre em Credenciais.",
        )

    # Se já está ativa, nem entra na fila do navegador.
    if status_sessao(creds["email"])["ativa"]:
        return LoginResponse(
            ok=True, mensagem="Sessão ativa", sessao=_status_para(creds["email"])
        )

    loop = asyncio.get_running_loop()
    try:
        # wait=False: evita disparar vários navegadores em polls concorrentes.
        async with browser_slot(wait=False):
            await loop.run_in_executor(
                None,
                lambda: garantir_sessao(
                    creds["email"], creds["senha"], creds.get("senha_secundaria")
                ),
            )
    except BusyError as e:
        # Já há uma (re)autenticação em andamento — não é erro.
        return LoginResponse(
            ok=False, mensagem=str(e), sessao=_status_para(creds["email"])
        )
    except ScraperError as e:
        log.info("Reautenticação automática falhou: %s", e)
        return LoginResponse(
            ok=False, mensagem=str(e), sessao=_status_para(creds["email"])
        )
    except Exception as e:
        log.exception("Erro inesperado na reautenticação automática")
        return LoginResponse(
            ok=False,
            mensagem=f"Falha ao reautenticar: {e}",
            sessao=_status_para(creds["email"]),
        )

    return LoginResponse(
        ok=True, mensagem="Sessão reautenticada", sessao=_status_para(creds["email"])
    )


@router.delete("/portal/session", response_model=SessaoStatus)
def encerrar() -> SessaoStatus:
    creds = secrets_store.carregar()
    if creds is None:
        return SessaoStatus(ativa=False)
    logout(creds["email"])
    return _status_para(creds["email"])


class ScoreNavigationStatus(BaseModel):
    status: str
    step: str
    progress: int = 0
    error: Optional[str] = None
    diagnostics_base: Optional[str] = None
    live_preview: Optional[str] = None
    updated_at: float


_score_nav_state = {
    "status": "idle",
    "step": "Nenhuma navegação iniciada",
    "progress": 0,
    "error": None,
    "diagnostics_base": None,
    "live_preview": None,
    "updated_at": 0.0,
}



async def _run_score_nav(creds: dict):
    global _score_nav_state
    _score_nav_state["status"] = "running"
    _score_nav_state["step"] = "Iniciando"
    _score_nav_state["progress"] = 5
    _score_nav_state["error"] = None
    _score_nav_state["diagnostics_base"] = None
    _score_nav_state["live_preview"] = None
    _score_nav_state["updated_at"] = time.time()

    loop = asyncio.get_running_loop()

    def progress(step: str, pct: int):
        _score_nav_state["step"] = step
        _score_nav_state["progress"] = pct
        _score_nav_state["updated_at"] = time.time()
        log.info("Progresso da navegação Score: %s (%s%%)", step, pct)

    def update_preview(page):
        try:
            img_bytes = page.screenshot(type="jpeg", quality=50)
            import base64
            base64_str = base64.b64encode(img_bytes).decode("utf-8")
            _score_nav_state["live_preview"] = f"data:image/jpeg;base64,{base64_str}"
            _score_nav_state["updated_at"] = time.time()
        except Exception:
            pass

    try:
        def run_scraper():
            garantir_sessao(
                creds["email"],
                creds["senha"],
                creds.get("senha_secundaria"),
            )
            return navegar_score_multiplike(
                creds["email"],
                creds["senha"],
                creds.get("senha_secundaria"),
                progress,
                update_preview,
            )

        res = await loop.run_in_executor(None, run_scraper)
        _score_nav_state["status"] = "done"
        _score_nav_state["step"] = "Tela de consulta alcançada"
        _score_nav_state["progress"] = 100
        _score_nav_state["diagnostics_base"] = res.get("diagnostics_base")
        _score_nav_state["updated_at"] = time.time()

        # Registrar sucesso no banco de dados
        db.registrar_navegacao_score(
            email=creds["email"],
            status="done",
            ultimo_passo=_score_nav_state["step"],
            diagnostics_base=res.get("diagnostics_base"),
        )
    except NavigationError as e:
        _score_nav_state["status"] = "error"
        _score_nav_state["step"] = e.step
        _score_nav_state["error"] = str(e)
        _score_nav_state["diagnostics_base"] = e.diagnostics_base
        _score_nav_state["updated_at"] = time.time()

        # Registrar erro no banco de dados
        db.registrar_navegacao_score(
            email=creds["email"],
            status="error",
            ultimo_passo=e.step,
            error=str(e),
            diagnostics_base=e.diagnostics_base,
        )
        log.warning("Navegação Score falhou no passo %s: %s", e.step, e)
    except ScraperError as e:
        _score_nav_state["status"] = "error"
        _score_nav_state["error"] = str(e)
        _score_nav_state["updated_at"] = time.time()

        # Registrar erro no banco de dados
        db.registrar_navegacao_score(
            email=creds["email"],
            status="error",
            ultimo_passo=_score_nav_state["step"],
            error=str(e),
        )
        log.warning("Erro de scraper na navegação Score: %s", e)
    except Exception as e:
        _score_nav_state["status"] = "error"
        _score_nav_state["error"] = f"Falha inesperada: {e}"
        _score_nav_state["updated_at"] = time.time()

        # Registrar erro no banco de dados
        db.registrar_navegacao_score(
            email=creds["email"],
            status="error",
            ultimo_passo=_score_nav_state["step"],
            error=f"Falha inesperada: {e}",
        )
        log.exception("Erro inesperado na navegação Score")



@router.post("/portal/score-navigation", response_model=ScoreNavigationStatus)
async def iniciar_score_navigation() -> ScoreNavigationStatus:
    global _score_nav_state
    creds = secrets_store.carregar()
    if creds is None:
        raise HTTPException(
            status_code=400,
            detail="Credenciais do portal não configuradas. Cadastre em Credenciais.",
        )

    if _score_nav_state["status"] == "running":
        return ScoreNavigationStatus(**_score_nav_state)

    try:
        async with browser_slot(wait=False):
            pass
    except BusyError as e:
        raise HTTPException(
            status_code=429,
            detail="O servidor de navegadores está ocupado. Tente em instantes.",
        )

    async def task_wrapper():
        try:
            async with browser_slot(wait=True):
                await _run_score_nav(creds)
        except BusyError as e:
            _score_nav_state["status"] = "error"
            _score_nav_state["step"] = "Servidor ocupado"
            _score_nav_state["error"] = str(e)
            _score_nav_state["updated_at"] = time.time()

    asyncio.create_task(task_wrapper())

    _score_nav_state["status"] = "running"
    _score_nav_state["step"] = "Iniciando"
    _score_nav_state["progress"] = 5
    _score_nav_state["error"] = None
    _score_nav_state["diagnostics_base"] = None
    _score_nav_state["live_preview"] = None
    _score_nav_state["updated_at"] = time.time()

    return ScoreNavigationStatus(**_score_nav_state)


@router.get("/portal/score-navigation", response_model=ScoreNavigationStatus)
def obter_score_navigation() -> ScoreNavigationStatus:
    return ScoreNavigationStatus(**_score_nav_state)


@router.get("/portal/diagnostics/{base_name}/{ext}")
def obter_diagnostico(base_name: str, ext: str):
    if ext not in ("png", "html"):
        raise HTTPException(status_code=400, detail="Extensão inválida. Use png ou html.")

    import re
    if not re.match(r"^[a-zA-Z0-9_\-]+$", base_name):
        raise HTTPException(status_code=400, detail="Nome de arquivo inválido.")

    from ..config import DIAG_DIR
    filename = f"{base_name}.{ext}"
    caminho = DIAG_DIR / filename
    if not caminho.exists():
        raise HTTPException(status_code=404, detail="Arquivo de diagnóstico não encontrado.")

    media_type = "image/png" if ext == "png" else "text/html"
    return FileResponse(str(caminho), media_type=media_type, filename=filename)


@router.get("/portal/score-navigation/history", response_model=list[ScoreHistoryItem])
def obter_historico_score(
    email: str | None = Query(
        None, description="E-mail para filtrar; padrão = e-mail configurado no cofre"
    )
) -> list[ScoreHistoryItem]:
    alvo = email
    if not alvo:
        creds = secrets_store.carregar()
        if creds is None:
            return []
        alvo = creds["email"]
    return db.listar_historico_score(alvo)


