import streamlit as st
from PIL import Image
from io import BytesIO
import base64

from translator import Translator
import ui_plots as uipl
import ui_processing as uipr

# === Session State Initialization ===
if "username" not in st.session_state:
    st.session_state["username"] = ""
if "user_info" not in st.session_state:
    st.session_state["user_info"] = None
if "days_info" not in st.session_state:
    st.session_state["days_info"] = None
if "daily_nutrition_norms" not in st.session_state:
    st.session_state["daily_nutrition_norms"] = None
if "table_ingredients" not in st.session_state:
    st.session_state["table_ingredients"] = None
if "total_macros" not in st.session_state:
    st.session_state["total_macros"] = None
if "last_deleted" not in st.session_state:
    st.session_state["last_deleted"] = []
if "saved_data" not in st.session_state:
    st.session_state["saved_data"] = False
if "empty_day" not in st.session_state:
    st.session_state["empty_day"] = False
if "stat_data" not in st.session_state:
    st.session_state["stat_data"] = {
        "weight": None,
        "info_nutrition": None,
        "norms": None,
    }
if "language" not in st.session_state:
    st.session_state["language"] = "ru"
if "first_start" not in st.session_state:
    st.session_state["first_start"] = True

if "auth_error" not in st.session_state:
    st.session_state["auth_error"] = ""
if "last_active_time" not in st.session_state:
    st.session_state["last_active_time"] = None

if "login_page_sh" not in st.session_state:
    st.session_state["login_page_sh"] = True
if "register_page_sh" not in st.session_state:
    st.session_state["register_page_sh"] = False

if "home_page_sh" not in st.session_state:
    st.session_state["home_page_sh"] = False
if "daily_log_sh" not in st.session_state:
    st.session_state["daily_log_sh"] = False
if "recognition_page_sh" not in st.session_state:
    st.session_state["recognition_page_sh"] = False
if "general_stat_sh" not in st.session_state:
    st.session_state["general_stat_sh"] = False
if "settings_sh" not in st.session_state:
    st.session_state["settings_sh"] = False

t = Translator()

def language_selector():
    """
    Displays language selector in sidebar.
    Available on all pages.
    """
    if not st.session_state["first_start"]:
        st.set_page_config(page_title="Food Assistant",
                           initial_sidebar_state="collapsed",
                           page_icon = "./icons8-chinese-noodle-100.png")
    else:
        st.set_page_config(page_title="Food Assistant",
                           page_icon = "./icons8-chinese-noodle-100.png")
        st.session_state["first_start"] = False

    with st.sidebar:
        st.divider()
        current_lang = st.session_state.get("language", "ru")
        selected_lang = st.selectbox(
            label="🌍 Language / Язык",
            options=t.available_languages,
            format_func=lambda x: {
                "en": "🇬🇧 English",
                "ru": "🇷🇺 Русский",
            }.get(x, x),
            index=t.available_languages.index(current_lang),
            key="language_selector",
        )

        if selected_lang != current_lang:
            t.set_language(selected_lang)
            st.rerun()

def login_page():
    """Authorization page"""
    st.title(t("login.title"))

    username = st.text_input(
        t("login.username"), placeholder=t("login.username"), key="username_l"
    )
    password = st.text_input(
        t("login.password"), placeholder=t("login.password"), type="password", key="password_l"
    )
    _, midle, _ = st.columns(3)
    if midle.button(t("login.sign_in_btn"), use_container_width=True):
        if uipr.authorization("login_page_sh", username, password):
            st.session_state["username"] = username
            uipr.change_page("login_page_sh", "home_page_sh")

    if midle.button(t("login.sign_up_btn"), use_container_width=True, key="sign_up_l"):
        uipr.change_page("login_page_sh", "register_page_sh")
    if st.session_state["auth_error"]:
        st.warning(st.session_state["auth_error"])
        st.session_state["auth_error"] = ""


