class Catalogo:
    """
    Catálogo das séries do painel: fonte única de metadados.

    Cada série descreve de onde vem (API, tabela, variável), como é lida e o que
    ela mede. O mesmo catálogo é usado pelo pipeline (para saber o que extrair) e
    pelo site (para exibir a metodologia e os links de checagem), então o texto
    que aparece na tela é sempre o da configuração realmente usada.

    Campos principais de cada série em `SERIES`:
        fonte: "ibge" (API de agregados/SIDRA) ou "bcb" (SGS do Banco Central)
        frequencia: "mensal", "trimestral_movel", "trimestral" ou "anual"
        tipo: define como a série é resumida por mandato (ver `Analise`)
            "nivel"            -> taxa ou valor observado em cada período (desocupação, dívida/PIB...)
            "variacao_mensal"  -> variação % no mês, acumulada por produto (IPCA)
            "variacao_anual"   -> variação % no ano, acumulada por produto (PIB)
        direcao: "menor" ou "maior": qual valor recebe destaque nas comparações;
            None quando a série é só contexto
        a_partir_de: descarta períodos anteriores (ex.: valores em moedas antigas)
        fator: multiplica os valores (ex.: -1 para inverter o sinal do primário)
        auxiliar: True para séries usadas só em cálculos/checagens, fora do resumo
        encerrada: True para pesquisas descontinuadas (não é cobrado dado recente)
        aviso_anos: False para não mostrar "(N anos)" nas médias de mandatos curtos
            (padrão: mostrar nas séries anuais)
        so_dezembro: True para séries mensais acumuladas em 12 meses lidas como anuais:
            só o valor de dezembro entra (o resultado do ano fechado)
        media_comparavel: False quando a média do mandato não serve para comparar
            governos (ex.: um índice de volume que cresce com o tempo: o mandato mais
            recente teria sempre a maior média). Fica fora de rankings e do destaque
        motivo_media: frase curta explicando por que a média não é comparável
        aviso_media: quando a média é comparada, mas pede cautela, o aviso que
            aparece junto, sugerindo olhar também a mudança no mandato
        ressalva_direcao: quando a leitura depende do ponto de vista, a ressalva que
            aparece ao lado do critério, para o leitor julgar
    """

    URL_IBGE = "https://servicodados.ibge.gov.br/api/v3/agregados"
    URL_BCB = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados"
    LINK_SGS = "https://www3.bcb.gov.br/sgspub/consultarvalores/telaCvsSelecionarSeries.paint"

    GRUPOS = ["Atividade", "Mercado de trabalho", "Preços", "Renda", "Fiscal", "Juros e câmbio"]

    SERIES = {
        # ------------------------------------------------------------------ Atividade
        "pib_anual": {
            "nome": "PIB – crescimento real anual",
            "grupo": "Atividade",
            "fonte": "bcb",
            "codigo": 7326,
            "frequencia": "anual",
            "tipo": "variacao_anual",
            "unidade": "% a.a.",
            "direcao": "maior",
            "o_que_mede": (
                "Variação real (descontada a inflação) do Produto Interno Bruto de um ano em "
                "relação ao ano anterior."
            ),
            "metodologia": (
                "Dado produzido pelo IBGE (Sistema de Contas Nacionais) e republicado pelo Banco "
                "Central na série SGS 7326, que tem a vantagem de cobrir desde 1962 em uma única "
                "série. A partir de 1996 coincide com a 'taxa acumulada em quatro trimestres' do "
                "4º trimestre da tabela SIDRA 5932."
            ),
            "cuidados": [
                "Os últimos anos são preliminares e costumam ser revisados pelo IBGE.",
                "Um ano inteiro é atribuído a um único governo (ver regra de atribuição): em anos de "
                "troca no meio do ano (1992, 2016) o resultado muda conforme a defasagem escolhida.",
            ],
            "link_checagem": "https://www3.bcb.gov.br/sgspub/consultarvalores/telaCvsSelecionarSeries.paint",
        },
        "pib_per_capita": {
            "nome": "PIB per capita – crescimento real anual",
            "grupo": "Atividade",
            "fonte": "ibge",
            "tabela": 6601,
            "variavel": 9347,
            "frequencia": "anual",
            "aviso_anos": False,
            "tipo": "variacao_anual",
            "unidade": "% a.a.",
            "direcao": "maior",
            "o_que_mede": (
                "Variação real do PIB dividido pela população. Desconta o crescimento populacional, "
                "por isso é mais adequado que o PIB total para comparar o ganho médio por pessoa."
            ),
            "metodologia": (
                "Tabela SIDRA 6601 (indicador 8.1.1 dos Objetivos de Desenvolvimento Sustentável: "
                "taxa de crescimento real do PIB per capita), variável 9347, Brasil, de 2000 em diante. "
                "Foi escolhida no lugar da tabela 6784 (Contas Nacionais anuais) porque já traz os anos "
                "mais recentes, enquanto as contas anuais definitivas saem com cerca de dois anos de "
                "atraso. Nos anos em comum, as duas tabelas diferem no máximo 0,1 ponto (arredondamento)."
            ),
            "cuidados": [
                "Valores com uma casa decimal; os anos mais recentes são preliminares e podem ser "
                "revisados pelo IBGE.",
                "Começa em 2000: FHC 1 (1995-1998) não tem esta série; FHC 2 tem 2000 a 2002.",
            ],
        },
        "pib_trimestral": {
            "nome": "PIB trimestral (índice dessazonalizado)",
            "grupo": "Atividade",
            "fonte": "ibge",
            "tabela": 1621,
            "variavel": 584,
            "classificacao": "11255[90707]",
            "frequencia": "trimestral",
            "tipo": "nivel",
            "unidade": "índice (média 1995 = 100)",
            "variacao_em": "percentual",
            "direcao": "maior",
            "media_comparavel": False,
            "motivo_media": "o índice cresce com o tempo",
            "o_que_mede": (
                "Volume do PIB a preços de mercado em cada trimestre, com ajuste sazonal. Como é um "
                "índice de volume, a variação entre dois trimestres mostra o crescimento real acumulado."
            ),
            "metodologia": (
                "Tabela SIDRA 1621, variável 584, categoria 90707 (PIB a preços de mercado), Brasil. "
                "A variação no mandato compara o último trimestre do governo com o último trimestre "
                "atribuído ao governo anterior. A média do índice no mandato não é usada para comparar "
                "governos, porque o índice cresce com o tempo."
            ),
            "cuidados": [
                "O ajuste sazonal é recalculado a cada divulgação, então toda a série pode mudar "
                "levemente de uma extração para outra.",
            ],
        },
        # -------------------------------------------------------- Mercado de trabalho
        "desocupacao": {
            "nome": "Taxa de desocupação (PNAD Contínua)",
            "grupo": "Mercado de trabalho",
            "fonte": "ibge",
            "tabela": 6381,
            "variavel": 4099,
            "frequencia": "trimestral_movel",
            "tipo": "nivel",
            "unidade": "%",
            "variacao_em": "pontos",
            "direcao": "menor",
            "o_que_mede": (
                "Percentual das pessoas de 14 anos ou mais na força de trabalho que estavam sem "
                "trabalho, disponíveis e procurando emprego na semana de referência."
            ),
            "metodologia": (
                "Tabela SIDRA 6381, variável 4099, Brasil. Cada valor é um trimestre móvel: o dado "
                "de 'ago/2026' é a média de jun, jul e ago/2026, e é atribuído ao governo do mês "
                "final (agosto), como o IBGE identifica o trimestre. A série começa no trimestre "
                "jan-mar/2012."
            ),
            "cuidados": [
                "Não existe PNAD Contínua antes de 2012. Para anos anteriores, veja a série da PME, "
                "que tem metodologia diferente e NÃO deve ser emendada a esta.",
                "Quem desiste de procurar emprego sai da força de trabalho e deixa de contar como "
                "desocupado: olhe junto o nível da ocupação.",
            ],
        },
        "desemprego_pme": {
            "nome": "Taxa de desemprego (PME – 6 regiões metropolitanas)",
            "grupo": "Mercado de trabalho",
            "fonte": "bcb",
            "codigo": 10777,
            "frequencia": "mensal",
            "encerrada": True,
            "tipo": "nivel",
            "unidade": "%",
            "variacao_em": "pontos",
            "direcao": "menor",
            "o_que_mede": (
                "Taxa de desocupação da antiga Pesquisa Mensal de Emprego do IBGE, que cobria apenas "
                "as regiões metropolitanas de Recife, Salvador, Belo Horizonte, Rio de Janeiro, "
                "São Paulo e Porto Alegre."
            ),
            "metodologia": (
                "Série SGS 10777 do Banco Central (dado do IBGE/PME), mensal, de nov/2001 até o "
                "encerramento da pesquisa em fev/2016."
            ),
            "cuidados": [
                "Cobre só 6 regiões metropolitanas (a PNAD Contínua cobre o país todo) e usa idade "
                "mínima de 10 anos (a PNAD Contínua usa 14). Os níveis das duas pesquisas não são "
                "comparáveis: compare tendências, não valores.",
            ],
        },
        "informalidade": {
            "nome": "Taxa de informalidade",
            "grupo": "Mercado de trabalho",
            "fonte": "ibge",
            "tabela": 8529,
            "variavel": 12466,
            "frequencia": "trimestral",
            "tipo": "nivel",
            "unidade": "%",
            "variacao_em": "pontos",
            "direcao": "menor",
            "o_que_mede": (
                "Percentual dos ocupados em situação de informalidade: empregados sem carteira "
                "(inclusive domésticos), empregadores e trabalhadores por conta própria sem CNPJ e "
                "trabalhadores familiares auxiliares."
            ),
            "metodologia": "Tabela SIDRA 8529, variável 12466, Brasil, trimestral.",
            "cuidados": [
                "O IBGE só calcula este indicador a partir do 4º trimestre de 2015, por isso governos "
                "anteriores não têm dado.",
            ],
        },
        "nivel_ocupacao": {
            "nome": "Nível da ocupação",
            "grupo": "Mercado de trabalho",
            "fonte": "ibge",
            "tabela": 6379,
            "variavel": 4097,
            "frequencia": "trimestral_movel",
            "tipo": "nivel",
            "unidade": "%",
            "variacao_em": "pontos",
            "direcao": "maior",
            "o_que_mede": (
                "Percentual das pessoas de 14 anos ou mais que estão trabalhando. Complementa a taxa "
                "de desocupação, porque não é afetado por quem desiste de procurar emprego."
            ),
            "metodologia": "Tabela SIDRA 6379, variável 4097, Brasil, trimestre móvel desde 2012.",
            "cuidados": ["Mesma cobertura temporal da PNAD Contínua (desde 2012)."],
        },
        # -------------------------------------------------------------------- Preços
        "ipca": {
            "nome": "Inflação (IPCA)",
            "grupo": "Preços",
            "fonte": "ibge",
            "tabela": 1737,
            "variavel": 63,
            "frequencia": "mensal",
            "tipo": "variacao_mensal",
            "unidade": "% no mês",
            "direcao": "menor",
            "o_que_mede": (
                "Índice oficial de inflação do país, usado no sistema de metas: variação dos preços "
                "para famílias com renda de 1 a 40 salários mínimos."
            ),
            "metodologia": (
                "Tabela SIDRA 1737, variável 63 (variação mensal), Brasil, desde dez/1979. A inflação "
                "acumulada no mandato é o produto dos fatores mensais: (1+i₁)×(1+i₂)×…×(1+iₙ) − 1."
            ),
            "cuidados": [
                "Antes do Plano Real (jul/1994) o país viveu hiperinflação; para comparar governos "
                "posteriores, use a escala logarítmica ou filtre o período.",
                "Inflação mais baixa nem sempre é boa notícia: deflação persistente também é sinal ruim. "
                "Desde 1999 a referência é a meta definida pelo CMN.",
            ],
        },
        "ipca_12m_ibge": {
            "nome": "IPCA acumulado em 12 meses (divulgado pelo IBGE)",
            "grupo": "Preços",
            "fonte": "ibge",
            "tabela": 1737,
            "variavel": 2265,
            "frequencia": "mensal",
            "tipo": "nivel",
            "unidade": "%",
            "auxiliar": True,
            "o_que_mede": "Usado só para conferir o acumulado em 12 meses que o painel calcula.",
            "metodologia": "Tabela SIDRA 1737, variável 2265, Brasil.",
            "cuidados": [],
        },
        "ipca_indice": {
            "nome": "IPCA – número-índice (dez/1993 = 100)",
            "grupo": "Preços",
            "fonte": "ibge",
            "tabela": 1737,
            "variavel": 2266,
            "frequencia": "mensal",
            "tipo": "nivel",
            "unidade": "índice",
            "auxiliar": True,
            "o_que_mede": "Usado para deflacionar o salário mínimo.",
            "metodologia": "Tabela SIDRA 1737, variável 2266, Brasil.",
            "cuidados": [],
        },
        # --------------------------------------------------------------------- Renda
        "rendimento_real": {
            "nome": "Renda média real do trabalhador",
            "grupo": "Renda",
            "fonte": "ibge",
            "tabela": 6390,
            "variavel": 5933,
            "frequencia": "trimestral_movel",
            "tipo": "nivel",
            "unidade": "R$ (preços do último trimestre)",
            "variacao_em": "percentual",
            "direcao": "maior",
            "o_que_mede": (
                "Rendimento mensal habitual médio dos ocupados, de todos os trabalhos, já corrigido "
                "pela inflação para os preços do trimestre mais recente."
            ),
            "metodologia": (
                "Tabela SIDRA 6390, variável 5933 (nome oficial: rendimento médio mensal real das "
                "pessoas ocupadas, habitualmente recebido em todos os trabalhos), Brasil, trimestre "
                "móvel desde 2012. É uma média por trabalhador, em reais."
            ),
            "cuidados": [
                "O IBGE reajusta toda a série para os preços mais recentes a cada divulgação: os "
                "valores em reais mudam de uma extração para outra, mas as variações não.",
                "É uma média: mudanças em quem está ocupado (ex.: perda de empregos de baixa renda na "
                "pandemia) elevam a média sem que ninguém tenha ganho aumento.",
            ],
        },
        "salario_minimo_real": {
            "nome": "Salário mínimo real (poder de compra)",
            "grupo": "Renda",
            "fonte": "bcb",
            "codigo": 1619,
            "frequencia": "mensal",
            "tipo": "nivel",
            "unidade": "R$ (preços do último mês do IPCA)",
            "variacao_em": "percentual",
            "direcao": "maior",
            "a_partir_de": "1994-07",
            "deflacionar_por": "ipca_indice",
            "o_que_mede": "Poder de compra do salário mínimo nacional, descontada a inflação.",
            "metodologia": (
                "Salário mínimo nominal da série SGS 1619 dividido pelo número-índice do IPCA do "
                "mesmo mês e multiplicado pelo índice do mês mais recente: "
                "SM_real(t) = SM(t) × IPCA(último) / IPCA(t). Começa em jul/1994 porque antes "
                "disso os valores estão em moedas extintas."
            ),
            "cuidados": [
                "O reajuste oficial do mínimo usa o INPC, não o IPCA; a escolha do IPCA aqui é para "
                "manter o mesmo deflator em todo o painel. A diferença entre os dois é pequena.",
            ],
        },
        # -------------------------------------------------------------------- Fiscal
        "resultado_primario": {
            "nome": "Resultado primário do setor público (ano fechado)",
            "grupo": "Fiscal",
            "fonte": "bcb",
            "codigo": 5793,
            "frequencia": "anual",
            "so_dezembro": True,
            "tipo": "nivel",
            "unidade": "% do PIB",
            "variacao_em": "pontos",
            "direcao": "maior",
            "fator": -1,
            "o_que_mede": (
                "Receitas menos despesas do setor público consolidado (União, estados, municípios e "
                "estatais), sem contar os juros, em cada ano fechado (janeiro a dezembro). "
                "Positivo = superávit."
            ),
            "metodologia": (
                "Série SGS 5793 (NFSP primária, acumulada em 12 meses, % do PIB), usando só o valor "
                "de dezembro, que é o resultado do ano fechado: assim cada ano conta inteiro para um "
                "governo, sem misturar meses do anterior. O ano corrente entra quando dezembro for "
                "divulgado. O Banco Central publica a NECESSIDADE de financiamento, em que déficit é "
                "positivo; o painel multiplica por −1 para que superávit apareça como positivo."
            ),
            "cuidados": [
                "Receitas extraordinárias (concessões, dividendos) e despesas atípicas (pandemia em "
                "2020) afetam muito o resultado de um único ano.",
            ],
        },
        "divida_liquida": {
            "nome": "Dívida líquida do setor público",
            "grupo": "Fiscal",
            "fonte": "bcb",
            "codigo": 4513,
            "frequencia": "mensal",
            "tipo": "nivel",
            "unidade": "% do PIB",
            "variacao_em": "pontos",
            "direcao": "menor",
            "aviso_media": "dívida é um estoque acumulado ao longo de décadas: a média reflete sobretudo o nível herdado",
            "o_que_mede": (
                "Dívida do setor público consolidado descontados os ativos (reservas internacionais, "
                "créditos), em proporção do PIB."
            ),
            "metodologia": "Série SGS 4513 do Banco Central, mensal, desde dez/2001.",
            "cuidados": [
                "Como as reservas são em dólar, uma alta do dólar REDUZ a dívida líquida. Olhe junto a "
                "dívida bruta.",
            ],
        },
        "divida_bruta": {
            "nome": "Dívida bruta do governo geral",
            "grupo": "Fiscal",
            "fonte": "bcb",
            "codigo": 13762,
            "frequencia": "mensal",
            "tipo": "nivel",
            "unidade": "% do PIB",
            "variacao_em": "pontos",
            "direcao": "menor",
            "aviso_media": "dívida é um estoque acumulado ao longo de décadas: a média reflete sobretudo o nível herdado",
            "o_que_mede": "Dívida total do governo geral (sem estatais), em proporção do PIB.",
            "metodologia": "Série SGS 13762 do Banco Central (metodologia vigente desde 2008), desde dez/2006.",
            "cuidados": ["Começa em dez/2006: o primeiro governo com dado completo é Lula 2."],
        },
        # ------------------------------------------------------------ Juros e câmbio
        "selic": {
            "nome": "Taxa Selic (meta do Copom)",
            "grupo": "Juros e câmbio",
            "fonte": "bcb",
            "codigo": 432,
            "frequencia": "mensal",
            "tipo": "nivel",
            "unidade": "% a.a.",
            "variacao_em": "pontos",
            "direcao": "menor",
            "ressalva_direcao": (
                "juro menor barateia o crédito; desde 2021 a Selic é decidida pelo Banco Central "
                "autônomo, não pelo presidente"
            ),
            "o_que_mede": (
                "Meta da taxa básica de juros definida pelo Copom, a que é anunciada nas reuniões "
                "e noticiada pela imprensa."
            ),
            "metodologia": (
                "Série SGS 432 do Banco Central (meta Selic, diária). O painel usa a meta em vigor "
                "no último dia de cada mês. A meta existe desde mar/1999, quando o Copom passou a "
                "definir uma meta para a Selic; antes disso o painel não mostra a série."
            ),
            "cuidados": [
                "Desde 2021 o Banco Central é formalmente autônomo e a Selic é decidida pelo Copom, "
                "não pelo presidente da República.",
                "O site destaca o juro menor porque ele barateia crédito e dívida, mas juro alto é a "
                "resposta do Banco Central à inflação: compare junto com o IPCA.",
            ],
        },
        "dolar": {
            "nome": "Dólar comercial (média do mês)",
            "grupo": "Juros e câmbio",
            "fonte": "bcb",
            "codigo": 3698,
            "frequencia": "mensal",
            "tipo": "nivel",
            "unidade": "R$/US$",
            "variacao_em": "percentual",
            "direcao": "menor",
            "ressalva_direcao": "dólar mais barato preserva o poder de compra, mas prejudica exportadores",
            "aviso_media": "valor nominal: entre décadas, pesa mais a inflação acumulada do que o governo",
            "a_partir_de": "1994-07",
            "o_que_mede": "Taxa de câmbio nominal de venda (PTAX), média mensal.",
            "metodologia": "Série SGS 3698 do Banco Central, a partir de jul/1994 (Plano Real).",
            "cuidados": [
                "Valor nominal: não desconta a inflação do Brasil nem a dos EUA, então não é "
                "comparável em nível entre décadas.",
                "O site destaca o dólar menor porque ele preserva o poder de compra e segura a "
                "inflação, mas favorece importações em vez de exportações. Por ser nominal, a média "
                "de governos de décadas diferentes reflete a inflação acumulada: confira também a "
                "variação durante o mandato.",
            ],
        },
    }

    @classmethod
    def series_exibidas(cls) -> dict:
        """Séries exibidas no site (exclui as auxiliares)."""
        return {k: v for k, v in cls.SERIES.items() if not v.get("auxiliar")}

    @classmethod
    def ordem(cls) -> list[str]:
        """Séries exibidas, na ordem dos grupos: é a ordem de colunas e listas no site."""
        exibidas = cls.series_exibidas()
        return [sid for g in cls.GRUPOS for sid in exibidas if exibidas[sid]["grupo"] == g]

    @classmethod
    def montar_url(cls, serie_id: str, inicio: str | None = None, fim: str | None = None) -> str:
        """
        Monta a URL exata consultada para uma série. No IBGE, sem período, pede
        todos os períodos disponíveis; no BCB, `inicio` e `fim` (dd/mm/aaaa) são
        obrigatórios desde 2025.
        """
        s = cls.SERIES[serie_id]
        if s["fonte"] == "ibge":
            periodos = f"{inicio}-{fim}" if inicio and fim else "all"
            url = (
                f"{cls.URL_IBGE}/{s['tabela']}/periodos/{periodos}/variaveis/{s['variavel']}"
                f"?localidades=N1[all]"
            )
            if s.get("classificacao"):
                url += f"&classificacao={s['classificacao']}"
            return url

        url = cls.URL_BCB.format(codigo=s["codigo"]) + "?formato=json"
        if inicio and fim:
            url += f"&dataInicial={inicio}&dataFinal={fim}"
        return url

    @classmethod
    def prefixo_url(cls, serie_id: str) -> str:
        """Início fixo das URLs de uma série: identifica com que configuração ela foi extraída."""
        s = cls.SERIES[serie_id]
        return cls.montar_url(serie_id) if s["fonte"] == "ibge" else cls.URL_BCB.format(codigo=s["codigo"])

    @classmethod
    def link_fonte(cls, serie_id: str) -> str:
        """Página pública onde qualquer pessoa pode conferir a série na fonte original."""
        s = cls.SERIES[serie_id]
        if s["fonte"] == "ibge":
            return f"https://sidra.ibge.gov.br/tabela/{s['tabela']}"
        return s.get("link_checagem", cls.LINK_SGS)

    @classmethod
    def descricao_fonte(cls, serie_id: str) -> str:
        s = cls.SERIES[serie_id]
        if s["fonte"] == "ibge":
            texto = f"IBGE – SIDRA, tabela {s['tabela']}, variável {s['variavel']}"
            if s.get("classificacao"):
                texto += f", classificação {s['classificacao']}"
            return texto
        return f"Banco Central – SGS, série {s['codigo']}"
