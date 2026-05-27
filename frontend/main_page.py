"""Main login page for the calorie tracker application.

Handles user authentication interface, session initialization,
and navigation to registration or home pages.
"""
import streamlit as st

from handlers.init_session_state import default_session_state
import handlers.main_page_handler as main_page_handler
from handlers.api_handler import log_out
from menu import menu
from translator import Translator

t = Translator()

default_session_state()
log_out()

menu()

st.title(t("login.title"))

username = st.text_input(
    t("login.username"), placeholder=t("login.username"), key="username_l"
)
password = st.text_input(
    t("login.password"),
    placeholder=t("login.password"),
    type="password",
    key="password_l",
)

_, middle, _ = st.columns(3)

if middle.button(t("login.sign_in_btn"), width="stretch"):
    if main_page_handler.authorization(username, password):
        st.session_state["username"] = username
        st.switch_page("pages/home.py")

if middle.button(t("login.sign_up_btn"), width="stretch", key="sign_up_l"):
    st.switch_page("pages/register.py")

if st.session_state.get("auth_error"):
    st.warning(st.session_state["auth_error"])
    st.session_state["auth_error"] = ""