"""Handler module for user settings and profile updates.

Provides utilities for mapping database values to UI component indices,
handling option translations, and submitting profile updates to the backend.
"""
import streamlit as st
from typing import Dict, Any

from handlers.api_handler import api_request
from translator import Translator

t = Translator()


def index_goal(goal: str) -> int:
    """Converts a database goal value to a UI radio button index.

    Args:
        goal (str): The goal identifier from the database
            (e.g., "weight_loss", "weight_maintenance", "weight_gain").

    Returns:
        int: The zero-based index for the st.radio component.
            Defaults to 1 if the goal is not found in YAML or fallback list.
    """
    options = t("register.goal.options")
    for i, opt in enumerate(options):
        if isinstance(opt, dict) and opt.get("value") == goal:
            return i
    goals = ["weight_loss", "weight_maintenance", "weight_gain"]
    try:
        return goals.index(goal)
    except ValueError:
        return 1


def index_gender(gender: str) -> int:
    """Converts a database gender value to a UI radio button index.

    Args:
        gender (str): The gender identifier from the database
            (e.g., "m", "w", "None").

    Returns:
        int: The zero-based index for the st.radio component.
            Defaults to 2 if the gender is not found in YAML or fallback list.
    """
    options = t("register.gender.options")
    for i, opt in enumerate(options):
        if isinstance(opt, dict) and opt.get("value") == gender:
            return i
    genders = ["m", "w", "None"]
    try:
        return genders.index(gender)
    except ValueError:
        return 2


def index_lifestyle(bmr_value: float) -> int:
    """Converts a BMR multiplier value to a UI selectbox index.

    Args:
        bmr_value (float): The BMR multiplier from the database
            (e.g., 1.2, 1.375, 1.55, 1.725, 1.9).

    Returns:
        int: The zero-based index for the st.selectbox component.
            Defaults to 0 if the value is not found.
    """
    options = t("register.lifestyle.selector.options")
    for i, opt in enumerate(options):
        if isinstance(opt, dict) and opt.get("value") == bmr_value:
            return i
        elif isinstance(opt, (int, float)) and opt == bmr_value:
            return i
    return 0


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


def update_user_info(
    age: int,
    lifestyle_description: str,
    goal: str,
    gender: str,
    weight: float,
    height: float,
) -> bool:
    """Updates the current user's profile information via the backend API.

    Validates input, maps UI labels to database values, and sends a PUT request
    to update the profile. Triggers backend recalculation of nutrition norms.

    Args:
        age (int): User's age in years.
        lifestyle_description (str): User-provided lifestyle description or selected mode.
        goal (str): Selected fitness goal label from the UI.
        gender (str): Selected gender label from the UI.
        weight (float): User's weight in kilograms.
        height (float): User's height in centimeters.

    Returns:
        bool: True if the update succeeds, False otherwise.
            Displays error message via st.error if lifestyle description is empty.
    """
    if not lifestyle_description.strip():
        st.error(t("error.form.lifestyle_description_required"))
        return False
    payload = {
        "age": age,
        "bmr": get_db_value(lifestyle_description, "settings.lifestyle.selector.options", None),
        "lifestyle_description": lifestyle_description,
        "goal": get_db_value(goal, "settings.goal.options", "weight_maintenance"),
        "gender": get_db_value(gender, "settings.gender.options", "None"),
        "weight": weight,
        "height": height,
    }
    response = api_request("PUT", "users/me", json=payload)
    return response is not None