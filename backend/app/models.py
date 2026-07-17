from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class BuscaRequest(BaseModel):
    """Payload enviado pelo frontend para buscar um CNPJ no portal.

    As credenciais NÃO vêm mais no request — são lidas do cofre (secrets_store).
    """

    cnpj: str = Field(..., description="CNPJ a ser pesquisado (com ou sem máscara)")


class CredenciaisInput(BaseModel):
    """Credenciais do portal enviadas uma única vez para cadastro no cofre."""

    email: str = Field(..., description="E-mail de login no portal")
    senha: str = Field(..., description="Senha de login do portal")
    senha_secundaria: Optional[str] = Field(
        None, description="Senha secundária / 2FA (opcional)"
    )


class CredenciaisStatus(BaseModel):
    """Estado do cofre — nunca expõe a senha."""

    configurado: bool
    email_mascarado: Optional[str] = None


class SalvarCredenciaisResponse(BaseModel):
    ok: bool
    mensagem: str


class SessaoStatus(BaseModel):
    """Estado da sessão autenticada no portal."""

    ativa: bool
    expira_em_seg: Optional[int] = None
    email_mascarado: Optional[str] = None
    # True = existe sessão salva (pode estar expirada); False = nunca autenticou/logout.
    existe: bool = False


class LoginResponse(BaseModel):
    ok: bool
    mensagem: str
    sessao: SessaoStatus


class DocumentoInfo(BaseModel):
    nome: str
    tamanho: int
    download_url: str


class JobStatus(str, Enum):
    pending = "pending"
    running = "running"
    done = "done"
    error = "error"


class ScoreData(BaseModel):
    """Dados estruturados extraídos do PDF Score Multiplike.

    Todos os campos são opcionais para garantir resiliência com documentos
    dinâmicos — campos ausentes no PDF retornam None em vez de causar erros.
    """

    cabecalho: Optional[dict] = None
    informacoes_cadastrais: Optional[dict] = None
    socios_administradores: Optional[dict] = None
    consultas: Optional[dict] = None
    informacoes_comportamentais: Optional[dict] = None
    anotacoes_negativas: Optional[dict] = None


class JobResult(BaseModel):
    cnpj: str
    empresa: Optional[str] = None
    documentos: List[DocumentoInfo] = []
    gerado_em: str
    job_id: str
    dados_extraidos: Optional[ScoreData] = None


class JobState(BaseModel):
    job_id: str
    status: JobStatus
    step: str = ""
    progress: int = 0  # 0-100
    cnpj: str
    email: str
    created_at: float
    updated_at: float
    result: Optional[JobResult] = None
    error: Optional[str] = None
    diagnostics_url: Optional[str] = None


class JobCreatedResponse(BaseModel):
    job_id: str
    status: JobStatus


class HistoryItem(BaseModel):
    job_id: str
    cnpj: str
    email: str
    empresa: Optional[str] = None
    status: str
    num_docs: int
    created_at: str


class ScoreHistoryItem(BaseModel):
    id: int
    email: str
    status: str
    ultimo_passo: str
    error: Optional[str] = None
    diagnostics_base: Optional[str] = None
    created_at: str



class HealthResponse(BaseModel):
    status: str
    timestamp: str


class ConsultarRequest(BaseModel):
    """Payload para consulta direta — credenciais + CNPJ em uma única chamada."""

    email: str = Field(..., description="E-mail de login no portal")
    senha: str = Field(..., description="Senha de login no portal")
    cnpj: str = Field(..., description="CNPJ a ser pesquisado (com ou sem máscara)")
    callback_url: Optional[str] = Field(
        None,
        description="URL opcional para receber o resultado via POST assim que pronto (webhook)",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "email": "financeiro@empresa.com",
                    "senha": "SuaSenha@123",
                    "cnpj": "01.838.723/0001-27",
                    "callback_url": None,
                }
            ]
        }
    }


class ConsultarResponse(BaseModel):
    """Resultado da consulta — retorna o JSON extraído diretamente."""

    cnpj: str
    empresa: Optional[str] = None
    dados_extraidos: Optional[ScoreData] = None
    cached: bool = False
    idade_cache_segundos: Optional[int] = None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "cnpj": "01.838.723/0001-27",
                    "empresa": "BRF S/A",
                    "cached": False,
                    "idade_cache_segundos": None,
                    "dados_extraidos": {
                        "cabecalho": {"data_consulta": "20260717 - 11:46:52"},
                        "informacoes_cadastrais": {
                            "cnpj": "01.838.723/0001-27",
                            "nome_fantasia": "BRF S/A",
                            "situacao_cnpj": "ATIVA",
                        },
                        "informacoes_comportamentais": {
                            "historico_pagamentos": {"classificacao": "PONTUAL"}
                        },
                        "anotacoes_negativas": {"pefin": "NADA CONSTA"},
                        "socios_administradores": None,
                        "consultas": None,
                    },
                }
            ]
        }
    }
