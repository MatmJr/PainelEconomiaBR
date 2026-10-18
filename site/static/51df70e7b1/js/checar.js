import {
  DEFASAGENS, aoMudarTema, baixarCSV, carregar, comDefasagem, esc, fmtData, fmtNum, ligarDefasagem, mostrarErro, negrito,
} from "./comum.js";
import { serieHistorica, trajetorias } from "./graficos.js";

const raiz = document.getElementById("checagem");
const mid = raiz.dataset.mandato;
const sid = raiz.dataset.serie;
let meta, checar, serie, d = 0;

// Trocar de mandato ou indicador leva à página daquela checagem (cada par tem sua URL)
function irPara() {
  const m = document.getElementById("sel-mandato").value;
  const s = document.getElementById("sel-serie").value;
  location.href = comDefasagem(`/checar/${m}/${s}/`, d);
}
document.getElementById("sel-mandato").addEventListener("change", irPara);
document.getElementById("sel-serie").addEventListener("change", irPara);
document.getElementById("escolha").addEventListener("submit", (ev) => { ev.preventDefault(); irPara(); });

function chavesMetricas(s) {
  return s.tipo === "nivel" ? ["heranca", "final", "variacao", "media"] : ["acumulado", "media"];
}

function desenharResumo(r, s) {
  document.getElementById("frase").innerHTML = negrito(r.frase);

  const aviso = document.getElementById("aviso-status");
  const semDados = r.status === "sem dados";
  aviso.hidden = r.status === "completo";
  aviso.textContent = semDados
    ? "Esta série não cobre este mandato. Veja na página Metodologia o período de cada série."
    : `Status dos dados: ${r.status} (${r.n} de ${r.esperado} períodos). Compare com cautela.`;
  document.getElementById("secoes-com-dados").hidden = semDados;

  document.getElementById("metricas").innerHTML = semDados ? "" : chavesMetricas(s).map((k) =>
    `<div class="metrica"><span class="metrica-rotulo">${esc(s.metricas[k])}</span>
     <span class="metrica-valor">${esc(r.texto[k] ?? "—")}</span></div>`).join("");
  document.getElementById("ranking").innerHTML = r.ranking ? negrito(r.ranking) : "";

  document.getElementById("explicacao").innerHTML = r.explicacao.map((l) => `<li>${negrito(l)}</li>`).join("");
  document.getElementById("regra").innerHTML =
    `<strong>Regra de atribuição:</strong> cada período conta para quem governou a maior parte dele (ponto médio do período` +
    `${d ? ` menos ${d} meses de defasagem` : ""}). Detalhes na <a href="/metodologia/#atribuicao">metodologia</a>.`;
}

function desenharRobustez(s) {
  const k = s.metrica_mudanca;
  const linhas = DEFASAGENS.map((x) => {
    const r = checar.lags[String(x)][mid];
    const atual = x === d ? ' aria-current="true" style="font-weight:600"' : "";
    return `<tr${atual}><td>${x} meses</td><td class="num">${esc(r.texto[k] ?? "—")}</td>
      <td class="num">${esc(r.texto.media ?? "—")}</td><td class="num">${r.n} de ${r.esperado}</td><td>${esc(r.status)}</td></tr>`;
  }).join("");
  document.getElementById("robustez").innerHTML = `<table><thead><tr><th>Defasagem</th>
    <th class="num">${esc(s.metricas[k])}</th><th class="num">${esc(s.metricas.media)}</th><th class="num">Períodos</th><th>Status</th>
    </tr></thead><tbody>${linhas}</tbody></table>`;
}

function desenharGraficos(s) {
  const rotulos = meta.mandatos.map((m) => m.rotulo);
  const pos = meta.mandatos.findIndex((m) => m.id === mid);
  const rotulo = rotulos[pos];
  const anterior = pos > 0 ? rotulos[pos - 1] : null;

  const traj = checar.trajetorias[String(d)];
  const alvoTraj = document.getElementById("grafico-trajetorias");
  const legenda = document.getElementById("legenda-trajetorias");
  if (traj.some((p) => p.mandato === rotulo)) {
    const tituloY = s.tipo !== "nivel" ? "% acumulado desde a posse"
      : s.unidades_metrica.variacao === "p.p." ? "p.p. em relação à herança" : "% em relação à herança";
    alvoTraj.hidden = false;
    trajetorias(alvoTraj, traj, rotulo, anterior, tituloY);
    legenda.textContent = `Azul: ${rotulo}. Laranja: mandato anterior. Cinza: demais. Todos começam em 0 na posse.`;
  } else {
    alvoTraj.hidden = true;
    legenda.textContent = "Sem valor herdado para alinhar as trajetórias deste mandato.";
  }

  // IPCA: mostrado como acumulado em 12 meses a partir de jun/1995, o primeiro
  // acumulado que cobre só meses do Plano Real
  const ipca = sid === "ipca";
  const pontos = ipca ? serie.acumulado_12m.filter((p) => p.i >= "1995-06-01") : serie.pontos;
  serieHistorica(document.getElementById("grafico-serie"), pontos, {
    anual: s.frequencia === "anual", tituloY: ipca ? "% em 12 meses" : s.unidade,
    mandatos: meta.mandatos, eventos: meta.eventos, destaque: mid,
  });
}

function desenharDados(r, s) {
  const linhas = r.linhas;
  document.getElementById("tabela-dados").innerHTML = `<table><thead><tr><th>Papel</th><th>Período</th><th>Início</th><th>Fim</th>
    <th>Data usada na atribuição</th><th class="num">Valor (${esc(s.unidade)})</th></tr></thead><tbody>${
    linhas.map((l) => `<tr><td>${esc(l.papel)}</td><td>${esc(l.p)}</td><td>${fmtData(l.i)}</td><td>${fmtData(l.f)}</td>
      <td>${fmtData(l.a)}</td><td class="num">${fmtNum(l.v, 2)}</td></tr>`).join("")}</tbody></table>`;
  document.getElementById("baixar").onclick = () => baixarCSV(`${sid}_${mid}_defasagem${d}.csv`, [
    { chave: "papel", titulo: "papel" }, { chave: "p", titulo: "periodo" }, { chave: "i", titulo: "data_inicio" },
    { chave: "f", titulo: "data_fim" }, { chave: "a", titulo: "data_atribuicao" }, { chave: "v", titulo: `valor (${s.unidade})` },
  ], linhas);
}

function desenhar() {
  const s = meta.series[sid];
  const r = checar.lags[String(d)][mid];
  desenharResumo(r, s);
  if (r.status === "sem dados") return;
  desenharRobustez(s);
  desenharGraficos(s);
  desenharDados(r, s);
}

async function iniciar() {
  try {
    [meta, checar, serie] = await Promise.all([carregar("meta.json"), carregar(`checar/${sid}.json`), carregar(`series/${sid}.json`)]);
  } catch (erro) {
    mostrarErro(document.getElementById("metricas"), erro);
    return;
  }
  ligarDefasagem((x) => { d = x; desenhar(); });
  aoMudarTema(() => desenharGraficos(meta.series[sid]));
}

iniciar();
