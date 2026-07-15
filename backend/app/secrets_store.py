"""Cofre de credenciais do portal — cifradas em repouso com Fernet.

As credenciais NUNCA são guardadas em texto claro: são cifradas com uma
chave-mestra (CREDENTIALS_KEY) e persistidas na tabela `credenciais` do SQLite.
Apenas um registro (`id="default"`) é usado — a conta de serviço do portal.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, TypedDict

from cryptography.fernet import Fernet, InvalidToken

from . import db
from .config import CREDENTIALS_KEY, SECRET_KEY_FILE
from .logging_config import get_logger

log = get_logger("secrets_store")

_DEFAULT_ID = "default"
_fernet: Optional[Fernet] = None


class Credenciais(TypedDict):
    email: str
    senha: str
    senha_secundaria: Optional[str]


def _get_fernet() -> Fernet:
    """Carrega/gera a chave-mestra. Preferência: env var; fallback dev: arquivo."""
    global _fernet
    if _fernet is not None:
        return _fernet

    key: Optional[bytes] = None
    if CREDENTIALS_KEY:
        key = CREDENTIALS_KEY.encode()
    elif SECRET_KEY_FILE.exists():
        key = SECRET_KEY_FILE.read_bytes().strip()
    else:
        key = Fernet.generate_key()
        try:
            SECRET_KEY_FILE.write_bytes(key)
            log.warning(
                "CREDENTIALS_KEY não definida — chave de dev gerada em %s. "
                "NÃO use isso em produção; defina CREDENTIALS_KEY no ambiente.",
                SECRET_KEY_FILE,
            )
        except Exception as e:
            log.error("Falha ao persistir chave de dev: %s", e)

    _fernet = Fernet(key)
    return _fernet


def _enc(valor: str) -> bytes:
    return _get_fernet().encrypt(valor.encode())


def _dec(dado: Optional[bytes]) -> Optional[str]:
    if dado is None:
        return None
    return _get_fernet().decrypt(bytes(dado)).decode()


def salvar(email: str, senha: str, senha_secundaria: Optional[str]) -> None:
    senha2_enc = _enc(senha_secundaria) if senha_secundaria else None
    with db._conn() as c:
        c.execute(
            """
            INSERT OR REPLACE INTO credenciais
                (id, email_enc, senha_enc, senha2_enc, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                _DEFAULT_ID,
                _enc(email),
                _enc(senha),
                senha2_enc,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
    log.info("Credenciais do portal atualizadas no cofre.")


def carregar() -> Optional[Credenciais]:
    with db._conn() as c:
        row = c.execute(
            "SELECT email_enc, senha_enc, senha2_enc FROM credenciais WHERE id = ?",
            (_DEFAULT_ID,),
        ).fetchone()
    if row is None:
        return None
    try:
        return Credenciais(
            email=_dec(row["email_enc"]),
            senha=_dec(row["senha_enc"]),
            senha_secundaria=_dec(row["senha2_enc"]),
        )
    except InvalidToken:
        log.error(
            "Falha ao decifrar credenciais — CREDENTIALS_KEY provavelmente mudou. "
            "Recadastre as credenciais."
        )
        return None


def existe() -> bool:
    with db._conn() as c:
        row = c.execute(
            "SELECT 1 FROM credenciais WHERE id = ?", (_DEFAULT_ID,)
        ).fetchone()
    return row is not None


def apagar() -> None:
    with db._conn() as c:
        c.execute("DELETE FROM credenciais WHERE id = ?", (_DEFAULT_ID,))
    log.info("Credenciais do portal removidas do cofre.")


def mascarar_email(email: str) -> str:
    """joao.silva@x.com -> jo***@x.com (não expõe o e-mail completo)."""
    try:
        local, dominio = email.split("@", 1)
    except ValueError:
        return "***"
    visivel = local[:2]
    return f"{visivel}{'*' * max(3, len(local) - 2)}@{dominio}"
