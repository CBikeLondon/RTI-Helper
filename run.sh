#!/usr/bin/env bash

# Constants
ALLOW_ROOT=false
DEBUG=0 # Define DEBUG variable (set to 1 to enable debug mode, 0 to disable)
export PYTHONUNBUFFERED=1  # Disable buffering for Python output
set -e # Exit immediately if a command exits with a non-zero status.
env_file=".env"
if [[ -f "$env_file" ]]; then
    set -a # Automatically export all variables
    source "$env_file"
    set +a # Disable auto-export
fi

# Define a delimiter for nicer output
delimiter="=================================================="

export PIP_IGNORE_INSTALLED=0 # Do not reinstall existing pip packages on Debian/Ubuntu
required_apps=(git ffmpeg) # List of required commands

# Redirect output for troubleshooting with timestamps
#exec > >(tee -a application.log | while IFS= read -r line; do printf "[$(date '+%Y-%m-%d %H:%M:%S')] $line"; done) 2>&1

# Function to print a message with delimiter
print_message() {
    local message=$1
    local type=$2

    if [[ "$type" == "error" ]]; then
        printf "\n%s\n\033[1;31m%s\033[0m\n%s\n" "${delimiter}" "${message}" "${delimiter}"
    elif [[ "$type" == "success" ]]; then
        printf "\033[1;32m%s\033[0m\n" "${message}"
    elif [[ "$type" == "welcome" ]]; then
        printf "\n%s\n\033[1;32m\033[1m%s\033[0m\n%s\n" "${delimiter}" "${message}" "${delimiter}"  # Changed to green and bold for welcome message
    else
        printf "\n%s\n%s\n%s\n" "${delimiter}" "${message}" "${delimiter}"
    fi
}

# Check if running on Windows and refuse to run if so for safety
if [[ "$(uname -s)" == MINGW* ]] || [[ "$(uname -s)" == CYGWIN* ]] || [[ "$(uname -s)" == MSYS* ]]; then
    print_message "This script cannot be run on Windows. Please use install.bat instead." "error"
    exit 1
fi

# Function to handle reset logic
handle_reset() {
    local confirmation
    while true; do
        print_message "Are you sure you want to reset the configuration to default values and erase local API key storage?" "error"
        read -p "This action cannot be undone. [Y/N]: " confirmation </dev/tty
        if [[ $confirmation =~ ^[Yy]$ ]]; then
            # Copy the contents of defaults.yaml into config.yaml
            if cp rti-helper/_defaults.yaml rti-helper/config.yaml; then
                print_message "Configuration has been reset to default values." "success"
            else
                print_message "Failed to reset configuration to default values." "error"
                exit 1
            fi
            break
        elif [[ $confirmation =~ ^[Nn]$ ]]; then
            print_message "Reset cancelled by user." "info"
            exit 0
        else
            print_message "Invalid input. Please enter 'Y' for yes or 'N' for no." "error"
        fi
    done

        # Remove the venv folder
        if [[ -d "venv" ]]; then
            rm -rf venv
            print_message "Virtual environment removed." "success"
        fi

        # Remove .env
        if [[ -f ".env" ]]; then
            rm -f .env
            print_message "Local API key storage removed." "success"
        fi

        # Remove .installed
        if [[ -f ".installed" ]]; then
            rm -f .installed
            print_message ".installed file removed." "success"
        fi

        # Restart script
        print_message "Config reset to defaults. Exiting, please run the script again." "info"
        sleep 2
        exit 0
}

