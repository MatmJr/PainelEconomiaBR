"""Testes da etapa de publicação do site (sem acesso às APIs)."""

import pandas as pd
import pytest

from src import publicar
from src.catalogo import SERIES


def test_negrito_escapa_html():
    assert str(publicar._negrito("**5%** <script>")) == "<strong>5%</strong> &lt;script&gt;"


def test_limpo_converte_nan_e_datas():
    assert publicar._limpo({"a": float("nan"), "b": pd.Timestamp(2020, 1, 31)}) == {"a": None, "b": "2020-01-31"}


def test_validar_recusa_serie_ausente():
    obs = pd.DataFrame(columns=["serie_id", "periodo", "data_inicio", "data_fim", "valor"])
    with pytest.raises(ValueError, match="nenhuma observação"):
        publicar.validar(obs)


def test_validar_aceita_dados_completos():
    hoje = pd.Timestamp.today().normalize()
    linhas = [{"serie_id": sid, "periodo": "1", "data_inicio": hoje, "data_fim": hoje, "valor": 1.0} for sid in SERIES]
    assert publicar.validar(pd.DataFrame(linhas)) == []


def test_primario_usa_so_dezembro():
    from src.transform import Transform
    resposta = [{"data": f"01/{m:02d}/{a}", "valor": str(m)} for a in (2021, 2022) for m in range(1, 13)]
    resposta += [{"data": "01/03/2023", "valor": "99"}]  # ano ainda aberto: não pode entrar
    df = Transform().transform_serie({"serie_id": "resultado_primario", "fonte": "bcb", "resposta": resposta})
    assert df["periodo"].tolist() == ["2021", "2022"]
    assert df["valor"].tolist() == [-12.0, -12.0]  # valor de dezembro, com o sinal invertido (fator −1)


def test_ultimo_bronze_recusa_extracao_com_outra_configuracao(tmp_path, monkeypatch):
    import json
    from src import config
    from src.load import Load
    monkeypatch.setattr(config, "PASTA_BRONZE", tmp_path / "bronze")
    monkeypatch.setattr(config, "RAIZ", tmp_path)
    pasta = tmp_path / "bronze" / "selic"
    pasta.mkdir(parents=True)
    antigo = {"serie_id": "selic", "fonte": "bcb", "urls": ["https://api.bcb.gov.br/dados/serie/bcdata.sgs.4189/dados?x"],
              "resposta": [], "data_extracao": "2026-01-01T00:00:00+00:00"}
    (pasta / "20260101T000000Z.json").write_text(json.dumps(antigo), encoding="utf-8")
    with pytest.raises(ValueError, match="outra configuração"):
        Load().ultimo_bronze("selic")
    atual = dict(antigo, urls=["https://api.bcb.gov.br/dados/serie/bcdata.sgs.432/dados?x"])
    (pasta / "20260201T000000Z.json").write_text(json.dumps(atual), encoding="utf-8")
    pacote, caminho = Load().ultimo_bronze("selic")
    assert caminho.endswith("20260201T000000Z.json")
