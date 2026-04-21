import streamlit as st
from PIL import Image
from io import BytesIO
import base64

import ui_plots as uipl
import ui_processing as uipr

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
if "total_macros" not in st.session_state:
    st.session_state["last_deleted"] = []
if "dish_saved" not in st.session_state:
    st.session_state["is_dish_saved"] = False


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


def login_page():
    """Authorization page"""
    st.title("Login")

    username = st.text_input(
        "Username", placeholder="Type a user's name...", key="username_l"
    )
    password = st.text_input(
        "Password", placeholder="Type a password...", type="password", key="password_l"
    )
    _, midle, _ = st.columns(3)
    if midle.button("Sign in", use_container_width=True):
        if uipr.authorization("login_page_sh", username, password):
            st.session_state["username"] = username
            uipr.change_page("login_page_sh", "home_page_sh")

    if midle.button("Sign up", use_container_width=True, key="sign_up_l"):
        uipr.change_page("login_page_sh", "register_page_sh")
    if st.session_state["auth_error"]:
        st.warning(st.session_state["auth_error"])
        st.session_state["auth_error"] = ""


def registration_page():
    """Registration page"""
    st.title("Registration")

    gender = st.radio(
        "What gender are you?",
        [":blue[Man]", ":red[Woman]", "Don't specify"],
        index=2,
    )

    col1, col2 = st.columns(2)

    age = col1.number_input(
        "How old are you?",
        min_value=10,
        max_value=120,
        value=None,
        step=1,
        placeholder="Type a age...",
        key="age_r",
    )

    lifestyle = col2.selectbox(
        "What kind of lifestyle do you lead?",
        options=(
            "Sedentary lifestyle",
            "Light training 1-2 times a week",
            "3-5 training sessions per week",
            "Daily intensive training",
            "Heavy physical labor",
        ),
        index=0,
        key="lifestyle_r",
    )

    weight = col1.number_input(
        "How much weight do you have?",
        min_value=20.0,
        max_value=500.0,
        value=None,
        step=1.0,
        placeholder="Type a weight...",
        format="%.1f",
        key="weight_r",
    )

    height = col2.number_input(
        "How tall are you in cm?",
        min_value=50.0,
        max_value=250.0,
        value=None,
        step=1.0,
        placeholder="Type a height...",
        format="%.1f",
        key="height_r",
    )

    username = st.text_input(
        "Username", key="username_r", placeholder="Type a username..."
    )
    password = st.text_input(
        "Password",
        type="password",
        placeholder="Type a password...",
        key="password_r",
        help=uipr.PASSWORD_PATTERN_TEXT,
    )
    re_password = st.text_input(
        "Repeat the password",
        placeholder="Type a re-password...",
        type="password",
        help=uipr.USERNAME_PATTERN_TEXT,
    )

    _, midle, _ = st.columns(3)
    if midle.button("Sign up", use_container_width=True, key="sign_up_r"):
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

    if midle.button("Back", use_container_width=True, key="back_r"):
        uipr.change_page("register_page_sh", "login_page_sh")


def home_page():
    """Home page containing information about today's consumption"""
    st.title(f"Hi, {st.session_state["username"]}!")
    if not st.session_state["user_info"]:
        st.session_state["user_info"] = uipr.get_user_information("home_page_sh")
    if not st.session_state["days_info"]:
        st.session_state["days_info"] = uipr.get_info_nutrition("home_page_sh")
    if not st.session_state["daily_nutrition_norms"]:
        st.session_state["daily_nutrition_norms"] = uipr.get_daily_nutrition_norms(
            "home_page_sh", st.session_state["user_info"]
        )
    uipl.display_days_nutrition_overview()

    left, midle, right = st.columns(3)
    if left.button("View daily log", use_container_width=True, key="daily_log"):
        uipr.change_page("home_page_sh", "daily_log_sh")
    if midle.button("Add dishes", use_container_width=True, key="add_dishes"):
        uipr.change_page("home_page_sh", "recognition_page_sh")
    if right.button("General statistics", use_container_width=True, key="statistics"):
        uipr.change_page("home_page_sh", "general_stat_sh")

    row1, row2 = st.columns(2)
    if row1.button("Log out", use_container_width=True, key="log_out"):
        uipr.change_page("home_page_sh", "login_page_sh")
    if row2.button("Settings", use_container_width=True, key="settings"):
        uipr.change_page("home_page_sh", "settings_sh")


