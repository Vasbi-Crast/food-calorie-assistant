import streamlit as st

from menu import menu
from handlers.api_handler import check_auth, check_activity
import handlers.settings_handler as settings_handler
from translator import Translator
t = Translator()

check_auth()
menu()

def_inf = st.session_state["user_info"]

st.title(t("settings.title"))

col1, col2 = st.columns(2)

goal = col1.radio(
    t("settings.goal.label"),
    options=[opt["label"] if isinstance(opt, dict) else opt for opt in t("settings.goal.options")],
    index=settings_handler.index_goal(def_inf.get("goal")),
)

gender = col2.radio(
    t("settings.gender.label"),
    options=[opt["label"] if isinstance(opt, dict) else opt for opt in t("settings.gender.options")],
    index=settings_handler.index_gender(def_inf.get("gender")),
)

age = col1.number_input(
    t("settings.age.label"),
    min_value=10,
    max_value=120,
    value=def_inf.get("age"),
    step=1,
    placeholder=t("settings.age.placeholder"),
    key="age_set",
)

lifestyle = col2.selectbox(
    t("settings.lifestyle.label"),
    options=[opt["label"] if isinstance(opt, dict) else opt for opt in t("settings.lifestyle.options")],
    index=settings_handler.index_lifestyle(def_inf.get("bmr")),
    key="lifestyle_set",
)

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

_, midle, _ = st.columns(3)
if midle.button(t("settings.apply_btn"), width='stretch', key="apply_set"):
    check_activity()
    if settings_handler.update_user_info( 
        age=age, 
        lifestyle=lifestyle, 
        goal=goal, 
        gender=gender, 
        weight=weight, 
        height=height
    ):
        st.session_state["user_info"] = {
            "age": age,
            "lifestyle": lifestyle,
            "bmr": settings_handler.get_db_value(lifestyle, "settings.lifestyle.options", 1.2),
            "goal": settings_handler.get_db_value(goal, "settings.goal.options", "weight_maintenance"),
            "gender": settings_handler.get_db_value(gender, "settings.gender.options", "None"),
            "weight": weight,
            "height": height,
        }
        st.session_state["daily_nutrition_norms"] = None
        st.switch_page("pages/home.py")

_, midle, _ = st.columns(3)
if midle.button(t("settings.back_btn"), width='stretch', key="back_set"):
    check_activity()
    st.switch_page("pages/home.py")