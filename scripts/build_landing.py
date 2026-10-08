"""Static landing page (_site/index.html), generated from results/default.json at build time.

Plain HTML + a few lines of inline JavaScript (no libraries) so it loads instantly on a phone. Rupee figures are stored as
fractions in data attributes and re-multiplied by the amount the visitor types; the button passes that amount to the
dashboard as ?amount=…
"""
from __future__ import annotations

import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src import config  # noqa: E402
from src import recommend as RC  # noqa: E402
from src.fmt import inr, inr_short, pct  # noqa: E402

AMT = config.AMOUNT_A


def rs(frac: float) -> str:
    """A rupee figure that the page's script re-computes for the visitor's amount."""
    return f"<b class='rs' data-f='{frac:.8f}'>{inr_short(frac * AMT)}</b>"


def sparkline(values, colour, w=300, h=70) -> str:
    v = [x for x in values if x is not None]
    lo, hi = min(v), max(v)
    pts = " ".join(f"{i * w / (len(v) - 1):.1f},{h - (x - lo) / (hi - lo + 1e-12) * (h - 6) - 3:.1f}" for i, x in enumerate(v))
    return f"<polyline fill='none' stroke='{colour}' stroke-width='2' points='{pts}'/>"


def main(site: Path) -> None:
    res = json.loads((config.RESULTS_DIR / "default.json").read_text())
    off = res["official"]
    crisis = res["regimes"][f"{off['crisis']}|standard"]
    calm = res["regimes"][f"{off['calm']}|standard"]
    cur = res["current"]
    board = res["scoreboard"]["standard"]
    ev_c = res["events"][off["crisis"]]
    P = res["portfolios"]
    lv = RC.label_verdict(crisis, calm, board)
    bv = RC.b_verdict(crisis, board)
    a, b = crisis["A"], crisis["B"]
    ea, eb = a["risk"]["Historical"]["0.99"]["es"], b["risk"]["Historical"]["0.99"]["es"]
    t2 = crisis["A"]["test2"]
    p95 = res["bootstrap"]["A"]["turnover_p95"]
    findings = [
        f"In the {ev_c['name']}, Portfolio A's 1-day 99% Expected Shortfall was {pct(ea)} ({rs(ea)} on your "
        f"<span class='amt'>{inr_short(AMT)}</span>) vs {pct(eb)} for B ({rs(eb)}) — the high-risk label "
        f"{'held' if RC.label_holds(a, b) else 'did not hold'}.",
        f"Bought at the start of that window, A would have fallen as far as {rs(a['replay']['largest_fall'])} and B {rs(b['replay']['largest_fall'])}; "
        f"the Nifty 50 lost {pct(crisis['nifty']['largest_fall'])}. Across all {len(board)} events tested, the high-risk label held in "
        f"<b>{lv['events_held']}</b> and B beat the Nifty 50 in {bv['crises_held']} of {bv['crises_total']} crises.",
        f"Re-optimising for today's target return with that period's data would have meant trading {pct(t2['turnover'], 0)} of A "
        f"({rs(t2['turnover'])}) — {'more' if t2['turnover'] > p95 else 'less'} than estimation noise alone produces ({pct(p95, 0)}).",
    ]
    cards = []
    for k, nm, col in (("A", "High risk — going for return", config.COLOR_A), ("B", "Low risk — playing it safe", config.COLOR_B)):
        p = P[k]
        r = crisis[k]
        ind = ", ".join(list(p["industry_weights"])[:3])
        cards.append(f"""
      <div class="card" style="border-top-color:{col}">
        <div class="k">Portfolio {k}</div><div class="nm">{nm}</div>
        <div class="big"><span class="amt">{inr_short(AMT)}</span></div>
        <ul>
          <li>{len(p['symbols'])} stocks · {html.escape(ind)}…</li>
          <li>Beta {res['evidence'][k]['weighted_beta']:.2f} · volatility {pct(res['evidence'][k]['portfolio_vol'])}</li>
          <li>Bad day today (99% VaR): {rs(cur[k]['risk']['Historical']['0.99']['var'])}</li>
          <li>Worst fall in the {html.escape(ev_c['name'])}: {rs(r['replay']['largest_fall'])}</li>
        </ul>
        <svg viewBox="0 0 300 70" class="spark" aria-label="Value path in the crisis">{sparkline(r['replay']['value'], col)}</svg>
        <div class="cap">₹ path through the crisis window (buy and hold)</div>
      </div>""")
    steps = ["Your amount", "Nifty 200 data, cleaned & verified", "Risk label: beta + volatility", "Optimum weights",
             "Test #1: VaR & ES in crisis / calm", "Test #2: re-optimise in each period", "Verdict"]
    flow = "".join(f"<div class='step'><span>{i}</span>{html.escape(s)}</div>" + ("<div class='arr'>→</div>" if i < len(steps) - 1 else "")
                   for i, s in enumerate(steps))
    presets = "".join(f"<button type='button' class='chip' data-v='{v}'>{inr_short(v)}</button>" for v in config.AMOUNT_PRESETS)
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{config.APP_NAME} — does 'safe' stay safe when the market crashes?</title>
<meta name="description" content="A Financial Risk Analytics project: two Nifty 200 portfolios (high risk, low risk) sent back to real Indian market crises. VaR, Expected Shortfall and Markowitz re-optimisation.">
<meta name="theme-color" content="#ffffff">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>⏳</text></svg>">
<style>
:root {{ --a:{config.COLOR_A}; --b:{config.COLOR_B}; --n:{config.COLOR_NIFTY}; --ink:#1F2430; --mut:#5B6170; --bg:#FFFFFF; --panel:#F5F6F8; --line:#E3E6EB; }}
* {{ box-sizing: border-box; }}
body {{ margin:0; background:var(--bg); color:var(--ink); font: 16px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }}
main {{ max-width: 1080px; margin: 0 auto; padding: 28px 16px 48px; }}
.eyebrow {{ color: var(--mut); font-size: .85rem; letter-spacing: .06em; text-transform: uppercase; font-weight: 700; }}
h1 {{ font-size: clamp(1.8rem, 5vw, 2.8rem); line-height: 1.12; margin: .3rem 0 .6rem; }}
.lede {{ color: var(--mut); font-size: 1.08rem; max-width: 760px; }}
.verdict {{ margin: 18px 0; padding: 16px 18px; border-radius: 16px; background: var(--panel); font-size: 1.08rem; }}
.verdict b.v {{ color: #1F6B40; }}
.cta {{ display:flex; flex-wrap:wrap; gap:10px; align-items:flex-end; margin: 18px 0 8px; padding: 16px; border:1px solid var(--line); border-radius:16px; }}
.cta label {{ font-weight: 700; display:block; margin-bottom: 6px; }}
.cta input {{ font-size: 1.1rem; padding: 12px 14px; border-radius: 12px; border:1px solid #C9CED8; width: 220px; max-width: 100%; }}
.cta .go {{ background: var(--a); color: #fff; border: 0; border-radius: 12px; padding: 13px 18px; font-size: 1.05rem; font-weight: 700; text-decoration:none; display:inline-block; }}
.chips {{ display:flex; flex-wrap:wrap; gap:6px; width: 100%; }}
.chip {{ border:1px solid var(--line); background:#fff; border-radius:999px; padding:6px 12px; font-size:.9rem; cursor:pointer; }}
.err {{ color:#8E2424; font-size:.9rem; width:100%; min-height:1.2em; }}
.cards {{ display:grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 14px; margin: 18px 0; }}
.card {{ border:1px solid var(--line); border-top: 6px solid; border-radius: 16px; padding: 14px 16px; }}
.card .k {{ font-weight:800; }} .card .nm {{ color: var(--mut); font-size:.92rem; }}
.card .big {{ font-size: 1.9rem; font-weight: 800; margin: 4px 0; }}
.card ul {{ padding-left: 1.1rem; margin: .3rem 0; }} .card li {{ margin: .15rem 0; }}
.spark {{ width:100%; height:70px; background: var(--panel); border-radius: 10px; }}
.cap {{ color: var(--mut); font-size: .78rem; }}
h2 {{ font-size: 1.3rem; margin: 28px 0 8px; }}
ol.f li {{ margin: .45rem 0; }}
.flow {{ display:flex; flex-wrap:wrap; align-items:center; gap:6px; }}
.step {{ border:1px solid var(--line); border-radius:12px; padding:8px 10px; font-size:.9rem; background:#fff; }}
.step span {{ display:inline-block; width:20px; height:20px; border-radius:50%; background:var(--a); color:#fff; font-size:.75rem; text-align:center; line-height:20px; margin-right:6px; }}
.arr {{ color: var(--mut); }}
footer {{ margin-top: 36px; color: var(--mut); font-size: .85rem; border-top: 1px solid var(--line); padding-top: 12px; }}
a {{ color: var(--b); }}
@media (max-width: 600px) {{ .arr {{ display:none; }} .flow {{ flex-direction: column; align-items: stretch; }} .cta input {{ width:100%; }} .cta .go {{ width:100%; text-align:center; }} }}
</style></head>
<body><main>
  <div class="eyebrow">Financial Risk Analytics · group project · data as of {res['as_of']}</div>
  <h1>{config.APP_NAME}: does 'safe' stay safe when the market crashes?</h1>
  <p class="lede">We built a <b style="color:var(--a)">high-risk</b> and a <b style="color:var(--b)">low-risk</b> portfolio from today's
  Nifty 200, then sent both back in time to real Indian market crises and calm spells — 2008, COVID-19, the taper tantrum and more —
  to test whether the labels, and the weights, survive.</p>
  <div class="verdict">30-second verdict: the high-risk label <b class="v">{'held' if lv['verdict'] != 'No' else 'did not hold'}</b>
  ({lv['events_held']} of {lv['events_total']} historical events); 'safe' stayed <b class="v">{ {'Yes': 'safe', 'Partly': 'mostly safe', 'No': 'not so safe'}[bv['verdict']] }</b>
  (B beat the Nifty 50 in {bv['crises_held']} of {bv['crises_total']} crises).</div>
  <form class="cta" id="f" action="app/" method="get" onsubmit="return go()">
    <div><label for="amt">How much would you invest?</label>
    <input id="amt" inputmode="numeric" autocomplete="off" value="{inr(AMT)}" aria-describedby="err"></div>
    <a class="go" id="go" href="app/?amount={AMT}">Open the interactive dashboard →</a>
    <div class="chips">{presets}</div>
    <div class="err" id="err" role="alert"></div>
  </form>
  <div class="cards">{''.join(cards)}</div>
  <h2>Three headline findings</h2>
  <ol class="f">{''.join(f'<li>{x}</li>' for x in findings)}</ol>
  <h2>How it works</h2>
  <div class="flow">{flow}</div>
  <p class="cap" style="margin-top:10px">Prices from Yahoo Finance, checked day-by-day against NSE's official closes; every split, bonus,
  rights issue and demerger rebuilt from NSE records. VaR and Expected Shortfall by four methods; Markowitz optimisation with SciPy.
  The dashboard runs Python in your browser (first load ≈ 15–30 s).</p>
  <footer>{config.FOOTER.format(date=res['as_of'])} · Team: {', '.join(config.TEAM)} · {config.CREDIT_LINE} ·
  <a href="{config.REPO_URL}">GitHub repository</a></footer>
</main>
<script>
const LAKH=1e5, CR=1e7, MIN={config.AMOUNT_MIN}, MAX={config.AMOUNT_MAX};
function grp(n){{n=Math.round(n);const s=String(n);if(s.length<=3)return s;let h=s.slice(0,-3),t=s.slice(-3),p=[];while(h.length>2){{p.unshift(h.slice(-2));h=h.slice(0,-2)}}if(h)p.unshift(h);return p.join(',')+','+t}}
function trim(x){{return (Math.round(x*100)/100).toString()}}
function short(v){{return v>=CR?'₹'+trim(v/CR)+' crore':v>=LAKH?'₹'+trim(v/LAKH)+' lakh':'₹'+grp(v)}}
function parse(t){{t=(t||'').toLowerCase().replace(/₹|rs\\.?|inr|,|\\s/g,'');const m=t.match(/^(\\d+(?:\\.\\d+)?)(crore|cr|lakhs?|lacs?|l|k)?$/);if(!m)return null;
 const u={{crore:CR,cr:CR,lakh:LAKH,lakhs:LAKH,lac:LAKH,lacs:LAKH,l:LAKH,k:1e3}}[m[2]]||1;return parseFloat(m[1])*u}}
function update(v){{const e=document.getElementById('err'),g=document.getElementById('go');
 if(v===null){{e.textContent="That doesn't look like an amount — try 15,00,000 or 15 lakh.";return}}
 if(v<MIN||v>MAX){{e.textContent='Please enter between ₹'+grp(MIN)+' and ₹100 crore.';return}}
 e.textContent='';g.href='app/?amount='+Math.round(v);
 document.querySelectorAll('.rs').forEach(x=>x.textContent=short(parseFloat(x.dataset.f)*v));
 document.querySelectorAll('.amt').forEach(x=>x.textContent=short(v));}}
const inp=document.getElementById('amt');inp.addEventListener('input',()=>update(parse(inp.value)));
document.querySelectorAll('.chip').forEach(c=>c.addEventListener('click',()=>{{inp.value='₹'+grp(+c.dataset.v);update(+c.dataset.v)}}));
function go(){{const v=parse(inp.value);if(v===null||v<MIN||v>MAX){{update(v);return false}}location.href='app/?amount='+Math.round(v);return false}}
</script>
</body></html>"""
    (site / "index.html").write_text(page)


if __name__ == "__main__":
    main(ROOT / "_site")
