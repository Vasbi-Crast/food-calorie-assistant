import requests
import streamlit as st
import matplotlib.pyplot as plt
import json
from threading import RLock
from dotenv import load_dotenv
import os

_lock = RLock()

load_dotenv()

SERVER_URL = os.getenv("SERVER_URL")

def change_page(old_page:str, new_page:str):
    st.session_state[old_page] = False
    st.session_state[new_page] = True
    st.rerun()

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
        raw_response = requests.post(
            SERVER_URL + "/generate_response", json=payload, headers=headers
        )

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

    with _lock:
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

        st.pyplot(fig, use_container_width=True, transparent=True)
    
    
def plot_norms_info(days_info, norms_info):
    st.subheader("Information of the day")

    labels = ["calories", "proteins", "fats", "carbohydrates"]
    values_day = [days_info[label] for label in labels]
    norms_day = [norms_info[label] for label in labels]
    colors = [[251, 251, 243], [29, 97, 221], [127, 20, 20], [165, 165, 41]]
    colors = [[el/255.0 for el in color] for color in colors]
    
    with _lock:
        fig, ax = plt.subplots(2, 2, figsize=(10, 10))
        fig.patch.set_alpha(0.0)
        ax = ax.reshape(1, 4)[0]

        for el, val, norm, label, color in zip(ax, values_day, norms_day, labels, colors):
            label = label[0].upper() + label[1:]
            remain = max(0, norm - val)
            wedges, texts = el.pie(
                [val, remain],
                startangle=90,
                wedgeprops={"width": 0.2},
                colors=[color+[1.], color+[0.3]],
            )

            el.axis("equal")
            el.set_title(label, color='white', fontsize=18, pad=8) 

            for text in texts:
                text.set_visible(False)

            if label != "Calories":
                el.text(
                    0,
                    0,
                    f'{int(val)} / {int(norm)}\ng.',
                    horizontalalignment="center",
                    verticalalignment="center",
                    fontsize=14,
                    color="white",
                    fontweight='bold'
                )
            else:
                el.text(
                    0,
                    0,
                    f'{int(val)} / {int(norm)}',
                    horizontalalignment="center",
                    verticalalignment="center",
                    fontsize=14,
                    color="white",
                    fontweight='bold'
                )
        st.pyplot(fig)


def authorization(user_name: str, password: str) -> bool:
    """
    Sends a POST request to the FastAPI service to authorize the user.

    Args:
        user_name (str): A unique username for authorization.
        password (str): User's password.

    Returns:
        bool: Returns verification of user authentication.
    """

    if not user_name.strip():
        st.error(f"The user's name is missing.")
        return False
    elif not password.strip():
        st.error(f"The password is missing.")
        return False

    # Prepare payload and headers for the request
    payload = {"user_name": user_name, "password": password}
    headers = {"Content-Type": "application/json"}

    try:
        # Send POST request
        raw_response = requests.post(
            SERVER_URL + "/authentication", json=payload, headers=headers
        )

        # Handle response
        if raw_response.status_code == 200:
            response = raw_response.json().get("response")
            if response == "SUCCESSFUL":
                return True
            elif response == "INVALID_PASSWORD":
                st.error(f"The password is entered incorrectly.")
            elif response == "USER_NOT_FOUND":
                st.error(f"The user does not exist. Please register.")
            else:
                st.error(f"Unexpected error.")
            return False

        else:
            st.error(f"Error: {raw_response.status_code}, {raw_response.text}")
            return False

    except Exception as e:
        st.error(f"Error: {e}")
        return False


def registration(
    gender: str,
    weight: float,
    height: float,
    user_name: str,
    password: str,
    re_password: str,
):
    """
    Sends a POST request to the FastAPI service to register the user.

    Args:
        gender (str): User's gender
        weight (float): User's weight
        height (float): User growth
        user_name (str): A unique username for authorization.
        password (str): User's password.
        re_password (str): Repeated password

    Returns:
        bool: returns successful registration
    """

    if not user_name.strip():
        st.error(f"The user's name is missing.")
        return False

    elif not password.strip():
        st.error(f"The password is missing.")
        return False

    elif not re_password.strip():
        st.error(f"The re-password is missing.")
        return False

    elif not weight:
        st.error(f"The weight is missing.")
        return False

    elif not height:
        st.error(f"The height is missing.")
        return False

    elif re_password != password:
        st.error(f"Passwords didn't match.")
        return False

    if gender == ":blue[Man]":
        gender = "m"
    elif gender == ":red[Woman]":
        gender = "w"
    else:
        gender = "None"

    # Prepare payload and headers for the request
    payload = {
        "user_name": user_name,
        "password": password,
        "gender": gender,
        "weight": weight,
        "height": height,
    }
    headers = {"Content-Type": "application/json"}

    try:
        # Send POST request
        raw_response = requests.post(
            SERVER_URL + "/registration", json=payload, headers=headers
        )

        # Handle response
        if raw_response.status_code == 200:
            result = bool(raw_response.json().get("response", False))
            if result:               
                return True
            else:
                st.error('A user with this name already exists.')
                return False

        else:
            st.error(f"Error: {raw_response.status_code}, {raw_response.text}")
            return False

    except Exception as e:
        st.error(f"Error: {e}")
        return False