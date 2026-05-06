import streamlit as st
from typing import Dict, List

import datetime as dt

from handlers.api_handler import api_request
from translator import Translator
t = Translator()

def get_daily_log(date: dt.datetime) -> List[Dict] | None:
    """
    Fetches daily log for a specific date.
    
    Args:
        date (datetime): Date to fetch log for.
    
    Returns:
        list: List of ingredient dicts, or empty list on error.
    
    Note:
        Date format changed to YYYY-MM-DD for SingleDate model.
    """
    params = {"date": date.strftime("%Y-%m-%d")}

    res = api_request("GET", "get_daily_log", params=params)

    if res:
        float_keys = ["weight", "calories", "proteins", "fats", "carbohydrates"]
        for row in res:
            for key, val in row.items():
                if key in float_keys and val is not None:
                    row[key] = float(val)
        st.session_state["table_ingredients"] = res
        return res
    return []

def daily_nutritional_table():
    """
    Displays editable table of ingredients for daily log page.
    Shows: ingredient, weight, calories, proteins, fats, carbohydrates.
    """
    if not st.session_state["table_ingredients"]:
        st.session_state["table_ingredients"] = [
            {
                "ingredient": "",
                "weight": 0.0,
                "calories": 0.0,
                "proteins": 0.0,
                "fats": 0.0,
                "carbohydrates": 0.0,
            }
        ]
        st.session_state["empty_day"] = True

    st.data_editor(
        st.session_state["table_ingredients"],
        key="log_widget_table",
        width='stretch',
        hide_index=True,
        num_rows="dynamic",
        column_config={
            "ingredient": st.column_config.TextColumn(
                t("ui.table.ingredient"),
                max_chars=25,
                required=True,
            ),
            "weight": st.column_config.NumberColumn(
                t("ui.table.weight_g"),
                min_value=0.0,
                format="%.1f",
                step=0.1,
            ),
            "calories": st.column_config.NumberColumn(
                t("ui.table.calories_kcal"),
                min_value=0.0,
                format="%.1f",
                step=0.1,
            ),
            "proteins": st.column_config.NumberColumn(
                t("ui.table.proteins_g"),
                min_value=0.0,
                format="%.2f",
                step=0.1,
            ),
            "fats": st.column_config.NumberColumn(
                t("ui.table.fats_g"),
                min_value=0.0,
                format="%.2f",
                step=0.1,
            ),
            "carbohydrates": st.column_config.NumberColumn(
                t("ui.table.carbs_g"),
                min_value=0.0,
                format="%.2f",
                step=0.1,
            ),
        },
    )

    total = {
        "weight": 0.0,
        "calories": 0.0,
        "proteins": 0.0,
        "fats": 0.0,
        "carbohydrates": 0.0,
    }
    for row in st.session_state.get("table_ingredients", []):
        for key in total.keys():
            try:
                value = row.get(key, 0)
                if value is not None and value != "" and value != "-":
                    total[key] += float(value)
            except (TypeError, ValueError):
                pass
    
    if st.session_state.get("saved_data", False):
        st.success(t("ui.table.saved_success"))
        st.session_state["saved_data"] = False
    
    st.divider()
    st.subheader(t("ui.table.total"))

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric(t("ui.metric.weight_g"), f"{total['weight']:.2f}")
    with col2:
        st.metric(t("ui.metric.calories_kcal"), f"{total['calories']:.1f}")
    with col3:
        st.metric(t("ui.metric.proteins_g"), f"{total['proteins']:.2f}")
    with col4:
        st.metric(t("ui.metric.fats_g"), f"{total['fats']:.2f}")
    with col5:
        st.metric(t("ui.metric.carbs_g"), f"{total['carbohydrates']:.2f}")

def change_daily_log(date: dt.datetime) -> bool:
    """
    Detects and saves ONLY the specific changes made in data_editor.
    Clears widget state after processing to prevent accumulation.
    
    Args:
        date (datetime): Date of the log to update.
    
    Returns:
        bool: True if successful, False otherwise.
    """
    widget_data = st.session_state.get("log_widget_table", {})

    edited_rows = widget_data.get("edited_rows", {}).copy()
    added_rows = widget_data.get("added_rows", []).copy()
    deleted_rows = widget_data.get("deleted_rows", []).copy()

    edited_converted = []
    for r_key, r_val in edited_rows.items():
        ed_row = st.session_state["table_ingredients"][int(r_key)].copy()
        for key, val in r_val.items():
            ed_row[key] = val
        edited_converted.append(
            {
                "name": ed_row["ingredient"],
                "weight": ed_row["weight"],
                "calories": ed_row["calories"],
                "proteins": ed_row["proteins"],
                "fats": ed_row["fats"],
                "carbohydrates": ed_row["carbohydrates"],
            }
        )

    added_converted = []
    for row in added_rows:
        added_converted.append(
            {
                "name": row["ingredient"],
                "weight": row["weight"],
                "calories": row["calories"],
                "proteins": row["proteins"],
                "fats": row["fats"],
                "carbohydrates": row["carbohydrates"],
            }
        )

    deleted_converted = [
        st.session_state["table_ingredients"][int(key)]["ingredient"]
        for key in deleted_rows
        if int(key) < len(st.session_state["table_ingredients"])
    ]

    if not st.session_state.get("empty_day"):
        changes = {
            "edited": edited_converted,
            "added": added_converted,
            "deleted": deleted_converted,
            "date": date.strftime("%Y-%m-%d"),
        }
    else:
        changes = {
            "edited": [],
            "added": edited_converted,
            "deleted": [],
            "date": date.strftime("%Y-%m-%d"),
        }
        if edited_converted:
            st.session_state["empty_day"] = False

    res = api_request("PUT", "daily_log/update", json=changes)
    return res is not None