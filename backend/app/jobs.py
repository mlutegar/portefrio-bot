"""Gerenciador de jobs assíncronos de scraping.

- Fila com worker que respeita um semáforo de concorrência.
- Cada job tem status/progresso consultável por polling.
- Limpeza periódica de jobs e arquivos antigos (TTL).
"""
from __future__ import annotations

import asyncio
import shutil
import time
from datetime import datetime, timezone
from typing import Dict, Optional

from . import db
from .concurrency import browser_slot
from .config import (
    CLEANUP_INTERVAL_SECONDS,
    DIAG_DIR,
    DIAGNOSTICS_TTL_SECONDS,
    JOB_TTL_SECONDS,
)

from .logging_config import get_logger
from .models import (
    BuscaRequest,
    DocumentoInfo,
    JobResult,
    JobState,
    JobStatus,
)
from .scraper.portal import ScraperError, buscar_documentos_cnpj
from .secrets_store import Credenciais
from .storage import job_dir, new_job_dir

log = get_logger("jobs")

_jobs: Dict[str, JobState] = {}


def _now() -> float:
    return time.time()


def get_job(job_id: str) -> Optional[JobState]:
    return _jobs.get(job_id)


def _set(job: JobState, **kwargs) -> None:
    for k, v in kwargs.items():
        setattr(job, k, v)
    job.updated_at = _now()


async def submit(req: BuscaRequest, creds: Credenciais) -> JobState:
    job_id, _ = new_job_dir()
    job = JobState(
        job_id=job_id,
        status=JobStatus.pending,
        step="Na fila",
        progress=0,
        cnpj=req.cnpj,
        email=creds["email"],
        created_at=_now(),
        updated_at=_now(),
    )
    _jobs[job_id] = job
    asyncio.create_task(_run(job, req, creds))
    return job


async def _run(job: JobState, req: BuscaRequest, creds: Credenciais) -> None:
    # Compartilha o mesmo teto de navegadores de login/teste de credenciais.
    async with browser_slot(wait=True):
        _set(job, status=JobStatus.running, step="Iniciando", progress=5)
        loop = asyncio.get_running_loop()

        def progress(step: str, pct: int) -> None:
            # chamado de dentro da thread do Playwright; atribuições simples são
            # thread-safe o suficiente para atualizar o estado consultável.
            job.step = step
            job.progress = pct
            job.updated_at = _now()

        destino = job_dir(job.job_id)
        try:
            resultado = await loop.run_in_executor(
                None,
                lambda: buscar_documentos_cnpj(
                    creds["email"],
                    creds["senha"],
                    creds.get("senha_secundaria"),
                    req.cnpj,
                    destino,
                    progress,
                ),
            )
            documentos = []
            for idx, nome in enumerate(resultado["arquivos"]):
                caminho = destino / nome
                documentos.append(
                    DocumentoInfo(
                        nome=nome,
                        tamanho=caminho.stat().st_size if caminho.exists() else 0,
                        download_url=f"/files/{job.job_id}/{idx}",
                    )
                )
            result = JobResult(
                cnpj=req.cnpj,
                empresa=resultado.get("empresa"),
                documentos=documentos,
                gerado_em=datetime.now(timezone.utc).isoformat(),
                job_id=job.job_id,
            )
            _set(job, status=JobStatus.done, step="Concluído", progress=100, result=result)
            db.registrar(
                job.job_id, req.cnpj, creds["email"], result.empresa, "done", len(documentos)
            )
            log.info("Job %s concluído: %s documentos", job.job_id, len(documentos))
        except ScraperError as e:
            _set(job, status=JobStatus.error, step="Erro", error=str(e))
            db.registrar(job.job_id, req.cnpj, creds["email"], None, "error", 0)
            log.warning("Job %s erro de negócio: %s", job.job_id, e)
        except Exception as e:
            _set(
                job,
                status=JobStatus.error,
                step="Erro",
                error=f"Falha inesperada: {e}",
            )
            db.registrar(job.job_id, req.cnpj, creds["email"], None, "error", 0)
            log.exception("Job %s erro inesperado", job.job_id)


async def cleanup_loop() -> None:
    """Remove jobs, arquivos e diagnósticos mais antigos que o TTL."""
    while True:
        try:
            agora = _now()
            # 1. Limpeza de jobs expirados
            expirados = [
                jid
                for jid, j in _jobs.items()
                if agora - j.created_at > JOB_TTL_SECONDS
            ]
            for jid in expirados:
                _jobs.pop(jid, None)
                d = job_dir(jid)
                if d.exists():
                    shutil.rmtree(d, ignore_errors=True)
            if expirados:
                log.info("Limpeza: %s jobs expirados removidos", len(expirados))

            # 2. Limpeza de diagnósticos antigos
            if DIAG_DIR.exists():
                diag_expirados = 0
                for f in DIAG_DIR.iterdir():
                    if f.is_file() and f.suffix in (".png", ".html"):
                        try:
                            mtime = f.stat().st_mtime
                            if agora - mtime > DIAGNOSTICS_TTL_SECONDS:
                                f.unlink()
                                diag_expirados += 1
                        except Exception:
                            pass
                if diag_expirados > 0:
                    log.info("Limpeza: %s arquivos de diagnóstico antigos removidos", diag_expirados)

        except Exception:
            log.exception("Erro no loop de limpeza")
        await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)

