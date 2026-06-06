FROM python:3.12-slim

WORKDIR /app

COPY requirements-frontend.txt .
RUN pip install --no-cache-dir -r requirements-frontend.txt

COPY frontend/ ./

RUN mkdir -p /app/helper

EXPOSE 8501
CMD ["streamlit", "run", "main_page.py", "--server.address", "0.0.0.0", "--server.port", "8501"]