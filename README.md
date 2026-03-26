# Food Calorie Assistant

Food Calorie Assistant is a small Python project for food nutrition search and calorie tracking.
It combines:

- `Streamlit` frontend (`ui.py`)
- `FastAPI` backend (`service.py`)
- search and assistant logic (`search.py`, `assistant.py`)

## Features

- Search food products and nutrition data
- Analyze calories and daily intake
- Simple local run for UI and API

## Tech Stack

- Python 3.12
- FastAPI
- Uvicorn
- Streamlit

## Project Structure

- `ui.py` - Streamlit user interface
- `service.py` - FastAPI service entrypoint
- `search.py` - nutrition search logic
- `assistant.py` - helper/business logic
- `requirements.txt` - project dependencies
- `Makefile` - handy run commands

## Run Locally

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run backend and frontend:

```bash
make run_app
```

Or run separately:

```bash
make backend
make frontend
```

## Notes

- Keep secrets in `.env` (do not commit it).
- Large or local data files can be excluded via `.gitignore`.
