import logging
import requests
import json
import time

def handle_dvla_errors(func):
    """
    A decorator to handle errors for DVLA API calls, including JSON decoding errors, and retry on specific exceptions.
    """
    def wrapper(registration_number, dvla_api_key, config_obj):
        max_attempts = config_obj.max_attempts
        for attempt in range(max_attempts):
            try:
                response = func(registration_number, dvla_api_key, config_obj)
                # Attempt to decode JSON only if the response is not None
                if response:
                    vehicle_details = response.json()  # This line can raise a json.JSONDecodeError
                    logging.info(f"Successfully retrieved vehicle details from DVLA for registration number {registration_number}.")
                    return vehicle_details
            except requests.exceptions.Timeout as e:
                logging.warning(f"TimeoutError on attempt {attempt + 1} of {max_attempts}: {e}. Retrying...")
            except requests.exceptions.HTTPError as e:
                logging.error(f"HTTPError on attempt {attempt + 1} of {max_attempts}: {e}.")
                break  # HTTP errors are often conclusive, no retry
            except (requests.exceptions.ConnectionError, requests.exceptions.RequestException, json.JSONDecodeError) as e:
                error_type = "JSONDecodeError" if isinstance(e, json.JSONDecodeError) else "Connection/Request Error"
                logging.warning(f"{error_type} on attempt {attempt + 1} of {max_attempts}: {e}. Retrying...")
            time.sleep(2)  # Wait before retrying
        logging.error("Max attempts reached. Proceeding without DVLA data.")
        return None
    return wrapper

@handle_dvla_errors
def get_vehicle_details_from_dvla(registration_number, dvla_api_key, config_obj):
    """
    Retrieves vehicle details from the DVLA API.
    """
    if not dvla_api_key or not config_obj.use_APIs:
        logging.info("DVLA API key is missing or use_APIs is set to false. Skipping DVLA data retrieval.")
        return None

    url = 'https://driver-vehicle-licensing.api.gov.uk/vehicle-enquiry/v1/vehicles'
    headers = {'x-api-key': dvla_api_key, 'Content-Type': 'application/json'}
    data = {'registrationNumber': registration_number}

    response = requests.post(url, headers=headers, data=json.dumps(data))
    response.raise_for_status()  # This will raise an HTTPError if the response was an error
    return response  # Return the response object for JSON decoding in the decorator