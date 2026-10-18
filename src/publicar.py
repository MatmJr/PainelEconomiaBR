"""
Gera o site estático (pasta site/) a partir da camada prata.

Todos os números do site são calculados aqui, em Python, pelas mesmas
funções testadas de src/analise.py. O JavaScript do site só lê os arquivos
gerados e reage aos controles (defasagem, indicador, mandato); ele não refaz
nenhuma conta, então o site nunca diverge da metodologia documentada.

Saídas em site/:
    dados/meta.json            catálogo, mandatos, eventos, proveniência
    dados/series/<serie>.json  observações de cada série
    dados/resumo.json          resumo série × mandato, para cada defasagem
    dados/checar/<serie>.json  resumo detalhado, dados usados e trajetórias
    dados/*.csv                os mesmos dados para download
    dados/bronze/<serie>.json  resposta bruta mais recente de cada API
    páginas HTML (resumo, comparar, checagens, séries, metodologia, dados), sitemap e 404
"""

import hashlib
import json
import math
import shutil
from datetime import datetime, timezone

import pandas as pd
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup, escape

import src.config as config
from src import analise
from src.catalogo import GRUPOS, SERIES, descricao_fonte, link_fonte, series_placar
from src.presidentes import EVENTOS, MANDATOS

DEFASAGENS = [0, 3, 6, 12]
PASTA_WEB = config.RAIZ / "web"
PASTA_SITE = config.RAIZ / "site"

# Dado mais antigo aceito no último período de cada frequência antes de
# avisar que a série pode estar desatualizada (as contas anuais saem com ~2 anos de atraso)
ATRASO_MAXIMO_MESES = {"mensal": 6, "trimestral_movel": 6, "trimestral": 9, "anual": 36}


# ---------------------------------------------------------------- validação
def validar(obs: pd.DataFrame) -> list[str]:
    """
    Confere a camada prata antes de publicar. Devolve a lista de avisos
    (séries que podem estar desatualizadas) e levanta ValueError para
    problemas que impediriam o site de funcionar: série ausente, valor nulo
    ou período duplicado.
    """
    erros, avisos = [], []
    hoje = pd.Timestamp.today()
    for sid, meta in SERIES.items():
        s = obs[obs["serie_id"] == sid]
        if s.empty:
            erros.append(f"{sid}: nenhuma observação")
            continue
        if s["valor"].isna().any():
            erros.append(f"{sid}: há valores nulos")
        if s["periodo"].duplicated().any():
            erros.append(f"{sid}: há períodos duplicados")
        atraso = (hoje - s["data_fim"].max()).days / 30.4
        if not meta.get("encerrada") and atraso > ATRASO_MAXIMO_MESES[meta["frequencia"]]:
            avisos.append(f"{sid}: último dado tem {atraso:.0f} meses — a série pode estar desatualizada")
    if erros:
        raise ValueError("A camada prata tem problemas:\n- " + "\n- ".join(erros))
    for aviso in avisos:
        print(f"Aviso: {aviso}")
    return avisos


