# Painel Economia BR — a economia por mandato presidencial

Site estático que extrai dados oficiais do **IBGE** e do **Banco Central** e resume os principais indicadores econômicos do Brasil por mandato presidencial (de Sarney a Lula 3): PIB, desemprego, informalidade, inflação, renda, salário mínimo, contas públicas, juros e câmbio.

O objetivo é permitir **checar** afirmações do tipo *"a economia estava ruim com o presidente X"*: cada número do site mostra o cálculo passo a passo, os dados usados, a URL exata consultada na API, o link da fonte original e a metodologia aplicada.

O projeto segue a mesma estrutura do [ProjEngDados](../ProjEngDados) (Extract → Load → Transform → Load, com camadas bronze e prata, orquestração com Prefect) e a ideia de catálogo de URLs com descrição do [ETL_IBGE_BCB](https://github.com/MatmJr/ETL_IBGE_BCB).

## Estrutura do projeto

```
src/
  config.py       # caminhos e DATABASE_URL (opcional) lidos do .env
  catalogo.py     # catálogo das séries: fonte, tabela/variável, unidade, metodologia e cuidados
  presidentes.py  # mandatos (datas de posse/saída) e eventos de contexto
  periodos.py     # converte códigos de período (202608, 201504, 2016...) em intervalos de datas
  extract.py      # Extract: busca as séries nas APIs do IBGE (SIDRA) e do BCB (SGS)
  transform.py    # Transform: respostas brutas -> tabela longa (serie, período, valor); deflaciona
  load.py         # Load: bronze em JSON, prata em SQLite (e no Neon, se configurado)
  analise.py      # atribuição de cada dado a um mandato e métricas por mandato
  publicar.py     # valida a camada prata e gera o site estático (dados + páginas)
web/
  templates/      # páginas HTML (Jinja2): resumo, comparar, checagem, séries, metodologia, dados
  static/         # CSS e JavaScript do site (o JS só exibe; não faz contas)
site/             # site gerado, publicado pelo Netlify (não edite à mão)
dashboard/        # painel Streamlit para exploração local (opcional)
tests/            # testes das regras de atribuição, das contas e da publicação
run_etl.py                # pipeline como script simples
orchestration_prefect.py  # o mesmo pipeline orquestrado com Prefect
gerar_site.py             # gera a pasta site/ a partir da camada prata
servir_site.py            # serve site/ localmente com os mesmos cabeçalhos do Netlify
netlify.toml              # configuração do Netlify (pasta publicada e cabeçalhos)
```

### Camadas de dados

| Camada | Onde fica | Como é gravada |
|--------|-----------|----------------|
| **Bronze** (resposta da API, sem alteração) | `data/bronze/<série>/<data_extracao>.json` | só recebe arquivos novos: cada execução cria um arquivo com a resposta bruta, as URLs consultadas e a data da extração. Nada é apagado, então dá para refazer qualquer conta a partir do que a API devolveu naquele dia |
| **Prata** (dado tratado) | tabelas `observacoes`, `extracoes` e `mandatos` em `data/economia.db` (SQLite) e, opcionalmente, no Neon | substituída a cada execução |
| **Publicação** (site) | pasta `site/`, versionada no git | gerada do zero a cada `python gerar_site.py` |

O pipeline e a geração do site rodam no seu computador; o Netlify só serve a pasta `site/`. Por isso `data/` fica fora do git e `site/` entra.

## Séries

| Grupo | Série | Fonte | Desde |
|-------|-------|-------|-------|
| Atividade | PIB – crescimento real anual | BCB SGS 7326 (dado do IBGE) | 1980 |
| Atividade | PIB per capita – crescimento real | IBGE SIDRA 6784 | 1996 |
| Atividade | PIB trimestral dessazonalizado | IBGE SIDRA 1621 | 1996 |
| Trabalho | Taxa de desocupação (PNAD Contínua) | IBGE SIDRA 6381 | 2012 |
| Trabalho | Taxa de desemprego (PME, 6 regiões metropolitanas) | BCB SGS 10777 | 2001–2016 |
| Trabalho | Taxa de informalidade | IBGE SIDRA 8529 | 2015 |
| Trabalho | Nível da ocupação | IBGE SIDRA 6379 | 2012 |
| Preços | IPCA (variação mensal) | IBGE SIDRA 1737 | 1979 |
| Renda | Rendimento médio real do trabalho | IBGE SIDRA 6390 | 2012 |
| Renda | Salário mínimo real (deflacionado pelo IPCA) | BCB SGS 1619 + IPCA | 1994 |
| Fiscal | Resultado primário (ano fechado, % PIB) | BCB SGS 5793 (valor de dezembro) | 2002 |
| Fiscal | Dívida líquida do setor público (% PIB) | BCB SGS 4513 | 2001 |
| Fiscal | Dívida bruta do governo geral (% PIB) | BCB SGS 13762 | 2006 |
| Juros e câmbio | Selic (meta do Copom) | BCB SGS 432 | 1999 |
| Juros e câmbio | Dólar (média mensal) | BCB SGS 3698 | 1994 |

Para incluir uma série nova, basta acrescentar uma entrada em `src/catalogo.py`: o pipeline, o resumo, a comparação e a página de metodologia passam a usá-la automaticamente.

## Metodologia (resumo)

A metodologia completa aparece na página **Metodologia** do site, gerada a partir do mesmo código usado nos cálculos.

- **Atribuição:** cada dado cobre um intervalo (mês, trimestre, trimestre móvel ou ano) e é atribuído ao governo que estava no cargo no **ponto médio** do intervalo, ou seja, a quem governou a maior parte do período. Ex.: maio/2016 vai para Temer (20 dos 31 dias). A exceção são os trimestres móveis da PNAD Contínua, atribuídos pelo mês final, como o IBGE os identifica e a imprensa os noticia (out-nov-dez/2018 é a herança de Bolsonaro).
- **Defasagem:** opcionalmente, cada dado é atribuído a quem governava 3, 6 ou 12 meses antes, para testar se a conclusão depende do tempo que as políticas levam para fazer efeito.
- **Herança:** o último dado atribuído ao governo anterior. Para séries de nível (desemprego, dívida...), o painel mostra herança, valor final, variação (fim − herança) e média.
- **Séries de variação** (IPCA, PIB): os percentuais são compostos, não somados — acumulado = ∏(1 + vᵢ/100) − 1 e média anual = (1 + acumulado)^(k/n) − 1.
- **Status:** cada número indica se os dados estão completos, parciais, sem herança ou se o mandato ainda está em curso. Rankings só comparam mandatos completos.
- **Conferência:** o IPCA em 12 meses calculado pelo painel é comparado com o publicado pelo IBGE, para mostrar que a conta de acumulação reproduz o número oficial.
- **Diferenças com o noticiado:** a página Metodologia explica por que um número pode não bater com reportagens antigas (revisões do PIB e das razões em % do PIB, reponderação da PNAD, anos de troca de governo, acumulado × média anual, meta × Selic efetiva).

## Configuração do ambiente

### Windows

```bash
python -m venv .venv
```

```bash
.venv\Scripts\activate
```

### Linux/Mac

```bash
python3 -m venv .venv
```

```bash
source .venv/bin/activate
```

### Dependências

```bash
pip install -r requirements.txt
```

### Variáveis de ambiente (opcional)

Sem nenhuma configuração, tudo funciona com o SQLite local. Copie `.env.example` para `.env` se quiser:

- `SITE_URL`: endereço público do site (ex.: `https://economia-por-presidente.netlify.app`). Com ele, o site é gerado com URLs canônicas, `sitemap.xml` e `robots.txt`;
- `REPO_URL`: endereço do repositório no GitHub, usado nos links "código aberto" e "reportar um erro";
- `DATABASE_URL`: grava a camada prata também no Neon (opcional).

## Atualizar e publicar

1. Extrair os dados (leva cerca de 30 segundos; as APIs públicas às vezes oscilam e o extrator tenta de novo sozinho):

```bash
python run_etl.py
```

2. Gerar o site. Antes de gerar, os dados são conferidos: série vazia, valor nulo ou período duplicado interrompem a geração, e séries que parecem desatualizadas geram um aviso.

```bash
python gerar_site.py
```

3. Conferir localmente, com os mesmos cabeçalhos de segurança do Netlify, em http://localhost:8000:

```bash
python servir_site.py
```

4. Publicar: faça commit da pasta `site/` e dê push. O Netlify publica sozinho a cada push.

### Configurar o Netlify (uma vez)

1. Suba o repositório para o GitHub.
2. No Netlify: **Add new site → Import an existing project**, escolha o repositório.
3. Não é preciso preencher nada: o `netlify.toml` já diz que a pasta publicada é `site/` e que não há comando de build.
4. Depois do primeiro deploy, coloque o endereço gerado em `SITE_URL` no `.env`, rode `python gerar_site.py` de novo e faça push.

Alternativa sem GitHub: instale a [Netlify CLI](https://docs.netlify.com/cli/get-started/) e publique a pasta direto com `netlify deploy --prod --dir=site`.

### Como o site funciona

- **Todas as contas são feitas em Python** (`src/analise.py`, com testes). `gerar_site.py` calcula os 720 resumos possíveis (15 séries × 12 mandatos × 4 defasagens) e grava em `site/dados/` como JSON. O JavaScript só lê esses arquivos e reage aos controles, então o site nunca diverge da metodologia.
- **Uma página por checagem**, como `/checar/bolsonaro/desocupacao/`, já com o resumo no HTML: aparece em buscadores e gera prévia ao ser compartilhada. A defasagem escolhida vai na URL (`?d=6`), então um link compartilhado mostra sempre os mesmos números.
- **Tudo é baixável**: `site/dados/observacoes.csv`, `resumo.csv` e a resposta bruta mais recente de cada API em `site/dados/bronze/`.
- **CSS e JS ficam em `/static/<hash>/`**: o endereço muda a cada versão, então podem ficar em cache por um ano sem que ninguém veja uma versão velha.
- **Único recurso externo**: o Plotly.js, carregado do jsDelivr com verificação de integridade (SRI). A política de segurança (CSP) do `netlify.toml` bloqueia qualquer outro script.

### Painel Streamlit (opcional)

O painel em `dashboard/` continua funcionando para explorar os dados localmente:

```bash
python -m streamlit run dashboard/app.py
```

### Testes

```bash
python -m pytest
```

## Páginas do site

1. **Resumo** — tabela com todos os indicadores × mandatos (cada número leva à sua checagem) e gráficos de barras por indicador.
2. **Comparar** — dois mandatos lado a lado em todos os indicadores, com a trajetória de cada um desde a posse. O valor melhor é marcado só onde há consenso sobre a direção (e nunca no acumulado de inflação/PIB, que depende da duração do mandato, nem na média de índices que crescem com o tempo). O site não soma quantas vezes cada mandato foi melhor. Nenhum mandato vem escolhido; depois de escolher, a seleção fica na URL (`/comparar/?a=lula2&b=bolsonaro`), para compartilhar.
3. **Checar** — escolha um mandato e um indicador: frase-resumo, comparação com os outros governos, cálculo passo a passo, teste de robustez com diferentes defasagens, trajetórias alinhadas pela posse, dados usados (com download) e fonte.
4. **Séries** — série completa com os mandatos sombreados e eventos de contexto (crise de 2008, pandemia etc.).
5. **Metodologia** — regra de atribuição, fórmulas, status, erros comuns ao comparar governos, datas dos mandatos e ficha de cada série.
6. **Dados** — registro da extração de cada série e downloads.

## Créditos

Desenvolvido por **Marco Mialaret Júnior** com [Claude Code](https://claude.com/claude-code).

Dados: [IBGE](https://sidra.ibge.gov.br) (SIDRA) e [Banco Central do Brasil](https://www3.bcb.gov.br/sgspub) (SGS).

## Limitações

- O painel **descreve** o que aconteceu durante cada mandato; não mede o efeito causal das políticas de cada governo. Congresso, Banco Central, estados e a economia mundial também influenciam os resultados.
- Séries com metodologias diferentes (PME e PNAD Contínua) não são emendadas.
- Dados recentes (PIB, contas nacionais) são preliminares e podem ser revisados pelo IBGE; a data de cada extração fica registrada.
