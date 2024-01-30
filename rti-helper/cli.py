import argparse
from datetime import datetime
import logging
from pathlib import Path
from .exceptions import InvalidTimeError, ConfigError, CriticalError
from .config import load_config

def load_configuration():
    try:
        # Get the directory of the current file (cli.py)
        dir_path = Path(__file__).parent
        # Construct the path to config.yaml
        config_path = dir_path / "config.yaml"
        # Load the configuration from the constructed path
        return load_config(str(config_path))
    except ConfigError as e:
        raise ConfigError(f"Configuration loading failed: {e}")

def get_parsed_arguments():
    try:
        return setup_argument_parser()
    except (InvalidTimeError, FileNotFoundError) as e:
        logging.error(f"CLI argument parsing failed: {e}")
        raise CriticalError(f"CLI argument parsing failed: {e}")
    
def valid_time(s):
    """
    Validate the provided time string and convert it to seconds.

    Args:
        s (str): Time string to be validated.

    Returns:
        int: The number of seconds represented by the time string.

    Raises:
        InvalidTimeError: If the time string is not in a valid format.
    """
    formats = ['%H:%M:%S', '%M:%S']  # List of allowed time formats
    for time_format in formats:
        try:
            # If the datetime object is successfully created, the format is correct
            parsed_time = datetime.strptime(s, time_format)
            # Convert the time to seconds
            seconds = parsed_time.hour * 3600 + parsed_time.minute * 60 + parsed_time.second
            return seconds  # Return the number of seconds
        except ValueError:
            continue  # Try the next format

    # If none of the formats are correct, raise an error
    raise InvalidTimeError(f"\nInvalid time format: {s}. Expected formats: 'HH:MM:SS' or 'MM:SS'.")


def valid_file_path(path):
    """
    Check if the provided file path points to an existing file.

    Args:
        path (str): Path to the file to be validated.

    Returns:
        str: The original file path if it points to an existing file.

    Raises:
        FileNotFoundError: If the file at the provided path does not exist.
    """
    # Strip single quotes from the start and end of the path if present
    path = path.strip("'")

    file_path = Path(path)
    if not file_path.is_file():
        error_message = f"The file {path} does not exist."
        logging.error(error_message)
        logging.debug(f"Current working directory: {Path.cwd()}")
        logging.debug(f"Attempted file path: {file_path.resolve()}")
        logging.debug(f"Is the path absolute? {file_path.is_absolute()}")
        logging.debug(f"File path exists? {file_path.exists()}")
        logging.debug(f"File path is a file? {file_path.is_file()}")
        raise FileNotFoundError(error_message)
    return path

def setup_argument_parser():
    """
    Parse command-line arguments.

    Returns:
        Namespace: The parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(description="Process a video file with RTI-video.")
    parser.add_argument('--video', required=True, type=valid_file_path, help='Path to the video file.')
    parser.add_argument('--time', required=True, type=valid_time, help='Time point in the video to process (formats HH:MM:SS or MM:SS).')
    parser.add_argument('--VRN', required=False, help='Vehicle Registration Number (VRN)') # Unused at the moment


    args = parser.parse_args()
    return args