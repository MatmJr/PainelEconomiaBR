import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

RAIZ = Path(__file__).resolve().parent.parent

# Camada bronze: respostas das APIs, exatamente como vieram, uma pasta por série
PASTA_BRONZE = RAIZ / "data" / "bronze"

# Camada prata: banco SQLite local, sempre gravado pelo pipeline
CAMINHO_SQLITE = RAIZ / "data" / "economia.db"

# Opcional: se definido no .env, o pipeline também grava a camada prata no
# Neon e o dashboard passa a ler de lá
DATABASE_URL = os.getenv("DATABASE_URL")

# Endereço público do site (ex.: https://economia-por-presidente.netlify.app) e
# do repositório. Opcionais: sem SITE_URL, o site é gerado sem sitemap e sem
# URLs absolutas nas prévias de compartilhamento.
SITE_URL = os.getenv("SITE_URL")
REPO_URL = os.getenv("REPO_URL")


def url_banco() -> str:
    """URL SQLAlchemy do banco lido pelo dashboard: Neon, se configurado; senão, SQLite local."""
    return DATABASE_URL or f"sqlite:///{CAMINHO_SQLITE.as_posix()}"
