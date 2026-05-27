"""General statistics page for visualizing user nutrition and weight trends.

Handles date range selection, fetches statistic data from the backend,
and renders comparative charts for weight, calories, proteins, fats,
and carbohydrates. Provides navigation back to home page.
"""
import streamlit as st
import datetime as dt

from menu import menu
from handlers.api_handler import check_auth, check_activity
from handlers.init_session_state import clear_session_states
import handlers.general_stat_handler as general_stat_handler
from translator import Translator

t = Translator()

check_auth()
menu()

st.title(t("general_stat.title"))
_, col2 = st.columns([0.7, 0.3])
date_range = col2.date_input(
    t("general_stat.select_period"),
    value=[
        dt.datetime.now() - dt.timedelta(days=7),
        dt.datetime.now(),
    ],
    max_value=dt.datetime.now(),
    help=t("general_stat.period_help"),
    on_change=general_stat_handler.get_statistic_info,
    key="stat_date_range",
)

if not st.session_state.get("saved_data", False):
    with st.spinner(t("ui.processing")):
        general_stat_handler.get_statistic_info()

if st.session_state.get("stat_data"):
    with st.spinner(t("ui.processing")):
        general_stat_handler.plot_general_stat()

_, middle, _ = st.columns(3)
if middle.button(t("general_stat.back_btn"), width="stretch", key="back_gs"):
    st.session_state["saved_data"] = False
    check_activity()
    clear_session_states()
    st.switch_page("pages/home.py")