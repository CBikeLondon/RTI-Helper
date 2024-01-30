from dotenv import load_dotenv
from pathlib import Path
import logging

def get_api_keys(config_obj):
    """
    Retrieves required API keys from environment variables or prompts the user for them.
    If the keys are not found and use_APIs is true, it prompts the user for input.

    Args:
        config_obj (Config): The configuration object which includes use_APIs setting.

    Returns:
        dict: Containing the values of the required API keys or an empty dict if not found or not required.
    """

    load_dotenv()
    api_keys = {}
    env_path = Path('.env')
    env_vars = env_path.read_text().splitlines() if env_path.exists() else []

    if config_obj.use_APIs:
        required_keys = ['OPENAI_API_KEY', 'DVLA_API_KEY']
        for key in required_keys:
            # Check if the key exists in the .env file
            key_value = next((line.split(f"{key}=")[1].strip() for line in env_vars if line.startswith(f"{key}=")), None)
            
            # Prompt the user for the key if it's not found
            if not key_value:
                key_value = input(f"(Optional) Enter your {key}: ").strip()
                if key_value:
                    # Write the provided key to the .env file
                    with env_path.open("a") as env_file:
                        env_file.write(f"{key}={key_value}\n")
                    api_keys[key] = key_value
                else:
                    logging.warning(f"{key} is missing. Some features will require manual input.")
            else:
                api_keys[key] = key_value

    # Return the api_keys dictionary regardless of whether it's empty or not
    return api_keys