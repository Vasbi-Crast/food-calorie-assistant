# Calorie Tracker

A smart nutrition assistant that helps you track calories and macros with minimal effort. Simply take a photo of your meal, and the app will recognize ingredients, estimate portions, and calculate nutritional values. Designed for people who want to maintain a healthy lifestyle without manual food logging.

>  **Before you start**: We recommend reading the in-app help section (`Settings → Help`) for detailed usage instructions, tips, and explanations of all features.

## ✨ What It Does

- **📷 Photo Recognition** : Upload a photo of your meal → AI identifies ingredients and estimates weights using a local vision LLM
- **🌍 Multi-language Support**: Ingredient names are available in **English and Russian**. The translation system is modular and allows easy extension to other languages by simply adding entries to the translation JSON file
- **📊 Statistics & Analytics**: View calorie/macro breakdowns, track weight changes, and compare nutrient intake against your personal norms over time using static matplotlib charts
- **🎯 Personalized Goals**: Set weight loss, maintenance, or gain targets with custom BMR calculations based on your profile
- **🔐 Private & Secure**: All data stays on your server; authentication via JWT tokens

Perfect for fitness enthusiasts, dietitians, or anyone who wants a smarter way to track nutrition.

---

## 🛠 Technical Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | Streamlit 1.57.0 (Python-based reactive UI) |
| **Backend** | FastAPI 0.136.1 + Uvicorn (async application server) |
| **Database** | PostgreSQL 16 with pgvector (semantic search) |
| **AI/ML** | Sentence Transformers (embeddings), Ollama (vision LLM) |
| **Auth** | JWT (python-jose), bcrypt password hashing (passlib) |
| **HTTP Clients** | httpx (async) |
| **Data Processing** | pandas, numpy, matplotlib |
| **Deployment** | Docker + Docker Compose |

---

## 💻 Minimum Requirements

### Software
- **Python**: 3.11+ (tested on 3.12)
- **Docker** + **Docker Compose** (v2.0+)
- **tmux** (for local development with Makefile)
- **Ollama** running locally with a vision-capable model (e.g., `qwen3.5:9b`)
- **Git** for cloning the repository

### Hardware (for local LLM inference)
| Component | Minimum | Recommended |
|-----------|---------|-------------|
| **CPU** | 4 cores | 8+ cores |
| **RAM** | 8 GB | 16+ GB |
| **GPU** | None (CPU inference) | NVIDIA GPU with 12 GB VRAM (CUDA 12) |
| **Storage** | 10 GB free | 20+ GB SSD (for models + cache) |

> 💡 **Note**: The application was tested and runs smoothly on NVIDIA GPU with 12 GB VRAM (CUDA 12) using the `qwen3.5:9b` model (~9B parameters). CPU-only inference is also supported but may be slower (~10–30 seconds per image).

---

## 📦 Installation

### Option 1: Quick Start with Docker (Recommended)

#### 1. Clone the repository
```bash
git clone https://github.com/your-username/calorie-tracker.git
cd calorie-tracker
```

#### 2. Configure environment variables
Create a `.env` file in the project root:

```env
# === AI Provider (Ollama) ===
OLLAMA_HOST=http://host.docker.internal:11434
MODEL_NAME=qwen3.5:9b

# === Server URLs ===
SERVER_URL=http://backend:8000
STREAMLIT_URL=http://localhost:8501

# === Database ===
DB_PASSWORD=your_secure_db_password

# === Authentication & Security ===
SECRET_KEY=your_jwt_secret_key_here
ADMIN_PASSWORD=admin
TOKEN_EXPIRE_MINUTES=1440

# === Logging ===
LOG_LEVEL=INFO
```

> ⚠️ **Important for WSL2/Docker Desktop**: 
> - `OLLAMA_HOST=http://host.docker.internal:11434` allows containers to reach Ollama on your host machine
> - Make sure Ollama is running and accessible

#### 3. Prepare nutrition dataset
Place your nutrition dataset as `nutrition.csv` in the `helper/` folder:

```bash
# Example structure:
name,calories,protein,fats,carbohydrates
"Apple, raw",52,0.3,0.2,14
"Chicken breast",165,31,3.6,0
```

You can use the provided sample file or replace it with your own dataset. If your CSV uses different column names, see the customization notes below.

#### 4. Start all services
```bash
docker compose up -d --build
```

