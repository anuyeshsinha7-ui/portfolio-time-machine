"""Plotly figures (no Streamlit) in the project's one colour system:
A = warm coral, B = cool blue, Nifty 50 = grey; crisis shading red, calm shading green, always labelled."""
from __future__ import annotations

import textwrap

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from . import config
from .fmt import inr_short

A, B, C, N = config.COLOR_A, config.COLOR_B, config.COLOR_C, config.COLOR_NIFTY
COLS = {"A": A, "B": B, "C": C}
CHOSEN = {"max_sharpe": "maximum Sharpe", "min_variance": "minimum variance", "max_return": "maximum return"}
CRISIS, CALM = config.COLOR_CRISIS, config.COLOR_CALM
COL = {"A": A, "B": B, "Nifty 50": N}
# one clearly different colour (and dash) per tested period, used by every period chart
PERIOD_PAL = [CRISIS, CALM, "#B45AC9", "#E0A33A", "#4BB5C1", "#6C7AE0", "#C2577A", "#9C6B3E", "#5FA35F", "#D9D96B"]
DASHES = ["dash", "dot", "dashdot", "longdash", "longdashdot"]


def _base(fig: go.Figure, height=380, title=None, yfmt=None, xfmt=None) -> go.Figure:
    # A title above a multi-row legend used to be drawn on top of it. When there is a legend, the title becomes the
    # legend's own heading, so the space Plotly reserves for the legend always includes it. Side "top", not "top left":
    # "top left" starts the items after the title's width, which pushed long legends off the right edge.
    in_legend = bool(title) and fig.layout.showlegend is not False and sum(t.showlegend is not False for t in fig.data) > 1
    fig.update_layout(height=height, margin=dict(l=8, r=8, t=10 if in_legend or not title else 46, b=8),
                      title=dict(text="" if in_legend else (title or ""), font=dict(size=14)),
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, font=dict(size=11),
                                  title=dict(text=f"<b>{title}</b><br>" if in_legend else "", side="top",
                                             font=dict(size=13, color="#E6E9EF"))),
                      font=dict(size=12, family="Inter, -apple-system, Helvetica, Arial", color="#C9CFDB"), plot_bgcolor="rgba(0,0,0,0)",
                      paper_bgcolor="rgba(0,0,0,0)", hoverlabel=dict(bgcolor="#1E2638", font=dict(color="#E6E9EF")))
    fig.update_xaxes(gridcolor="#263043", zeroline=False, tickformat=xfmt)
    fig.update_yaxes(gridcolor="#263043", zeroline=False, tickformat=yfmt)
    return fig


