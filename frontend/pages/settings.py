"""Settings page for managing user profile and preferences.

Allows updating user information (age, weight, height, goal, lifestyle),
visualizes current settings, and handles saving changes via the handler.
"""

import streamlit as st

from menu import menu
from handlers.api_handler import check_auth, check_activity
from handlers.init_session_state import clear_session_states
import handlers.settings_handler as settings_handler
from translator import Translator

t = Translator()

check_auth()
menu()

def_inf = st.session_state.get("user_info", {})

st.title(t("settings.title"))

goal = st.radio(
    t("settings.goal.label"),
    options=[
        opt["label"] if isinstance(opt, dict) else opt
        for opt in t("settings.goal.options")
    ],
    index=settings_handler.index_goal(def_inf.get("goal")),
    horizontal=True,
)

gender = st.radio(
    t("settings.gender.label"),
    options=[
        opt["label"] if isinstance(opt, dict) else opt
        for opt in t("settings.gender.options")
    ],
    index=settings_handler.index_gender(def_inf.get("gender")),
    horizontal=True,
)

lifestyle_mode = st.radio(
    t("settings.lifestyle.label_mode_selector"),
    options=t("settings.lifestyle.modes"),
    horizontal=True,
    index=0 if def_inf.get("lifestyle_description") else 1,
)

if lifestyle_mode == t("settings.lifestyle.modes")[0]:
    lifestyle_description = st.text_area(
        t("settings.lifestyle.text_area.label"),
        placeholder=t("settings.lifestyle.text_area.placeholder"),
        max_chars=300,
        value=def_inf.get("lifestyle_description"),
    )

else:
    lifestyle_description = st.selectbox(
        t("settings.lifestyle.selector.label"),
        options=[
            opt["label"] if isinstance(opt, dict) else opt
            for opt in t("settings.lifestyle.selector.options")
        ],
        index=settings_handler.index_lifestyle(def_inf.get("bmr")),
        key="lifestyle_s",
    )

age = st.number_input(
    t("settings.age.label"),
    min_value=10,
    max_value=120,
    value=def_inf.get("age"),
    step=1,
    placeholder=t("settings.age.placeholder"),
    key="age_s",
)

col1, col2 = st.columns(2)

weight = col1.number_input(
    t("settings.weight.label"),
    min_value=20.0,
    max_value=500.0,
    value=def_inf.get("weight"),
    step=1.0,
    placeholder=t("settings.weight.placeholder"),
    format="%.1f",
    key="weight_set",
)

height = col2.number_input(
    t("settings.height.label"),
    min_value=50.0,
    max_value=250.0,
    value=def_inf.get("height"),
    step=1.0,
    placeholder=t("settings.height.placeholder"),
    format="%.1f",
    key="height_set",
)

_, middle, _ = st.columns(3)
if middle.button(t("settings.apply_btn"), width="stretch", key="apply_set"):
    check_activity()
    with st.spinner(t("ui.processing")):
        if settings_handler.update_user_info(
            age=age,
            lifestyle_description=lifestyle_description,
            goal=goal,
            gender=gender,
            weight=weight,
            height=height,
        ):
            st.session_state["user_info"] = None
            st.session_state["daily_nutrition_norms"] = None
            st.switch_page("pages/home.py")

if middle.button(t("settings.back_btn"), width="stretch", key="back_set"):
    check_activity()
    clear_session_states()
    st.switch_page("pages/home.py")
