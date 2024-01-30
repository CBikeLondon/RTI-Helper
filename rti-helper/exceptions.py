class InvalidTimeError(Exception):
    """Exception raised for errors in the input time format."""

class MissingEnvironmentVariableError(Exception):
    """Exception raised if an expected environment variable is missing."""

class FFmpegVideoTrimError(Exception):
    """Exception raised when video trimming fails."""

class FFmpegAudioTrimError(Exception):
    """Exception raised when audio trimming fails."""

class VideoProcessingError(Exception):
    """Exception raised for errors during video processing."""

class ConfigError(Exception):
    """Exception raised for errors in the configuration."""

class FileOpenError(Exception):
    """Exception raised when a PDF file cannot be opened."""

class CriticalError(Exception):
    """Exception raised for critical errors that require immediate attention."""

class FileManagementError(Exception):
    """Exception raised for errors that occur during file management operations."""

class UserAbortException(Exception):
    """Exception raised when the user decides to abort the process."""