def replay(dates, a, b, n, amount_a, amount_b, title=None, c=None, amount_c=None) -> go.Figure:
    """₹ path of buy-and-hold A, B (and C) and the Nifty 50 from the client's amount."""
    fig = go.Figure()
    lines = [("Portfolio A", a, amount_a, A), ("Portfolio B", b, amount_b, B)]
    if c is not None:
        lines.append(("Portfolio C", c, amount_c, C))
    for name, path, amt, col in lines + [("Nifty 50", n, (amount_a + amount_b) / 2, N)]:
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
    col = COLS[p["name"]]
    if show_cloud and p.get("cloud"):
        c = p["cloud"]
        fig.add_trace(go.Scattergl(x=c["vol"], y=c["ret"], mode="markers", name="5,000 random portfolios" if len(c["vol"]) > 2500 else "Random portfolios",
                                   marker=dict(size=3, color="#3A4560", opacity=.55), hoverinfo="skip"))
    fr = p["frontier"]
    fig.add_trace(go.Scatter(x=fr["vols"], y=fr["rets"], mode="lines", name="Best mixes today (frontier)",
                             line=dict(color=col, width=3),
                             hovertemplate="Today's frontier<br>return %{y:.1%} · volatility %{x:.1%}<extra></extra>"))
    if show_stocks:
        syms = sorted(p["symbols"], key=lambda s: (p["vol_i"][s], p["mu"][s]))
        pos = ["top center", "bottom center", "middle right", "middle left"]  # alternate so neighbouring labels don't collide
        fig.add_trace(go.Scatter(x=[p["vol_i"][s] for s in syms], y=[p["mu"][s] for s in syms], mode="markers+text", text=syms,
                                 textposition=[pos[i % 4] for i in range(len(syms))], textfont=dict(size=9, color="#9AA3B5"),
                                 name="Individual stocks", marker=dict(size=7, color="#161D2C", line=dict(color="#9AA3B5", width=1.2)),
                                 hovertemplate="%{text}<br>return %{y:.1%} · volatility %{x:.1%}<extra></extra>"))
    mv = fr["minvar"]
    top = ", ".join(f"{s} {w:.0%}" for s, w in sorted(p["weights"].items(), key=lambda x: -x[1])[:3])
    fig.add_trace(go.Scatter(x=[mv["vol"]], y=[mv["ret"]], mode="markers", name="Least risky mix",
                             marker=dict(symbol="diamond", size=12, color="#E6E9EF"),
                             hovertemplate="Least risky mix<br>return %{y:.1%} · volatility %{x:.1%}<extra></extra>"))
    fig.add_trace(go.Scatter(x=[p["expected_vol"]], y=[p["expected_return"]], mode="markers",
                             name=f"Chosen: {CHOSEN[p['objective']]}",
                             marker=dict(symbol="star", size=17, color=col, line=dict(color="#E6E9EF", width=1)),
                             hovertemplate=f"Today's weights ({CHOSEN[p['objective']]})<br>return %{{y:.1%}} · volatility %{{x:.1%}}"
                                           f"<br>largest: {top}<extra></extra>"))
    for i, (name, rc, rfr, today, opt, *rest) in enumerate(regimes or []):
        opt_top = rest[0] if rest else ""
        fig.add_trace(go.Scatter(x=rfr["vols"], y=rfr["rets"], mode="lines", name=f"Frontier — {name}", legendgroup=name,
                                 line=dict(color=rc, width=2, dash=DASHES[i % len(DASHES)]),
                                 hovertemplate=f"{name} frontier<br>return %{{y:.1%}} · volatility %{{x:.1%}}<extra></extra>"))
        fig.add_trace(go.Scatter(x=[today[0]], y=[today[1]], mode="markers", name=f"Today's weights in {name}", legendgroup=name,
                                 marker=dict(symbol="x", size=12, color=rc), showlegend=False,
                                 hovertemplate=f"Today's weights during {name}<br>return %{{y:.1%}} · volatility %{{x:.1%}}<extra></extra>"))
        fig.add_trace(go.Scatter(x=[opt[0]], y=[opt[1]], mode="markers", name=f"Optimal in {name}", legendgroup=name,
                                 marker=dict(symbol="star-open", size=14, color=rc, line=dict(width=2)), showlegend=False,
                                 hovertemplate=f"Best mix for {name}<br>return %{{y:.1%}} · volatility %{{x:.1%}}"
                                               + (f"<br>largest: {opt_top}" if opt_top else "") + "<extra></extra>"))
    fig.update_xaxes(title="Volatility (annual)")
    fig.update_yaxes(title="Expected return (annual)")
    return _base(fig, 460, title, yfmt=".0%", xfmt=".0%")


def returns_hist(r, var, es, colour, name, conf) -> go.Figure:
    r = np.asarray(r)
    fig = go.Figure(go.Histogram(x=r, nbinsx=50, marker=dict(color=colour, opacity=.75), name=f"Daily returns — {name}",
                                 hovertemplate="%{x:.1%}: %{y} days<extra></extra>"))
    fig.add_vline(x=-var, line=dict(color="#E6E9EF", width=2), annotation_text=f"VaR {conf:.0%} = {var:.1%} loss",
                  annotation_position="top left", annotation_font_size=11)
    fig.add_vline(x=-es, line=dict(color=CRISIS, width=2, dash="dash"), annotation_text=f"ES = {es:.1%} loss",
                  annotation_position="bottom left", annotation_font_size=11)
    fig.update_xaxes(title="Daily return")
    return _base(fig, 280, None, xfmt=".0%")


def breach_timeline(dates, r, var, colour, name) -> go.Figure:
    r = np.asarray(r)
    hit = r < -var
    fig = go.Figure()
    fig.add_trace(go.Bar(x=dates, y=r, marker=dict(color=np.where(hit, CRISIS, "#3A4560")), name="Daily return",
                         hovertemplate="%{x|%d %b %Y}: %{y:.1%}<extra></extra>"))
    fig.add_hline(y=-var, line=dict(color="#E6E9EF", dash="dash"), annotation_text=f"VaR = {var:.1%} loss", annotation_font_size=11)
    fig.update_layout(showlegend=False)
    return _base(fig, 240, f"Portfolio {name}: red bars breach the VaR line", yfmt=".0%")


