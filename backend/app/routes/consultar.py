"""Rota POST /consultar — recebe email + senha + cnpj e devolve o JSON extraído.

Funcionalidades:
- Autenticação via X-API-Key (se API_KEY configurado no .env)
- Rate limiting por IP
- Cache de resultado por CNPJ (TTL configurável)
- Retry automático em falhas transitórias
- Webhook opcional: POST no callback_url ao concluir
- GET /consultar/{cnpj}/ultimo — último resultado em cache
"""
from __future__ import annotations

import asyncio
import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Security
from fastapi.security.api_key import APIKeyHeader
from slowapi import Limiter
from slowapi.util import get_remote_address

from .. import db, jobs
from ..config import API_KEY, CONSULTAR_TIMEOUT_SECONDS, RATE_LIMIT
from ..concurrency import BusyError
from ..models import BuscaRequest, ConsultarRequest, ConsultarResponse, ScoreData

log = logging.getLogger("consultar")

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

_MAX_RETRIES = 2  # tentativas automáticas em falhas transitórias


# ---------------------------------------------------------------------------
# Dependência: verificação de API Key
# ---------------------------------------------------------------------------

async def _verificar_api_key(api_key: str = Security(_api_key_header)) -> None:
    """Se API_KEY estiver configurado, exige o header X-API-Key correto."""
    if not API_KEY:
        return  # sem chave configurada = modo dev aberto
    if api_key != API_KEY:
        raise HTTPException(status_code=401, detail="API Key inválida ou ausente.")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _e_erro_transitorio(mensagem: str) -> bool:
    """Determina se o erro é candidato a retry."""
    termos = ["timeout", "network", "connection", "playwright", "falha inesperada"]
    return any(t in mensagem.lower() for t in termos)


async def _aguardar_job(job, timeout: int = CONSULTAR_TIMEOUT_SECONDS):
    """Polling interno até o job terminar ou timeout."""
    deadline = asyncio.get_event_loop().time() + timeout
    while True:
        if job.status.value == "done":
            return job
        if job.status.value == "error":
            raise RuntimeError(job.error or "Erro desconhecido no scraping")
        if asyncio.get_event_loop().time() > deadline:
            raise TimeoutError(f"Scraping não concluiu em {timeout}s")
        await asyncio.sleep(1)


async def _disparar_webhook(url: str, payload: dict) -> None:
    """Envia o resultado para o callback_url em background (fire-and-forget)."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(url, json=payload)
            log.info("Webhook enviado para %s — status %s", url, r.status_code)
    except Exception as exc:
        log.warning("Falha ao enviar webhook para %s: %s", url, exc)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/consultar",
    response_model=ConsultarResponse,
    tags=["consultar"],
    summary="Consulta CNPJ e retorna dados extraídos",
    description=(
        "Recebe credenciais do portal e um CNPJ. Executa o scraping completo, "
        "extrai os dados do PDF Score Multiplike e devolve o JSON estruturado. "
        "As credenciais não são armazenadas. Suporta cache por CNPJ e webhook opcional."
    ),
)
@limiter.limit(RATE_LIMIT)
async def consultar(
    request: Request,
    req: ConsultarRequest,
    _: None = Depends(_verificar_api_key),
):
    cnpj_norm = req.cnpj.strip()

    # 1. Verifica cache
    cache = db.buscar_cache(cnpj_norm)
    if cache:
        log.info("Cache hit para CNPJ %s (idade: %ds)", cnpj_norm, cache["idade_segundos"])
        score = ScoreData(**cache["resultado"]) if cache["resultado"] else None
        return ConsultarResponse(
            cnpj=cache["cnpj"],
            empresa=cache["empresa"],
            dados_extraidos=score,
            cached=True,
            idade_cache_segundos=cache["idade_segundos"],
        )

    # 2. Executa scraping com retry automático
    creds = {"email": req.email, "senha": req.senha, "senha_secundaria": None}
    busca = BuscaRequest(cnpj=cnpj_norm)
    ultimo_erro = None

    for tentativa in range(1, _MAX_RETRIES + 1):
        try:
            job = await jobs.submit(busca, creds)
            await _aguardar_job(job)
            break
        except BusyError:
            raise HTTPException(
                status_code=429,
                detail="Servidor ocupado. Tente novamente em alguns segundos.",
            )
        except TimeoutError as exc:
            raise HTTPException(status_code=504, detail=str(exc))
        except RuntimeError as exc:
            err = str(exc)
            if "login" in err.lower() or "credencial" in err.lower() or "senha" in err.lower():
                raise HTTPException(status_code=401, detail=err)
            if "não encontrado" in err.lower():
                raise HTTPException(status_code=404, detail=err)
            if not _e_erro_transitorio(err) or tentativa == _MAX_RETRIES:
                raise HTTPException(status_code=422, detail=err)
            log.warning("Tentativa %d/%d falhou (%s) — tentando novamente...", tentativa, _MAX_RETRIES, err)
            ultimo_erro = err
            await asyncio.sleep(2 * tentativa)
    else:
        raise HTTPException(status_code=422, detail=ultimo_erro or "Erro no scraping")

    result = job.result
    dados = result.dados_extraidos

    # 3. Salva no cache
    if dados:
        db.salvar_cache(
            cnpj=result.cnpj,
            empresa=result.empresa,
            resultado=dados.model_dump(),
        )

    # 4. Dispara webhook se fornecido
    if req.callback_url:
        payload = ConsultarResponse(
            cnpj=result.cnpj,
            empresa=result.empresa,
            dados_extraidos=dados,
        ).model_dump()
        asyncio.create_task(_disparar_webhook(req.callback_url, payload))

    return ConsultarResponse(
        cnpj=result.cnpj,
        empresa=result.empresa,
        dados_extraidos=dados,
        cached=False,
    )


@router.get(
    "/consultar/{cnpj}/ultimo",
    response_model=ConsultarResponse,
    tags=["consultar"],
    summary="Último resultado em cache para um CNPJ",
    description="Retorna o último resultado já extraído para o CNPJ informado, sem re-scraping.",
)
async def ultimo_resultado(
    cnpj: str,
    _: None = Depends(_verificar_api_key),
):
    cache = db.buscar_cache(cnpj.strip())
    if not cache:
        raise HTTPException(
            status_code=404,
            detail="Nenhum resultado em cache para este CNPJ. Faça uma consulta primeiro.",
        )
    score = ScoreData(**cache["resultado"]) if cache["resultado"] else None
    return ConsultarResponse(
        cnpj=cache["cnpj"],
        empresa=cache["empresa"],
        dados_extraidos=score,
        cached=True,
        idade_cache_segundos=cache["idade_segundos"],
    )
