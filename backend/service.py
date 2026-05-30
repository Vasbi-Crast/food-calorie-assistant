from asyncpg import UniqueViolationError
from fastapi import FastAPI, Depends, HTTPException, Request, Query
from fastapi.security import OAuth2PasswordBearer
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from contextlib import asynccontextmanager
from typing import Annotated, Any, List, Dict, Optional
import os
from dotenv import load_dotenv
import logging
from pathlib import Path

from assistant import LLMAssistant
from db_connector import DBConnector
from auth import create_token, decode_token
from schemas import (
    LoginInput,
    RegisterInput,
    User,
    SingleDate,
    DateRange,
    DishPayload,
    IngredientRecognitionInput,
    IngredientItem,
    TranslatorInput,
)

load_dotenv()

# === Configuration Constants ===

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

EMBEDDING_BATCH_SIZE = 32
EMBEDDING_MODEL_NAME = "intfloat/multilingual-e5-small"

TRANSLATION_BATCH_SIZE = 50
ALLOWED_BMR_VALUES = {1.2, 1.375, 1.55, 1.725, 1.9}

DEFAULT_BMR = 1.375
LLM_TIMEOUT_SHORT = 30
LLM_TIMEOUT_LONG = 240
LLM_TIMEOUT_TRANSLATION = 120
DB_TIMEOUT = 20

# === Logging Settings ===

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger("service")

