# Decisions and defaults

Every default chosen without asking the team. ⚠️ marks an item the team should double-check before presenting.

## Environment and stack

1. **Python 3.13 locally, not 3.11/3.12.** stlite 1.9.2 (latest release, 23 Sep 2026) runs Pyodide 0.29.3, which is Python 3.13.2 and ships a `cp313` Streamlit wheel. Using 3.13 locally keeps the offline backup (`streamlit run app.py`) and the browser on the same interpreter. Conda env: `fra`.
2. **Pinned versions.** stlite `@stlite/browser@1.9.2`; Streamlit 1.62.0 (the wheel bundled in that stlite release); pandas 2.3.3, NumPy 2.2.5, SciPy 1.14.1 (the Pyodide 0.29.3 builds); Plotly 5.24.1 and openpyxl 3.1.5 (pure-Python wheels installed from PyPI in the browser). Plotly 5.x follows stlite's own advice to avoid a micropip resolution clash with Altair.
3. **Risk-free rate = 5.5747% a year**, the 91-day Treasury bill implicit yield at cut-off in the Reserve Bank of India (RBI) auction of 7 Oct 2026 (press release 2026-2027/1268, <https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=63746>). Used as a constant annual rate for Sharpe and Sortino ratios in every window (historical windows are compared on today's hurdle so only the market data changes).
