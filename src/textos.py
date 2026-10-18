import pandas as pd

from src.analise import Analise
from src.catalogo import Catalogo
from src.periodos import Periodo


class Textos:
    """
    Responsável por transformar os resultados da `Analise` em texto: números no
    padrão brasileiro, unidades, a frase-resumo de cada checagem e o passo a
    passo do cálculo. Separar o texto das contas deixa claro que nenhuma frase
    muda um número: elas só descrevem o que a `Analise` calculou.

    Os métodos são estáticos: a classe agrupa as regras de redação, sem estado.
    Os textos usam **negrito** em markdown, convertido em HTML pelo site.
    """

    # ------------------------------------------------------------------ números
    @staticmethod
    def fmt(valor, casas: int = 1, sinal: bool = False) -> str:
        """Formata número no padrão brasileiro: 1234.5 -> '1.234,5'."""
        if valor is None or pd.isna(valor):
            return "—"
        texto = f"{valor:+,.{casas}f}" if sinal else f"{valor:,.{casas}f}"
        return texto.replace(",", "_").replace(".", ",").replace("_", ".")

    @staticmethod
    def casas_decimais(serie_id: str) -> int:
        unidade = Catalogo.SERIES[serie_id]["unidade"]
        return 4 if unidade == "R$/US$" else (0 if "R$" in unidade else 1)

    @staticmethod
    def unidade_metrica(serie_id: str, metrica: str) -> str:
        meta = Catalogo.SERIES[serie_id]
        if meta["tipo"] == "nivel":
            if metrica == "variacao":
                return "p.p." if meta.get("variacao_em") == "pontos" else "%"
            return meta["unidade"]
        return "% a.a." if metrica == "media" else "% no mandato"

    @classmethod
    def rotulo_unidade(cls, serie_id: str, metrica: str) -> str:
        """
        Unidade para títulos de colunas e eixos. Igual a `unidade_metrica`, mas deixa
        explícito quando o número é uma mudança, e não o nível do indicador:
        "variação p.p." e "variação %" em vez de "p.p." e "%".
        """
        un = cls.unidade_metrica(serie_id, metrica)
        return f"variação {un}" if metrica == "variacao" else un

    @classmethod
    def fmt_metrica(cls, serie_id: str, metrica: str, valor) -> str:
        """Valor de uma métrica com a unidade certa: '−3,8 p.p.', '6,14% a.a.', 'R$ 1.440'."""
        if valor is None or pd.isna(valor):
            return "—"
        un = cls.unidade_metrica(serie_id, metrica)
        if metrica == "variacao":
            return f"{cls.fmt(valor, 1, sinal=True)} {un}" if un == "p.p." else f"{cls.fmt(valor, 1, sinal=True)}%"
        if Catalogo.SERIES[serie_id]["tipo"] != "nivel":
            return f"{cls.fmt(valor, 2 if metrica == 'media' else 1)}{'% a.a.' if metrica == 'media' else '%'}"
        casas = cls.casas_decimais(serie_id)
        if un.startswith("R$"):
            return f"R$ {cls.fmt(valor, casas)}"
        if un.startswith("índice"):
            return cls.fmt(valor, casas)  # a base do índice já aparece no título da coluna
        if un.startswith("%"):
            return f"{cls.fmt(valor, casas)}{un}"
        return f"{cls.fmt(valor, casas)} {un}"

    @staticmethod
    def sufixo_anos(serie_id: str, metrica: str, n: int) -> str:
        """
        Nas séries anuais (PIB, resultado primário), avisa quantos anos entram na média
        quando são menos de 4: uma média de 1 ou 2 anos (Dilma 2, Collor) é bem menos estável.
        """
        meta = Catalogo.SERIES[serie_id]
        if meta["frequencia"] != "anual" or not meta.get("aviso_anos", True):
            return ""
        if metrica not in ("media", "acumulado") or not 0 < n < 4:
            return ""
        return f" ({n} ano{'s' if n > 1 else ''})"

    # ------------------------------------------------------------------- frases
    @classmethod
    def explicar(cls, r: dict) -> list[str]:
        """
        Passo a passo do cálculo, em texto, com os números usados. É o que o
        site mostra em "Como este número foi calculado".

        Atributos:
            r: retorno de `Analise.resumo`
        """
        sid = r["serie_id"]
        meta = Catalogo.SERIES[sid]
        casas = cls.casas_decimais(sid)
        fmt, fmt_metrica = cls.fmt, cls.fmt_metrica
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
            por_ano = Periodo.PERIODOS_POR_ANO[meta["frequencia"]]
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

    @classmethod
    def frase(cls, r: dict) -> str:
        """Resumo neutro, em uma frase, do que os dados mostram para a série no mandato."""
        sid = r["serie_id"]
        meta = Catalogo.SERIES[sid]
        fmt_metrica = cls.fmt_metrica
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
            f"**{cls.fmt(mt['acumulado'], 1)}%**, o equivalente a **{cls.fmt(mt['media'], 2)}% ao ano**."
        )

    @staticmethod
    def frase_ranking(tabela: pd.DataFrame, serie_id: str, mandato_id: str) -> str | None:
        """
        Posição do mandato entre os mandatos com dados completos, ou None quando
        a série não tem direção (contexto) ou o mandato não entra no ranking.

        Atributos:
            tabela: retorno de `Analise.tabela_resumos` para a mesma defasagem
        """
        meta = Catalogo.SERIES[serie_id]
        if not meta.get("direcao"):
            return None
        chaves = [Analise.METRICA_MUDANCA[meta["tipo"]], "media"] if meta["tipo"] == "nivel" else ["media"]
        if meta.get("media_comparavel") is False:
            chaves.remove("media")
        textos = []
        for k in chaves:
            rk = Analise.ranking(tabela, serie_id, k)
            if mandato_id in rk["mandato_id"].values:
                pos = list(rk["mandato_id"]).index(mandato_id) + 1
                textos.append(f"**{pos}º de {len(rk)}** em {Analise.METRICAS[meta['tipo']][k].lower()}")
        if not textos:
            return None
        primeiro, ultimo = ("menor", "maior") if meta["direcao"] == "menor" else ("maior", "menor")
        return (
            f"Entre os mandatos com dados completos, do {primeiro} para o {ultimo} valor: "
            + " · ".join(textos) + "."
        )
