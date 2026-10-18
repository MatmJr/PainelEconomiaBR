import argparse

from src.catalogo import Catalogo
from src.extract import Extract
from src.load import Load
from src.transform import Transform


def main(series: list[str] | None = None):
    """
    Roda o pipeline. Com `series`, só essas são buscadas de novo nas APIs; as
    demais são relidas da extração mais recente guardada na camada bronze (útil
    quando uma API está fora do ar ou bloqueando acessos).
    """
    ext = Extract()
    ld = Load()
    transformer = Transform()

    print("Etapa 1: Extração das APIs e carga na camada bronze!")
    pacotes, arquivos = {}, {}
    for serie_id in Catalogo.SERIES:
        if series and serie_id not in series:
            pacotes[serie_id], arquivos[serie_id] = ld.ultimo_bronze(serie_id)
            continue
        pacotes[serie_id] = ext.extrair(serie_id)
        arquivos[serie_id] = ld.load_bronze(pacotes[serie_id])
    ext.close()

    print("Etapa 2: Transformando os dados!")
    obs = transformer.transform_todas(pacotes)
    extracoes = ld.registro_extracoes(pacotes, arquivos, obs)

    print("Etapa 3: Salvando a camada prata!")
    ld.load_prata(obs, extracoes)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extrai as séries do IBGE e do BCB e grava as camadas bronze e prata.")
    parser.add_argument(
        "--series", nargs="+", choices=list(Catalogo.SERIES), metavar="SERIE",
        help="extrai só estas séries; as demais são relidas da última extração salva",
    )
    main(parser.parse_args().series)
