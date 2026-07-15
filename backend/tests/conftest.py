import pytest

from app import db


@pytest.fixture(autouse=True, scope="session")
def _init_db():
    # Garante que a tabela de histórico exista sem depender do lifespan.
    db.init_db()
    yield
