// Página /checar/: começa sem mandato escolhido e no primeiro indicador; leva à página da checagem
const mandato = document.getElementById("sel-mandato");
const serie = document.getElementById("sel-serie");
const aviso = document.getElementById("aviso-escolha");

// Ao voltar para a página, o navegador pode restaurar escolhas antigas: recomeça do zero
window.addEventListener("pageshow", () => {
  mandato.value = "";
  serie.selectedIndex = 0;
  aviso.hidden = true;
});

mandato.addEventListener("change", () => { aviso.hidden = true; });

document.getElementById("escolha").addEventListener("submit", (ev) => {
  ev.preventDefault();
  if (!mandato.value) {
    aviso.hidden = false;
    mandato.focus();
    return;
  }
  location.href = `/checar/${mandato.value}/${serie.value}/`;
});
