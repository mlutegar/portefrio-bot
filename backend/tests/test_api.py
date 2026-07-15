"""Testes das rotas com o scraper mockado (não acessa o portal real).

Usa o TestClient como context manager (`with`) para manter o event loop ativo,
permitindo que o worker de background do job execute entre as requisições.
"""
from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import jobs, secrets_store
from app.main import app

CREDS_FAKE = {
    "email": "a@b.com",
    "senha": "x",
    "senha_secundaria": None,
}


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def com_credenciais(monkeypatch):
    """Simula credenciais já configuradas no cofre."""
    monkeypatch.setattr(secrets_store, "carregar", lambda: dict(CREDS_FAKE))
    return CREDS_FAKE


def _aguardar(client, job_id, timeout=15.0):
    inicio = time.time()
    while time.time() - inicio < timeout:
        s = client.get(f"/jobs/{job_id}").json()
        if s["status"] in ("done", "error"):
            return s
        time.sleep(0.1)
    return None


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_root(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "health" in r.json()


def test_validacao_cnpj_vazio(client, com_credenciais):
    r = client.post("/cnpj/buscar", json={"cnpj": ""})
    assert r.status_code == 400


def test_busca_sem_credenciais(client, monkeypatch):
    monkeypatch.setattr(secrets_store, "carregar", lambda: None)
    r = client.post("/cnpj/buscar", json={"cnpj": "123"})
    assert r.status_code == 400
    assert "não configuradas" in r.json()["detail"].lower() or "configure" in r.json()["detail"].lower()


def test_status_credenciais_mascarado(client, com_credenciais):
    r = client.get("/credenciais")
    assert r.status_code == 200
    body = r.json()
    assert body["configurado"] is True
    # Nunca devolve a senha; e-mail vem mascarado.
    assert "senha" not in body
    assert "@" in body["email_mascarado"]
    assert body["email_mascarado"] != CREDS_FAKE["email"]


def test_salvar_e_testar(client, monkeypatch):
    chamadas = {}

    def fake_testar(email, senha, senha2=None):
        chamadas["testado"] = (email, senha, senha2)

    def fake_salvar(email, senha, senha2):
        chamadas["salvo"] = (email, senha, senha2)

    monkeypatch.setattr("app.routes.credenciais.testar_login", fake_testar)
    monkeypatch.setattr(secrets_store, "salvar", fake_salvar)

    r = client.post(
        "/credenciais/salvar-e-testar",
        json={"email": "x@y.com", "senha": "s3nha", "senha_secundaria": None},
    )
    assert r.status_code == 200
    assert r.json() == {"ok": True, "mensagem": "Credenciais válidas"}
    assert chamadas["testado"][0] == "x@y.com"
    assert chamadas["salvo"][0] == "x@y.com"


def test_salvar_e_testar_login_invalido(client, monkeypatch):
    from app.scraper.portal import LoginError

    def fake_testar(*a, **k):
        raise LoginError("usuário ou senha inválidos")

    salvou = {"chamado": False}
    monkeypatch.setattr("app.routes.credenciais.testar_login", fake_testar)
    monkeypatch.setattr(
        secrets_store, "salvar", lambda *a, **k: salvou.__setitem__("chamado", True)
    )

    r = client.post(
        "/credenciais/salvar-e-testar",
        json={"email": "x@y.com", "senha": "errada"},
    )
    assert r.status_code == 200
    assert r.json()["ok"] is False
    # Não deve gravar credenciais inválidas.
    assert salvou["chamado"] is False


def test_portal_session_sem_credenciais(client, monkeypatch):
    monkeypatch.setattr(secrets_store, "carregar", lambda: None)
    r = client.get("/portal/session")
    assert r.status_code == 200
    assert r.json()["ativa"] is False


def test_portal_login_sucesso(client, com_credenciais, monkeypatch):
    monkeypatch.setattr("app.routes.portal.testar_login", lambda *a, **k: None)
    monkeypatch.setattr(
        "app.routes.portal.status_sessao",
        lambda email: {"ativa": True, "expira_em_seg": 1200},
    )
    r = client.post("/portal/login")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["mensagem"] == "Sessão ativa"
    assert body["sessao"]["ativa"] is True
    assert body["sessao"]["expira_em_seg"] == 1200


def test_portal_login_invalido(client, com_credenciais, monkeypatch):
    from app.scraper.portal import LoginError

    def fake(*a, **k):
        raise LoginError("usuário ou senha inválidos")

    monkeypatch.setattr("app.routes.portal.testar_login", fake)
    monkeypatch.setattr(
        "app.routes.portal.status_sessao",
        lambda email: {"ativa": False, "expira_em_seg": None},
    )
    r = client.post("/portal/login")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert "inválid" in body["mensagem"].lower()
    assert body["sessao"]["ativa"] is False


def test_portal_login_sem_credenciais(client, monkeypatch):
    monkeypatch.setattr(secrets_store, "carregar", lambda: None)
    r = client.post("/portal/login")
    assert r.status_code == 400


def test_portal_ensure_ja_ativa_nao_reautentica(client, com_credenciais, monkeypatch):
    """Se a sessão já está ativa, ensure não abre navegador (não chama garantir_sessao)."""
    monkeypatch.setattr(
        "app.routes.portal.status_sessao",
        lambda email: {"ativa": True, "expira_em_seg": 1200, "existe": True},
    )
    chamou = {"garantir": False}

    def nao_deve_chamar(*a, **k):
        chamou["garantir"] = True

    monkeypatch.setattr("app.routes.portal.garantir_sessao", nao_deve_chamar)
    r = client.post("/portal/session/ensure")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["sessao"]["ativa"] is True
    assert chamou["garantir"] is False


def test_portal_ensure_reautentica_quando_expirada(client, com_credenciais, monkeypatch):
    estados = iter(
        [
            {"ativa": False, "expira_em_seg": None, "existe": True},  # check inicial
            {"ativa": True, "expira_em_seg": 1200, "existe": True},  # após reauth
        ]
    )
    monkeypatch.setattr(
        "app.routes.portal.status_sessao", lambda email: next(estados)
    )
    chamadas = {"n": 0}

    def fake_garantir(email, senha, senha2=None):
        chamadas["n"] += 1

    monkeypatch.setattr("app.routes.portal.garantir_sessao", fake_garantir)
    r = client.post("/portal/session/ensure")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["mensagem"] == "Sessão reautenticada"
    assert body["sessao"]["ativa"] is True
    assert chamadas["n"] == 1


def test_portal_ensure_falha_login(client, com_credenciais, monkeypatch):
    from app.scraper.portal import LoginError

    monkeypatch.setattr(
        "app.routes.portal.status_sessao",
        lambda email: {"ativa": False, "expira_em_seg": None, "existe": True},
    )

    def fake_garantir(*a, **k):
        raise LoginError("usuário ou senha inválidos")

    monkeypatch.setattr("app.routes.portal.garantir_sessao", fake_garantir)
    r = client.post("/portal/session/ensure")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert "inválid" in body["mensagem"].lower()


def test_portal_ensure_sem_credenciais(client, monkeypatch):
    monkeypatch.setattr(secrets_store, "carregar", lambda: None)
    r = client.post("/portal/session/ensure")
    assert r.status_code == 400


def test_fluxo_completo_mockado(client, com_credenciais, monkeypatch):
    def fake_scrape(email, senha, senha2, cnpj, destino, progress=None):
        if progress:
            progress("Baixando", 80)
        p = Path(destino) / "cartao_cnpj.pdf"
        p.write_bytes(b"%PDF-1.4 fake")
        return {"empresa": "ACME LTDA", "arquivos": ["cartao_cnpj.pdf"]}

    monkeypatch.setattr(jobs, "buscar_documentos_cnpj", fake_scrape)

    r = client.post("/cnpj/buscar", json={"cnpj": "11.222.333/0001-44"})
    assert r.status_code == 202
    job_id = r.json()["job_id"]

    final = _aguardar(client, job_id)
    assert final is not None, "job não concluiu"
    assert final["status"] == "done", final
    assert final["result"]["empresa"] == "ACME LTDA"
    assert len(final["result"]["documentos"]) == 1

    dl = client.get(f"/files/{job_id}/0")
    assert dl.status_code == 200
    assert dl.content.startswith(b"%PDF")

    z = client.get(f"/files/{job_id}/zip")
    assert z.status_code == 200
    assert z.headers["content-type"] == "application/zip"

    h = client.get("/history?email=a@b.com")
    assert h.status_code == 200
    assert any(item["job_id"] == job_id for item in h.json())


def test_erro_negocio_mockado(client, com_credenciais, monkeypatch):
    from app.scraper.portal import CnpjNaoEncontrado

    def fake_scrape(*a, **k):
        raise CnpjNaoEncontrado("Nenhum resultado para o CNPJ.")

    monkeypatch.setattr(jobs, "buscar_documentos_cnpj", fake_scrape)

    r = client.post("/cnpj/buscar", json={"cnpj": "1"})
    job_id = r.json()["job_id"]
    final = _aguardar(client, job_id)
    assert final is not None
    assert final["status"] == "error"
    assert "Nenhum resultado" in final["error"]


def test_score_navigation_sem_credenciais(client, monkeypatch):
    monkeypatch.setattr("app.routes.portal.secrets_store.carregar", lambda: None)
    r = client.post("/portal/score-navigation")
    assert r.status_code == 400
    assert "não configuradas" in r.json()["detail"].lower()


def test_score_navigation_fluxo_sucesso(client, com_credenciais, monkeypatch):
    chamou_navegar = {"sim": False}

    def fake_navegar(email, senha, senha_secundaria, progress_cb=None, preview_cb=None):
        chamou_navegar["sim"] = True
        if progress_cb:
            progress_cb("Clicando em 'Ir para portal do cedente'", 60)
        if preview_cb:
            class MockPage:
                def screenshot(self, *a, **k):
                    return b"fake jpeg screenshot bytes"
            preview_cb(MockPage())
        return {"sucesso": True, "diagnostics_base": "teste_sucesso_diag"}

    # Mockar a reautenticação automática para não subir o navegador de verdade
    monkeypatch.setattr("app.routes.portal.garantir_sessao", lambda *a, **k: {"ativa": True})
    monkeypatch.setattr("app.routes.portal.navegar_score_multiplike", fake_navegar)

    # Inicia a navegação
    r = client.post("/portal/score-navigation")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "running"
    assert body["step"] == "Iniciando"

    # Aguardar a conclusão do background task
    import time
    status_body = {}
    for _ in range(30):
        r_status = client.get("/portal/score-navigation")
        status_body = r_status.json()
        if status_body["status"] in ("done", "error"):
            break
        time.sleep(0.1)

    assert status_body["status"] == "done"
    assert status_body["step"] == "Tela de consulta alcançada"
    assert status_body["diagnostics_base"] == "teste_sucesso_diag"
    assert status_body["progress"] == 100
    assert "data:image/jpeg;base64," in status_body["live_preview"]
    assert chamou_navegar["sim"] is True


def test_score_navigation_fluxo_erro(client, com_credenciais, monkeypatch):
    from app.scraper.portal import NavigationError

    def fake_navegar_error(email, senha, senha_secundaria, progress_cb=None, preview_cb=None):
        if progress_cb:
            progress_cb("Localizando card 'Score Multiplike'", 80)
        if preview_cb:
            class MockPage:
                def screenshot(self, *a, **k):
                    return b"fake jpeg screenshot bytes"
            preview_cb(MockPage())
        raise NavigationError("Elemento não encontrado", step="Localizando card 'Score Multiplike'", diagnostics_base="teste_erro_diag")

    monkeypatch.setattr("app.routes.portal.garantir_sessao", lambda *a, **k: {"ativa": True})
    monkeypatch.setattr("app.routes.portal.navegar_score_multiplike", fake_navegar_error)

    # Reseta o estado global iniciando nova navegação
    r = client.post("/portal/score-navigation")
    assert r.status_code == 200

    import time
    status_body = {}
    for _ in range(30):
        r_status = client.get("/portal/score-navigation")
        status_body = r_status.json()
        if status_body["status"] in ("done", "error"):
            break
        time.sleep(0.1)

    assert status_body["status"] == "error"
    assert status_body["step"] == "Localizando card 'Score Multiplike'"
    assert "Elemento não encontrado" in status_body["error"]
    assert status_body["diagnostics_base"] == "teste_erro_diag"


def test_diagnostics_endpoint(client, tmp_path, monkeypatch):
    from app import config
    monkeypatch.setattr(config, "DIAG_DIR", tmp_path)

    # Cria arquivo mock de diagnóstico
    mock_file = tmp_path / "nav_mock_123.png"
    mock_file.write_bytes(b"fake png data")

    # 1. Requisição com extensão inválida
    r = client.get("/portal/diagnostics/nav_mock_123/pdf")
    assert r.status_code == 400
    assert "Extensão inválida" in r.json()["detail"]

    # 2. Requisição com caracteres inválidos (tentativa de path traversal)
    r = client.get("/portal/diagnostics/nav..mock/png")
    assert r.status_code == 400
    assert "Nome de arquivo inválido" in r.json()["detail"]


    # 3. Requisição de arquivo inexistente
    r = client.get("/portal/diagnostics/nao_existe/png")
    assert r.status_code == 404

    # 4. Requisição com sucesso
    r = client.get("/portal/diagnostics/nav_mock_123/png")
    assert r.status_code == 200
    assert r.content == b"fake png data"
    assert r.headers["content-type"] == "image/png"


def test_score_navigation_historico(client, com_credenciais, monkeypatch):
    from app import db
    from app.models import ScoreHistoryItem

    mock_history = [
        ScoreHistoryItem(
            id=1,
            email="a@b.com",
            status="done",
            ultimo_passo="Tela de consulta alcançada",
            diagnostics_base="teste_sucesso_diag",
            created_at="2026-07-14T13:48:54Z"
        )
    ]

    monkeypatch.setattr(db, "listar_historico_score", lambda email, limit=50: mock_history)

    r = client.get("/portal/score-navigation/history")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["status"] == "done"
    assert body[0]["ultimo_passo"] == "Tela de consulta alcançada"


