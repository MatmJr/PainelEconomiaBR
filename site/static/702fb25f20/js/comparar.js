import { aoMudarTema, carregar, comDefasagem, esc, ligarDefasagem, mostrarErro } from "./comum.js";
import { trajetorias } from "./graficos.js";

const MARCA = { "completo": "", "mandato em curso": "*", "dados parciais": "*", "sem valor herdado": "†", "sem dados": "" };
const EXPLICA_MODO = {
  media: "Média: como o indicador ficou, em média, durante cada mandato. Para inflação e PIB, quanto subiram por ano, em média.",
  mudanca: "Mudança: quanto o indicador mudou entre o que cada governo recebeu e o que entregou. Para inflação e PIB, o total acumulado — que depende da duração do mandato, por isso ali não há destaque.",
};

const el = (id) => document.getElementById(id);
const alvo = el("comparacao");
// Nenhum mandato vem escolhido: a pessoa decide o que comparar (um link compartilhado traz ?a= e ?b=)
const estado = { a: "", b: "", modo: "media", d: 0 };
let meta, placar;

// ---------------------------------------------------------------- estado na URL
// A escolha fica na URL (?a=...&b=...), para o link compartilhado abrir a mesma comparação
function lerUrl() {
  const q = new URL(location.href).searchParams;
  const ids = meta.mandatos.map((m) => m.id);
  // Prioridade: o que está na URL; senão, o que o navegador restaurou nos seletores
  // (ao voltar para a página), para a tabela nunca divergir do que aparece selecionado
  for (const chave of ["a", "b"]) {
    const daUrl = q.get(chave);
    const restaurado = el(`sel-${chave}`).value;
    if (ids.includes(daUrl)) estado[chave] = daUrl;
    else if (ids.includes(restaurado)) estado[chave] = restaurado;
  }
  el("sel-a").value = estado.a;
  el("sel-b").value = estado.b;
}

const ambosEscolhidos = () => Boolean(estado.a && estado.b);

function gravarUrl() {
  const url = new URL(location.href);
  for (const chave of ["a", "b"]) {
    if (estado[chave]) url.searchParams.set(chave, estado[chave]); else url.searchParams.delete(chave);
  }
  history.replaceState(null, "", url);
}

// ---------------------------------------------------------------- tabela
const metricaDe = (sid) => (estado.modo === "mudanca" ? meta.series[sid].metrica_mudanca : "media");

/**
 * Qual dos dois valores é melhor, segundo a direção do catálogo. Não marca nada
 * quando a série é de contexto, quando falta um dos valores, quando empatam, ou
 * no acumulado (mudança) de inflação e PIB, que depende da duração do mandato.
 */
function melhor(sid, ea, eb, m) {
  const s = meta.series[sid];
  if (!s.direcao || (estado.modo === "mudanca" && s.tipo !== "nivel")) return null;
  if (estado.modo === "media" && !s.media_comparavel) return null;
  const va = ea?.metricas[m];
  const vb = eb?.metricas[m];
  if (va == null || vb == null || va === vb) return null;
  // Iguais na tela (diferença só em casas que não aparecem): sem marca, para não confundir
  const naTela = (e) => e.texto[m].replace(/ \(\d+ anos?\)$/, "");
  if (naTela(ea) === naTela(eb)) return null;
  const aVence = s.direcao === "menor" ? va < vb : va > vb;
  return aVence ? "a" : "b";
}

function celula(sid, mid, e, m, ehMelhor) {
  // data-mandato: no celular, cada valor mostra o nome do mandato acima dele
  const rotulo = esc(meta.mandatos.find((x) => x.id === mid).rotulo);
  if (!e || e.status === "sem dados" || e.metricas[m] == null) {
    const marca = e && e.status === "sem valor herdado" ? "†" : "";
    return `<td class="num vazio" data-mandato="${rotulo}">—${marca}</td>`;
  }
  const classe = e.status === "completo" ? "num" : "num parcial";
  const href = comDefasagem(`/checar/${mid}/${sid}/`, estado.d);
  const valor = `<a href="${href}" title="${esc(e.status)}">${esc(e.texto[m] + MARCA[e.status])}</a>`;
  // O valor que atende ao critério ganha destaque visual (negrito e fundo), sem etiqueta; o texto
  // escondido mantém a informação para leitores de tela
  const conteudo = ehMelhor ? `<span class="realce">${valor}<span class="pular"> (em destaque)</span></span>` : valor;
  return `<td class="${classe}" data-mandato="${rotulo}">${conteudo}</td>`;
}

