"""Handler module for general statistics visualization.

Provides functions to fetch weight history, nutrition data, and norms
from the backend API, and renders comparative charts using Matplotlib.
"""
import streamlit as st
from typing import Dict, List, Optional, Any, Union
import datetime as dt
import matplotlib.pyplot as plt
from threading import RLock

from handlers.api_handler import api_request, check_activity
from translator import Translator

t = Translator()


def _parse_time_span(
    time_span: Union[List[dt.datetime], dt.datetime],
) -> tuple[str, str, bool]:
    """Parses time_span argument into start/end date strings and one_day flag.

    Args:
        time_span (Union[List[datetime], datetime]): A single datetime object
            for a specific day, or a list/tuple of two datetimes [start, end].

    Returns:
        Tuple[str, str, bool]: (start_date, end_date, is_single_day)
            Dates formatted as "YYYY-MM-DD".
    """
    if isinstance(time_span, (list, tuple)) and len(time_span) == 2:
        start = min(time_span).strftime("%Y-%m-%d")
        end = max(time_span).strftime("%Y-%m-%d")
        return start, end, False
    elif isinstance(time_span, dt.datetime):
        date_str = time_span.strftime("%Y-%m-%d")
        return date_str, date_str, True
    else:
        st.error("⚠️ Incorrect time interval format.")
        return "", "", False


def _fetch_history_data(
    endpoint: str,
    time_span: Union[List[dt.datetime], dt.datetime],
    one_day_default: Any = None,
    convert_values: bool = True,
) -> Optional[Dict[str, Any]]:
    """Internal helper to fetch history data from backend API.

    Args:
        endpoint (str): API endpoint name (e.g., "info_nutrition").
        time_span (Union[List[datetime], datetime]): Date range or single date.
        one_day_default (Any): Default value to return for single-day queries
            if no data is found. Defaults to None.
        convert_values (bool): Whether to convert nested values to float.
            Defaults to True.

    Returns:
        Optional[Dict[str, Any]]: Parsed response dictionary or None on error.
    """
    start, end, one_day = _parse_time_span(time_span)
    if not start:
        return None

    params = {"start": start, "end": end}
    response = api_request("GET", endpoint, params=params)
    
    if not response:
        return None
    
    if convert_values:
        parsed = {
            r_key: {key: float(val) for key, val in r_val.items()}
            for r_key, r_val in response.items()
        }
    else:
        parsed = {key: float(val) for key, val in response.items()}
    
    return parsed.get(start, one_day_default) if one_day else parsed


def get_weight_history(
    time_span: Union[List[dt.datetime], dt.datetime] = dt.datetime.now(),
) -> Optional[Dict[str, float]]:
    """Retrieves user weight history for a specified time period.

    Args:
        time_span (Union[List[datetime], datetime]): A single datetime object
            for a specific day, or a list/tuple of two datetimes [start, end].

    Returns:
        Optional[Dict[str, float]]: Dictionary keyed by date strings with weight
            values as floats, or None if the API request fails. For a single day,
            returns the full dict (may contain one key) or None if not found.
    """
    return _fetch_history_data("weight_history", time_span, convert_values=False)


def get_info_nutrition(
    time_span: Union[List[dt.datetime], dt.datetime] = dt.datetime.now(),
) -> Optional[Dict[str, Dict[str, float]]]:
    """Retrieves nutrition consumption history for a specified time period.

    Args:
        time_span (Union[List[datetime], datetime]): A single datetime object
            for a specific day, or a list/tuple of two datetimes [start, end].

    Returns:
        Optional[Dict[str, Dict[str, float]]]: Dictionary keyed by date strings
            containing nutrition data (calories, proteins, fats, carbohydrates),
            or None if the request fails.
    """
    return _fetch_history_data("info_nutrition", time_span, one_day_default={})


def get_nutrition_norms(
    time_span: Union[List[dt.datetime], dt.datetime] = dt.datetime.now(),
) -> Optional[Dict[str, Dict[str, float]]]:
    """Retrieves daily nutrition norms for a specified time period.

    Args:
        time_span (Union[List[datetime], datetime]): A single datetime object
            for a specific day, or a list/tuple of two datetimes [start, end].

    Returns:
        Optional[Dict[str, Dict[str, float]]]: Dictionary keyed by date strings
            containing norm values, or None if the request fails.
    """
    return _fetch_history_data("daily_nutrition_norms", time_span, one_day_default={})


