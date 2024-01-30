import logging
import yaml
from .video_processing import VideoProcessor

def cleanup(directory, created_files, prompt_user=False):
    """
    Cleans up the specified files in the given directory.

    Args:
        directory (Path): The directory containing the files to clean up.
        created_files (list): List of files that were created and are safe to delete.
        prompt_user (bool): If True, prompts the user before deleting files.
    """
    for temp_filename in created_files:
        if not temp_filename.exists() or temp_filename.parent != directory:
            continue  # Skip files that do not exist or are not in the specified directory
        if prompt_user:
            user_input = input(f"Do you want to delete {temp_filename}? [Y/n] ").strip().lower()
            if user_input not in ['', 'y', 'yes']:
                continue
        try:
            temp_filename.unlink()
            logging.info(f"Deleted file {temp_filename}")
        except OSError as e:
            logging.error(f"An error occurred while deleting file {temp_filename}: {e}")

  
def generate_cheat_sheet(args, actual_vrn, video_processor, video_folder, vehicle_details):
    # Helper function to fetch details with a default value if not found or if vehicle_details is None
    def get_vehicle_detail(key, default='Not available'):
        if vehicle_details is not None:
            return vehicle_details.get(key, default)
        return default

    # Construct a dictionary with the cheat sheet content
    cheat_sheet_content = {
        "Manual Submission Cheat Sheet": {
            "Essential Information": {
                "Submission ID": "Not available - Will be provided after submission",
                "NIP": "Pending",
            },
            "Vehicle Details": {
                "VRN": actual_vrn,
                "Make": get_vehicle_detail('make'),
                "Colour": get_vehicle_detail('colour'),
                "Type": get_vehicle_detail('typeApproval'),
                "Tax Status": get_vehicle_detail('taxStatus'),
                "MOT status": get_vehicle_detail('motStatus'),
            },
            "Incident Details": {
                "Date": "Not available - Will be provided after submission",
                "Time": "Not available - Will be provided after submission",
                "Location": "Not available - Will be provided after submission",
                "Offence Category": "Not available - Will be provided after submission",
            }
        }
    }

    # Define the filename for the cheat sheet
    cheat_sheet_filename = video_folder / f"{actual_vrn}_cheat_sheet_yaml.txt"

    # Write the cheat sheet content to a YAML file
    with open(cheat_sheet_filename, 'w') as file:
        yaml.dump(cheat_sheet_content, file, default_flow_style=False, sort_keys=False)

    logging.info(f"Cheat sheet saved to {cheat_sheet_filename}")

    # Add the cheat sheet to the list of created files so it can be used in cleanup if necessary
    video_processor.created_files.append(cheat_sheet_filename)

    return cheat_sheet_filename


def update_cheat_sheet_with_submission_details(cheat_sheet_filename, submission_details):
    """
    Updates the cheat sheet with submission details including submission ID, offence category,
    incident date, time, and location. Adjusted to match the new structure.
    """
    # Load the existing cheat sheet content
    with open(cheat_sheet_filename, 'r') as file:
        cheat_sheet_content = yaml.safe_load(file)

    # Update the Essential Information section with the Submission ID
    essential_info_section = cheat_sheet_content['Manual Submission Cheat Sheet']['Essential Information']
    essential_info_section['Submission ID'] = submission_details.get('submission_id', 'Not available')

    # Update the Incident Details section with the provided submission details
    incident_details_section = cheat_sheet_content['Manual Submission Cheat Sheet']['Incident Details']
    incident_details_section.update({
        "Date": submission_details.get('incident_date', 'Not available'),
        "Time": submission_details.get('incident_time', 'Not available'),
        "Location": submission_details.get('incident_location', 'Not available'),
        "Offence Category": submission_details.get('offence_category', 'Not available'),
    })

    # Write the updated content back to the YAML file
    with open(cheat_sheet_filename, 'w') as file:
        yaml.dump(cheat_sheet_content, file, default_flow_style=False, sort_keys=False)

    logging.info(f"Cheat sheet updated with submission details in {cheat_sheet_filename}")