import shutil
import sys
from pkg_resources import parse_version
import pkg_resources
from pathlib import Path
from .exceptions import CriticalError

def check_virtual_environment():
    """
    Checks if the script is running inside a virtual environment.
    Raises CriticalError if not running in a venv.
    """
    if not (getattr(sys, 'base_prefix', None) != sys.prefix or hasattr(sys, 'real_prefix')):
        raise CriticalError("This script is not running in a virtual environment. Please activate a virtual environment and try again.")

def check_requirements():
    """
    Checks if all packages listed in requirements.txt are installed.
    Raises CriticalError if a package is not installed.
    """
    # Construct the absolute path to the requirements.txt file
    script_dir = Path(__file__).resolve().parent  # Directory of the current script
    requirements_path = script_dir.parent / 'requirements.txt'  # Path to requirements.txt

    if not requirements_path.exists():
        raise CriticalError(f"Requirements file not found: {requirements_path}")

    with requirements_path.open('r') as f:
        required_packages = f.readlines()

    required_packages = [line.strip() for line in required_packages if line.strip() and not line.startswith('#')]
    required_packages = {pkg.split('>=')[0].lower(): pkg.split('>=')[1] for pkg in required_packages if '>=' in pkg}

    installed_packages = {pkg.key.lower(): pkg.version for pkg in pkg_resources.working_set}
    missing_packages = []
    for pkg, required_version in required_packages.items():
        installed_version = installed_packages.get(pkg)
        if installed_version is None or parse_version(installed_version) < parse_version(required_version):
            missing_packages.append(f"{pkg} (required: >= {required_version}, installed: {installed_version if installed_version else 'none'})")

    if missing_packages:
        missing = ', '.join(missing_packages)
        raise CriticalError(f"The following packages are required but not installed or do not meet the version requirement: {missing}. Please install them and try again.")
    
def check_ffmpeg_availability():
    ffmpeg_path = shutil.which('ffmpeg')
    if ffmpeg_path is None:
        raise CriticalError("FFmpeg is required but not installed. Please install FFmpeg and try again.")