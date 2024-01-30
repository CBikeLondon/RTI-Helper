import logging, time
import fitz  # pymupdf
from pathlib import Path
from .exceptions import FileOpenError
from .openai_utils import infer_submission_info_from_text_using_AI

def stringify_pdf_and_infer_info(filename, openai_api_key, config_obj, video_file_path):
    """
    Extracts text from a PDF document and handles errors.

    Args:
        filename (str): The filename of the PDF document.
        openai_api_key (str): The API key for OpenAI is not used in this function.
        config_obj (Config): The configuration object.
        video_file_path (str): The path to the video file associated with the PDF.

    Returns:
        str: The extracted text from the PDF or None if extraction fails.
    """
    file_path = Path(filename)
    submission_info = {'submission_id': None, 'offence_category': None}
    try:
        with fitz.open(file_path) as doc:
            text = "".join(page.get_text() for page in doc)
        submission_info = infer_submission_info_from_text_using_AI(text, openai_api_key, config_obj)
        return submission_info
    except Exception as e:
        raise


def extract_info_from_submission_pdf(config_obj, video_folder, openai_api_key, confirmation_pdf_filename):
    logging.info(f"Extracting submission info from PDF: {confirmation_pdf_filename}, please wait...")
    # Initialize submission_info with potential fields
    submission_info = {'submission_id': None, 'offence_category': None, 'incident_date': None, 'incident_time': None, 'incident_location': None}

    try:
        ai_inferred_info = stringify_pdf_and_infer_info(confirmation_pdf_filename, openai_api_key, config_obj, video_folder)
        # If AI inference was not successful, ai_inferred_info will be None or empty dict
        if not ai_inferred_info or not ai_inferred_info.get('submission_id'):
            raise ValueError("AI inference failed; falling back to manual input.")
        # Update submission_info with the AI-inferred details
        submission_info.update(ai_inferred_info)
        logging.debug(f"AI inferred submission info: {submission_info}")
    except Exception as e:
        logging.warning(f"Couldn't infer submission info due to: {e}.")
        # Prompt for manual input for each field
        for key in submission_info:
            prompt_text = f"Enter {key.replace('_', ' ')}: "
            submission_info[key] = input(prompt_text).strip() or None

    # Display the extracted information using logging before asking for confirmation
    logging.info("\nExtracted information:")
    for key, value in submission_info.items():
        logging.info(f"{key.replace('_', ' ').capitalize()}: {value if value else 'Not available'}")

    # Confirm all at once or individually as before
    confirm_all = input("\nIs all the above information correct? (Y/n): ").strip().lower()
    if confirm_all in ['', 'y']:
        return submission_info

    # If the user does not confirm all the information, allow them to correct each field
    for key in list(submission_info):  # Use list to copy keys because we might modify the dict in the loop
        current_value = submission_info[key] if submission_info[key] else 'Not available'
        user_input = input(f"\nIf the {key.replace('_', ' ')} '{current_value}' is correct, press ENTER. Otherwise, enter the correct value: ").strip()
        if user_input:
            submission_info[key] = user_input

    return submission_info