# ---------------------------------------------------------------- utilidades
def _limpo(v):
    """Converte valores do pandas para JSON: NaN -> null, datas -> 'AAAA-MM-DD'."""
    if isinstance(v, dict):
        return {k: _limpo(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_limpo(x) for x in v]
    if isinstance(v, pd.Timestamp):
        return v.strftime("%Y-%m-%d")
    if isinstance(v, float) and math.isnan(v):
        return None
    if hasattr(v, "item"):  # escalares do numpy
        return _limpo(v.item())
    return v


def _gravar_json(obj, caminho) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(_limpo(obj), f, ensure_ascii=False, separators=(",", ":"))


def _pontos(df: pd.DataFrame) -> list[dict]:
    meio = df["data_inicio"] + (df["data_fim"] + pd.Timedelta(days=1) - df["data_inicio"]) / 2
    return [
        {"p": r.periodo_rotulo, "i": r.data_inicio, "f": r.data_fim, "m": m.normalize(), "v": round(r.valor, 6)}
        for r, m in zip(df.itertuples(), meio)
    ]


def _meta_serie(sid: str) -> dict:
    meta = SERIES[sid]
    metricas = analise.METRICAS[meta["tipo"]]
    return {
        "nome": meta["nome"],
        "grupo": meta["grupo"],
        "unidade": meta["unidade"],
        "tipo": meta["tipo"],
        "frequencia": meta["frequencia"],
        "direcao": meta.get("direcao"),
        "auxiliar": bool(meta.get("auxiliar")),
        "encerrada": bool(meta.get("encerrada")),
        "media_comparavel": meta.get("media_comparavel", True),
        "motivo_media": meta.get("motivo_media"),
        "aviso_media": meta.get("aviso_media"),
        "ressalva_direcao": meta.get("ressalva_direcao"),
        "metricas": metricas,
        "metrica_mudanca": analise.METRICA_MUDANCA[meta["tipo"]],
        "unidades_metrica": {k: analise.unidade_metrica(sid, k) for k in metricas},
        "rotulos_unidade": {k: analise.rotulo_unidade(sid, k) for k in metricas},
        "fonte": descricao_fonte(sid),
        "link_fonte": link_fonte(sid),
    }


# ---------------------------------------------------------------- dados
def exportar_dados(obs: pd.DataFrame, ext: pd.DataFrame) -> dict:
    """Grava os JSON e CSV em site/dados e devolve o contexto usado nas páginas."""
    pasta = PASTA_SITE / "dados"
    placar_ids = list(series_placar())
    ordem = [sid for g in GRUPOS for sid in placar_ids if SERIES[sid]["grupo"] == g]

    # Séries
    for sid in SERIES:
        s = obs[obs["serie_id"] == sid].sort_values("data_inicio")
        conteudo = {"pontos": _pontos(s)}
        if sid == "ipca":
            conteudo["acumulado_12m"] = _pontos(analise.acumulado_12m(s))
        _gravar_json(conteudo, pasta / "series" / f"{sid}.json")

    # Resumos por defasagem: página Resumo e Comparar (compacto) e checagem (detalhado)
    placar, checar, tabelas = {}, {sid: {"lags": {}, "trajetorias": {}} for sid in ordem}, []
    for d in DEFASAGENS:
        at = analise.atribuir(obs, d)
        resumos = {(sid, m["id"]): analise.resumo(at, sid, m["id"], d) for sid in ordem for m in MANDATOS}

        linhas_tabela = []
        for (sid, mid), r in resumos.items():
            linha = {k: r[k] for k in ("serie_id", "mandato_id", "rotulo", "n", "esperado", "cobertura", "status")}
            linha.update(r["metricas"])
            linhas_tabela.append(linha)
        tabela = pd.DataFrame(linhas_tabela)
        tabelas.append(tabela.assign(defasagem_meses=d))

        placar[str(d)] = []
        for (sid, mid), r in resumos.items():
            texto = {k: analise.fmt_metrica(sid, k, v) + analise.sufixo_anos(sid, k, r["n"])
                     for k, v in r["metricas"].items()}
            placar[str(d)].append({
                "s": sid, "m": mid, "status": r["status"], "n": r["n"], "esperado": r["esperado"],
                "metricas": r["metricas"], "texto": texto,
            })

            usadas = r["linhas"].assign(papel="no mandato")
            # Nas séries de variação a herança não entra na conta, então não é listada
            if r["heranca"] is not None and SERIES[sid]["tipo"] == "nivel":
                usadas = pd.concat([r["heranca"].to_frame().T.assign(papel="herança"), usadas], ignore_index=True)
            checar[sid]["lags"].setdefault(str(d), {})[mid] = {
                "status": r["status"], "n": r["n"], "esperado": r["esperado"],
                "metricas": r["metricas"], "texto": texto,
                "frase": analise.frase(r),
                "explicacao": analise.explicar(r),
                "ranking": analise.frase_ranking(tabela, sid, mid),
                "linhas": [
                    {"papel": u["papel"], "p": u["periodo_rotulo"], "i": pd.Timestamp(u["data_inicio"]),
                     "f": pd.Timestamp(u["data_fim"]), "a": pd.Timestamp(u["data_atribuicao"]).normalize(),
                     "v": float(u["valor"])}
                    for _, u in usadas.iterrows()
                ],
            }

        for sid in ordem:
            traj = analise.trajetorias(at, sid)
            checar[sid]["trajetorias"][str(d)] = (
                [] if traj.empty else
                [{"mandato": t.mandato, "x": t.meses, "y": round(t.valor, 6), "p": t.periodo_rotulo} for t in traj.itertuples()]
            )

    _gravar_json(placar, pasta / "resumo.json")
    for sid, conteudo in checar.items():
        _gravar_json(conteudo, pasta / "checar" / f"{sid}.json")

    # Downloads em CSV (separador ; e vírgula decimal, que abrem direto no Excel em português)
    obs.to_csv(pasta / "observacoes.csv", index=False, sep=";", decimal=",", encoding="utf-8-sig")
    pd.concat(tabelas).to_csv(pasta / "resumo.csv", index=False, sep=";", decimal=",", encoding="utf-8-sig")

    # Resposta bruta mais recente de cada API, para conferência
    for e in ext.itertuples():
        destino = pasta / "bronze" / f"{e.serie_id}.json"
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(config.RAIZ / e.arquivo_bronze, destino)

    conf = analise.conferir_ipca_12m(obs)
    extracoes = {e.serie_id: e._asdict() for e in ext.itertuples(index=False)}
    meta = {
        "gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "ultima_extracao": ext["data_extracao"].max(),
        "defasagens": DEFASAGENS,
        "grupos": GRUPOS,
        "ordem": ordem,
        "series": {sid: _meta_serie(sid) for sid in SERIES},
        "mandatos": [{**m, "inicio": pd.Timestamp(m["inicio"]), "fim": pd.Timestamp(m["fim"])} for m in MANDATOS],
        "eventos": [{"data": pd.Timestamp(d), "nome": n} for d, n in EVENTOS],
        "extracoes": extracoes,
    }
    _gravar_json(meta, pasta / "meta.json")

    print(f"Dados do site exportados em '{pasta.relative_to(config.RAIZ).as_posix()}'!")
    return {
        "meta": meta,
        "ordem": ordem,
        "checar": checar,
        "conferencia": {
            "desde_1995": conf.loc[conf["periodo"] >= "199501", "diferenca"].abs().max(),
            "total": conf["diferenca"].abs().max(),
        },
    }


# ---------------------------------------------------------------- páginas
def _negrito(texto: str) -> Markup:
    """Converte o **negrito** dos textos de src/analise.py em <strong>, escapando o resto."""
    partes = str(escape(texto)).split("**")
    return Markup("".join(f"<strong>{p}</strong>" if i % 2 else p for i, p in enumerate(partes)))


def _sem_marcacao(texto: str) -> str:
    return texto.replace("**", "")


def gerar_paginas(contexto: dict) -> int:
    """Renderiza os templates de web/templates em site/ e copia web/static. Devolve o nº de páginas."""
    env = Environment(loader=FileSystemLoader(PASTA_WEB / "templates"), autoescape=select_autoescape(["html", "xml"]))
    env.filters["negrito"] = _negrito
    env.filters["sem_marcacao"] = _sem_marcacao
    env.filters["data_br"] = lambda d: pd.Timestamp(d).strftime("%d/%m/%Y")
    env.filters["num"] = lambda v, casas=3: analise.fmt(v, casas)

    # CSS e JS vão para uma pasta com o hash do conteúdo: cada mudança gera um
    # endereço novo, então o navegador pode guardá-los em cache por muito tempo
    # sem nunca usar uma versão velha
    resumo = hashlib.sha256()
    for arquivo in sorted((PASTA_WEB / "static").rglob("*")):
        if arquivo.is_file():
            resumo.update(arquivo.relative_to(PASTA_WEB).as_posix().encode() + arquivo.read_bytes())
    versao = resumo.hexdigest()[:10]

    site_url = (config.SITE_URL or "").rstrip("/")
    comum = {
        "static": f"/static/{versao}",
        "meta": contexto["meta"],
        "series": SERIES,
        "ordem": contexto["ordem"],
        "mandatos": MANDATOS,
        "site_url": site_url,
        "repo_url": config.REPO_URL,
        "ultima_extracao": contexto["meta"]["ultima_extracao"][:10],
        "descricao_fonte": descricao_fonte,
        "link_fonte": link_fonte,
    }
    paginas = {
        "index.html": ("resumo.html", {"caminho": "/"}),
        "comparar/index.html": ("comparar.html", {"caminho": "/comparar/"}),
        "series/index.html": ("series.html", {"caminho": "/series/"}),
        "metodologia/index.html": ("metodologia.html", {"caminho": "/metodologia/", "conferencia": contexto["conferencia"],
                                                        "eventos": EVENTOS}),
        "dados/index.html": ("dados.html", {"caminho": "/dados/"}),
        "checar/index.html": ("checar_indice.html", {"caminho": "/checar/"}),
        "404.html": ("404.html", {"caminho": "/404.html"}),
    }
    for sid in contexto["ordem"]:
        for m in MANDATOS:
            r = contexto["checar"][sid]["lags"]["0"][m["id"]]
            paginas[f"checar/{m['id']}/{sid}/index.html"] = (
                "checar.html", {"caminho": f"/checar/{m['id']}/{sid}/", "sid": sid, "mandato": m, "r": r},
            )

    shutil.copytree(PASTA_WEB / "static", PASTA_SITE / "static" / versao)

    for destino, (template, extra) in paginas.items():
        caminho = PASTA_SITE / destino
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_text(env.get_template(template).render(**comum, **extra), encoding="utf-8")

    # sitemap e robots só fazem sentido com o endereço público definido
    if site_url:
        urls = [extra["caminho"] for destino, (_, extra) in paginas.items() if destino != "404.html"]
        corpo = "\n".join(f"  <url><loc>{site_url}{u}</loc></url>" for u in urls)
        (PASTA_SITE / "sitemap.xml").write_text(
            f'<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{corpo}\n</urlset>\n', encoding="utf-8")
        (PASTA_SITE / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {site_url}/sitemap.xml\n", encoding="utf-8")

    print(f"{len(paginas)} páginas geradas em 'site/'!")
    return len(paginas)
