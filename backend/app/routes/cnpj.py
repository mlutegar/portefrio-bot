from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, Response

from .. import db, jobs, secrets_store
from ..models import (
    BuscaRequest,
    HistoryItem,
    JobCreatedResponse,
    JobState,
)
from ..storage import file_by_index, zip_bytes

router = APIRouter()


@router.post("/cnpj/buscar", response_model=JobCreatedResponse, status_code=202)
async def buscar_cnpj(req: BuscaRequest) -> JobCreatedResponse:
    if not req.cnpj.strip():
        raise HTTPException(status_code=400, detail="CNPJ é obrigatório.")
    creds = secrets_store.carregar()
    if creds is None:
        raise HTTPException(
            status_code=400,
            detail="Credenciais do portal não configuradas. Cadastre em Configurações.",
        )
    job = await jobs.submit(req, creds)
    return JobCreatedResponse(job_id=job.job_id, status=job.status)


@router.get("/jobs/{job_id}", response_model=JobState)
async def status_job(job_id: str) -> JobState:
    job = jobs.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job não encontrado ou expirado.")
    return job


@router.get("/files/{job_id}/zip")
def baixar_zip(job_id: str):
    data = zip_bytes(job_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Nenhum arquivo para este job.")
    return Response(
        content=data,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="documentos-{job_id}.zip"'
        },
    )


@router.get("/files/{job_id}/{idx}")
def baixar_arquivo(job_id: str, idx: int):
    caminho = file_by_index(job_id, idx)
    if caminho is None:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado.")
    return FileResponse(
        path=str(caminho), media_type="application/pdf", filename=caminho.name
    )


@router.get("/history", response_model=list[HistoryItem])
def historico(
    email: str | None = Query(
        None, description="E-mail para filtrar; padrão = e-mail configurado no cofre"
    )
):
    alvo = email
    if not alvo:
        creds = secrets_store.carregar()
        if creds is None:
            return []
        alvo = creds["email"]
    return db.listar(alvo)
