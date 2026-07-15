"""Testa a lógica de sessão persistente e reautenticação automática.

Não acessa o portal nem sobe Chromium: mocka o arquivo de sessão e o ``testar_login``.
"""
from __future__ import annotations

import time

from app.scraper import portal


def _touch(path, age_seconds=0.0):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{}", encoding="utf-8")
    if age_seconds:
        antigo = time.time() - age_seconds
        import os

        os.utime(path, (antigo, antigo))


def test_status_sem_sessao(monkeypatch, tmp_path):
    path = tmp_path / "sess.json"
    monkeypatch.setattr(portal, "_session_path", lambda email: path)
    s = portal.status_sessao("joao@x.com")
    assert s == {"ativa": False, "expira_em_seg": None, "existe": False}


def test_status_expirada(monkeypatch, tmp_path):
    path = tmp_path / "sess.json"
    monkeypatch.setattr(portal, "_session_path", lambda email: path)
    monkeypatch.setattr(portal, "SESSION_TTL_SECONDS", 60)
    _touch(path, age_seconds=120)  # mais velho que o TTL -> expirada
    s = portal.status_sessao("joao@x.com")
    assert s["existe"] is True and s["ativa"] is False


def test_status_ativa(monkeypatch, tmp_path):
    path = tmp_path / "sess.json"
    monkeypatch.setattr(portal, "_session_path", lambda email: path)
    monkeypatch.setattr(portal, "SESSION_TTL_SECONDS", 600)
    _touch(path, age_seconds=0)
    s = portal.status_sessao("joao@x.com")
    assert s["ativa"] is True and s["existe"] is True
    assert s["expira_em_seg"] > 0


def test_garantir_sessao_nao_reautentica_quando_fresca(monkeypatch, tmp_path):
    path = tmp_path / "sess.json"
    monkeypatch.setattr(portal, "_session_path", lambda email: path)
    monkeypatch.setattr(portal, "SESSION_TTL_SECONDS", 600)
    _touch(path, age_seconds=0)
    chamado = {"n": 0}

    def fake_login(*a, **k):
        chamado["n"] += 1

    monkeypatch.setattr(portal, "testar_login", fake_login)
    s = portal.garantir_sessao("joao@x.com", "senha", None)
    assert chamado["n"] == 0  # não reautenticou
    assert s["ativa"] is True


def test_garantir_sessao_reautentica_quando_expirada(monkeypatch, tmp_path):
    path = tmp_path / "sess.json"
    monkeypatch.setattr(portal, "_session_path", lambda email: path)
    monkeypatch.setattr(portal, "SESSION_TTL_SECONDS", 60)
    _touch(path, age_seconds=120)  # expirada
    chamado = {"n": 0}

    def fake_login(email, senha, senha_secundaria=None):
        chamado["n"] += 1
        _touch(path, age_seconds=0)  # simula sessão renovada

    monkeypatch.setattr(portal, "testar_login", fake_login)
    s = portal.garantir_sessao("joao@x.com", "senha", None)
    assert chamado["n"] == 1  # reautenticou uma vez
    assert s["ativa"] is True
