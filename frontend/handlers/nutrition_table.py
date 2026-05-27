import streamlit as st
import datetime as dt
import uuid

from handlers.api_handler import check_activity, ing_translator
from translator import Translator, detect_input_language, get_canonical_name

t = Translator()


def add_new_ingredient(
    name: str,
    weight: float,
    calories: float,
    proteins: float,
    fats: float,
    carbohydrates: float,
) -> bool:
    """Adds a new ingredient to session_state"""
    input_lang = detect_input_language(name)

    canonical_key = ing_translator.register(name, input_lang)

    for item in st.session_state.get("table_ingredients", []):
        if ing_translator.resolve(item["name"],  st.session_state.get("language")) == canonical_key:
            return False

    st.session_state["table_ingredients"].append(
        {
            "idx": str(uuid.uuid4()),
            "name": canonical_key,
            "weight": weight,
            "calories": calories,
            "proteins": proteins,
            "fats": fats,
            "carbohydrates": carbohydrates,
            "owner": st.session_state["username"].lower(),
        }
    )

    return True


def clear_new_uploader():
    """Clears uploader-related session state."""
    check_activity()
    for key in list(st.session_state.keys()):
        if key.startswith(("weight_", "edit_", "delete_")):
            del st.session_state[key]
    st.session_state["table_ingredients"] = None


def update_ingredient_weight(idx: int, new_weight: float) -> bool:
    """
    Updates weight of ingredient in table_ingredients.
    Recalculates macros proportionally.
    """
    ing = st.session_state.get("table_ingredients")
    if not ing or idx < 0 or idx >= len(ing):
        return False

    ing = ing[idx]

    old_weight = ing.get("weight", 0)
    if old_weight <= 0 or new_weight <= 0:
        return False

    ing["weight"] = new_weight
    ing["calories"] = scale_macros(ing.get("calories", 0), old_weight, new_weight)
    ing["proteins"] = scale_macros(ing.get("proteins", 0), old_weight, new_weight)
    ing["fats"] = scale_macros(ing.get("fats", 0), old_weight, new_weight)
    ing["carbohydrates"] = scale_macros(
        ing.get("carbohydrates", 0), old_weight, new_weight
    )

    return True


def update_ingredient_macros(idx: int, new_per_100g: dict) -> bool:
    """
    Updates macros per 100g in table_ingredients.
    """

    if idx < 0 or idx >= len(st.session_state["table_ingredients"]):
        return False

    ing = st.session_state["table_ingredients"][idx]

    weight = ing.get("weight", 0)
    if weight <= 0:
        return False

    st.session_state["modified_ingredients"].append(
        {
            "name": ing["name"],
            "weight": 100,
            "calories": new_per_100g["calories"],
            "proteins": new_per_100g["proteins"],
            "fats": new_per_100g["fats"],
            "carbohydrates": new_per_100g["carbohydrates"],
            "owner": st.session_state["username"].lower().strip(),
        }
    )

    ing["calories"] = scale_macros(new_per_100g["calories"], 100, weight)
    ing["proteins"] = scale_macros(new_per_100g["proteins"], 100, weight)
    ing["fats"] = scale_macros(new_per_100g["fats"], 100, weight)
    ing["carbohydrates"] = scale_macros(new_per_100g["carbohydrates"], 100, weight)
    ing["owner"] = st.session_state.get("username", "").lower().strip()

    return True


def scale_macros(value: float, from_weight: float, to_weight: float) -> float:
    """
    Scales the macro value from one weight to another.
    Example: 150 kcal per 150g → ? kcal per 200g
    """
    if from_weight <= 0:
        return 0.0
    return round(value * to_weight / from_weight, 2)


def cancel_edit_dialog():
    st.session_state["idx_edit_ingredient"] = None


def cancel_add_ingredient_dialog():
    st.session_state["show_add_dialog"] = False


# ============================================
# EDIT DIALOG
# ============================================