configure_yaml() {
    local yaml_file="rti-helper/config.yaml"
    local temp_yaml_file="${yaml_file}.tmp"
    local key existing_value new_value comment

    # Ensure the temporary YAML file is empty before starting
    > "${temp_yaml_file}"

    # Backup the current config file
    if ! cp "${yaml_file}" "${yaml_file}.bak"; then
        print_message "Failed to back up the current config file." "error"
        return 1
    fi

    declare -A written_keys

    # Read each setting from the YAML file and prompt the user for a new value or use the existing
    while IFS= read -r line || [[ -n "$line" ]]; do
        # Check if the line is a comment or empty and just echo it to the temp file
        if [[ "$line" =~ ^[[:space:]]*# ]] || [[ -z "$line" ]]; then
            echo "$line" >> "${temp_yaml_file}"
            continue
        fi

        # Extract the key, existing value, and comment from the line
        IFS=":" read -r key value_and_comment <<< "$line"
        existing_value=$(echo "$value_and_comment" | cut -d'#' -f1 | xargs)
        comment=$(echo "$value_and_comment" | grep -o '#.*' || echo '')

        # Skip if the key has already been written to prevent duplicates
        if [[ -n "${written_keys[$key]}" ]]; then
            echo "Duplicate key '${key}' detected. Skipping."
            continue
        fi

        # Prompt the user for a new value, showing the existing value
        read -p "Put a new value for ${key} or confirm with ENTER [${existing_value}]: " new_value </dev/tty
        # Strip leading/trailing whitespace from the user input
        new_value=$(echo "$new_value" | xargs)

        # If the user did not provide a new value, use the existing value
        if [[ -z "$new_value" ]]; then
            new_value="$existing_value"
        else
            # Remove any pre-existing single or double quotes from the user input
            new_value="${new_value%\'*}"
            new_value="${new_value%\"*}"
            new_value="${new_value#\'}"
            new_value="${new_value#\"}"

            # Escape special characters if necessary and add single quotes
            if [[ "$new_value" =~ [[:space:]] || "$new_value" =~ [[:punct:]] && ! "$new_value" =~ ^[[:alnum:]/_+-]+$ ]]; then
                # Escape special characters significant in YAML
                new_value=$(echo "$new_value" | sed 's/[\&]/\\&/g')
                new_value="'$new_value'"
            fi
        fi

        # Mark the key as written
        written_keys[$key]=1

        # Write the new or existing value to the temporary YAML file, preserving comments
        if [[ -n "$comment" ]]; then
            echo "${key}: ${new_value} ${comment}" >> "${temp_yaml_file}"
        else
            echo "${key}: ${new_value}" >> "${temp_yaml_file}"
        fi
    done < "${yaml_file}"

    # Replace the old YAML file with the new one
    if ! mv -f "${temp_yaml_file}" "${yaml_file}"; then
        print_message "Failed to update the config file with new settings." "error"
        return 1
    fi
    print_message "Updated the config file with new settings." "success"
}

# Function to display current configuration values
display_current_config() {
    local yaml_file="rti-helper/config.yaml"
    printf "\nCurrent configuration values:\n"
    while IFS= read -r line || [[ -n "$line" ]]; do
        if [[ ! "$line" =~ ^[[:space:]]*# ]] && [[ -n "$line" ]]; then
            printf "%s\n" "$line"
        fi
    done < "${yaml_file}"
    printf "\n"
}

# Function to ask user if they want to change configuration values
ask_to_change_config() {
    local change_config
    read -p "Would you like to change any configuration values? [Y/N]: " change_config </dev/tty
    if [[ $change_config =~ ^[Yy]$ ]]; then
        return 0  # User wants to change configuration
    elif [[ $change_config =~ ^[Nn]$ ]]; then
        return 1  # User does not want to change configuration
    else
        print_message "Invalid input. Please enter 'Y' for yes or 'N' for no." "error"
        ask_to_change_config  # Ask again
    fi
}

# Modify the check_installation function to use the new functions
check_installation() {
    local config_required=false

    echo "Checking installation requirements..."
    
    # Check if the script is running for the first time
    if [[ ! -f ".installed" ]]; then
        print_message "Running for the first time, launching configuration..." "info"
        sleep 1
        config_required=true
    fi

    # If the --config flag is used or it's the first run, display current config
    if [[ "$1" == "--config" ]] || [[ "$config_required" == true ]]; then
        print_message "Current configuration:" "info"
        display_current_config
        # Ask the user if they want to change the configuration
        if ask_to_change_config; then
            configure_yaml
        fi
    fi

    # If it's the first run, create the .installed file
    if [[ "$config_required" == true ]] && [[ ! -f ".installed" ]]; then
        touch .installed  # Create the sentinel file after successful installation
    fi
}


sed_in_place() {
    local sed_script=$1
    local file=$2

    if [[ "$(uname)" == "Darwin" ]]; then
        sed -i '' "$sed_script" "$file"
    else
        sed -i "$sed_script" "$file"
    fi
}



# Function to display help message
show_help() {
    printf "Usage: %s [OPTIONS]\n" "$0"
    printf "Install the application and its dependencies.\n\n"
    printf "Options:\n"
    printf "  -h, --help       Show this help message and exit.\n"
    printf "  -v, --verbose    Run the script in verbose mode.\n"
    printf "      --allow-root Allow the script to run as the root user.\n"
    printf "      --reset      Reset the configuration to default values and erase local API key storage.\n\n"
}


# Parse script arguments
for arg in "$@"; do
    case "$arg" in
        -h|--help)
            show_help
            exit 0
            ;;
        -v|--verbose)
            DEBUG=1
            ;;
        --allow-root)
            ALLOW_ROOT=true
            ;;
        --config)
            check_installation "$arg"
            ;;
        --reset)
            handle_reset
            ;;
        *)
            # Handle other unknown options
            show_help
            exit 0
            ;;
    esac
