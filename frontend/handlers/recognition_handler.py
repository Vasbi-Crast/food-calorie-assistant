import streamlit as st
from typing import List, Optional, Dict
import datetime as dt
import matplotlib.pyplot as plt
from threading import RLock
import json


from handlers.api_handler import api_request, check_activity
from translator import Translator
t = Translator()

_lock = RLock()

def clear_new_uploader():
    """Clears uploader-related session state."""
    check_activity()
    st.session_state["table_ingredients"], st.session_state["total_macros"] = None, None
    st.session_state["last_table_ingredients"] = []
    
def get_meal_macros(
    image_base64: str, user_description: str
) -> Optional[List[Dict]]:
    """
    Sends image for ingredient recognition and nutrition search.
    No authentication required.
    
    Args:
        image_base64 (str): Base64-encoded image data.
        user_description (str): Optional dish description.
    
    Returns:
        list: List of ingredient dicts, or None on error.
    """
    payload = {"image_base64": image_base64, "user_description": user_description}

    response = api_request(
        "POST", "ingredient_recognition", json=payload
    )

    if response:
        result = response.get("result")
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except json.JSONDecodeError:
                st.warning(t("warning.recognition.parse_failed"))
                return None

        if result:
            return result
        else:
            st.warning(t("warning.recognition.no_data"))
    return None