def show_edit_dialog(idx: int):
    """
    Displays the edit ingredient dialog.
    Args:
        idx (int): Index of the ingredient to be changed
    """

    @st.dialog(
        t("dialog.edit_ingredient.title"), width="medium", on_dismiss=cancel_edit_dialog
    )
    def edit_dialog(idx: int):
        """Modal window for editing macros per 100g"""

        ing = st.session_state["table_ingredients"][idx]
        weight = ing["weight"]
        per_100g = {
            "calories": scale_macros(ing["calories"], weight, 100),
            "proteins": scale_macros(ing["proteins"], weight, 100),
            "fats": scale_macros(ing["fats"], weight, 100),
            "carbohydrates": scale_macros(ing["carbohydrates"], weight, 100),
        }

        st.write(
            f"**{ing_translator.resolve(ing['name'], st.session_state['language'])}**"
        )
        st.caption(t("dialog.edit_ingredient.caption").format(weight=weight))
        st.divider()

        calories = st.number_input(
            t("dialog.edit_ingredient.form.calories"),
            value=per_100g["calories"],
            step=1.0,
            min_value=0.0,
        )
        proteins = st.number_input(
            t("dialog.edit_ingredient.form.proteins"),
            value=per_100g["proteins"],
            step=0.1,
            min_value=0.0,
        )
        fats = st.number_input(
            t("dialog.edit_ingredient.form.fats"),
            value=per_100g["fats"],
            step=0.1,
            min_value=0.0,
        )
        carbohydrates = st.number_input(
            t("dialog.edit_ingredient.form.carbs"),
            value=per_100g["carbohydrates"],
            step=0.1,
            min_value=0.0,
        )

        col1, col2 = st.columns(2)

        if col1.button(
            t("dialog.edit_ingredient.form.buttons.save"),
            type="primary",
            use_container_width=True,
        ):
            new_macros = {
                "calories": calories,
                "proteins": proteins,
                "fats": fats,
                "carbohydrates": carbohydrates,
            }
            update_ingredient_macros(idx, new_macros)
            st.success(t("dialog.edit_ingredient.success.updated"))
            st.session_state["idx_edit_ingredient"] = None
            st.rerun()

        if col2.button(
            t("dialog.edit_ingredient.form.buttons.cancel"),
            use_container_width=True,
        ):
            cancel_edit_dialog()
            st.rerun()

        st.divider()
        st.write(t("dialog.edit_ingredient.preview.title").format(weight=weight))
        actual = {
            "calories": scale_macros(calories, 100, weight),
            "proteins": scale_macros(proteins, 100, weight),
            "fats": scale_macros(fats, 100, weight),
            "carbohydrates": scale_macros(carbohydrates, 100, weight),
        }
        col1, col2, col3, col4 = st.columns(4)
        col1.metric(
            t("dialog.edit_ingredient.preview.metrics.calories_short"),
            f"{actual['calories']}",
        )
        col2.metric(
            t("dialog.edit_ingredient.preview.metrics.proteins_short"),
            f"{actual['proteins']} {t('common.units.grams')}",
        )
        col3.metric(
            t("dialog.edit_ingredient.preview.metrics.fats_short"),
            f"{actual['fats']} {t('common.units.grams')}",
        )
        col4.metric(
            t("dialog.edit_ingredient.preview.metrics.carbs_short"),
            f"{actual['carbohydrates']} {t('common.units.grams')}",
        )

    edit_dialog(idx)


# ============================================
# ADD INGREDIENT DIALOG (MODAL)
# ============================================


