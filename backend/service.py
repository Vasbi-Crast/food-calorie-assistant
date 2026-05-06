from fastapi import FastAPI, Depends, HTTPException, Request, Query
from fastapi.security import OAuth2PasswordBearer
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
from typing import Annotated, Any, List, Dict
import os
from dotenv import load_dotenv

from assistant import LLMAssistant
from search import IngredientNutritionSearch
from db_connector import DB_connector
from auth import create_token, decode_token
from schemas import (
    LoginInput,
    RegisterInput,
    User,
    SingleDate,
    DateRange,
    DishPayload,
    IngredientRecognitionInput,
    ChangeDailyLog,
)


load_dotenv()

connector = DB_connector()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Initializes and closes database connection.
    """
    await connector.connection()
    yield
    await connector.close()


app = FastAPI(lifespan=lifespan)

# CORS for Streamlit frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("STREAMLIT_URL")],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)


# === Exception Handlers ===


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    """
    Handles custom value errors raised in business logic.

    Returns 400 Bad Request with error message.
    """
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """
    Handles Pydantic validation errors.

    Formats them into a simple list for the frontend.
    Returns 422 Unprocessable Entity.
    """
    errors = []
    for error in exc.errors():
        error_type = error.get("type", "undefined_error")
        loc = error.get("loc", [])       
        field = loc[1] if len(loc) > 1 else "unknown"
        ctx = None
        if error_type in ["string_too_short", "string_too_long"]:
            ctx = error.get("ctx", None)
        errors.append({"field": field, "type_error": error_type, "ctx": ctx})
    return JSONResponse(
        status_code=422, content={"detail": "Validation failed", "errors": errors}
    )


@app.exception_handler(RuntimeError)
async def runtime_error_handler(request: Request, exc: RuntimeError) -> JSONResponse:
    """
    Handles critical runtime errors.

    Returns 500 Internal Server Error.
    """
    print(f"CRITICAL ERROR: {exc}")
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.exception_handler(TimeoutError)
async def timeout_error_handler(request: Request, exc: TimeoutError) -> JSONResponse:
    """
    Handles database or external service timeouts.

    Returns 504 Gateway Timeout.
    """
    return JSONResponse(
        status_code=504, content={"detail": "Request timed out. Try again later."}
    )


# === Authentication ===

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/authentication")


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]) -> str:
    """
    Dependency to extract and validate JWT token.

    Args:
        token (str): JWT token from Authorization header.

    Returns:
        str: Authenticated username.

    Raises:
        HTTPException: 401 if token is invalid or expired.
    """
    username = decode_token(token)
    if not username:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return username


# === LLM Initialization ===

with open("./prompt_ingredient_recognition.txt", "r") as f:
    prompt_ingredient_recognition = "".join(f.readlines())

with open("./prompt_macros_extraction.txt", "r") as f:
    prompt_macros_extraction = "".join(f.readlines())


assistant = LLMAssistant(prompt_ingredient_recognition,
                         prompt_macros_extraction,
                         temperature=0.01,
                         max_tokens=250,
                         top_p=0.1)
engine = IngredientNutritionSearch("nutrition.csv")


# === API Endpoints ===


@app.post("/authentication")
async def authentication(data: LoginInput) -> Dict[str, str]:
    """
    User authorization based on username and password.

    Args:
        data (LoginInput): Username and password for authentication.

    Returns:
        dict: JWT access token.
            - 'access_token' (str): JWT token for authorized requests.
            - 'token_type' (str): Token type (always 'bearer').

    Raises:
        HTTPException:
            - 401: If username not found or password is invalid.
            - 504: If a TimeoutError occurs.
            - 500: If an unexpected error occurs.
    """
    result = await connector.verify(data.username, data.password)

    if result == "SUCCESSFUL":
        token = create_token(data.username)
        return {"access_token": token, "token_type": "bearer"}
    raise HTTPException(status_code=401, detail=result)


@app.post("/registration")
async def registration(data: RegisterInput) -> Dict[str, bool]:
    """
    Register a new user.

    Args:
        data (RegisterInput): User registration data including credentials and profile.

    Returns:
        dict: Registration status.
            - 'response' (bool): True if successful.

    Raises:
        HTTPException:
            - 400: If username already exists.
            - 504: If a TimeoutError occurs.
            - 500: If an unexpected error occurs.
    """
    res_adding = await connector.add_user(data)

    if not res_adding:
        raise HTTPException(status_code=400, detail="Username already exists")

    return {"response": True}


@app.get("/users/me")
async def get_user_information(
    current_user: Annotated[str, Depends(get_current_user)]
) -> Dict[str, Any]:
    """
    Get current user profile information.

    Args:
        current_user (str): Authenticated username from JWT token.

    Returns:
        dict: User's profile information (age, bmr, gender, weight, height).

    Raises:
        HTTPException:
            - 401: If token is invalid or expired.
            - 504: If a TimeoutError occurs.
            - 500: If an unexpected error occurs.
    """
    return await connector.user_information(current_user)


@app.put("/users/me")
async def update_user_info(
    data: User, current_user: Annotated[str, Depends(get_current_user)]
) -> Dict[str, bool]:
    """
    Update current user profile information.

    Args:
        data (User): Updated user parameters.
        current_user (str): Authenticated username from JWT token.

    Returns:
        dict: Operation status.
            - 'response' (bool): True if successful.

    Raises:
        HTTPException:
            - 401: If token is invalid or expired.
            - 504: If a TimeoutError occurs.
            - 500: If an unexpected error occurs.
    """
    return {
        "response": await connector.update_user(
            current_user,
            data,
        )
    }


@app.get("/info_nutrition")
async def info_nutrition(
    current_user: Annotated[str, Depends(get_current_user)],
    start: str = Query(default="", description="Start date (YYYY-MM-DD)"),
    end: str = Query(default="", description="End date (YYYY-MM-DD)"),
) -> Dict[str, Dict[str, Any]]:
    """
    Get daily nutrition history for a date range.

    Query Parameters:
        - start: Start date (YYYY-MM-DD). Defaults to today if empty.
        - end: End date (YYYY-MM-DD). Defaults to today if empty.

    Args:
        current_user (str): Authenticated username from JWT token.
        start (str): Start date in YYYY-MM-DD format.
        end (str): End date in YYYY-MM-DD format.

    Returns:
        dict: Daily nutrition information keyed by date.
            Example: {
                "2024-04-01": {"calories": 2000, "proteins": 150, "fats": 70, "carbohydrates": 250},
                "2024-04-02": {"calories": 0, "proteins": 0, "fats": 0, "carbohydrates": 0},
                ...
            }
            Note: All days in range are returned (gaps filled with zeros).

    Raises:
        HTTPException:
            - 401: If token is invalid or expired.
            - 422: If date validation fails (start > end or invalid format).
            - 504: If a TimeoutError occurs.
            - 500: If an unexpected error occurs.
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
    Get nutrition norms history for a date range.

    IMPORTANT:
        - Days without records use the last known norm (carry-forward).
        - If no history exists, uses initial norms from registration.
        - All days in range are returned (same format as /info_nutrition).

    Query Parameters:
        - start: Start date (YYYY-MM-DD). Defaults to today if empty.
        - end: End date (YYYY-MM-DD). Defaults to today if empty.

    Args:
        current_user (str): Authenticated username from JWT token.
        start (str): Start date in YYYY-MM-DD format.
        end (str): End date in YYYY-MM-DD format.

    Returns:
        dict: Nutrition norms keyed by date.
            Example: {
                "2024-04-01": {"calories": 2200, "proteins": 125, "fats": 73, "carbohydrates": 260},
                "2024-04-02": {"calories": 2200, "proteins": 125, "fats": 73, "carbohydrates": 260},
                "2024-04-03": {"calories": 2300, "proteins": 130, "fats": 75, "carbohydrates": 270},
                ...
            }
            Note: Format matches /info_nutrition for easy comparison.

    Raises:
        HTTPException:
            - 401: If token is invalid or expired.
            - 422: If date validation fails (start > end or invalid format).
            - 504: If a TimeoutError occurs.
            - 500: If an unexpected error occurs.
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
    Get user weight history for a date range.

    IMPORTANT:
        - Days without weight records are filled with the last known weight (carry-forward).
        - If no history exists, uses initial weight from registration.
        - All days in range are returned (same format as /info_nutrition).

    Query Parameters:
        - start: Start date (YYYY-MM-DD). Defaults to today if empty.
        - end: End date (YYYY-MM-DD). Defaults to today if empty.

    Args:
        current_user (str): Authenticated username from JWT token.
        start (str): Start date in YYYY-MM-DD format.
        end (str): End date in YYYY-MM-DD format.

    Returns:
        dict: Weight values keyed by date.
            Example: {
                "2024-04-01": {"weight": 75.5},
                "2024-04-02": {"weight": 75.5},
                "2024-04-03": {"weight": 74.0},
                ...
            }
            Note: Format matches /info_nutrition for easy comparison.

    Raises:
        HTTPException:
            - 401: If token is invalid or expired.
            - 422: If date validation fails (start > end or invalid format).
            - 504: If a TimeoutError occurs.
            - 500: If an unexpected error occurs.
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


