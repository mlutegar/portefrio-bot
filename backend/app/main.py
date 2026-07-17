from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from . import db, jobs
from .config import CORS_ORIGINS
from .logging_config import get_logger
from .routes import cnpj, consultar, credenciais, health, portal
from .routes.consultar import limiter

log = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    task = asyncio.create_task(jobs.cleanup_loop())
    log.info("Aplicação iniciada.")
    try:
        yield
    finally:
        task.cancel()
        log.info("Aplicação encerrada.")


app = FastAPI(title="Portefrio Web Scraping API", version="2.0.0", lifespan=lifespan)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, tags=["health"])
app.include_router(cnpj.router, tags=["cnpj"])
app.include_router(consultar.router, tags=["consultar"])
app.include_router(credenciais.router, tags=["credenciais"])
app.include_router(portal.router, tags=["portal"])


@app.get("/")
def root():
    return {"app": "Portefrio Web Scraping API", "docs": "/docs", "health": "/health"}