def show_add_ingredient_dialog():
    """
    Displays the add ingredient dialog
    """

    @st.dialog(
        t("dialog.add_ingredient.title"),
        width="medium",
        on_dismiss=cancel_add_ingredient_dialog,
    )
    def add_ingredient_dialog():
        """Modal window for adding a new ingredient"""

        tab1, tab2 = st.tabs(
            [
                t("dialog.add_ingredient.tabs.select"),
                t("dialog.add_ingredient.tabs.create"),
            ]
        )

        # ============================================
        # TAB 1: Select existing ingredient
        # ============================================
        with tab1:
            options_map = {
                ing_translator.resolve(
                    item["name"], st.session_state["language"]
                ): item["name"]
                for item in st.session_state.get("users_ingredients", [])
            }

            if not options_map:
                st.info(t("dialog.add_ingredient.tab1.empty"))

            else:
                selected_display = st.selectbox(
                    t("dialog.add_ingredient.tab1.selectbox.label"),
                    options=list(options_map.keys()),
                    placeholder=t("dialog.add_ingredient.tab1.selectbox.placeholder"),
                    key="sel_ing_name",
                )

                weight = st.number_input(
                    t("dialog.add_ingredient.tab1.weight.label"),
                    value=100.0,
                    min_value=0.0,
                    max_value=10000.0,
                    step=1.0,
                    key="sel_ing_weight",
                )

                if selected_display:
                    canonical_key = options_map[selected_display]
                    selected_item = next(
                        (
                            item
                            for item in st.session_state["users_ingredients"]
                            if item["name"] == canonical_key
                        ),
                        None,
                    )

                    st.divider()
                    st.text(t("dialog.add_ingredient.tab1.per_100g.caption"))

                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric(
                            t("dialog.add_ingredient.tab1.metrics.calories"),
                            f"{selected_item['calories']}",
                        )
                        st.metric(
                            t("dialog.add_ingredient.tab1.metrics.proteins"),
                            f"{selected_item['proteins']} {t('common.units.grams')}",
                        )
                    with col2:
                        st.metric(
                            t("dialog.add_ingredient.tab1.metrics.fats"),
                            f"{selected_item['fats']} {t('common.units.grams')}",
                        )
                        st.metric(
                            t("dialog.add_ingredient.tab1.metrics.carbs"),
                            f"{selected_item['carbohydrates']} {t('common.units.grams')}",
                        )

                    if weight > 0:
                        st.divider()
                        st.text(
                            t("dialog.add_ingredient.tab1.actual.title").format(
                                weight=weight
                            )
                        )

                        actual = {
                            "calories": scale_macros(
                                selected_item["calories"], 100, weight
                            ),
                            "proteins": scale_macros(
                                selected_item["proteins"], 100, weight
                            ),
                            "fats": scale_macros(selected_item["fats"], 100, weight),
                            "carbohydrates": scale_macros(
                                selected_item["carbohydrates"], 100, weight
                            ),
                        }

                        col1, col2 = st.columns(2)

                        with col1:
                            st.metric(
                                t("dialog.add_ingredient.tab1.metrics.calories"),
                                f"{actual['calories']}",
                            )
                            st.metric(
                                t("dialog.add_ingredient.tab1.metrics.proteins"),
                                f"{actual['proteins']} {t('common.units.grams')}",
                            )

                        with col2:
                            st.metric(
                                t("dialog.add_ingredient.tab1.metrics.fats"),
                                f"{actual['fats']} {t('common.units.grams')}",
                            )
                            st.metric(
                                t("dialog.add_ingredient.tab1.metrics.carbs"),
                                f"{actual['carbohydrates']} {t('common.units.grams')}",
                            )

                st.divider()
                col1, col2 = st.columns(2)
                if col1.button(
                    t("dialog.add_ingredient.tab1.buttons.add"),
                    type="primary",
                    use_container_width=True,
                    key="add_sel_ing_btn",
                ):
                    if selected_item and weight > 0:
                        if add_new_ingredient(
                            canonical_key,
                            weight,
                            actual["calories"],
                            actual["proteins"],
                            actual["fats"],
                            actual["carbohydrates"],
                        ):
                            st.session_state["show_add_dialog"] = False
                            st.rerun()
                        else:
                            st.error(
                                t("dialog.add_ingredient.tab1.error.duplicate").format(
                                    name=selected_display
                                )
                            )

                    else:
                        st.error(t("dialog.add_ingredient.tab1.error.select"))

                if col2.button(
                    t("dialog.add_ingredient.tab1.buttons.cancel"),
                    use_container_width=True,
                    key="cancel_sel_ing_btn",
                ):
                    cancel_add_ingredient_dialog()
                    st.rerun()

        # ============================================
        # TAB 2: Create new ingredient
        # ============================================
        with tab2:
            name = st.text_input(
                t("dialog.add_ingredient.tab2.name.label"),
                placeholder=t("dialog.add_ingredient.tab2.name.placeholder"),
            )

            weight = st.number_input(
                t("dialog.add_ingredient.tab2.weight.label"),
                value=100.0,
                min_value=0.0,
                max_value=10000.0,
                step=1.0,
                key="new_ing_weight",
            )

            st.divider()

            calories = st.number_input(
                t("dialog.add_ingredient.tab2.macros.calories"),
                value=0.0,
                step=1.0,
                min_value=0.0,
                key="new_ing_calories",
            )
            proteins = st.number_input(
                t("dialog.add_ingredient.tab2.macros.proteins"),
                value=0.0,
                step=0.1,
                min_value=0.0,
                key="new_ing_proteins",
            )
            fats = st.number_input(
                t("dialog.add_ingredient.tab2.macros.fats"),
                value=0.0,
                step=0.1,
                min_value=0.0,
                key="new_ing_fats",
            )
            carbohydrates = st.number_input(
                t("dialog.add_ingredient.tab2.macros.carbohydrates"),
                value=0.0,
                step=0.1,
                min_value=0.0,
                key="new_ing_carbs",
            )

            if name.strip() and weight > 0:
                st.divider()
                st.write(
                    t("dialog.add_ingredient.tab2.preview.title").format(weight=weight)
                )

                col1, col2 = st.columns(2)

                actual = {
                    "calories": scale_macros(calories, 100, weight),
                    "proteins": scale_macros(proteins, 100, weight),
                    "fats": scale_macros(fats, 100, weight),
                    "carbohydrates": scale_macros(carbohydrates, 100, weight),
                }

                with col1:
                    st.metric(
                        t("dialog.add_ingredient.tab1.metrics.calories"),
                        f"{actual['calories']}",
                    )
                    st.metric(
                        t("dialog.add_ingredient.tab1.metrics.proteins"),
                        f"{actual['proteins']} {t('common.units.grams')}",
                    )

                with col2:
                    st.metric(
                        t("dialog.add_ingredient.tab1.metrics.fats"),
                        f"{actual['fats']} {t('common.units.grams')}",
                    )
                    st.metric(
                        t("dialog.add_ingredient.tab1.metrics.carbs"),
                        f"{actual['carbohydrates']} {t('common.units.grams')}",
                    )

                st.divider()
                col1, col2 = st.columns(2)

                if col1.button(
                    t("dialog.add_ingredient.tab2.buttons.add"),
                    type="primary",
                    use_container_width=True,
                ):
                    if not name.strip():
                        st.error(t("dialog.add_ingredient.tab2.error.name"))
                    else:
                        canonical = get_canonical_name(name)
                        if any(
                            ing_translator.resolve(ing["name"], st.session_state.get("language")) == canonical
                            for ing in st.session_state.get("users_ingredients", [])
                        ):
                            st.error(
                                t(
                                    "dialog.add_ingredient.tab2.error.duplicate_name"
                                ).format(name=name)
                            )

                        else:
                            if add_new_ingredient(
                                name,
                                weight,
                                actual["calories"],
                                actual["proteins"],
                                actual["fats"],
                                actual["carbohydrates"],
                            ):
                                st.session_state["show_add_dialog"] = False
                                st.rerun()
                            else:
                                st.error(
                                    t(
                                        "dialog.add_ingredient.tab2.error.duplicate_in_table"
                                    ).format(name=name)
                                )

                if col2.button(
                    t("dialog.add_ingredient.tab2.buttons.cancel"),
                    use_container_width=True,
                ):
                    cancel_add_ingredient_dialog()
                    st.rerun()

    add_ingredient_dialog()


