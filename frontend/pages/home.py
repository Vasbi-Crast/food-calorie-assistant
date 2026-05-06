import streamlit as st

from menu import menu
from handlers.api_handler import check_auth, check_activity, log_out
import handlers.home_handler as home_handler
from translator import Translator
t = Translator()

check_auth()
menu()

st.title(t("home.title").format(username=st.session_state["username"]))

if not st.session_state["user_info"]:
    st.session_state["user_info"] = home_handler.get_user_information()
if not st.session_state["days_info"]:
    st.session_state["days_info"] = home_handler.get_info_nutrition()
if not st.session_state["daily_nutrition_norms"]:
    st.session_state["daily_nutrition_norms"] = home_handler.get_nutrition_norms()

home_handler.display_days_nutrition_overview()

left, midle, right = st.columns(3)
if left.button(t("home.view_daily_log"), width='stretch', key="daily_log"):
    check_activity()
    st.switch_page("pages/daily_log.py")

if midle.button(t("home.add_dishes"), width='stretch', key="add_dishes"):
    check_activity()
    st.switch_page("pages/recognition.py")

if right.button(t("home.general_statistics"), width='stretch', key="statistics"):
    check_activity()
    st.switch_page("pages/general_stat.py")

col1, col2 = st.columns(2)
if col1.button(t("home.settings"), width='stretch', key="settings"):
    check_activity()
    st.switch_page("pages/settings.py")
if col2.button(t("home.log_out"), width='stretch', key="log_out"):
    st.session_state["first_start"] = True
    st.switch_page("main_page.py")