def registration_page():
    """Registration page"""
    st.title(t("register.title"))

    gender = st.radio(
        t("register.gender.label"),
        t("register.gender.options"),
        index=2,
    )

    col1, col2 = st.columns(2)

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
        options=t("register.lifestyle.options"),
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
    if midle.button(t("register.sign_up_btn"), use_container_width=True, key="sign_up_r"):
        if uipr.registration(
            "register_page_sh",
            username,
            password,
            re_password,
            age,
            lifestyle,
            gender,
            weight,
            height,
        ):
            uipr.change_page("register_page_sh", "login_page_sh")

    if midle.button(t("register.back_btn"), use_container_width=True, key="back_r"):
        uipr.change_page("register_page_sh", "login_page_sh")


def home_page():
    """Home page containing information about today's consumption"""
    st.title(t("home.title").format(username=st.session_state["username"]))

    if not st.session_state["user_info"]:
        st.session_state["user_info"] = uipr.get_user_information("home_page_sh")
    if not st.session_state["days_info"]:
        st.session_state["days_info"] = uipr.get_info_nutrition("home_page_sh")
    if not st.session_state["daily_nutrition_norms"]:
        st.session_state["daily_nutrition_norms"] = uipr.get_nutrition_norms("home_page_sh")

    uipl.display_days_nutrition_overview()

    left, midle, right = st.columns(3)
    if left.button(t("home.view_daily_log"), use_container_width=True, key="daily_log"):
        uipr.change_page("home_page_sh", "daily_log_sh")
    if midle.button(t("home.add_dishes"), use_container_width=True, key="add_dishes"):
        uipr.change_page("home_page_sh", "recognition_page_sh")
    if right.button(t("home.general_statistics"), use_container_width=True, key="statistics"):
        uipr.change_page("home_page_sh", "general_stat_sh")

    col1, col2 = st.columns(2)
    if col1.button(t("home.settings"), use_container_width=True, key="settings"):
        uipr.change_page("home_page_sh", "settings_sh")
    if col2.button(t("home.log_out"), use_container_width=True, key="log_out"):
        st.session_state["first_start"] = True
        uipr.change_page("home_page_sh", "login_page_sh")


def recognition_page():
    """A page containing the functionality for calculating the macros from a photo"""
    st.title(t("recognition.title"))

    st.config.set_option("server.maxUploadSize", 3)
    uploaded_file = st.file_uploader(
        t("recognition.choose_image"),
        on_change=uipr.clear_new_uploader,
        type=["jpg", "jpeg", "png"],
        key="file_loader",
    )

    if uploaded_file:
        try:
            img = Image.open(uploaded_file)
            st.image(img, use_column_width=True)

            buffered = BytesIO()
            img.save(buffered, format="JPEG")
            image_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

        except Exception as e:
            st.error(t("recognition.failed_image"))
            image_base64 = None

    user_description = st.text_input(
        t("recognition.describe_dish"), max_chars=250
    )

    if st.session_state["table_ingredients"] is not None:
        uipl.plot_nutritional_info()

    _, midle, _ = st.columns(3)

    if st.session_state["table_ingredients"]:
        text = t("recognition.save_dish")
    else:
        text = t("recognition.upload")

    if midle.button(text, use_container_width=True):
        if text == t("recognition.save_dish"):
            if uipr.save_dish("recognition_page_sh"):
                st.session_state["table_ingredients"] = None
                st.session_state["total_macros"] = None
                uipr.change_page("recognition_page_sh", "home_page_sh")
            else:
                st.error(t("recognition.failed_save"))
        else:
            if image_base64:
                nutritional_info = uipr.get_meal_macros(
                    "recognition_page_sh", image_base64, user_description
                )
                if nutritional_info:
                    uipr.parse_dish(nutritional_info)
                    st.rerun()
            else:
                st.error(t("recognition.please_upload"))

    if midle.button(t("recognition.back_btn"), use_container_width=True, key="back_rec"):
        st.session_state["table_ingredients"], st.session_state["total_macros"] = None, None
        st.session_state["last_deleted"] = []
        uipr.change_page("recognition_page_sh", "home_page_sh")


