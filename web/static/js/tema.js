// Tema claro/escuro. Script clássico (não módulo), carregado no <head> para
// aplicar o tema salvo antes de a página aparecer.
//   automático -> segue o sistema (sem data-theme)
//   claro/escuro -> fixa data-theme="light"/"dark" na raiz
// Ao trocar, avisa as páginas com o evento "temamudou" para redesenharem os gráficos.
(function () {
  var CHAVE = "tema";
  var ORDEM = ["auto", "claro", "escuro"];
  var ROTULOS = { auto: "Automático", claro: "Claro", escuro: "Escuro" };
  var atual = "auto";
  try { atual = localStorage.getItem(CHAVE) || "auto"; } catch (e) { /* armazenamento indisponível */ }
  if (ORDEM.indexOf(atual) < 0) atual = "auto";

  function aplicar(tema) {
    var raiz = document.documentElement;
    if (tema === "claro") raiz.setAttribute("data-theme", "light");
    else if (tema === "escuro") raiz.setAttribute("data-theme", "dark");
    else raiz.removeAttribute("data-theme");
  }
  aplicar(atual);

  document.addEventListener("DOMContentLoaded", function () {
    var botao = document.getElementById("tema");
    if (!botao) return;
    function mostrar() {
      botao.setAttribute("data-tema", atual);
      botao.querySelector(".tema-rotulo").textContent = ROTULOS[atual];
      botao.setAttribute("aria-label", "Tema: " + ROTULOS[atual].toLowerCase() + ". Clique para trocar.");
    }
    mostrar();
    botao.addEventListener("click", function () {
      atual = ORDEM[(ORDEM.indexOf(atual) + 1) % ORDEM.length];
      try { localStorage.setItem(CHAVE, atual); } catch (e) { /* ignora */ }
      aplicar(atual);
      mostrar();
      document.dispatchEvent(new CustomEvent("temamudou"));
    });
  });
})();
