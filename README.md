# Food Calorie Assistant

A small app that estimates **calories and macros from a photo of food**: a vision model ([Ollama](https://ollama.com/)) infers ingredients and approximate gram weights, then a local lookup matches them against a nutrition table and returns totals. It includes a **Streamlit** UI and a **FastAPI** backend; sign-up and sign-in use **PostgreSQL**.

## How it works

1. The user uploads a photo and optionally describes the dish in Streamlit (`ui.py`).
2. The client calls the backend: `POST /generate_response` with `image_base64` and `user_description`.
3. The backend (`service.py`) loads the system prompt from `prompt.txt` and sends the image to **Ollama** (async client in `assistant.py`; default model is something like `llava`).
4. The model returns JSON with ingredient names and weights in grams.
5. `search.py` (`IngredientNutritionSearch`) loads a CSV dataset and resolves nutrition via **semantic** search (Sentence Transformers) and fuzzy name matching when needed.
6. The UI shows the result, including matplotlib charts.

Separately, `POST /authentication` and `POST /registration` handle users via `db_connector.py` (asyncpg + password hashing).

## In the repo vs local-only

| In Git | Not in Git (see `.gitignore`) |
|--------|-------------------------------|
| Source (`*.py`), `Makefile`, `requirements.txt`, `prompt.txt` | **`.env`** — API URL, Ollama, DB, model name, etc. |
| `README.md`, license | **`*.csv`** — ingredient nutrition table (e.g. `nutrition.csv` next to the code, as `service.py` expects) |
| | Virtualenv pieces (`bin/`, `lib/`, …), Python cache |

Without a local **`nutrition.csv`**, the backend cannot initialize search (path is hardcoded as `"nutrition.csv"`). Provide a CSV in the format `search.py` expects (ingredient name and macro columns), or keep your own copy locally and do not commit it.

Keep secrets and environment-specific config in **`.env`** only (never commit it).

## Requirements

- Python 3.12+
- **Ollama** running with a vision-capable model (defaults assume something like `llava`; override via environment).
- **PostgreSQL** and a valid **`DB_CONFIG`** in `.env` for authentication flows.
- On first run, Sentence Transformers will download model weights locally.

The code may import packages not listed in `requirements.txt` (e.g. `ollama`, `asyncpg`, `passlib`, Pillow). After `pip install -r requirements.txt`, install any missing imports for your setup.

## Environment variables (example)

Create `.env` in the project root (it is gitignored):

```env
# Backend URL for Streamlit (must match where uvicorn runs)
SERVER_URL=http://127.0.0.1:8000

# Ollama
OLLAMA_HOST=http://127.0.0.1:11434
MODEL_NAME=llava

# PostgreSQL (JSON for asyncpg.create_pool)
DB_CONFIG={"host":"localhost","port":5432,"user":"...","password":"...","database":"..."}
```

Adjust `DB_CONFIG` to match your database and the schema expected by `db_connector.py`.

## Run

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
# Place nutrition.csv next to service.py (do not commit) and configure .env

make run_app
```

Or use two terminals:

```bash
make backend
make frontend
```

## Project layout

| File | Role |
|------|------|
| `ui.py` | Streamlit: photo upload, API calls, charts |
| `service.py` | FastAPI: `/generate_response`, `/authentication`, `/registration` |
| `assistant.py` | Ollama calls with image + prompt |
| `search.py` | CSV load and nutrition lookup per ingredient |
| `db_connector.py` | asyncpg pool and user records |
| `prompt.txt` | System instructions for the vision model |
| `Makefile` | `frontend` / `backend` / `run_app` |

## License

See `LICENSE` in this repository.
