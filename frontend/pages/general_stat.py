import streamlit as st
import datetime as dt

from menu import menu
from handlers.api_handler import check_auth, check_activity
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
if not st.session_state["saved_data"]:
    general_stat_handler.get_statistic_info()
if st.session_state["stat_data"]:
    general_stat_handler.plot_general_stat()
_, midle, _ = st.columns(3)
if midle.button(t("general_stat.back_btn"), width='stretch', key="back_gs"):
    check_activity()
    st.session_state["saved_data"] = False
    st.switch_page("pages/home.py")