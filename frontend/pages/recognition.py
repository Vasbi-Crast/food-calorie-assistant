"""Meal recognition page for analyzing food images.

Handles image upload, displays preview, manages user description input,
and provides navigation to save recognized meals or return to home.
Supports async translation synchronization before saving.
"""

import asyncio
import streamlit as st
from PIL import Image
from io import BytesIO
import base64

from menu import menu
from handlers.api_handler import (
    check_auth,
    check_activity,
    parse_meals,
    translate_table_ingredients,
)
from handlers.init_session_state import clear_session_states
import handlers.recognition_handler as recognition_handler
import handlers.nutrition_table as nutrition_table
from translator import Translator

t = Translator()

check_auth()
menu()

st.title(t("recognition.title"))

uploaded_file = st.file_uploader(
    t("recognition.choose_image"),
    on_change=nutrition_table.clear_new_uploader,
    type=["jpg", "jpeg", "png"],
    key="file_loader",
)

if uploaded_file:
    try:
        img = Image.open(uploaded_file)
        st.image(img, width="stretch")

        buffered = BytesIO()
        img.save(buffered, format="JPEG")
        image_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

    except Exception as e:
        st.error(t("recognition.failed_image"))
        image_base64 = None

user_description = st.text_input(t("recognition.describe_dish"), max_chars=250)

if st.session_state["table_ingredients"]:
    st.subheader(t("ui.recognition.ingredients"))
    nutrition_table.plot_nutritional_info()

_, middle, _ = st.columns(3)

if st.session_state.get("table_ingredients"):
    text = t("recognition.save_dish")
else:
    text = t("recognition.upload")

if middle.button(text, width="stretch", disabled=not bool(uploaded_file)):
    check_activity()
    if st.session_state.get("table_ingredients") is not None:
        with st.spinner(t("ui.processing")):
            asyncio.run(translate_table_ingredients())

            if recognition_handler.save_meal():
                nutrition_table.clear_new_uploader()
                clear_session_states()
                st.switch_page("pages/home.py")
    else:
        with st.spinner(t("ui.processing")):
            if image_base64:
                nutritional_info = recognition_handler.get_meal_macros(
                    image_base64, user_description
                )
                if nutritional_info:
                    parse_meals(nutritional_info)
                    st.rerun()
            else:
                st.error(t("recognition.please_upload"))

if middle.button(t("recognition.back_btn"), width="stretch", key="back_rec"):
    check_activity()
    clear_session_states()
    st.switch_page("pages/home.py")
