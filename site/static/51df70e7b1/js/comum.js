// Funções compartilhadas pelas páginas. Nenhuma conta econômica é feita aqui:
// todos os números chegam prontos dos arquivos gerados por src/publicar.py.

export const DEFASAGENS = [0, 3, 6, 12];

const cache = new Map();

/** Lê um arquivo de /dados (com cache, para não baixar duas vezes). */
export function carregar(caminho) {
  if (!cache.has(caminho)) {
    cache.set(
      caminho,
      fetch(`/dados/${caminho}`).then((r) => {
        if (!r.ok) throw new Error(`Não foi possível ler ${caminho} (${r.status})`);
        return r.json();
      }),
    );
  }
  return cache.get(caminho);
}

// ---------------------------------------------------------------- defasagem
/**
 * Defasagem atual, lida só do parâmetro ?d= da URL (padrão 0). Não é guardada
 * no navegador de propósito: um link compartilhado mostra sempre os mesmos números.
 */
export function defasagem() {
  const q = new URL(location.href).searchParams.get("d");
  return q !== null && DEFASAGENS.includes(Number(q)) ? Number(q) : 0;
}

function definirDefasagem(d) {
  const url = new URL(location.href);
  if (d) url.searchParams.set("d", d); else url.searchParams.delete("d");
  history.replaceState(null, "", url);
}

/** Liga o <select id="defasagem"> ao estado e chama `aoMudar(d)` agora e a cada mudança. */
export function ligarDefasagem(aoMudar) {
  const sel = document.getElementById("defasagem");
  const aviso = document.getElementById("aviso-defasagem");
  const aplicar = (d) => {
    if (aviso) {
      aviso.hidden = d === 0;
      aviso.textContent = `Defasagem de ${d} meses ativa: cada dado é atribuído a quem governava ${d} meses antes.`;
    }
    aoMudar(d);
  };
  const inicial = defasagem();
  if (sel) {
    sel.value = String(inicial);
    sel.addEventListener("change", () => {
      const d = Number(sel.value);
      definirDefasagem(d);
      aplicar(d);
    });
  }
  aplicar(inicial);
}

/** Acrescenta ?d= a um link interno quando há defasagem, para o link compartilhado reproduzir a mesma visão. */
export function comDefasagem(href, d) {
  return d ? `${href}?d=${d}` : href;
}

// ---------------------------------------------------------------- texto e HTML
export function esc(texto) {
  return String(texto ?? "")
    .replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;").replaceAll("'", "&#39;");
}

/** Converte o **negrito** dos textos gerados em Python em <strong>, escapando o resto. */
export function negrito(texto) {
  return esc(texto).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
}

const numero = (casas) => new Intl.NumberFormat("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas });

export function fmtNum(v, casas = 2) {
  return v === null || v === undefined || Number.isNaN(v) ? "—" : numero(casas).format(v);
}

/** "2016-05-12" -> "12/05/2016" */
export function fmtData(iso) {
  if (!iso) return "—";
  const [a, m, d] = iso.slice(0, 10).split("-");
  return `${d}/${m}/${a}`;
}

// ---------------------------------------------------------------- downloads
/** Gera e baixa um CSV no padrão brasileiro (separador ; e vírgula decimal). */
export function baixarCSV(nomeArquivo, colunas, linhas) {
  const celula = (v) => {
    if (typeof v === "number") return String(v).replace(".", ",");
    const s = String(v ?? "");
    return /[;"\n]/.test(s) ? `"${s.replaceAll('"', '""')}"` : s;
  };
  const corpo = [colunas.map((c) => c.titulo), ...linhas.map((l) => colunas.map((c) => l[c.chave]))]
    .map((l) => l.map(celula).join(";"))
    .join("\r\n");
  const blob = new Blob(["﻿" + corpo], { type: "text/csv;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = nomeArquivo;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

/** Mostra uma mensagem de erro no lugar do conteúdo quando os dados não carregam. */
export function mostrarErro(alvo, erro) {
  console.error(erro);
  alvo.innerHTML = `<p class="alerta alerta-aviso">Não foi possível carregar os dados. Recarregue a página. (${esc(erro.message)})</p>`;
}

/**
 * Executa `fn` de novo quando o tema muda — pelo botão de tema (evento "temamudou",
 * de tema.js) ou pelo sistema operacional —, porque os gráficos leem as cores do CSS.
 */
export function aoMudarTema(fn) {
  document.addEventListener("temamudou", fn);
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", fn);
}
