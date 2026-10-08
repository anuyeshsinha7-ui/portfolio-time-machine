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
  color: #5B6170; margin: 0 0 .4rem 0; display:flex; align-items:center; gap:.4rem; }}
.ptm-panel-label .dot {{ width:.55rem; height:.55rem; border-radius:50%; display:inline-block; }}
.ptm-card {{ border: 1px solid #E3E6EB; border-radius: 14px; padding: 14px 16px; background: #fff; height: 100%; }}
.ptm-card h4 {{ margin: 0 0 6px 0; font-size: 1rem; }}
.ptm-card .big {{ font-size: 1.7rem; font-weight: 700; line-height: 1.15; }}
.ptm-card .sub {{ color: #5B6170; font-size: .86rem; }}
.ptm-a {{ border-top: 5px solid var(--a); }} .ptm-b {{ border-top: 5px solid var(--b); }}
.ptm-n {{ border-top: 5px solid var(--n); }}
.ptm-crisis {{ border-left: 5px solid var(--crisis); background: #FDF5F5; }}
.ptm-calm {{ border-left: 5px solid var(--calm); background: #F3FAF6; }}
.ptm-concept {{ border: 1px solid #D9DEF0; background: #F6F8FD; border-radius: 14px; padding: 12px 16px; margin: .6rem 0 1rem 0; }}
.ptm-concept .t {{ font-weight: 700; font-size: .95rem; margin-bottom: .35rem; }}
.ptm-concept .k {{ font-size: .7rem; text-transform: uppercase; letter-spacing: .07em; color: #3B4A8C; font-weight: 700; margin-top:.45rem; }}
.ptm-concept p {{ margin: .1rem 0 .2rem 0; font-size: .9rem; }}
.ptm-pill {{ display:inline-block; padding: 2px 9px; border-radius: 999px; font-size: .78rem; font-weight: 600; }}
.ptm-pill.a {{ background: #FCE9E4; color: #9A3B26; }} .ptm-pill.b {{ background: #E3EDFB; color: #1E4F94; }}
.ptm-pill.ok {{ background: #E3F4EA; color: #1F6B40; }} .ptm-pill.bad {{ background: #FBE5E5; color: #8E2424; }}
.ptm-pill.mid {{ background: #FFF3D6; color: #7A5A00; }} .ptm-pill.grey {{ background:#EEF0F3; color:#3F4654; }}
.ptm-verdict {{ font-size: 1.05rem; line-height: 1.5; }}
.ptm-footer {{ color: #6B7280; font-size: .8rem; border-top: 1px solid #E5E7EB; padding-top: .6rem; margin-top: 2rem; }}
.ptm-hero {{ font-size: 1.9rem; font-weight: 750; line-height: 1.2; margin: .2rem 0 .3rem 0; }}
.ptm-tag {{ color:#5B6170; font-size: 1.02rem; margin-bottom: .8rem; }}
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
def split():
    """(left, right): Client view and The Backing; right is None when the Backing is hidden.
    On phones the Backing becomes a tap-to-open section under the client view."""
    if st.session_state.get("phone"):
        left = st.container()
        right = st.expander("📐 The Backing — logic, maths and evidence", expanded=False) \
            if st.session_state.get("show_backing", True) else None
        return left, right
    if not st.session_state.get("show_backing", True):
        c = st.container()
        with c:
            panel_label("Client view", A_COL)
        return c, None
    left, right = st.columns([1.05, 1], gap="large")
    with left:
        panel_label("Client view", A_COL)
    with right:
        panel_label("The Backing — logic, maths and evidence", B_COL)
    return left, right


def panel_label(text: str, colour: str) -> None:
    st.html(f'<div class="ptm-panel-label"><span class="dot" style="background:{colour}"></span>{text}</div>')


def page_header(step_key: str, title: str, subtitle: str = "") -> None:
    step = dict(STEPS).get(step_key, "")
    st.caption(step)
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
    """Pipeline flowchart with the current step highlighted."""
    nodes = [("data", "Yahoo Finance +\nNSE data"), ("clean", "Clean & verify\n(splits, demergers…)")] + \
            [(k, lbl.split(" · ")[1]) for k, lbl in STEPS[:9]]
    lines = ['digraph G { rankdir=LR; bgcolor="transparent"; nodesep=0.25; ranksep=0.25;',
             'node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10, color="#C9CED8", fillcolor="#FFFFFF", fontcolor="#1F2430", margin="0.12,0.06"];',
             'edge [color="#9AA1AE", arrowsize=0.6];']
    for k, lbl in nodes:
        lbl = lbl.replace('"', "'")
        if k == current:
            lines.append(f'"{k}" [label="{lbl}", fillcolor="{A_COL}", fontcolor="white", color="{A_COL}", penwidth=2];')
        else:
            lines.append(f'"{k}" [label="{lbl}"];')
    order = [k for k, _ in nodes]
    for a, b in zip(order[:-1], order[1:]):
        lines.append(f'"{a}" -> "{b}";')
    lines.append("}")
    st.graphviz_chart("\n".join(lines), width="stretch")


def footer() -> None:
    st.html(f"<div class='ptm-footer'>{config.FOOTER.format(date=D.as_of())} · "
            f"<a href='{config.REPO_URL}' target='_blank'>Source code on GitHub</a></div>")


def fig_style(fig: go.Figure, height: int = 380, title: str | None = None) -> go.Figure:
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=40 if title else 10, b=10), title=title,
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0), font=dict(size=12),
                      plot_bgcolor="white", paper_bgcolor="white", hovermode="x unified")
    fig.update_xaxes(gridcolor="#EEF0F3", zeroline=False)
    fig.update_yaxes(gridcolor="#EEF0F3", zeroline=False)
    return fig


def show(fig: go.Figure) -> None:
    if st.session_state.get("phone"):
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
    c1, c2 = st.columns(2)
    for col, kind in ((c1, "crisis"), (c2, "calm")):
        key = f"top_{kind}_{page}"
        opts = event_options(kind)
        s[key] = s[f"{kind}_id"] if s[f"{kind}_id"] in opts else opts[0]
        labels = {e: event_label_for(e, s["pick_A"] + s["pick_B"], s["window_mode"]) for e in opts}
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
    c1, c2 = st.columns(2)
    for col, ev, kind in ((c1, ctx.crisis_ev, "crisis"), (c2, ctx.calm_ev, "calm")):
        w = ev["windows"].get(ctx.mode) or ev["windows"]["standard"]
        col.html(f"<div class='ptm-card ptm-{kind}'><h4>{'🔴' if kind == 'crisis' else '🟢'} {ev['name']}</h4>"
                 f"<div class='sub'>Window used: {w[0]} → {w[1]} ({'standard 252 days' if ctx.mode == 'standard' else 'event only'})</div>"
                 f"<p style='margin:.4rem 0 0'>{ev['story']}</p></div>")


# ---------------------------------------------------------------- phone chrome
TABS = [("home", "🏠", "Home"), ("pick", "🧺", "Pick"), ("test1", "🌪️", "Test 1"), ("test2", "🔁", "Test 2"),
        ("verdict", "✅", "Verdict")]
MORE = [("start", "💰", "Your amount"), ("how", "🧭", "How it works"), ("call", "⚖️", "The risk call"),
        ("weights", "🎯", "Optimum weights"), ("method", "📚", "Methodology & data")]

PHONE_CSS = f"""
<style>
.block-container {{ padding: 4.2rem .85rem 6.5rem .85rem !important; }}
.st-key-ptm_topbar {{ position: sticky; top: 3.1rem; z-index: 990; background: rgba(255,255,255,.96); backdrop-filter: blur(6px);
  border-bottom: 1px solid #E8EAEE; margin: -.6rem -.85rem .6rem -.85rem; padding: .45rem .85rem; }}
.st-key-ptm_topbar p {{ margin: 0; font-size: .82rem; line-height: 1.25; }}
.st-key-ptm_topbar [data-testid="stPopover"] button {{ border-radius: 999px; padding: .25rem .8rem; min-height: 2.4rem; }}
.st-key-ptm_tabbar {{ position: fixed; left: 0; right: 0; bottom: 0; z-index: 999; background: #fff; border-top: 1px solid #E3E6EB;
  box-shadow: 0 -6px 18px rgba(31,36,48,.07); padding: .25rem .2rem calc(.3rem + env(safe-area-inset-bottom)); gap: 0 !important;
  justify-content: space-around; }}
.st-key-ptm_tabbar > div {{ flex: 1 1 0; min-width: 0; }}
.st-key-ptm_tabbar a {{ display: flex !important; flex-direction: column; align-items: center; gap: 0; padding: .3rem .1rem !important;
  border-radius: 12px; min-height: 3rem; justify-content: center; }}
.st-key-ptm_tabbar a p, .st-key-ptm_tabbar a span {{ font-size: .68rem !important; line-height: 1.1; text-align: center; white-space: nowrap; }}
.st-key-ptm_tabbar [data-testid="stPopover"] button {{ border: none; min-height: 3rem; font-size: .7rem; padding: .2rem; width: 100%; }}
.ptm-tab-active a {{ background: #FCE9E4; }}
.ptm-hero, h2 {{ font-size: 1.4rem !important; }}
h4 {{ font-size: 1.05rem !important; }}
.ptm-card {{ border-radius: 16px; box-shadow: 0 2px 10px rgba(31,36,48,.05); margin-bottom: .5rem; }}
.ptm-card .big {{ font-size: 1.45rem; }}
div[data-testid="stExpander"] details {{ border-radius: 14px; border-color: #D9DEF0; background: #F8F9FD; }}
div[data-testid="stExpander"] summary {{ min-height: 3rem; font-weight: 600; }}
button[kind="primary"], button[kind="secondary"] {{ min-height: 2.8rem; border-radius: 12px; }}
[data-testid="stMetricValue"] {{ font-size: 1.35rem; }}
.ptm-footer {{ margin-bottom: 1rem; }}
</style>
"""


def top_bar(page_title: str):
    """Sticky app header: page name, the client's amount, and the ⚙️ settings sheet. Returns the sheet's container."""
    st.html(PHONE_CSS)
    s = st.session_state
    bar = st.container(key="ptm_topbar", horizontal=True, vertical_alignment="center", horizontal_alignment="distribute")
    with bar:
        a, b = amounts()
        st.markdown(f"**⏳ {page_title.split(' — ')[0]}**  \n"
                    f"<span style='color:#5B6170'>A {inr_short(a)} · B {inr_short(b)}</span>", unsafe_allow_html=True)
        sheet = st.popover("⚙️", width="content", help="Settings: amount, events, confidence, horizon")
    return sheet


def tab_bar(pages: dict, current_title: str) -> None:
    """Fixed bottom navigation, like a phone app."""
    bar = st.container(key="ptm_tabbar", horizontal=True)
    with bar:
        for key, icon, label in TABS:
            st.page_link(pages[key], label=label, icon=icon)
        with st.popover("☰", width="stretch", help="More pages"):
            for key, icon, label in MORE:
                st.page_link(pages[key], label=label, icon=icon)
