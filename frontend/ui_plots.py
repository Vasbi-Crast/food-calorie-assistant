import streamlit as st
import matplotlib.pyplot as plt
from threading import RLock
from ui_processing import calculate_total_macros

from ui import t

_lock = RLock()


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
        use_container_width=True,
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
    ax.set_title(t("chart.weight.title"), fontweight="bold", pad=5, color="white")  # ✅ "Weight Trend"
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
           label=t("chart.legend.actual"), color=colors["calories"], edgecolor="black", linewidth=0.5)  # ✅ "Actual"
    ax.plot(x_pos, cal_norm, label=t("chart.legend.norm"), color=colors["norm"], linewidth=2, marker="o", markersize=4)  # ✅ "Norm"
    ax.set_title(t("chart.calories.title"), fontweight="bold", pad=5, color="white")  # ✅ "Calories vs Norm"
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
        st.pyplot(fig, use_container_width=True, bbox_inches="tight")

    plt.close(fig)


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
                "match": "",
                "weight": 0.0,
                "calories": 0.0,
                "proteins": 0.0,
                "fats": 0.0,
                "carbohydrates": 0.0,
            }
        ]

    has_match = any("match" in row for row in st.session_state["table_ingredients"])

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

    if has_match:
        column_config["match"] = st.column_config.TextColumn(
            t("ui.table.match"),
            max_chars=50,
            validate=None,
            required=False,
            help=t("help.table.match"),
        )

    st.data_editor(
        st.session_state["table_ingredients"],
        key="recognition_widget_table",
        on_change=calculate_total_macros,
        use_container_width=True,
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
        st.pyplot(fig, use_container_width=True, transparent=True)

    plt.close(fig)


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
        st.pyplot(fig, use_container_width=True)

    plt.close()