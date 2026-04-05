import streamlit as st
from PIL import Image
from io import BytesIO
import base64

import ui_processing as pui

if "username" not in st.session_state:
    st.session_state["username"] = ""

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
    # Streamlit app
    st.title("Login")

    user_name = st.text_input(
        "Username", placeholder="Type a user's name...", key="username_l"
    )
    password = st.text_input(
        "Password", placeholder="Type a password...", type="password", key="password_l"
    )
    _, midle, _ = st.columns(3)
    if midle.button("Sign in", use_container_width=True):
        if pui.authorization(user_name, password):
            st.session_state["username"] = user_name
            pui.change_page("login_page_sh", "home_page_sh")

    if midle.button("Sign up", use_container_width=True, key="sign_up_l"):
        pui.change_page("login_page_sh", "register_page_sh")


def registration_page():
    """Registration page"""
    st.title("Registration")

    gender = st.radio(
        "What gender are you?",
        [":blue[Man]", ":red[Woman]", "Don't specify"],
        index=None,
    )

    col1, col2 = st.columns(2)
    weight = col1.number_input(
        "How much weight do you have?",
        min_value=20.,
        max_value=500.,
        value=None,
        step=1.,
        placeholder="Type a weight...",
        format="%.1f",
        key="weight_r",
    )

    height = col2.number_input(
        "How tall are you in cm?",
        min_value=50.,
        max_value=250.,
        value=None,
        step=1.,
        placeholder="Type a height...",
        format="%.1f",
        key="height_r",
    )

    user_name = st.text_input(
        "Username", key="username_r", placeholder="Type a username..."
    )
    password = st.text_input(
        "Password", type="password", placeholder="Type a password...", key="password_r"
    )
    re_password = st.text_input(
        "Repeat the password", placeholder="Type a re-password...", type="password"
    )

    _, midle, _ = st.columns(3)
    if midle.button("Sign up", use_container_width=True, key="sign_up_r"):
        if pui.registration(gender, weight, height, user_name, password, re_password):
            pui.change_page("register_page_sh", "login_page_sh")
    
    if midle.button("Back", use_container_width=True, key="back_r"):
        pui.change_page("register_page_sh", "login_page_sh")

                
def home_page():
    """Home page containing information about today's consumption"""
    st.title(f"Hi, {st.session_state["username"]}!")

    pui.plot_norms_info({"calories":1248, "proteins":50, "fats":100, "carbohydrates":69},
                {"calories":2535, "proteins":127, "fats":88, "carbohydrates":317})
    
    left, midle, right = st.columns(3)
    if left.button('View daily log', use_container_width=True, key="daily_log"):
        pui.change_page("home_page_sh", "daily_log_sh")
    if midle.button('Add dishes', use_container_width=True, key="add_dishes"):
        pui.change_page("home_page_sh", "recognition_page_sh")
    if right.button('General statistics', use_container_width=True, key="statistics"):
        pui.change_page("home_page_sh", "general_stat_sh")

    row1, row2 = st.columns(2)
    if row1.button('Log out', use_container_width=True, key="log_out"):
        st.session_state["username"] = ""
        pui.change_page("home_page_sh", "login_page_sh")
    if row2.button('Settings', use_container_width=True, key="settings"):
        pui.change_page("home_page_sh", "settings_sh")
    

def recognition_page():
    """A page containing the functionality for calculating the macros from a photo"""
    st.title("Calorie Tracker")
    
    st.config.set_option("server.maxUploadSize", 3)
    uploaded_file = st.file_uploader("Choose an image...", type=["jpg", "jpeg", "png"])

    if uploaded_file is not None:
        try:
            img = Image.open(uploaded_file)
            st.image(img, use_column_width=True)

            buffered = BytesIO()
            img.save(buffered, format="JPEG")
            image_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

        except Exception as e:
            st.error(f"Error processing image: {e}")

    user_description = st.text_input(
        "Describe the dish (max 250 characters)", max_chars=250
    )

    _, midle, _ = st.columns(3)

    if midle.button("Upload", use_container_width=True):
        try:
            # Send Base64-encoded image to FastAPI
            nutritional_info = pui.get_nutritional_info(image_base64, user_description)
            if nutritional_info:
                pui.plot_nutritional_info(nutritional_info)
        except Exception as e:
            st.error(f"Error api request or plot_nutritional_info: {e}")

    if midle.button('Back', use_container_width=True, key="back_rec"):
        pui.change_page("recognition_page_sh", "home_page_sh")
        


def daily_log_page():
    _, midle, _ = st.columns(3)
    if midle.button('Back', use_container_width=True, key="back_dl"):
        pui.change_page("daily_log_page", "home_page_sh")

def general_stat_page():
    _, midle, _ = st.columns(3)
    if midle.button('Back', use_container_width=True, key="back_gs"):
        pui.change_page("general_stat_page", "home_page_sh")

def settings_page():
    _, midle, _ = st.columns(3)
    if midle.button('Back', use_container_width=True, key="back_set"):
        pui.change_page("settings_page", "home_page_sh")




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
