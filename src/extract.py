import time
from datetime import date, datetime, timezone

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.catalogo import SERIES, montar_url


class Extract:
    """
    Responsável por extrair as séries do catálogo (src/catalogo.py) das APIs
    públicas do IBGE (agregados/SIDRA) e do Banco Central (SGS).

    Cada extração devolve um "pacote" com a resposta bruta da API e os dados
    de proveniência (URLs consultadas e data da extração), que é o que fica
    guardado na camada bronze e permite refazer a conta a partir da fonte.
    """

    # O SGS limita cada consulta a uma janela de 10 anos
    ANOS_POR_CONSULTA_BCB = 10
    ANO_INICIAL_BCB = 1980

    def __init__(self, timeout: int = 120):
        self.timeout = timeout
        self.session = requests.Session()
        # As APIs públicas oscilam (o SGS devolve 502/503 com frequência): tenta
        # de novo até 5 vezes, esperando 2, 4, 8, 16 s entre as tentativas
        retry = Retry(total=5, backoff_factor=2, status_forcelist=[429, 500, 502, 503, 504])
        self.session.mount("https://", HTTPAdapter(max_retries=retry))

    def close(self) -> None:
        self.session.close()

    TENTATIVAS_JSON = 4

    def _get(self, url: str):
        # Às vezes a API responde 200 com o corpo vazio ou cortado: isso não passa
        # pelo Retry acima (que só olha o status), então tenta de novo aqui
        for tentativa in range(1, self.TENTATIVAS_JSON + 1):
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            try:
                return response.json()
            except requests.exceptions.JSONDecodeError:
                if tentativa == self.TENTATIVAS_JSON:
                    raise
                print(f"Resposta inválida da API (tentativa {tentativa}); tentando de novo...")
                time.sleep(2 * tentativa)

    def ibge(self, serie_id: str) -> dict:
        """
        Busca, na API de agregados do IBGE, todos os períodos disponíveis de
        uma série do catálogo, para o Brasil (N1).

        Atributos:
            serie_id: chave da série em `catalogo.SERIES` com fonte "ibge"
        """
        url = montar_url(serie_id)
        return {"urls": [url], "resposta": self._get(url)}

    def bcb(self, serie_id: str) -> dict:
        """
        Busca uma série do SGS do Banco Central desde 1980, em janelas de 10
        anos, e junta as respostas numa única lista.

        Atributos:
            serie_id: chave da série em `catalogo.SERIES` com fonte "bcb"
        """
        urls, dados = [], []
        hoje = date.today()
        for ano in range(self.ANO_INICIAL_BCB, hoje.year + 1, self.ANOS_POR_CONSULTA_BCB):
            fim = min(ano + self.ANOS_POR_CONSULTA_BCB - 1, hoje.year)
            url = montar_url(serie_id, f"01/01/{ano}", f"31/12/{fim}")
            try:
                dados.extend(self._get(url))
            except requests.HTTPError as erro:
                # O SGS responde 404 quando a janela não tem nenhum dado (ex.: antes do início da série)
                if erro.response is None or erro.response.status_code != 404:
                    raise
            urls.append(url)
        return {"urls": urls, "resposta": dados}

    def extrair(self, serie_id: str) -> dict:
        """
        Extrai uma série do catálogo, qualquer que seja a fonte, e devolve o
        pacote bruto com a proveniência.
        """
        fonte = SERIES[serie_id]["fonte"]
        pacote = self.ibge(serie_id) if fonte == "ibge" else self.bcb(serie_id)
        pacote["serie_id"] = serie_id
        pacote["fonte"] = fonte
        pacote["data_extracao"] = datetime.now(timezone.utc).isoformat(timespec="seconds")

        print(f"Série '{serie_id}' extraída com sucesso ({fonte.upper()})!")
        return pacote
