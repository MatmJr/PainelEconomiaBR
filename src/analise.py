"""
Cálculos por mandato: a parte que transforma séries em afirmações checáveis.

Regra de atribuição
-------------------
Cada dado cobre um intervalo (um mês, trimestre ou ano). Ele é atribuído ao
governo que estava no cargo no PONTO MÉDIO desse intervalo, o que equivale a
dizer "ao governo que governou a maior parte do período". Exemplos:

    - maio/2016: Dilma governou até 11/05 e Temer a partir de 12/05; o ponto
      médio (16/05) cai com Temer, que governou 20 dos 31 dias;
    - o PIB de 2016: ponto médio em 02/07/2016, atribuído a Temer.

A exceção são os trimestres móveis da PNAD Contínua, atribuídos pelo MÊS FINAL,
como o IBGE os identifica e a imprensa os noticia: out-nov-dez/2018 é de Temer
(a herança de Bolsonaro) e nov-dez-jan/2019 já é de Bolsonaro. Ver
`periodos.referencia`.

Opcionalmente, aplica-se uma DEFASAGEM de N meses: o dado passa a ser
atribuído a quem governava N meses antes do ponto médio. Isso representa a
ideia de que medidas econômicas levam tempo para fazer efeito; mudar a
defasagem e ver se a conclusão se mantém é um teste de robustez.

Herança
-------
O "valor herdado" de um mandato é o último dado atribuído a um período
anterior à posse. Comparar o fim do mandato com a herança mostra o que mudou
durante o governo, em vez de premiar ou punir o governo pelo nível que
recebeu.
"""

import numpy as np
import pandas as pd

from src import periodos
from src.catalogo import SERIES
from src.presidentes import mandatos_df

METRICAS = {
    "nivel": {
        "variacao": "Variação no mandato (fim − herança)",
        "media": "Média no mandato",
        "final": "Valor no fim do mandato",
        "heranca": "Valor herdado",
    },
    "variacao_mensal": {
        "media": "Média anual (anualizada)",
        "acumulado": "Acumulado no mandato",
    },
    "variacao_anual": {
        "media": "Média anual (geométrica)",
        "acumulado": "Acumulado no mandato",
    },
}

# Métrica usada quando o placar mostra "mudança durante o mandato"
METRICA_MUDANCA = {"nivel": "variacao", "variacao_mensal": "acumulado", "variacao_anual": "acumulado"}


def unidade_metrica(serie_id: str, metrica: str) -> str:
    meta = SERIES[serie_id]
    if meta["tipo"] == "nivel":
        if metrica == "variacao":
            return "p.p." if meta.get("variacao_em") == "pontos" else "%"
        return meta["unidade"]
    return "% a.a." if metrica == "media" else "% no mandato"


def rotulo_unidade(serie_id: str, metrica: str) -> str:
    """
    Unidade para títulos de colunas e eixos. Igual a `unidade_metrica`, mas deixa
    explícito quando o número é uma mudança, e não o nível do indicador:
    "variação p.p." e "variação %" em vez de "p.p." e "%".
    """
    un = unidade_metrica(serie_id, metrica)
    return f"variação {un}" if metrica == "variacao" else un


def fmt(valor, casas: int = 1, sinal: bool = False) -> str:
    """Formata número no padrão brasileiro: 1234.5 -> '1.234,5'."""
    if valor is None or pd.isna(valor):
        return "—"
    texto = f"{valor:+,.{casas}f}" if sinal else f"{valor:,.{casas}f}"
    return texto.replace(",", "_").replace(".", ",").replace("_", ".")


def casas_decimais(serie_id: str) -> int:
    return 4 if SERIES[serie_id]["unidade"] == "R$/US$" else (0 if "R$" in SERIES[serie_id]["unidade"] else 1)


