import streamlit as st

pages = {
    "Pair trading": [
        st.Page("src/pages/arb_stat_screener.py", title="Screener"),
        st.Page("src/pages/arb_stat_chart_history.py", title="Chart history"),
        st.Page("src/pages/arb_stat_position.py", title="Position info"),
    ],
}

pg = st.navigation(pages)
pg.run()