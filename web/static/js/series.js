import { aoMudarTema, baixarCSV, carregar, mostrarErro } from "./comum.js";
import { serieHistorica } from "./graficos.js";

const el = (id) => document.getElementById(id);
const sel = el("sel-serie");
const grafico = el("grafico");
let meta;

const casasDe = (s) => (s.unidade === "R$/US$" ? 4 : s.unidade.startsWith("R$") ? 0 : 2);

/** Preenche os seletores de ano com o intervalo da série e mantém a escolha quando possível. */
function preencherAnos(pontos, padraoIni) {
  const primeiro = Number(pontos[0].i.slice(0, 4));
  const ultimo = Number(pontos[pontos.length - 1].f.slice(0, 4));
  const opcoes = Array.from({ length: ultimo - primeiro + 1 }, (_, k) => primeiro + k);
  for (const [id, valor] of [["ano-ini", Math.max(primeiro, padraoIni ?? primeiro)], ["ano-fim", ultimo]]) {
    el(id).innerHTML = opcoes.map((a) => `<option value="${a}">${a}</option>`).join("");
    el(id).value = String(valor);
  }
}

async function pontosDaSerie(sid) {
  const dados = await carregar(`series/${sid}.json`);
  const mensal = document.querySelector('input[name="forma"]:checked').value === "mensal";
  return sid === "ipca" && !mensal ? dados.acumulado_12m : dados.pontos;
}

async function desenhar() {
  const sid = sel.value;
  const s = meta.series[sid];
  const ipca12 = sid === "ipca" && document.querySelector('input[name="forma"]:checked').value === "12m";
  const ini = el("ano-ini").value;
  const fim = el("ano-fim").value;
  const pontos = (await pontosDaSerie(sid)).filter((p) => p.i.slice(0, 4) >= ini && p.i.slice(0, 4) <= fim);

  const temNaoPositivo = pontos.some((p) => p.v <= 0);
  el("log").disabled = temNaoPositivo;
  if (temNaoPositivo) el("log").checked = false;
  el("log").parentElement.title = temNaoPositivo ? "Indisponível quando há valores menores ou iguais a zero." : "";

  serieHistorica(grafico, pontos, {
    anual: s.frequencia === "anual", tituloY: ipca12 ? "% em 12 meses" : s.unidade, casas: casasDe(s),
    mandatos: meta.mandatos, eventos: meta.eventos, mostrarEventos: el("eventos").checked, log: el("log").checked,
  });

  el("baixar").onclick = () => baixarCSV(`${sid}${ipca12 ? "_12meses" : ""}.csv`, [
    { chave: "p", titulo: "periodo" }, { chave: "i", titulo: "data_inicio" }, { chave: "f", titulo: "data_fim" },
    { chave: "v", titulo: `valor (${ipca12 ? "% em 12 meses" : s.unidade})` },
  ], pontos);
}

async function trocarSerie() {
  const sid = sel.value;
  el("campo-forma").hidden = sid !== "ipca";
  document.querySelectorAll(".cartao-serie").forEach((c) => { c.hidden = c.dataset.serie !== sid; });
  const url = new URL(location.href);
  url.searchParams.set("s", sid);
  history.replaceState(null, "", url);
  // IPCA começa em 1996 por padrão: até meados de 1995 o acumulado em 12 meses ainda
  // inclui a hiperinflação anterior ao Plano Real e achata o resto do gráfico
  preencherAnos(await pontosDaSerie(sid), sid === "ipca" ? 1996 : null);
  await desenhar();
}

async function iniciar() {
  try {
    meta = await carregar("meta.json");
  } catch (erro) {
    mostrarErro(grafico, erro);
    return;
  }
  const pedida = new URL(location.href).searchParams.get("s");
  if (pedida && meta.ordem.includes(pedida)) sel.value = pedida;

  sel.addEventListener("change", trocarSerie);
  document.querySelectorAll('input[name="forma"]').forEach((r) => r.addEventListener("change", trocarSerie));
  for (const id of ["ano-ini", "ano-fim", "eventos", "log"]) el(id).addEventListener("change", desenhar);
  aoMudarTema(desenhar);
  await trocarSerie();
}

iniciar();