def plot_nutritional_info():
    """
    Visualizes ingredient list and total nutrition (donut chart).
    Used on recognition page after image analysis.
    """

    with st.container():
        header_cols = st.columns(
            [2.3, 1.2, 1, 1, 1, 1.2, 0.8, 0.8],
            vertical_alignment="center",
            gap="xsmall",
        )
        header_cols[0].text(
            t("ui.table.ingredient"), width="stretch", text_alignment="center"
        )
        header_cols[1].text(
            t("ui.table.weight_g"), width="stretch", text_alignment="center"
        )
        header_cols[2].text(
            t("ui.table.calories_kcal"), width="stretch", text_alignment="center"
        )
        header_cols[3].text(
            t("ui.table.proteins_g"), width="stretch", text_alignment="center"
        )
        header_cols[4].text(
            t("ui.table.fats_g"), width="stretch", text_alignment="center"
        )
        header_cols[5].text(
            t("ui.table.carbs_g"), width="stretch", text_alignment="center"
        )
        if st.session_state.get("table_ingredients"):
            with st.container(
                height=(
                    600
                    if len(st.session_state.get("table_ingredients", [])) >= 7
                    else "content"
                ),
                border=False,
            ):
                for row in st.session_state.get("table_ingredients", []):
                    with st.container(border=True):
                        cols = st.columns(
                            [2.3, 1.2, 1, 1, 1, 1.2, 0.8, 0.8],
                            vertical_alignment="center",
                            gap="xsmall",
                        )
                        cols[0].text(
                            ing_translator.resolve(
                                row["name"], st.session_state.get("language")
                            ),
                            width="stretch",
                            text_alignment="left",
                        )
                        with cols[1]:
                            new_weight = st.number_input(
                                "weight",
                                value=row["weight"],
                                min_value=1.0,
                                max_value=10000.0,
                                step=1.0,
                                key=f"weight_{row['idx']}",
                                label_visibility="collapsed",
                            )
                            if new_weight != row["weight"]:
                                check_activity()
                                for i, item in enumerate(
                                    st.session_state["table_ingredients"]
                                ):
                                    if item["idx"] == row["idx"]:
                                        update_ingredient_weight(i, new_weight)
                                        break

                                st.rerun()

                        cols[2].text(
                            f"{row['calories']}",
                            width="stretch",
                            text_alignment="center",
                        )
                        cols[3].text(
                            f"{row['proteins']} {t('ui.unit.g')}",
                            width="stretch",
                            text_alignment="center",
                        )
                        cols[4].text(
                            f"{row['fats']} {t('ui.unit.g')}",
                            width="stretch",
                            text_alignment="center",
                        )
                        cols[5].text(
                            f"{row['carbohydrates']} {t('ui.unit.g')}",
                            width="stretch",
                            text_alignment="center",
                        )

                        with cols[6]:
                            if st.button(
                                "✏️",
                                key=f"edit_{row['idx']}",
                                use_container_width=True,
                                help=t("help.table.edit"),
                            ):
                                check_activity()
                                for i, item in enumerate(
                                    st.session_state["table_ingredients"]
                                ):
                                    if item["idx"] == row["idx"]:
                                        st.session_state["idx_edit_ingredient"] = i
                                        break
                                st.rerun()

                        with cols[7]:
                            if st.button(
                                "🗑️",
                                key=f"delete_{row['idx']}",
                                use_container_width=True,
                                help=t("help.table.delete"),
                            ):
                                check_activity()
                                for i, item in enumerate(
                                    st.session_state["table_ingredients"]
                                ):
                                    if item["idx"] == row["idx"]:
                                        st.session_state["table_ingredients"].pop(i)
                                        break
                                st.rerun()

        if st.button(t("ui.btn.add_ing"), width="stretch", key="add_ingredient_btn"):
            st.session_state["show_add_dialog"] = True
            st.rerun()

    if st.session_state.get("idx_edit_ingredient") is not None:
        show_edit_dialog(st.session_state.get("idx_edit_ingredient"))

    if st.session_state.get("show_add_dialog"):
        show_add_ingredient_dialog()

    total = {
        "weight": 0.0,
        "calories": 0.0,
        "proteins": 0.0,
        "fats": 0.0,
        "carbohydrates": 0.0,
    }

    for row in st.session_state.get("table_ingredients", []):
        for key in total.keys():
            total[key] += row.get(key, 0)

    st.divider()
    st.subheader(t("ui.table.total"))

    col1, col2, col3, col4, col5 = st.columns(5, gap="xxsmall")
    col1.metric(t("ui.metric.weight_g"), f"{total['weight']:.1f}")
    col2.metric(t("ui.metric.calories_kcal"), f"{total['calories']:.1f}")
    col3.metric(t("ui.metric.proteins_g"), f"{total['proteins']:.1f}")
    col4.metric(t("ui.metric.fats_g"), f"{total['fats']:.1f}")
    col5.metric(t("ui.metric.carbs_g"), f"{total['carbohydrates']:.1f}")
