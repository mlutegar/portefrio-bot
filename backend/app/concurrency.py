"""Controle de concorrência para operações que sobem um navegador (Playwright).

Login, teste de credenciais e busca disparam Chromium — caros em CPU/RAM. Este
semáforo compartilhado limita quantas dessas operações rodam ao mesmo tempo,
protegendo o servidor contra rajadas (duplo-clique, abuso).
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Optional

from .config import MAX_CONCURRENCY

_browser_sem: Optional[asyncio.Semaphore] = None


def _sem() -> asyncio.Semaphore:
    global _browser_sem
    if _browser_sem is None:
        _browser_sem = asyncio.Semaphore(MAX_CONCURRENCY)
    return _browser_sem


class BusyError(Exception):
    """Todas as vagas de navegador estão ocupadas no momento."""


@asynccontextmanager
async def browser_slot(wait: bool = True, timeout: float = 90.0):
    """Adquire uma vaga de navegador.

    wait=False → levanta BusyError imediatamente se não houver vaga (útil para
    ações interativas como o botão "Entrar no portal", evitando fila longa).
    """
    sem = _sem()
    if not wait:
        if sem.locked() and sem._value <= 0:  # sem vaga livre agora
            raise BusyError(
                "Servidor ocupado processando outra autenticação. Tente em instantes."
            )
    try:
        await asyncio.wait_for(sem.acquire(), timeout=timeout)
    except asyncio.TimeoutError as e:
        raise BusyError("Tempo de espera esgotado — servidor ocupado.") from e
    try:
        yield
    finally:
        sem.release()
