import streamlit as st
import datetime as dt

from menu import menu
from handlers.api_handler import check_auth, check_activity
import handlers.daily_log_handler as daily_log_handler
from translator import Translator
t = Translator()

check_auth()
menu()

st.title(t("daily_log.title"))
_, col2 = st.columns([0.8, 0.2])
date = col2.date_input(
    t("daily_log.select_date"),
    value="today",
    max_value=dt.datetime.now(),
    help=t("daily_log.date_help"),
)

result = daily_log_handler.get_daily_log(date)
if result is not None:
    st.session_state["table_ingredients"] = result
else:
    st.session_state["table_ingredients"] = []
    st.info(t("daily_log.no_data").format(date=date.strftime("%Y-%m-%d")))

with st.form(clear_on_submit=True, border=False, key="data_form"):
    st.session_state["name_table_widget"] = "log_widget_table"
    daily_log_handler.daily_nutritional_table()
    _, midle, _ = st.columns(3)
    if midle.form_submit_button(t("daily_log.save_changes"), width='stretch'):
        if daily_log_handler.change_daily_log(date):
            st.session_state["saved_data"] = True
            st.rerun()

_, midle, _ = st.columns(3)
if midle.button(t("daily_log.back_btn"), width='stretch', key="back_dl"):
    st.session_state["table_ingredients"] = None
    st.session_state["name_table_widget"] = ""
    st.session_state["days_info"] = None
    st.session_state["saved_data"] = False
    check_activity()
    st.switch_page("pages/home.py")