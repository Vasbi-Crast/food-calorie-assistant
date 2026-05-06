import streamlit as st
from typing import Dict, List
import datetime as dt
import matplotlib.pyplot as plt
from threading import RLock

from handlers.api_handler import api_request, check_activity
from translator import Translator
t = Translator()

def get_weight_history(
    time_span: List[dt.datetime] | dt.datetime = dt.datetime.now(),
) -> Dict[str, float] | None:
    """
    Retrieves weight history for a time period.
    Requires authentication.
    
    Args:
        time_span: Either a single datetime or a list/tuple of [start, end].
    
    Returns:
        dict: Weight values keyed by date. Example: {"2024-04-01": 75.5, ...}
        None: On error.
    """
    if isinstance(time_span, (list, tuple)) and len(time_span) == 2:
        start = min(time_span).strftime("%Y-%m-%d")
        end = max(time_span).strftime("%Y-%m-%d")
        one_day = False
    elif isinstance(time_span, dt.datetime):
        start = end = time_span.strftime("%Y-%m-%d")
        one_day = True
    else:
        st.error("⚠️ Incorrect time interval format.")
        return None

    params = {"start": start, "end": end}

    response = api_request("GET", "weight_history", params=params)

    if response:
        response = {key: float(val) for key, val in response.items()}
        if one_day:
            return response.get(start)
        return response

    return None

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

def get_statistic_info():
    """Fetches all statistic data for the selected date range."""
    check_activity()
    if (
        "stat_date_range" in st.session_state
        and len(st.session_state["stat_date_range"]) == 2
    ):
        history_weight = get_weight_history(st.session_state["stat_date_range"])
        history_info_nutrition = get_info_nutrition(st.session_state["stat_date_range"])
        history_norms = get_nutrition_norms(st.session_state["stat_date_range"])

        st.session_state["stat_data"]["weight"] = history_weight
        st.session_state["stat_data"]["info_nutrition"] = history_info_nutrition
        st.session_state["stat_data"]["norms"] = history_norms
        st.session_state["saved_data"] = True

_lock = RLock()