function desenharTabela() {
  const rot = Object.fromEntries(meta.mandatos.map((m) => [m.id, m.rotulo]));
  el("explica-modo").textContent = EXPLICA_MODO[estado.modo];

  if (!ambosEscolhidos()) {
    const falta = !estado.a && !estado.b ? "os dois mandatos" : "o outro mandato";
    alvo.innerHTML = `<p class="carregando">Escolha ${falta} acima para comparar.</p>`;
    return;
  }
  if (estado.a === estado.b) {
    alvo.innerHTML = '<p class="alerta alerta-aviso">Escolha dois mandatos diferentes para comparar.</p>';
    return;
  }
  const mapa = new Map(placar[String(estado.d)].map((e) => [`${e.s}|${e.m}`, e]));
  const corpo = meta.grupos.map((grupo) => {
    const sids = meta.ordem.filter((sid) => meta.series[sid].grupo === grupo);
    const linhas = sids.map((sid) => {
      const s = meta.series[sid];
      const m = metricaDe(sid);
      const ea = mapa.get(`${sid}|${estado.a}`);
      const eb = mapa.get(`${sid}|${estado.b}`);
      const venc = melhor(sid, ea, eb, m);
      // Linhas sem dado nos dois mandatos (ex.: PME em governos recentes) não ajudam a comparar
      if ([ea, eb].every((e) => !e || e.metricas[m] == null)) return "";
      const semMelhor = !s.direcao ? "contexto, sem destaque"
        : estado.modo === "media" && !s.media_comparavel ? `média não comparável (${s.motivo_media}); veja a mudança no mandato` : null;
      const ressalva = s.ressalva_direcao ? ` (${s.ressalva_direcao})` : "";
      const aviso = estado.modo === "media" && s.aviso_media ? ` · atenção: ${s.aviso_media}; veja também a mudança no mandato` : "";
      const direcao = semMelhor ?? `destaque: ${s.direcao === "menor" ? "menor valor" : "maior valor"}${ressalva}${aviso}`;
      return `<tr><th scope="row"><span class="indicador">${esc(s.nome)}</span>
        <span class="unidade">${esc(s.rotulos_unidade[m])} · ${direcao}</span></th>
        ${celula(sid, estado.a, ea, m, venc === "a")}${celula(sid, estado.b, eb, m, venc === "b")}</tr>`;
    }).join("");
    return linhas ? `<tr class="grupo"><th colspan="3" scope="colgroup">${esc(grupo)}</th></tr>${linhas}` : "";
  }).join("");

  alvo.innerHTML = `<table class="comparacao"><caption class="pular">Comparação entre ${esc(rot[estado.a])} e ${esc(rot[estado.b])}</caption>
    <thead><tr><th scope="col">Indicador</th>
      <th scope="col" class="coluna-mandato"><span class="marcador marcador-a" aria-hidden="true"></span>${esc(rot[estado.a])}</th>
      <th scope="col" class="coluna-mandato"><span class="marcador marcador-b" aria-hidden="true"></span>${esc(rot[estado.b])}</th>
    </tr></thead><tbody>${corpo}</tbody></table>`;
}

// ---------------------------------------------------------------- trajetória
async function desenharTrajetoria() {
  const sid = el("sel-serie").value;
  const s = meta.series[sid];
  const rot = Object.fromEntries(meta.mandatos.map((m) => [m.id, m.rotulo]));
  const alvoGrafico = el("grafico-trajetorias");
  const legenda = el("legenda-trajetorias");
  if (!ambosEscolhidos() || estado.a === estado.b) {
    alvoGrafico.hidden = true;
    legenda.textContent = "A trajetória aparece depois de escolher dois mandatos diferentes.";
    return;
  }
  let dados;
  try {
    dados = await carregar(`checar/${sid}.json`);
  } catch (erro) {
    mostrarErro(alvoGrafico, erro);
    return;
  }
  const escolhidos = [rot[estado.a], rot[estado.b]];
  const pontos = dados.trajetorias[String(estado.d)].filter((p) => escolhidos.includes(p.mandato));
  const faltam = escolhidos.filter((r) => !pontos.some((p) => p.mandato === r));

  alvoGrafico.hidden = pontos.length === 0;
  if (pontos.length) {
    const tituloY = s.tipo !== "nivel" ? "% acumulado desde a posse"
      : s.unidades_metrica.variacao === "p.p." ? "p.p. em relação à herança" : "% em relação à herança";
    trajetorias(alvoGrafico, pontos, rot[estado.a], rot[estado.b], tituloY, { iguais: true });
  }
  const cores = [["Azul", rot[estado.a]], ["Laranja", rot[estado.b]]].filter(([, r]) => !faltam.includes(r));
  legenda.textContent = [
    cores.map(([cor, r]) => `${cor}: ${r}.`).join(" "),
    pontos.length ? "As linhas começam em 0 na posse, para comparar o que mudou em cada governo." : "",
    faltam.length ? `Sem dados desta série para ${faltam.join(" e ")}.` : "",
  ].filter(Boolean).join(" ");
}

// ---------------------------------------------------------------- início
function atualizar() {
  gravarUrl();
  desenharTabela();
  desenharTrajetoria();
}

async function iniciar() {
  try {
    [meta, placar] = await Promise.all([carregar("meta.json"), carregar("resumo.json")]);
  } catch (erro) {
    mostrarErro(alvo, erro);
    return;
  }
  lerUrl();
  estado.modo = document.querySelector('input[name="modo"]:checked')?.value ?? "media";

  el("sel-a").addEventListener("change", () => { estado.a = el("sel-a").value; atualizar(); });
  el("sel-b").addEventListener("change", () => { estado.b = el("sel-b").value; atualizar(); });
  el("trocar").addEventListener("click", () => {
    [estado.a, estado.b] = [estado.b, estado.a];
    el("sel-a").value = estado.a;
    el("sel-b").value = estado.b;
    atualizar();
  });
  document.querySelectorAll('input[name="modo"]').forEach((r) => r.addEventListener("change", () => {
    estado.modo = r.value;
    desenharTabela();
  }));
  el("sel-serie").addEventListener("change", desenharTrajetoria);
  el("escolha").addEventListener("submit", (ev) => ev.preventDefault());

  ligarDefasagem((d) => { estado.d = d; atualizar(); });
  aoMudarTema(desenharTrajetoria);
}

iniciar();
