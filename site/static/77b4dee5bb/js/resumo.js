import { aoMudarTema, carregar, comDefasagem, esc, ligarDefasagem, mostrarErro } from "./comum.js";
import { barrasMandatos } from "./graficos.js";

const MARCA = { "completo": "", "mandato em curso": "*", "dados parciais": "*", "sem valor herdado": "†", "sem dados": "" };
const EXPLICA_MODO = {
  mudanca: "Mudança: quanto o indicador mudou entre o que o governo recebeu do anterior e o que entregou no fim. Para inflação e PIB, o total acumulado no mandato.",
  media: "Média: como o indicador ficou, em média, durante o mandato. Para inflação e PIB, quanto subiram por ano, em média.",
};

const alvoTabela = document.getElementById("placar-tabela");
// A média é a visão inicial: é a leitura mais direta para quem não é da área
const estado = { d: 0, modo: "media", grupo: null };
let meta, placar;

const metricaDe = (sid) => (estado.modo === "mudanca" ? meta.series[sid].metrica_mudanca : "media");

function indice() {
  const mapa = new Map();
  for (const e of placar[String(estado.d)]) mapa.set(`${e.s}|${e.m}`, e);
  return mapa;
}

function desenharTabela() {
  const mapa = indice();
  const cab = meta.ordem.map((sid) => {
    const m = metricaDe(sid);
    return `<th scope="col">${esc(meta.series[sid].nome)}<span class="unidade">${esc(meta.series[sid].rotulos_unidade[m])}</span></th>`;
  }).join("");
  const linhas = meta.mandatos.map((mand) => {
    const celulas = meta.ordem.map((sid) => {
      const e = mapa.get(`${sid}|${mand.id}`);
      const m = metricaDe(sid);
      const href = comDefasagem(`/checar/${mand.id}/${sid}/`, estado.d);
      if (!e || e.status === "sem dados") return `<td class="num vazio">—</td>`;
      const texto = (e.texto[m] ?? "—") + MARCA[e.status];
      const classe = e.status === "completo" ? "num" : "num parcial";
      const titulo = `${meta.series[sid].nome} · ${mand.rotulo} · ${e.status}`;
      return `<td class="${classe}"><a href="${href}" title="${esc(titulo)}">${esc(texto)}</a></td>`;
    }).join("");
    return `<tr><th scope="row">${esc(mand.rotulo)}</th>${celulas}</tr>`;
  }).join("");
  alvoTabela.innerHTML = `<table class="placar"><caption class="pular">Indicadores por mandato</caption>
    <thead><tr><th scope="col">Mandato</th>${cab}</tr></thead><tbody>${linhas}</tbody></table>`;
}

function desenharGraficos() {
  const alvo = document.getElementById("graficos");
  // Pesquisas encerradas (como a PME, até 2016) ficam só na tabela: não ganham gráfico
  const doGrupo = meta.ordem.filter((sid) => meta.series[sid].grupo === estado.grupo);
  const sids = doGrupo.filter((sid) => !meta.series[sid].encerrada);
  const encerradas = doGrupo.filter((sid) => meta.series[sid].encerrada);
  const aviso = encerradas.length
    ? `<p class="nota" style="grid-column: 1 / -1; margin: 0">${encerradas.map((sid) => esc(meta.series[sid].nome)).join(", ")}:
       pesquisa encerrada, sem gráfico aqui. Os valores continuam na tabela acima e nas páginas de checagem.</p>`
    : "";
  alvo.innerHTML = aviso + sids.map((sid) => {
    const s = meta.series[sid];
    const m = metricaDe(sid);
    const criterio = s.direcao === "menor" ? "Destaque para o menor valor" : "Destaque para o maior valor";
    const contexto = !s.direcao ? `<p class="nota">Série de contexto, sem critério de destaque.</p>`
      : m === "media" && !s.media_comparavel ? `<p class="nota">A média não serve para comparar governos (${esc(s.motivo_media)}): use “Mudança no mandato”.</p>`
      : [s.ressalva_direcao ? `<p class="nota">${criterio}, com ressalva: ${esc(s.ressalva_direcao)}.</p>` : "",
         m === "media" && s.aviso_media ? `<p class="nota">Atenção: ${esc(s.aviso_media)}. Confira também a “Mudança no mandato”.</p>` : ""].join("");
    return `<section class="cartao"><h3>${esc(s.nome)}</h3>
      <p class="nota">${esc(s.metricas[m])}, em ${esc(s.unidades_metrica[m])}</p>
      <div class="grafico" id="barra-${sid}" style="min-height:300px" role="img" aria-label="${esc(s.nome)} por mandato"></div>
      <p class="nota" id="nota-log-${sid}" hidden>Escala logarítmica: cada linha de grade vale 10 vezes a anterior, e a altura da barra
        mostra a ordem de grandeza, não a proporção entre os valores. Sem ela, a hiperinflação antes do Plano Real
        esconderia as diferenças entre os governos seguintes. Passe o mouse para ver cada valor.</p>${contexto}</section>`;
  }).join("");
  const entradas = placar[String(estado.d)];
  for (const sid of sids) {
    const m = metricaDe(sid);
    const log = barrasMandatos(document.getElementById(`barra-${sid}`), entradas.filter((e) => e.s === sid), m,
                               meta.mandatos, meta.series[sid].rotulos_unidade[m]);
    document.getElementById(`nota-log-${sid}`).hidden = !log;
  }
}

function desenharGrupos() {
  const alvo = document.getElementById("grupos");
  alvo.innerHTML = meta.grupos.map((g) =>
    `<button type="button" role="tab" aria-selected="${g === estado.grupo}" data-grupo="${esc(g)}">${esc(g)}</button>`).join("");
  alvo.querySelectorAll("button").forEach((b) => b.addEventListener("click", () => {
    estado.grupo = b.dataset.grupo;
    desenharGrupos();
    desenharGraficos();
  }));
}

function desenharTudo() {
  document.getElementById("explica-modo").textContent = EXPLICA_MODO[estado.modo];
  desenharTabela();
  desenharGraficos();
}

async function iniciar() {
  try {
    [meta, placar] = await Promise.all([carregar("meta.json"), carregar("resumo.json")]);
  } catch (erro) {
    mostrarErro(alvoTabela, erro);
    return;
  }
  estado.grupo = meta.grupos[0];
  // Ao recarregar, o navegador pode restaurar o botão marcado antes: o estado parte dele
  estado.modo = document.querySelector('input[name="modo"]:checked')?.value ?? "media";
  desenharGrupos();
  document.querySelectorAll('input[name="modo"]').forEach((r) => r.addEventListener("change", () => {
    estado.modo = r.value;
    desenharTudo();
  }));
  ligarDefasagem((d) => { estado.d = d; desenharTudo(); });
  aoMudarTema(desenharGraficos);
}

iniciar();
