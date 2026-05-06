import streamlit as st
from typing import Dict, Any

from handlers.api_handler import api_request
from translator import Translator
t = Translator()

def get_options_mapping(key: str) -> Dict[str, Any]:
    """
    Returns dict mapping label → value from YAML options.
    
    Args:
        key (str): YAML key like "register.goal.options".
    
    Returns:
        dict: Dict mapping UI label → DB value.
    """
    options = t(key)
    if options and isinstance(options[0], dict):
        return {opt["label"]: opt["value"] for opt in options}
    return {}

def get_db_value(user_label: str, key: str, default: Any) -> Any:
    """
    Converts UI label to DB value using YAML mapping.
    
    Args:
        user_label (str): Selected label from UI.
        key (str): YAML key like "register.goal.options".
        default (Any): Fallback value if not found.
    
    Returns:
        Any: DB value (e.g., "weight_loss", "m", 1.55).
    """
    mapping = get_options_mapping(key)
    return mapping.get(user_label, default)

def registration(
    username: str,
    password: str,
    re_password: str,
    age: int,
    lifestyle: str,
    goal: str,
    gender: str,
    weight: float,
    height: float,
) -> bool:
    """
    Registers a new user.
    Frontend validates password match; Backend validates types/ranges.
    
    Args:
        username (str): Unique username.
        password (str): User password.
        re_password (str): Password confirmation.
        age (int): User age.
        lifestyle (str): Lifestyle label from UI.
        goal (str): Goal label from UI.
        gender (str): Gender label from UI.
        weight (float): User weight in kg.
        height (float): User height in cm.
    
    Returns:
        bool: True if successful, False otherwise.
    
    Note:
        Nutrition norms are calculated on backend automatically.
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

    payload = {
        "username": username,
        "password": password,
        "age": age,
        "bmr": get_db_value(lifestyle, "register.lifestyle.options", 1.2),
        "goal": get_db_value(goal, "register.goal.options", "weight_maintenance"),
        "gender": get_db_value(gender, "register.gender.options", "None"),
        "weight": weight,
        "height": height,
    }

    response = api_request("POST", "registration", json=payload)
    return response is not None