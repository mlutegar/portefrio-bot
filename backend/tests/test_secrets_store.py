"""Testa o cofre de credenciais: roundtrip cifrado e mascaramento."""
from __future__ import annotations

import pytest
from cryptography.fernet import Fernet

from app import db, secrets_store


@pytest.fixture()
def cofre(monkeypatch, tmp_path):
    # DB temporário e chave Fernet fixa para o teste.
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    fernet = Fernet(Fernet.generate_key())
    monkeypatch.setattr(secrets_store, "_get_fernet", lambda: fernet)
    db.init_db()
    yield


def test_roundtrip(cofre):
    assert secrets_store.existe() is False
    secrets_store.salvar("joao@x.com", "senha123", "2fa")
    assert secrets_store.existe() is True

    creds = secrets_store.carregar()
    assert creds == {
        "email": "joao@x.com",
        "senha": "senha123",
        "senha_secundaria": "2fa",
    }


def test_persistencia_cifrada(cofre):
    secrets_store.salvar("joao@x.com", "segredo", None)
    # Lê o valor bruto no banco: não pode conter a senha em texto claro.
    with db._conn() as c:
        row = c.execute(
            "SELECT senha_enc FROM credenciais WHERE id = 'default'"
        ).fetchone()
    assert b"segredo" not in bytes(row["senha_enc"])


def test_apagar(cofre):
    secrets_store.salvar("joao@x.com", "s", None)
    secrets_store.apagar()
    assert secrets_store.existe() is False
    assert secrets_store.carregar() is None


def test_mascarar_email():
    m = secrets_store.mascarar_email("financeiro@portefrio.com")
    assert m.endswith("@portefrio.com")
    assert m.startswith("fi")
    assert "financeiro" not in m
