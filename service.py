from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
from typing import Annotated, Any
import base64
import os
from dotenv import load_dotenv

from assistant import LLMAssistant
from search import IngredientNutritionSearch
from db_connector import DB_connector
from auth import create_token, decode_token
from schemas import LoginInput, RegisterInput, SettingsInput, NutritionInput, NutritionOutput, DishPayload
load_dotenv()

connector = DB_connector()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connector.connection()
    yield
    await connector.close()


app = FastAPI(lifespan=lifespan)

# CORS for Streamlit
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)


# === Exception Handlers ===

@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    """Handles custom value errors raised in business logic."""
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc)}
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Handles Pydantic validation errors.
    Formats them into a simple list for the frontend.
    """
    errors = []
    for error in exc.errors():
        error_type = error.get("type", "undefined_error")

        loc = error.get("loc", [])
        field = loc[1] if len(loc) > 1 else "unknown"
        
        errors.append({"field": field, "type_error": error_type})
    
    return JSONResponse(
        status_code=422,
        content={"detail": "Validation failed", "errors": errors}
    )

@app.exception_handler(RuntimeError)
async def runtime_error_handler(request: Request, exc: RuntimeError):
    """Handles critical runtime errors."""
    print(f"CRITICAL ERROR: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )

@app.exception_handler(TimeoutError)
async def timeout_error_handler(request: Request, exc: TimeoutError):
    """Handles database or external service timeouts."""
    return JSONResponse(
        status_code=504,
        content={"detail": "Request timed out. Try again later."}
    )

# OAuth2 scheme (reads the token from the Authorization header: Bearer <token>)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/authentication")


# --- Dependency for protecting routes ---
async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]) -> str:
    username = decode_token(token)
    if not username:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return username


# === LLM initialization ===
with open("./prompt.txt", "r") as f:
    system_prompt = "".join(f.readlines())

assistant = LLMAssistant(system_prompt, temperature=0.01, max_tokens=250, top_p=0.1)
engine = IngredientNutritionSearch("nutrition.csv")


@app.post("/authentication")
async def authentication(data: LoginInput) -> Any:
    """
    User authorization based on a request with username and password

    Args:
        The request should contain a JSON body with a 'username' field that contains
        a unique username for authorization and 'password' field that contains user's password.

    Returns:
        dict: A JSON-serializable dictionary with authentication token.
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

    elif result == "USER_NOT_FOUND":
        raise HTTPException(status_code=401, detail="User not found")

    else:
        raise HTTPException(status_code=401, detail="Invalid password")


@app.post("/registration")
async def registration(data: RegisterInput) -> Any:
    """
    Register a new user

    Args:
        The request should contain a JSON body with:
        - username: A unique username for authorization.
        - password: User's password.
        - age: User's age.
        - bmr: The user's basal metabolic rate.
        - gender: User's gender.
        - weight: User's weight.
        - height: User growth.

    Returns:
        dict: A JSON-serializable dictionary with registration status.
            - 'response' (bool): True - if registration is successful.

    Raises:
        HTTPException:
            - 400: If username already exists.
            - 504: If a TimeoutError occurs.
            - 500: If an unexpected error occurs.
    """

    res_adding = await connector.add_user(
        data.username,
        data.password,
        data.age,
        data.bmr,
        data.gender,
        data.weight,
        data.height,
    )
    if not res_adding:
        raise HTTPException(status_code=400, detail="Username already exists")
    else:
        return {"response": True}


@app.get("/users/me")
async def get_user_information(
    current_user: Annotated[str, Depends(get_current_user)]
) -> Any:
    """
    Getting current user information

    Args:
        The request should contain an Authorization header with a valid Bearer token.
        Username is extracted from the token automatically.

    Returns:
        dict: A JSON-serializable dictionary with
        user's information (age, bmr, gender, weight, height).

    Raises:
        HTTPException:
            - 401: If token is invalid or expired.
            - 504: If a TimeoutError occurs.
            - 500: If an unexpected error occurs.
    """

    return await connector.user_information(current_user)


@app.put("/users/me")
async def update_user_info(
    data: RegisterInput, current_user: Annotated[str, Depends(get_current_user)]
) -> Any:
    """
    Update current user information

    Args:
        The request should contain:
        - Authorization header with a valid Bearer token (username extracted automatically).
        - JSON body with updated user parameters:
            - age: User's age.
            - bmr: The user's basal metabolic rate.
            - gender: User's gender.
            - weight: User's weight.
            - height: User growth.

    Returns:
        dict: A JSON-serializable dictionary with information about the operation performed.
            - 'response' (bool): True - if update is successful.

    Raises:
        HTTPException:
            - 401: If token is invalid or expired.
            - 504: If a TimeoutError occurs.
            - 500: If an unexpected error occurs.
    """

    return {
        "response": await connector.update_user(
            current_user, data.age, data.bmr, data.gender, data.weight, data.height
        )
    }


