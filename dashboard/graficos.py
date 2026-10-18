"""Gráficos do dashboard (Plotly). Cores de dados/visualização, nunca cores de partidos."""

import pandas as pd
import plotly.graph_objects as go

from src.catalogo import Catalogo
from src.presidentes import Mandatos

AZUL = "#2a78d6"      # série principal / mandato em destaque
LARANJA = "#eb6834"   # mandato anterior (comparação)
CINZA = "#9a9993"     # demais mandatos, dados parciais
FAIXA = "rgba(128,128,128,0.10)"
DESTAQUE = "rgba(42,120,214,0.12)"


def _layout(fig: go.Figure, titulo_y: str, altura: int = 420) -> go.Figure:
    fig.update_layout(
        height=altura,
        margin=dict(t=50, b=10, l=10, r=10),
        hovermode="x unified",
        yaxis_title=titulo_y,
        xaxis_title=None,
        legend=dict(orientation="h", y=-0.12, x=0, title=None),
    )
    fig.update_xaxes(showgrid=False)
    return fig


def faixas_mandatos(fig: go.Figure, inicio: pd.Timestamp, fim: pd.Timestamp, destaque: str | None = None) -> None:
    """Sombreia o período de cada mandato e escreve o nome no topo (alternando a altura para não sobrepor)."""
    for i, m in Mandatos.tabela().iterrows():
        a, b = max(m["inicio"], inicio), min(m["fim"], fim)
        if a >= b:
            continue
        cor = DESTAQUE if m["id"] == destaque else (FAIXA if i % 2 == 0 else "rgba(0,0,0,0)")
        fig.add_vrect(x0=a, x1=b, fillcolor=cor, line_width=0, layer="below")
        fig.add_annotation(
            x=a + (b - a) / 2, y=1.0 if i % 2 == 0 else 1.06, yref="paper",
            text=m["rotulo"], showarrow=False, font=dict(size=10), yanchor="bottom",
        )


def marcas_eventos(fig: go.Figure, inicio: pd.Timestamp, fim: pd.Timestamp) -> None:
    """Linha fina em cada evento de contexto; o nome do evento aparece ao passar o mouse no marcador."""
    eventos = [(pd.Timestamp(d), nome) for d, nome in Mandatos.EVENTOS if inicio <= pd.Timestamp(d) <= fim]
    if not eventos:
        return
    for d, _ in eventos:
        fig.add_vline(x=d, line_width=1, line_color=CINZA, opacity=0.6)
    fig.add_trace(
        go.Scatter(
            x=[d for d, _ in eventos], y=[0] * len(eventos), yaxis="y2",
            mode="markers", marker=dict(symbol="triangle-up", size=10, color=CINZA),
            text=[n for _, n in eventos], hovertemplate="%{text}<extra></extra>",
            name="Eventos de contexto",
        )
    )
    fig.update_layout(yaxis2=dict(overlaying="y", range=[0, 1], visible=False, fixedrange=True))


def serie_historica(df: pd.DataFrame, serie_id: str, titulo_y: str, eventos: bool = True,
                    log: bool = False, destaque: str | None = None) -> go.Figure:
    """Linha (ou barras, para séries anuais) com os mandatos sombreados ao fundo."""
    meta = Catalogo.SERIES[serie_id]
    fig = go.Figure()
    hover = "%{customdata}: %{y:,.2f}<extra></extra>"
    if meta["frequencia"] == "anual":
        fig.add_trace(go.Bar(x=df["data_meio"], y=df["valor"], marker_color=AZUL, customdata=df["periodo_rotulo"],
                             hovertemplate=hover, name=meta["nome"], showlegend=False))
    else:
        fig.add_trace(go.Scatter(x=df["data_meio"], y=df["valor"], mode="lines", line=dict(color=AZUL, width=2),
                                 customdata=df["periodo_rotulo"], hovertemplate=hover, name=meta["nome"],
                                 showlegend=False))
    if len(df):
        ini, fim = df["data_inicio"].min(), df["data_fim"].max()
        faixas_mandatos(fig, ini, fim, destaque)
        if eventos:
            marcas_eventos(fig, ini, fim)
    if log:
        fig.update_yaxes(type="log")
    fig.update_layout(separators=",.")
    return _layout(fig, titulo_y)


def barras_mandatos(tabela: pd.DataFrame, serie_id: str, metrica: str, titulo_y: str) -> go.Figure:
    """Uma barra por mandato, em ordem cronológica; mandatos sem dados completos ficam em cinza."""
    t = tabela[tabela["serie_id"] == serie_id].dropna(subset=[metrica])
    completo = t["status"] == "completo"
    fig = go.Figure()
    for mask, nome, cor in [(completo, "Dados completos", AZUL), (~completo, "Parcial / em curso / sem herança", CINZA)]:
        parte = t[mask]
        if parte.empty:
            continue
        fig.add_trace(go.Bar(
            x=parte["rotulo"], y=parte[metrica], name=nome, marker_color=cor,
            customdata=parte["status"], hovertemplate="%{x}: %{y:,.2f}<br>%{customdata}<extra></extra>",
        ))
    fig.update_xaxes(categoryorder="array", categoryarray=Mandatos.tabela()["rotulo"].tolist(),
                     tickangle=-45, tickfont=dict(size=11), automargin=True)
    fig.update_layout(barmode="overlay", bargap=0.25, separators=",.")
    fig.add_hline(y=0, line_width=1, line_color=CINZA)
    fig = _layout(fig, titulo_y, altura=320)
    fig.update_layout(hovermode="closest", margin=dict(t=20))
    return fig


def trajetorias(traj: pd.DataFrame, destaque: str, anterior: str | None, titulo_y: str) -> go.Figure:
    """Trajetórias alinhadas pela posse: mandato escolhido em azul, anterior em laranja, demais em cinza."""
    fig = go.Figure()
    outros = [m for m in traj["mandato"].unique() if m not in (destaque, anterior)]
    for i, m in enumerate(outros + [anterior, destaque]):
        parte = traj[traj["mandato"] == m]
        if parte.empty:
            continue
        cor, largura, opac = (AZUL, 3, 1) if m == destaque else (LARANJA, 2, 1) if m == anterior else (CINZA, 1, 0.5)
        # Os demais mandatos dividem uma única entrada na legenda
        cinza = m not in (destaque, anterior)
        fig.add_trace(go.Scatter(
            x=parte["meses"], y=parte["valor"], mode="lines", opacity=opac,
            name="Demais mandatos" if cinza else m, legendgroup="outros" if cinza else m,
            showlegend=(not cinza) or i == 0,
            line=dict(color=cor, width=largura), customdata=parte["periodo_rotulo"],
            hovertemplate=f"{m} · %{{customdata}}: %{{y:,.2f}}<extra></extra>",
        ))
        if m in (destaque, anterior):
            ultimo = parte.iloc[-1]
            fig.add_annotation(x=ultimo["meses"], y=ultimo["valor"], text=m, showarrow=False,
                               xanchor="left", xshift=6, font=dict(color=cor, size=12))
    fig.add_hline(y=0, line_width=1, line_color=CINZA)
    fig.update_xaxes(title="meses desde a posse", dtick=12)
    fig.update_layout(separators=",.")
    fig = _layout(fig, titulo_y)
    fig.update_layout(hovermode="closest")
    return fig
