import streamlit as st

from menu import menu
from handlers.init_session_state import default_session_state
import handlers.register_handler as register_handler
from translator import Translator
t = Translator()

default_session_state()
menu()
    
st.title(t("register.title"))
col1, col2 = st.columns(2)

goal = col1.radio(
    t("register.goal.label"),
    options=[opt["label"] if isinstance(opt, dict) else opt for opt in t("register.goal.options")],
    index=1,
)

gender = col2.radio(
    t("register.gender.label"),
    options=[opt["label"] if isinstance(opt, dict) else opt for opt in t("register.gender.options")],
    index=2,
)

age = col1.number_input(
    t("register.age.label"),
    min_value=10,
    max_value=120,
    value=None,
    step=1,
    placeholder=t("register.age.placeholder"),
    key="age_r",
)

lifestyle = col2.selectbox(
    t("register.lifestyle.label"),
    options=[opt["label"] if isinstance(opt, dict) else opt for opt in t("register.lifestyle.options")],
    index=0,
    key="lifestyle_r",
)

weight = col1.number_input(
    t("register.weight.label"),
    min_value=20.0,
    max_value=500.0,
    value=None,
    step=1.0,
    placeholder=t("register.weight.placeholder"),
    format="%.1f",
    key="weight_r",
)

height = col2.number_input(
    t("register.height.label"),
    min_value=50.0,
    max_value=250.0,
    value=None,
    step=1.0,
    placeholder=t("register.height.placeholder"),
    format="%.1f",
    key="height_r",
)

username = st.text_input(
    t("register.username.label"),
    key="username_r",
    placeholder=t("register.username.placeholder"),
    help=t("register.username.pattern"),
)
password = st.text_input(
    t("register.password.label"),
    type="password",
    placeholder=t("register.password.placeholder"),
    key="password_r",
    help=t("register.password.pattern"),
)
re_password = st.text_input(
    t("register.re_password.label"),
    placeholder=t("register.re_password.placeholder"),
    type="password",
)

_, midle, _ = st.columns(3)
if midle.button(t("register.sign_up_btn"), width='stretch', key="sign_up_r"):
    if register_handler.registration(
        username=username,
        password=password,
        re_password=re_password,
        age=age,
        lifestyle=lifestyle,
        goal=goal,
        gender=gender,
        weight=weight,
        height=height,
    ):
        st.switch_page("main_page.py")

if midle.button(t("register.back_btn"), width='stretch', key="back_r"):
    st.switch_page("main_page.py")