def plot_general_stat() -> None:
    """
    Plots 5 charts for general statistics page using matplotlib.
    Wrapped with _lock for thread-safe rendering.

    1. Weight (bar chart)
    2-5. Macros vs Norms (calories, proteins, fats, carbohydrates)

    Expected session_state["stat_data"] format:
        {
            'weight': {'2024-04-01': 75.5, ...},
            'info_nutrition': {'2024-04-01': {'calories': 2000, ...}, ...},
            'norms': {'2024-04-01': {'calories': 2200, ...}, ...}
        }

    Args:
        height (int): Total height of the figure in pixels.
        dpi (int): Dots per inch for figure rendering.

    Returns:
        None: Displays charts directly in Streamlit.
    """

    stat_data = st.session_state.get("stat_data", {})

    if not stat_data:
        st.warning(t("warning.stats.no_data"))
        return

    weight = stat_data.get("weight", {})
    nutrition = stat_data.get("info_nutrition", {})
    norms = stat_data.get("norms", {})

    if not nutrition:
        st.info(t("info.stats.no_nutrition"))
        return

    dates = sorted(nutrition.keys())
    x_pos = range(len(dates))

    weight_values = [
        (
            weight.get(d, {}).get("weight", 0)
            if isinstance(weight.get(d), dict)
            else weight.get(d, 0)
        )
        for d in dates
    ]

    calories = [nutrition[d].get("calories", 0) for d in dates]
    proteins = [nutrition[d].get("proteins", 0) for d in dates]
    fats = [nutrition[d].get("fats", 0) for d in dates]
    carbs = [nutrition[d].get("carbohydrates", 0) for d in dates]

    cal_norm = [norms[d].get("calories", 0) for d in dates]
    prot_norm = [norms[d].get("proteins", 0) for d in dates]
    fats_norm = [norms[d].get("fats", 0) for d in dates]
    carbs_norm = [norms[d].get("carbohydrates", 0) for d in dates]

    colors = {
        "weight": [6 / 255, 167 / 255, 125 / 255, 1.0],
        "calories": [46 / 255, 134 / 255, 171 / 255, 1.0],
        "proteins": [162 / 255, 59 / 255, 114 / 255, 1.0],
        "fats": [241 / 255, 143 / 255, 1 / 255, 1.0],
        "carbs": [106 / 255, 76 / 255, 147 / 255, 1.0],
        "norm": [199 / 255, 62 / 255, 29 / 255, 1.0],
    }

    plt.rcParams.update(
        {
            "font.size": 9,
            "axes.titlesize": 11,
            "axes.labelsize": 10,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "legend.fontsize": 8,
            "figure.titlesize": 13,
            "axes.facecolor": "none",
            "figure.facecolor": "none",
        }
    )

    fig, axes = plt.subplots(5, 1, figsize=(6, 22), constrained_layout=True)
    fig.patch.set_alpha(0.0)

    # === 1. Weight ===
    ax = axes[0]
    ax.bar(x_pos, weight_values, color=colors["weight"], edgecolor="black", linewidth=0.5)
    ax.set_title(t("chart.weight.title"), fontweight="bold", pad=5, color="white")
    ax.set_ylabel(t("chart.weight.ylabel"), color="white")
    ax.tick_params(axis="both", colors="white")
    ax.set_xticks(x_pos)
    ax.set_xticklabels([d[5:] for d in dates], rotation=45, ha="right", color="white")
    ax.grid(axis="y", linestyle="--", alpha=0.3, color="gray")
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("white")
    ax.spines["bottom"].set_color("white")

    # === 2. Calories ===
    ax = axes[1]
    bar_width = 0.35
    ax.bar([p - bar_width / 2 for p in x_pos], calories, width=bar_width, 
           label=t("chart.legend.actual"), color=colors["calories"], edgecolor="black", linewidth=0.5)
    ax.plot(x_pos, cal_norm, label=t("chart.legend.norm"), color=colors["norm"], linewidth=2, marker="o", markersize=4)
    ax.set_title(t("chart.calories.title"), fontweight="bold", pad=5, color="white")
    ax.set_ylabel(t("chart.calories.ylabel"), color="white")
    ax.tick_params(axis="both", colors="white")
    ax.set_xticks(x_pos)
    ax.set_xticklabels([d[5:] for d in dates], rotation=45, ha="right", color="white")
    ax.legend(loc="upper right", fontsize=8, facecolor="gray", edgecolor="white", labelcolor="white")
    ax.grid(axis="y", linestyle="--", alpha=0.3, color="gray")
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("white")
    ax.spines["bottom"].set_color("white")

    # === 3. Proteins ===
    ax = axes[2]
    ax.bar([p - bar_width / 2 for p in x_pos], proteins, width=bar_width, 
           label=t("chart.legend.actual"), color=colors["proteins"], edgecolor="black", linewidth=0.5)
    ax.plot(x_pos, prot_norm, label=t("chart.legend.norm"), color=colors["norm"], linewidth=2, marker="o", markersize=4)
    ax.set_title(t("chart.proteins.title"), fontweight="bold", pad=5, color="white")
    ax.set_ylabel(t("chart.proteins.ylabel"), color="white")
    ax.tick_params(axis="both", colors="white")
    ax.set_xticks(x_pos)
    ax.set_xticklabels([d[5:] for d in dates], rotation=45, ha="right", color="white")
    ax.legend(loc="upper right", fontsize=8, facecolor="gray", edgecolor="white", labelcolor="white")
    ax.grid(axis="y", linestyle="--", alpha=0.3, color="gray")
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("white")
    ax.spines["bottom"].set_color("white")

    # === 4. Fats ===
    ax = axes[3]
    ax.bar([p - bar_width / 2 for p in x_pos], fats, width=bar_width, 
           label=t("chart.legend.actual"), color=colors["fats"], edgecolor="black", linewidth=0.5)
    ax.plot(x_pos, fats_norm, label=t("chart.legend.norm"), color=colors["norm"], linewidth=2, marker="o", markersize=4)
    ax.set_title(t("chart.fats.title"), fontweight="bold", pad=5, color="white")
    ax.set_ylabel(t("chart.fats.ylabel"), color="white")
    ax.tick_params(axis="both", colors="white")
    ax.set_xticks(x_pos)
    ax.set_xticklabels([d[5:] for d in dates], rotation=45, ha="right", color="white")
    ax.legend(loc="upper right", fontsize=8, facecolor="gray", edgecolor="white", labelcolor="white")
    ax.grid(axis="y", linestyle="--", alpha=0.3, color="gray")
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("white")
    ax.spines["bottom"].set_color("white")

    # === 5. Carbohydrates ===
    ax = axes[4]
    ax.bar([p - bar_width / 2 for p in x_pos], carbs, width=bar_width, 
           label=t("chart.legend.actual"), color=colors["carbs"], edgecolor="black", linewidth=0.5)
    ax.plot(x_pos, carbs_norm, label=t("chart.legend.norm"), color=colors["norm"], linewidth=2, marker="o", markersize=4)
    ax.set_title(t("chart.carbs.title"), fontweight="bold", pad=5, color="white")
    ax.set_ylabel(t("chart.carbs.ylabel"), color="white")
    ax.set_xlabel(t("chart.xlabel_date"), color="white")
    ax.tick_params(axis="both", colors="white")
    ax.set_xticks(x_pos)
    ax.set_xticklabels([d[5:] for d in dates], rotation=45, ha="right", color="white")
    ax.legend(loc="upper right", fontsize=8, facecolor="gray", edgecolor="white", labelcolor="white")
    ax.grid(axis="y", linestyle="--", alpha=0.3, color="gray")
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("white")
    ax.spines["bottom"].set_color("white")

    with _lock:
        st.pyplot(fig, width='stretch', bbox_inches="tight")

    plt.close(fig)