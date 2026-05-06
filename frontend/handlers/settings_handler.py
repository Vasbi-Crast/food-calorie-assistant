import streamlit as st
from typing import Dict, Any

from handlers.api_handler import api_request
from translator import Translator
t = Translator()

def index_goal(goal: str) -> int:
    """
    Converts DB goal value to index for UI components.
    
    Args:
        goal (str): DB value ("weight_loss", "weight_maintenance", "weight_gain").
    
    Returns:
        int: Index for st.radio (0, 1, or 2).
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
    """
    Converts DB gender value to index for UI components.
    
    Args:
        gender (str): DB value ("m", "w", "None").
    
    Returns:
        int: Index for st.radio (0, 1, or 2).
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
    """
    Converts BMR value to index for UI components.
    
    Args:
        bmr_value (float): BMR value from DB (1.2, 1.375, 1.55, 1.725, 1.9).
    
    Returns:
        int: Index for st.selectbox.
    """
    options = t("register.lifestyle.options")
    for i, opt in enumerate(options):
        if isinstance(opt, dict) and opt.get("value") == bmr_value:
            return i
        elif isinstance(opt, (int, float)) and opt == bmr_value:
            return i
    return 0

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


def update_user_info(
    age: int,
    lifestyle: str,
    goal: str,
    gender: str,
    weight: float,
    height: float,
) -> bool:
    """
    Updates current user profile.
    Requires authentication.
    
    Args:
        age (int): User age.
        lifestyle (str): Lifestyle label from UI.
        goal (str): Goal label from UI.
        gender (str): Gender label from UI.
        weight (float): User weight in kg.
        height (float): User height in cm.
    
    Returns:
        bool: True if successful, False otherwise.
    
    Note:
        Nutrition norms are recalculated on backend automatically.
    """
    payload = {
        "age": age,
        "bmr": get_db_value(lifestyle, "register.lifestyle.options", 1.2),
        "goal": get_db_value(goal, "register.goal.options", "weight_maintenance"),
        "gender": get_db_value(gender, "register.gender.options", "None"),
        "weight": weight,
        "height": height,
    }

    response = api_request("PUT", "users/me", json=payload)
    return response is not None