def recognition_page():
    """A page containing the functionality for calculating the macros from a photo"""
    st.title("Calorie Tracker")

    st.config.set_option("server.maxUploadSize", 3)
    uploaded_file = st.file_uploader(
        "Choose an image...",
        on_change=uipr.clear_new_uploader,
        type=["jpg", "jpeg", "png"],
        key="file_loader",
    )

    if uploaded_file:
    if uploaded_file:
        try:
            img = Image.open(uploaded_file)
            st.image(img, use_column_width=True)

            buffered = BytesIO()
            img.save(buffered, format="JPEG")
            image_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

        except Exception as e:
            st.error("🖼️ Failed to process image. Please ensure the file is valid.")
            image_base64 = None
            st.error("🖼️ Failed to process image. Please ensure the file is valid.")
            image_base64 = None

    user_description = st.text_input(
        "Describe the dish (max 250 characters)", max_chars=250
    )

    if st.session_state["table_ingredients"] is not None:
        uipl.plot_nutritional_info()

    _, midle, _ = st.columns(3)

    if st.session_state["table_ingredients"]:
        text = "Save dish"
    else:
        text = "Upload"

    if midle.button(text, use_container_width=True):
        if text == "Save dish":
            if uipr.save_dish("recognition_page_sh"):
                st.session_state["table_ingredients"] = None
                st.session_state["total_macros"] = None
                uipr.change_page("recognition_page_sh", "home_page_sh")
            st.error("Failed to save dish")
            
        else:
            if image_base64:
                nutritional_info = uipr.get_meal_macros(
                    "recognition_page_sh", image_base64, user_description
                )
                uipr.parse_dish(nutritional_info)
                st.rerun()
            else:
                st.error("📷 Please upload an image first")

    if midle.button("Back", use_container_width=True, key="back_rec"):
        st.session_state["table_ingredients"], st.session_state["total_macros"] = None, None
        st.session_state["is_dish_saved"] = False
        st.session_state["last_deleted"] = []
        uipr.change_page("recognition_page_sh", "home_page_sh")


def daily_log_page():
    _, midle, _ = st.columns(3)
    if midle.button("Back", use_container_width=True, key="back_dl"):
        uipr.change_page("daily_log_page", "home_page_sh")


def general_stat_page():
    _, midle, _ = st.columns(3)
    if midle.button("Back", use_container_width=True, key="back_gs"):
        uipr.change_page("general_stat_page", "home_page_sh")


def settings_page():

    def_inf = st.session_state["user_info"]

    st.title("Settings")

    gender = st.radio(
        "What gender are you?",
        [":blue[Man]", ":red[Woman]", "Don't specify"],
        index=uipr.index_gender(def_inf.get("gender")),
    )

    col1, col2 = st.columns(2)

    age = col1.number_input(
        "How old are you?",
        min_value=10,
        max_value=120,
        value=def_inf.get("age"),
        step=1,
        placeholder="Type a age...",
        key="age_set",
    )

    lifestyle = col2.selectbox(
        "What kind of lifestyle do you lead?",
        options=(
            "Sedentary lifestyle",
            "Light training 1-2 times a week",
            "3-5 training sessions per week",
            "Daily intensive training",
            "Heavy physical labor",
        ),
        index=uipr.index_lifestyle(def_inf.get("lifestyle")),
        key="lifestyle_set",
    )

    weight = col1.number_input(
        "How much weight do you have?",
        min_value=20.0,
        max_value=500.0,
        value=def_inf.get("weight"),
        step=1.0,
        placeholder="Type a weight...",
        format="%.1f",
        key="weight_set",
    )

    height = col2.number_input(
        "How tall are you in cm?",
        min_value=50.0,
        max_value=250.0,
        value=def_inf.get("height"),
        step=1.0,
        placeholder="Type a height...",
        format="%.1f",
        key="height_set",
    )

    _, midle, _ = st.columns(3)
    if midle.button("Apply", use_container_width=True, key="apply_set"):
        if uipr.update_user_info(
            "home_page_sh", age, lifestyle, gender, weight, height
        ):
            if gender == ":blue[Man]":
                gender = "m"
            elif gender == ":red[Woman]":
                gender = "w"
            else:
                gender = "None"

            st.session_state["user_info"] = {
                "age": age,
                "lifestyle": lifestyle,
                "bmp": uipr.bmr.get(lifestyle),
                "gender": gender,
                "weight": weight,
                "height": height,
            }
            st.session_state["daily_nutrition_norms"] = None
            st.session_state["daily_nutrition_norms"] = None
            uipr.change_page("settings_sh", "home_page_sh")

    _, midle, _ = st.columns(3)
    if midle.button("Back", use_container_width=True, key="back_set"):
        uipr.change_page("settings_sh", "home_page_sh")


def main():
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
