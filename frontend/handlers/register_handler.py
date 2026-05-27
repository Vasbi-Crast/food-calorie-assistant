"""Handler module for user registration logic.

Provides utilities for mapping UI labels to database values
and handles registration form validation and API submission.
"""
import streamlit as st
from typing import Dict, Any

from handlers.api_handler import api_request
from translator import Translator

t = Translator()


def get_options_mapping(key: str) -> Dict[str, Any]:
    """Returns a dictionary mapping UI labels to their corresponding database values.

    Args:
        key (str): The translation key pointing to a list of options in YAML.
            Example: "register.goal.options"

    Returns:
        Dict[str, Any]: Mapping of UI label to DB value. Returns an empty
            dictionary if the key is missing, empty, or options are not in dict format.
    """
    options = t(key)
    if isinstance(options, list) and len(options) > 0 and isinstance(options[0], dict):
        return {opt["label"]: opt["value"] for opt in options}
    return {}


def get_db_value(user_label: str, key: str, default: Any) -> Any:
    """Converts a UI-selected label to its corresponding database value.

    Args:
        user_label (str): The label selected by the user in the UI.
        key (str): The translation key for the option list.
        default (Any): Fallback value if the label is not found in the mapping.

    Returns:
        Any: The database value corresponding to the label, or the default value.
    """
    mapping = get_options_mapping(key)
    return mapping.get(user_label, default)


def registration(
    username: str,
    password: str,
    re_password: str,
    age: int,
    lifestyle_description: str,
    goal: str,
    gender: str,
    weight: float,
    height: float,
) -> bool:
    """Validates input and submits a new user registration request to the backend.

    Performs frontend validation (empty fields, password match) and constructs
    the payload. Sends the data to the registration endpoint and handles the response.

    Args:
        username (str): Unique username for the account.
        password (str): User password in plain text.
        re_password (str): Password confirmation input.
        age (int): User's age in years.
        lifestyle_description (str): User-provided lifestyle description or selected mode.
        goal (str): Selected fitness goal label from the UI.
        gender (str): Selected gender label from the UI.
        weight (float): User's weight in kilograms.
        height (float): User's height in centimeters.

    Returns:
        bool: True if registration succeeds, False otherwise. Displays error
            messages via Streamlit UI on validation or API failure.
    """
    if not username.strip():
        st.error(t("error.form.username_required"))
        return False
    if not password.strip():
        st.error(t("error.form.password_required"))
        return False
    if password != re_password:
        st.error(t("error.form.passwords_mismatch"))
        return False
    if not lifestyle_description.strip():
        st.error(t("error.form.lifestyle_description_required"))
        return False

    payload = {
        "username": username,
        "password": password,
        "age": age,
        "bmr": get_db_value(lifestyle_description, "register.lifestyle.selector.options", None),
        "lifestyle_description": lifestyle_description,
        "goal": get_db_value(goal, "register.goal.options", "weight_maintenance"),
        "gender": get_db_value(gender, "register.gender.options", "None"),
        "weight": weight,
        "height": height,
    }

    response = api_request("POST", "registration", json=payload)
    return response is not None