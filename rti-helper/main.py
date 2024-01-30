import logging
import sys, time
from pathlib import Path  
from .cli import get_parsed_arguments, load_configuration
from .openai_utils import get_audio_transcript, extract_or_request_VRN
from .submission_ID_extraction import extract_info_from_submission_pdf
from .file_management import move_files, rename_files_with_vrn, get_confirmation_pdf_filename
from .credentials import get_api_keys
from .system_checks import check_ffmpeg_availability, check_requirements, check_virtual_environment
from .video_processing import initialize_video_processing
from .utils import cleanup, generate_cheat_sheet, update_cheat_sheet_with_submission_details
from .dvla_utils import get_vehicle_details_from_dvla
from .exceptions import (
    FFmpegVideoTrimError,
    FFmpegAudioTrimError,
    VideoProcessingError,
    UserAbortException,
    CriticalError,
    ConfigError
)

def main():
    video_folder = None  # Initialize video_folder to ensure it's in the local scope
    video_processor = None  # Initialize video_processor as well
    try:
        check_virtual_environment()  # Ensure the script is running in a virtual environment
        check_requirements()  # Check if all required packages are installed

        config_obj = load_configuration()  # Load the configuration from the config.yaml
        args = get_parsed_arguments()  # Parse the command-line arguments provided by the user

        
        use_apis = config_obj.use_APIs
        openai_api_key = None
        dvla_api_key = None

        if use_apis:
            api_keys = get_api_keys(config_obj)
            openai_api_key = api_keys.get('OPENAI_API_KEY')
            dvla_api_key = api_keys.get('DVLA_API_KEY')

        video_folder = Path(args.video).parent  # Get the folder of the video file

        check_ffmpeg_availability()  # Ensure FFmpeg is available in the system

        # Process the source video, create trimmed video
        video_processor = initialize_video_processing(args, config_obj)
        trimmed_video_filename, trimmed_audio_filename = trim_video(args, video_processor, config_obj, video_folder)
        logging.debug("Transcode Complete")

        # Attempt to obtain an audio transcript for VRN extraction if OpenAI API key is provided
        if openai_api_key:
            transcript = get_audio_transcript(trimmed_audio_filename, openai_api_key, config_obj)
            logging.debug("Transcripting process complete")
            actual_vrn = extract_or_request_VRN(transcript, openai_api_key, config_obj)
        else:
            actual_vrn = extract_or_request_VRN(None, None, config_obj)

        video_processor.created_files = rename_files_with_vrn(video_processor.created_files, actual_vrn)
        
        # Call to get vehicle details from DVLA, if applicable
        if use_apis and dvla_api_key and actual_vrn:
            logging.info(f"Contacting DVLA for information, please wait...")
            time.sleep(0.5)
            vehicle_details = get_vehicle_details_from_dvla(actual_vrn, dvla_api_key, config_obj)
            if vehicle_details:
                logging.debug(f"Vehicle details retrieved: {vehicle_details}")
            else:
                logging.warning("Failed to retrieve vehicle details from DVLA.")
        if not use_apis:
            logging.info("Skipping DVLA data retrieval as API usage is disabled in configuration.")
        elif not dvla_api_key:
            logging.info("Skipping DVLA data retrieval due to missing DVLA API key.")

        # Generate Cheat Sheet
        cheat_sheet_filename = generate_cheat_sheet(args, actual_vrn, video_processor, video_folder, vehicle_details if 'vehicle_details' in locals() else None)

        # Manual submission step
        handle_manual_submission(config_obj, video_folder, video_processor.created_files, actual_vrn)

        # Find the latest PDF in download_dir
        confirmation_pdf_filename = get_confirmation_pdf_filename(config_obj)

        # Add the confirmation PDF to the list of created files to be moved
        confirmation_pdf_path = Path(config_obj.download_dir) / confirmation_pdf_filename
        if confirmation_pdf_path.exists():
            video_processor.created_files.append(confirmation_pdf_path)

        # Extract submission info from the confirmation PDF
        submission_info = extract_info_from_submission_pdf(config_obj, video_folder, openai_api_key, confirmation_pdf_filename)
        submission_id = submission_info.get('submission_id')

        # After obtaining submission_info dictionary
        update_cheat_sheet_with_submission_details(cheat_sheet_filename, submission_info)

        # Move files to archive, submission_dir
        move_files(video_processor.created_files, config_obj.submission_dir / submission_id)  # Archive the files
        logging.info(f"Files moved to {config_obj.submission_dir / submission_id}")
        time.sleep(1)
        logging.info("Process complete. Hope this saved you time. Please give feedback to @CBikeLondon for improvements.")
    except CriticalError as e:
        logging.error(f"Critical error: {e}")
        sys.exit(1)
    except ConfigError as e:
        logging.error(f"Configuration error: {e}")
        sys.exit(1)
    except UserAbortException as e:
        logging.warning(f"User aborted the process: {e}")
        if video_processor:
            cleanup(video_folder, video_processor.created_files, prompt_user=True)
        sys.exit(1)
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        if video_processor:
            cleanup(video_folder, video_processor.created_files, prompt_user=True)
        sys.exit(1)