# --------------------------------------------------------------------- atribuição
def atribuir(obs: pd.DataFrame, defasagem_meses: int = 0) -> pd.DataFrame:
    """
    Acrescenta a cada observação o ponto médio do período (`data_meio`), a
    data usada para atribuição (`data_atribuicao` = data de referência −
    defasagem; ver `periodos.referencia`) e o mandato correspondente (`mandato`).
    """
    df = obs.copy()
    df["data_meio"] = periodos.meio(df["data_inicio"], df["data_fim"])
    referencia = df["data_meio"].copy()
    for freq in ("trimestral_movel",):
        ids = [sid for sid, meta in SERIES.items() if meta["frequencia"] == freq]
        sel = df["serie_id"].isin(ids)
        if sel.any():
            referencia[sel] = periodos.referencia(df.loc[sel, "data_inicio"], df.loc[sel, "data_fim"], freq)
    df["data_atribuicao"] = referencia - pd.DateOffset(months=defasagem_meses)

    mandatos = mandatos_df()
    inicios = mandatos["inicio"].to_numpy()
    fim_ultimo = mandatos["fim"].iloc[-1] + pd.Timedelta(days=1)

    # Os mandatos são contíguos: basta achar o último que começou antes da data
    pos = np.searchsorted(inicios, df["data_atribuicao"].to_numpy(), side="right") - 1
    valido = (pos >= 0) & (df["data_atribuicao"] < fim_ultimo).to_numpy()
    df["mandato"] = np.where(valido, mandatos["id"].to_numpy()[pos.clip(0)], None)
    return df


def _esperados(frequencia: str, inicio: pd.Timestamp, fim: pd.Timestamp, defasagem_meses: int) -> int:
    """Quantos períodos da frequência seriam atribuídos ao mandato se a série fosse completa."""
    g = periodos.grade(frequencia, inicio - pd.DateOffset(years=2), fim + pd.DateOffset(years=2))
    ref = periodos.referencia(g["data_inicio"], g["data_fim"], frequencia) - pd.DateOffset(months=defasagem_meses)
    return int(((ref >= inicio) & (ref < fim + pd.Timedelta(days=1))).sum())


# ------------------------------------------------------------------------ resumo
def resumo(atribuidas: pd.DataFrame, serie_id: str, mandato_id: str, defasagem_meses: int = 0) -> dict:
    """
    Resume uma série durante um mandato. Devolve as métricas, as linhas
    usadas no cálculo (para checagem) e o status de cobertura dos dados.

    Atributos:
        atribuidas: observações já passadas por `atribuir` (com a mesma defasagem)
        serie_id: chave da série no catálogo
        mandato_id: id do mandato (ver src/presidentes.py)
        defasagem_meses: a mesma defasagem usada em `atribuir`
    """
    meta = SERIES[serie_id]
    m = mandatos_df().set_index("id").loc[mandato_id]

    s = atribuidas[atribuidas["serie_id"] == serie_id].sort_values("data_inicio")
    dentro = s[s["mandato"] == mandato_id]
    antes = s[s["data_atribuicao"] < m["inicio"]]
    heranca = antes.iloc[-1] if len(antes) else None

    esperado = _esperados(meta["frequencia"], m["inicio"], m["fim"], defasagem_meses)
    em_curso = m["fim"] > pd.Timestamp.today()

    if dentro.empty:
        status = "sem dados"
    elif heranca is None and meta["tipo"] == "nivel":
        status = "sem valor herdado"
    elif len(dentro) < esperado:
        status = "mandato em curso" if em_curso else "dados parciais"
    else:
        status = "completo"

    r = {
        "serie_id": serie_id,
        "mandato_id": mandato_id,
        "rotulo": m["rotulo"],
        "presidente": m["presidente"],
        "tipo": meta["tipo"],
        "n": len(dentro),
        "esperado": esperado,
        "cobertura": len(dentro) / esperado if esperado else np.nan,
        "status": status,
        "linhas": dentro,
        "heranca": heranca,
        "metricas": {},
    }
    if dentro.empty:
        return r

    v = dentro["valor"]
    if meta["tipo"] == "nivel":
        final = v.iloc[-1]
        ini = heranca["valor"] if heranca is not None else np.nan
        if meta.get("variacao_em") == "percentual":
            variacao = (final / ini - 1) * 100
        else:
            variacao = final - ini
        r["metricas"] = {
            "variacao": variacao,
            "media": v.mean(),
            "final": final,
            "heranca": ini,
            "minimo": v.min(),
            "maximo": v.max(),
        }
    else:
        fator = (1 + v / 100).prod()
        por_ano = periodos.PERIODOS_POR_ANO[meta["frequencia"]]
        r["metricas"] = {
            "acumulado": (fator - 1) * 100,
            "media": (fator ** (por_ano / len(v)) - 1) * 100,
            "minimo": v.min(),
            "maximo": v.max(),
        }
    return r