@app.get("/info_nutrition")
async def info_nutrition(
    st_time_span: str,
    fin_time_span: str,
    current_user: Annotated[str, Depends(get_current_user)],
) -> Any:
    """
    Getting information about daily nutrition history

    Args:
        The request should contain:
        - Authorization header with a valid Bearer token (username extracted automatically).
        - Query parameters:
            - st_time_span: The beginning of the time interval. Format: YYYY-MM-DD.
            - fin_time_span: The end of the time interval. Format: YYYY-MM-DD.

    Returns:
        dict: A JSON-serializable dictionary of daily nutrition
        information, with dates as keys.

    Raises:
        HTTPException:
            - 401: If token is invalid or expired.
            - 504: If a TimeoutError occurs.
            - 500: If an unexpected error occurs.
    """

    return await connector.info_nutrition(current_user, st_time_span, fin_time_span)


@app.post("/daily_nutrition_norms", response_model=NutritionOutput)
async def calculate_daily_nutrition_norms(
    data: NutritionInput, current_user: Annotated[str, Depends(get_current_user)]
) -> Any:
    """
    Calculates daily caloric intake and macronutrient distribution based on user parameters.

    Uses the Mifflin-St Jeor equation adjusted by an activity/goal multiplier (`bmr`)
    and splits total calories into proteins, fats, and carbohydrates using predefined ratios.

    Args:
        The request should contain:
        - Authorization header with a valid Bearer token (username extracted automatically).
        - JSON body with calculation parameters:
            - age (int): User's age in years.
            - bmr (float): Activity level or goal multiplier (e.g., 1.2, 1.55).
            - gender (str): 'm' for male, 'w' for female, or other for neutral.
            - weight (float): Weight in kilograms.
            - height (float): Height in centimeters.

    Returns:
        dict: JSON-serializable dictionary containing calculated daily norms:
            - calories (int)
            - proteins (float)
            - fats (float)
            - carbohydrates (float)

    Raises:
        HTTPException:
            - 401: If token is invalid or expired.
            - 504: If a TimeoutError occurs during processing.
            - 500: If an unexpected error occurs.
    """

    res = {"calories": 0, "proteins": 0, "fats": 0, "carbohydrates": 0}

    # Caloric values per gram of macronutrients
    CAL_PER_G = {"proteins": 4, "fats": 9, "carbohydrates": 4}

    # Base ratios (Maintenance / Balanced diet)
    # Adjust these based on your goal (see table below)
    P_RATIO, F_RATIO, C_RATIO = 0.3, 0.3, 0.4

    # 1️⃣ Calculate BMR (Mifflin-St Jeor equation) without code duplication
    base = 10 * data.weight + 6.25 * data.height - 5 * data.age
    if data.gender == "m":
        base += 5
    elif data.gender == "w":
        base -= 161
    else:
        base -= 78  # Neutral/averaged fallback

    # 2️⃣ Total daily calories (user_info["bmr"] here acts as an activity/goal multiplier)
    total_calories = base * data.bmr
    res["calories"] = round(total_calories)

    # 3️⃣ Calculate macronutrients in grams
    res["proteins"] = round((total_calories * P_RATIO) / CAL_PER_G["proteins"], 1)
    res["fats"] = round((total_calories * F_RATIO) / CAL_PER_G["fats"], 1)
    res["carbohydrates"] = round(
        (total_calories * C_RATIO) / CAL_PER_G["carbohydrates"], 1
    )

    return res


@app.post("/ingredient_recognition")
async def ingredient_recognition(request: Request) -> Any:
    """
    Generates a response based on the Base64-encoded image string provided in the request.

    Args:
        The request should contain a JSON body with a 'image_base64' field that contains
        the base64 encoded image data and 'user_description' field that contains custom
        description of the dish in the image.

    Returns:
        Any: The response generated by the assistant.

    Raises:
        HTTPException:
            - 400: If the Base64 decoding fails.
            - 504: If a TimeoutError occurs.
            - 500: If an unexpected error occurs.
    """
    data = await request.json()
    image_base64 = data.get("image_base64")
    user_description = data.get("user_description")

    if not image_base64:
        raise HTTPException(
            status_code=400, detail="Base64 image data is required."
        )

    try:
        base64.b64decode(image_base64)
    except Exception as e:
        raise HTTPException(
            status_code=400, detail=f"Invalid Base64 string: {str(e)}"
        )

    llm_response = await assistant.generate_response_async(
        image_base64, user_description, timeout=240
    )

    if llm_response.get("result"):
        search_results = engine.search(
            llm_response["result"], search_type="semantic"
        )
        llm_response["result"] = search_results

    return llm_response

@app.post("/add_new_dish")
async def add_new_dish(data: DishPayload,
                                 current_user: Annotated[str, Depends(get_current_user)]) -> Any:
    """
    Generates a response based on the Base64-encoded image string provided in the request.

    Args:
        The request should contain a JSON body with a 'image_base64' field that contains
        the base64 encoded image data and 'user_description' field that contains custom
        description of the dish in the image.

    Returns:
        Any: The response generated by the assistant.

    Raises:
        HTTPException:
            - 400: If the Base64 decoding fails.
            - 504: If a TimeoutError occurs.
            - 500: If an unexpected error occurs.
    """
    return await connector.new_dish(current_user, data)