"""Page 1 — Home: the 30-second verdict (placeholder until P4)."""
import streamlit as st

from src import ui

ctx = ui.context()
ui.page_header("home", "Does 'safe' stay safe when the market crashes?")
left, right = ui.split()
with left:
    st.write(f"Your amount: {ui.inr(ctx.amount_a)} in A and {ui.inr(ctx.amount_b)} in B.")
    st.write(ctx.crisis_ev["label"])
if right is not None:
    with right:
        ui.flowchart("home")