This will:
- Build and start PostgreSQL with pgvector extension
- Initialize the database schema
- Load ingredients from `nutrition.csv`
- Start the backend API
- Start the Streamlit frontend
- Generate and sync ingredient translations

#### 5. Access the application
- **Frontend**: http://localhost:8501
- **Backend API docs**: http://localhost:8000/docs
- **Database**: localhost:5432 (postgres/postgres)

#### 6. View logs
```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f frontend
docker compose logs -f backend
```

---

### Option 2: Manual Setup (Local Development)

#### 1. Clone and setup Python environment
```bash
git clone https://github.com/your-username/calorie-tracker.git
cd calorie-tracker

python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate  # Windows

pip install -r requirements-backend.txt
pip install -r requirements-frontend.txt
```

#### 2. Start PostgreSQL with pgvector
```bash
# Using Docker (recommended):
docker run -d \
  --name calorie-db \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=calorie_tracker_db \
  -p 5432:5432 \
  pgvector/pgvector:pg16
```

#### 3. Initialize database
```bash
docker exec -i calorie-db psql -U postgres -d calorie_tracker_db < backend/create_db.sql
```

#### 4. Configure `.env` for local development
```env
OLLAMA_HOST=http://localhost:11434
MODEL_NAME=qwen3.5:9b
SERVER_URL=http://127.0.0.1:8000
STREAMLIT_URL=http://localhost:8501
DB_CONFIG='{"host": "localhost", "port": 5432, "database": "calorie_tracker_db", "user": "postgres", "password": "postgres"}'
SECRET_KEY=your_secret_key
ADMIN_PASSWORD=admin
TOKEN_EXPIRE_MINUTES=1440
LOG_LEVEL=INFO
```

#### 5. Load ingredients and generate translations
```bash
# Load nutrition data
python helper/csv_to_db.py

# Generate translation dictionary
python helper/init_translation_dict.py
```

#### 6. Start services manually
**Terminal 1 — Backend:**
```bash
cd backend
uvicorn service:app &
```

**Terminal 2 — Frontend:**
```bash
cd frontend
streamlit run main_page.py
```

---

## 🗂 Project Structure

```
calorie-tracker/
├── backend/
│   ├── service.py              # FastAPI app entry point
│   ├── assistant.py            # LLM client (Ollama integration)
│   ├── auth.py                 # JWT authentication
│   ├── db_connector.py         # PostgreSQL asyncpg connector
│   ├── schemas.py              # Pydantic models
│   ├── create_db.sql           # Database schema initialization
│   └── prompt_*.txt            # LLM system prompts
│
├── db/
│   └── Dockerfile              # PostgreSQL + pgvector setup
│
── frontend/
│   ├── main_page.py            # Streamlit entry point (router)
│   ├── menu.py                 # Navigation sidebar
│   ├── translator.py           # Translation manager for ingredients
│   ├── Dockerfile              # Frontend container setup
│   ├── .streamlit/
│   │   └── config.toml         # Streamlit configuration (theme, server settings)
│   ├── pages/
│   │   ├── home.py             # Main dashboard page after authentication
│   │   ├── recognition.py      # Photo recognition interface
│   │   ├── daily_log.py        # Meal logging interface
│   │   ├── settings.py         # User settings and help
│   │   ├── general_stat.py     # Statistics and charts (matplotlib-based)
│   │   └── register.py         # User registration
│   ├── handlers/
│   │   ├── api_handler.py      # API request wrapper
│   │   ├── recognition_handler.py
│   │   ├── daily_log_handler.py
│   │   ├── home_handler.py
│   │   ├── settings_handler.py
│   │   ├── general_stat_handler.py
│   │   ├── register_handler.py
│   │   ├── nutrition_table.py  # Table initializer and handler for ingredients
│   │   └── init_session_state.py  # Initializes Streamlit session_state for persistent UI data
│   └── resources/
│       ├── locales/
│       │   ├── en.yaml         # English UI translations
│       │   ├── ru.yaml         # Russian UI translations
│       │   └── ingredient_translations.json  # Database of ingredient name translations (EN ↔ RU)
│       └── icons8-chinese-noodle-100.png
│
├── helper/
│   ├── csv_to_db.py            # Initializes basic ingredients in DB + generates semantic embeddings
│   ├── init_translation_dict.py # Generates base translation JSON from CSV
│   ├── pre_run_sync.py         # Startup script: generates base translations and syncs with backend
│   └── nutrition.csv           # Nutrition dataset (sample or custom)
│
├── docker-compose.yml          # Multi-container orchestration
├── requirements-backend.txt    # Backend dependencies
├── requirements-frontend.txt   # Frontend dependencies
├── .env                        # Environment variables (git-ignored)
├── Makefile                    # Quick start commands for local development
└── .streamlit/                 # Global Streamlit config (optional, for local development)
    └── config.toml
```

