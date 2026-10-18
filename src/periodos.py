"""
Conversão dos códigos de período das APIs em intervalos de datas.

Todo dado do painel representa um intervalo [data_inicio, data_fim]:
um mês, um trimestre, um trimestre móvel ou um ano. Guardar o intervalo (e
não só uma data) é o que permite atribuir cada dado ao governo que esteve no
cargo na maior parte dele (ver src/analise.py).
"""

import pandas as pd

MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]

# Quantos meses cada período cobre
MESES_POR_PERIODO = {"mensal": 1, "trimestral_movel": 3, "trimestral": 3, "anual": 12}

# Quantos períodos de cada frequência cabem em um ano (para anualizar)
PERIODOS_POR_ANO = {"mensal": 12, "trimestral_movel": 12, "trimestral": 4, "anual": 1}


def intervalo(codigo: str, frequencia: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    """
    Converte o código de período do IBGE em (data_inicio, data_fim).

        mensal            "202608" -> 01/08/2026 a 31/08/2026
        trimestral_movel  "202608" -> 01/06/2026 a 31/08/2026 (jun-jul-ago)
        trimestral        "201504" -> 01/10/2015 a 31/12/2015 (4º trimestre)
        anual             "2016"   -> 01/01/2016 a 31/12/2016
    """
    ano = int(codigo[:4])
    if frequencia == "anual":
        inicio = pd.Timestamp(ano, 1, 1)
    elif frequencia == "trimestral":
        tri = int(codigo[4:])
        inicio = pd.Timestamp(ano, 3 * tri - 2, 1)
    else:
        mes_final = pd.Timestamp(ano, int(codigo[4:6]), 1)
        inicio = mes_final - pd.DateOffset(months=MESES_POR_PERIODO[frequencia] - 1)
    fim = inicio + pd.DateOffset(months=MESES_POR_PERIODO[frequencia]) - pd.Timedelta(days=1)
    return inicio, fim


def codigo_de_data(data: pd.Timestamp, frequencia: str) -> str:
    """Código de período (formato do IBGE) do período que começa em `data`; usado para as séries do BCB."""
    if frequencia == "anual":
        return f"{data.year}"
    if frequencia == "trimestral":
        return f"{data.year}{(data.month - 1) // 3 + 1:02d}"
    return f"{data.year}{data.month:02d}"


def rotulo(data_inicio: pd.Timestamp, data_fim: pd.Timestamp, frequencia: str) -> str:
    """Nome legível do período: 'ago/2026', 'jun-jul-ago/2026', '4º tri/2015' ou '2016'."""
    if frequencia == "anual":
        return f"{data_inicio.year}"
    if frequencia == "trimestral":
        return f"{(data_inicio.month - 1) // 3 + 1}º tri/{data_inicio.year}"
    if frequencia == "trimestral_movel":
        meses = pd.date_range(data_inicio, data_fim, freq="MS")
        return "-".join(MESES[m.month - 1] for m in meses) + f"/{data_fim.year}"
    return f"{MESES[data_inicio.month - 1]}/{data_inicio.year}"


def meio(data_inicio, data_fim):
    """Ponto médio do período (funciona com Timestamps ou Series de datas)."""
    return data_inicio + (data_fim + pd.Timedelta(days=1) - data_inicio) / 2


def referencia(data_inicio, data_fim, frequencia: str):
    """
    Data que decide a que governo o período pertence (antes da defasagem).

    - Trimestre móvel: o meio do MÊS FINAL. O IBGE identifica cada trimestre
      móvel pelo último mês ("ago/2026" = jun-jul-ago) e é assim que ele é
      noticiado; a herança de quem toma posse em janeiro fica sendo out-nov-dez,
      sempre comparada com out-nov-dez no fim do mandato (mesma estação do ano).
    - Demais frequências: o ponto médio do período, ou seja, quem governou a
      maior parte dele.
    """
    if frequencia == "trimestral_movel":
        if hasattr(data_fim, "dt"):  # Series de datas
            inicio_mes_final = data_fim - pd.to_timedelta(data_fim.dt.day - 1, unit="D")
        else:
            inicio_mes_final = data_fim.replace(day=1)
        return meio(inicio_mes_final, data_fim)
    return meio(data_inicio, data_fim)


def grade(frequencia: str, inicio: pd.Timestamp, fim: pd.Timestamp) -> pd.DataFrame:
    """Todos os períodos de uma frequência entre duas datas (para medir a cobertura dos dados)."""
    passo = 1 if frequencia == "trimestral_movel" else MESES_POR_PERIODO[frequencia]
    primeiro = pd.Timestamp(inicio.year, 1, 1)
    linhas = []
    atual = primeiro
    while atual <= fim:
        if frequencia == "trimestral_movel":
            ini, f = atual - pd.DateOffset(months=2), atual + pd.DateOffset(months=1) - pd.Timedelta(days=1)
        else:
            ini, f = atual, atual + pd.DateOffset(months=passo) - pd.Timedelta(days=1)
        linhas.append({"data_inicio": ini, "data_fim": f})
        atual = atual + pd.DateOffset(months=passo)
    return pd.DataFrame(linhas)
