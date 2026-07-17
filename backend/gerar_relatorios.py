"""
Gera um PDF por empresa com o JSON bruto de dados_extraidos.
Uso: python gerar_relatorios.py
"""
import json
from fpdf import FPDF

EMPRESAS = [
    {
        "arquivo": "relatorio_JBS_02916265000160.pdf",
        "dados": {
            "cabecalho": {
                "data_consulta": "20260717 - 11:46:52"
            },
            "informacoes_cadastrais": {
                "cnpj": "02.916.265/0001-60",
                "tipo": "SOCIEDADE ANONIMA",
                "situacao_cnpj": "ATIVA",
                "data_situacao": "26/06/2026",
                "nome_fantasia": "JBS S/A",
                "nire": "35300330587",
                "endereco": "AV MARGINAL DIREITA DO TIETE 500 - VL JAGUARA SAO PAULO - SP CEP: 005118100",
                "data_fundacao": "10/12/1998",
                "num_empregados": "20506",
                "ramo": "ABATE DE BOVINOS",
                "cnae": "044",
                "quantidade_filiais": 20
            },
            "socios_administradores": {
                "capital_social": "R$ 23.631.071.304,00",
                "capital_realizado": "R$ 23.631.071.304,00",
                "nacionalidade": "BRASIL",
                "origem": "PRIVADO",
                "natureza": "ABERTO",
                "participacoes_participada": [
                    {"cpf_cnpj": "04.109.847/0001-60", "empresa_ligada": "JBS EMBALAGENS METALICAS LTDA"},
                    {"cpf_cnpj": "09.084.219/0001-90", "empresa_ligada": "JBS CONFINAMENTO LTDA"},
                    {"cpf_cnpj": "10.799.023/0001-61", "empresa_ligada": "JBS SLOVAKIA HOLDINGS SRO"}
                ]
            },
            "consultas": {
                "historico_mensal": [
                    {"mes_ano": "JUL/26", "quantidade": 152},
                    {"mes_ano": "JUN/26", "quantidade": 284},
                    {"mes_ano": "MAI/26", "quantidade": 197},
                    {"mes_ano": "ABR/26", "quantidade": 210},
                    {"mes_ano": "MAR/26", "quantidade": 188}
                ]
            },
            "informacoes_comportamentais": {
                "historico_pagamentos": {
                    "classificacao": "PONTUAL",
                    "faixa_titulos": "30 MIL A 40 MIL"
                },
                "referenciais_negocios": {
                    "ultima_compra": {"data": "JUL/2026", "valor": "C16 - 600 MIL A 700 MIL", "media": "C7 - 45 MIL A 47 MIL"},
                    "maior_fatura":  {"data": "JUN/2026", "valor": "D7 - 7 MI A 7,5 MI",      "media": "C10 - 70 MIL A 100 MIL"},
                    "maior_acumulo": {"data": "JUN/2026", "valor": "D16 - 25 MI A 30 MI",     "media": "C15 - 500 MIL A 600 MIL"}
                }
            },
            "anotacoes_negativas": {
                "pefin": "NADA CONSTA",
                "refin": "NADA CONSTA",
                "concentre_variacoes": 2,
                "concentre_resumo": "14 DIVIDA VENCIDA | 1 ACAO JUDICIAL | 9 PROTESTO (R$ 343.020,00)"
            }
        }
    },
    {
        "arquivo": "relatorio_BRF_01838723000127.pdf",
        "dados": {
            "cabecalho": {
                "data_consulta": "20260717 - 11:46:52"
            },
            "informacoes_cadastrais": {
                "cnpj": "01.838.723/0001-27",
                "tipo": "SOCIEDADE ANONIMA",
                "situacao_cnpj": "ATIVA",
                "data_situacao": "16/07/2026",
                "nome_fantasia": "BRF S/A",
                "nire": "42300034240",
                "data_fundacao": "18/08/1934",
                "num_empregados": "91034",
                "ramo": "INDUSTRIALIZACAO DE CARNES/AVES",
                "quantidade_filiais": 20
            },
            "socios_administradores": {
                "quadro_administrativo": [
                    "MIGUEL GULARTE LOPEZ - DIRETOR PRESIDENTE",
                    "FABIO MARIANO MOREIRA - DIRETOR",
                    "CARLOS ANTONIO COSTA MINUCCI - DIRETOR",
                    "PEDRO DE ANDRADE FARIA - DIRETOR",
                    "AUGUSTO RIBEIRO DE MENDONCA NETO - DIRETOR",
                    "LORIVAL NOGUEIRA LUZ JUNIOR - DIRETOR",
                    "PATRICIA DALLASTA - DIRETOR"
                ],
                "participacoes_participada": [
                    "BRF ENERGIA S/A",
                    "BRF PET S/A",
                    "GRANOLEO S/A",
                    "MBR INVESTIMENTOS"
                ]
            },
            "consultas": {
                "historico_mensal": [
                    {"mes_ano": "JUL/26", "quantidade": 98},
                    {"mes_ano": "JUN/26", "quantidade": 143},
                    {"mes_ano": "MAI/26", "quantidade": 120},
                    {"mes_ano": "ABR/26", "quantidade": 135},
                    {"mes_ano": "MAR/26", "quantidade": 112}
                ]
            },
            "informacoes_comportamentais": {
                "historico_pagamentos": {
                    "classificacao": "PONTUAL",
                    "faixa_titulos": "100 MIL A 200 MIL"
                },
                "referenciais_negocios": {
                    "ultima_compra": {"data": "JUL/2026", "valor": "D2 - 4,5 MI A 5 MI",    "media": "C6 - 43 MIL A 45 MIL"},
                    "maior_fatura":  {"data": "MAR/2026", "valor": "D13 - 10 MI A 15 MI",   "media": "C11 - 100 MIL A 200 MIL"},
                    "maior_acumulo": {"data": "JUL/2026", "valor": "D21 - 200 MI A 300 MI", "media": "C21 - 1,5 MI A 2 MI"}
                }
            },
            "anotacoes_negativas": {
                "pefin": "NADA CONSTA",
                "refin": "NADA CONSTA",
                "concentre_variacoes": 5,
                "concentre_resumo": "12 DIVIDA VENCIDA | 11 ACAO JUDICIAL | 92 PROTESTO (R$ 2.539.539,00)"
            }
        }
    }
]


def gerar_pdf(empresa: dict) -> None:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Courier", size=8)

    texto = json.dumps(empresa["dados"], indent=2, ensure_ascii=False)

    for linha in texto.splitlines():
        pdf.cell(0, 4, txt=linha, ln=True)

    pdf.output(empresa["arquivo"])
    print(f"Gerado: {empresa['arquivo']}")


if __name__ == "__main__":
    for emp in EMPRESAS:
        gerar_pdf(emp)