def get_statistic_info() -> None:
    """Fetches all statistic data for the selected date range from the backend.

    Retrieves weight history, nutrition consumption, and nutrition norms for
    the date range stored in session_state. Updates session_state["stat_data"]
    and sets saved_data flag to True upon completion.
    """
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
    """Renders five comparative charts for general statistics using Matplotlib.

    Displays:
        1. Weight history (bar chart)
        2. Calories: actual vs norm (bar + line)
        3. Proteins: actual vs norm (bar + line)
        4. Fats: actual vs norm (bar + line)
        5. Carbohydrates: actual vs norm (bar + line)

    Uses a reentrant lock for thread-safe rendering in Streamlit.
    Expects session_state["stat_data"] to contain weight, info_nutrition,
    and norms dictionaries keyed by date strings.
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
    date_labels = [dt.datetime.strptime(date, "%Y-%m-%d").strftime("%d-%m") for date in dates]
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

    bar_width = 0.35
    
    def style_dark_axis(ax: plt.Axes, title: str, ylabel: str, xlabel: str = "", pad_title: float = 50.0):
        ax.set_title(title, loc="center", fontweight="bold", pad=pad_title, color="white")
        ax.set_ylabel(ylabel, color="white")
        if xlabel:
            ax.set_xlabel(xlabel, color="white")
        ax.tick_params(axis="both", colors="white")
        ax.set_xticks(x_pos)
        ax.set_xticklabels(date_labels, rotation=45, ha="right", color="white")
        ax.grid(axis="y", linestyle="--", alpha=0.3, color="gray")
        ax.set_axisbelow(True)
        for spine in ["top", "right"]:
            ax.spines[spine].set_visible(False)
        for spine in ["left", "bottom"]:
            ax.spines[spine].set_color("white")

    with _lock:
        # === 1. Weight ===
        fig, ax = plt.subplots(figsize=(6, 4), constrained_layout=True)
        fig.patch.set_alpha(0.0)
        ax.bar(
            x_pos,
            weight_values,
            color=colors["weight"],
            edgecolor="black",
            linewidth=0.5,
        )
        style_dark_axis(ax, t("chart.weight.title"), t("chart.weight.ylabel"), pad_title=10)
        st.pyplot(fig, width="stretch")
        st.divider()
        plt.close(fig)

        # === 2. Calories ===
        fig, ax = plt.subplots(figsize=(6, 4), constrained_layout=True)
        fig.patch.set_alpha(0.0)
        ax.bar(
            [p - bar_width / 2 for p in x_pos],
            calories,
            width=bar_width,
            label=t("chart.legend.actual"),
            color=colors["calories"],
            edgecolor="black",
            linewidth=0.5,
        )
        ax.plot(
            x_pos,
            cal_norm,
            label=t("chart.legend.norm"),
            color=colors["norm"],
            linewidth=2,
            marker="o",
            markersize=4,
        )
        style_dark_axis(ax, t("chart.calories.title"), t("chart.calories.ylabel"))
        ax.legend(
            loc="upper right",
            bbox_to_anchor=(1, 1.2),
            fontsize=8,
            facecolor="gray",
            edgecolor="white",
            labelcolor="white",
        )
        st.pyplot(fig, width="stretch")
        st.divider()
        plt.close(fig)

        # === 3. Proteins ===
        fig, ax = plt.subplots(figsize=(6, 4), constrained_layout=True)
        fig.patch.set_alpha(0.0)
        ax.bar(
            [p - bar_width / 2 for p in x_pos],
            proteins,
            width=bar_width,
            label=t("chart.legend.actual"),
            color=colors["proteins"],
            edgecolor="black",
            linewidth=0.5,
        )
        ax.plot(
            x_pos,
            prot_norm,
            label=t("chart.legend.norm"),
            color=colors["norm"],
            linewidth=2,
            marker="o",
            markersize=4,
        )
        style_dark_axis(ax, t("chart.proteins.title"), t("chart.proteins.ylabel"))
        ax.legend(
            loc="upper right",
            bbox_to_anchor=(1, 1.2),
            fontsize=8,
            facecolor="gray",
            edgecolor="white",
            labelcolor="white",
        )
        st.pyplot(fig, width="stretch")
        st.divider()
        plt.close(fig)

        # === 4. Fats ===
        fig, ax = plt.subplots(figsize=(6, 4), constrained_layout=True)
        fig.patch.set_alpha(0.0)
        ax.bar(
            [p - bar_width / 2 for p in x_pos],
            fats,
            width=bar_width,
            label=t("chart.legend.actual"),
            color=colors["fats"],
            edgecolor="black",
            linewidth=0.5,
        )
        ax.plot(
            x_pos,
            fats_norm,
            label=t("chart.legend.norm"),
            color=colors["norm"],
            linewidth=2,
            marker="o",
            markersize=4,
        )
        style_dark_axis(ax, t("chart.fats.title"), t("chart.fats.ylabel"))
        ax.legend(
            loc="upper right",
            bbox_to_anchor=(1, 1.2),
            fontsize=8,
            facecolor="gray",
            edgecolor="white",
            labelcolor="white",
        )
        st.pyplot(fig, width="stretch")
        st.divider()
        plt.close(fig)

        # === 5. Carbohydrates ===
        fig, ax = plt.subplots(figsize=(6, 4), constrained_layout=True)
        fig.patch.set_alpha(0.0)
        ax.bar(
            [p - bar_width / 2 for p in x_pos],
            carbs,
            width=bar_width,
            label=t("chart.legend.actual"),
            color=colors["carbs"],
            edgecolor="black",
            linewidth=0.5,
        )
        ax.plot(
            x_pos,
            carbs_norm,
            label=t("chart.legend.norm"),
            color=colors["norm"],
            linewidth=2,
            marker="o",
            markersize=4,
        )
        style_dark_axis(ax, t("chart.carbs.title"), t("chart.carbs.ylabel"))
        ax.legend(
            loc="upper right",
            bbox_to_anchor=(1, 1.2),
            fontsize=8,
            facecolor="gray",
            edgecolor="white",
            labelcolor="white",
        )
        st.pyplot(fig, width="stretch")
        plt.close(fig)
        st.divider()