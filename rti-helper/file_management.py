import logging
from pathlib import Path
import shutil
from .exceptions import FileManagementError
from .submission_ID_extraction import extract_info_from_submission_pdf


def check_and_create_subdirectory(path):
    """
    Ensures that the specified path exists as a directory.
    """
    if not isinstance(path, Path):
        path = Path(path)
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as e:  
        logging.error(f"Failed to create subdirectory {path}: {e}")
        raise FileManagementError(f"Failed to create subdirectory {path}")

def move_files(src_files, dst, stringify=False):
    """
    Moves a list of source files to the specified destination directory.
    If the destination directory does not exist, it will be created.
    If stringify is True, the source files will be converted to strings before moving.
    """
    if not isinstance(dst, Path):
        dst = Path(dst)
    check_and_create_subdirectory(dst)
    
    for src_file in src_files:
        if not isinstance(src_file, Path):
            src_file = Path(src_file)
        if stringify:
            src_file = str(src_file)
        try:
            # Use shutil instead of pathlib to ensure cross filessystem transfer, like from a usb stick
            shutil.move(str(src_file), dst / src_file.name) 
            logging.debug(f"Moved {src_file} to {dst}")
        except Exception as e:
            logging.error(f"Failed to move {src_file} to {dst}: {e}")
            raise FileManagementError(f"Failed to move {src_file} to {dst}: {e}")

def find_latest_file(directory, file_extension):
    """
    Finds the latest (most recently modified) file in a directory with the given file extension.
    """
    if not isinstance(directory, Path):
        directory = Path(directory)
    try:
        files = list(directory.glob(f'*.{file_extension}'))
        if not files:
            return None
        latest_file = max(files, key=lambda x: x.stat().st_mtime)
        return latest_file
    except Exception as e:
        logging.error(f"Failed to find latest file with extension {file_extension} in {directory}: {e}")
        raise FileManagementError(f"Failed to find latest file with extension {file_extension} in {directory}: {e}")


def rename_files_with_vrn(created_files, actual_vrn):
    """
    Renames the video and frame capture files in created_files with the actual VRN and deletes the audio file.
    """
    new_filenames = []
    # Filter out only the frame capture files and sort them to maintain order
    frame_captures = sorted((f for f in created_files if f.suffix == '.jpg'), key=lambda f: f.stem)
    frame_capture_index = 1  # Initialize a counter for frame capture files

    for temp_filename in created_files:
        if not isinstance(temp_filename, Path):
            temp_filename = Path(temp_filename)

        if temp_filename.suffix == '.mp4':
            # Rename video file with the actual VRN
            new_filename = temp_filename.with_name(f"{actual_vrn}{temp_filename.suffix}")
        elif temp_filename.suffix == '.jpg':
            # Rename frame capture files with the actual VRN and an index
            new_filename = temp_filename.with_name(f"{actual_vrn}_frame_{frame_capture_index}{temp_filename.suffix}")
            frame_capture_index += 1
        elif temp_filename.suffix in ['.wav', '.mp3', '.aac']:
            # Delete audio files
            try:
                temp_filename.unlink()
                logging.debug(f"Deleted audio file {temp_filename}")
                continue  # Skip to the next file
            except OSError as e:
                logging.error(f"An error occurred while deleting audio file {temp_filename}: {e}")
                raise FileManagementError(f"An error occurred while deleting audio file {temp_filename}: {e}")
        else:
            # If the file is not a video, frame capture, or audio, just keep the filename as is
            new_filenames.append(temp_filename)
            continue  # Skip to the next file

        # Attempt to rename the file
        try:
            temp_filename.rename(new_filename)
            logging.debug(f"Renamed file {temp_filename} to {new_filename}")
            new_filenames.append(new_filename)
        except OSError as e:
            logging.error(f"An error occurred while renaming file {temp_filename} to {new_filename}: {e}")
            raise FileManagementError(f"An error occurred while renaming file {temp_filename} to {new_filename}: {e}")

    return new_filenames
    
def get_confirmation_pdf_filename(config_obj):
    """
    Selects the latest PDF file as the submission file from police.
    Prompts the user for confirmation if the config setting `confirm_pdf_selection` is True.
    """
    download_dir = config_obj.download_dir
    if not isinstance(download_dir, Path):
        download_dir = Path(download_dir)
    pdf_files = list(download_dir.glob("*.pdf"))
    if not pdf_files:
        raise FileNotFoundError("No PDF found in the download directory.")
    latest_pdf = max(pdf_files, key=lambda p: p.stat().st_mtime)

    # Check if the configuration requires user confirmation
    if config_obj.confirm_pdf_selection:
        print(f"PDF found: {latest_pdf.name}")
        confirmation = input("Is this the correct submission file from police? (Y/n): ").strip().lower()
        if confirmation not in ['', 'y', 'yes']:
            raise FileNotFoundError("The user indicated that the latest PDF is not the confirmation file.")
    else:
        logging.info(f"Automatically selected the latest PDF as the submission file: {latest_pdf.name}")

    return latest_pdf