"""Handler module for meal recognition via image analysis.

Provides functions to send images for ingredient recognition,
parse nutrition data, and save meals to the backend database.
"""

import streamlit as st
from typing import List, Optional, Dict
import datetime as dt
import json

from handlers.api_handler import api_request
from handlers.home_handler import get_user_ingredients
from translator import Translator

t = Translator()


def get_meal_macros(image_base64: str, user_description: str) -> Optional[List[Dict]]:
    """Sends an image to the backend for ingredient recognition and nutrition analysis.

    Args:
        image_base64 (str): Base64-encoded image data of the meal.
        user_description (str): Optional text description provided by the user
            to assist with recognition.

    Returns:
        Optional[List[Dict]]: A list of ingredient dictionaries with nutrition
            information if successful, or None if the API request fails or
            parsing encounters an error.
    """
    payload = {"image_base64": image_base64, "user_description": user_description}

    response = api_request("POST", "ingredient_recognition", json=payload, timeout=240)

    if response:
        result = response.get("result")
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except json.JSONDecodeError:
                st.warning(t("warning.recognition.parse_failed"))
                return None

        if result:
            return result
        else:
            st.warning(t("warning.recognition.no_data"))
    return None


def save_meal() -> bool:
    """Saves the current meal from the session state to the backend database.

    Validates that ingredients exist in session state, constructs the payload
    with modified ingredients and timestamp, and sends a POST request to the API.

    Returns:
        bool: True if the save operation succeeds, False otherwise.
            Displays error message via st.error if no ingredients are present.
    """
    ingredients = st.session_state.get("table_ingredients")
    if not ingredients:
        st.error(t("error.meal.no_ingredients"))
        return False

    payload = {
        "table": ingredients,
        "modified_ingredients": st.session_state.get("modified_ingredients", []),
        "created_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    res = api_request("POST", "save_meal", json=payload)

    if res:
        st.session_state["days_info"] = None
        st.session_state["users_ingredients"] = get_user_ingredients()
        return True
    return False
