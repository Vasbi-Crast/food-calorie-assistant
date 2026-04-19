import streamlit as st
import matplotlib.pyplot as plt
from threading import RLock

_lock = RLock()


def _calculate_total_macros():
    if "widget_table" in st.session_state:
        edited_rows = st.session_state["widget_table"].get('edited_rows')
        added_rows = st.session_state["widget_table"].get('added_rows')
        deleted_rows = st.session_state["widget_table"].get('deleted_rows')
        for r_key, r_val in edited_rows.items():
            for key, val in r_val.items():
                st.session_state["table_ingredients"][r_key][key] = val
        for val in added_rows:
            st.session_state["table_ingredients"].append(val)
        deleted_row = set(deleted_rows) - set(st.session_state["last_table_ingredients"])
        for idx in deleted_row:
            del(st.session_state["table_ingredients"][idx])
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


def plot_nutritional_info(nutritional_info=None):
    """Visualizes ingredient list and total nutrition (donut chart)."""

    if not st.session_state.get("table_ingredients"):
        if not nutritional_info:
            st.warning("No data to display")
            return
            
        rows = []
        for item in nutritional_info:
            if not isinstance(item, dict) or not item:
                continue
            
            original_name, payload = next(iter(item.items()))
            if not payload:
                rows.append({
                    "ingredient": original_name,
                    "match": "no match",
                    "weight_g": 0,
                    "calories": 0,
                    "proteins": 0,
                    "fats": 0,
                    "carbohydrates": 0,
                })
            else:
                rows.append({
                    "ingredient": original_name,
                    "match": payload.get("match", ""),
                    "weight_g": payload.get("weight", 0),
                    "calories": payload.get("calories", 0),
                    "proteins": payload.get("proteins", 0),
                    "fats": payload.get("fats", 0),
                    "carbohydrates": payload.get("carbohydrates", 0),
                })
        
        st.session_state["table_ingredients"] = rows
        _calculate_total_macros()

    st.subheader("Ingredients")
    st.data_editor(
        st.session_state["table_ingredients"],
        key="widget_table",
        on_change=_calculate_total_macros,
        use_container_width=True,
        hide_index=True,
        num_rows="dynamic",
        column_config={
    "ingredient": st.column_config.TextColumn(
        "Ingredient",
        max_chars=25,
        validate=r"^[a-zA-Zа-яА-Я0-9\s\-_]+$",
        required=True,
        help="Ingredient name (e.g., apple, rice, chicken breast)"
    ),
    "match": st.column_config.TextColumn(
        "Match",
        max_chars=50,
        validate=None,
        required=False,
        help="Matched name from database (auto-detected or manual)"
    ),
    "weight_g": st.column_config.NumberColumn(
        "Weight (g)",
        min_value=0.0,
        max_value=10000.0,
        format="%.2f",
        step=1.0,
        help="Weight of the ingredient in grams"
    ),
    "calories": st.column_config.NumberColumn(
        "Calories",
        min_value=0.0,
        max_value=10000.0,
        format="%.1f",
        step=1.0,
        help="Calorie content of the ingredient"
    ),
    "proteins": st.column_config.NumberColumn(
        "Proteins (g)",
        min_value=0.0,
        max_value=1000.0,
        format="%.2f",
        step=0.1,
        help="Protein content in grams"
    ),
    "fats": st.column_config.NumberColumn(
        "Fats (g)",
        min_value=0.0,
        max_value=1000.0,
        format="%.2f",
        step=0.1,
        help="Fat content in grams"
    ),
    "carbohydrates": st.column_config.NumberColumn(
        "Carbohydrates (g)",
        min_value=0.0,
        max_value=1000.0,
        format="%.2f",
        step=0.1,
        help="Carbohydrate content in grams"
    ),
}
    )

    st.subheader("Total nutrition")

    total = st.session_state.get("total_macros", {
        "calories": 0, "proteins": 0, "fats": 0, "carbohydrates": 0
    })
    
    sizes = []
    labels = []
    colors = {
    "proteins": [0.122, 0.467, 0.706],
    "fats": [1.0, 0.498, 0.055],
    "carbohydrates": [0.173, 0.627, 0.173]
    }
    for key, val in total.items():
        if key == "calories":
            continue
        if val > 0:
            sizes.append(val)
            labels.append(key)
    
    with _lock:
        fig, ax = plt.subplots()
        fig.patch.set_alpha(0.0)
        
        if labels:
            if len(labels) == 1:
                wedges, texts = ax.pie(
                    sizes,
                    labels=labels,
                    startangle=90,
                    wedgeprops={"width": 0.5},
                    colors=[colors.get(labels[0], [1., 1., 1.])]
                )

                ax.set_title(labels[0][0].upper() + labels[0][1:], fontdict = {"color": "white", "fontsize": 18})
                
                plt.text(
                    0, 0,
                    f'{round(sizes[0], 1)} g.\n{round(total["calories"], 1)} kcal',
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
                    f'{round(total["calories"], 0)}\nkcal',
                    horizontalalignment="center",
                    verticalalignment="center",
                    fontsize=20,
                    color="white",
                )
        else:
            ax.pie([1], colors=[[0.5, 0.5, 0.5]])
            plt.text(
                0, 0,
                f'No data',
                horizontalalignment="center",
                verticalalignment="center",
                fontsize=20,
                color="white",
            )
        
        ax.axis("equal")
        st.pyplot(fig, use_container_width=True, transparent=True)


def display_days_nutrition_overview(days_info, norms_info):
    st.subheader("Information of the day")

    labels = ["calories", "proteins", "fats", "carbohydrates"]
    values_day = [days_info[label] for label in labels]
    norms_day = [norms_info[label] for label in labels]
    colors = [[251, 251, 243], [29, 97, 221], [127, 20, 20], [165, 165, 41]]
    colors = [[el / 255.0 for el in color] for color in colors]

    with _lock:
        fig, ax = plt.subplots(2, 2, figsize=(10, 10))
        fig.patch.set_alpha(0.0)
        ax = ax.reshape(1, 4)[0]

        for el, val, norm, label, color in zip(
            ax, values_day, norms_day, labels, colors
        ):
            label = label[0].upper() + label[1:]
            remain = max(0, norm - val)
            wedges, texts = el.pie(
                [val, remain],
                startangle=90,
                wedgeprops={"width": 0.2},
                colors=[color + [1.0], color + [0.3]],
            )

            el.axis("equal")
            el.set_title(label, color="white", fontsize=18, pad=8)

            for text in texts:
                text.set_visible(False)

            if label != "Calories":
                el.text(
                    0,
                    0,
                    f"{int(val)} / {int(norm)}\ng.",
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
                    f"{int(val)} / {int(norm)}\nKcal.",
                    horizontalalignment="center",
                    verticalalignment="center",
                    fontsize=14,
                    color="white",
                    fontweight="bold",
                )
        st.pyplot(fig)
