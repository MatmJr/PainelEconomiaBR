import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, inspect

import src.config as config
from dashboard import graficos
from src.analise import Analise
from src.catalogo import Catalogo
from src.presidentes import Mandatos
from src.textos import Textos

st.set_page_config(page_title="Economia por presidente", page_icon="📊", layout="wide")

DEFASAGENS = [0, 3, 6, 12]
STATUS_MARCA = {"completo": "", "mandato em curso": "*", "dados parciais": "*", "sem valor herdado": "†", "sem dados": ""}


# ------------------------------------------------------------------ dados
@st.cache_data(ttl=3600)
def carregar() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Lê a camada prata (SQLite local ou Neon). Fica em cache por 1 hora."""
    engine = create_engine(config.url_banco())
    if not inspect(engine).has_table("observacoes"):
        engine.dispose()
        return pd.DataFrame(), pd.DataFrame()
    obs = pd.read_sql("SELECT * FROM observacoes", engine, parse_dates=["data_inicio", "data_fim"])
    ext = pd.read_sql("SELECT * FROM extracoes", engine)
    engine.dispose()
    return obs, ext


@st.cache_resource(ttl=3600)
def analise() -> Analise:
    """Uma única `Analise` por sessão do servidor: ela guarda as atribuições já calculadas."""
    obs, _ = carregar()
    return Analise(obs)


@st.cache_data(ttl=3600)
def calcular_placar(defasagem: int) -> pd.DataFrame:
    return analise().tabela_resumos(Catalogo.ordem(), defasagem)


def nome_serie(sid: str) -> str:
    return f"{Catalogo.SERIES[sid]['grupo']} · {Catalogo.SERIES[sid]['nome']}"


def ordem_series() -> list[str]:
    return Catalogo.ordem()


def defasagem_atual() -> int:
    return st.session_state.get("defasagem", 0)


def aviso_defasagem() -> None:
    d = defasagem_atual()
    if d:
        st.info(f"Defasagem de **{d} meses** ativa: cada dado é atribuído a quem governava {d} meses antes.", icon="⏱️")


def cartao_metodologia(sid: str, ext: pd.DataFrame) -> None:
    """Bloco padrão com o que a série mede, de onde vem e como conferir."""
    meta = Catalogo.SERIES[sid]
    st.markdown(f"**O que mede.** {meta['o_que_mede']}")
    st.markdown(f"**Fonte e método.** {meta['metodologia']}")
    if meta["cuidados"]:
        st.markdown("**Cuidados ao interpretar:**\n" + "\n".join(f"- {c}" for c in meta["cuidados"]))
    linha = ext[ext["serie_id"] == sid]
    st.markdown(f"**Conferir na fonte:** [{Catalogo.descricao_fonte(sid)}]({Catalogo.link_fonte(sid)})")
    if not linha.empty:
        e = linha.iloc[0]
        st.caption(
            f"Extraído em {e['data_extracao']} · {e['n_periodos']} períodos "
            f"({e['primeiro_periodo']} a {e['ultimo_periodo']}) · bruto guardado em `{e['arquivo_bronze']}`"
        )
        with st.expander("URL(s) exata(s) consultada(s) na API"):
            st.code(e["urls"], language=None, wrap_lines=True)


# ------------------------------------------------------------------ páginas
def pagina_placar():
    st.title("Resumo por mandato")
    st.markdown(
        "Cada célula resume um indicador durante um mandato. Clique em **Checar uma afirmação** "
        "para ver o cálculo de qualquer número, com os dados usados e o link da fonte."
    )
    aviso_defasagem()

    modo = st.radio(
        "O que comparar",
        ["Média durante o mandato", "Mudança durante o mandato"],
        horizontal=True,
        help=(
            "Mudança: valor no fim − valor herdado (para inflação e PIB, o acumulado). "
            "Média: média dos valores do mandato (para inflação e PIB, a média anual composta)."
        ),
    )
    tabela = calcular_placar(defasagem_atual())

    def metrica_de(sid):
        return Analise.METRICA_MUDANCA[Catalogo.SERIES[sid]["tipo"]] if modo.startswith("Mudança") else "media"

    # Tabela compacta: mandatos nas linhas, indicadores nas colunas
    largura = {}
    for sid in ordem_series():
        m = metrica_de(sid)
        t = tabela[tabela["serie_id"] == sid].set_index("rotulo")
        largura[f"{Catalogo.SERIES[sid]['nome']} ({Textos.rotulo_unidade(sid, m)})"] = [
            Textos.fmt_metrica(sid, m, t.loc[r, m]) + Textos.sufixo_anos(sid, m, t.loc[r, "n"])
            + STATUS_MARCA[t.loc[r, "status"]]
            if m in t.columns else "—"
            for r in Mandatos.tabela()["rotulo"]
        ]
    placar_largo = pd.DataFrame(largura, index=pd.Index(Mandatos.tabela()["rotulo"], name="Mandato"))
    st.dataframe(placar_largo, width="stretch", height=460)
    st.caption(
        "\\* dados parciais ou mandato em curso · † sem valor herdado (a série começa depois da posse) · "
        "— sem dados. Os números não medem causa: descrevem o que aconteceu durante cada governo."
    )

    st.subheader("Por indicador")
    grupo = st.segmented_control("Grupo", Catalogo.GRUPOS, default=Catalogo.GRUPOS[0])
    sids = [s for s in ordem_series() if Catalogo.SERIES[s]["grupo"] == grupo]
    colunas = st.columns(2)
    for i, sid in enumerate(sids):
        m = metrica_de(sid)
        with colunas[i % 2]:
            st.markdown(f"**{Catalogo.SERIES[sid]['nome']}** — {Analise.METRICAS[Catalogo.SERIES[sid]['tipo']][m].lower()}")
            fig = graficos.barras_mandatos(tabela, sid, m, Textos.rotulo_unidade(sid, m))
            st.plotly_chart(fig, width="stretch", key=f"barra_{sid}")
            if Catalogo.SERIES[sid].get("direcao") is None:
                st.caption("Série de contexto, sem critério de destaque.")


def pagina_series():
    st.title("Séries históricas")
    obs, ext = carregar()
    aviso_defasagem()

    c1, c2 = st.columns([2, 1])
    sid = c1.selectbox("Indicador", ordem_series(), format_func=nome_serie)
    meta = Catalogo.SERIES[sid]
    df = obs[obs["serie_id"] == sid].sort_values("data_inicio").copy()

    titulo_y = meta["unidade"]
    if sid == "ipca":
        forma = c2.radio("Mostrar", ["Acumulado em 12 meses", "Variação mensal"], horizontal=True)
        if forma.startswith("Acumulado"):
            df = Analise.acumulado_12m(df)
            titulo_y = "% em 12 meses"

    ano_min, ano_max = int(df["data_inicio"].dt.year.min()), int(df["data_fim"].dt.year.max())
    padrao_ini = max(ano_min, 1995) if sid == "ipca" else ano_min
    anos = st.slider("Período", ano_min, ano_max, (padrao_ini, ano_max))
    df = df[df["data_inicio"].dt.year.between(*anos)]
    df["data_meio"] = df["data_inicio"] + (df["data_fim"] + pd.Timedelta(days=1) - df["data_inicio"]) / 2

    o1, o2 = st.columns(2)
    eventos = o1.toggle("Mostrar eventos de contexto", value=True)
    log = o2.toggle("Escala logarítmica", value=False, disabled=bool((df["valor"] <= 0).any()),
                    help="Útil para o IPCA antes do Plano Real. Indisponível quando há valores ≤ 0.")

    st.plotly_chart(graficos.serie_historica(df, sid, titulo_y, eventos, log), width="stretch")
    st.caption("Faixas cinza alternadas: mandatos. Triângulos: eventos de contexto (passe o mouse).")

    with st.container(border=True):
        cartao_metodologia(sid, ext)

    st.download_button(
        "Baixar esta série (CSV)",
        df[["periodo", "periodo_rotulo", "data_inicio", "data_fim", "valor"]].to_csv(index=False, sep=";", decimal=","),
        file_name=f"{sid}.csv",
        mime="text/csv",
    )


def pagina_checar():
    st.title("Checar uma afirmação")
    st.markdown(
        "Escolha um mandato e um indicador. O painel mostra o resultado, compara com os outros "
        "governos, explica a conta passo a passo e lista os dados usados, com o link da fonte."
    )
    ext = carregar()[1]
    defasagem = defasagem_atual()
    aviso_defasagem()

    ids = [m["id"] for m in Mandatos.MANDATOS]
    rotulos = {m["id"]: m["rotulo"] for m in Mandatos.MANDATOS}
    qp = st.query_params
    c1, c2 = st.columns(2)
    mid = c1.selectbox("Mandato", ids, format_func=rotulos.get,
                       index=ids.index(qp["mandato"]) if qp.get("mandato") in ids else ids.index("bolsonaro"))
    opcoes = ordem_series()
    sid = c2.selectbox("Indicador", opcoes, format_func=nome_serie,
                       index=opcoes.index(qp["serie"]) if qp.get("serie") in opcoes else opcoes.index("desocupacao"))
    st.query_params.update({"mandato": mid, "serie": sid})

    meta = Catalogo.SERIES[sid]
    m = next(x for x in Mandatos.MANDATOS if x["id"] == mid)
    r = analise().resumo(sid, mid, defasagem)

    st.caption(f"{m['presidente']} · {m['inicio']:%d/%m/%Y} a {m['fim']:%d/%m/%Y}" + (f" · {m['nota']}" if m["nota"] else ""))
    st.markdown(Textos.frase(r))

    if r["status"] == "sem dados":
        st.warning("Esta série não cobre este mandato. Veja na página **Metodologia** o período de cada série.")
        with st.container(border=True):
            cartao_metodologia(sid, ext)
        return
    if r["status"] != "completo":
        st.warning(f"Status dos dados: **{r['status']}** ({r['n']} de {r['esperado']} períodos). Compare com cautela.", icon="⚠️")

    # Indicadores principais
    mt = r["metricas"]
    chaves = ["heranca", "final", "variacao", "media"] if meta["tipo"] == "nivel" else ["acumulado", "media"]
    for col, k in zip(st.columns(len(chaves)), chaves):
        col.metric(Analise.METRICAS[meta["tipo"]][k], Textos.fmt_metrica(sid, k, mt.get(k)))

    # Posição entre os mandatos com dados completos
    tabela = calcular_placar(defasagem)
    texto_ranking = Textos.frase_ranking(tabela, sid, mid)
    if texto_ranking:
        st.markdown(texto_ranking)

    # Como foi calculado
    with st.expander("Como este número foi calculado", expanded=True):
        for linha in Textos.explicar(r):
            st.markdown(f"- {linha}")
        st.markdown(
            f"- **Regra de atribuição:** cada período conta para quem governou a maior parte dele "
            f"(ponto médio do período{f' menos {defasagem} meses de defasagem' if defasagem else ''}). "
            "Detalhes na página **Metodologia**."
        )

    # A conclusão depende da defasagem?
    k = Analise.METRICA_MUDANCA[meta["tipo"]]
    robustez = []
    for d in DEFASAGENS:
        rd = analise().resumo(sid, mid, d)
        robustez.append({
            "Defasagem": f"{d} meses",
            Analise.METRICAS[meta["tipo"]][k]: Textos.fmt_metrica(sid, k, rd["metricas"].get(k)),
            Analise.METRICAS[meta["tipo"]]["media"]: Textos.fmt_metrica(sid, "media", rd["metricas"].get("media")),
            "Períodos": f"{rd['n']} de {rd['esperado']}",
            "Status": rd["status"],
        })
    st.subheader("A conclusão muda com a defasagem?")
    st.caption("Medidas de governo levam tempo para fazer efeito. Se o resultado muda muito com a defasagem, a afirmação é frágil.")
    st.dataframe(pd.DataFrame(robustez), hide_index=True, width="stretch")

    # Comparação com os outros mandatos
    st.subheader("Comparação com os outros governos, a partir da posse")
    traj = analise().trajetorias(sid, defasagem)
    if not traj.empty and m["rotulo"] in traj["mandato"].values:
        pos = ids.index(mid)
        anterior = rotulos[ids[pos - 1]] if pos > 0 else None
        un = "p.p. em relação à herança" if meta.get("variacao_em") == "pontos" else "% em relação à herança"
        titulo_y = un if meta["tipo"] == "nivel" else "% acumulado desde a posse"
        st.plotly_chart(graficos.trajetorias(traj, m["rotulo"], anterior, titulo_y), width="stretch")
        st.caption(f"Azul: {m['rotulo']}. Laranja: mandato anterior. Cinza: demais. Todos começam em 0 na posse.")
    else:
        st.caption("Sem valor herdado para alinhar as trajetórias deste mandato.")

    # Série com o mandato em destaque
    obs = carregar()[0]
    df = obs[obs["serie_id"] == sid].sort_values("data_inicio").copy()
    df["data_meio"] = df["data_inicio"] + (df["data_fim"] + pd.Timedelta(days=1) - df["data_inicio"]) / 2
    if sid == "ipca":
        df = Analise.acumulado_12m(df)
        df["data_meio"] = df["data_inicio"] + (df["data_fim"] + pd.Timedelta(days=1) - df["data_inicio"]) / 2
        df = df[df["data_inicio"] >= "1995-01-01"]
    st.plotly_chart(graficos.serie_historica(df, sid, "% em 12 meses" if sid == "ipca" else meta["unidade"],
                                             eventos=True, destaque=mid), width="stretch")

    # Dados usados
    st.subheader("Dados usados no cálculo")
    linhas = r["linhas"].assign(papel="no mandato")
    if r["heranca"] is not None:
        heranca = r["heranca"].to_frame().T.assign(papel="herança")
        linhas = pd.concat([heranca, linhas], ignore_index=True)
    for col in ("data_inicio", "data_fim", "data_atribuicao"):
        linhas[col] = pd.to_datetime(linhas[col])
    linhas["valor"] = linhas["valor"].astype(float)
    mostrar = linhas[["papel", "periodo_rotulo", "data_inicio", "data_fim", "data_atribuicao", "valor"]].rename(columns={
        "papel": "Papel", "periodo_rotulo": "Período", "data_inicio": "Início", "data_fim": "Fim",
        "data_atribuicao": "Data usada na atribuição", "valor": f"Valor ({meta['unidade']})",
    })
    st.dataframe(mostrar, hide_index=True, width="stretch", column_config={
        "Início": st.column_config.DateColumn(format="DD/MM/YYYY"),
        "Fim": st.column_config.DateColumn(format="DD/MM/YYYY"),
        "Data usada na atribuição": st.column_config.DateColumn(format="DD/MM/YYYY"),
        f"Valor ({meta['unidade']})": st.column_config.NumberColumn(format="localized"),
    })
    st.download_button("Baixar estes dados (CSV)", mostrar.to_csv(index=False, sep=";", decimal=","),
                       file_name=f"{sid}_{mid}.csv", mime="text/csv")

    with st.container(border=True):
        st.markdown("#### Fonte e metodologia da série")
        cartao_metodologia(sid, ext)


def pagina_metodologia():
    st.title("Metodologia")
    obs, ext = carregar()

    st.header("1. Que governo recebe cada dado")
    st.markdown(
        "Cada dado cobre um intervalo: um mês, um trimestre, um trimestre móvel (média de três meses) "
        "ou um ano. Ele é atribuído ao governo que estava no cargo no **ponto médio** do intervalo — "
        "ou seja, ao governo que governou **a maior parte** do período."
    )
    st.latex(r"\text{mandato}(p) = M \iff t_{\text{médio}}(p) - d \in [\text{posse}_M,\ \text{saída}_M]")
    st.markdown(
        "onde *d* é a **defasagem** escolhida na barra lateral (0, 3, 6 ou 12 meses). Exemplos com "
        "defasagem zero:\n"
        "- **maio/2016**: Dilma foi afastada em 12/05; o ponto médio (16/05) cai com Temer, que governou 20 dos 31 dias;\n"
        "- **PIB de 2016**: ponto médio em 02/07/2016 → Temer. Com defasagem de 6 meses → Dilma;\n"
        "- **trimestres móveis** (PNAD Contínua) são a exceção: contam pelo mês final, como o IBGE os identifica. "
        "out-nov-dez/2018 é de Temer (herança de Bolsonaro) e nov-dez-jan/2019 já é de Bolsonaro.\n\n"
        "Por que oferecer defasagem? Juros, programas e reformas levam meses para afetar a economia. "
        "Não existe um valor 'certo': a recomendação é verificar se a conclusão se mantém com várias defasagens "
        "(a página **Checar uma afirmação** mostra isso automaticamente)."
    )

    st.header("2. Como cada indicador é resumido")
    st.markdown("**Séries de nível** (desocupação, informalidade, dívida/PIB, Selic, dólar, rendimento, salário mínimo):")
    st.latex(r"\text{herança} = x \text{ do último período atribuído antes da posse}")
    st.latex(r"\Delta = x_{\text{fim}} - x_{\text{herança}} \quad\text{(p.p.)} \qquad\text{ou}\qquad "
             r"\Delta\% = \left(\frac{x_{\text{fim}}}{x_{\text{herança}}} - 1\right)\times 100")
    st.latex(r"\bar{x} = \frac{1}{n}\sum_{i=1}^{n} x_i")
    st.markdown(
        "Comparar o fim com a herança mostra **o que mudou durante o governo**; a média mostra **como foi viver** "
        "naquele período. As duas respostas podem divergir: um governo que herda desemprego alto e o reduz pode ter "
        "média alta e variação muito boa."
    )
    st.markdown("**Séries de variação** (IPCA mensal, PIB anual): os percentuais são compostos, não somados.")
    st.latex(r"A = \prod_{i=1}^{n}\left(1 + \frac{v_i}{100}\right) - 1 \qquad\qquad "
             r"\text{média anual} = (1 + A)^{k/n} - 1")
    st.markdown("onde *k* é o número de períodos por ano (12 para mensal, 1 para anual).")

    st.subheader("Conferência da conta de acumulação")
    conf = analise().conferir_ipca_12m()
    if not conf.empty:
        recente = conf[conf["periodo"] >= "199501"]
        c1, c2 = st.columns(2)
        c1.metric("Maior diferença desde 1995", f"{Textos.fmt(recente['diferenca'].abs().max(), 3)} p.p.")
        c2.metric("Maior diferença na série toda", f"{Textos.fmt(conf['diferenca'].abs().max(), 3)} p.p.")
        st.caption(
            "O IPCA em 12 meses calculado pelo painel a partir das variações mensais, comparado com o publicado "
            "pelo IBGE (tabela 1737, variável 2265). As diferenças vêm do arredondamento das variações mensais "
            "a duas casas decimais, e são maiores na hiperinflação."
        )
        with st.expander("Ver a comparação mês a mês"):
            st.dataframe(conf, hide_index=True, width="stretch")

    st.header("3. Status dos dados")
    st.markdown(
        "- **completo**: a série cobre todos os períodos do mandato e existe valor herdado;\n"
        "- **mandato em curso**: o governo ainda não terminou — os números são parciais;\n"
        "- **dados parciais**: a série começou ou terminou no meio do mandato (ex.: PME encerrada em 2016);\n"
        "- **sem valor herdado**: a série começa depois da posse, então não há com o que comparar o fim;\n"
        "- **sem dados**: a série não cobre o mandato.\n\n"
        "Os rankings só incluem mandatos com status **completo**."
    )

    st.header("4. Erros comuns ao comparar governos")
    st.markdown(
        "1. **Escolher a dedo o ponto de partida.** Comparar o mês mais desfavorável de um governo com o mais favorável de outro. "
        "O painel usa sempre a herança e o último dado do mandato, e mostra a média.\n"
        "2. **Confundir nível com variação.** \"O desemprego era alto no governo X\" pode ser herança do governo anterior.\n"
        "3. **Ignorar choques externos.** Crise de 2008, pandemia, guerra, preço de commodities. Veja os eventos de contexto.\n"
        "4. **Ignorar defasagens.** Use o seletor de defasagem e veja se a conclusão se mantém.\n"
        "5. **Emendar séries com metodologias diferentes.** A PME (até 2016) e a PNAD Contínua (desde 2012) não são comparáveis em nível.\n"
        "6. **Comparar valores nominais.** Dólar e salário de décadas diferentes só se comparam descontada a inflação.\n"
        "7. **Comparar mandato incompleto com completo.** Veja o status de cada número.\n"
        "8. **Confundir correlação com causa.** O painel descreve o que aconteceu durante cada governo; não mede o efeito "
        "de cada política. Congresso, Banco Central (autônomo desde 2021), estados e a economia mundial também influenciam."
    )

    st.header("5. Mandatos")
    md = Mandatos.tabela()[["rotulo", "presidente", "inicio", "fim", "nota"]].rename(columns={
        "rotulo": "Mandato", "presidente": "Presidente", "inicio": "Início", "fim": "Fim", "nota": "Observação"})
    st.dataframe(md, hide_index=True, width="stretch", column_config={
        "Início": st.column_config.DateColumn(format="DD/MM/YYYY"),
        "Fim": st.column_config.DateColumn(format="DD/MM/YYYY")})
    st.caption("Nos impeachments, o vice é considerado no cargo desde o afastamento do titular, quando passa a exercer a Presidência.")

    st.header("6. Eventos de contexto")
    st.dataframe(pd.DataFrame(Mandatos.EVENTOS, columns=["Data", "Evento"]), hide_index=True, width="stretch",
                 column_config={"Data": st.column_config.DateColumn(format="DD/MM/YYYY")})

    st.header("7. Séries")
    for sid in ordem_series() + [s for s in Catalogo.SERIES if Catalogo.SERIES[s].get("auxiliar")]:
        with st.expander(nome_serie(sid) + (" (auxiliar)" if Catalogo.SERIES[sid].get("auxiliar") else "")):
            meta = Catalogo.SERIES[sid]
            st.markdown(
                f"Unidade: **{meta['unidade']}** · Frequência: **{meta['frequencia'].replace('_', ' ')}** · "
                f"Resumo por mandato: **{meta['tipo'].replace('_', ' ')}** · "
                f"Critério de destaque: **{ {'menor': 'menor valor', 'maior': 'maior valor'}.get(meta.get('direcao'), 'nenhum (série de contexto)') }**"
            )
            cartao_metodologia(sid, ext)

    st.header("8. Como reproduzir")
    st.markdown(
        "Todo o código é aberto. Para refazer os números do zero:\n"
        "```bash\npip install -r requirements.txt\npython run_etl.py\npython -m streamlit run dashboard/app.py\n```\n"
        "As respostas brutas das APIs ficam em `data/bronze/<série>/<data>.json` e as tabelas tratadas em "
        "`data/economia.db` (SQLite). Os cálculos por mandato estão na classe `Analise` (`src/analise.py`) e têm testes em `tests/`."
    )


def pagina_dados():
    st.title("Dados e fontes")
    obs, ext = carregar()
    st.markdown("Registro da última extração de cada série: de onde veio, quando, e o que ela cobre.")
    st.dataframe(
        ext[["nome", "fonte", "link_fonte", "data_extracao", "n_periodos", "primeiro_periodo", "ultimo_periodo", "arquivo_bronze"]],
        hide_index=True, width="stretch",
        column_config={
            "nome": "Série", "fonte": "Fonte",
            "link_fonte": st.column_config.LinkColumn("Conferir", display_text="abrir fonte"),
            "data_extracao": "Extraído em", "n_periodos": "Períodos",
            "primeiro_periodo": "Primeiro", "ultimo_periodo": "Último", "arquivo_bronze": "Arquivo bruto",
        },
    )
    st.download_button(
        "Baixar todas as observações (CSV)",
        obs.to_csv(index=False, sep=";", decimal=","), file_name="observacoes.csv", mime="text/csv",
    )
    tabela = calcular_placar(defasagem_atual())
    st.download_button(
        f"Baixar o resumo completo (CSV, defasagem {defasagem_atual()} meses)",
        tabela.to_csv(index=False, sep=";", decimal=","), file_name="resumo.csv", mime="text/csv",
    )


# ------------------------------------------------------------------ navegação
obs, ext = carregar()
if obs.empty:
    st.error("Ainda não há dados. Rode o pipeline a partir da raiz do projeto: `python run_etl.py`")
    st.stop()

with st.sidebar:
    st.selectbox(
        "Defasagem na atribuição", DEFASAGENS, key="defasagem",
        format_func=lambda d: "Nenhuma" if d == 0 else f"{d} meses",
        help="Atribui cada dado a quem governava N meses antes. Serve para testar se uma conclusão "
             "depende de quanto tempo as políticas levam para fazer efeito.",
    )
    st.caption(f"Última extração: {ext['data_extracao'].max()[:10]}")
    st.caption("Fontes: IBGE (SIDRA) e Banco Central (SGS).")
    st.caption("Desenvolvido por [Marco Mialaret Júnior](https://github.com/MatmJr) com [Claude Code](https://claude.com/claude-code).")

pg = st.navigation([
    st.Page(pagina_placar, title="Resumo por mandato", icon="📋", default=True),
    st.Page(pagina_checar, title="Checar uma afirmação", icon="🔎", url_path="checar"),
    st.Page(pagina_series, title="Séries históricas", icon="📈", url_path="series"),
    st.Page(pagina_metodologia, title="Metodologia", icon="📐", url_path="metodologia"),
    st.Page(pagina_dados, title="Dados e fontes", icon="🗂️", url_path="dados"),
])
pg.run()
