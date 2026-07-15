from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent

# Carrega o backend/.env automaticamente (se existir), sem precisar de --env-file.
# Variáveis já definidas no ambiente têm precedência (override=False).
try:
    from dotenv import load_dotenv

    load_dotenv(BASE_DIR / ".env", override=False)
except ImportError:  # dotenv é opcional; sem ele, usa só o ambiente
    pass

# URL base do portal alvo. Pode ser sobrescrita por variável de ambiente.
PORTAL_URL = os.environ.get("PORTAL_URL", "https://portal.multiplike.com.br/")

# Rodar o navegador com interface visível (útil no desenvolvimento para mapear
# seletores). Defina HEADLESS=false para ver o navegador.
HEADLESS = os.environ.get("HEADLESS", "true").lower() not in ("false", "0", "no")

# Timeout padrão (ms) para operações do Playwright.
NAV_TIMEOUT = int(os.environ.get("NAV_TIMEOUT", "45000"))

# Nº máximo de tentativas do scraper em erros transitórios.
MAX_RETRIES = int(os.environ.get("MAX_RETRIES", "2"))

# Máximo de navegadores/scrapes simultâneos.
MAX_CONCURRENCY = int(os.environ.get("MAX_CONCURRENCY", "2"))

# Pasta onde os PDFs baixados ficam temporariamente armazenados.
STORAGE_DIR = Path(os.environ.get("STORAGE_DIR", BASE_DIR / "downloads"))
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

# Pasta com os storageState (cookies/sessão) reutilizáveis por usuário.
SESSION_DIR = Path(os.environ.get("SESSION_DIR", BASE_DIR / "sessions"))
SESSION_DIR.mkdir(parents=True, exist_ok=True)

# Pasta com screenshots/HTML de diagnóstico em falhas.
DIAG_DIR = Path(os.environ.get("DIAG_DIR", BASE_DIR / "diagnostics"))
DIAG_DIR.mkdir(parents=True, exist_ok=True)

# Banco SQLite de histórico.
DB_PATH = Path(os.environ.get("DB_PATH", BASE_DIR / "history.db"))

# Chave-mestra (Fernet) para cifrar as credenciais do portal em repouso.
# Em produção defina CREDENTIALS_KEY no ambiente. Em dev, se ausente, uma chave
# é gerada e persistida em backend/.secret_key (NÃO versionar).
CREDENTIALS_KEY = os.environ.get("CREDENTIALS_KEY")
SECRET_KEY_FILE = Path(os.environ.get("SECRET_KEY_FILE", BASE_DIR / ".secret_key"))

# Tempo de vida (segundos) dos jobs/arquivos antes da limpeza automática.
JOB_TTL_SECONDS = int(os.environ.get("JOB_TTL_SECONDS", str(60 * 60 * 6)))  # 6h

# Tempo de vida (segundos) dos screenshots/HTML de diagnóstico.
DIAGNOSTICS_TTL_SECONDS = int(os.environ.get("DIAGNOSTICS_TTL_SECONDS", str(60 * 60 * 24)))  # 24h

# Validade (segundos) de uma sessão salva antes de forçar novo login.
SESSION_TTL_SECONDS = int(os.environ.get("SESSION_TTL_SECONDS", str(60 * 20)))  # 20min


# Intervalo (segundos) do loop de limpeza.
CLEANUP_INTERVAL_SECONDS = int(os.environ.get("CLEANUP_INTERVAL_SECONDS", "600"))

# Nível de log.
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()

# Origens permitidas no CORS (frontend Vite por padrão).
CORS_ORIGINS = os.environ.get(
    "CORS_ORIGINS", "http://localhost:5200,http://127.0.0.1:5200"
).split(",")
