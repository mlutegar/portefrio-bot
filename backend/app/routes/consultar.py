"""Rota POST /consultar — recebe email + senha + cnpj e devolve o JSON extraído."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException

from .. import jobs
from ..models import BuscaRequest, ConsultarRequest, ConsultarResponse
from ..scraper.portal import CnpjNaoEncontrado, LoginError
from ..concurrency import BusyError

router = APIRouter()

_TIMEOUT_SEGUNDOS = 180  # tempo máximo de espera pela conclusão do job


@router.post("/consultar", response_model=ConsultarResponse, tags=["consultar"])
async def consultar(req: ConsultarRequest):
    """
    Recebe email, senha e CNPJ. Executa o scraping completo e retorna
    os dados estruturados extraídos do PDF Score Multiplike.

    As credenciais são usadas apenas nesta requisição e não são salvas.
    """
    creds = {
        "email": req.email,
        "senha": req.senha,
        "senha_secundaria": None,
    }
    busca = BuscaRequest(cnpj=req.cnpj)

    try:
        job = await jobs.submit(busca, creds)
    except BusyError:
        raise HTTPException(
            status_code=429,
            detail="Servidor ocupado. Tente novamente em alguns segundos.",
        )

    # Aguarda o job terminar (polling interno)
    deadline = asyncio.get_event_loop().time() + _TIMEOUT_SEGUNDOS
    while True:
        if job.status.value == "done":
            return ConsultarResponse(
                cnpj=job.result.cnpj,
                empresa=job.result.empresa,
                dados_extraidos=job.result.dados_extraidos,
            )
        if job.status.value == "error":
            err = job.error or "Erro desconhecido"
            if "login" in err.lower() or "credencial" in err.lower() or "senha" in err.lower():
                raise HTTPException(status_code=401, detail=err)
            if "não encontrado" in err.lower() or "cnpj" in err.lower():
                raise HTTPException(status_code=404, detail=err)
            raise HTTPException(status_code=422, detail=err)
        if asyncio.get_event_loop().time() > deadline:
            raise HTTPException(
                status_code=504,
                detail=f"Timeout: o scraping não concluiu em {_TIMEOUT_SEGUNDOS}s.",
            )
        await asyncio.sleep(1)