def daily_log_page():
    st.title(t("daily_log.title"))
    _, col2 = st.columns([0.8, 0.2])
    date = col2.date_input(
        t("daily_log.select_date"),
        value="today",
        max_value=uipr.dt.datetime.now(),
        help=t("daily_log.date_help"),
    )

    result = uipr.get_daily_log(date, "daily_log_page")
    if result is not None:
        st.session_state["table_ingredients"] = result
    else:
        st.session_state["table_ingredients"] = []
        st.info(t("daily_log.no_data").format(date=date.strftime("%Y-%m-%d")))

    with st.form(clear_on_submit=True, border=False, key="data_form"):
        uipl.daily_nutritional_table()
        _, midle, _ = st.columns(3)
        if midle.form_submit_button(t("daily_log.save_changes"), use_container_width=True):
            if uipr.change_daily_log(date, "daily_log_page"):
                st.session_state["saved_data"] = True
                st.rerun()

    _, midle, _ = st.columns(3)
    if midle.button(t("daily_log.back_btn"), use_container_width=True, key="back_dl"):
        st.session_state["table_ingredients"] = None
        st.session_state["days_info"] = None
        st.session_state["saved_data"] = False
        uipr.change_page("daily_log_sh", "home_page_sh")


def general_stat_page():
    st.title(t("general_stat.title"))
    _, col2 = st.columns([0.7, 0.3])
    date_range = col2.date_input(
        t("general_stat.select_period"),
        value=[
            uipr.dt.datetime.now() - uipr.dt.timedelta(days=7),
            uipr.dt.datetime.now(),
        ],
        max_value=uipr.dt.datetime.now(),
        help=t("general_stat.period_help"),
        on_change=uipr.get_statistic_info(),
        key="stat_date_range",
    )
    if not st.session_state["saved_data"]:
        uipr.get_statistic_info()
    if st.session_state["stat_data"]:
        uipl.plot_general_stat()
    _, midle, _ = st.columns(3)
    if midle.button(t("general_stat.back_btn"), use_container_width=True, key="back_gs"):
        st.session_state["saved_data"] = False
        uipr.change_page("general_stat_sh", "home_page_sh")


def settings_page():
    def_inf = st.session_state["user_info"]

    st.title(t("settings.title"))

    gender = st.radio(
        t("settings.gender.label"),
        t("settings.gender.options"),
        index=uipr.index_gender(def_inf.get("gender")),
    )

    col1, col2 = st.columns(2)

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
        options=t("settings.lifestyle.options"),
        index=uipr.index_lifestyle(def_inf.get("lifestyle")),
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
    if midle.button(t("settings.apply_btn"), use_container_width=True, key="apply_set"):
        if uipr.update_user_info("settings_sh", age, lifestyle, gender, weight, height):
            if gender == ":blue[Man]":
                gender_stored = "m"
            elif gender == ":red[Woman]":
                gender_stored = "w"
            else:
                gender_stored = "None"

            st.session_state["user_info"] = {
                "age": age,
                "lifestyle": lifestyle,
                "bmr": uipr.bmr.get(lifestyle),
                "gender": gender_stored,
                "weight": weight,
                "height": height,
            }
            st.session_state["daily_nutrition_norms"] = None
            uipr.change_page("settings_sh", "home_page_sh")

    _, midle, _ = st.columns(3)
    if midle.button(t("settings.back_btn"), use_container_width=True, key="back_set"):
        uipr.change_page("settings_sh", "home_page_sh")


def main():

    language_selector()
    
    if st.session_state["login_page_sh"]:
        login_page()
    elif st.session_state["register_page_sh"]:
        registration_page()
    elif st.session_state["home_page_sh"]:
        home_page()
    elif st.session_state["daily_log_sh"]:
        daily_log_page()
    elif st.session_state["recognition_page_sh"]:
        recognition_page()
    elif st.session_state["general_stat_sh"]:
        general_stat_page()
    elif st.session_state["settings_sh"]:
        settings_page()


if __name__ == "__main__":
    main()
