"""Daily log page for tracking nutrition intake.

Handles date selection, displays nutritional info chart, manages ingredient table,
and provides save/back navigation. Supports async translation synchronization.
"""

import asyncio
import streamlit as st
import datetime as dt

from menu import menu
from handlers.api_handler import check_auth, check_activity, translate_table_ingredients
from handlers.nutrition_table import plot_nutritional_info
from handlers.init_session_state import clear_session_states
import handlers.daily_log_handler as daily_log_handler
from translator import Translator

t = Translator()

check_auth()
menu()

if st.session_state.get("first_daily_log"):
    daily_log_handler.new_date_update()
    st.session_state["first_daily_log"] = False

st.title(t("daily_log.title"))
_, col2 = st.columns([0.8, 0.2])
col2.date_input(
    t("daily_log.select_date"),
    value="today",
    max_value=dt.datetime.now(),
    help=t("daily_log.date_help"),
    on_change=daily_log_handler.new_date_update,
    key="daily_log_date",
)

if not st.session_state.get("table_ingredients"):
    st.info(
        t("daily_log.no_data").format(
            date=st.session_state.get("daily_log_date").strftime("%Y-%m-%d")
        )
    )

plot_nutritional_info()

_, middle, _ = st.columns(3)
with st.container(border=False):

    if middle.button(t("daily_log.save_changes"), width="stretch"):
        with st.spinner(t("ui.processing")):

            asyncio.run(translate_table_ingredients())

            st.session_state["successful_save_daily_log"] = (
                daily_log_handler.save_daily_log(st.session_state.get("daily_log_date"))
            )
            st.session_state["table_ingredients"] = []
            st.session_state["first_daily_log"] = True
        st.rerun()

if middle.button(t("daily_log.back_btn"), width="stretch", key="back_dl"):
    check_activity()
    clear_session_states()
    st.switch_page("pages/home.py")

if st.session_state.get("successful_save_daily_log") is True:
    st.success(
        t("daily_log.success").format(date=st.session_state.get("daily_log_date"))
    )
    st.session_state["successful_save_daily_log"] = None
elif st.session_state.get("successful_save_daily_log") is False:
    st.error(t("daily_log.error").format(date=st.session_state.get("daily_log_date")))
    st.session_state["successful_save_daily_log"] = None
