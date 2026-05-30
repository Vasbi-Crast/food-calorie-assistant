"""Handler module for daily log operations.

Provides functions to fetch, save, and update daily nutrition logs,
and handles date-based data synchronization with the backend API.
"""

import streamlit as st
from typing import Dict, List, Optional
import datetime as dt

from handlers.api_handler import api_request, check_activity, parse_meals
from handlers.home_handler import get_user_ingredients
from translator import Translator, IngredientTranslator

t = Translator()


def get_daily_log(date: dt.datetime) -> Optional[List[Dict]]:
    """Fetches the daily nutrition log for a specific date from the backend.

    Args:
        date (datetime.datetime): The date to fetch the log for.

    Returns:
        Optional[List[Dict]]: A list of ingredient dictionaries if successful,
            or None if the API request fails.
    """
    check_activity()
    params = {"date": date.strftime("%Y-%m-%d")}
    return api_request("GET", "get_daily_log", params=params)


def save_daily_log(date: dt.datetime) -> bool:
    """Saves the current meal table to the backend database.

    Validates that ingredients exist in session state, constructs the payload
    with modified ingredients and timestamp, and sends a PUT request to the API.

    Args:
        date (datetime.datetime): The date to save the log for.

    Returns:
        bool: True if the save operation succeeds, False otherwise.
            Displays error message via st.error if no ingredients are present.
    """
    check_activity()
    ingredients = st.session_state.get("table_ingredients")
    if not ingredients:
        st.error(t("error.meal.no_ingredients"))
        return False

    payload = {
        "table": ingredients,
        "modified_ingredients": st.session_state.get("modified_ingredients", []),
        "date": date.strftime("%Y-%m-%d %H:%M:%S"),
    }

    res = api_request("PUT", "save_daily_log", json=payload)

    if res:
        st.session_state["days_info"] = None
        st.session_state["users_ingredients"] = get_user_ingredients()
        return True
    return False


def new_date_update() -> None:
    """Resets the ingredient table and fetches nutrition data for the selected date.

    Clears the session state table_ingredients list and retrieves the daily log
    for the date stored in session state, then parses the meals into the UI.
    """
    st.session_state["table_ingredients"] = []
    nutritional_info = get_daily_log(
        st.session_state.get("daily_log_date", dt.datetime.now())
    )
    parse_meals(nutritional_info)
