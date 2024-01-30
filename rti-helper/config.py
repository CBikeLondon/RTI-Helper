import yaml
import sys
import logging
from pathlib import Path
from .exceptions import ConfigError  

class Config:
    def __init__(self, config_dict):
        missing_parameters = []
        self.download_dir = Path(config_dict.get('download_dir')).expanduser()
        self.submission_dir = Path(config_dict.get('submission_dir')).expanduser()
        self.start_offset_seconds = config_dict.get('start_offset_seconds')
        self.end_offset_seconds = config_dict.get('end_offset_seconds')
        self.start_audio_offset_seconds = config_dict.get('start_audio_offset_seconds')
        self.end_audio_offset_seconds = config_dict.get('end_audio_offset_seconds')
        self.openai_model = config_dict.get('openai_model')
        self.audio_model = config_dict.get('audio_model')
        self.max_attempts = config_dict.get('max_attempts')
        self.initial_temperature = config_dict.get('initial_temperature')
        self.increased_temperature = config_dict.get('increased_temperature')
        self.frame_capture_count = config_dict.get('frame_capture_count')
        self.frame_capture_interval = config_dict.get('frame_capture_interval')
        self.short_edge_resolution = config_dict.get('short_edge_resolution') 
        self.confirm_pdf_selection = config_dict.get('confirm_pdf_selection')
        self.trim_only = config_dict.get('trim_only')  
        self.use_APIs = config_dict.get('use_APIs')  

        # Check for None values which indicate missing parameters
        for attribute in self.__dict__:
            if getattr(self, attribute) is None:
                missing_parameters.append(attribute)
        
        if missing_parameters:
            raise ConfigError(f"Missing configuration parameters: {', '.join(missing_parameters)}")


def load_config(config_path):
    """Load configuration from a YAML file."""

    try:
        with open(config_path, 'r') as stream:
            config = yaml.safe_load(stream)
            config_obj = Config(config)
            return config_obj
    except ConfigError as exc:
        logging.error(f"Configuration error: {exc}")
        offer_configuration_reset(config_path)
    except yaml.YAMLError as exc:
        raise ConfigError(f"Failed to parse configuration file: {exc}")
    except FileNotFoundError:
        raise ConfigError(f"Configuration file not found: {config_path}")
    except Exception as exc:
        raise ConfigError(f"An unexpected error occurred while loading configuration: {exc}")

def offer_configuration_reset(config_path):
    user_input = input("Would you like to reset the configuration to default? [Y/N]: ")
    if user_input.lower() == 'y':
        backup_current_config(config_path)  # Backup before resetting
        reset_config_to_default(config_path)
        logging.info("Configuration has been reset. Please run the application again to configure.")
        sys.exit(0)
    else:
        logging.error("Please manually fix the configuration parameters and try again.")
        sys.exit(1)

def backup_current_config(config_path):

    backup_path = Path(config_path).with_suffix(".bak")
    try:
        Path(config_path).replace(backup_path)
        logging.info(f"Current configuration backed up to {backup_path}")
    except Exception as exc:
        logging.error(f"Failed to backup current configuration: {exc}")


def reset_config_to_default(config_path):
    """Reset configuration to default values."""
    try:
        # Assuming the default configuration is stored in '_defaults.yaml'
        default_config_path = Path(config_path).parent / '_defaults.yaml'
        if default_config_path.exists():
            default_config_path.replace(config_path)
            logging.info("Configuration reset to default values.")
        else:
            logging.error("Default configuration file not found.")
    except Exception as exc:
        logging.error(f"Failed to reset configuration: {exc}")


# Example usage:
# config_obj = load_config("path/to/config.yaml")