### Key Files Reference

| File | Purpose |
|------|---------|
| `backend/service.py` | Backend server entry point (FastAPI app) |
| `frontend/main_page.py` | Frontend server entry point (Streamlit router) |
| `frontend/pages/home.py` | Main dashboard page after authentication |
| `frontend/handlers/init_session_state.py` | Initializes Streamlit `session_state` for persistent UI data |
| `frontend/handlers/nutrition_table.py` | Initializes and handles ingredient tables in the UI |
| `frontend/resources/locales/ingredient_translations.json` | Database of ingredient name translations (English ↔ Russian) |
| `helper/csv_to_db.py` | Initializes basic ingredients in the database + generates semantic embeddings |
| `helper/pre_run_sync.py` | Runs on first frontend startup: generates base translations and syncs with backend |
| `frontend/.streamlit/config.toml` | Streamlit configuration (theme, server address, etc.) |
| `.streamlit/config.toml` | Global Streamlit config (optional, for local development) |

### Customizing CSV Column Names

If your `nutrition.csv` uses different column headers, edit the `fields_config` dictionary in **both** scripts:

**In `helper/csv_to_db.py`:**
```python
fields_config = {
    "name": "name",              # Column with ingredient names
    "calories": "calories",      # Column with calorie values
    "fats": "total_fat",         # Column with fat values
    "proteins": "protein",       # Column with protein values
    "carbohydrates": "carbohydrate",  # Column with carb values
}
```

**In `helper/init_translation_dict.py`:**
```python
# Change this parameter when calling the function:
generate_base_translations_from_csv(
    csv_path="nutrition.csv",
    col_with_ing_name="your_column_name",  # 👈 Your column with ingredient names
    # ... other params
)
```

---

## 🛠 Using the Makefile

The project includes a `Makefile` for quick local development using `tmux` (requires `tmux` installed):

```bash
# Start backend and frontend in detached tmux sessions
make run_app

# View live output from both sessions without attaching
make peek

# Stop both sessions
make stop
```

> 💡 **Note**: The `run_app` command automatically handles session cleanup, starts the backend (`uvicorn service:app --reload`) and frontend (`streamlit run main_page.py`) in separate `tmux` windows, and prints quick reference commands. Requires `tmux` to be installed on your system.

---

## 🛠 Troubleshooting

| Issue | Solution |
|-------|----------|
| `pgvector extension does not exist` | Use `pgvector/pgvector:pg16` Docker image or run `CREATE EXTENSION vector;` manually |
| Ollama connection refused | Verify `OLLAMA_HOST` points to correct IP; run `ollama serve` and `ollama pull qwen3.5:9b` |
| Missing translations | Run `python helper/init_translation_dict.py` or check `pre_run_sync.py` logs |
| Slow semantic search | Ensure pgvector index is built; pre-generate embeddings via `csv_to_db.py` |
| JWT auth fails | Check `SECRET_KEY` matches; verify token expiration in `TOKEN_EXPIRE_MINUTES` |
| Database connection failed | Ensure Docker container is running (`docker ps`) and `DB_CONFIG` matches container port/user/password |
| CSV columns not found | Edit `fields_config` in `helper/csv_to_db.py` AND `col_with_ing_name` in `init_translation_dict.py` |
| First-run sync fails | Check if backend is running. If not, restart all containers: `docker compose down && docker compose up -d --build`. Default admin password is `admin`. |

---

## 📄 License

See `LICENSE` in this repository.

---

> 💡 **Tip**: For the best experience, start with a small `nutrition.csv` (100–500 items) to test the pipeline, then scale up. Embedding generation for 10k items takes ~5–10 minutes on CPU, ~1 minute on GPU.

*Built with ❤️ for smarter nutrition tracking.*