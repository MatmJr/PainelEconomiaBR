// Gráficos (Plotly.js, carregado como script global). Cores lidas dos tokens do CSS,
// para acompanhar o tema claro/escuro. Cores de visualização, nunca de partidos.

/**
 * Cores do tema ativo. Os tokens do CSS usam light-dark(), que só é resolvido
 * quando aplicado a uma propriedade de cor: por isso cada token é aplicado a um
 * elemento de teste e lido já como rgb(), no tema que estiver valendo.
 */
function cores() {
  const teste = document.createElement("span");
  teste.style.display = "none";
  document.body.append(teste);
  const ler = (token) => {
    teste.style.color = `var(${token})`;
    return getComputedStyle(teste).color;
  };
  const c = {
    azul: ler("--serie-1"), laranja: ler("--serie-2"), cinza: ler("--cinza"),
    texto: ler("--texto"), textoSec: ler("--texto-sec"), grade: ler("--grade"),
    faixa: ler("--faixa"), destaque: ler("--destaque"), superficie: ler("--superficie"),
  };
  teste.remove();
  return c;
}

// Telas de toque (celular, tablet) ou estreitas: o gráfico fica fixo. Arrastar o dedo
// sobre ele rola a página em vez de dar zoom, e tocar só mostra o valor. Zoom e
// arraste confundem quem não está acostumado e não têm botão óbvio para desfazer.
const TOQUE = window.matchMedia("(pointer: coarse), (max-width: 600px)").matches;

const CONFIG = {
  responsive: true,
  displaylogo: false,
  scrollZoom: false,
  doubleClick: TOQUE ? false : "reset+autosize",
  // No celular a barra de ferramentas cobre os nomes dos mandatos e só serve para zoom
  displayModeBar: TOQUE ? false : "hover",
  modeBarButtonsToRemove: ["select2d", "lasso2d", "autoScale2d", "toggleSpikelines"],
};

/** No toque: sem zoom/arraste nos eixos e sem esconder séries ao tocar na legenda. */
function fixarNoToque(layout) {
  if (!TOQUE) return layout;
  layout.dragmode = false;
  layout.xaxis = { ...layout.xaxis, fixedrange: true };
  layout.yaxis = { ...layout.yaxis, fixedrange: true };
  if (layout.yaxis2) layout.yaxis2 = { ...layout.yaxis2, fixedrange: true };
  layout.legend = { ...layout.legend, itemclick: false, itemdoubleclick: false };
  return layout;
}

function layoutBase(c, tituloY, altura) {
  return {
    height: altura,
    margin: { t: 48, b: 40, l: 56, r: 16 },
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    font: { family: getComputedStyle(document.body).fontFamily, color: c.textoSec, size: 12 },
    separators: ",.",
    hovermode: "x unified",
    hoverlabel: { bgcolor: c.superficie, bordercolor: c.grade, font: { color: c.texto } },
    xaxis: { showgrid: false, linecolor: c.grade, tickcolor: c.grade, automargin: true },
    yaxis: { title: { text: tituloY, standoff: 8 }, gridcolor: c.grade, zerolinecolor: c.grade, automargin: true },
    legend: { orientation: "h", y: -0.16, x: 0 },
    shapes: [],
    annotations: [],
  };
}

const MS_DIA = 86400000;
const data = (iso) => new Date(`${iso}T00:00:00`);

/** Sombreia cada mandato e escreve o nome no topo, alternando a altura para não sobrepor. */
function faixasMandatos(layout, c, mandatos, ini, fim, destaque) {
  mandatos.forEach((m, i) => {
    const a = Math.max(data(m.inicio), ini);
    const b = Math.min(data(m.fim).getTime() + MS_DIA, fim);
    if (a >= b) return;
    const cor = m.id === destaque ? c.destaque : i % 2 === 0 ? c.faixa : "rgba(0,0,0,0)";
    layout.shapes.push({ type: "rect", xref: "x", yref: "paper", x0: new Date(a), x1: new Date(b), y0: 0, y1: 1,
                         fillcolor: cor, line: { width: 0 }, layer: "below" });
    layout.annotations.push({ x: new Date(a + (b - a) / 2), y: i % 2 === 0 ? 1.0 : 1.07, xref: "x", yref: "paper",
                              text: m.rotulo, showarrow: false, yanchor: "bottom", font: { size: 10, color: c.textoSec } });
  });
}

