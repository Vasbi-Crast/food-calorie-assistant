"""Registration page for new users.

Handles input of user credentials, profile details (gender, age, height, weight),
and fitness goals. Validates input and redirects to login on success.
"""

import streamlit as st

from menu import menu
from handlers.init_session_state import default_session_state
import handlers.register_handler as register_handler
from translator import Translator

t = Translator()

default_session_state()
menu()

st.title(t("register.title"))

st.divider()
st.subheader(t("register.section_login"))

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

st.divider()
st.subheader(t("register.section_profile"))

goal = st.radio(
    t("register.goal.label"),
    options=[
        opt["label"] if isinstance(opt, dict) else opt
        for opt in t("register.goal.options")
    ],
    index=1,
    horizontal=True,
)

gender = st.radio(
    t("register.gender.label"),
    options=[
        opt["label"] if isinstance(opt, dict) else opt
        for opt in t("register.gender.options")
    ],
    index=2,
    horizontal=True,
)

lifestyle_mode = st.radio(
    t("register.lifestyle.label_mode_selector"),
    options=t("register.lifestyle.modes"),
    horizontal=True,
)

if lifestyle_mode == t("settings.lifestyle.modes")[0]:
    lifestyle_description = st.text_area(
        t("settings.lifestyle.text_area.label"),
        placeholder=t("settings.lifestyle.text_area.placeholder"),
        max_chars=300,
    )

else:
    lifestyle_description = st.selectbox(
        t("settings.lifestyle.selector.label"),
        options=[
            opt["label"] if isinstance(opt, dict) else opt
            for opt in t("settings.lifestyle.selector.options")
        ],
        index=0,
        key="lifestyle_r",
    )

age = st.number_input(
    t("register.age.label"),
    min_value=10,
    max_value=120,
    value=None,
    step=1,
    placeholder=t("register.age.placeholder"),
    key="age_r",
)

col1, col2 = st.columns(2)

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

st.divider()

_, middle, _ = st.columns(3)

if middle.button(t("register.sign_up_btn"), width="stretch", key="sign_up_r"):
    with st.spinner(t("ui.processing")):
        if register_handler.registration(
            username=username,
            password=password,
            re_password=re_password,
            age=age,
            lifestyle_description=lifestyle_description,
            goal=goal,
            gender=gender,
            weight=weight,
            height=height,
        ):
            st.switch_page("main_page.py")

if middle.button(t("register.back_btn"), width="stretch", key="back_r"):
    st.switch_page("main_page.py")
