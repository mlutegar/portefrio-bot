from __future__ import annotations

import io
import uuid
import zipfile
from pathlib import Path
from typing import List

from .config import STORAGE_DIR


def new_job_dir() -> tuple[str, Path]:
    """Cria uma pasta única para os arquivos de um job e retorna (job_id, path)."""
    job_id = uuid.uuid4().hex
    path = STORAGE_DIR / job_id
    path.mkdir(parents=True, exist_ok=True)
    return job_id, path


def job_dir(job_id: str) -> Path:
    return STORAGE_DIR / job_id


def list_files(job_id: str) -> List[Path]:
    d = job_dir(job_id)
    if not d.exists():
        return []
    return sorted(p for p in d.iterdir() if p.is_file())


def file_by_index(job_id: str, idx: int) -> Path | None:
    files = list_files(job_id)
    if 0 <= idx < len(files):
        return files[idx]
    return None


def zip_bytes(job_id: str) -> bytes | None:
    """Empacota todos os PDFs de um job em um ZIP em memória."""
    files = list_files(job_id)
    if not files:
        return None
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            zf.write(f, arcname=f.name)
    buf.seek(0)
    return buf.read()
