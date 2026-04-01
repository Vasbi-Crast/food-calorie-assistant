import requests
import streamlit as st
from PIL import Image
from io import BytesIO
import matplotlib.pyplot as plt
import base64
import json
from dotenv import load_dotenv
import os


load_dotenv()

SERVER_URL = os.getenv("SERVER_URL")

if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
if "username" not in st.session_state:
    st.session_state["username"] = ""
if "new_user" not in st.session_state:
    st.session_state["new_user"] = False


def get_nutritional_info(image_base64: str, user_description: str):
    """
    Sends a POST request to the FastAPI service to retrieve nutritional information
    for a given base64 encoded image.

    Args:
        image_base64 (str): The base64 encoded image string.
        user_description (str): Custom description of the dish in the image.

    Returns:
        dict or None: A dictionary containing nutritional information with the keys
        'calories', 'proteins', 'fats', and 'carbohydrates' if the request is
        successful. Returns None if there is an error or if the nutritional information
        is not available.
    """
    try:
        # Prepare payload and headers for the request
        payload = {"image_base64": image_base64, "user_description": user_description}
        headers = {"Content-Type": "application/json"}

        # Send POST request
        raw_response = requests.post(SERVER_URL+'/generate_response', json=payload, headers=headers)

        # Handle response
        if raw_response.status_code == 200:
            response = raw_response.json()

            if response["status"] == "success":
                result = response["result"]

                if isinstance(result, str):
                    result = json.loads(response["result"])

                if result:
                    return result
                else:
                    st.warning("Nutritional information not available for this image.")
                    return None
            else:
                st.error(f"Unable to retrieve nutritional information: {response}.")
                return None
        else:
            st.error(f"Error: {raw_response.status_code}, {raw_response.text}")
            return None
    except Exception as e:
        st.error(f"Error: {e}")
        return None


def plot_nutritional_info(nutritional_info):
    """Visualizes ingredient list and total nutrition (donut chart)."""
    if not nutritional_info:
        st.warning("No ingredients found.")
        return

    rows = []
    total = {"calories": 0.0, "proteins": 0.0, "fats": 0.0, "carbohydrates": 0.0}

    for item in nutritional_info:
        if not isinstance(item, dict) or not item:
            continue
        original_name, payload = next(iter(item.items()))
        if not payload:
            rows.append(
                {
                    "ingredient": original_name,
                    "match": "",
                    "weight_g": "",
                    "calories": "",
                    "proteins": "",
                    "fats": "",
                    "carbohydrates": "",
                }
            )
            continue

        rows.append(
            {
                "ingredient": original_name,
                "match": payload.get("match", ""),
                "weight_g": payload.get("weight", ""),
                "calories": payload.get("calories", ""),
                "proteins": payload.get("proteins", ""),
                "fats": payload.get("fats", ""),
                "carbohydrates": payload.get("carbohydrates", ""),
            }
        )

        for k in total:
            try:
                total[k] += float(payload.get(k, 0) or 0)
            except (TypeError, ValueError):
                pass

    st.subheader("Ingredients")
    st.table(rows)

    st.subheader("Total nutrition")
    labels = "Proteins", "Fats", "Carbohydrates"
    sizes = [total["proteins"], total["fats"], total["carbohydrates"]]

    fig, ax = plt.subplots()
    fig.patch.set_alpha(0.0)

    wedges, texts, autotexts = ax.pie(
        sizes,
        labels=labels,
        autopct=lambda p: f"{p * sum(sizes) / 100:.0f}",
        startangle=90,
        wedgeprops={"width": 0.5},
    )

    ax.axis("equal")

    for text in texts:
        text.set_color("white")

    for autotext in autotexts:
        autotext.set_color("white")
        autotext.set_fontsize(16)
        x, y = autotext.get_position()
        autotext.set_position((x * 1.2, y * 1.2))

    plt.text(
        0,
        0,
        f'{round(total["calories"], 0)}\nkcal',
        horizontalalignment="center",
        verticalalignment="center",
        fontsize=20,
        color="white",
    )

    st.pyplot(fig, transparent=True)


def login_page():
    """Authorization window"""
    # Streamlit app
    st.title("Login")

    user_name = st.text_input("Username", key="username_l")
    password = st.text_input("Password", type="password", key="password_l")
    _, midle, _ = st.columns(3)
    if midle.button("Sign in", use_container_width=True):
        if user_name == "Test" and password == "Test":
            st.session_state["logged_in"] = True
            st.session_state["sername"] = user_name
            st.rerun()
        else:
            st.error("Invalid credentials")

    if midle.button("Sign up", use_container_width=True, key="sign_up_l"):
        st.session_state["new_user"] = True
        st.rerun()


def register_page():
    """Registration window"""
    st.title("Registration")

    genre = st.radio(
        "What gender are you?",
        [":blue[Man]", ":red[Woman]", "Don't specify"],
        index=None,
    )
    col1, col2 = st.columns(2)
    weight = col1.text_input("How much weight do you have?")
    height = col2.text_input("How tall are you?")

    user_name = st.text_input("Username", key="username_r")
    password = st.text_input("Password", type="password", key="password_r")
    re_password = st.text_input("Repeat the password", type="password")

    _, midle, _ = st.columns(3)
    if midle.button("Sign up", use_container_width=True, key="sign_up_r"):
        st.session_state["new_user"] = False
        st.rerun()


def main_app():
    """A window containing the main functionality of the application"""
    # Streamlit app
    st.title("Calorie Tracker")

    # File uploader for image
    st.config.set_option("server.maxUploadSize", 3)
    uploaded_file = st.file_uploader("Choose an image...", type=["jpg", "jpeg", "png"])

    if uploaded_file is not None:
        try:
            # Display uploaded image
            img = Image.open(uploaded_file)
            st.image(img, use_column_width=True)

            # Convert image to Base64
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
            nutritional_info = get_nutritional_info(image_base64, user_description)
            if nutritional_info:
                plot_nutritional_info(nutritional_info)
        except Exception as e:
            st.error(f"Error api request or plot_nutritional_info: {e}")


def main():
    if st.session_state["new_user"]:
        register_page()
    elif not st.session_state["logged_in"]:
        login_page()
    else:
        main_app()


if __name__ == "__main__":
    main()