def trim_video(args, video_processor, config_obj, video_folder):
    try:
        trimmed_video_filename, trimmed_audio_filename = video_processor.process_video(video_path=args.video, timestamp=args.time, config_obj=config_obj)
        return trimmed_video_filename, trimmed_audio_filename
    except (VideoProcessingError, FFmpegVideoTrimError, FFmpegAudioTrimError) as e:
        logging.error(f"Video trimming failed: {e}")
        cleanup(video_folder, video_processor.created_files, prompt_user=True)
        raise

def handle_manual_submission(config_obj, video_folder, created_files, actual_vrn):
    while True:
        time.sleep(1)
        user_input = input(f"\nFILES ARE READY!\n"
                           f"==============================================================\n"
                           f"Please manually submit the files to the relevant police force.\n"
                           f"==============================================================\n"
                           f"\nUse the VRN: {actual_vrn}\n"
                           f"Once you have submitted the police form,\n"
                           f"download the confirmation pdf into your folder:\n"
                           f"{config_obj.download_dir} \n"
                           f"==================================================\n"
                           f"Ready to continue? Type 'yes', or 'abort': ").lower().strip().replace("'", "")
        if user_input in ['abort', 'cancel']:
            logging.warning("Submission process aborted by the user. Proceeding to cleanup.")
            time.sleep(2)
            cleanup(video_folder, created_files, prompt_user=True)
            raise UserAbortException("User aborted the submission process.")
        elif user_input in ['y', 'yes']:
            break
        else:
            print("Invalid input. Please type 'y', 'yes' to continue or 'abort' to cancel.")

if __name__ == "__main__":
    if not Path('logs').exists():
        Path('logs').mkdir(parents=True, exist_ok=True)
    # Set up logging format
    log_format = '%(asctime)s - %(levelname)s - %(message)s'

    # Set up file handler with DEBUG level for all logs
    file_handler = logging.FileHandler("logs/debug.log")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(log_format))

    # Set up stream handler with INFO level for general output
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(logging.Formatter(log_format))

    # Get the root logger and set its level to DEBUG
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(stream_handler)

    # Configure openai logger to only output WARNING and above to the console
    openai_logger = logging.getLogger("openai")
    openai_logger.setLevel(logging.DEBUG)  # Set the openai logger level to DEBUG for the file handler
    openai_stream_handler = logging.StreamHandler()
    openai_stream_handler.setLevel(logging.WARNING)
    openai_stream_handler.setFormatter(logging.Formatter(log_format))
    openai_logger.addHandler(openai_stream_handler)
    openai_logger.addHandler(file_handler)  
    httpx_logger = logging.getLogger("httpx")
    httpx_logger.setLevel(logging.WARNING)
    openai_logger.propagate = False  # Prevents the openai logs from being handled by the root logger's handlers

    main()