def placar(obs: pd.DataFrame, series: list[str], defasagem_meses: int = 0) -> pd.DataFrame:
    """Resumo de todas as séries × todos os mandatos, em formato longo (uma linha por par)."""
    atribuidas = atribuir(obs, defasagem_meses)
    linhas = []
    for sid in series:
        for mid in mandatos_df()["id"]:
            r = resumo(atribuidas, sid, mid, defasagem_meses)
            linha = {k: r[k] for k in ("serie_id", "mandato_id", "rotulo", "n", "esperado", "cobertura", "status")}
            linha.update(r["metricas"])
            linhas.append(linha)
    return pd.DataFrame(linhas)


def ranking(tabela: pd.DataFrame, serie_id: str, metrica: str) -> pd.DataFrame:
    """
    Ordena os mandatos de uma série pela métrica, do melhor para o pior
    segundo a `direcao` do catálogo. Só entram mandatos com status
    "completo", para não comparar governos com dados pela metade.
    """
    direcao = SERIES[serie_id].get("direcao")
    t = tabela[(tabela["serie_id"] == serie_id) & (tabela["status"] == "completo")].dropna(subset=[metrica])
    if direcao is None:
        return t.sort_values(metrica)
    return t.sort_values(metrica, ascending=(direcao == "menor"))


# ------------------------------------------------------------------- explicação
def explicar(r: dict) -> list[str]:
    """
    Passo a passo do cálculo, em texto, com os números usados. É o que o
    dashboard mostra em "Como este número foi calculado".
    """
    sid = r["serie_id"]
    meta = SERIES[sid]
    casas = casas_decimais(sid)
    linhas_txt = []
    d = r["linhas"]

    if d.empty:
        return ["Não há nenhum dado desta série atribuído a este mandato."]

    linhas_txt.append(
        f"**Períodos usados:** {len(d)} ({d['periodo_rotulo'].iloc[0]} a {d['periodo_rotulo'].iloc[-1]}), "
        f"de {r['esperado']} que caberiam no mandato pela regra de atribuição."
    )
    mt = r["metricas"]

    if meta["tipo"] == "nivel":
        h = r["heranca"]
        if h is not None:
            linhas_txt.append(f"**Valor herdado:** {fmt_metrica(sid, 'heranca', h['valor'])} em {h['periodo_rotulo']} (último dado atribuído ao governo anterior).")
        else:
            linhas_txt.append("**Valor herdado:** indisponível — a série começa depois da posse.")
        linhas_txt.append(f"**Valor no fim:** {fmt_metrica(sid, 'final', mt['final'])} em {d['periodo_rotulo'].iloc[-1]}.")
        if h is not None:
            if meta.get("variacao_em") == "percentual":
                linhas_txt.append(
                    f"**Variação:** ({fmt(mt['final'], casas)} ÷ {fmt(h['valor'], casas)} − 1) × 100 = "
                    f"**{fmt(mt['variacao'], 1, sinal=True)}%**."
                )
            else:
                linhas_txt.append(
                    f"**Variação:** {fmt(mt['final'], casas)} − {fmt(h['valor'], casas)} = "
                    f"**{fmt(mt['variacao'], 1, sinal=True)} p.p.**"
                )
        linhas_txt.append(
            f"**Média no mandato:** soma dos {len(d)} valores ÷ {len(d)} = **{fmt_metrica(sid, 'media', mt['media'])}** "
            f"(mínimo {fmt(mt['minimo'], casas)}, máximo {fmt(mt['maximo'], casas)})."
        )
    else:
        por_ano = periodos.PERIODOS_POR_ANO[meta["frequencia"]]
        linhas_txt.append(
            f"**Acumulado:** (1 + v₁/100) × (1 + v₂/100) × … × (1 + v{len(d)}/100) − 1 = "
            f"**{fmt(mt['acumulado'], 1)}%**."
        )
        linhas_txt.append(
            f"**Média anual:** (1 + {fmt(mt['acumulado'], 1)}/100)^({por_ano}/{len(d)}) − 1 = "
            f"**{fmt(mt['media'], 2)}% ao ano**. É a taxa constante que, repetida todo ano, "
            f"daria o mesmo acumulado."
        )
        linhas_txt.append(
            f"**Menor e maior valor no período:** {fmt(mt['minimo'], 2)}% e {fmt(mt['maximo'], 2)}%."
        )

    if r["status"] != "completo":
        linhas_txt.append(f"⚠️ **Atenção:** {r['status']} — compare com cautela.")
    return linhas_txt


