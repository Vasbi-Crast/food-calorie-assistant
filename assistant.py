from typing import Dict, Any
import os
import json
import asyncio
import ollama
from dotenv import load_dotenv


class LLMAssistant:
    """
    A class to interact with a large language model (LLM) using the Ollama API.
    """

    def __init__(
        self,
        system_prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 1024,
        top_p: float = 0.5,
    ):
        """
        Initializes the LLMAssistant instance with a system prompt and generation parameters.

        Raises:
            ValueError: If the OLLAMA_HOST environment variable is not set.
        """
        load_dotenv()

        ollama_host = os.getenv("OLLAMA_HOST")
        if not ollama_host:
            raise ValueError("Environment variable OLLAMA_HOST is missing or empty.")

        self.system_prompt = system_prompt
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.top_p = top_p

        self.client = ollama.AsyncClient(host=ollama_host)

    def _generate_payload(self, image_base64: str, user_desk: str) -> Dict[str, Any]:
        """
        Generates the input payload for the model using the Base64-encoded image.
        """
        if not user_desk.strip():
            return {
                "model": os.getenv("MODEL_NAME", "llava"),
                "messages": [
                    {
                        "role": "user",
                        "content": self.system_prompt + "None",
                        "images": [image_base64],
                    }
                ],
                "options": {
                    "temperature": self.temperature,
                    "num_predict": self.max_tokens,
                    "top_p": self.top_p,
                },
            }
        else:
            return {
                "model": os.getenv("MODEL_NAME", "llava"),
                "messages": [
                    {
                        "role": "user",
                        "content": self.system_prompt + user_desk,
                        "images": [image_base64],
                    }
                ],
                "options": {
                    "temperature": self.temperature,
                    "num_predict": self.max_tokens,
                    "top_p": self.top_p,
                },
            }

    def _parse_response(self, output: str) -> Dict[str, Any]:
        """
        Parses the model output into a JSON object.
        """
        try:
            output = output.replace("```", "").replace("json", "")
            print(output)
            json_result = json.loads(output)
            return {"status": "success", "result": json_result, "error": ""}
        except json.JSONDecodeError:
            return {
                "status": "error",
                "result": {},
                "error": "Failed to parse the model response as JSON.",
            }

    async def _chat(self, input_data: dict, timeout: int):
        """
        Execute chat request with timeout and error handling.
        """
        try:
            response = await asyncio.wait_for(
                self.client.chat(**input_data), timeout=timeout
            )
            return response
        except asyncio.TimeoutError:
            raise Exception(f"The request exceeded the time limit ({timeout} seconds)")
        except ollama.ResponseError as e:
            raise Exception(f"Ollama API error: {e.status_code} - {e.error}")
        except Exception as e:
            raise Exception(f"An unexpected error occurred: {type(e).__name__}: {e}")

    async def generate_response_async(
        self, image_base64: str, user_desk: str, timeout: int = 60
    ) -> Dict[str, Any]:
        """
        Generator for asynchronous access to the model

        Args:
            image_base64 (str): The base64 encoded image string.
            user_desk (str): Custom description of the dish in the image
            timeout (int): Time limit for accessing the model.

        Return:
            dict: A dictionary containing the request status ('success' or 'error'),
            the request result, and the error text

        """
        if timeout < 1:
            raise ValueError("Timeout value must be greater than or equal to 1.")

        payload = self._generate_payload(image_base64, user_desk)

        try:
            response = await self._chat(payload, timeout)

            output = response["message"]["content"]

            return self._parse_response(output)

        except Exception as e:
            return {
                "status": "error",
                "result": {},
                "error": f"An error occurred during prediction: {str(e)}",
            }