done

# After the argument parsing loop
if [[ ! -f ".installed" ]]; then
    check_installation
fi

# Function to print a status message followed by 'Done' upon success
print_status_done() {
    local message=$1
    printf "%s... " "${message}"
}


# Function to check for command existence
command_exists() {
    type "$1" &> /dev/null
}

# Function to find the best matching Python command
find_python_command() {
    local python_cmds=('python3' 'python' 'python3.8' 'python3.9' 'python3.10' 'python3.11')
    local min_version="3.8"
    local python_cmd=""
    local python_version=""

    for cmd in "${python_cmds[@]}"; do
        if command_exists "$cmd"; then
            python_version=$($cmd -c 'import sys; print(".".join(map(str, sys.version_info[:3])))')
            if [[ $(printf '%s\n' "$min_version" "$python_version" | sort -V | head -n1) == "$min_version" ]]; then
                # Ensure the command is not pointing to Python 2
                if [[ $($cmd -c 'import sys; print(sys.version_info[0])') -eq 3 ]]; then
                    python_cmd="$cmd"
                    break
                fi
            fi
        fi
    done

    if [[ -z "$python_cmd" ]]; then
        print_message "Python 3.8+ not found. Please install Python 3.8+ and try again." "error"
        exit 1
    fi

    printf "%s\n" "$python_cmd"
}

ensure_pip() {
    local python_cmd=$1
    print_status_done "Ensuring pip is installed and up to date"
    
    # Ensure pip is installed and up to date
    if [[ $DEBUG -eq 1 ]]; then
        $python_cmd -m pip install --upgrade pip && print_message "Done" "success" || {
            print_message "Failed to upgrade pip" "error"; exit 1;
        }
    else
        $python_cmd -m pip install --upgrade pip > /dev/null 2>&1 && print_message "Done" "success" || {
            print_message "Failed to upgrade pip" "error"; exit 1;
        }
    fi
}

ensure_venv_module() {
    local python_cmd=$1
    if ! "${python_cmd}" -c "import venv" &> /dev/null; then
        print_message "ERROR: python3-venv is not installed, aborting..." "error"
        exit 1
    fi
}