# ------------------------------------------------------------------ trajetórias
def trajetorias(atribuidas: pd.DataFrame, serie_id: str) -> pd.DataFrame:
    """
    Trajetória de cada mandato alinhada pela posse (eixo x = meses desde a
    posse), para comparar governos lado a lado partindo do mesmo ponto.

    - séries de nível: valor em relação à herança (p.p. ou %), começando em 0;
    - séries de variação: acumulado desde a posse (%), começando em 0.
    """
    meta = SERIES[serie_id]
    mandatos = mandatos_df().set_index("id")
    s = atribuidas[atribuidas["serie_id"] == serie_id].sort_values("data_inicio")
    partes = []

    for mid, m in mandatos.iterrows():
        dentro = s[s["mandato"] == mid]
        if dentro.empty:
            continue
        meses = ((dentro["data_atribuicao"] - m["inicio"]).dt.days / 30.4375).round(1)

        if meta["tipo"] == "nivel":
            antes = s[s["data_atribuicao"] < m["inicio"]]
            if antes.empty:
                continue
            base = antes["valor"].iloc[-1]
            if meta.get("variacao_em") == "percentual":
                y = (dentro["valor"] / base - 1) * 100
            else:
                y = dentro["valor"] - base
        else:
            y = ((1 + dentro["valor"] / 100).cumprod() - 1) * 100

        parte = pd.DataFrame({"meses": meses, "valor": y, "periodo_rotulo": dentro["periodo_rotulo"]})
        inicio = pd.DataFrame({"meses": [0.0], "valor": [0.0], "periodo_rotulo": ["posse"]})
        parte = pd.concat([inicio, parte], ignore_index=True)
        parte["mandato"] = m["rotulo"]
        partes.append(parte)

    return pd.concat(partes, ignore_index=True) if partes else pd.DataFrame()


# --------------------------------------------------------------------- conferências
def acumulado_12m(obs_mensal: pd.DataFrame) -> pd.DataFrame:
    """Variação acumulada em 12 meses a partir das variações mensais: produto dos 12 últimos fatores."""
    s = obs_mensal.sort_values("data_inicio").copy()
    fator = (1 + s["valor"] / 100).rolling(12).apply(np.prod, raw=True)
    s["valor"] = (fator - 1) * 100
    return s.dropna(subset=["valor"])


def conferir_ipca_12m(obs: pd.DataFrame) -> pd.DataFrame:
    """
    Compara o IPCA em 12 meses calculado pelo painel (a partir das variações
    mensais) com o divulgado pelo IBGE. Serve para mostrar que a conta de
    acumulação usada nos mandatos reproduz o número oficial.
    """
    calc = acumulado_12m(obs[obs["serie_id"] == "ipca"])[["periodo", "periodo_rotulo", "valor"]]
    oficial = obs[obs["serie_id"] == "ipca_12m_ibge"][["periodo", "valor"]]
    t = calc.merge(oficial, on="periodo", suffixes=("_calculado", "_ibge"))
    t["diferenca"] = t["valor_calculado"] - t["valor_ibge"]
    return t


