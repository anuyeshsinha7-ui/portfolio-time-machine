"""Plotly figures (no Streamlit) in the project's one colour system:
A = warm coral, B = cool blue, Nifty 50 = grey; crisis shading red, calm shading green, always labelled."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from . import config
from .fmt import inr_short

A, B, N = config.COLOR_A, config.COLOR_B, config.COLOR_NIFTY
CRISIS, CALM = config.COLOR_CRISIS, config.COLOR_CALM
COL = {"A": A, "B": B, "Nifty 50": N}


def _base(fig: go.Figure, height=380, title=None, yfmt=None, xfmt=None) -> go.Figure:
    fig.update_layout(height=height, margin=dict(l=8, r=8, t=46 if title else 10, b=8),
                      title=dict(text=title or "", font=dict(size=14)),
                      legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0, font=dict(size=11)),
                      font=dict(size=12, family="Source Sans Pro, Helvetica, Arial", color="#C9CFDB"), plot_bgcolor="rgba(0,0,0,0)",
                      paper_bgcolor="rgba(0,0,0,0)", hoverlabel=dict(bgcolor="#1E2638", font=dict(color="#E6E9EF")))
    fig.update_xaxes(gridcolor="#263043", zeroline=False, tickformat=xfmt)
    fig.update_yaxes(gridcolor="#263043", zeroline=False, tickformat=yfmt)
    return fig


def replay(dates, a, b, n, amount_a, amount_b, title=None) -> go.Figure:
    """₹ path of buy-and-hold A, B and the Nifty 50 from the client's amount."""
    fig = go.Figure()
    for name, path, amt, col in (("Portfolio A", a, amount_a, A), ("Portfolio B", b, amount_b, B),
                                 ("Nifty 50", n, (amount_a + amount_b) / 2, N)):
        v = np.asarray(path) * amt
        fig.add_trace(go.Scatter(x=dates, y=v, name=name, line=dict(color=col, width=2.4 if name != "Nifty 50" else 1.6,
                                                                       dash=None if name != "Nifty 50" else "dot"),
                                 hovertemplate="%{x|%d %b %Y}: ₹%{y:,.0f}<extra>" + name + "</extra>"))
        i = int(np.argmin(v))
        fig.add_trace(go.Scatter(x=[dates[i]], y=[v[i]], mode="markers+text", marker=dict(color=col, size=8),
                                 text=[f"low {inr_short(v[i])}"], textposition="bottom center", showlegend=False,
                                 textfont=dict(color=col, size=11), hoverinfo="skip"))
    fig.add_hline(y=amount_a, line=dict(color="#6B7690", width=1, dash="dash"))
    return _base(fig, 380, title, yfmt=",.0f")


