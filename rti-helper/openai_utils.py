import logging
import json
import time
from pathlib import Path
from openai import (
    OpenAI,
    APIError,
    OpenAIError,
    ConflictError,
    NotFoundError,
    APIStatusError,
    RateLimitError,
    APITimeoutError,
    BadRequestError,
    APIConnectionError,
    AuthenticationError,
    InternalServerError,
    PermissionDeniedError,
    UnprocessableEntityError,
    APIResponseValidationError,
)
from .exceptions import (
    MissingEnvironmentVariableError,
    CriticalError,
)


def handle_openai_errors(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (RateLimitError, InternalServerError, APITimeoutError, APIConnectionError) as e:
            logging.error(f"{e.__class__.__name__} occurred: {e}. Trying again...")
            time.sleep(1.1)
            return {}  # Return an empty dictionary to indicate a retryable error that still failed after retries
        except (AuthenticationError, PermissionDeniedError) as e:
            logging.error(f"{e.__class__.__name__} occurred: {e}. API authentication failed, proceeding with manual input.")
            return None  # Return None to indicate an authentication failure or permission issue
        except (BadRequestError, NotFoundError, ConflictError, UnprocessableEntityError, APIResponseValidationError, APIStatusError, OpenAIError, APIError) as e:
            logging.error(f"{e.__class__.__name__} occurred: {e}.")
            return None  # Return None to indicate a critical API request error
    return wrapper

@handle_openai_errors
def get_audio_transcript(trimmed_audio_filename, openai_api_key, config_obj):
    """
    Attempts to get the audio transcript from a trimmed audio file using OpenAI's API.
    Retries up to max_attempts times if certain exceptions occur.
    Uses the audio model specified in the configuration.
    """
    logging.debug(f"Starting transcription process for audio file: {trimmed_audio_filename}")
    if openai_api_key is None:
        logging.warning("OpenAI API key is missing. Unable to obtain audio transcript.")
        return None

    for attempt in range(config_obj.max_attempts):  # try up to max_attempts times
        logging.debug(f"Attempt {attempt+1} for audio transcription.")
        with open(trimmed_audio_filename, 'rb') as audio_file:
            logging.debug("Sending audio file to OpenAI for transcription.")
            response = OpenAI(api_key=openai_api_key).audio.transcriptions.create(
                model=config_obj.audio_model,
                file=audio_file, 
                language="en",
                response_format="text"
            )
            if response is None:
                logging.error(f"Attempt {attempt+1}: Received None response from OpenAI API.")
                time.sleep(1.1)  # Wait before retrying to avoid API limit
                continue  # Skip the current iteration and try again
            logging.debug(f"API response: {response}")
            return response

    # If the loop completes without returning, it means transcription failed
    logging.error("Failed to obtain audio transcript after multiple attempts. Proceeding with manual input.")
    return None
    

@handle_openai_errors
def call_AI_for_VRN_in_transcript(transcript, config_obj, openai_api_key):
    """
    Calls the AI model to identify British Vehicle Registration Numbers (VRNs) in the provided transcript.
    Retries up to max_attempts times with an increasing temperature if certain exceptions occur.
    """
    system_prompt = "Your task is to identify a British Vehicle Registration Number (VRN) in text. " \
                    "A VRN typically looks like 'LD23 ABC', 'MA74 GHI', etc."
    user_prompt = f"Transcript: {transcript}. Identify the target VRN. VRN may be spelt out phonetically. " \
                  "Respond in JSON format with the VRN itself or 'FAIL'."

    for attempt in range(1, config_obj.max_attempts + 1):
        logging.debug(f"Attempt {attempt} for VRN identification.")
        temperature = config_obj.initial_temperature if attempt == 1 else config_obj.increased_temperature
        prompt = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        try:
            response = OpenAI(api_key=openai_api_key).chat.completions.create(
                model=config_obj.openai_model,
                temperature=temperature,
                response_format={"type": "json_object"},
                max_tokens=250,
                messages=prompt
            )
            logging.debug(f"API response: {response}")

            # Attempt to decode the JSON response
            AI_response_content = response.choices[0].message.content
            AI_response_json = json.loads(AI_response_content)
            AI_VRN = AI_response_json.get("VRN", "FAIL")

            return AI_VRN
        except json.JSONDecodeError as e:
            logging.error(f"Error decoding JSON response: {e}. Retrying...")
            time.sleep(1.1)  # Wait before retrying to avoid API limit
            continue  # Continue to the next attempt

    logging.error("Failed to identify VRN after multiple attempts. Proceeding with manual input.")
    return "FAIL"

def extract_or_request_VRN(transcript, openai_api_key, config_obj):
    """
    Extracts or requests the user to provide a Vehicle Registration Number (VRN) based on the transcript.
    """
    if transcript:
        try:
            # Call the function to extract VRN from the transcript in json format using the provided AI model
            VRN_response = call_AI_for_VRN_in_transcript(transcript, config_obj, openai_api_key)
            if VRN_response is None:
                logging.error("Failed to obtain VRN from OpenAI. Proceeding with manual input.")
                # Since VRN_response is None, skip the processing and move to manual input
            else:
                VRN = VRN_response.replace(" ", "")  # Remove any spaces from the VRN
                # If extraction is successful and doesn't return a 'FAIL' message, ask for user confirmation
                if VRN != 'FAIL':
                    delimiter = '=' * (len(VRN) + 32)  # Adjust the length of the delimiter based on the VRN length
                    user_input_prompt = f"\n{delimiter}\nPlease confirm VRN is '{VRN}': [Y/n] \n{delimiter}\n"
                    user_input = input(user_input_prompt).strip().lower()
                    if user_input in ['', 'y', 'yes']:
                        return VRN
                    else:
                        logging.info("VRN rejected by the user. Requesting manual input.")
        except Exception as e:
            logging.error(f"An error occurred while trying to extract the VRN: {e}")
            # Handle the error or decide to ask the user for VRN manually

    # If the VRN is not confirmed, an error occurs, or the OpenAI response was None, ask the user to provide it manually
    logging.info("Unable to extract VRN from audio transcript.")
    while True:
        provided_vrn = input("Please enter VRN of the third-party vehicle: ")
        # Check if the VRN contains at least one integer and one letter
        if any(char.isdigit() for char in provided_vrn) and any(char.isalpha() for char in provided_vrn):
            provided_vrn = provided_vrn.replace(" ", "").upper()  # Remove any spaces from the provided VRN and capitalize all letters
            return provided_vrn
        logging.error("Invalid VRN format. Please try again.")

def normalize_keys(d):
    """Normalize all keys in a dictionary to lowercase with underscores."""
    return {k.replace(" ", "_").lower(): v for k, v in d.items()}

@handle_openai_errors
def infer_submission_info_from_text_using_AI(full_text, openai_api_key, config_obj):
    """
    Infers submission details such as 'submission ID', suspected offence category, incident date, time, 
    and location from the provided text using an AI model. 
    This function makes multiple attempts (as defined in the configuration object) 
    to get a valid response from the AI, handling bad JSON responses and other retryable exceptions.

    Parameters:
    - full_text (str): The text from which submission details are to be inferred.
    - openai_api_key (str): The API key for accessing the OpenAI service.
    - config_obj (object): A configuration object containing settings like the AI model to use, 
        the number of maximum attempts, and temperature settings for the AI response.

    Returns:
    - dict: A dictionary containing the inferred submission details. 
        Keys include 'submission_id', 'offence_category', 'incident_date', 'incident_time', and 'incident_location'.
        If the function fails to infer the details after the maximum number of attempts, it returns a dictionary with all keys set to None.
    """

    # Initialize a dictionary with all keys set to None
    result = {'submission_id': None, 'offence_category': None, 'incident_date': None, 'incident_time': None, 'incident_location': None}
    if not openai_api_key:
        logging.info("OpenAI API key is not provided. Cannot proceed with AI inference.")
        return result  # Return the result dictionary with all keys set to None

    client = OpenAI(api_key=openai_api_key)

    for attempt in range(1, config_obj.max_attempts + 1):
        logging.debug(f"Attempt {attempt} out of {config_obj.max_attempts} for inferring submission ID and offence category.")
        AI_model = config_obj.openai_model
        temperature = config_obj.initial_temperature if attempt == 1 else config_obj.increased_temperature

        try:
            response = client.chat.completions.create(
                model=AI_model,
                temperature=temperature,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": "You are a helpful assistant, very good at text analysis of police reports. You respond in JSON as required."},
                    {"role": "user", "content": f"This incident report submission document contains the following text: {full_text}. "
                                                "Can you infer the 'submission ID' and categorize the suspected offence into one of the following categories: "
                                                "'Careless Driving including close pass [CD]' , 'Mobile Phone Use [CU]', "
                                                "'Not complying with a street sign or stopping in the cycle box [TS]', 'Other [Other]'? "
                                                "Return the submission ID, offence category's code such as (eg. CD, CU, TS, Other), incident date in dd/mm/yyyy format, incident time in 24-hr hh:mm format and incident location. "
                                                "In summary the keys you need to return are submission_id, offence_category, incident_date, incident_time, incident_location."
                                                "Choose only one offence category. If you are unsure of any key return that one blank."}
                ]
            )
            response_json = json.loads(response.choices[0].message.content)
        except json.JSONDecodeError as e:
            logging.error(f"Error decoding JSON response: {e}. Retrying...")
            time.sleep(1.1)  # Wait before retrying to avoid API limit
            continue

        if isinstance(response_json, dict):
            normalized_response_json = normalize_keys(response_json)
            missing_keys = [key for key in result if not normalized_response_json.get(key, '').strip()]
            if not missing_keys:
                # Update the result dictionary with values from the normalized_response_json
                result.update({key: normalized_response_json[key] for key in result})
                return result
            else:
                logging.error(f"Received unusable JSON content: Missing {', '.join(missing_keys)}. Retrying...")
                logging.debug(f"Raw AI response:{response}")
                continue

    logging.info(f"All {config_obj.max_attempts} attempts to infer the submission ID and offence category have failed.")
    return result  # Return the result dictionary with None values if all attempts fail