# ------------------------------------------------------------------- textos prontos
def fmt_metrica(serie_id: str, metrica: str, valor) -> str:
    """Valor de uma métrica com a unidade certa: '−3,8 p.p.', '6,14% a.a.', 'R$ 1.440'."""
    if valor is None or pd.isna(valor):
        return "—"
    un = unidade_metrica(serie_id, metrica)
    if metrica == "variacao":
        return f"{fmt(valor, 1, sinal=True)} {un}" if un == "p.p." else f"{fmt(valor, 1, sinal=True)}%"
    if SERIES[serie_id]["tipo"] != "nivel":
        return f"{fmt(valor, 2 if metrica == 'media' else 1)}{'% a.a.' if metrica == 'media' else '%'}"
    casas = casas_decimais(serie_id)
    if un.startswith("R$"):
        return f"R$ {fmt(valor, casas)}"
    if un.startswith("índice"):
        return fmt(valor, casas)  # a base do índice já aparece no título da coluna
    if un.startswith("%"):
        return f"{fmt(valor, casas)}{un}"
    return f"{fmt(valor, casas)} {un}"


def sufixo_anos(serie_id: str, metrica: str, n: int) -> str:
    """
    Nas séries anuais (PIB, resultado primário), avisa quantos anos entram na média
    quando são menos de 4: uma média de 1 ou 2 anos (Dilma 2, Collor) é bem menos estável.
    """
    meta = SERIES[serie_id]
    if meta["frequencia"] != "anual" or not meta.get("aviso_anos", True):
        return ""
    if metrica not in ("media", "acumulado") or not 0 < n < 4:
        return ""
    return f" ({n} ano{'s' if n > 1 else ''})"


def frase(r: dict) -> str:
    """Resumo neutro, em uma frase, do que os dados mostram para a série no mandato."""
    sid = r["serie_id"]
    meta = SERIES[sid]
    d = r["linhas"]
    if d.empty:
        return f"Não há dados de **{meta['nome']}** para o mandato {r['rotulo']}."

    mt = r["metricas"]
    primeiro, ultimo = d["periodo_rotulo"].iloc[0], d["periodo_rotulo"].iloc[-1]
    janela = f"em {primeiro}" if primeiro == ultimo else f"entre {primeiro} e {ultimo}"
    if meta["tipo"] == "nivel":
        h = r["heranca"]
        if h is None:
            return (
                f"No mandato {r['rotulo']} ({janela}), **{meta['nome']}** teve média de "
                f"**{fmt_metrica(sid, 'media', mt['media'])}** e terminou em "
                f"**{fmt_metrica(sid, 'final', mt['final'])}**. Não há valor herdado para comparar."
            )
        return (
            f"No mandato {r['rotulo']}, **{meta['nome']}** passou de "
            f"**{fmt_metrica(sid, 'heranca', mt['heranca'])}** ({h['periodo_rotulo']}, herança) para "
            f"**{fmt_metrica(sid, 'final', mt['final'])}** ({d['periodo_rotulo'].iloc[-1]}): "
            f"variação de **{fmt_metrica(sid, 'variacao', mt['variacao'])}**; "
            f"a média no período foi {fmt_metrica(sid, 'media', mt['media'])}."
        )
    return (
        f"No mandato {r['rotulo']} ({janela}), **{meta['nome']}** acumulou "
        f"**{fmt(mt['acumulado'], 1)}%**, o equivalente a **{fmt(mt['media'], 2)}% ao ano**."
    )


def frase_ranking(tabela: pd.DataFrame, serie_id: str, mandato_id: str) -> str | None:
    """
    Posição do mandato entre os mandatos com dados completos, ou None quando
    a série não tem direção (contexto) ou o mandato não entra no ranking.
    `tabela` é o retorno de `placar` para a mesma defasagem.
    """
    meta = SERIES[serie_id]
    if not meta.get("direcao"):
        return None
    chaves = [METRICA_MUDANCA[meta["tipo"]], "media"] if meta["tipo"] == "nivel" else ["media"]
    if meta.get("media_comparavel") is False:
        chaves.remove("media")
    textos = []
    for k in chaves:
        rk = ranking(tabela, serie_id, k)
        if mandato_id in rk["mandato_id"].values:
            pos = list(rk["mandato_id"]).index(mandato_id) + 1
            textos.append(f"**{pos}º de {len(rk)}** em {METRICAS[meta['tipo']][k].lower()}")
    if not textos:
        return None
    melhor, pior = ("menor", "maior") if meta["direcao"] == "menor" else ("maior", "menor")
    return (
        f"Entre os mandatos com dados completos, ordenando do {melhor} valor para o {pior} "
        f"({melhor} é melhor): " + " · ".join(textos) + "."
    )