@app.post("/ingredient_recognition")
async def ingredient_recognition(
    data: IngredientRecognitionInput,
    current_user: Annotated[str, Depends(get_current_user)],
) -> Any:
    """
    Recognize ingredients from a food image using AI analysis.

    Args:
        data (IngredientRecognitionInput): Image and optional description.
            - image_base64: Base64-encoded image data.
            - user_description: Optional dish description.
        current_user (str): Authenticated username from JWT token.

    Returns:
        Any: LLM response with identified ingredients and nutrition info.

    Raises:
        HTTPException:
            - 400: If image_base64 is missing or invalid.
            - 504: If a TimeoutError occurs.
            - 500: If an unexpected error occurs.
    """
    llm_response = await assistant.get_ingredient_recognition(
        data.image_base64,
        data.user_description,
        timeout=240,
    )

    if llm_response.get("result"):
        search_results = await engine.search(llm_response["result"], assistant=assistant, search_type="semantic")
        llm_response["result"] = search_results

    return llm_response


@app.post("/add_new_dish")
async def add_new_dish(
    data: DishPayload, current_user: Annotated[str, Depends(get_current_user)]
) -> bool:
    """
    Add a new dish with ingredients to the user's day record.

    Args:
        data (DishPayload): Ingredient data in parallel lists.
        current_user (str): Authenticated username from JWT token.

    Returns:
        bool: True if successful.

    Raises:
        RuntimeError: If failed to create or retrieve day record.
        HTTPException:
            - 401: If token is invalid or expired.
            - 504: If a TimeoutError occurs.
            - 500: If an unexpected error occurs.
    """
    day_id = await connector.add_day(
        username=current_user,
        created_at=data.parsed_date,
        timeout=20,
    )

    if not day_id:
        raise HTTPException(status_code=500, detail="Failed to create day record")

    await connector.add_ingredients_to_day(
        day_id=day_id,
        ingredients=data.ingredients,
        created_at=data.parsed_date,
        timeout=20,
    )

    return True


