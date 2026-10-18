import pandas as pd
from sqlalchemy import create_engine

import src.config as config
from src.publicar import Publicador


def main():
    print("Etapa 1: Lendo a camada prata!")
    engine = create_engine(config.url_banco())
    obs = pd.read_sql("SELECT * FROM observacoes", engine, parse_dates=["data_inicio", "data_fim"])
    ext = pd.read_sql("SELECT * FROM extracoes", engine)
    engine.dispose()

    print("Etapa 2: Conferindo os dados e gerando o site do zero!")
    Publicador(obs, ext).publicar()


if __name__ == "__main__":
    main()
