import pandas as pd

from src import periodos
from src.catalogo import SERIES

# Símbolos que o IBGE usa no lugar de um número
SIMBOLOS_SEM_DADO = {"...", "-", "X", "..", ""}


class Transform:
    """
    Responsável por transformar as respostas brutas das APIs (camada bronze)
    em um único DataFrame "longo", com uma linha por série e período (camada
    prata):

        serie_id | periodo | periodo_rotulo | data_inicio | data_fim | valor

    O formato é o mesmo para IBGE e BCB, então o dashboard e os cálculos por
    mandato não precisam saber de onde veio cada dado.
    """

    def _linhas_ibge(self, resposta: list[dict]) -> dict[str, str]:
        """Extrai o dicionário {código do período: valor} da resposta do IBGE (Brasil, sem quebras)."""
        return resposta[0]["resultados"][0]["series"][0]["serie"]

    def _linhas_bcb(self, resposta: list[dict], frequencia: str) -> dict[str, str]:
        """
        Converte a lista [{"data": "dd/mm/aaaa", "valor": "x"}] do SGS para o mesmo
        formato do IBGE. Em séries diárias (ex.: meta Selic), vários dias caem no
        mesmo mês: como a lista é percorrida em ordem de data, fica o valor do
        último dia do mês.
        """
        datados = sorted((pd.to_datetime(item["data"], format="%d/%m/%Y"), item["valor"]) for item in resposta)
        linhas = {}
        for data, valor in datados:
            linhas[periodos.codigo_de_data(data, frequencia)] = valor
        return linhas

    def transform_serie(self, pacote: dict) -> pd.DataFrame:
        """
        Transforma o pacote bruto de uma série (retorno de `Extract.extrair`).

        Regras aplicadas, na ordem:
            1. símbolos do IBGE sem dado ("...", "-", "X") viram nulo e são descartados;
            2. períodos anteriores a `a_partir_de` são descartados;
            3. períodos que ainda não começaram são descartados (o SGS publica o
               salário mínimo de meses futuros já definidos em lei);
            4. os valores são multiplicados por `fator`, quando houver.
        """
        serie_id = pacote["serie_id"]
        meta = SERIES[serie_id]
        frequencia = meta["frequencia"]

        if pacote["fonte"] == "ibge":
            brutos = self._linhas_ibge(pacote["resposta"])
        else:
            resposta = pacote["resposta"]
            if meta.get("so_dezembro"):
                # Acumulado em 12 meses lido como resultado do ano: só dezembro conta
                resposta = [item for item in resposta if item["data"][3:5] == "12"]
            brutos = self._linhas_bcb(resposta, frequencia)

        linhas = []
        for codigo, valor in brutos.items():
            if valor is None or str(valor).strip() in SIMBOLOS_SEM_DADO:
                continue
            inicio, fim = periodos.intervalo(codigo, frequencia)
            linhas.append(
                {
                    "serie_id": serie_id,
                    "periodo": codigo,
                    "periodo_rotulo": periodos.rotulo(inicio, fim, frequencia),
                    "data_inicio": inicio,
                    "data_fim": fim,
                    "valor": float(valor),
                }
            )

        df = pd.DataFrame(linhas).sort_values("data_inicio", ignore_index=True)

        if meta.get("a_partir_de"):
            df = df[df["data_inicio"] >= pd.Timestamp(meta["a_partir_de"])]
        df = df[df["data_inicio"] <= pd.Timestamp.today()]
        df["valor"] = df["valor"] * meta.get("fator", 1)

        print(f"Série '{serie_id}' transformada: {len(df)} períodos.")
        return df.reset_index(drop=True)

    def deflacionar(self, df: pd.DataFrame, indice: pd.DataFrame) -> pd.DataFrame:
        """
        Converte uma série em reais correntes para reais do mês mais recente
        do índice de preços: valor_real(t) = valor(t) × índice(último) / índice(t).
        Meses sem índice divulgado ainda são descartados.

        Atributos:
            df: série nominal já transformada (ex.: salário mínimo)
            indice: número-índice de preços já transformado (ex.: ipca_indice)
        """
        base = indice.set_index("periodo")["valor"]
        ultimo = indice.sort_values("data_inicio")["valor"].iloc[-1]

        df = df[df["periodo"].isin(base.index)].copy()
        df["valor"] = df["valor"] * ultimo / df["periodo"].map(base)

        print(f"Série '{df['serie_id'].iloc[0]}' deflacionada: {len(df)} períodos.")
        return df.reset_index(drop=True)

    def transform_todas(self, pacotes: dict[str, dict]) -> pd.DataFrame:
        """Transforma todos os pacotes extraídos e aplica os deflatores indicados no catálogo."""
        series = {sid: self.transform_serie(p) for sid, p in pacotes.items()}

        for sid, df in series.items():
            deflator = SERIES[sid].get("deflacionar_por")
            if deflator:
                series[sid] = self.deflacionar(df, series[deflator])

        return pd.concat(series.values(), ignore_index=True)
