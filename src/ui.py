"""Streamlit UI helpers: split layout, Finance Concept Box, flowchart, colours, rupee formatting,
amount input, and the shared app context (results for the client's picks, events and amounts).

The only module in src/ that imports Streamlit. Everything numeric comes from src/engine.py results.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from . import config
from . import data as D
from . import engine as E
from . import events as EV
from . import universe as U
from .fmt import AmountError, inr, inr_short, parse_amount, pct, validate_amount  # noqa: F401 (re-exported)

A_COL, B_COL, N_COL = config.COLOR_A, config.COLOR_B, config.COLOR_NIFTY
CRISIS_COL, CALM_COL = config.COLOR_CRISIS, config.COLOR_CALM

STEPS = [
    ("start", "0 · Your amount"), ("how", "1 · How it works"), ("universe", "2 · Stock universe"),
    ("pick", "3 · Pick stocks"), ("call", "4 · The risk call"), ("weights", "5 · Optimum weights"),
    ("test1", "6 · Test #1: the label"), ("test2", "7 · Test #2: the allocation"), ("verdict", "8 · Verdict"),
    ("method", "9 · Methodology & data"),
]

CSS = f"""
<style>
:root {{ --a:{A_COL}; --b:{B_COL}; --n:{N_COL}; --crisis:{CRISIS_COL}; --calm:{CALM_COL}; }}
.block-container {{ padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1400px; }}
.ptm-panel-label {{ font-size: .72rem; letter-spacing: .08em; text-transform: uppercase; font-weight: 700;
  color: #9AA3B5; margin: 0 0 .4rem 0; display:flex; align-items:center; gap:.4rem; }}
.ptm-panel-label .dot {{ width:.55rem; height:.55rem; border-radius:50%; display:inline-block; }}
.ptm-card {{ border: 1px solid #2A3448; border-radius: 14px; padding: 14px 16px; background: #161D2C; height: 100%; }}
.ptm-card h4 {{ margin: 0 0 6px 0; font-size: 1rem; }}
.ptm-card .big {{ font-size: 1.7rem; font-weight: 700; line-height: 1.15; }}
.ptm-card .sub {{ color: #9AA3B5; font-size: .86rem; }}
.ptm-a {{ border-top: 5px solid var(--a); }} .ptm-b {{ border-top: 5px solid var(--b); }}
.ptm-n {{ border-top: 5px solid var(--n); }}
.ptm-crisis {{ border-left: 5px solid var(--crisis); background: #2A1A1D; }}
.ptm-calm {{ border-left: 5px solid var(--calm); background: #15281E; }}
.ptm-concept {{ border: 1px solid #2B3756; background: #162036; border-radius: 14px; padding: 12px 16px; margin: .6rem 0 1rem 0; }}
.ptm-concept .t {{ font-weight: 700; font-size: .95rem; margin-bottom: .35rem; }}
.ptm-concept .k {{ font-size: .7rem; text-transform: uppercase; letter-spacing: .07em; color: #9DB1F0; font-weight: 700; margin-top:.45rem; }}
.ptm-concept p {{ margin: .1rem 0 .2rem 0; font-size: .9rem; }}
.ptm-pill {{ display:inline-block; padding: 2px 9px; border-radius: 999px; font-size: .78rem; font-weight: 600; }}
.ptm-pill.a {{ background: #3A2420; color: #F4A48F; }} .ptm-pill.b {{ background: #1C2C47; color: #8FB8F2; }}
.ptm-pill.ok {{ background: #163225; color: #7FD3A0; }} .ptm-pill.bad {{ background: #3A1D1F; color: #F19A9A; }}
.ptm-pill.mid {{ background: #3A3016; color: #F2C96B; }} .ptm-pill.grey {{ background:#263043; color:#C9CFDB; }}
.ptm-verdict {{ font-size: 1.05rem; line-height: 1.5; }}
.ptm-footer {{ color: #8E97A8; font-size: .8rem; border-top: 1px solid #2A3448; padding-top: .6rem; margin-top: 2rem; }}
.ptm-hero {{ font-size: 1.9rem; font-weight: 750; line-height: 1.2; margin: .2rem 0 .3rem 0; }}
.ptm-tag {{ color:#9AA3B5; font-size: 1.02rem; margin-bottom: .8rem; }}
@media (max-width: 640px) {{
  .block-container {{ padding-left: 1rem; padding-right: 1rem; padding-top: 1rem; }}
  .ptm-hero {{ font-size: 1.45rem; }}
  .ptm-card .big {{ font-size: 1.35rem; }}
}}
</style>
"""


def inject_css() -> None:
    st.html(CSS)


# ---------------------------------------------------------------- layout
def panel_label(text: str, colour: str) -> None:
    st.html(f'<div class="ptm-panel-label"><span class="dot" style="background:{colour}"></span>{text}</div>')


def page_header(step_key: str, title: str, subtitle: str = "") -> None:
    client, _ = split()
    with client:
        st.caption(dict(STEPS).get(step_key, ""))
        st.markdown(f"## {title}")
        if subtitle:
            st.markdown(f"<div class='ptm-tag'>{subtitle}</div>", unsafe_allow_html=True)


def card(title: str, value: str, sub: str = "", kind: str = "") -> None:
    st.html(f"<div class='ptm-card ptm-{kind}'><h4>{title}</h4><div class='big'>{value}</div><div class='sub'>{sub}</div></div>")


def pill(text: str, kind: str = "grey") -> str:
    return f"<span class='ptm-pill {kind}'>{text}</span>"


def concept_box(title: str, plain: str, formally: str, why: str, where: str, latex: str | None = None) -> None:
    """Finance Concept Box: In plain words → Formally → Why an investor cares → Where you see it here."""
    with st.container():
        st.html(f"<div class='ptm-concept'><div class='t'>📘 Finance concept: {title}</div>"
                f"<div class='k'>In plain words</div><p>{plain}</p>"
                f"<div class='k'>Formally</div><p>{formally}</p></div>")
        if latex:
            st.latex(latex)
        st.html(f"<div class='ptm-concept' style='margin-top:-.4rem'><div class='k'>Why an investor cares</div><p>{why}</p>"
                f"<div class='k'>Where you see it here</div><p>{where}</p></div>")


def flowchart(current: str) -> None:
    """Pipeline flowchart (two rows) with the current step highlighted."""
    nodes = [("data", "Yahoo Finance +\nNSE data"), ("clean", "Clean & verify")] + \
            [(k, lbl.split(" · ")[1]) for k, lbl in STEPS[:9]]
    lines = ['digraph G { rankdir=TB; bgcolor="transparent"; nodesep=0.25; ranksep=0.45; newrank=true; size="11,3";',
             'node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=11, color="#3A4560", fillcolor="#161D2C", fontcolor="#E6E9EF", margin="0.15,0.08"];',
             'edge [color="#6B7690", arrowsize=0.7];']
    for k, lbl in nodes:
        lbl = lbl.replace('"', "'")
        style = f', fillcolor="{A_COL}", fontcolor="white", color="{A_COL}", penwidth=2' if k == current else ""
        lines.append(f'"{k}" [label="{lbl}"{style}];')
    order = [k for k, _ in nodes]
    half = (len(order) + 1) // 2
    lines.append("{rank=same; " + " ".join(f'"{k}"' for k in order[:half]) + "}")
    lines.append("{rank=same; " + " ".join(f'"{k}"' for k in order[half:]) + "}")
    for a, b in zip(order[:half - 1], order[1:half]):
        lines.append(f'"{a}" -> "{b}";')
    lines.append(f'"{order[half - 1]}" -> "{order[half]}" [constraint=false];')
    for a, b in zip(order[half:-1], order[half + 1:]):
        lines.append(f'"{a}" -> "{b}";')
    lines.append(f'"{order[0]}" -> "{order[half]}" [style=invis];')
    lines.append("}")
    st.graphviz_chart("\n".join(lines), width="stretch")


def footer() -> None:
    st.html(f"<div class='ptm-footer'>{config.FOOTER.format(date=D.as_of())} · "
            f"<a href='{config.REPO_URL}' target='_blank'>Source code on GitHub</a></div>")


def fig_style(fig: go.Figure, height: int = 380, title: str | None = None) -> go.Figure:
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=40 if title else 10, b=10), title=title,
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0), font=dict(size=12),
                      plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", hovermode="x unified")
    fig.update_xaxes(gridcolor="#263043", zeroline=False)
    fig.update_yaxes(gridcolor="#263043", zeroline=False)
    return fig


def show(fig: go.Figure) -> None:
    if st.session_state.get("phone") or _CTX["in_client"]:
        h = fig.layout.height or 380
        fig.update_layout(height=min(int(h * 0.82), 420) if h < 600 else 520,
                          margin=dict(l=4, r=4, t=36 if (fig.layout.title.text or "") else 8, b=4),
                          legend=dict(font=dict(size=10)), font=dict(size=11))
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False, "responsive": True, "scrollZoom": False})


# ---------------------------------------------------------------- state
DEFAULT_STATE = {
    "amount_a": float(config.AMOUNT_A), "amount_b": float(config.AMOUNT_B), "amount_total": float(config.AMOUNT_A * 2),
    "amount_mode": config.AMOUNT_MODE, "amount_confirmed": False, "conf": 0.99, "horizon": 1,
    "window_mode": config.EVENT_WINDOW_MODE, "show_backing": True, "tolerance": None,
}
MOBILE_UA = ("iphone", "android", "mobile", "ipod", "blackberry", "opera mini", "iemobile")


def detect_phone() -> bool:
    """Phone if the stlite loader flagged a narrow screen (?phone=1) or the browser says it is mobile."""
    try:
        if st.query_params.get("phone") == "1":
            return True
    except Exception:
        pass
    try:
        ua = (st.context.headers.get("User-Agent") or "").lower()
    except Exception:
        ua = ""
    return any(k in ua for k in MOBILE_UA)


@st.cache_data(show_spinner=False)
def default_results() -> dict:
    return json.loads((config.RESULTS_DIR / "default.json").read_text())


@st.cache_data(show_spinner=False)
def universe_table() -> pd.DataFrame:
    rows = json.loads((config.RESULTS_DIR / "universe.json").read_text())
    return pd.DataFrame(rows).set_index("symbol")


def init_state() -> None:
    for k, v in DEFAULT_STATE.items():
        st.session_state.setdefault(k, v)
    st.session_state.setdefault("phone", detect_phone())
    res = default_results()
    st.session_state.setdefault("pick_A", list(res["picks"]["A"]))
    st.session_state.setdefault("pick_B", list(res["picks"]["B"]))
    st.session_state.setdefault("crisis_id", res["official"]["crisis"])
    st.session_state.setdefault("calm_id", res["official"]["calm"])
    if "qp_done" not in st.session_state:
        st.session_state["qp_done"] = True
        try:
            q = st.query_params.get("amount")
        except Exception:  # some hosts do not expose query parameters
            q = None
        if q:
            try:
                v = parse_amount(q)
                if validate_amount(v, config.AMOUNT_MIN, config.AMOUNT_MAX) is None:
                    st.session_state["amount_a"] = st.session_state["amount_b"] = v
                    st.session_state["amount_total"] = 2 * v
                    st.session_state["amount_from_link"] = v
            except AmountError:
                pass


def amounts() -> tuple[float, float]:
    s = st.session_state
    if s["amount_mode"] == "split_total":
        return s["amount_total"] / 2, s["amount_total"] / 2
    if s["amount_mode"] == "separate":
        return s["amount_a"], s["amount_b"]
    return s["amount_a"], s["amount_a"]


def reset_team_picks() -> None:
    res = default_results()
    st.session_state["pick_A"] = list(res["picks"]["A"])
    st.session_state["pick_B"] = list(res["picks"]["B"])
    st.session_state["crisis_id"] = res["official"]["crisis"]
    st.session_state["calm_id"] = res["official"]["calm"]
    for k in ("custom_crisis", "custom_calm", "board_custom", "boot_custom"):
        st.session_state.pop(k, None)


def is_default_picks() -> bool:
    res = default_results()
    return (sorted(st.session_state["pick_A"]) == sorted(res["picks"]["A"]) and
            sorted(st.session_state["pick_B"]) == sorted(res["picks"]["B"]))


# ---------------------------------------------------------------- cached computations for custom picks
@st.cache_data(show_spinner=False, max_entries=8)
def _portfolios(a: tuple, b: tuple) -> dict:
    pa = E.build_portfolio("A", list(a), config.OBJECTIVE_A, cloud_k=config.RANDOM_PORTFOLIOS_BROWSER)
    pb = E.build_portfolio("B", list(b), config.OBJECTIVE_B, cloud_k=config.RANDOM_PORTFOLIOS_BROWSER)
    return {"A": pa, "B": pb}


@st.cache_data(show_spinner=False, max_entries=8)
def _evidence(a: tuple, b: tuple) -> dict:
    P = _portfolios(a, b)
    return E.evidence(P["A"], P["B"], resamples=config.BOOTSTRAP_RESAMPLES_BROWSER)


@st.cache_data(show_spinner=False, max_entries=32)
def _regime(a: tuple, b: tuple, start: str, end: str) -> dict:
    P = _portfolios(a, b) if (a, b) != _default_key() else default_results()["portfolios"]
    lab = E.labels_in_window(start, end)
    return {"A": E.regime_result(P["A"], start, end, lab), "B": E.regime_result(P["B"], start, end, lab),
            "nifty": E.nifty_replay(start, end), "start": start, "end": end}


def _default_key():
    res = default_results()
    return tuple(res["picks"]["A"]), tuple(res["picks"]["B"])


@st.cache_data(show_spinner=False)
def nifty_close() -> pd.Series:
    return D.benchmark()["NIFTY50"]


@dataclass
class Ctx:
    res: dict
    P: dict
    evidence: dict
    events: dict
    current: dict
    crisis: dict
    calm: dict
    crisis_ev: dict
    calm_ev: dict
    amount_a: float
    amount_b: float
    conf: float
    horizon: int
    mode: str
    default: bool

    def amount(self, k: str) -> float:
        return self.amount_a if k == "A" else self.amount_b

    def ck(self) -> str:
        """JSON key for the selected confidence level ('0.95', '0.99' or '0.975')."""
        return str(self.conf)

    def h(self, x: float) -> float:
        """Scale a 1-day loss to the chosen horizon (√t)."""
        return x * (self.horizon ** 0.5)

    def regimes(self):
        return (("Current", self.current, None), ("Crisis", self.crisis, self.crisis_ev), ("Calm", self.calm, self.calm_ev))

    def scoreboard(self) -> list[dict] | None:
        if self.default:
            return self.res["scoreboard"]["standard" if self.mode == "standard" else "event_only"]
        return st.session_state.get("board_custom", {}).get((tuple(self.P["A"]["symbols"]), tuple(self.P["B"]["symbols"]), self.mode))

    def bootstrap(self) -> dict | None:
        if self.default:
            return self.res["bootstrap"]
        return st.session_state.get("boot_custom", {}).get((tuple(self.P["A"]["symbols"]), tuple(self.P["B"]["symbols"])))


def event_options(kind: str) -> list[str]:
    evs = default_results()["events"]
    auto = "auto_crisis" if kind == "crisis" else "auto_calm"
    ids = [auto] + [k for k, v in evs.items() if v["type"] == kind and not k.startswith("auto_")]
    return ids + ["custom"]


def event_label(eid: str) -> str:
    if eid == "custom":
        return "Custom: a date range"
    ev = default_results()["events"][eid]
    if eid.startswith("auto_"):
        return "Auto · " + ev["label"]
    return ev["label"] if ev["available"] else f"{ev['name']} · not available ({'; '.join(ev['notes'])[:80]})"


def coverage_problem(eid: str, symbols: list[str], mode: str) -> str | None:
    """Reason the event can't be tested with these stocks (None when every stock has data)."""
    evs = default_results()["events"]
    if eid not in evs:
        return None
    ev = evs[eid]
    if not ev["available"]:
        return "not supported by the Nifty 50 data"
    w = ev["windows"].get(mode) or ev["windows"]["standard"]
    t = universe_table()
    for s in symbols:
        fd = t.loc[s, "first_date"] if s in t.index else None
        if fd and pd.Timestamp(fd) > pd.Timestamp(w[0]):
            return f"{s} listed in {pd.Timestamp(fd).year} — not available for this event"
    return None


def fallback_event(kind: str, symbols: list[str], mode: str) -> str:
    """The official pick if these stocks cover it, otherwise the first event (official first) they all cover."""
    off = default_results()["official"][kind]
    for eid in [off] + [e for e in event_options(kind) if e not in (off, "custom")]:
        if coverage_problem(eid, symbols, mode) is None:
            return eid
    return "custom"


def _resolve_event(kind: str) -> dict:
    s = st.session_state
    eid = s[f"{kind}_id"]
    if eid == "custom":
        rng = s.get(f"custom_{kind}")
        if rng:
            try:
                ev = EV.custom_event(rng[0], rng[1], nifty_close(), kind)
                return E.event_payload(ev)
            except ValueError:
                pass
        eid = default_results()["official"][kind]
    if coverage_problem(eid, s["pick_A"] + s["pick_B"], s["window_mode"]):
        eid = fallback_event(kind, s["pick_A"] + s["pick_B"], s["window_mode"])
        if eid == "custom":  # nothing in the catalogue fits: use the most recent 252 days before Current
            cal = D.calendar()
            ev = EV.custom_event(cal[-2 * config.REGIME_DAYS], cal[-config.REGIME_DAYS - 1], nifty_close(), kind)
            return E.event_payload(ev)
    return default_results()["events"][eid]


def context() -> Ctx:
    s = st.session_state
    res = default_results()
    a, b = tuple(s["pick_A"]), tuple(s["pick_B"])
    default = (a, b) == _default_key() or (sorted(a), sorted(b)) == tuple(sorted(x) for x in _default_key())
    mode = s["window_mode"]
    if default:
        P, evd = res["portfolios"], res["evidence"]
    else:
        with st.spinner("Re-optimising your portfolios in the browser…"):
            P, evd = _portfolios(a, b), _evidence(a, b)
    out = {}
    for kind in ("crisis", "calm"):
        ev = _resolve_event(kind)
        w = ev["windows"].get(mode) or ev["windows"]["standard"]
        key = f"{ev['id']}|{mode}" if f"{ev['id']}|{mode}" in res["regimes"] else f"{ev['id']}|standard"
        if default and ev["id"] != "custom" and key in res["regimes"] and res["regimes"][key]["start"] == w[0]:
            out[kind] = (res["regimes"][key], ev)
        else:
            with st.spinner(f"Testing your portfolios in {ev['name']}…"):
                out[kind] = (_regime(a, b, w[0], w[1]), ev)
    if default:
        cur = res["current"]
    else:
        cal = D.calendar()
        cur = _regime(a, b, str(cal[-config.REGIME_DAYS].date()), str(cal[-1].date()))
    aa, ab = amounts()
    return Ctx(res=res, P=P, evidence=evd, events=res["events"], current=cur, crisis=out["crisis"][0], calm=out["calm"][0],
               crisis_ev=out["crisis"][1], calm_ev=out["calm"][1], amount_a=aa, amount_b=ab, conf=s["conf"],
               horizon=s["horizon"], mode=mode, default=default)


def compute_scoreboard(ctx: Ctx) -> list[dict]:
    """All-events scoreboard for custom picks, with a progress bar."""
    res = default_results()
    a, b = tuple(ctx.P["A"]["symbols"]), tuple(ctx.P["B"]["symbols"])
    ids = [k for k, v in res["events"].items() if v["available"] and not k.startswith("auto_")]
    bar = st.progress(0.0, text="Testing every event…")
    regs = {}
    for n, eid in enumerate(ids, 1):
        ev = res["events"][eid]
        if coverage_problem(eid, list(a) + list(b), ctx.mode):
            continue
        w = ev["windows"].get(ctx.mode) or ev["windows"]["standard"]
        regs[f"{eid}|{ctx.mode}"] = _regime(a, b, w[0], w[1])
        bar.progress(n / len(ids), text=f"Tested {ev['name']}")
    bar.empty()
    board = E.scoreboard({"regimes": regs, "events": res["events"]}, ctx.mode)
    st.session_state.setdefault("board_custom", {})[(a, b, ctx.mode)] = board
    return board


def compute_bootstrap(ctx: Ctx) -> dict:
    a, b = tuple(ctx.P["A"]["symbols"]), tuple(ctx.P["B"]["symbols"])
    out = {}
    for k in ("A", "B"):
        bar = st.progress(0.0, text=f"Bootstrapping Portfolio {k} ({config.BOOTSTRAP_RESAMPLES_BROWSER} resamples)…")
        out[k] = E.bootstrap_noise(ctx.P[k], config.BOOTSTRAP_RESAMPLES_BROWSER,
                                   progress=lambda f, bar=bar, k=k: bar.progress(f, text=f"Bootstrapping Portfolio {k}… {f:.0%}"))
        bar.empty()
    st.session_state.setdefault("boot_custom", {})[(a, b)] = out
    return out


def health_badge() -> str:
    meta = D.metadata()
    return f"Data health: {meta['n_core']} core + {meta['n_extended']} extended stocks checked · see page 9"


def universe_symbols() -> list[str]:
    return U.usable()["symbol"].tolist()


def _sync(src: str, dst: str) -> None:
    st.session_state[dst] = st.session_state[src]


def event_selectors(page: str) -> None:
    """The crisis and calm dropdowns repeated at the top of a page, kept in sync with the sidebar."""
    s = st.session_state
    client, _ = split()
    with client:
        c1, c2 = st.columns(2)
    for col, kind in ((c1, "crisis"), (c2, "calm")):
        key = f"top_{kind}_{page}"
        opts = event_options(kind)
        s[key] = s[f"{kind}_id"] if s[f"{kind}_id"] in opts else opts[0]
        labels = {e: compact_label(e, s["pick_A"] + s["pick_B"], s["window_mode"]) for e in opts}
        col.selectbox(f"{'🔴 Crisis' if kind == 'crisis' else '🟢 Calm'} to test against", opts, format_func=labels.get,
                      key=key, on_change=_sync, args=(key, f"{kind}_id"))


def event_label_for(eid: str, symbols: list[str], mode: str) -> str:
    lab = event_label(eid)
    if eid != "custom":
        prob = coverage_problem(eid, symbols, mode)
        if prob and "not supported" not in prob:
            return f"⛔ {lab} — unavailable: {prob}"
    return lab


def story_cards(ctx: "Ctx") -> None:
    client, _ = split()
    with client:
        c1, c2 = st.columns(2)
    for col, ev, kind in ((c1, ctx.crisis_ev, "crisis"), (c2, ctx.calm_ev, "calm")):
        w = ev["windows"].get(ctx.mode) or ev["windows"]["standard"]
        col.html(f"<div class='ptm-card ptm-{kind}'><h4>{'🔴' if kind == 'crisis' else '🟢'} {ev['name']}</h4>"
                 f"<div class='sub'>Window used: {w[0]} → {w[1]} ({'standard 252 days' if ctx.mode == 'standard' else 'event only'})</div>"
                 f"<p style='margin:.4rem 0 0'>{ev['story']}</p></div>")


# ---------------------------------------------------------------- frames: virtual phone (desktop) or full-screen app (phones)
TABS = [("home", "🏠", "Home"), ("pick", "🧺", "Pick"), ("test1", "🌪️", "Test 1"), ("test2", "🔁", "Test 2"),
        ("verdict", "✅", "Verdict")]
MORE = [("start", "💰", "Your amount"), ("how", "🧭", "How it works"), ("call", "⚖️", "The risk call"),
        ("weights", "🎯", "Optimum weights"), ("method", "📚", "Methodology & data")]
_CTX = {"in_client": False}

DEVICE_CSS = """
<style>
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], [data-testid="collapsedControl"] { display: none !important; }
.block-container { padding-top: 1.4rem !important; max-width: 1500px !important; }
.st-key-ptm_stage > div > [data-testid="stColumn"]:first-child { position: sticky; top: .8rem; align-self: flex-start; }
.st-key-ptm_phone { width: 400px; max-width: 100%; margin: 0 auto; background: #161D2C; border: 13px solid #05070B; border-radius: 52px;
  box-shadow: 0 0 0 2px #2E3445, 0 28px 70px rgba(0,0,0,.6), 0 0 80px rgba(232,115,90,.08); padding: 0 !important; gap: 0 !important; overflow: hidden; }
.ptm-status { display: flex; justify-content: space-between; align-items: center; padding: 10px 26px 4px; font: 600 13px/1 -apple-system, "SF Pro Text", Helvetica, sans-serif; color: #E6E9EF; position: relative; background: #0F1521; }
.ptm-status .island { position: absolute; left: 50%; top: 6px; transform: translateX(-50%); width: 112px; height: 28px; background: #000; border-radius: 20px; }
.ptm-status .icons { letter-spacing: 3px; font-size: 11px; }
.st-key-ptm_appbar { padding: 6px 14px 8px !important; border-bottom: 1px solid #263043; gap: 6px !important; }
.st-key-ptm_appbar p { margin: 0; font-size: .82rem; line-height: 1.25; }
.st-key-ptm_appbar [data-testid="stPopover"] button { border-radius: 999px; min-height: 2.1rem; padding: 0 .7rem; }
.st-key-ptm_screen { padding: 10px 14px 18px !important; background: #0F1521; }
.st-key-ptm_screen h2 { font-size: 1.28rem !important; line-height: 1.25; padding-top: .2rem; }
.st-key-ptm_screen h4 { font-size: 1rem !important; }
.st-key-ptm_screen .ptm-tag { font-size: .9rem; }
.st-key-ptm_screen [data-testid="stHorizontalBlock"] { flex-wrap: wrap !important; }
.st-key-ptm_screen [data-testid="stColumn"] { min-width: 100% !important; flex: 1 1 100% !important; }
.st-key-ptm_screen .ptm-card { border-radius: 16px; box-shadow: 0 2px 10px rgba(31,36,48,.06); margin-bottom: .4rem; }
.st-key-ptm_screen .ptm-card .big { font-size: 1.35rem; }
.st-key-ptm_screen [data-testid="stMetricValue"] { font-size: 1.25rem; }
.st-key-ptm_tabs { border-top: 1px solid #2A3448; padding: 4px 2px 2px !important; gap: 0 !important; justify-content: space-around; background: #161D2C; }
.st-key-ptm_tabs > div { flex: 1 1 0; min-width: 0; }
.st-key-ptm_tabs a { display: flex !important; flex-direction: column; align-items: center; padding: .25rem .05rem !important; border-radius: 12px; min-height: 2.8rem; justify-content: center; }
.st-key-ptm_tabs a p, .st-key-ptm_tabs a span { font-size: .64rem !important; line-height: 1.1; white-space: nowrap; }
.st-key-ptm_tabs [data-testid="stPopover"] button { border: none; min-height: 2.8rem; padding: .1rem; width: 100%; }
.ptm-homebar { height: 22px; display: flex; justify-content: center; align-items: center; background: #161D2C; }
.ptm-homebar span { width: 120px; height: 5px; border-radius: 3px; background: #9AA3B5; }
.st-key-ptm_working { padding-top: .2rem; }
.ptm-working-head { font-size: .72rem; letter-spacing: .08em; text-transform: uppercase; font-weight: 700; color: #3B7DD8; }
.ptm-working-title { font-size: 1.55rem; font-weight: 750; margin: .1rem 0 .2rem; }
.ptm-caption-phone { text-align: center; color: #8E97A8; font-size: .8rem; margin-top: .6rem; }
@media (max-width: 900px) {
  .st-key-ptm_stage > div > [data-testid="stColumn"]:first-child { position: static; }
}
@media (max-width: 520px) {  /* a real phone that slipped through detection: drop the device frame */
  .st-key-ptm_phone { width: 100%; border: 0; border-radius: 0; box-shadow: none; }
  .ptm-status, .ptm-homebar, .ptm-caption-phone { display: none; }
  .block-container { padding-left: .5rem !important; padding-right: .5rem !important; }
}
</style>
"""

MOBILE_CSS = """
<style>
.block-container { padding: 4.2rem .85rem 6.5rem .85rem !important; }
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], [data-testid="collapsedControl"] { display: none !important; }
.st-key-ptm_appbar { position: sticky; top: 3.1rem; z-index: 990; background: rgba(15,21,33,.96); backdrop-filter: blur(6px);
  border-bottom: 1px solid #263043; margin: -.6rem -.85rem .6rem -.85rem; padding: .45rem .85rem !important; }
.st-key-ptm_appbar p { margin: 0; font-size: .82rem; line-height: 1.25; }
.st-key-ptm_appbar [data-testid="stPopover"] button { border-radius: 999px; min-height: 2.4rem; }
.st-key-ptm_tabs { position: fixed; left: 0; right: 0; bottom: 0; z-index: 999; background: #161D2C; border-top: 1px solid #2A3448;
  box-shadow: 0 -6px 18px rgba(31,36,48,.07); padding: .25rem .2rem calc(.3rem + env(safe-area-inset-bottom)) !important; gap: 0 !important;
  justify-content: space-around; }
.st-key-ptm_tabs > div { flex: 1 1 0; min-width: 0; }
.st-key-ptm_tabs a { display: flex !important; flex-direction: column; align-items: center; padding: .3rem .1rem !important;
  border-radius: 12px; min-height: 3rem; justify-content: center; }
.st-key-ptm_tabs a p, .st-key-ptm_tabs a span { font-size: .68rem !important; line-height: 1.1; white-space: nowrap; }
.st-key-ptm_tabs [data-testid="stPopover"] button { border: none; min-height: 3rem; padding: .2rem; width: 100%; }
h2 { font-size: 1.4rem !important; }
.ptm-card { border-radius: 16px; box-shadow: 0 2px 10px rgba(31,36,48,.05); margin-bottom: .5rem; }
div[data-testid="stExpander"] details { border-radius: 14px; border-color: #2B3756; background: #141B2B; }
div[data-testid="stExpander"] summary { min-height: 3rem; font-weight: 600; }
button[kind="primary"], button[kind="secondary"] { min-height: 2.8rem; border-radius: 12px; }
</style>
"""


class _Client:
    """Wraps the customer-view container so charts drawn inside it are sized for a phone screen."""

    def __init__(self, c):
        self._c = c

    def __enter__(self):
        self._prev = _CTX["in_client"]
        _CTX["in_client"] = True
        return self._c.__enter__()

    def __exit__(self, *a):
        _CTX["in_client"] = self._prev
        return self._c.__exit__(*a)

    def __getattr__(self, name):
        return getattr(self._c, name)


def _app_bar(page_title: str, controls) -> None:
    bar = st.container(key="ptm_appbar", horizontal=True, vertical_alignment="center", horizontal_alignment="distribute")
    with bar:
        a, b = amounts()
        right_txt = f"A {inr_short(a)} · B {inr_short(b)}" if st.session_state["amount_confirmed"] else "Portfolio Time Machine"
        st.markdown(f"**⏳ {page_title.split(' — ')[0]}**  \n<span style='color:#9AA3B5'>{right_txt}</span>",
                    unsafe_allow_html=True)
        with st.popover("⚙️", width="content", help="Settings: amount, events, confidence, horizon",
                        key=f"ptm_settings_{page_title}"):
            controls()


def _tab_bar(pages: dict, page_title: str = "") -> None:
    with st.container(key="ptm_tabs", horizontal=True):
        for key, icon, label in TABS:
            st.page_link(pages[key], label=label, icon=icon)
        # a fresh key on every page, so the menu is closed after you navigate
        with st.popover("☰", width="stretch", help="More pages", key=f"ptm_more_{page_title}"):
            for key, icon, label in MORE:
                st.page_link(pages[key], label=label, icon=icon)


def setup_frames(pages: dict, page_title: str, controls) -> None:
    """Build the page skeleton before the page runs.

    Computer: a virtual phone on the left (the customer app exactly as a client sees it) and "The working" on the right.
    Phone: the app full screen, with the working as a tap-to-open section under each screen."""
    s = st.session_state
    confirmed = s["amount_confirmed"]
    st.html(APP_CSS)
    if s.get("phone"):
        st.html(MOBILE_CSS)
        _app_bar(page_title, controls)
        client = st.container()
        working = st.expander("📐 The working — logic, maths and evidence") if s.get("show_backing", True) else None
        if confirmed:
            _tab_bar(pages, page_title)
        s["_frames"] = {"client": client, "working": working}
        return
    st.html(DEVICE_CSS)
    show_working = s.get("show_backing", True)
    stage = st.container(key="ptm_stage")
    with stage:
        cols = st.columns([0.36, 0.64], gap="large") if show_working else st.columns([1, 1.2, 1])[1:2]
        with cols[0]:
            with st.container(key="ptm_phone"):
                st.html("<div class='ptm-status'><span>9:41</span><span class='island'></span><span class='icons'>▂▄▆ ᯤ ▮</span></div>")
                _app_bar(page_title, controls)
                screen = st.container(key="ptm_screen", height=640, border=False)
                if confirmed:
                    _tab_bar(pages, page_title)
                st.html("<div class='ptm-homebar'><span></span></div>")
            st.html("<div class='ptm-caption-phone'>The customer app, as a client sees it on their phone — tap through it.</div>")
        working = None
        if show_working:
            with cols[1]:
                working = st.container(key="ptm_working")
                with working:
                    st.html(f"<div class='ptm-working-head'>The working · logic, maths and evidence</div>"
                            f"<div class='ptm-working-title'>Behind “{page_title.split(' — ')[0]}”</div>")
    s["_frames"] = {"client": screen, "working": working}


def split():
    """(client, working): the customer screen (inside the virtual phone on a computer, full screen on a phone) and the
    working panel (None when hidden)."""
    f = st.session_state.get("_frames")
    if not f:  # page run on its own (tests): plain two columns
        left, right = st.columns([1.05, 1], gap="large")
        return _Client(left), right
    return _Client(f["client"]), f["working"]


# ---------------------------------------------------------------- app components (the customer screens)
APP_CSS = f"""
<style>
.app-hero {{ border-radius: 22px; padding: 18px 18px 16px; color: #fff; margin: 2px 0 12px;
  background: linear-gradient(135deg, #2B3550 0%, #182032 100%); border: 1px solid #2E3A57; box-shadow: 0 10px 24px rgba(0,0,0,.35); }}
.app-hero .l {{ font-size: .78rem; opacity: .8; letter-spacing: .02em; }}
.app-hero .v {{ font-size: 2rem; font-weight: 800; line-height: 1.1; margin: 2px 0 4px; }}
.app-hero .s {{ font-size: .82rem; opacity: .85; }}
.app-hero.a {{ background: linear-gradient(135deg, #E8735A 0%, #C9533B 100%); }}
.app-hero.b {{ background: linear-gradient(135deg, #3B7DD8 0%, #2457A5 100%); }}
.app-hero.crisis {{ background: linear-gradient(135deg, #B83A3A 0%, #7E2020 100%); }}
.app-hero.calm {{ background: linear-gradient(135deg, #2E9E5B 0%, #1C6B3C 100%); }}
.app-sec {{ display:flex; justify-content: space-between; align-items: baseline; margin: 16px 2px 6px; }}
.app-sec .t {{ font-weight: 750; font-size: .98rem; color: #E6E9EF; }}
.app-sec .x {{ font-size: .75rem; color: #8E97A8; }}
.app-plan {{ background: #161D2C; border-radius: 18px; padding: 14px 14px 10px; margin-bottom: 10px; border: 1px solid #263043;
  box-shadow: 0 3px 12px rgba(31,36,48,.06); }}
.app-plan .top {{ display:flex; align-items:center; gap: 10px; }}
.app-plan .ic {{ width: 38px; height: 38px; border-radius: 12px; display:flex; align-items:center; justify-content:center; font-size: 1.15rem; }}
.app-plan .ic.a {{ background: #3A2420; }} .app-plan .ic.b {{ background: #1C2C47; }}
.app-plan .nm {{ font-weight: 750; font-size: .98rem; line-height: 1.15; }}
.app-plan .tg {{ font-size: .75rem; color: #8E97A8; }}
.app-plan .amt {{ margin-left: auto; text-align: right; font-weight: 800; font-size: 1.05rem; }}
.app-plan .rows {{ margin-top: 10px; border-top: 1px dashed #2A3448; }}
.app-plan .row {{ display:flex; justify-content: space-between; padding: 7px 0; font-size: .85rem; border-bottom: 1px solid #1E2638; }}
.app-plan .row:last-child {{ border-bottom: 0; }}
.app-plan .row .k {{ color: #9AA3B5; }} .app-plan .row .v {{ font-weight: 700; }}
.app-tiles {{ display:grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 10px; }}
.app-tile {{ background: #161D2C; border: 1px solid #263043; border-radius: 16px; padding: 10px 12px; }}
.app-tile .l {{ font-size: .72rem; color: #8E97A8; }} .app-tile .v {{ font-size: 1.15rem; font-weight: 800; margin-top: 2px; }}
.app-tile .s {{ font-size: .7rem; color: #8E97A8; }}
.app-tile.a {{ border-left: 4px solid {A_COL}; }} .app-tile.b {{ border-left: 4px solid {B_COL}; }}
.app-cmp {{ background: #161D2C; border: 1px solid #263043; border-radius: 16px; padding: 12px 14px; margin-bottom: 10px; }}
.app-cmp .q {{ font-weight: 700; font-size: .88rem; margin-bottom: 8px; }}
.app-cmp .ln {{ display:grid; grid-template-columns: 22px 1fr auto; gap: 8px; align-items:center; margin: 5px 0; font-size: .8rem; }}
.app-cmp .bar {{ height: 9px; border-radius: 6px; background: #1E2638; overflow: hidden; }}
.app-cmp .bar span {{ display:block; height:100%; border-radius: 6px; }}
.app-cmp .tag {{ font-weight: 800; font-size: .75rem; text-align:center; border-radius: 6px; color:#fff; }}
.app-cmp .val {{ font-weight: 700; min-width: 70px; text-align: right; }}
.app-cmp .note {{ font-size: .74rem; color: #8E97A8; margin-top: 6px; }}
.app-list {{ background: #161D2C; border: 1px solid #263043; border-radius: 16px; padding: 2px 12px; margin-bottom: 10px; }}
.app-li {{ display:flex; align-items:center; gap: 10px; padding: 10px 0; border-bottom: 1px solid #1E2638; }}
.app-li:last-child {{ border-bottom: 0; }}
.app-li .ic {{ width: 34px; height: 34px; border-radius: 10px; background: #1E2638; display:flex; align-items:center; justify-content:center; font-size: 1rem; flex: none; }}
.app-li .tx {{ flex: 1; min-width: 0; }}
.app-li .t1 {{ font-weight: 650; font-size: .86rem; line-height: 1.2; }}
.app-li .t2 {{ font-size: .72rem; color: #8E97A8; line-height: 1.25; }}
.app-li .rt {{ text-align: right; flex: none; }}
.app-li .r1 {{ font-weight: 750; font-size: .86rem; }} .app-li .r2 {{ font-size: .7rem; color: #8E97A8; }}
.chip {{ display:inline-block; padding: 2px 8px; border-radius: 999px; font-size: .68rem; font-weight: 700; }}
.chip.ok {{ background: #163225; color: #7FD3A0; }} .chip.bad {{ background: #3A1D1F; color: #F19A9A; }}
.chip.mid {{ background: #3A3016; color: #F2C96B; }} .chip.a {{ background: #3A2420; color: #F4A48F; }}
.chip.b {{ background: #1C2C47; color: #8FB8F2; }} .chip.grey {{ background: #263043; color: #C9CFDB; }}
.app-note {{ display:flex; gap: 10px; background: #162036; border: 1px solid #2B3756; border-radius: 16px; padding: 10px 12px;
  font-size: .82rem; line-height: 1.4; margin-bottom: 10px; }}
.app-note .i {{ font-size: 1.1rem; }}
.app-note.warn {{ background: #2E2814; border-color: #5A4A1E; }} .app-note.good {{ background: #15281E; border-color: #24503A; }}
.app-note.bad {{ background: #2A1A1D; border-color: #5A2A2E; }}
.app-verdict {{ text-align:center; background: #161D2C; border: 1px solid #263043; border-radius: 20px; padding: 16px 14px; margin-bottom: 10px; }}
.app-verdict .e {{ font-size: 2rem; }} .app-verdict .h {{ font-weight: 800; font-size: 1.1rem; margin: 2px 0; }}
.app-verdict .b {{ font-size: .82rem; color: #B4BCCB; }}
.app-steps {{ counter-reset: s; }}
.app-step {{ display:flex; gap: 10px; align-items:flex-start; margin: 0 0 10px; }}
.app-step .n {{ flex:none; width: 26px; height: 26px; border-radius: 50%; background: {A_COL}; color:#fff; font-weight:800; font-size:.8rem;
  display:flex; align-items:center; justify-content:center; }}
.app-step .t1 {{ font-weight: 700; font-size: .88rem; }} .app-step .t2 {{ font-size: .78rem; color: #9AA3B5; }}
.app-onb {{ text-align:center; padding: 6px 4px 2px; }}
.app-onb .logo {{ font-size: 2.4rem; }} .app-onb .h {{ font-size: 1.35rem; font-weight: 800; line-height: 1.2; margin: 4px 0; }}
.app-onb .p {{ font-size: .86rem; color: #9AA3B5; }}
</style>
"""

PLAN = {"A": ("Portfolio A", "Bold · aims for higher returns", "🚀", "a", "High risk"),
        "B": ("Portfolio B", "Steady · plays it safe", "🛡️", "b", "Low risk")}


def app_css() -> None:
    st.html(APP_CSS)


def esc(x) -> str:
    import html as _h
    return _h.escape(str(x))


def hero(label: str, value: str, sub: str = "", tone: str = "") -> None:
    st.html(f"<div class='app-hero {tone}'><div class='l'>{label}</div><div class='v'>{value}</div><div class='s'>{sub}</div></div>")


def section(title: str, extra: str = "") -> None:
    st.html(f"<div class='app-sec'><span class='t'>{title}</span><span class='x'>{extra}</span></div>")


def plan_card(k: str, amount: float, rows: list[tuple[str, str]]) -> None:
    nm, tg, ic, tone, risk = PLAN[k]
    body = "".join(f"<div class='row'><span class='k'>{a}</span><span class='v'>{b}</span></div>" for a, b in rows)
    st.html(f"<div class='app-plan'><div class='top'><div class='ic {tone}'>{ic}</div><div><div class='nm'>{nm} "
            f"<span class='chip {tone}'>{risk}</span></div><div class='tg'>{tg}</div></div>"
            f"<div class='amt'>{inr_short(amount)}</div></div><div class='rows'>{body}</div></div>")


def tiles(items: list[tuple]) -> None:
    """items: (label, value, sub, tone)."""
    st.html("<div class='app-tiles'>" + "".join(
        f"<div class='app-tile {t}'><div class='l'>{l}</div><div class='v'>{v}</div><div class='s'>{s}</div></div>"
        for l, v, s, t in items) + "</div>")


def compare(question: str, a_val: float, b_val: float, a_txt: str, b_txt: str, note: str = "") -> None:
    """A-vs-B bars, like a fintech comparison widget."""
    m = max(abs(a_val), abs(b_val), 1e-12)
    st.html(f"<div class='app-cmp'><div class='q'>{question}</div>"
            f"<div class='ln'><span class='tag' style='background:{A_COL}'>A</span><div class='bar'><span style='width:{abs(a_val) / m * 100:.0f}%;background:{A_COL}'></span></div><span class='val'>{a_txt}</span></div>"
            f"<div class='ln'><span class='tag' style='background:{B_COL}'>B</span><div class='bar'><span style='width:{abs(b_val) / m * 100:.0f}%;background:{B_COL}'></span></div><span class='val'>{b_txt}</span></div>"
            + (f"<div class='note'>{note}</div>" if note else "") + "</div>")


def list_rows(items: list[tuple]) -> None:
    """items: (icon, title, subtitle, right_main, right_sub)."""
    st.html("<div class='app-list'>" + "".join(
        f"<div class='app-li'><div class='ic'>{i}</div><div class='tx'><div class='t1'>{t1}</div><div class='t2'>{t2}</div></div>"
        f"<div class='rt'><div class='r1'>{r1}</div><div class='r2'>{r2}</div></div></div>" for i, t1, t2, r1, r2 in items) + "</div>")


def note(text: str, icon: str = "💡", tone: str = "") -> None:
    st.html(f"<div class='app-note {tone}'><span class='i'>{icon}</span><span>{text}</span></div>")


def verdict(emoji: str, head: str, body: str) -> None:
    st.html(f"<div class='app-verdict'><div class='e'>{emoji}</div><div class='h'>{head}</div><div class='b'>{body}</div></div>")


def chip(text: str, tone: str = "grey") -> str:
    return f"<span class='chip {tone}'>{text}</span>"


def working_header(title: str, sub: str = "") -> None:
    st.markdown(f"#### {title}")
    if sub:
        st.caption(sub)


def short(ev: dict) -> str:
    """Event name for the phone screens: '2008 crash (deepest in the data)' → '2008 crash'."""
    return ev["name"].split(" (")[0] if ev["id"].startswith("auto_") else ev["name"]


def compact_label(eid: str, symbols: list[str], mode: str) -> str:
    """Short dropdown label for the phone: '2008 crash · Nifty −60%'."""
    if eid == "custom":
        return "Choose my own dates…"
    ev = default_results()["events"][eid]
    if not ev["available"]:
        return f"{ev['name'].split(' (')[0]} · not available"
    prob = coverage_problem(eid, symbols, mode)
    tail = ev["label"].split(" · ")[2] if ev["label"].count(" · ") >= 2 else ""
    base = f"{'⭐ ' if eid.startswith('auto_') else ''}{short(ev)}{' · ' + tail if tail else ''}"
    return f"⛔ {base} (needs older data)" if prob and "not supported" not in prob else base
