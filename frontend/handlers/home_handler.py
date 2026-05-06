import streamlit as st
from typing import Dict, Any
import datetime as dt
from typing import List
import matplotlib.pyplot as plt
from threading import RLock

from handlers.api_handler import api_request
from translator import Translator
t = Translator()

def get_ui_label(db_value: Any, key: str) -> str:
    """
    Converts DB value to UI label using YAML mapping.
    
    Args:
        db_value (Any): Value from database (e.g., "weight_loss", "m", 1.55).
        key (str): YAML key like "register.goal.options".
    
    Returns:
        str: UI label for current language.
    """
    options = t(key)
    if options and isinstance(options[0], dict):
        for opt in options:
            if opt.get("value") == db_value:
                return opt["label"]
    return str(db_value)

def get_user_information() -> Dict:
    """
    Retrieves current user profile.
    Requires authentication (token added by wrapper).
    
    Returns:
        dict: User's profile information with UI-ready labels.
    """
    response = api_request("GET", "users/me")

    if response:
        return {
            "age": int(response.get("age")),
            "bmr": float(response.get("bmr")),
            "goal": response.get("goal", "weight_maintenance"),
            "gender": response.get("gender", "None"),
            "weight": float(response.get("weight")),
            "height": float(response.get("height")),
        }
    return {}

def get_info_nutrition(
    time_span: List[dt.datetime] | dt.datetime = dt.datetime.now(),
) -> Dict | None:
    """
    Retrieves nutrition history for a time period.
    Requires authentication.
    
    Args:
        time_span: Either a single datetime or a list/tuple of [start, end].
    
    Returns:
        dict: Nutrition info keyed by date, or None on error.
    
    Note:
        Query params changed from st_time_span/fin_time_span to start/end.
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
    """
    Retrieves nutrition norms history for a time period.
    Requires authentication.
    
    Args:
        time_span: Either a single datetime or a list/tuple of [start, end].
    
    Returns:
        dict: Nutrition norms keyed by date, or None on error.
    
    Note:
        Query params changed from st_time_span/fin_time_span to start/end.
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

    response = api_request(
        "GET", "daily_nutrition_norms", params=params
    )
    if response:
        response = {
            r_key: {key: float(val) for key, val in r_val.items()}
            for r_key, r_val in response.items()
        }
        if one_day:
            return response.get(start, {})
        return response
    return {}

_lock = RLock()

def display_days_nutrition_overview():
    """
    Displays today's nutrition overview with donut charts comparing actual vs norms.
    Shows: calories, proteins, fats, carbohydrates.
    """
    days_info = st.session_state.get("days_info", {})
    norms_info = st.session_state.get("daily_nutrition_norms", {})

    st.subheader(t("ui.home.today_info"))

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
                0, 0,
                f"{int(val)} / {int(norm)}\n{unit_g}",
                horizontalalignment="center",
                verticalalignment="center",
                fontsize=14,
                color="white",
                fontweight="bold",
            )
        else:
            el.text(
                0, 0,
                f"{int(val)} / {int(norm)}\n{unit_kcal}",
                horizontalalignment="center",
                verticalalignment="center",
                fontsize=14,
                color="white",
                fontweight="bold",
            )

    with _lock:
        st.pyplot(fig, width='stretch')

    plt.close()