/** Linha fina em cada evento e um marcador com o nome ao passar o mouse. */
function marcasEventos(layout, tracos, c, eventos, ini, fim) {
  const dentro = eventos.filter((e) => data(e.data) >= ini && data(e.data) <= fim);
  if (!dentro.length) return;
  dentro.forEach((e) => layout.shapes.push({ type: "line", xref: "x", yref: "paper", x0: e.data, x1: e.data, y0: 0, y1: 1,
                                             line: { color: c.cinza, width: 1 }, opacity: 0.6 }));
  tracos.push({
    type: "scatter", mode: "markers", x: dentro.map((e) => e.data), y: dentro.map(() => 0.02), yaxis: "y2",
    marker: { symbol: "triangle-up", size: 11, color: c.cinza }, text: dentro.map((e) => e.nome),
    hovertemplate: "%{text}<extra></extra>", name: "Eventos de contexto", showlegend: false,
  });
  layout.yaxis2 = { overlaying: "y", range: [0, 1], visible: false, fixedrange: true };
}

/**
 * Série histórica: linha (ou barras, se anual), com mandatos sombreados.
 * pontos: [{p, i, f, m, v}] vindos de dados/series/<serie>.json
 */
export function serieHistorica(div, pontos, { anual, tituloY, mandatos, eventos, mostrarEventos = true, log = false, destaque = null, casas = 2 }) {
  const c = cores();
  const layout = layoutBase(c, tituloY, div.classList.contains("grafico-alto") ? 460 : 400);
  const traco = {
    x: pontos.map((p) => p.m), y: pontos.map((p) => p.v), customdata: pontos.map((p) => p.p),
    hovertemplate: `%{customdata}: %{y:,.${casas}f}<extra></extra>`, showlegend: false,
  };
  // Plotly rejeita chaves com valor undefined: cada tipo recebe só as suas
  const tracos = [anual
    ? { ...traco, type: "bar", marker: { color: c.azul } }
    : { ...traco, type: "scatter", mode: "lines", line: { color: c.azul, width: 2 } }];
  if (pontos.length) {
    const ini = data(pontos[0].i).getTime();
    const fim = data(pontos[pontos.length - 1].f).getTime() + MS_DIA;
    faixasMandatos(layout, c, mandatos, ini, fim, destaque);
    if (mostrarEventos) marcasEventos(layout, tracos, c, eventos, ini, fim);
    layout.xaxis.range = [new Date(ini), new Date(fim)];
  }
  layout.xaxis.type = "date";
  if (log) layout.yaxis.type = "log";
  Plotly.react(div, tracos, fixarNoToque(layout), CONFIG);
}

/**
 * Uma marca por mandato, em ordem cronológica; sem dados completos em cinza.
 *
 * Quando os valores são todos positivos e o maior é 100 vezes o menor ou mais
 * (caso do IPCA, por causa da hiperinflação de Sarney a Itamar), o eixo passa a
 * ser logarítmico. As barras partem da linha de 1 (e não do zero, que não existe
 * num eixo log), então a altura mostra a ordem de grandeza, não a proporção entre
 * os valores — a nota abaixo do gráfico avisa isso. Devolve true quando usou a escala log.
 */
