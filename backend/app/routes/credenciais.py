from __future__ import annotations

import asyncio

from fastapi import APIRouter

from .. import secrets_store
from ..concurrency import BusyError, browser_slot
from ..logging_config import get_logger
from ..models import (
    CredenciaisInput,
    CredenciaisStatus,
    SalvarCredenciaisResponse,
)
from ..scraper.portal import ScraperError, testar_login

log = get_logger("routes.credenciais")

router = APIRouter()


@router.get("/credenciais", response_model=CredenciaisStatus)
def status_credenciais() -> CredenciaisStatus:
    creds = secrets_store.carregar()
    if creds is None:
        return CredenciaisStatus(configurado=False)
    return CredenciaisStatus(
        configurado=True,
        email_mascarado=secrets_store.mascarar_email(creds["email"]),
    )


@router.post("/credenciais/salvar-e-testar", response_model=SalvarCredenciaisResponse)
async def salvar_e_testar(inp: CredenciaisInput) -> SalvarCredenciaisResponse:
    if not inp.email.strip() or not inp.senha.strip():
        return SalvarCredenciaisResponse(
            ok=False, mensagem="E-mail e senha são obrigatórios."
        )

    loop = asyncio.get_running_loop()
    try:
        async with browser_slot(wait=False):
            await loop.run_in_executor(
                None,
                lambda: testar_login(inp.email, inp.senha, inp.senha_secundaria),
            )
    except BusyError as e:
        return SalvarCredenciaisResponse(ok=False, mensagem=str(e))
    except ScraperError as e:
        log.info("Teste de credenciais falhou: %s", e)
        return SalvarCredenciaisResponse(ok=False, mensagem=str(e))
    except Exception as e:
        log.exception("Erro inesperado no teste de credenciais")
        return SalvarCredenciaisResponse(
            ok=False, mensagem=f"Falha ao testar conexão: {e}"
        )

    # Só grava se o login foi validado.
    secrets_store.salvar(inp.email, inp.senha, inp.senha_secundaria)
    return SalvarCredenciaisResponse(ok=True, mensagem="Credenciais válidas")


@router.delete("/credenciais", response_model=CredenciaisStatus)
def apagar_credenciais() -> CredenciaisStatus:
    secrets_store.apagar()
    return CredenciaisStatus(configurado=False)