def weights_bars(table: pd.DataFrame, title=None) -> go.Figure:
    """table: index = stocks, columns = regimes → grouped horizontal bars."""
    fig = go.Figure()
    others = iter(PERIOD_PAL * 3)
    for c in table.columns:
        colour = "#E6E9EF" if c in ("Today", "Current") else next(others)
        fig.add_trace(go.Bar(y=table.index, x=table[c], name=c, orientation="h", marker=dict(color=colour),
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
    fig = go.Figure(go.Histogram(x=draws, nbinsx=40, marker=dict(color="#8792A8", opacity=.8), name="Reshuffled data"))
    for x, txt, c in ((lo, f"2.5%: {lo:.2f}", "#E6E9EF"), (hi, f"97.5%: {hi:.2f}", "#E6E9EF"), (1.0, "1 = equal risk", CRISIS)):
        fig.add_vline(x=x, line=dict(color=c, dash="dash" if x != 1 else "solid"), annotation_text=txt, annotation_font_size=11)
    fig.add_vline(x=point, line=dict(color=A, width=3), annotation_text=f"actual {point:.2f}", annotation_position="top left")
    fig.update_xaxes(title="A's volatility ÷ B's (σA / σB)")
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
    fig.add_trace(go.Scatter(x=dd.index, y=dd, fill="tozeroy", line=dict(color=CRISIS, width=1), name="Fall from last high",
                             fillcolor="rgba(214,69,69,.18)", hovertemplate="%{x|%b %Y}: %{y:.0%}<extra></extra>"), row=3, col=1)
    if vix is not None:
        fig.add_trace(go.Scatter(x=vix.index, y=vix, line=dict(color="#B45AC9", width=1), name="India VIX",
                                 hovertemplate="%{x|%b %Y}: %{y:.1f}<extra></extra>"), row=4, col=1)
    # one layout update instead of ~60 add_vrect calls: plotly re-validates the whole layout on every add_* call
    def ax(r):
        return "" if r == 1 else str(r)
    shapes, notes = [], []

    def shade(x0, x1, fill, label, colour):
        shapes.extend(dict(type="rect", xref=f"x{ax(r)}", yref=f"y{ax(r)} domain", x0=x0, x1=x1, y0=0, y1=1,
                           fillcolor=fill, line_width=0, layer="below") for r in range(1, rows + 1))
        notes.append(dict(x=x0, y=1, xref="x", yref="y domain", text=label, showarrow=False, xanchor="left", yanchor="top",
                          textangle=-90, font=dict(size=9, color=colour)))
    for ev in events:
        w = ev["windows"]["standard"]
        if w:
            crisis = ev["type"] == "crisis"
            shade(w[0], w[1], config.COLOR_CRISIS_FILL if crisis else config.COLOR_CALM_FILL, ev.get("short", ev["name"]),
                  CRISIS if crisis else CALM)
    if current:
        shade(current[0], current[1], "rgba(59,125,216,.12)", "Current", B)
    fig.update_layout(shapes=shapes, annotations=list(fig.layout.annotations) + notes)
    fig.update_yaxes(type="log", row=1, col=1)
    fig.update_yaxes(tickformat=".0%", row=2, col=1)
    fig.update_yaxes(tickformat=".0%", row=3, col=1)
    fig.update_layout(showlegend=False)
    return _base(fig, 640 if rows == 4 else 560, None)


def scoreboard_heatmap(board: list[dict], amount_a: float, amount_b: float) -> go.Figure:
    names = [r["event"] for r in board]
    metrics = [("ES 95% (1 day)", "es"), ("Volatility", "vol"), ("Max drawdown", "mdd"), ("Worst ₹ fall", "fall")]
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
    rows = np.arange(len(symbols), dtype=float)
    regs = list(regime_w.values() if isinstance(regime_w, dict) else regime_w)
    fig = go.Figure()
    fig.add_trace(go.Bar(y=rows, x=[hi[s] - lo[s] for s in symbols], base=[lo[s] for s in symbols], orientation="h", width=0.8,
                         marker=dict(color="rgba(122,131,148,.30)"), name="90% noise band (chance alone)", customdata=symbols,
                         hovertemplate="%{customdata}: noise band %{base:.1%} – %{x:.1%} wide<extra></extra>"))
    fig.add_trace(go.Scatter(y=rows, x=[base[s] for s in symbols], mode="markers", name="Today's weight", customdata=symbols,
                             marker=dict(symbol="line-ns", size=22, line=dict(width=4, color="#FFFFFF")),
                             hovertemplate="%{customdata}: today %{x:.1%}<extra></extra>"))
    for k, (name, w, col) in enumerate(regs):  # each period on its own sub-row, so overlapping markers stay visible
        off = (k - (len(regs) - 1) / 2) * min(0.18, 0.7 / max(len(regs), 1))
        inside = ["inside" if lo[s] - 1e-9 <= w[s] <= hi[s] + 1e-9 else "OUTSIDE" for s in symbols]
        fig.add_trace(go.Scatter(y=rows + off, x=[w[s] for s in symbols], mode="markers", name=name, customdata=list(zip(symbols, inside)),
                                 marker=dict(size=9, color=col, symbol="diamond", line=dict(width=1, color="#0B0F17")),
                                 hovertemplate="%{customdata[0]}: " + name + " %{x:.1%} (%{customdata[1]} the band)<extra></extra>"))
    fig.update_layout(yaxis=dict(autorange="reversed", tickmode="array", tickvals=rows, ticktext=symbols))
    fig.update_xaxes(title="Weight")
    return _base(fig, 120 + 30 * len(symbols), title, xfmt=".0%")


def turnover_hist(noise, p95, marks: list[tuple]) -> go.Figure:
    fig = go.Figure(go.Histogram(x=noise, nbinsx=30, marker=dict(color="#3A4560"), name="Money moved by noise alone"))
    fig.add_vline(x=p95, line=dict(color="#E6E9EF", dash="dash"), annotation_text=f"95% limit {p95:.0%}", annotation_font_size=11)
    for name, v, col in marks:  # periods named in the legend: labels on the lines piled on top of each other when close
        fig.add_vline(x=v, line=dict(color=col, width=3))
        fig.add_trace(go.Scatter(x=[None], y=[None], mode="lines", line=dict(color=col, width=3), name=f"{name} {v:.0%}"))
    fig.update_xaxes(title="Share of money moved (½ Σ |Δw|)")
    return _base(fig, 300, None, xfmt=".0%")


def risk_compare(labels: list[str], a_vals: list[float], b_vals: list[float], title: str, rupees: bool = False,
                 c_vals: list[float] | None = None) -> go.Figure:
    """Grouped bars: a risk measure for A, B (and C) today and in each tested period."""
    fmt = (lambda v: inr_short(v)) if rupees else (lambda v: f"{v:.1%}")
    fig = go.Figure()
    bars = [("Portfolio A", a_vals, A), ("Portfolio B", b_vals, B)] + ([("Portfolio C", c_vals, C)] if c_vals else [])
    labels = ["<br>".join(textwrap.wrap(str(x), 12)) for x in labels]  # stacked, not tilted and cut off on a phone
    for name, vals, col in bars:
        fig.add_trace(go.Bar(x=labels, y=vals, name=name, marker=dict(color=col), text=[fmt(v) for v in vals],
                             textposition="outside", textfont=dict(size=10), cliponaxis=False,
                             hovertemplate="%{x}: %{text}<extra>" + name + "</extra>"))
    fig.update_layout(barmode="group", bargap=0.25, xaxis=dict(tickangle=0, tickfont=dict(size=10)))
    fig.update_yaxes(tickformat=None if rupees else ".0%", rangemode="tozero")
    return _base(fig, 340, title)


def weights_heat(table: pd.DataFrame, title: str | None = None) -> go.Figure:
    """Stocks × periods heatmap of weights (today vs each period's optimum)."""
    z = table.to_numpy()
    cols = ["<br>".join(textwrap.wrap(str(c), 11)) for c in table.columns]  # long period names stacked, not tilted over each other
    fig = go.Figure(go.Heatmap(z=z, x=cols, y=list(table.index), zmin=0, zmax=max(0.25, float(np.nanmax(z))),
                               colorscale=[[0, "#121826"], [0.5, "#2B5A9E"], [1, A]], text=np.vectorize(lambda v: f"{v:.0%}")(z),
                               texttemplate="%{text}", textfont=dict(size=10), showscale=False,
                               hovertemplate="%{y} · %{x}: %{text}<extra></extra>"))
    fig.update_layout(yaxis=dict(autorange="reversed"), xaxis=dict(side="top", tickangle=0, tickfont=dict(size=10)))
    return _base(fig, 120 + 26 * len(table), title)
