# Portefrio — Consulta de CNPJ (Web Scraping)

Aplicação web que loga no portal `https://portal.multiplike.com.br/`, busca um
CNPJ, baixa os PDFs dos documentos e devolve tudo como JSON para o usuário.

- **Backend:** Python + FastAPI + Playwright (Chromium headless)
- **Frontend:** React (Vite)
- As credenciais do portal são cadastradas **uma vez** na interface, **testadas**
  contra o portal e guardadas **cifradas** (Fernet) num cofre no backend — nunca em
  texto claro no front ou no código. A sessão autenticada é reutilizada entre buscas.

## Recursos
- ✅ Shell + health check (botão "Verificar API" → online/offline)
- ✅ **Jobs assíncronos** com polling e barra de progresso (não trava em buscas longas)
- ✅ **Reuso de sessão** (cookies) por usuário — evita relogar a cada busca
- ✅ **Retry com backoff** em erros transitórios
- ✅ **Screenshots + HTML de diagnóstico** salvos em falhas (`backend/diagnostics/`)
- ✅ Erros distintos: credenciais, CNPJ não encontrado, seletor a ajustar
- ✅ **Concorrência limitada** por semáforo (`MAX_CONCURRENCY`)
- ✅ **Limpeza automática** de jobs/arquivos por TTL
- ✅ **Histórico** de consultas por e-mail (SQLite)
- ✅ Download por PDF, **JSON** e **ZIP** de todos os documentos
- ✅ **Logging estruturado**
- ✅ Testes automatizados (scraper mockado) + **Docker Compose**

## Estrutura
```
backend/
  app/
    main.py            FastAPI (lifespan: init DB + limpeza)
    config.py          Configs via variáveis de ambiente
    logging_config.py  Logging estruturado
    models.py          Schemas Pydantic (job, resultado, histórico)
    jobs.py            Fila assíncrona + worker + semáforo + limpeza TTL
    db.py              Histórico em SQLite
    storage.py         Arquivos por job + geração de ZIP
    scraper/portal.py  Scraper Playwright (login, busca, download, diagnóstico)
    routes/            /health, /cnpj/buscar, /jobs, /files, /history
  tests/               Testes com scraper mockado
frontend/
  src/                 App React (HealthBadge, CnpjSearch com progresso/histórico)
docker-compose.yml     Sobe backend (Chromium) + frontend (nginx)
```

## Como rodar (dev)

### Backend
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate            # Windows  (Linux/Mac: source .venv/bin/activate)
pip install -r requirements.txt
python -m playwright install chromium
cp .env.example .env              # e gere a CREDENTIALS_KEY (abaixo)
uvicorn app.main:app --reload --port 8000
```
- O backend carrega `backend/.env` automaticamente (via python-dotenv) — não precisa
  de `--env-file`.
- Gere a chave-mestra do cofre uma vez e cole em `CREDENTIALS_KEY` no `.env`:
  ```bash
  python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())"
  ```
- Health: http://localhost:8000/health · Docs: http://localhost:8000/docs

### Frontend
```bash
cd frontend
npm install
npm run dev            # http://localhost:5200
```

### Testes
```bash
cd backend
pytest
```

## Rodar com Docker
```bash
docker compose up --build
# Frontend: http://localhost:8080  (proxy /health,/cnpj,/jobs,/files,/history → backend)
```

## Fluxo de uso
1. Abra o frontend — o botão **"Verificar API"** mostra o backend online (verde) / offline (vermelho).
2. Em **Credenciais do portal**, cadastre e-mail/senha e clique **"Salvar e testar"** (valida e cifra no cofre).
3. Em **Sessão no portal**, clique **"Entrar no portal"** → indicador "🟢 Sessão ativa".
4. Informe o **CNPJ** e clique **"Buscar"** → cria um job; a UI faz polling e mostra o progresso.
5. Ao concluir: resultado em JSON, links de cada PDF, **Baixar tudo (ZIP)** e **Baixar JSON**. O histórico aparece abaixo.

## Endpoints
| Método | Rota                          | Descrição                                   |
|--------|-------------------------------|---------------------------------------------|
| GET    | `/health`                     | Estado da API                               |
| POST   | `/credenciais/salvar-e-testar`| Testa credenciais e grava cifradas no cofre |
| GET    | `/credenciais`                | Estado do cofre (e-mail mascarado)          |
| DELETE | `/credenciais`                | Remove credenciais do cofre                 |
| POST   | `/portal/login`               | Autentica no portal e guarda a sessão       |
| GET    | `/portal/session`             | Estado da sessão (ativa + expira em)        |
| DELETE | `/portal/session`             | Encerra a sessão                            |
| POST   | `/cnpj/buscar`                | Cria job de scraping → `{job_id, status}` (202) |
| GET    | `/jobs/{id}`                  | Status/progresso/resultado do job           |
| GET    | `/files/{id}/{idx}`           | Baixa um PDF                                 |
| GET    | `/files/{id}/zip`             | Baixa todos os PDFs em ZIP                   |
| GET    | `/history?email=`             | Histórico (padrão: e-mail do cofre)         |

## Ajuste dos seletores do portal
O portal é autenticado e bloqueia acessos simples (HTTP 403), então os seletores
exatos de login/busca/download só podem ser confirmados rodando o navegador de
verdade. Em `backend/app/scraper/portal.py` procure os comentários `AJUSTAR`.
Para depurar, rode com `HEADLESS=false` e veja o navegador; em qualquer falha,
um screenshot + HTML são salvos em `backend/diagnostics/`.

## Segurança
- Sempre sirva atrás de **HTTPS** em produção (as credenciais trafegam no corpo do POST ao cadastrar).
- As credenciais ficam **cifradas** (Fernet) na tabela `credenciais` do SQLite; a chave-mestra
  vem de `CREDENTIALS_KEY` (nunca versionada). Sem a chave, os dados são ilegíveis.
- **Rotação de chave:** `python rotate_key.py <chave_antiga> <chave_nova>` re-cifra as
  credenciais; depois atualize `CREDENTIALS_KEY` no `.env` e reinicie.
- A sessão autenticada (cookies) é guardada em `backend/sessions/` com validade curta
  (`SESSION_TTL_SECONDS`) e reutilizada entre buscas.
- Operações que sobem o navegador (login, teste de credenciais, busca) compartilham um
  semáforo (`MAX_CONCURRENCY`) para proteger o servidor contra rajadas.
# portefrio-bot
