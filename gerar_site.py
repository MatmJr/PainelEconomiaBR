import shutil

import pandas as pd
from sqlalchemy import create_engine

import src.config as config
from src.publicar import PASTA_SITE, exportar_dados, gerar_paginas, validar


def main():
    print("Etapa 1: Lendo a camada prata!")
    engine = create_engine(config.url_banco())
    obs = pd.read_sql("SELECT * FROM observacoes", engine, parse_dates=["data_inicio", "data_fim"])
    ext = pd.read_sql("SELECT * FROM extracoes", engine)
    engine.dispose()

    print("Etapa 2: Conferindo os dados antes de publicar!")
    validar(obs)

    print("Etapa 3: Gerando o site!")
    if PASTA_SITE.exists():
        shutil.rmtree(PASTA_SITE)  # o site é sempre gerado do zero
    contexto = exportar_dados(obs, ext)
    gerar_paginas(contexto)


if __name__ == "__main__":
    main()
