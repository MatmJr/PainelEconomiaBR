"""
Testes dos cálculos que sustentam as afirmações do painel. Usam dados
sintéticos, sem acesso às APIs, para que cada regra fique explícita.
"""

import pandas as pd
import pytest

from src import analise, periodos


def obs(serie_id: str, frequencia: str, valores: dict[str, float]) -> pd.DataFrame:
    linhas = []
    for codigo, valor in valores.items():
        ini, fim = periodos.intervalo(codigo, frequencia)
        linhas.append({"serie_id": serie_id, "periodo": codigo, "periodo_rotulo": periodos.rotulo(ini, fim, frequencia),
                       "data_inicio": ini, "data_fim": fim, "valor": valor})
    return pd.DataFrame(linhas)


# ---------------------------------------------------------------- períodos
def test_intervalos():
    assert periodos.intervalo("202608", "mensal") == (pd.Timestamp(2026, 8, 1), pd.Timestamp(2026, 8, 31))
    assert periodos.intervalo("202608", "trimestral_movel") == (pd.Timestamp(2026, 6, 1), pd.Timestamp(2026, 8, 31))
    assert periodos.intervalo("201504", "trimestral") == (pd.Timestamp(2015, 10, 1), pd.Timestamp(2015, 12, 31))
    assert periodos.intervalo("2016", "anual") == (pd.Timestamp(2016, 1, 1), pd.Timestamp(2016, 12, 31))


def test_rotulos():
    assert periodos.rotulo(*periodos.intervalo("201901", "trimestral_movel"), "trimestral_movel") == "nov-dez-jan/2019"
    assert periodos.rotulo(*periodos.intervalo("201504", "trimestral"), "trimestral") == "4º tri/2015"


# ---------------------------------------------------------------- atribuição
def test_maio_2016_vai_para_temer():
    """Dilma governou 11 dias de maio/2016 e Temer 20: o mês é de Temer."""
    a = analise.atribuir(obs("x", "mensal", {"201604": 1, "201605": 1}))
    assert a["mandato"].tolist() == ["dilma2", "temer"]


def test_pib_2016_depende_da_defasagem():
    d = obs("x", "anual", {"2016": -3.3})
    assert analise.atribuir(d, 0)["mandato"].iloc[0] == "temer"
    assert analise.atribuir(d, 6)["mandato"].iloc[0] == "dilma2"


def test_janeiro_e_do_novo_governo_e_dezembro_do_anterior():
    a = analise.atribuir(obs("x", "mensal", {"201812": 1, "201901": 1}))
    assert a["mandato"].tolist() == ["temer", "bolsonaro"]


def test_antes_de_1985_sem_mandato():
    assert analise.atribuir(obs("x", "mensal", {"198001": 1}))["mandato"].iloc[0] is None


# ---------------------------------------------------------------- métricas
def test_variacao_em_pontos_usa_heranca(monkeypatch):
    monkeypatch.setitem(analise.SERIES, "teste", {"tipo": "nivel", "frequencia": "anual", "variacao_em": "pontos",
                                                  "unidade": "%", "nome": "Teste"})
    valores = {"2002": 10.0, "2003": 12.0, "2004": 11.0, "2005": 9.0, "2006": 8.0}
    r = analise.resumo(analise.atribuir(obs("teste", "anual", valores)), "teste", "lula1")
    assert r["metricas"]["heranca"] == 10.0
    assert r["metricas"]["final"] == 8.0
    assert r["metricas"]["variacao"] == pytest.approx(-2.0)
    assert r["metricas"]["media"] == pytest.approx(10.0)
    assert r["status"] == "completo"


