import hashlib
import json
import math
import shutil
from datetime import datetime, timezone

import pandas as pd
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup, escape

import src.config as config
from src.analise import Analise
from src.catalogo import Catalogo
from src.presidentes import Mandatos
from src.textos import Textos


class Publicador:
    """
    Responsável por gerar o site estático (pasta site/) a partir da camada prata.

    Todos os números do site são calculados aqui, em Python, pela `Analise`.
    O JavaScript do site só lê os arquivos gerados e reage aos controles
    (defasagem, indicador, mandato); ele não refaz nenhuma conta, então o site
    nunca diverge da metodologia documentada.

    Saídas em site/:
        dados/meta.json            catálogo, mandatos, eventos, proveniência
        dados/series/<serie>.json  observações de cada série
        dados/resumo.json          resumo série × mandato, para cada defasagem
        dados/checar/<serie>.json  resumo detalhado, dados usados e trajetórias
        dados/*.csv                os mesmos dados para download
        dados/bronze/<serie>.json  resposta bruta mais recente de cada API
        páginas HTML (resumo, comparar, checagens, séries, metodologia, dados), sitemap e 404
    """

    DEFASAGENS = [0, 3, 6, 12]
    PASTA_WEB = config.RAIZ / "web"
    PASTA_SITE = config.RAIZ / "site"

    # Dado mais antigo aceito no último período de cada frequência antes de
    # avisar que a série pode estar desatualizada (as contas anuais saem com ~2 anos de atraso)
    ATRASO_MAXIMO_MESES = {"mensal": 6, "trimestral_movel": 6, "trimestral": 9, "anual": 36}

    def __init__(self, obs: pd.DataFrame, ext: pd.DataFrame):
        """
        Atributos:
            obs: tabela `observacoes` da camada prata
            ext: tabela `extracoes` da camada prata (proveniência de cada série)
        """
        self.obs = obs
        self.ext = ext
        self.analise = Analise(obs)

    def publicar(self) -> None:
        """Confere os dados e gera o site do zero: dados exportados e páginas."""
        self.validar()
        if self.PASTA_SITE.exists():
            shutil.rmtree(self.PASTA_SITE)
        contexto = self.exportar_dados()
        self.gerar_paginas(contexto)

    # ------------------------------------------------------------ validação
    def validar(self) -> list[str]:
        """
        Confere a camada prata antes de publicar. Devolve a lista de avisos
        (séries que podem estar desatualizadas) e levanta ValueError para
        problemas que impediriam o site de funcionar: série ausente, valor nulo
        ou período duplicado.
        """
        erros, avisos = [], []
        obs = self.obs
        hoje = pd.Timestamp.today()
        for sid, meta in Catalogo.SERIES.items():
            s = obs[obs["serie_id"] == sid]
            if s.empty:
                erros.append(f"{sid}: nenhuma observação")
                continue
            if s["valor"].isna().any():
                erros.append(f"{sid}: há valores nulos")
            if s["periodo"].duplicated().any():
                erros.append(f"{sid}: há períodos duplicados")
            atraso = (hoje - s["data_fim"].max()).days / 30.4
            if not meta.get("encerrada") and atraso > self.ATRASO_MAXIMO_MESES[meta["frequencia"]]:
                avisos.append(f"{sid}: último dado tem {atraso:.0f} meses — a série pode estar desatualizada")
        if erros:
            raise ValueError("A camada prata tem problemas:\n- " + "\n- ".join(erros))
        for aviso in avisos:
            print(f"Aviso: {aviso}")
        return avisos
    # ------------------------------------------------------------ utilidades
    @staticmethod
    def _limpo(v):
        """Converte valores do pandas para JSON: NaN -> null, datas -> 'AAAA-MM-DD'."""
        if isinstance(v, dict):
            return {k: Publicador._limpo(x) for k, x in v.items()}
        if isinstance(v, (list, tuple)):
            return [Publicador._limpo(x) for x in v]
        if isinstance(v, pd.Timestamp):
            return v.strftime("%Y-%m-%d")
        if isinstance(v, float) and math.isnan(v):
            return None
        if hasattr(v, "item"):  # escalares do numpy
            return Publicador._limpo(v.item())
        return v


    @staticmethod
    def _gravar_json(obj, caminho) -> None:
        caminho.parent.mkdir(parents=True, exist_ok=True)
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump(Publicador._limpo(obj), f, ensure_ascii=False, separators=(",", ":"))


    @staticmethod
    def _pontos(df: pd.DataFrame) -> list[dict]:
        meio = df["data_inicio"] + (df["data_fim"] + pd.Timedelta(days=1) - df["data_inicio"]) / 2
        return [
            {"p": r.periodo_rotulo, "i": r.data_inicio, "f": r.data_fim, "m": m.normalize(), "v": round(r.valor, 6)}
            for r, m in zip(df.itertuples(), meio)
        ]


    @staticmethod
    def _meta_serie(sid: str) -> dict:
        meta = Catalogo.SERIES[sid]
        metricas = Analise.METRICAS[meta["tipo"]]
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
            "metrica_mudanca": Analise.METRICA_MUDANCA[meta["tipo"]],
            "unidades_metrica": {k: Textos.unidade_metrica(sid, k) for k in metricas},
            "rotulos_unidade": {k: Textos.rotulo_unidade(sid, k) for k in metricas},
            "fonte": Catalogo.descricao_fonte(sid),
            "link_fonte": Catalogo.link_fonte(sid),
        }
    # ------------------------------------------------------------ dados
    def exportar_dados(self) -> dict:
        """Grava os JSON e CSV em site/dados e devolve o contexto usado nas páginas."""
        obs, ext, analise = self.obs, self.ext, self.analise
        pasta = self.PASTA_SITE / "dados"
        ordem = Catalogo.ordem()

        # Séries
        for sid in Catalogo.SERIES:
            s = obs[obs["serie_id"] == sid].sort_values("data_inicio")
            conteudo = {"pontos": self._pontos(s)}
            if sid == "ipca":
                conteudo["acumulado_12m"] = self._pontos(Analise.acumulado_12m(s))
            self._gravar_json(conteudo, pasta / "series" / f"{sid}.json")

        # Resumos por defasagem: página Resumo e Comparar (compacto) e checagem (detalhado)
        resumo, checar, tabelas = {}, {sid: {"lags": {}, "trajetorias": {}} for sid in ordem}, []
        for d in self.DEFASAGENS:
            resumos = {(sid, mid): analise.resumo(sid, mid, d) for sid in ordem for mid in Mandatos.ids()}

            linhas_tabela = []
            for (sid, mid), r in resumos.items():
                linha = {k: r[k] for k in ("serie_id", "mandato_id", "rotulo", "n", "esperado", "cobertura", "status")}
                linha.update(r["metricas"])
                linhas_tabela.append(linha)
            tabela = pd.DataFrame(linhas_tabela)
            tabelas.append(tabela.assign(defasagem_meses=d))

            resumo[str(d)] = []
            for (sid, mid), r in resumos.items():
                texto = {k: Textos.fmt_metrica(sid, k, v) + Textos.sufixo_anos(sid, k, r["n"])
                         for k, v in r["metricas"].items()}
                resumo[str(d)].append({
                    "s": sid, "m": mid, "status": r["status"], "n": r["n"], "esperado": r["esperado"],
                    "metricas": r["metricas"], "texto": texto,
                })

                usadas = r["linhas"].assign(papel="no mandato")
                # Nas séries de variação a herança não entra na conta, então não é listada
                if r["heranca"] is not None and Catalogo.SERIES[sid]["tipo"] == "nivel":
                    usadas = pd.concat([r["heranca"].to_frame().T.assign(papel="herança"), usadas], ignore_index=True)
                checar[sid]["lags"].setdefault(str(d), {})[mid] = {
                    "status": r["status"], "n": r["n"], "esperado": r["esperado"],
                    "metricas": r["metricas"], "texto": texto,
                    "frase": Textos.frase(r),
                    "explicacao": Textos.explicar(r),
                    "ranking": Textos.frase_ranking(tabela, sid, mid),
                    "linhas": [
                        {"papel": u["papel"], "p": u["periodo_rotulo"], "i": pd.Timestamp(u["data_inicio"]),
                         "f": pd.Timestamp(u["data_fim"]), "a": pd.Timestamp(u["data_atribuicao"]).normalize(),
                         "v": float(u["valor"])}
                        for _, u in usadas.iterrows()
                    ],
                }

            for sid in ordem:
                traj = analise.trajetorias(sid, d)
                checar[sid]["trajetorias"][str(d)] = (
                    [] if traj.empty else
                    [{"mandato": t.mandato, "x": t.meses, "y": round(t.valor, 6), "p": t.periodo_rotulo} for t in traj.itertuples()]
                )

        self._gravar_json(resumo, pasta / "resumo.json")
        for sid, conteudo in checar.items():
            self._gravar_json(conteudo, pasta / "checar" / f"{sid}.json")

        # Downloads em CSV (separador ; e vírgula decimal, que abrem direto no Excel em português)
        obs.to_csv(pasta / "observacoes.csv", index=False, sep=";", decimal=",", encoding="utf-8-sig")
        pd.concat(tabelas).to_csv(pasta / "resumo.csv", index=False, sep=";", decimal=",", encoding="utf-8-sig")

        # Resposta bruta mais recente de cada API, para conferência
        for e in ext.itertuples():
            destino = pasta / "bronze" / f"{e.serie_id}.json"
            destino.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(config.RAIZ / e.arquivo_bronze, destino)

        conf = analise.conferir_ipca_12m()
        extracoes = {e.serie_id: e._asdict() for e in ext.itertuples(index=False)}
        meta = {
            "gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "ultima_extracao": ext["data_extracao"].max(),
            "defasagens": self.DEFASAGENS,
            "grupos": Catalogo.GRUPOS,
            "ordem": ordem,
            "series": {sid: self._meta_serie(sid) for sid in Catalogo.SERIES},
            "mandatos": [{**m, "inicio": pd.Timestamp(m["inicio"]), "fim": pd.Timestamp(m["fim"])} for m in Mandatos.MANDATOS],
            "eventos": [{"data": pd.Timestamp(d), "nome": n} for d, n in Mandatos.EVENTOS],
            "extracoes": extracoes,
        }
        self._gravar_json(meta, pasta / "meta.json")

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
    # ------------------------------------------------------------ páginas
    @staticmethod
    def _negrito(texto: str) -> Markup:
        """Converte o **negrito** dos textos de `Textos` em <strong>, escapando o resto."""
        partes = str(escape(texto)).split("**")
        return Markup("".join(f"<strong>{p}</strong>" if i % 2 else p for i, p in enumerate(partes)))


    @staticmethod
    def _sem_marcacao(texto: str) -> str:
        return texto.replace("**", "")
    def gerar_paginas(self, contexto: dict) -> int:
        """Renderiza os templates de web/templates em site/ e copia web/static. Devolve o nº de páginas."""
        env = Environment(loader=FileSystemLoader(self.PASTA_WEB / "templates"), autoescape=select_autoescape(["html", "xml"]))
        env.filters["negrito"] = self._negrito
        env.filters["sem_marcacao"] = self._sem_marcacao
        env.filters["data_br"] = lambda d: pd.Timestamp(d).strftime("%d/%m/%Y")
        env.filters["num"] = lambda v, casas=3: Textos.fmt(v, casas)

        # CSS e JS vão para uma pasta com o hash do conteúdo: cada mudança gera um
        # endereço novo, então o navegador pode guardá-los em cache por muito tempo
        # sem nunca usar uma versão velha
        resumo = hashlib.sha256()
        for arquivo in sorted((self.PASTA_WEB / "static").rglob("*")):
            if arquivo.is_file():
                resumo.update(arquivo.relative_to(self.PASTA_WEB).as_posix().encode() + arquivo.read_bytes())
        versao = resumo.hexdigest()[:10]

        site_url = (config.SITE_URL or "").rstrip("/")
        comum = {
            "static": f"/static/{versao}",
            "meta": contexto["meta"],
            "series": Catalogo.SERIES,
            "ordem": contexto["ordem"],
            "mandatos": Mandatos.MANDATOS,
            "site_url": site_url,
            "repo_url": config.REPO_URL,
            "ultima_extracao": contexto["meta"]["ultima_extracao"][:10],
            "descricao_fonte": Catalogo.descricao_fonte,
            "link_fonte": Catalogo.link_fonte,
        }
        paginas = {
            "index.html": ("resumo.html", {"caminho": "/"}),
            "comparar/index.html": ("comparar.html", {"caminho": "/comparar/"}),
            "series/index.html": ("series.html", {"caminho": "/series/"}),
            "metodologia/index.html": ("metodologia.html", {"caminho": "/metodologia/", "conferencia": contexto["conferencia"],
                                                            "eventos": Mandatos.EVENTOS}),
            "dados/index.html": ("dados.html", {"caminho": "/dados/"}),
            "checar/index.html": ("checar_indice.html", {"caminho": "/checar/"}),
            "404.html": ("404.html", {"caminho": "/404.html"}),
        }
        for sid in contexto["ordem"]:
            for m in Mandatos.MANDATOS:
                r = contexto["checar"][sid]["lags"]["0"][m["id"]]
                paginas[f"checar/{m['id']}/{sid}/index.html"] = (
                    "checar.html", {"caminho": f"/checar/{m['id']}/{sid}/", "sid": sid, "mandato": m, "r": r},
                )

        shutil.copytree(self.PASTA_WEB / "static", self.PASTA_SITE / "static" / versao)

        for destino, (template, extra) in paginas.items():
            caminho = self.PASTA_SITE / destino
            caminho.parent.mkdir(parents=True, exist_ok=True)
            caminho.write_text(env.get_template(template).render(**comum, **extra), encoding="utf-8")

        # sitemap e robots só fazem sentido com o endereço público definido
        if site_url:
            urls = [extra["caminho"] for destino, (_, extra) in paginas.items() if destino != "404.html"]
            corpo = "\n".join(f"  <url><loc>{site_url}{u}</loc></url>" for u in urls)
            (self.PASTA_SITE / "sitemap.xml").write_text(
                f'<?xml version="1.0" encoding="UTF-8"?>\n'
                f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{corpo}\n</urlset>\n', encoding="utf-8")
            (self.PASTA_SITE / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {site_url}/sitemap.xml\n", encoding="utf-8")

        print(f"{len(paginas)} páginas geradas em 'site/'!")
        return len(paginas)