# Function to check for the existence of required commands
check_required_apps() {
    local missing_apps=()
    for cmd in "$@"; do
        if ! command_exists "$cmd"; then
            missing_apps+=("$cmd")
        fi
    done

    if [ ${#missing_apps[@]} -ne 0 ]; then
        for cmd in "${missing_apps[@]}"; do
            print_message "ERROR: $cmd is not installed. Please install $cmd and try again." "error"
        done
        exit 1
    fi
}




# Check if the script is running as root and if root is not allowed
if [[ $(id -u) -eq 0 && $ALLOW_ROOT != true ]]; then
    print_message "ERROR: This script must not be launched as root without the --allow-root argument, aborting..." "error"
    exit 1
else
    print_message "Running locally" "info"
fi

# Check if required commands are installed
check_required_apps "${required_apps[@]}"

# Execute ffmpeg with a command that completes immediately
ffmpeg -loglevel quiet -version > /dev/null 2>&1

# Find the best matching Python command
PYTHON_CMD=$(find_python_command)


# Check for pip corresponding to the found Python command
PIP_CMD="${PYTHON_CMD} -m pip"

# Ensure venv module exists
ensure_venv_module $PYTHON_CMD || { print_message "ERROR: python3-venv is not installed, aborting..." "error"; exit 1; } 

# Check for Python virtual environment and create one if it doesn't exist
if [[ ! -d "venv" ]]; then
    print_status_done "Creating a new Python virtual environment"
    
    # Check if the .env file exists, if not, create it
    if [[ ! -f "$env_file" ]]; then
        touch "$env_file"
        chmod 600 "$env_file"
    fi

    $PYTHON_CMD -m venv venv && print_message "Done" "success" || { print_message "Failed to create virtual environment" "error"; exit 1; }
   
    
else
    print_message "Existing virtual environment found." "info"
fi

# Activate the virtual environment or ensure it's already activated
activate_virtual_environment() {
    if [[ -z "$VIRTUAL_ENV" ]]; then
        if [[ ! -f "venv/bin/activate" ]]; then
            print_message "Virtual environment activation script not found" "error"
            exit 1
        fi

        printf "Activating the virtual environment..."
        source venv/bin/activate
        if [[ "$(realpath $(which python))" != "$(realpath $(pwd)/venv/bin/python)" ]]; then
            print_message "Failed to activate virtual environment correctly" "error"
            exit 1
        fi
        printf "\e[1;32mDone\e[0m\n"
    else
        print_message "Virtual environment already active." "success"
    fi
}



# Activate the virtual environment or ensure it's already activated
activate_virtual_environment

# After activation, set PIP_CMD to the pip executable within the virtual environment
PIP_CMD="$(which pip)"

# Ensure pip is installed and up to date
ensure_pip $PYTHON_CMD

# Only display Python and Pip paths if DEBUG is set to 1
if [[ $DEBUG -eq 1 ]]; then
    printf "Python path: %s\n" "$(which python)"
    printf "Pip path: %s\n" "$(which pip)"
fi

# Install dependencies with pip
print_status_done "Checking dependencies from requirements.txt"


# Install dependencies
if [[ $DEBUG -eq 1 ]]; then
    $PIP_CMD install --no-cache-dir -r requirements.txt && print_message "Done" "success" || { print_message "Failed to install dependencies" "error"; exit 1; }
else
    $PIP_CMD install --no-cache-dir -r requirements.txt > /dev/null 2>&1 && print_message "Done" "success" || { print_message "Failed to install dependencies" "error"; exit 1; }
fi
sleep 1

# Debug: List contents of requirements.txt before installing
if [[ $DEBUG -eq 1 ]]; then
    printf "Contents of requirements.txt:\n"
    cat requirements.txt
fi

# Debug: Check if the required packages are installed by listing them
if [[ $DEBUG -eq 1 ]]; then
    printf "Verifying installed packages with pip list:"
    $PIP_CMD list
    sleep 1

    # Extract package names from requirements.txt and check each one
    while IFS= read -r package || [[ -n "$package" ]]; do
        # Use a regular expression to extract the package name before any version specifier
        package_name=$(echo "$package" | grep -oE '^[a-zA-Z0-9_-]+')
        if ! $PIP_CMD list | grep -qw "$package_name"; then
            print_message "Package $package_name is not installed." "error"
            sleep 1
            exit 1
        else
            print_message "Package $package_name is installed." "success"
        fi
    done < requirements.txt
fi

# Function to run the main application with video path and time
run_application() {
    local video_path=$1
    local video_time=$2

    # Run the Python command without redirecting output
    $PYTHON_CMD -u -m rti-helper.main --video "$video_path" --time "$video_time"

    local exit_code=$?

    if [ $exit_code -ne 0 ]; then
        if [ $exit_code -eq 1 ]; then
            print_message "The application encountered an error during execution." "error"
        else
            print_message "The application failed to start with the provided arguments." "error"
        fi
        exit 1
    fi
}



prompt_for_arguments() {
    print_message "Launching Road Traffic Incident helper tool" "welcome"
    sleep 1

    local video_path
    local video_time
    local valid_time_regex='^([0-9]{1,2}:)?[0-5][0-9]:[0-5][0-9]$' # Regex for HH:MM:SS or MM:SS

    # Prompt for the video path with a multi-line message and do not accept a blank entry
    while true; do
        printf "### Enter below the path to the source video file ###\nHint: Drag and drop the video file into this terminal.\n" "info"
        read -p "Path: " video_path
        if [[ -z "$video_path" ]]; then
            print_message "The video path cannot be empty. Please enter a valid path." "error"
        else
            break
        fi
    done

    # Loop until the user enters a valid time
    while true; do
        read -p "Enter the time point in the video (HH:MM:SS or MM:SS): " video_time
        if [[ $video_time =~ $valid_time_regex ]]; then
            break # Valid time format, exit the loop
        else
            print_message "Invalid time format: $video_time. Expected formats: 'HH:MM:SS' or 'MM:SS'." "error"
        fi
    done
    
    # Call run_application function with the provided arguments
    run_application "$video_path" "$video_time"
}

# Prompt the user for the required arguments
prompt_for_arguments || { print_message "Failed to run the application." "error"; exit 1; }