"""Parser do PDF Score Multiplike.

Extrai texto com pdfplumber e usa regex para mapear cada seção em um dict
estruturado.  Campos ausentes no PDF sempre retornam None — nunca levantam
exceção — para garantir resiliência com documentos dinâmicos.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional

try:
    import pdfplumber  # type: ignore
except ImportError as e:  # pragma: no cover
    raise ImportError(
        "pdfplumber não está instalado. Execute: pip install pdfplumber"
    ) from e


# ---------------------------------------------------------------------------
# Utilitários internos
# ---------------------------------------------------------------------------

def _strip(value: Optional[str]) -> Optional[str]:
    """Remove espaços extras e retorna None se vazio."""
    if value is None:
        return None
    v = re.sub(r"\s+", " ", value).strip()
    return v or None


def _between(text: str, start_pattern: str, end_pattern: str) -> str:
    """Fatia o texto entre dois padrões regex (não inclusivos)."""
    m_start = re.search(start_pattern, text, re.IGNORECASE)
    if not m_start:
        return ""
    chunk = text[m_start.end():]
    m_end = re.search(end_pattern, chunk, re.IGNORECASE)
    return chunk[: m_end.start()] if m_end else chunk


def _find(pattern: str, text: str, group: int = 1) -> Optional[str]:
    m = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    if m:
        try:
            return _strip(m.group(group))
        except IndexError:
            return None
    return None


def _first_line(text: str) -> Optional[str]:
    """Retorna a primeira linha não-vazia de um texto."""
    for line in text.splitlines():
        line = line.strip()
        if line:
            return line
    return None


# ---------------------------------------------------------------------------
# Ponto de entrada público
# ---------------------------------------------------------------------------

def parse_score_pdf(pdf_path: Path) -> dict[str, Any]:
    """Lê *pdf_path* e devolve um dict com os dados estruturados do Score."""
    with pdfplumber.open(pdf_path) as pdf:
        pages_text = [p.extract_text() or "" for p in pdf.pages]

    full_text = "\n".join(pages_text)

    return {
        "cabecalho": _parse_cabecalho(full_text),
        "informacoes_cadastrais": _parse_cadastro(full_text),
        "socios_administradores": _parse_socios(full_text),
        "consultas": _parse_consultas(full_text),
        "informacoes_comportamentais": _parse_comportamental(full_text),
        "anotacoes_negativas": _parse_anotacoes(full_text),
    }


# ---------------------------------------------------------------------------
# Seção 0 – Cabeçalho
# ---------------------------------------------------------------------------

def _parse_cabecalho(text: str) -> dict:
    data = _find(r"DATA\s+DA\s+CONSULTA[:\s]+(\d{8}\s*-\s*[\d:]+)", text)
    return {"data_consulta": data}


# ---------------------------------------------------------------------------
# Seção 1 – Informações Cadastrais
# ---------------------------------------------------------------------------

def _parse_cadastro(text: str) -> dict:
    chunk = _between(
        text,
        r"1\.\s*INFORMA[CÇ][OÕ]ES CADASTRAIS",
        r"2\.\s*INFORMA[CÇ][OÕ]ES SOBRE S[OÓ]CIOS",
    )

    # CNPJ
    cnpj = _find(r"(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})", chunk)

    # Tipo jurídico (antes da situação)
    tipo_m = re.search(
        r"(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})\s+([\w\s]+?)\s+(ATIVA|BAIXADA|SUSPENSA|INAPTA)",
        chunk, re.IGNORECASE,
    )
    tipo = _strip(tipo_m.group(2)) if tipo_m else None
    situacao = _strip(tipo_m.group(3)) if tipo_m else None

    data_situacao = _find(r"Situa[cç][aã]o do CNPJ em\s+([\d/]+)", chunk)

    # Após "Nome fantasia Razão Social Nire" vêm os valores na próxima(s) linha(s)
    nomes_block = _between(chunk, r"Nome\s+fantasia\s+Raz[aã]o Social\s+Nire", r"Endere[cç]o completo")
    nomes_lines = [l.strip() for l in nomes_block.splitlines() if l.strip()]
    # Nire é sempre numérico ao final da primeira linha de valores
    nome_fantasia: Optional[str] = None
    razao_social: Optional[str] = None
    nire: Optional[str] = None
    if nomes_lines:
        first = nomes_lines[0]
        nire_m = re.search(r"\b(\d{10,})\s*$", first)
        if nire_m:
            nire = nire_m.group(1)
            before_nire = first[: nire_m.start()].strip()
        else:
            before_nire = first
        # Nome fantasia: primeira palavra(s) até razão social (palavras em caps)
        parts = before_nire.split()
        # Heurística: nome fantasia = palavras antes de "RDS/LTDA/ME/SA/etc." na linha
        rs_m = re.search(r"(\b\w+\s+(?:LTDA|ME|EPP|SA|S\.A\.|EIRELI|SLU)\b.*)", before_nire, re.IGNORECASE)
        if rs_m:
            razao_social = _strip(rs_m.group(1))
            nome_fantasia = _strip(before_nire[: rs_m.start()])
        else:
            # Sem sufixo reconhecível: usa linha inteira como fantasia e resto como razão
            nome_fantasia = _strip(before_nire)
            razao_social = _strip(" ".join(nomes_lines[1:])) if len(nomes_lines) > 1 else None

    # Endereço: uma linha
    endereco_m = re.search(r"Endere[cç]o completo\s*\n(.+)", chunk)
    endereco = _strip(endereco_m.group(1)) if endereco_m else None

    # Telefone
    tel_m = re.search(r"Telefone\s+Site\s+FAX\s*\n(.+)", chunk)
    tel_line = tel_m.group(1).strip() if tel_m else ""
    # Separa telefone do site/fax: telefone tem parênteses, depois números
    tel_parts = re.split(r"\s{2,}", tel_line)
    telefone = _strip(tel_parts[0]) if tel_parts else None
    site_val = _strip(tel_parts[1]) if len(tel_parts) > 1 else None

    # Datas / empregados / ramo: linha após os labels
    data_emp_m = re.search(
        r"Data\s+Funda[cç][aã]o\s+Data\s+Inscri[cç][aã]o\s+Empregados\s+Ramo\s*\n(.+)",
        chunk,
    )
    data_fundacao = data_inscricao = num_empregados = ramo = None
    if data_emp_m:
        vals = data_emp_m.group(1).split()
        data_fundacao = vals[0] if len(vals) > 0 else None
        data_inscricao = vals[1] if len(vals) > 1 else None
        num_empregados = vals[2] if len(vals) > 2 else None
        ramo = _strip(" ".join(vals[3:])) if len(vals) > 3 else None
        # ramo pode continuar na próxima linha se foi quebrado
        if ramo and len(ramo) < 5:
            after = chunk[data_emp_m.end():]
            cont_m = re.search(r"^(.+)\n", after.lstrip("\n"))
            if cont_m:
                ramo = _strip(ramo + " " + cont_m.group(1).strip())

    # CNAE e filiais: linha após o cabeçalho
    cnae_m = re.search(r"CNAE\s+Quantidade de Filiais.*?\n(\d+)\s+(\d+)", chunk)
    cnae = cnae_m.group(1) if cnae_m else None
    qtd_filiais = int(cnae_m.group(2)) if cnae_m else None

    # Contabilidade: label "Contabilidade … CNPJ\n<valor>"
    cont_m = re.search(r"Contabilidade\s+Consul.*?CNPJ\s*\n\s*\w+\s+([\w\s]+?)\s+\d{2}\.", chunk, re.DOTALL)
    contabilidade = _strip(cont_m.group(1)) if cont_m else None
    # fallback simples
    if not contabilidade:
        contabilidade = _find(r"NAO\s+INFORMADO", chunk)
        if contabilidade:
            contabilidade = "NAO INFORMADO"

    return {
        "cnpj": cnpj,
        "tipo": tipo,
        "situacao_cnpj": situacao,
        "data_situacao": data_situacao,
        "nome_fantasia": nome_fantasia,
        "razao_social": razao_social,
        "nire": nire,
        "endereco": endereco,
        "telefone": telefone,
        "site": site_val if site_val and not site_val.isdigit() else None,
        "data_fundacao": data_fundacao,
        "data_inscricao": data_inscricao,
        "num_empregados": num_empregados,
        "ramo": ramo,
        "cnae": cnae,
        "quantidade_filiais": qtd_filiais,
        "contabilidade": contabilidade,
    }


# ---------------------------------------------------------------------------
# Seção 2 – Sócios e Administradores
# ---------------------------------------------------------------------------

def _parse_socios(text: str) -> dict:
    chunk = _between(
        text,
        r"2\.\s*INFORMA[CÇ][OÕ]ES SOBRE S[OÓ]CIOS",
        r"3\.\s*INFORMA[CÇ][OÕ]ES SOBRE CONSULTAS",
    )

    # Capital: layout "R$ X,00  R$ Y,00\nCapital Social  Capital Realizado"
    # ou "Capital Social\nR$ X,00"
    cap_s = _find(r"Capital\s+Social\s+(R\$\s*[\d.,]+)", chunk)
    if not cap_s:
        # valores antes do label
        cap_m = re.search(
            r"(R\$\s*[\d.,]+)\s+(R\$\s*[\d.,]+)\s*\nCapital\s+Social\s+Capital\s+Realizado",
            chunk,
        )
        cap_s = _strip(cap_m.group(1)) if cap_m else None
        cap_r = _strip(cap_m.group(2)) if cap_m else None
    else:
        cap_r = _find(r"Capital\s+Realizado\s+(R\$\s*[\d.,]+)", chunk)

    cap_a_m = re.search(r"(R\$\s*[\d.,]+)\s*\nCapital\s+Autorizado", chunk)
    cap_a = _strip(cap_a_m.group(1)) if cap_a_m else _find(r"Capital\s+Autorizado\s+(R\$\s*[\d.,]+)", chunk)

    # Nacionalidade/Origem: "BRASIL  PRIVADO\nNacionalidade  Origem"
    nac_m = re.search(r"(\w+)\s+(\w+)\s*\nNacionalidade\s+Origem", chunk)
    nacionalidade = _strip(nac_m.group(1)) if nac_m else None
    origem = _strip(nac_m.group(2)) if nac_m else None

    # Natureza: "FECHADO\nNatureza"
    nat_m = re.search(r"(\w+)\s*\nNatureza", chunk)
    natureza = _strip(nat_m.group(1)) if nat_m else None

    return {
        "capital_social": cap_s,
        "capital_realizado": cap_r,
        "capital_autorizado": cap_a,
        "nacionalidade": nacionalidade,
        "origem": origem,
        "natureza": natureza,
        "quadro_societario": _parse_quadro_societario(chunk),
        "quadro_administrativo": _parse_quadro_administrativo(chunk),
        "participacoes_participada": _parse_participada(chunk),
        "participacoes_participantes": _parse_participantes(chunk),
    }


def _parse_quadro_societario(chunk: str) -> list:
    """Extrai linhas do CONTROLE SOCIETÁRIO — ignora cabeçalho da tabela."""
    section = _between(chunk, r"CONTROLE SOCIET[AÁ]RIO", r"QUADRO ADMINISTRATIVO")
    # Ignora linhas de cabeçalho e capital
    pattern = re.compile(
        r"(\d{3}\.\d{3}\.\d{3}[-/]\d{2}|\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})"  # cpf ou cnpj
        r"\s+(.+?)\s+"
        r"(\d{2}/\d{2}/\d{4})\s+"   # entrada
        r"(\d+,\d+%)\s+"             # votante
        r"(\d+,\d+%)",               # total
        re.DOTALL,
    )
    results = []
    for m in pattern.finditer(section):
        results.append({
            "cpf_cnpj": m.group(1).strip(),
            "nome": _strip(m.group(2)),
            "entrada": m.group(3).strip(),
            "capital_votante_perc": m.group(4).strip(),
            "capital_total_perc": m.group(5).strip(),
        })
    return results


def _parse_quadro_administrativo(chunk: str) -> list:
    """Extrai administradores — pula cabeçalho e datas de atualização."""
    section = _between(chunk, r"QUADRO ADMINISTRATIVO", r"PARTICIPA[CÇ][OÕ]ES\s+-\s+PARTICIPADA")
    pattern = re.compile(
        r"(\d{3}\.\d{3}\.\d{3}[-/]\d{2}|\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})"  # cpf/cnpj real
        r"\s+(.+?)\s+"
        r"(ADMINISTR\w*|REPRES\w*|DIRETOR\w*|GERENTE\w*|PRESIDENTE\w*|S[OÓ]CIO\w*|PROCURAD\w*)\s+"
        r"(\d{2}/\d{2}/\d{4})",
        re.IGNORECASE | re.DOTALL,
    )
    results = []
    for m in pattern.finditer(section):
        cpf = m.group(1).strip()
        # Filtra datas capturadas como CPF (formato DD/MM/YYYY)
        if re.match(r"\d{2}/\d{2}/\d{4}", cpf):
            continue
        results.append({
            "cpf_cnpj": cpf,
            "nome": _strip(m.group(2)),
            "cargo": _strip(m.group(3)),
            "inicio_mandato": m.group(4).strip(),
        })
    return results


def _parse_participada(chunk: str) -> list:
    """Empresas em que a consultada participa."""
    section = _between(chunk, r"PARTICIPA[CÇ][OÕ]ES\s+-\s+PARTICIPADA", r"PARTICIPA[CÇ][OÕ]ES\s+-\s+PARTICIPANTES")
    pattern = re.compile(
        r"(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})\s+(.+?)(?=\d{2}\.\d{3}\.\d{3}/|\Z)",
        re.DOTALL,
    )
    results = []
    for m in pattern.finditer(section):
        nome = _strip(re.sub(r"\s+", " ", m.group(2)))
        if nome and not re.match(r"Empresa\s+ligada", nome, re.IGNORECASE):
            results.append({"cpf_cnpj": m.group(1).strip(), "empresa_ligada": nome})
    return results


def _parse_participantes(chunk: str) -> list:
    """Participantes/sócios que compõem o capital da consultada."""
    section = _between(chunk, r"PARTICIPA[CÇ][OÕ]ES\s+-\s+PARTICIPANTES", r"3\.\s*INFORMA[CÇ][OÕ]ES|$")
    pattern = re.compile(
        r"(\d{3}\.\d{3}\.\d{3}[-/]\d{2}|\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})"
        r"\s+(.+?)\s+"
        r"(SC/AD|SOCIO|ADMIN\w*)\s+"
        r"(\d+,\d+%)",
        re.IGNORECASE | re.DOTALL,
    )
    results = []
    for m in pattern.finditer(section):
        cpf = m.group(1).strip()
        if re.match(r"\d{2}/\d{2}/\d{4}", cpf):
            continue
        results.append({
            "cpf_cnpj": cpf,
            "nome": _strip(m.group(2)),
            "vinculo": _strip(m.group(3)),
            "perc_participacao": m.group(4).strip(),
        })
    return results


# ---------------------------------------------------------------------------
# Seção 3 – Consultas
# ---------------------------------------------------------------------------

def _parse_consultas(text: str) -> dict:
    chunk = _between(
        text,
        r"3\.\s*INFORMA[CÇ][OÕ]ES SOBRE CONSULTAS",
        r"4\.\s*INFORMA[CÇ][OÕ]ES COMPORTAMENTAIS",
    )

    # Histórico mensal: pares "MES/AA  N"
    hist_section = _between(chunk, r"Data\s+Quantidade/M[êe]s", r"[ÚU]LTIMAS CONSULTAS")
    hist_pattern = re.compile(r"([A-Z]{3}/\d{2})\s+(\d+)", re.IGNORECASE)
    historico_mensal = [
        {"mes_ano": m.group(1).upper(), "quantidade": int(m.group(2))}
        for m in hist_pattern.finditer(hist_section)
    ]

    # Últimas consultas: "DD/MM/YYYY  CNPJ  Nome  Qtde"
    uc_section = _between(chunk, r"[ÚU]LTIMAS CONSULTAS", r"$")
    uc_pattern = re.compile(
        r"(\d{2}/\d{2}/\d{4})\s+"
        r"(\d{5,})\s+"
        r"(.+?)\s+"
        r"(\d+)\s*$",
        re.MULTILINE,
    )
    ultimas_consultas = [
        {
            "data": m.group(1).strip(),
            "cnpj": m.group(2).strip(),
            "nome": _strip(m.group(3)),
            "quantidade": int(m.group(4)),
        }
        for m in uc_pattern.finditer(uc_section)
    ]

    return {"historico_mensal": historico_mensal, "ultimas_consultas": ultimas_consultas}


# ---------------------------------------------------------------------------
# Seção 4 – Informações Comportamentais
# ---------------------------------------------------------------------------

def _parse_comportamental(text: str) -> dict:
    chunk = _between(
        text,
        r"4\.\s*INFORMA[CÇ][OÕ]ES COMPORTAMENTAIS",
        r"5\.\s*MENSAGENS DOS BLOCOS",
    )

    # Classificação e faixa de títulos: linhas após o cabeçalho
    class_m = re.search(
        r"HIST[OÓ]RICO DE PAGAMENTOS\s*-\s*Qtde\.\s*De\s*T[ií]tulos\s*\n(\w+)\s*\n([\d\sA-Z]+?)(?:\n|$)",
        chunk,
    )
    classificacao = _strip(class_m.group(1)) if class_m else None
    faixa_titulos_raw = _strip(class_m.group(2)) if class_m else None
    # Limpa lixo extra (palavras que não sejam dígitos/A)
    faixa_titulos = None
    if faixa_titulos_raw:
        ft_m = re.match(r"([\d]+\s+A\s+[\d]+)", faixa_titulos_raw, re.IGNORECASE)
        faixa_titulos = ft_m.group(1) if ft_m else faixa_titulos_raw

    historico_mensal = _parse_historico_pagamentos(chunk)
    referenciais = _parse_referenciais(chunk)

    return {
        "historico_pagamentos": {
            "classificacao": classificacao,
            "faixa_titulos": faixa_titulos,
        },
        "historico_mensal": historico_mensal,
        "referenciais_negocios": referenciais,
    }


def _parse_historico_pagamentos(chunk: str) -> list:
    """Extrai o histórico mensal de pagamentos."""
    section = _between(chunk, r"HIST[OÓ]RICO DE PAGAMENTOS NO MERCADO", r"REFERENCIAIS DE NEGOCIOS")

    mes_pattern = re.compile(r"^([A-Z]{3}/\d{2})$", re.MULTILINE)
    mes_positions = [(m.group(1), m.start()) for m in mes_pattern.finditer(section)]

    results = []
    for i, (mes_ano, pos) in enumerate(mes_positions):
        end = mes_positions[i + 1][1] if i + 1 < len(mes_positions) else len(section)
        bloco = section[pos:end]

        # Total do mês: captura faixas de valor como "X MIL A Y MIL"
        # O PDF pode quebrar "13 M\nIL", "13 MI\nL", "13\nMIL" — normaliza tudo
        bloco_norm = re.sub(r"M\s*\nIL\b", "MIL", bloco)        # "M\nIL" → "MIL"
        bloco_norm = re.sub(r"MI\s*\nL\b", "MIL", bloco_norm)   # "MI\nL" → "MIL"
        bloco_norm = re.sub(r"(\d+)\s*\nMIL\b", r"\1 MIL", bloco_norm)  # "13\nMIL" → "13 MIL"
        bloco_norm = re.sub(r"\bMIL\s+MIL\b", "MIL", bloco_norm)        # deduplicar
        totais = re.findall(r"(\d+(?:,\d+)?\s+MIL\s+A\s+\d+(?:,\d+)?\s+MIL)", bloco_norm, re.IGNORECASE)
        total_mes = _strip(totais[-1]) if totais else None

        # Pontual: valor na coluna pontual (segunda coluna), após normalização
        pontual = _find(r"Pontual\s+([\d\s.,MILAa]+?MIL)", bloco_norm)

        # Percentual pontual: o maior valor percentual do bloco (ex: 97,0% - 100,0%)
        # O PDF lista muitos "0,0% -0,0%" para colunas vazias; pegamos o primeiro
        # par que tenha valor real (>= 70%)
        perc = None
        for pm in re.finditer(r"(\d+,\d+%)\s*-\s*(\d+,\d+%)", bloco):
            v1 = float(pm.group(1).replace(",", ".").replace("%", ""))
            if v1 >= 50:
                perc = f"{pm.group(1)} - {pm.group(2)}"
                break

        results.append({
            "mes_ano": mes_ano,
            "pontual_valor": pontual,
            "pontual_perc": perc,
            "total_mes": total_mes,
        })
    return results


def _parse_referenciais(chunk: str) -> dict:
    """Extrai última compra, maior fatura e maior acúmulo.

    Formato real do PDF (sem duplo espaco entre valor e media):
      ULTIMA COMPRA JUL/2026 B2 - 2 MIL A 2,5 MIL A24 - 1 MIL A 1,5 MIL
    O separador entre valor e media e um codigo tipo letra+digito (ex: B2, A24).
    """
    section = _between(chunk, r"REFERENCIAIS DE NEGOCIOS NO MERCADO", r"5\.\s*MENSAGENS|$")

    # Código de referência: letras maiúsculas + dígitos (ex: B2, A24, C3)
    CODE = r"[A-Z]\d+"

    def _ref(label: str) -> Optional[dict]:
        # Captura: LABEL  DATA  <código - valor>  <código - média>
        m = re.search(
            label + r"\s+(\S+/\S+)\s+"                  # data
            r"(" + CODE + r"\s*-\s*[\w\s.,]+?)\s+"      # valor (código + descrição)
            r"(" + CODE + r"\s*-\s*[\w\s.,]+?)(?:\n|$)",# média (código + descrição)
            section,
            re.IGNORECASE,
        )
        if not m:
            return None
        return {
            "data": _strip(m.group(1)),
            "valor": _strip(m.group(2)),
            "media": _strip(m.group(3)),
        }

    return {
        "ultima_compra": _ref(r"ULTIMA\s+COMPRA"),
        "maior_fatura":  _ref(r"MAIOR\s+FATURA"),
        "maior_acumulo": _ref(r"MAIOR\s+ACUMULO"),
    }


# ---------------------------------------------------------------------------
# Seção 5 – Mensagens dos Blocos / Anotações Negativas
# ---------------------------------------------------------------------------

def _parse_anotacoes(text: str) -> dict:
    chunk = _between(text, r"5\.\s*MENSAGENS DOS BLOCOS", r"Este relat[oó]rio")

    def _status(header: str, next_header: str) -> Optional[str]:
        section = _between(chunk, header, next_header)
        if not section.strip():
            return None
        if re.search(r"NADA\s+CONSTA", section, re.IGNORECASE):
            return "NADA CONSTA"
        # Retorna as linhas relevantes concatenadas
        lines = [l.strip() for l in section.strip().splitlines() if l.strip()]
        # Remove linhas que são só separadores
        lines = [l for l in lines if not re.match(r"^=+$", l)]
        return " | ".join(lines) if lines else None

    # Variações Concentre
    variacoes_raw = _find(r"EXISTEM\s+(\d+)\s+VARIA[CÇ][OÕ]ES", chunk)
    variacoes = int(variacoes_raw) if variacoes_raw and variacoes_raw.isdigit() else None

    # Anotações de participantes (lista de empresas)
    part_section = _between(chunk, r"Anota[cç][oõ]es De Participantes", r"Recheque")
    participantes = [
        l.strip() for l in part_section.strip().splitlines()
        if l.strip() and not re.match(r"Anota|CPF|^=$", l, re.IGNORECASE)
    ]

    return {
        "pefin": _status(r"Pend[eê]ncia\s+Financeira\s+-\s+Pefin", r"Pend[eê]ncia\s+Financeira\s+-\s+Refin"),
        "refin": _status(r"Pend[eê]ncia\s+Financeira\s+-\s+Refin", r"Informa[cç][oõ]es\s+Do\s+Concentre"),
        "concentre_variacoes": variacoes,
        "concentre_resumo": _status(r"Resumo\s+Concentre", r"Anota[cç][oõ]es\s+De\s+Participantes"),
        "anotacoes_participantes": participantes,
        "recheque": _status(r"Recheque", r"Este\s+relat[oó]rio|$"),
    }
