# Road Traffic Incident Reporting Helper

This Python utility is a valuable tool designed to streamline the process of reporting road traffic incidents to the police. It automates the preparation of video evidence for submission, saving users time and reducing the likelihood of errors. The utility takes a source video file, an incident timestamp, and a third-party vehicle registration number as inputs, and performs several tasks to assist in creating a concise and clear report for law enforcement review.

## Overview

The utility addresses the common need to report road incidents with video evidence from devices like helmet cameras or dashcams. It simplifies the reporting process by performing the following tasks:

- **Video Trimming**: Trims the video to desired length before and after the incident timestamp
- **Frame Captures**: Generates screenshots from the video at the specified timestamp for additional visual evidence
- **File Renaming**: Renames the generated files for easy identification and management.
- **File Archiving**: Moves the video, screenshots, and confirmation PDF to an archive folder after the online reporting form is completed.

## Functionality

- The utility is a command-line script that leverages [FFmpeg](https://github.com/FFmpeg/FFmpeg) for video processing
- It includes helper functions for tasks such as locating the latest file of a given type, extracting submission codes from filenames, directory management, file moving, and argument validation.


## Requirements

To run this utility, your system needs to meet the following requirements:

- **Python**: Version 3.8 or higher. Download it from [Python's official website](https://www.python.org/downloads/).
- **git**: Version control system required for cloning the repository.
    - For Linux, follow the instructions [here](https://git-scm.com/download/linux).
    - For Windows, download it from [this link](https://git-scm.com/download/win).
    - For MacOSX, instructions are available [here](https://git-scm.com/download/mac).
- **OpenAI API key**: Necessary for certain features. Obtain one from [OpenAI's platform](https://platform.openai.com/api-keys).

## Installation

Follow these steps to install the utility:

1. Clone the repository:
   ```bash
   git clone https://github.com/CBikeLondon/RTI-Helper.git
   ```

2. Run the script for your operating system:
   - **MacOSX and Linux**:
     ```bash
     ./run.sh
     ```
   - **Windows (not yet implemented) **:
     ```bash
     ./run.bat
     ```


## Pipeline
- Extract timestamp from GoPro or other cameras
- Extract GPS if available
- simple local web app graphical user interface for accessible user experience
- AI user agent that will complete the form on a police force website all the way up to but not including the confirmation and signing stage.

## Contributions

Contributions to this project are very welcome. If you have a feature request, bug report, or want to contribute code, please feel free to open an issue or submit a pull request.

## License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details.