def save_dish() -> bool:
    """
    Saves the current dish from the table to the database.
    
    Returns:
        bool: True if successful, False otherwise.
    """
    ingredients = st.session_state.get("table_ingredients")
    if not ingredients:
        st.error(t("error.dish.no_ingredients"))
        return False

    payload = {
        "name": [],
        "weight": [],
        "calories": [],
        "proteins": [],
        "fats": [],
        "carbohydrates": [],
        "created_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    for row in ingredients:
        payload["name"].append(row.get("ingredient", "").strip())
        payload["weight"].append(float(row.get("weight", 0)))
        payload["calories"].append(float(row.get("calories", 0)))
        payload["proteins"].append(float(row.get("proteins", 0)))
        payload["fats"].append(float(row.get("fats", 0)))
        payload["carbohydrates"].append(float(row.get("carbohydrates", 0)))

    res = api_request("POST", "add_new_dish", json=payload)

    if res:
        st.session_state["days_info"] = None
        return True
    return False

def parse_dish(nutritional_info):
    """
    Parses LLM response into ingredients table.
    
    Args:
        nutritional_info: List of ingredient dicts from LLM.
    """
    if not nutritional_info:
        st.warning("No data to display")
        return

    rows = []
    for item in nutritional_info:
        if not isinstance(item, dict) or not item:
            continue

        original_name, payload = next(iter(item.items()))
        if not payload:
            rows.append(
                {
                    "ingredient": original_name,
                    "weight": 0,
                    "calories": 0,
                    "proteins": 0,
                    "fats": 0,
                    "carbohydrates": 0,
                }
            )
        else:
            rows.append(
                {
                    "ingredient": original_name,
                    "weight": payload.get("weight", 0),
                    "calories": payload.get("calories", 0),
                    "proteins": payload.get("proteins", 0),
                    "fats": payload.get("fats", 0),
                    "carbohydrates": payload.get("carbohydrates", 0),
                }
            )

    st.session_state["table_ingredients"] = rows
    update_table_and_total_macros()

def update_table_and_total_macros():
    """Calculates total macros from the ingredients table."""
    if "recognition_widget_table" in st.session_state:
        edited_rows = st.session_state["recognition_widget_table"].get("edited_rows")
        added_rows = st.session_state["recognition_widget_table"].get("added_rows")
        deleted_rows = st.session_state["recognition_widget_table"].get("deleted_rows")
        for r_key, r_val in edited_rows.items():
            for key, val in r_val.items():
                print(r_key, r_val, key, val)
                st.session_state["table_ingredients"][r_key][key] = val
                
        for val in added_rows:
            st.session_state["table_ingredients"].append(val)

        deleted_row = set(deleted_rows) - set(
            st.session_state["last_table_ingredients"]
        )
        if deleted_row:
            st.session_state["table_ingredients"] = [
                row
                for idx, row in enumerate(st.session_state["table_ingredients"])
                if idx not in deleted_row
            ]

        st.session_state["last_table_ingredients"] = deleted_rows

    total = {"calories": 0.0, "proteins": 0.0, "fats": 0.0, "carbohydrates": 0.0}

    for row in st.session_state.get("table_ingredients", []):
        for key in total.keys():
            try:
                value = row.get(key)
                if value is None or value == "":
                    value = 0.0
                total[key] += float(value)
            except (TypeError, ValueError):
                pass

    st.session_state["total_macros"] = total
    
def plot_nutritional_info():
    """
    Visualizes ingredient list and total nutrition (donut chart).
    Used on recognition page after image analysis.
    """
    st.subheader(t("ui.recognition.ingredients"))

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

    column_config = {
        "ingredient": st.column_config.TextColumn(
            t("ui.table.ingredient"),
            max_chars=25,
            validate=r"^[a-zA-Zа-яА-Я0-9\s\-_]+$",
            required=True,
            help=t("help.table.ingredient"),
        ),
        "weight": st.column_config.NumberColumn(
            t("ui.table.weight_g"),
            min_value=0.0,
            max_value=10000.0,
            format="%.2f",
            step=0.1,
            required=True,
            help=t("help.table.weight"),
        ),
        "calories": st.column_config.NumberColumn(
            t("ui.table.calories_kcal"),
            min_value=0.0,
            max_value=10000.0,
            format="%.1f",
            step=0.1,
            required=True,
            help=t("help.table.calories"),
        ),
        "proteins": st.column_config.NumberColumn(
            t("ui.table.proteins_g"),
            min_value=0.0,
            max_value=1000.0,
            format="%.2f",
            step=0.1,
            required=True,
            help=t("help.table.proteins"),
        ),
        "fats": st.column_config.NumberColumn(
            t("ui.table.fats_g"),
            min_value=0.0,
            max_value=1000.0,
            format="%.2f",
            step=0.1,
            required=True,
            help=t("help.table.fats"),
        ),
        "carbohydrates": st.column_config.NumberColumn(
            t("ui.table.carbs_g"),
            min_value=0.0,
            max_value=1000.0,
            format="%.2f",
            step=0.1,
            required=True,
            help=t("help.table.carbs"),
        ),
    }

    st.data_editor(
        st.session_state["table_ingredients"],
        key="recognition_widget_table",
        on_change=update_table_and_total_macros,
        width='stretch',
        hide_index=True,
        num_rows="dynamic",
        column_config=column_config,
    )

    st.subheader(t("ui.recognition.total"))

    total = st.session_state.get(
        "total_macros", {"calories": 0, "proteins": 0, "fats": 0, "carbohydrates": 0}
    )

    sizes = []
    labels = []
    colors = {
        "proteins": [0.122, 0.467, 0.706],
        "fats": [1.0, 0.498, 0.055],
        "carbohydrates": [0.173, 0.627, 0.173],
    }

    for key, val in total.items():
        if key == "calories":
            continue
        if val and val > 0:
            sizes.append(val)
            labels.append(key)

        fig, ax = plt.subplots()
        fig.patch.set_alpha(0.0)

        if labels:
            if len(labels) == 1:
                wedges, texts = ax.pie(
                    sizes,
                    labels=[""],
                    startangle=90,
                    wedgeprops={"width": 0.5},
                    colors=[colors.get(labels[0], [1.0, 1.0, 1.0])],
                )

                label_title = t(f"macros.{labels[0]}")
                ax.set_title(label_title, fontdict={"color": "white", "fontsize": 18})

                unit_g = t("ui.unit.g")
                unit_kcal = t("ui.unit.kcal")
                
                plt.text(
                    0, 0,
                    f'{round(sizes[0], 1)} {unit_g}\n{round(total["calories"], 1)} {unit_kcal}',
                    horizontalalignment="center",
                    verticalalignment="center",
                    fontsize=14,
                    color="white",
                )

            else:
                wedges, texts, autotexts = ax.pie(
                    sizes,
                    labels=labels,
                    autopct=lambda p: f"{p * sum(sizes) / 100:.0f}",
                    startangle=90,
                    wedgeprops={"width": 0.5},
                )

                for text in texts:
                    text.set_color("white")

                for autotext in autotexts:
                    autotext.set_color("white")
                    autotext.set_fontsize(16)
                    x, y = autotext.get_position()
                    autotext.set_position((x * 1.2, y * 1.2))

                plt.text(
                    0, 0,
                    f'{round(total["calories"], 0)}\n{t("ui.unit.kcal")}',
                    horizontalalignment="center",
                    verticalalignment="center",
                    fontsize=20,
                    color="white",
                )
        else:
            ax.pie([1], colors=[[0.5, 0.5, 0.5]])
            plt.text(
                0, 0,
                t("ui.chart.no_data"),
                horizontalalignment="center",
                verticalalignment="center",
                fontsize=20,
                color="white",
            )

        ax.axis("equal")

    with _lock:
        st.pyplot(fig, width='stretch', transparent=True)

    plt.close(fig)