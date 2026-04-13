import streamlit as st
import matplotlib.pyplot as plt
from threading import RLock

from ui_processing import get_info_nutrition

_lock = RLock()


def plot_nutritional_info(nutritional_info):
    """Visualizes ingredient list and total nutrition (donut chart)."""
    if not nutritional_info:
        st.warning("No ingredients found.")
        return

    rows = []
    total = {"calories": 0.0, "proteins": 0.0, "fats": 0.0, "carbohydrates": 0.0}

    for item in nutritional_info:
        if not isinstance(item, dict) or not item:
            continue
        original_name, payload = next(iter(item.items()))
        if not payload:
            rows.append(
                {
                    "ingredient": original_name,
                    "match": "",
                    "weight_g": "",
                    "calories": "",
                    "proteins": "",
                    "fats": "",
                    "carbohydrates": "",
                }
            )
            continue

        rows.append(
            {
                "ingredient": original_name,
                "match": payload.get("match", ""),
                "weight_g": payload.get("weight", ""),
                "calories": payload.get("calories", ""),
                "proteins": payload.get("proteins", ""),
                "fats": payload.get("fats", ""),
                "carbohydrates": payload.get("carbohydrates", ""),
            }
        )

        for k in total:
            try:
                total[k] += float(payload.get(k, 0) or 0)
            except (TypeError, ValueError):
                pass

    st.subheader("Ingredients")
    st.table(rows)

    st.subheader("Total nutrition")
    labels = "Proteins", "Fats", "Carbohydrates"
    sizes = [total["proteins"], total["fats"], total["carbohydrates"]]

    with _lock:
        fig, ax = plt.subplots()
        fig.patch.set_alpha(0.0)

        wedges, texts, autotexts = ax.pie(
            sizes,
            labels=labels,
            autopct=lambda p: f"{p * sum(sizes) / 100:.0f}",
            startangle=90,
            wedgeprops={"width": 0.5},
        )

        ax.axis("equal")

        for text in texts:
            text.set_color("white")

        for autotext in autotexts:
            autotext.set_color("white")
            autotext.set_fontsize(16)
            x, y = autotext.get_position()
            autotext.set_position((x * 1.2, y * 1.2))

        plt.text(
            0,
            0,
            f'{round(total["calories"], 0)}\nkcal',
            horizontalalignment="center",
            verticalalignment="center",
            fontsize=20,
            color="white",
        )

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