@app.get("/get_daily_log")
async def get_daily_log(
    current_user: Annotated[str, Depends(get_current_user)],
    date: str = Query(default="", description="Date (YYYY-MM-DD)"),
) -> List[Dict[str, Any]]:
    """
    Get daily log for a specific date.

    Query Parameters:
        - date: Date string (YYYY-MM-DD). Defaults to today if empty.

    Args:
        current_user (str): Authenticated username from JWT token.

    Returns:
        list: List of ingredients with nutrition info for the specified date.
            Example: [{"ingredient": "apple", "weight": 100, "calories": 52, ...}]

    Raises:
        HTTPException:
            - 401: If token is invalid or expired.
            - 422: If date format is invalid.
            - 504: If a TimeoutError occurs.
            - 500: If an unexpected error occurs.
    """
    # Validate date using Pydantic model
    single_date = SingleDate(date=date)

    result = await connector.daily_log(
        username=current_user,
        date=single_date.parsed_date,
        timeout=20,
    )

    return result if result else []


@app.put("/daily_log/update")
async def update_daily_log(
    data: ChangeDailyLog, current_user: Annotated[str, Depends(get_current_user)]
) -> bool:
    """
    Update daily log with partial changes (edited, added, deleted).

    Args:
        data (ChangeDailyLog): Changes to apply.
            - edited: List of ingredients with new weight values.
            - added: List of new ingredients to add.
            - deleted: List of ingredient names to remove.
        current_user (str): Authenticated username from JWT token.

    Returns:
        dict: Operation status.
            - 'response' (bool): True if successful.

    Raises:
        HTTPException:
            - 401: If token is invalid or expired.
            - 504: If a TimeoutError occurs.
            - 500: If an unexpected error occurs.
    """

    day_id = await connector.add_day(
        username=current_user,
        created_at=data.parsed_date,
        timeout=20,
    )

    if not day_id:
        raise HTTPException(status_code=500, detail="Failed to create day record")

    if data.deleted:
        await connector.del_ingredients_in_day(
            day_id=day_id,
            deleted=data.deleted,
            timeout=20,
        )

    if data.edited:
        await connector.change_ingredients_in_day(
            day_id=day_id,
            edited=data.edited,
            timeout=20,
        )

    if data.added:
        await connector.add_ingredients_to_day(
            day_id=day_id,
            ingredients=data.added,
            created_at=data.parsed_date,
            timeout=20,
        )

    return True