export function barrasMandatos(div, entradas, metrica, mandatos, tituloY) {
  const c = cores();
  const layout = layoutBase(c, tituloY, 300);
  const ordem = mandatos.map((m) => m.id);
  const rotulos = Object.fromEntries(mandatos.map((m) => [m.id, m.rotulo]));
  const validas = entradas
    .filter((e) => e.metricas[metrica] !== null && e.metricas[metrica] !== undefined)
    .sort((a, b) => ordem.indexOf(a.m) - ordem.indexOf(b.m));

  const valores = validas.map((e) => e.metricas[metrica]);
  const log = valores.length > 1 && valores.every((v) => v > 0) && Math.max(...valores) / Math.min(...valores) >= 100;

  const grupo = (completo, nome, cor) => {
    const parte = validas.filter((e) => (e.status === "completo") === completo);
    const comum = {
      name: nome, x: parte.map((e) => rotulos[e.m]), y: parte.map((e) => e.metricas[metrica]),
      customdata: parte.map((e) => [e.texto[metrica], e.status]),
      hovertemplate: "%{x}: %{customdata[0]}<br>%{customdata[1]}<extra></extra>",
    };
    return { ...comum, type: "bar", marker: { color: cor } };
  };
  const tracos = [grupo(true, "Dados completos", c.azul), grupo(false, "Parcial / em curso / sem herança", c.cinza)]
    .filter((t) => t.x.length);

  layout.barmode = "overlay";
  layout.bargap = 0.25;
  layout.hovermode = "closest";
  layout.margin.t = 12;
  layout.xaxis = { ...layout.xaxis, type: "category", categoryorder: "array",
                   categoryarray: mandatos.map((m) => m.rotulo), tickangle: -45, tickfont: { size: 11 } };
  if (log) {
    // Uma linha de grade por potência de 10, com rótulos 1, 10, 100, 1 mil, 10 mil...
    // O eixo começa em 1 (ou na potência de 10 abaixo do menor valor, se houver valor < 1)
    const inicio = Math.min(0, Math.floor(Math.log10(Math.min(...valores))));
    layout.yaxis = { ...layout.yaxis, type: "log", dtick: 1, exponentformat: "none",
                     range: [inicio, Math.log10(Math.max(...valores)) + 0.25],
                     title: { ...layout.yaxis.title, text: `${tituloY} (escala log)` } };
  } else {
    layout.shapes.push({ type: "line", xref: "paper", x0: 0, x1: 1, y0: 0, y1: 0, line: { color: c.cinza, width: 1 } });
  }
  layout.legend.y = -0.42;
  Plotly.react(div, tracos, fixarNoToque(layout), CONFIG);
  return log;
}

/**
 * Trajetórias alinhadas pela posse: `destaque` em azul, `anterior` em laranja,
 * demais em cinza. Com `iguais`, as duas linhas coloridas têm a mesma espessura
 * (usado na página Comparar, onde nenhum dos dois mandatos é o principal).
 */
export function trajetorias(div, pontos, destaque, anterior, tituloY, { iguais = false } = {}) {
  const c = cores();
  const layout = layoutBase(c, tituloY, 420);
  const nomes = [...new Set(pontos.map((p) => p.mandato))];
  const outros = nomes.filter((m) => m !== destaque && m !== anterior);
  const tracos = [];
  // Na página Comparar (iguais), A vem antes de B na legenda; nas demais, o destaque é desenhado por cima
  const ordem = iguais ? [destaque, anterior, ...outros] : [...outros, anterior, destaque];
  ordem.forEach((m, i) => {
    const parte = pontos.filter((p) => p.mandato === m);
    if (!m || !parte.length) return;
    const cinza = m !== destaque && m !== anterior;
    const cor = m === destaque ? c.azul : m === anterior ? c.laranja : c.cinza;
    tracos.push({
      type: "scatter", mode: "lines", x: parte.map((p) => p.x), y: parte.map((p) => p.y),
      customdata: parte.map((p) => p.p), name: cinza ? "Demais mandatos" : m, legendgroup: cinza ? "outros" : m,
      showlegend: !cinza || m === outros[0], opacity: cinza ? 0.55 : 1,
      line: { color: cor, width: cinza ? 1 : iguais ? 2.5 : m === destaque ? 3 : 2 },
      hovertemplate: `${m} · %{customdata}: %{y:,.2f}<extra></extra>`,
    });
    if (!cinza) {
      const ultimo = parte[parte.length - 1];
      layout.annotations.push({ x: ultimo.x, y: ultimo.y, text: m, showarrow: false, xanchor: "left", xshift: 6,
                                font: { color: cor, size: 12 } });
    }
  });
  layout.hovermode = "closest";
  layout.legend.y = -0.3;
  layout.margin.b = 60;
  layout.xaxis = { ...layout.xaxis, title: { text: "meses desde a posse" }, dtick: 12, zeroline: false };
  layout.shapes.push({ type: "line", xref: "paper", x0: 0, x1: 1, y0: 0, y1: 0, line: { color: c.cinza, width: 1 } });
  Plotly.react(div, tracos, fixarNoToque(layout), CONFIG);
}
