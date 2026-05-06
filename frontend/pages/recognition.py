import streamlit as st
from PIL import Image
from io import BytesIO
import base64

from menu import menu
from handlers.api_handler import check_auth, check_activity
import handlers.recognition_handler as recognition_handler
from translator import Translator
t = Translator()

check_auth()
menu()

st.title(t("recognition.title"))

st.config.set_option("server.maxUploadSize", 3)
uploaded_file = st.file_uploader(
    t("recognition.choose_image"),
    on_change=recognition_handler.clear_new_uploader,
    type=["jpg", "jpeg", "png"],
    key="file_loader",
)

if uploaded_file:
    try:
        img = Image.open(uploaded_file)
        st.image(img, use_column_width=True)

        buffered = BytesIO()
        img.save(buffered, format="JPEG")
        image_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

    except Exception as e:
        st.error(t("recognition.failed_image"))
        image_base64 = None

user_description = st.text_input(
    t("recognition.describe_dish"), max_chars=250
)

if st.session_state["table_ingredients"] is not None:
    recognition_handler.plot_nutritional_info()

_, midle, _ = st.columns(3)

if st.session_state["table_ingredients"]:
    text = t("recognition.save_dish")
else:
    text = t("recognition.upload")

if midle.button(text, width='stretch'):
    check_activity()
    if text == t("recognition.save_dish"):
        if recognition_handler.save_dish():
            st.session_state["table_ingredients"] = None
            st.session_state["total_macros"] = None
            st.switch_page("pages/home.py")
        else:
            st.error(t("recognition.failed_save"))
    else:
        if image_base64:
            nutritional_info = recognition_handler.get_meal_macros(image_base64, user_description)
            if nutritional_info:
                recognition_handler.parse_dish(nutritional_info)
                st.rerun()
        else:
            st.error(t("recognition.please_upload"))

if midle.button(t("recognition.back_btn"), width='stretch', key="back_rec"):
    st.session_state["table_ingredients"], st.session_state["total_macros"] = None, None
    st.session_state["last_deleted"] = []
    st.session_state["name_table_widget"] = ""
    st.switch_page("pages/home.py")