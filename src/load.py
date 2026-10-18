import json
from datetime import datetime

import pandas as pd
from sqlalchemy import create_engine

import src.config as config
from src.catalogo import SERIES, descricao_fonte, link_fonte
from src.presidentes import mandatos_df


class Load:
    """
    Responsável por persistir os dados do pipeline:

    - camada bronze: cada resposta bruta das APIs vira um arquivo JSON em
      data/bronze/<serie>/<data_extracao>.json. Nada é apagado, então dá
      para refazer qualquer conta a partir do que a API devolveu naquele dia;
    - camada prata: as observações já transformadas, o registro das extrações
      e a tabela de mandatos, num banco SQLite local e, se `DATABASE_URL`
      estiver no .env, também no Neon. Por ser derivada do bronze, é
      substituída a cada execução.
    """

    def load_bronze(self, pacote: dict) -> str:
        """
        Salva o pacote bruto de uma série (retorno de `Extract.extrair`) e
        devolve o caminho do arquivo, relativo à raiz do projeto.
        """
        pasta = config.PASTA_BRONZE / pacote["serie_id"]
        pasta.mkdir(parents=True, exist_ok=True)

        carimbo = datetime.fromisoformat(pacote["data_extracao"]).strftime("%Y%m%dT%H%M%SZ")
        caminho = pasta / f"{carimbo}.json"
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump(pacote, f, ensure_ascii=False)

        relativo = caminho.relative_to(config.RAIZ).as_posix()
        print(f"Bruto salvo em '{relativo}'!")
        return relativo

    @staticmethod
    def registro_extracoes(pacotes: dict[str, dict], arquivos: dict[str, str], obs: pd.DataFrame) -> pd.DataFrame:
        """Monta a tabela de proveniência: de onde e quando veio cada série, e o que ela cobre."""
        linhas = []
        for sid, pacote in pacotes.items():
            dados = obs[obs["serie_id"] == sid].sort_values("data_inicio")
            linhas.append(
                {
                    "serie_id": sid,
                    "nome": SERIES[sid]["nome"],
                    "fonte": descricao_fonte(sid),
                    "link_fonte": link_fonte(sid),
                    "urls": "\n".join(pacote["urls"]),
                    "data_extracao": pacote["data_extracao"],
                    "arquivo_bronze": arquivos[sid],
                    "n_periodos": len(dados),
                    "primeiro_periodo": dados["periodo_rotulo"].iloc[0] if len(dados) else None,
                    "ultimo_periodo": dados["periodo_rotulo"].iloc[-1] if len(dados) else None,
                }
            )
        return pd.DataFrame(linhas)

    def load_prata(self, obs: pd.DataFrame, extracoes: pd.DataFrame) -> None:
        """Grava as tabelas `observacoes`, `extracoes` e `mandatos` no SQLite e, se configurado, no Neon."""
        tabelas = {
            "observacoes": obs,
            "extracoes": extracoes,
            "mandatos": mandatos_df().drop(columns="ordem"),
        }

        destinos = {"SQLite": f"sqlite:///{config.CAMINHO_SQLITE.as_posix()}"}
        if config.DATABASE_URL:
            destinos["Neon"] = config.DATABASE_URL

        config.CAMINHO_SQLITE.parent.mkdir(parents=True, exist_ok=True)
        for nome, url in destinos.items():
            engine = create_engine(url)
            for tabela, df in tabelas.items():
                df.to_sql(tabela, engine, if_exists="replace", index=False)
            engine.dispose()
            print(f"Camada prata salva no {nome} ({', '.join(tabelas)})!")
