import numpy as np
import pandas as pd

from src.catalogo import Catalogo
from src.periodos import Periodo
from src.presidentes import Mandatos


class Analise:
    """
    Responsável pelos cálculos por mandato: a parte que transforma séries em
    afirmações checáveis. Cada instância guarda as observações da camada prata
    e reaproveita a atribuição a mandatos de cada defasagem já calculada.

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
    `Periodo.referencia`.

    Opcionalmente, aplica-se uma DEFASAGEM de N meses: o dado passa a ser
    atribuído a quem governava N meses antes. Isso representa a ideia de que
    medidas econômicas levam tempo para fazer efeito; mudar a defasagem e ver se
    a conclusão se mantém é um teste de robustez.

    Herança
    -------
    O "valor herdado" de um mandato é o último dado atribuído a um período
    anterior à posse. Comparar o fim do mandato com a herança mostra o que mudou
    durante o governo, em vez de premiar ou punir o governo pelo nível que
    recebeu.
    """

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

    # Métrica usada quando o site mostra "mudança durante o mandato"
    METRICA_MUDANCA = {"nivel": "variacao", "variacao_mensal": "acumulado", "variacao_anual": "acumulado"}

    def __init__(self, obs: pd.DataFrame):
        """
        Atributos:
            obs: observações da camada prata (serie_id, periodo, periodo_rotulo,
                data_inicio, data_fim, valor)
        """
        self.obs = obs
        self.mandatos = Mandatos.tabela()
        self._atribuidas = {}  # defasagem -> observações já atribuídas

    # ----------------------------------------------------------------- atribuição
    def atribuir(self, defasagem_meses: int = 0) -> pd.DataFrame:
        """
        Devolve as observações com o ponto médio do período (`data_meio`), a data
        usada para atribuição (`data_atribuicao` = data de referência − defasagem;
        ver `Periodo.referencia`) e o mandato correspondente (`mandato`). O
        resultado de cada defasagem é calculado uma vez e reaproveitado.
        """
        if defasagem_meses in self._atribuidas:
            return self._atribuidas[defasagem_meses]

        df = self.obs.copy()
        df["data_meio"] = Periodo.meio(df["data_inicio"], df["data_fim"])
        referencia = df["data_meio"].copy()
        for freq in ("trimestral_movel",):
            ids = [sid for sid, meta in Catalogo.SERIES.items() if meta["frequencia"] == freq]
            sel = df["serie_id"].isin(ids)
            if sel.any():
                referencia[sel] = Periodo.referencia(df.loc[sel, "data_inicio"], df.loc[sel, "data_fim"], freq)
        df["data_atribuicao"] = referencia - pd.DateOffset(months=defasagem_meses)

        inicios = self.mandatos["inicio"].to_numpy()
        fim_ultimo = self.mandatos["fim"].iloc[-1] + pd.Timedelta(days=1)

        # Os mandatos são contíguos: basta achar o último que começou antes da data
        pos = np.searchsorted(inicios, df["data_atribuicao"].to_numpy(), side="right") - 1
        valido = (pos >= 0) & (df["data_atribuicao"] < fim_ultimo).to_numpy()
        df["mandato"] = np.where(valido, self.mandatos["id"].to_numpy()[pos.clip(0)], None)

        self._atribuidas[defasagem_meses] = df
        return df

    @staticmethod
    def _esperados(frequencia: str, inicio: pd.Timestamp, fim: pd.Timestamp, defasagem_meses: int) -> int:
        """Quantos períodos da frequência seriam atribuídos ao mandato se a série fosse completa."""
        g = Periodo.grade(frequencia, inicio - pd.DateOffset(years=2), fim + pd.DateOffset(years=2))
        ref = Periodo.referencia(g["data_inicio"], g["data_fim"], frequencia) - pd.DateOffset(months=defasagem_meses)
        return int(((ref >= inicio) & (ref < fim + pd.Timedelta(days=1))).sum())

    # --------------------------------------------------------------------- resumo
    def resumo(self, serie_id: str, mandato_id: str, defasagem_meses: int = 0) -> dict:
        """
        Resume uma série durante um mandato. Devolve as métricas, as linhas
        usadas no cálculo (para checagem) e o status de cobertura dos dados.

        Atributos:
            serie_id: chave da série no catálogo
            mandato_id: id do mandato (ver `Mandatos`)
            defasagem_meses: defasagem usada na atribuição
        """
        meta = Catalogo.SERIES[serie_id]
        m = self.mandatos.set_index("id").loc[mandato_id]
        atribuidas = self.atribuir(defasagem_meses)

        s = atribuidas[atribuidas["serie_id"] == serie_id].sort_values("data_inicio")
        dentro = s[s["mandato"] == mandato_id]
        antes = s[s["data_atribuicao"] < m["inicio"]]
        heranca = antes.iloc[-1] if len(antes) else None

        esperado = self._esperados(meta["frequencia"], m["inicio"], m["fim"], defasagem_meses)
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
            por_ano = Periodo.PERIODOS_POR_ANO[meta["frequencia"]]
            r["metricas"] = {
                "acumulado": (fator - 1) * 100,
                "media": (fator ** (por_ano / len(v)) - 1) * 100,
                "minimo": v.min(),
                "maximo": v.max(),
            }
        return r

    def tabela_resumos(self, series: list[str], defasagem_meses: int = 0) -> pd.DataFrame:
        """Resumo de todas as séries × todos os mandatos, em formato longo (uma linha por par)."""
        linhas = []
        for sid in series:
            for mid in self.mandatos["id"]:
                r = self.resumo(sid, mid, defasagem_meses)
                linha = {k: r[k] for k in ("serie_id", "mandato_id", "rotulo", "n", "esperado", "cobertura", "status")}
                linha.update(r["metricas"])
                linhas.append(linha)
        return pd.DataFrame(linhas)

    @staticmethod
    def ranking(tabela: pd.DataFrame, serie_id: str, metrica: str) -> pd.DataFrame:
        """
        Ordena os mandatos de uma série pela métrica, começando pelo valor em
        destaque segundo a `direcao` do catálogo. Só entram mandatos com status
        "completo", para não comparar governos com dados pela metade.

        Atributos:
            tabela: retorno de `tabela_resumos`
        """
        direcao = Catalogo.SERIES[serie_id].get("direcao")
        t = tabela[(tabela["serie_id"] == serie_id) & (tabela["status"] == "completo")].dropna(subset=[metrica])
        if direcao is None:
            return t.sort_values(metrica)
        return t.sort_values(metrica, ascending=(direcao == "menor"))

    # ---------------------------------------------------------------- trajetórias
    def trajetorias(self, serie_id: str, defasagem_meses: int = 0) -> pd.DataFrame:
        """
        Trajetória de cada mandato alinhada pela posse (eixo x = meses desde a
        posse), para comparar governos lado a lado partindo do mesmo ponto.

        - séries de nível: valor em relação à herança (p.p. ou %), começando em 0;
        - séries de variação: acumulado desde a posse (%), começando em 0.

        Cada ponto fica no FIM do seu período (menos a defasagem), porque o valor
        acumulado só se completa ali: o PIB do 1º ano fica no mês 12 e o do 4º no
        mês 48, e janeiro fica no mês 1.
        """
        meta = Catalogo.SERIES[serie_id]
        atribuidas = self.atribuir(defasagem_meses)
        s = atribuidas[atribuidas["serie_id"] == serie_id].sort_values("data_inicio")
        partes = []

        for mid, m in self.mandatos.set_index("id").iterrows():
            dentro = s[s["mandato"] == mid]
            if dentro.empty:
                continue
            fim_periodo = dentro["data_fim"] + pd.Timedelta(days=1) - pd.DateOffset(months=defasagem_meses)
            meses = ((fim_periodo - m["inicio"]).dt.days / 30.4375).round(1)

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

    # --------------------------------------------------------------- conferências
    @staticmethod
    def acumulado_12m(obs_mensal: pd.DataFrame) -> pd.DataFrame:
        """Variação acumulada em 12 meses a partir das variações mensais: produto dos 12 últimos fatores."""
        s = obs_mensal.sort_values("data_inicio").copy()
        fator = (1 + s["valor"] / 100).rolling(12).apply(np.prod, raw=True)
        s["valor"] = (fator - 1) * 100
        return s.dropna(subset=["valor"])

    def conferir_ipca_12m(self) -> pd.DataFrame:
        """
        Compara o IPCA em 12 meses calculado pelo painel (a partir das variações
        mensais) com o divulgado pelo IBGE. Serve para mostrar que a conta de
        acumulação usada nos mandatos reproduz o número oficial.
        """
        obs = self.obs
        calc = self.acumulado_12m(obs[obs["serie_id"] == "ipca"])[["periodo", "periodo_rotulo", "valor"]]
        oficial = obs[obs["serie_id"] == "ipca_12m_ibge"][["periodo", "valor"]]
        t = calc.merge(oficial, on="periodo", suffixes=("_calculado", "_ibge"))
        t["diferenca"] = t["valor_calculado"] - t["valor_ibge"]
        return t