connector: Optional[DBConnector] = None
assistant: Optional[LLMAssistant] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown lifecycle.

    Initializes database connection, loads prompts, and sets up LLM assistant
    on startup. Cleans up resources on shutdown.

    Args:
        app (FastAPI): The FastAPI application instance.

    Yields:
        None: Control returns to FastAPI after startup completes.

    Raises:
        Exception: If LLM Assistant initialization fails, propagates error.
    """

    global connector, assistant

    logger.info(" Starting application...")

    connector = DBConnector(
        model_name=EMBEDDING_MODEL_NAME, embedding_batch_size=EMBEDDING_BATCH_SIZE
    )
    await connector.connection()
    await connector.load_model()
    logger.info("✅ Database connected.")

    try:
        prompts = {}
        prompt_dir = Path(__file__).parent
        for name in [
            "ingredient_recognition",
            "macros_extraction",
            "ingredient_translation",
            "get_bmr",
        ]:
            path = prompt_dir / f"prompt_{name}.txt"
            with open(path, "r", encoding="utf-8") as f:
                prompts[name] = f.read()
        logger.info("✅ Prompts loaded.")

        assistant = LLMAssistant(
            prompts["ingredient_recognition"],
            prompts["macros_extraction"],
            prompts["ingredient_translation"],
            prompts["get_bmr"],
            temperature=0.01,
            max_tokens=250,
            top_p=0.1,
            translation_batch_size=TRANSLATION_BATCH_SIZE,
            allowed_bmr_values=ALLOWED_BMR_VALUES,
        )
        logger.info("✅ LLM Assistant initialized.")
    except Exception as e:
        logger.error(f"Failed to initialize LLM Assistant: {e}", exc_info=True)
        raise

    yield

    logger.info("🛑 Shutting down...")
    if connector:
        await connector.close()
        logger.info("✅ Database closed.")


app = FastAPI(lifespan=lifespan)

streamlit_url = os.getenv("STREAMLIT_URL")
if not streamlit_url:
    logger.warning("⚠️ STREAMLIT_URL not set in .env, falling back to localhost")
    raise ValueError("STREAMLIT_URL environment variable is required in production")

allowed_origins = [streamlit_url, "http://localhost:8501", "http://127.0.0.1:8501"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)


# === Exception Handlers ===


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    """Handle ValueError exceptions from business logic.

    Args:
        request (Request): The incoming HTTP request.
        exc (ValueError): The raised ValueError exception.

    Returns:
        JSONResponse: HTTP 400 response with error detail message.
    """
    logger.warning(f"ValueError | {request.method} {request.url.path} | {exc}")
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(UniqueViolationError)
async def duplicate_key_handler(
    request: Request, exc: UniqueViolationError
) -> JSONResponse:
    """Handles database unique constraint violation errors.

    Catches asyncpg.UniqueViolationError exceptions (e.g., duplicate username),
    logs a warning with request details, and returns an HTTP 409 Conflict response.

    Args:
        request (Request): The incoming FastAPI HTTP request object.
        exc (UniqueViolationError): The raised unique constraint violation exception.

    Returns:
        JSONResponse: HTTP 409 response containing a JSON payload with the error detail.
            Example: {"detail": "duplicate key value violates unique constraint..."}
    """
    logger.warning(
        f"UniqueViolationError | {request.method} {request.url.path} | {exc}"
    )
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(ValidationError)
async def validation_exception_handler(
    request: Request, exc: ValidationError
) -> JSONResponse:
    """Handle Pydantic request validation errors.

    Formats validation errors into a simplified list for frontend consumption.

    Args:
        request (Request): The incoming HTTP request.
        exc (RequestValidationError): The raised validation exception.

    Returns:
        JSONResponse: HTTP 422 response with formatted error details.
    """
    errors = []
    for error in exc.errors():
        error_type = error.get("type", "undefined_error")
        loc = error.get("loc", [])
        field = loc[0] if loc else "unknown"
        ctx = error.get("ctx")
        errors.append({"field": field, "type_error": error_type, "ctx": ctx})
    logger.warning(f"Validation Error | {request.method} {request.url.path}")
    return JSONResponse(
        status_code=422, content={"detail": "Validation failed", "errors": errors}
    )


@app.exception_handler(RuntimeError)
async def runtime_error_handler(request: Request, exc: RuntimeError) -> JSONResponse:
    """Handle critical runtime errors.

    Args:
        request (Request): The incoming HTTP request.
        exc (RuntimeError): The raised RuntimeError exception.

    Returns:
        JSONResponse: HTTP 500 response with generic error message.
    """
    logger.error(
        f"CRITICAL ERROR | {request.method} {request.url.path} | {exc}", exc_info=True
    )
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.exception_handler(TimeoutError)
async def timeout_error_handler(request: Request, exc: TimeoutError) -> JSONResponse:
    """Handle timeout errors from database or external services.

    Args:
        request (Request): The incoming HTTP request.
        exc (TimeoutError): The raised TimeoutError exception.

    Returns:
        JSONResponse: HTTP 504 response with timeout message.
    """
    logger.error(f"Timeout Error | {request.method} {request.url.path}")
    return JSONResponse(
        status_code=504, content={"detail": "Request timed out. Try again later."}
    )


# === Authentication ===

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/authentication")


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]) -> str:
    """
    Dependency to extract and validate JWT token.

    Args:
        token: JWT token from Authorization header.

    Returns:
        Authenticated username.

    Raises:
        HTTPException:
            401: If token is invalid or expired.
    """
    username = decode_token(token)
    if not username:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return username


# === API Endpoints ===


@app.post("/authentication")
async def authentication(data: LoginInput) -> Dict[str, str]:
    """
    Authenticate user and return JWT access token.

    Args:
        data: LoginInput with username and password.

    Returns:
        dict: {"access_token": str, "token_type": "bearer"}

    Raises:
        HTTPException:
            401: If username not found or password invalid.
            504: If timeout occurs.
            500: If unexpected error occurs.
    """
    logger.info(f"Auth request: {data.username}")
    result = await connector.verify(data.username, data.password)

    if result == "SUCCESSFUL":
        token = create_token(data.username)
        return {"access_token": token, "token_type": "bearer"}

    status_map = {
        "USER_NOT_FOUND": 401,
        "INVALID_PASSWORD": 401,
    }
    raise HTTPException(status_code=status_map.get(result, 500), detail=result)


@app.post("/registration")
async def registration(request: Request) -> Dict[str, bool]:
    """Register a new user account.

    Parses JSON body, handles lifestyle description marker, calculates BMR
    via LLM for custom descriptions, validates payload via Pydantic,
    and persists user data to database.

    Args:
        request (Request): FastAPI request object containing JSON body with
            user registration data.

    Returns:
        Dict[str, bool]: Dictionary with key 'response' indicating success.

    Raises:
        HTTPException:
            422: If request body is invalid JSON or Pydantic validation fails.
            400: If registration fails (e.g., duplicate username).
    """
    logger.info(f"Registration request received")

    body = await request.json()
    lifestyle_desc = body.get("lifestyle_description")

    if body.get("bmr"):
        logger.debug(f"Preset selected, stripping marker: {lifestyle_desc}")
    else:
        if lifestyle_desc:
            logger.info(f"Calculating BMR for custom lifestyle: {lifestyle_desc}")
            bmr_response = await assistant.get_bmr(
                lifestyle_description=lifestyle_desc, timeout=LLM_TIMEOUT_SHORT
            )
            if bmr_response.get("status") == "success":
                body["bmr"] = bmr_response["result"]["bmr"]
                logger.debug(f"✅ BMR calculated: {body['bmr']}")
            else:
                logger.warning("⚠️ BMR calculation failed, using default 1.375")
                body["bmr"] = DEFAULT_BMR
        else:
            logger.warning("⚠️ lifestyle description was mise, BMR using default 1.375")
            body["bmr"] = DEFAULT_BMR

    user_data = RegisterInput(**body)
    success = await connector.add_user(user_data)

    logger.info(f"✅ User registered: {user_data.username}")

    return {"response": success}


@app.get("/users/me")
async def get_user_information(
    current_user: Annotated[str, Depends(get_current_user)]
) -> Dict[str, Any]:
    """
    Retrieves current authenticated user's profile information.

    Args:
        current_user (str): Authenticated username extracted from JWT token.

    Returns:
        Dict[str, Any]: User profile dictionary containing:
            age (int)
            lifestyle_description (str)
            bmr (float)
            gender (str)
            goal (str)
            weight (float)
            height (float)

    Raises:
        HTTPException:
            401: If token is invalid or expired.
            504: If database timeout occurs.
            500: If unexpected error occurs.
    """
    logger.debug(f"Fetching profile for user: {current_user}")
    profile = await connector.user_information(current_user)
    logger.debug(f"✅ Profile retrieved for: {current_user}")
    return profile


@app.put("/users/me")
async def update_user_info(
    request: Request, current_user: Annotated[str, Depends(get_current_user)]
) -> Dict[str, bool]:
    """
    Updates current authenticated user's profile information.

    Parses JSON request body, handles lifestyle description marker,
    recalculates BMR via LLM for custom descriptions, validates payload,
    and delegates persistence to the database connector.

    Args:
        request (Request): FastAPI request object containing JSON body.
        current_user (str): Authenticated username extracted from JWT token.

    Returns:
        Dict[str, bool]: {"response": True} if update successful,
                         False if user not found.
    """
    logger.info(f"Profile update request for user: {current_user}")

    body = await request.json()
    lifestyle_desc = body.get("lifestyle_description")

    if body.get("bmr"):
        logger.debug(f"Preset selected, stripping marker: {lifestyle_desc}")
    else:
        if lifestyle_desc:
            logger.info(f"Recalculating BMR for custom lifestyle: {lifestyle_desc}")
            bmr_response = await assistant.get_bmr(
                lifestyle_description=lifestyle_desc, timeout=LLM_TIMEOUT_SHORT
            )
            if bmr_response.get("status") == "success":
                body["bmr"] = bmr_response["result"]["bmr"]
                logger.debug(f"✅ BMR recalculated: {body['bmr']}")
            else:
                logger.warning("⚠️ BMR calculation failed, using default 1.375")
                body["bmr"] = DEFAULT_BMR
        else:
            logger.warning("⚠️ lifestyle description was mise, BMR using default 1.375")
            body["bmr"] = DEFAULT_BMR

    user_data = User(**body)
    success = await connector.update_user(current_user, user_data)

    if success:
        logger.info(f"✅ Profile updated for: {current_user}")
    else:
        logger.warning(f"⚠️ Profile update failed (user not found?): {current_user}")

    return {"response": success}


@app.get("/info_nutrition")
async def info_nutrition(
    current_user: Annotated[str, Depends(get_current_user)],
    start: str = Query(default="", description="Start date (YYYY-MM-DD)"),
    end: str = Query(default="", description="End date (YYYY-MM-DD)"),
) -> Dict[str, Dict[str, Any]]:
    """Get daily nutrition history for a date range.

    Args:
        current_user (str): Authenticated username from JWT token.
        start (str): Start date in YYYY-MM-DD format. Defaults to today if empty.
        end (str): End date in YYYY-MM-DD format. Defaults to today if empty.

    Returns:
        Dict[str, Dict[str, Any]]: Nutrition info keyed by date. Example:
            {
                "2024-04-01": {"calories": 2000, "proteins": 150, ...},
                "2024-04-02": {"calories": 0, "proteins": 0, ...},
            }
            Note: All days in range returned; gaps filled with zeros.

    Raises:
        HTTPException:
            401: If token invalid/expired.
            422: If date validation fails.
            504: If timeout occurs.
            500: If unexpected error occurs.
    """
    try:
        date_range = DateRange(start=start, end=end)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    result = await connector.info_nutrition(
        current_user,
        date_range.st_time_span,
        date_range.fin_time_span,
    )
    return result if result else {}


@app.get("/daily_nutrition_norms")
async def daily_nutrition_norms(
    current_user: Annotated[str, Depends(get_current_user)],
    start: str = Query(default="", description="Start date (YYYY-MM-DD)"),
    end: str = Query(default="", description="End date (YYYY-MM-DD)"),
) -> Dict[str, Dict[str, Any]]:
    """
    Get nutrition norms history for a date range with carry-forward logic.

    IMPORTANT:
        Days without records use the last known norm (carry-forward).
        If no history exists, uses initial norms from registration.
        All days in range are returned.

    Args:
        current_user (str): Authenticated username from JWT token.
        start (str): Start date in YYYY-MM-DD format. Defaults to today if empty.
        end (str): End date in YYYY-MM-DD format. Defaults to today if empty.

    Returns:
        dict: Nutrition norms keyed by date (YYYY-MM-DD).
            Example: {
                "2024-04-01": {"calories": 2200, "proteins": 125, "fats": 73, "carbohydrates": 260},
                "2024-04-02": {"calories": 2200, "proteins": 125, "fats": 73, "carbohydrates": 260},
            }

    Raises:
        HTTPException:
            401: If token invalid/expired.
            422: If date validation fails.
            504: If timeout occurs.
            500: If unexpected error occurs.
    """
    try:
        date_range = DateRange(start=start, end=end)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    norms = await connector.nutrition_norms(
        username=current_user,
        st_time_span=date_range.st_time_span,
        fin_time_span=date_range.fin_time_span,
    )
    return norms if norms else {}


@app.get("/weight_history")
async def weight_history(
    current_user: Annotated[str, Depends(get_current_user)],
    start: str = Query(default="", description="Start date (YYYY-MM-DD)"),
    end: str = Query(default="", description="End date (YYYY-MM-DD)"),
) -> Dict[str, Any]:
    """
    Get user weight history for a date range with carry-forward logic.

    IMPORTANT:
        Days without weight records use the last known weight.
        If no history exists, uses initial weight from registration.
        All days in range are returned.

    Args:
        current_user (str): Authenticated username from JWT token.
        start (str): Start date in YYYY-MM-DD format. Defaults to today if empty.
        end (str): End date in YYYY-MM-DD format. Defaults to today if empty.

    Returns:
        dict: Weight values keyed by date (YYYY-MM-DD).
            Example: {
                "2024-04-01": {"weight": 75.5},
                "2024-04-02": {"weight": 75.5},
                "2024-04-03": {"weight": 74.0},
            }

    Raises:
        HTTPException:
            401: If token invalid/expired.
            422: If date validation fails.
            504: If timeout occurs.
            500: If unexpected error occurs.
    """
    try:
        date_range = DateRange(start=start, end=end)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    result = await connector.weight_history(
        current_user,
        date_range.st_time_span,
        date_range.fin_time_span,
    )
    return result if result else {}


@app.get("/user_ingredients")
async def user_ingredients(
    current_user: Annotated[str, Depends(get_current_user)],
) -> List[Dict[str, Any]]:
    """
    Fetches all ingredients owned by the authenticated user.

    Returns ingredient names and nutritional values (per 100g) from the
    database for the current authenticated user. Used to populate the
    user's personal ingredient library in the UI.

    Authentication:
        Requires valid JWT token via `get_current_user` dependency.

    Args:
        current_user (str): Authenticated username extracted from JWT token.

    Returns:
        List[Dict[str, Any]]: List of ingredient dictionaries.
            Each dict contains:
                name (str): Ingredient name
                calories (float): Calories per 100g
                proteins (float): Proteins per 100g
                fats (float): Fats per 100g
                carbohydrates (float): Carbohydrates per 100g
            Note: All ingredients belong to the authenticated user.

    Raises:
        HTTPException:
            401: If JWT token is invalid, expired, or missing.
            500: If database connection fails or unexpected error occurs.
    """
    ingredients = await connector.user_ingredients(username=current_user)
    return ingredients


@app.post("/ingredient_recognition")
async def ingredient_recognition(
    data: IngredientRecognitionInput,
    current_user: Annotated[str, Depends(get_current_user)],
) -> Dict[str, Any]:
    """Recognize ingredients from a food image using AI analysis.

    Processes base64 image, extracts ingredients via LLM, searches database
    for matches, and falls back to macros extraction for unknown items.
    Returns actual nutritional values (for portion weight).

    Args:
        data (IngredientRecognitionInput): Input containing base64 image
            and optional user description.
        current_user (str): Authenticated username from JWT token.

    Returns:
        Dict[str, Any]: LLM response with recognized ingredients and nutritional data.

    Raises:
        HTTPException: Propagated from underlying service calls on failure.
    """
    logger.info(f"Recognition request for user: {current_user}")
    llm_response = await assistant.get_ingredient_recognition(
        data.image_base64,
        data.user_description,
        timeout=LLM_TIMEOUT_LONG,
    )

    if llm_response.get("result"):
        img_ingredients = llm_response["result"]

        search_results, not_found = await connector.search_ingredients_batch(
            img_ingredients=img_ingredients,
            owner_username=current_user,
            distance_threshold_user_ingr=0.1,
            distance_threshold_admin_ingr=0.11,
            timeout=DB_TIMEOUT,
        )

        if not_found:
            fallback_response = await assistant.get_macros_extraction(
                not_found, timeout=LLM_TIMEOUT_LONG
            )
            if fallback_response.get("status") == "success":
                for name, macros in fallback_response.get("result", {}).items():
                    search_results.append(
                        {
                            "name": f"~{name}",
                            "weight": not_found[name],
                            "owner": "admin",
                            **macros,
                        }
                    )

        converted_results = [
            item.to_actual() if isinstance(item, IngredientItem) else item
            for item in search_results
        ]

        llm_response["result"] = converted_results

    return llm_response


@app.post("/save_meal")
async def save_meal(
    current_user: Annotated[str, Depends(get_current_user)], data: DishPayload
) -> bool:
    """
    Add a new meal with ingredients to the user's day record.

    Args:
        data (DishPayload): DishPayload with ingredient data in parallel lists.
            All nutritional values are actual (not per-100g).
            Owner field defaults to "admin" if not specified.
        current_user (str): Authenticated username from JWT token.

    Raises:
        HTTPException:
            401: If token invalid/expired.
            500: If failed to create day record.
            504: If timeout occurs.
    """

    await connector.save_meal(
        current_user,
        data.parse_modified_ingredients,
        data.parse_table,
        data.parsed_date,
    )

    return True


@app.get("/get_daily_log")
async def get_daily_log(
    current_user: Annotated[str, Depends(get_current_user)],
    date: str = Query(default="", description="Date (YYYY-MM-DD)"),
) -> List[Dict[str, Any]]:
    """Get daily nutrition log for a specific date.

    Args:
        current_user (str): Authenticated username from JWT token.
        date (str): Target date in YYYY-MM-DD format. Defaults to today if empty.

    Returns:
        List[Dict[str, Any]]: List of meal entries with actual nutritional
            values (portion-based, not per-100g).

    Raises:
        HTTPException:
            401: If token invalid/expired.
            422: If date validation fails.
            504: If timeout occurs.
    """
    single_date = SingleDate(date=date)

    result = await connector.daily_log(
        username=current_user,
        date=single_date.parsed_date,
        timeout=DB_TIMEOUT,
    )

    return [item.to_actual() for item in result] if result else []


@app.put("/save_daily_log")
async def save_daily_log(
    current_user: Annotated[str, Depends(get_current_user)], data: DishPayload
) -> bool:
    """
    Fully synchronizes the user's daily nutrition log for a specific date.

    Replaces the entire ingredient list for the day with the provided `table`.
    Ingredients not present in `table` are removed from the day's log.
    Updates per-100g macros for modified ingredients in the reference table.
    Idempotent: safe to retry without unintended side effects.

    Args:
        current_user (str): Authenticated username extracted from JWT token.
        data (DishPayload): DishPayload containing the complete desired state
            for the day:
            - `table`: Final list of ingredients that should remain in the log.
            - `modified_ingredients`: Ingredients with corrected per-100g macros.
            - `parsed_date`: Target date for the synchronization.

    Returns:
        bool: True if the synchronization completes successfully.
    """

    await connector.save_daily_log(
        current_user,
        data.parse_modified_ingredients,
        data.parse_table,
        data.parsed_date,
    )

    return True


@app.post("/translate_ingredients")
async def translate_ingredients(
    current_user: Annotated[str, Depends(get_current_user)],
    data: TranslatorInput,
) -> Dict[str, Any]:
    """Translate and normalize ingredient names to target languages.

    Accepts a dictionary where keys are original ingredient names and values
    are lists of target language codes. Returns structured JSON with canonical
    English keys and translations.

    Args:
        current_user (str): Authenticated username from JWT token.
        data (TranslatorInput): Input containing ingredients dict mapping
            original names to list of target language codes.

    Returns:
        Dict[str, Any]: Translation result with status, result dict, and
            optional error message. Example:
            {"status": "success", "result": {...}, "error": ""}

    Raises:
        HTTPException:
            502: If translation service returns error status.
    """
    if not data.ingredients:
        return {"status": "success", "result": {}, "error": ""}

    result = await assistant.translate_ingredients(
        payload=data.ingredients, timeout_on_chunk=LLM_TIMEOUT_TRANSLATION
    )

    if result.get("status") == "error":
        logger.error(f"Translation Error: {result.get('error')}")
        raise HTTPException(
            status_code=502, detail=result.get("error", "Translation failed")
        )

    if result.get("status") == "partial_success":
        logger.warning(f"Partial Translation Success: {result.get('error')}")
        return result

    return result