def test_acumulado_e_composto_nao_somado(monkeypatch):
    monkeypatch.setitem(analise.SERIES, "teste", {"tipo": "variacao_anual", "frequencia": "anual",
                                                  "unidade": "% a.a.", "nome": "Teste"})
    valores = {"2003": 10.0, "2004": 10.0, "2005": 10.0, "2006": 10.0}
    r = analise.resumo(analise.atribuir(obs("teste", "anual", valores)), "teste", "lula1")
    assert r["metricas"]["acumulado"] == pytest.approx(46.41)  # 1,1^4 − 1, e não 40%
    assert r["metricas"]["media"] == pytest.approx(10.0)


def test_status_sem_valor_herdado_e_parcial(monkeypatch):
    monkeypatch.setitem(analise.SERIES, "teste", {"tipo": "nivel", "frequencia": "anual", "variacao_em": "pontos",
                                                  "unidade": "%", "nome": "Teste"})
    a = analise.atribuir(obs("teste", "anual", {"2004": 1.0, "2005": 1.0, "2006": 1.0}))
    assert analise.resumo(a, "teste", "lula1")["status"] == "sem valor herdado"
    assert analise.resumo(a, "teste", "lula2")["status"] == "sem dados"


def test_acumulado_12m():
    d = obs("ipca", "mensal", {f"2020{m:02d}": 1.0 for m in range(1, 13)})
    assert analise.acumulado_12m(d)["valor"].iloc[-1] == pytest.approx((1.01**12 - 1) * 100)


def test_fmt_brasileiro():
    assert analise.fmt(1234.5) == "1.234,5"
    assert analise.fmt(-3.84, sinal=True) == "-3,8"


def test_rotulo_unidade_deixa_claro_que_e_variacao():
    assert analise.rotulo_unidade("desocupacao", "variacao") == "variação p.p."
    assert analise.rotulo_unidade("rendimento_real", "variacao") == "variação %"
    assert analise.rotulo_unidade("rendimento_real", "media") == "R$ (preços do último trimestre)"


def test_media_nao_comparavel_fica_fora_do_ranking():
    tabela = pd.DataFrame([
        {"serie_id": "pib_trimestral", "mandato_id": m, "status": "completo", "variacao": v, "media": 100 + i}
        for i, (m, v) in enumerate([("lula1", 15.0), ("lula2", 19.0), ("dilma1", 8.0)])
    ])
    texto = analise.frase_ranking(tabela, "pib_trimestral", "lula2")
    assert "1º de 3" in texto and "média" not in texto


def test_trimestre_movel_e_atribuido_pelo_mes_final(monkeypatch):
    """out-nov-dez/2018 é herança de Bolsonaro; nov-dez-jan/2019 já é do mandato dele."""
    monkeypatch.setitem(analise.SERIES, "tm", {"tipo": "nivel", "frequencia": "trimestral_movel",
                                               "variacao_em": "pontos", "unidade": "%", "nome": "Teste"})
    a = analise.atribuir(obs("tm", "trimestral_movel", {"201812": 11.7, "201901": 12.2}))
    assert a["mandato"].tolist() == ["temer", "bolsonaro"]
    valores = {f"{ano}{m:02d}": 10.0 for ano in range(2018, 2024) for m in range(1, 13)}
    r = analise.resumo(analise.atribuir(obs("tm", "trimestral_movel", valores)), "tm", "bolsonaro")
    assert r["heranca"]["periodo_rotulo"] == "out-nov-dez/2018"
    assert r["linhas"]["periodo_rotulo"].iloc[-1] == "out-nov-dez/2022"
    assert r["n"] == r["esperado"] == 48


def test_sufixo_de_anos_so_em_series_anuais_com_menos_de_4_anos():
    assert analise.sufixo_anos("pib_anual", "media", 1) == " (1 ano)"
    assert analise.sufixo_anos("pib_anual", "acumulado", 3) == " (3 anos)"
    assert analise.sufixo_anos("pib_anual", "media", 4) == ""
    assert analise.sufixo_anos("desocupacao", "media", 1) == ""
    assert analise.sufixo_anos("resultado_primario", "media", 1) == " (1 ano)"
    assert analise.sufixo_anos("pib_per_capita", "media", 1) == ""
