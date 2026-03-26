import random
import requests
import json


class FakeResponse:
    """
    A class to simulate the response object returned by requests.post.
    """

    def __init__(self, json_data, status_code):
        self._json_data = json_data
        self.status_code = status_code
        self.text = json.dumps(self._json_data)

    def json(self):
        return self._json_data


def post(url, json=None, headers=None):
    """
    Simulates the behavior of requests.post and returns a mocked response.

    Args:
        url (str): The URL the request is being sent to (ignored in mock).
        json (dict): JSON payload (ignored in mock).
        headers (dict): Headers (ignored in mock).

    Returns:
        FakeResponse: A mock response object with random nutritional values.
    """
    # Returning random data simulating the response from the service
    mock_result = {
        "calories": random.randint(100, 1000),
        "proteins": random.randint(50, 100),
        "fats": random.randint(50, 100),
        "carbohydrates": random.randint(50, 100),
    }

    # Create the fake response object with mock_result
    return FakeResponse(
        {"status": "success", "result": mock_result, "error": ""},
        200,
    )


def get(url, **kwargs):
    """
    Uses the real requests library to perform a GET request.

    Args:
        url (str): The URL to send the request to (typically an image URL).
        headers (dict): Optional headers to include in the request.

    Returns:
        requests.Response: The response object from the requests library.
    """
    response = requests.get(url, stream=True)
    response.raise_for_status()

    return response
