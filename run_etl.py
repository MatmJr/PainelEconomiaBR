from src.catalogo import SERIES
from src.extract import Extract
from src.load import Load
from src.transform import Transform


def main():
    ext = Extract()
    ld = Load()
    transformer = Transform()

    print("Etapa 1: Extração das APIs e carga na camada bronze!")
    pacotes, arquivos = {}, {}
    for serie_id in SERIES:
        pacotes[serie_id] = ext.extrair(serie_id)
        arquivos[serie_id] = ld.load_bronze(pacotes[serie_id])
    ext.close()

    print("Etapa 2: Transformando os dados!")
    obs = transformer.transform_todas(pacotes)
    extracoes = ld.registro_extracoes(pacotes, arquivos, obs)

    print("Etapa 3: Salvando a camada prata!")
    ld.load_prata(obs, extracoes)


if __name__ == "__main__":
    main()
