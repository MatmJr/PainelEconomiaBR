import pandas as pd
from prefect import flow, get_run_logger, task

from src.catalogo import Catalogo
from src.extract import Extract
from src.load import Load
from src.transform import Transform


@task(retries=3, retry_delay_seconds=10)
def extract(serie_id: str) -> dict:
    logger = get_run_logger()
    extractor = Extract()
    pacote = extractor.extrair(serie_id)
    extractor.close()
    logger.info(f"Série {serie_id}: {len(pacote['urls'])} consulta(s) à API")
    return pacote


@task
def load_bronze(pacote: dict) -> str:
    return Load().load_bronze(pacote)


@task
def transform(pacotes: dict[str, dict], arquivos: dict[str, str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    logger = get_run_logger()
    obs = Transform().transform_todas(pacotes)
    extracoes = Load.registro_extracoes(pacotes, arquivos, obs)
    logger.info(f"{len(obs)} observações transformadas em {obs['serie_id'].nunique()} séries")
    return obs, extracoes


@task(retries=3, retry_delay_seconds=10)
def load_prata(obs: pd.DataFrame, extracoes: pd.DataFrame):
    Load().load_prata(obs, extracoes)


@flow(name="ETL Painel Economia BR", log_prints=True)
def etl_economia_flow(series: list[str] | None = None):
    series = series or list(Catalogo.SERIES)

    # As extrações são independentes: o Prefect as executa em paralelo
    futuros = {sid: extract.submit(sid) for sid in series}
    pacotes = {sid: f.result() for sid, f in futuros.items()}
    arquivos = {sid: load_bronze(p) for sid, p in pacotes.items()}

    obs, extracoes = transform(pacotes, arquivos)
    load_prata(obs, extracoes)


if __name__ == "__main__":
    etl_economia_flow()