def frontier(p: dict, regimes: list[tuple] | None = None, title=None, show_cloud=True, show_stocks=True) -> go.Figure:
    """Current efficient frontier with the random cloud, individual stocks, minimum variance, max Sharpe and the
    chosen point; optional regime frontiers [(name, colour, frontier dict, today's (vol, ret), optimal (vol, ret))]."""
    fig = go.Figure()
    col = A if p["name"] == "A" else B
    if show_cloud and p.get("cloud"):
        c = p["cloud"]
        fig.add_trace(go.Scattergl(x=c["vol"], y=c["ret"], mode="markers", name="5,000 random portfolios" if len(c["vol"]) > 2500 else "Random portfolios",
                                   marker=dict(size=3, color="#3A4560", opacity=.55), hoverinfo="skip"))
    fr = p["frontier"]
    fig.add_trace(go.Scatter(x=fr["vols"], y=fr["rets"], mode="lines", name="Efficient frontier (today)",
                             line=dict(color=col, width=3)))
    if show_stocks:
        syms = p["symbols"]
        fig.add_trace(go.Scatter(x=[p["vol_i"][s] for s in syms], y=[p["mu"][s] for s in syms], mode="markers+text", text=syms,
                                 textposition="top center", textfont=dict(size=9, color="#9AA3B5"), name="Individual stocks",
                                 marker=dict(size=7, color="#161D2C", line=dict(color="#9AA3B5", width=1.2))))
    mv = fr["minvar"]
    fig.add_trace(go.Scatter(x=[mv["vol"]], y=[mv["ret"]], mode="markers", name="Minimum variance",
                             marker=dict(symbol="diamond", size=12, color="#E6E9EF")))
    fig.add_trace(go.Scatter(x=[p["expected_vol"]], y=[p["expected_return"]], mode="markers",
                             name=f"Chosen: {'maximum Sharpe' if p['objective'] == 'max_sharpe' else 'minimum variance'}",
                             marker=dict(symbol="star", size=17, color=col, line=dict(color="#E6E9EF", width=1))))
    for name, rc, rfr, today, opt in regimes or []:
        fig.add_trace(go.Scatter(x=rfr["vols"], y=rfr["rets"], mode="lines", name=f"Frontier — {name}",
                                 line=dict(color=rc, width=2, dash="dash")))
        fig.add_trace(go.Scatter(x=[today[0]], y=[today[1]], mode="markers", name=f"Today's weights in {name}",
                                 marker=dict(symbol="x", size=12, color=rc)))
        fig.add_trace(go.Scatter(x=[opt[0]], y=[opt[1]], mode="markers", name=f"Optimal in {name}",
                                 marker=dict(symbol="star-open", size=14, color=rc, line=dict(width=2))))
    fig.update_xaxes(title="Volatility (annual)")
    fig.update_yaxes(title="Expected return (annual)")
    return _base(fig, 460, title, yfmt=".0%", xfmt=".0%")


def returns_hist(r, var, es, colour, name, conf) -> go.Figure:
    r = np.asarray(r)
    fig = go.Figure(go.Histogram(x=r, nbinsx=50, marker=dict(color=colour, opacity=.75), name=f"Daily returns — {name}",
                                 hovertemplate="%{x:.1%}: %{y} days<extra></extra>"))
    fig.add_vline(x=-var, line=dict(color="#E6E9EF", width=2), annotation_text=f"VaR {conf:.0%}: −{var:.1%}",
                  annotation_position="top left", annotation_font_size=11)
    fig.add_vline(x=-es, line=dict(color=CRISIS, width=2, dash="dash"), annotation_text=f"ES: −{es:.1%}",
                  annotation_position="bottom left", annotation_font_size=11)
    fig.update_xaxes(title="Daily return")
    return _base(fig, 280, None, xfmt=".0%")


def breach_timeline(dates, r, var, colour, name) -> go.Figure:
    r = np.asarray(r)
    hit = r < -var
    fig = go.Figure()
    fig.add_trace(go.Bar(x=dates, y=r, marker=dict(color=np.where(hit, CRISIS, "#3A4560")), name="Daily return",
                         hovertemplate="%{x|%d %b %Y}: %{y:.1%}<extra></extra>"))
    fig.add_hline(y=-var, line=dict(color="#E6E9EF", dash="dash"), annotation_text=f"VaR line −{var:.1%}", annotation_font_size=11)
    fig.update_layout(showlegend=False)
    return _base(fig, 240, f"Portfolio {name}: red bars breach the VaR line", yfmt=".0%")


