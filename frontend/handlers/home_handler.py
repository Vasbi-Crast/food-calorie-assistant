"""Handler module for home page data retrieval and visualization.

Provides functions to fetch user profile, nutrition history, norms,
and ingredients from the backend API. Also handles rendering of
today's nutrition overview using Matplotlib donut charts.
"""

import streamlit as st
from typing import Dict, Any, List
import datetime as dt
import matplotlib.pyplot as plt
from threading import RLock

from handlers.api_handler import api_request
from translator import Translator

t = Translator()


def get_ui_label(db_value: Any, key: str) -> str:
    """Converts a database value to its corresponding UI label.

    Args:
        db_value (Any): The value retrieved from the database
            (e.g., "weight_loss", "m", 1.55).
        key (str): The translation key pointing to the option list in YAML.
            Example: "register.goal.options"

    Returns:
        str: The UI label for the current language, or the string
            representation of the database value if no match is found.
    """
    options = t(key)
    if isinstance(options, list) and len(options) > 0 and isinstance(options[0], dict):
        for opt in options:
            if opt.get("value") == db_value:
                return opt["label"]
    return str(db_value)


def get_user_information() -> Dict[str, Any]:
    """Retrieves the current user's profile information from the backend.

    Requires a valid authentication token in the session state.

    Returns:
        Dict[str, Any]: A dictionary containing the user's profile data
            with types cast to int/float where applicable. Returns an
            empty dictionary if the API request fails.
    """
    response = api_request("GET", "users/me")
    if response:
        return {
            "age": int(response.get("age")),
            "bmr": float(response.get("bmr")),
            "lifestyle_description": response.get("lifestyle_description"),
            "goal": response.get("goal", "weight_maintenance"),
            "gender": response.get("gender", "None"),
            "weight": float(response.get("weight")),
            "height": float(response.get("height")),
        }
    return {}


def get_info_nutrition(
    time_span: List[dt.datetime] | dt.datetime = dt.datetime.now(),
) -> Dict[str, Any] | None:
    """Retrieves nutrition consumption history for a specified time period.

    Args:
        time_span (Union[List[datetime], datetime]): A single datetime object
            for a specific day, or a list/tuple of two datetimes [start, end].

    Returns:
        Union[Dict[str, Any], None]: Dictionary keyed by date strings containing
            nutrition data, or None if the request fails. Returns an empty
            dict for a single day if no data exists.
    """
    if isinstance(time_span, (list, tuple)) and len(time_span) == 2:
        start = min(time_span).strftime("%Y-%m-%d")
        end = max(time_span).strftime("%Y-%m-%d")
        one_day = False
    elif isinstance(time_span, dt.datetime):
        start = time_span.strftime("%Y-%m-%d")
        end = time_span.strftime("%Y-%m-%d")
        one_day = True
    else:
        st.error("⚠️ Incorrect time interval format.")
        return {}

    params = {"start": start, "end": end}

    response = api_request("GET", "info_nutrition", params=params)
    if response:
        response = {
            r_key: {key: float(val) for key, val in r_val.items()}
            for r_key, r_val in response.items()
        }
        if one_day:
            return response.get(start, {})
        return response
    return {}


def get_nutrition_norms(
    time_span: List[dt.datetime] | dt.datetime = dt.datetime.now(),
) -> Dict[str, float] | List[Dict[str, float]] | None:
    """Retrieves daily nutrition norms for a specified time period.

    Args:
        time_span (Union[List[datetime], datetime]): A single datetime object
            for a specific day, or a list/tuple of two datetimes [start, end].

    Returns:
        Union[Dict[str, float], List[Dict[str, float]], None]: Nutrition norms
            keyed by date. Returns None if the request fails.
    """
    if isinstance(time_span, (list, tuple)) and len(time_span) == 2:
        start = min(time_span).strftime("%Y-%m-%d")
        end = max(time_span).strftime("%Y-%m-%d")
        one_day = False
    elif isinstance(time_span, dt.datetime):
        start = time_span.strftime("%Y-%m-%d")
        end = time_span.strftime("%Y-%m-%d")
        one_day = True
    else:
        st.error("️ Incorrect time interval format.")
        return {}

    params = {"start": start, "end": end}

    response = api_request("GET", "daily_nutrition_norms", params=params)
    if response:
        response = {
            r_key: {key: float(val) for key, val in r_val.items()}
            for r_key, r_val in response.items()
        }
        if one_day:
            return response.get(start, {})
        return response
    return {}


def get_user_ingredients() -> List[Dict[str, Any]]:
    """Retrieves the list of ingredients saved by the current user.

    Requires authentication. Casts numerical fields (calories, proteins,
    fats, carbohydrates) to float for consistency.

    Returns:
        List[Dict[str, Any]]: A list of dictionaries containing ingredient
            data. Returns an empty list if the request fails or no ingredients exist.
    """
    response = api_request("GET", "user_ingredients")
    if response:
        for items in response:
            items["calories"] = float(items["calories"])
            items["proteins"] = float(items["proteins"])
            items["fats"] = float(items["fats"])
            items["carbohydrates"] = float(items["carbohydrates"])
        return response
    return []


_lock = RLock()


def display_days_nutrition_overview() -> None:
    """Renders today's nutrition overview using Matplotlib donut charts.

    Compares actual intake against daily norms for calories, proteins,
    fats, and carbohydrates. Uses a reentrant lock to ensure thread-safe
    rendering in Streamlit.
    """
    days_info = st.session_state.get("days_info", {})
    norms_info = st.session_state.get("daily_nutrition_norms", {})

    st.subheader(t("home.today_info"))

    if isinstance(norms_info, list) and len(norms_info) > 0:
        norms_info = norms_info[0]

    labels = ["calories", "proteins", "fats", "carbohydrates"]

    values_day = [days_info.get(label, 0) for label in labels]
    norms_day = [norms_info.get(label, 0) for label in labels]

    colors = [[251, 251, 243], [29, 97, 221], [127, 20, 20], [165, 165, 41]]
    colors = [[el / 255.0 for el in color] for color in colors]

    fig, ax = plt.subplots(2, 2, figsize=(10, 10))
    fig.patch.set_alpha(0.0)
    ax = ax.reshape(1, 4)[0]

    for el, val, norm, label, color in zip(ax, values_day, norms_day, labels, colors):
        label_title = t(f"macros.{label}").title()
        remain = max(0, norm - val)

        if norm == 0:
            wedges, texts = el.pie(
                [1],
                startangle=90,
                wedgeprops={"width": 0.2},
                colors=[color + [0.3]],
            )
        else:
            wedges, texts = el.pie(
                [val, remain],
                startangle=90,
                wedgeprops={"width": 0.2},
                colors=[color + [1.0], color + [0.3]],
            )

        el.axis("equal")
        el.set_title(label_title, color="white", fontsize=18, pad=8)

        for text in texts:
            text.set_visible(False)

        unit_g = t("ui.unit.g")
        unit_kcal = t("ui.unit.kcal")

        if label != "calories":
            el.text(
                0,
                0,
                f"{int(val)} / {int(norm)}\n{unit_g}",
                horizontalalignment="center",
                verticalalignment="center",
                fontsize=14,
                color="white",
                fontweight="bold",
            )
        else:
            el.text(
                0,
                0,
                f"{int(val)} / {int(norm)}\n{unit_kcal}",
                horizontalalignment="center",
                verticalalignment="center",
                fontsize=14,
                color="white",
                fontweight="bold",
            )

    with _lock:
        st.pyplot(fig, width="stretch")

    plt.close()
