STREAMLIT_APP = ui.py
FASTAPI_APP = service

.PHONY: frontend backend run_app

frontend:
	streamlit run $(STREAMLIT_APP)

backend:
	uvicorn $(FASTAPI_APP):app &

run_app: backend frontend