def weights_bars(table: pd.DataFrame, title=None) -> go.Figure:
    """table: index = stocks, columns = regimes → grouped horizontal bars."""
    fig = go.Figure()
    palette = {"Today": "#E6E9EF", "Current": "#E6E9EF", "Crisis": CRISIS, "Calm": CALM, "Equal": "#6B7690"}
    for c in table.columns:
        fig.add_trace(go.Bar(y=table.index, x=table[c], name=c, orientation="h", marker=dict(color=palette.get(c, "#8792A8")),
                             hovertemplate="%{y}: %{x:.1%}<extra>" + c + "</extra>"))
    fig.update_layout(barmode="group", yaxis=dict(autorange="reversed"))
    return _base(fig, max(300, 28 * len(table) * max(1, len(table.columns)) // 2 + 120), title, xfmt=".0%")


def industry_bars(d: dict[str, dict], title=None) -> go.Figure:
    """d: {label: {industry: weight}} → stacked horizontal bars, one per label."""
    inds = sorted({i for v in d.values() for i in v})
    pal = ["#E8735A", "#3B7DD8", "#2E9E5B", "#B45AC9", "#E0A33A", "#4BB5C1", "#8A8F98", "#D64545", "#6C7AE0", "#9C6B3E",
           "#5FA35F", "#C2577A"]
    fig = go.Figure()
    for k, ind in enumerate(inds):
        fig.add_trace(go.Bar(y=list(d), x=[d[l].get(ind, 0) for l in d], name=ind, orientation="h",
                             marker=dict(color=pal[k % len(pal)]), hovertemplate="%{y}: %{x:.1%}<extra>" + ind + "</extra>"))
    fig.update_layout(barmode="stack", yaxis=dict(autorange="reversed"), legend=dict(font=dict(size=10)))
    return _base(fig, 150 + 34 * len(d), title, xfmt=".0%")


def beta_vol_scatter(t: pd.DataFrame, vol_median: float, a: list[str], b: list[str], highlight: str | None = None) -> go.Figure:
    fig = go.Figure()
    other = t[~t.index.isin(a + b)]
    fig.add_trace(go.Scatter(x=other["volatility"], y=other["beta"], mode="markers", name="Other stocks",
                             marker=dict(size=6, color="#3A4560"), text=other.index,
                             hovertemplate="%{text}: β %{y:.2f}, σ %{x:.0%}<extra></extra>"))
    for name, syms, col in (("Portfolio A", a, A), ("Portfolio B", b, B)):
        s = t[t.index.isin(syms)]
        fig.add_trace(go.Scatter(x=s["volatility"], y=s["beta"], mode="markers+text", name=name, text=s.index,
                                 textposition="top center", textfont=dict(size=9, color=col),
                                 marker=dict(size=9, color=col, line=dict(color="#0B0F17", width=1)),
                                 hovertemplate="%{text}: β %{y:.2f}, σ %{x:.0%}<extra></extra>"))
    if highlight and highlight in t.index:
        r = t.loc[highlight]
        fig.add_trace(go.Scatter(x=[r["volatility"]], y=[r["beta"]], mode="markers", name=highlight,
                                 marker=dict(size=18, color="rgba(0,0,0,0)", line=dict(color="#E6E9EF", width=2))))
    fig.add_hline(y=1.0, line=dict(color="#9AA3B5", dash="dash"))
    fig.add_vline(x=vol_median, line=dict(color="#9AA3B5", dash="dash"))
    xmax, ymax = float(t["volatility"].max()) * 1.02, float(t["beta"].max()) * 1.02
    fig.add_annotation(x=xmax, y=ymax, text="HIGH RISK<br>β ≥ 1 and σ ≥ median", showarrow=False, xanchor="right", yanchor="top",
                       font=dict(color=A, size=11))
    fig.add_annotation(x=float(t["volatility"].min()), y=float(t["beta"].min()), text="LOW RISK<br>β < 1 and σ < median",
                       showarrow=False, xanchor="left", yanchor="bottom", font=dict(color=B, size=11))
    fig.update_xaxes(title="Volatility σ (annual, 3 years)")
    fig.update_yaxes(title="Beta β vs Nifty 50 (3 years)")
    return _base(fig, 460, None, xfmt=".0%")


def corr_heatmap(corr, labels, title, colour) -> go.Figure:
    fig = go.Figure(go.Heatmap(z=corr, x=labels, y=labels, zmin=-1, zmax=1, colorscale=[[0, "#3B7DD8"], [0.5, "#161D2C"], [1, colour]],
                               text=np.round(np.asarray(corr), 2), texttemplate="%{text}", textfont=dict(size=8),
                               hovertemplate="%{y} × %{x}: %{z:.2f}<extra></extra>", showscale=False))
    fig.update_layout(yaxis=dict(autorange="reversed"))
    return _base(fig, 360, title)


def ratio_hist(draws, lo, hi, point) -> go.Figure:
    fig = go.Figure(go.Histogram(x=draws, nbinsx=40, marker=dict(color="#8792A8", opacity=.8), name="Bootstrap σA/σB"))
    for x, txt, c in ((lo, f"2.5%: {lo:.2f}", "#E6E9EF"), (hi, f"97.5%: {hi:.2f}", "#E6E9EF"), (1.0, "1 = equal risk", CRISIS)):
        fig.add_vline(x=x, line=dict(color=c, dash="dash" if x != 1 else "solid"), annotation_text=txt, annotation_font_size=11)
    fig.add_vline(x=point, line=dict(color=A, width=3), annotation_text=f"observed {point:.2f}", annotation_position="top left")
    fig.update_xaxes(title="Volatility ratio σA / σB")
    return _base(fig, 280, None)


def nifty_history(close: pd.Series, events: list[dict], vix: pd.Series | None = None, current=None) -> go.Figure:
    """Full-history Nifty 50 with every catalogue event shaded and labelled; rolling 12-month volatility; drawdown."""
    rows = 4 if vix is not None else 3
    fig = make_subplots(rows=rows, cols=1, shared_xaxes=True, vertical_spacing=0.04,
                        row_heights=[0.5, 0.17, 0.17, 0.16][:rows],
                        subplot_titles=("Nifty 50 (log scale) with test windows", "Rolling 12-month volatility", "Drawdown from peak",
                                        "India VIX")[:rows])
    fig.add_trace(go.Scatter(x=close.index, y=close, line=dict(color="#E6E9EF", width=1.2), name="Nifty 50",
                             hovertemplate="%{x|%d %b %Y}: %{y:,.0f}<extra></extra>"), row=1, col=1)
    r = close.pct_change()
    rv = r.rolling(252).std() * np.sqrt(252)
    fig.add_trace(go.Scatter(x=rv.index, y=rv, line=dict(color="#8792A8", width=1.2), name="12-month volatility",
                             hovertemplate="%{x|%b %Y}: %{y:.0%}<extra></extra>"), row=2, col=1)
    dd = close / close.cummax() - 1
    fig.add_trace(go.Scatter(x=dd.index, y=dd, fill="tozeroy", line=dict(color=CRISIS, width=1), name="Drawdown",
                             fillcolor="rgba(214,69,69,.18)", hovertemplate="%{x|%b %Y}: %{y:.0%}<extra></extra>"), row=3, col=1)
    if vix is not None:
        fig.add_trace(go.Scatter(x=vix.index, y=vix, line=dict(color="#B45AC9", width=1), name="India VIX",
                                 hovertemplate="%{x|%b %Y}: %{y:.1f}<extra></extra>"), row=4, col=1)
    for ev in events:
        w = ev["windows"]["standard"]
        if not w:
            continue
        fill = config.COLOR_CRISIS_FILL if ev["type"] == "crisis" else config.COLOR_CALM_FILL
        for row in range(1, rows + 1):
            fig.add_vrect(x0=w[0], x1=w[1], fillcolor=fill, line_width=0, row=row, col=1)
        fig.add_annotation(x=w[0], y=1, yref="y domain", text=ev.get("short", ev["name"]), showarrow=False, xanchor="left",
                           yanchor="top", textangle=-90, font=dict(size=9, color=CRISIS if ev["type"] == "crisis" else CALM),
                           row=1, col=1)
    if current:
        for row in range(1, rows + 1):
            fig.add_vrect(x0=current[0], x1=current[1], fillcolor="rgba(59,125,216,.12)", line_width=0, row=row, col=1)
        fig.add_annotation(x=current[0], y=1, yref="y domain", text="Current", showarrow=False, xanchor="left", yanchor="top",
                           textangle=-90, font=dict(size=9, color=B), row=1, col=1)
    fig.update_yaxes(type="log", row=1, col=1)
    fig.update_yaxes(tickformat=".0%", row=2, col=1)
    fig.update_yaxes(tickformat=".0%", row=3, col=1)
    fig.update_layout(showlegend=False)
    return _base(fig, 640 if rows == 4 else 560, None)


def scoreboard_heatmap(board: list[dict], amount_a: float, amount_b: float) -> go.Figure:
    names = [r["event"] for r in board]
    metrics = [("ES 99% (1 day)", "es99"), ("Volatility", "vol"), ("Max drawdown", "mdd"), ("Worst ₹ fall", "fall")]
    z, text, x = [], [], []
    for lab, key in metrics:
        for p, amt in (("A", amount_a), ("B", amount_b)):
            x.append(f"{lab} — {p}")
            col = [r[f"{key}_{p}"] for r in board]
            z.append(col)
            text.append([inr_short(v * amt) if key == "fall" else f"{v:.1%}" for v in col])
    z = np.array(z).T
    zn = (z - z.min(axis=0)) / np.where(np.ptp(z, axis=0) == 0, 1, np.ptp(z, axis=0))
    fig = go.Figure(go.Heatmap(z=zn, x=x, y=names, text=np.array(text).T, texttemplate="%{text}", textfont=dict(size=10),
                               colorscale=[[0, "#15281E"], [0.5, "#3A3016"], [1, "#5A2A2E"]], showscale=False,
                               hovertemplate="%{y}<br>%{x}: %{text}<extra></extra>"))
    fig.update_layout(yaxis=dict(autorange="reversed"), xaxis=dict(side="top", tickangle=-30))
    return _base(fig, 120 + 34 * len(board), None)


def bootstrap_bands(symbols, base, lo, hi, regime_w: dict, title=None) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Bar(y=symbols, x=[hi[s] - lo[s] for s in symbols], base=[lo[s] for s in symbols], orientation="h",
                         marker=dict(color="rgba(122,131,148,.35)"), name="90% noise band (bootstrap)",
                         hovertemplate="%{y}: %{base:.1%} – %{x:.1%}<extra></extra>"))
    fig.add_trace(go.Scatter(y=symbols, x=[base[s] for s in symbols], mode="markers", name="Today",
                             marker=dict(symbol="line-ns", size=16, line=dict(width=3, color="#E6E9EF"))))
    for name, w, col in regime_w.values() if isinstance(regime_w, dict) else regime_w:
        fig.add_trace(go.Scatter(y=symbols, x=[w[s] for s in symbols], mode="markers", name=name,
                                 marker=dict(size=10, color=col, symbol="diamond")))
    fig.update_layout(yaxis=dict(autorange="reversed"))
    fig.update_xaxes(title="Weight")
    return _base(fig, 120 + 30 * len(symbols), title, xfmt=".0%")


def turnover_hist(noise, p95, marks: list[tuple]) -> go.Figure:
    fig = go.Figure(go.Histogram(x=noise, nbinsx=30, marker=dict(color="#3A4560"), name="Turnover from noise alone"))
    fig.add_vline(x=p95, line=dict(color="#E6E9EF", dash="dash"), annotation_text=f"95th pct {p95:.0%}", annotation_font_size=11)
    for name, v, col in marks:
        fig.add_vline(x=v, line=dict(color=col, width=3), annotation_text=f"{name} {v:.0%}", annotation_position="top left",
                      annotation_font_size=11)
    fig.update_xaxes(title="Turnover = ½ Σ |Δw|")
    return _base(fig, 260, None, xfmt=".0%")
