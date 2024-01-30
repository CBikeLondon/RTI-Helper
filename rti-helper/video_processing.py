import ffmpeg
import logging
import uuid
from datetime import timedelta, datetime
from pathlib import Path
from .exceptions import FFmpegVideoTrimError, FFmpegAudioTrimError, VideoProcessingError, FileManagementError

def initialize_video_processing(args, config_obj):
    return VideoProcessor()

class VideoProcessor:
    def __init__(self):
        # Generate a unique UUID for each instance of VideoProcessor
        self.temp_uuid = uuid.uuid4().hex
        self.created_files = []  # Track created files


    @staticmethod
    def get_video_info(video_path):
        try:
            # Use ffmpeg.probe to get metadata of the video file
            video_info = ffmpeg.probe(str(video_path))
            # Extract duration and frame rate from the video metadata
            duration = float(video_info['format']['duration'])
            video_streams = [stream for stream in video_info['streams'] if stream['codec_type'] == 'video']
            frame_rate_str = video_streams[0]['r_frame_rate']
            num, den = map(int, frame_rate_str.split('/'))
            frame_rate = num / den
            return duration, frame_rate
        except ffmpeg.Error as e:
            raise VideoProcessingError(f"Failed to get video info: {e}")
        
    @staticmethod
    def is_timestamp_valid(timestamp, video_duration):
        """ 
        Check if the timestamp is within the valid range of the video's duration.
        A timestamp is considered valid if it is greater than or equal to 0 (the start of the video)
        and less than or equal to the video's total duration.
        This prevents referencing a point in time that does not exist in the video.
        """
        return 0 <= timestamp <= video_duration
    
    @staticmethod
    def format_seconds_to_hhmmss(seconds):
        """
        Convert seconds to a formatted string in HH:MM:SS or MM:SS format.
        If the hours are zero, they are not included in the format.

        Args:
            seconds (int): The number of seconds.

        Returns:
            str: The formatted time string.
        """
        # Create a time object starting at midnight
        formatted_time = (datetime.min + timedelta(seconds=seconds)).time()
        # Format as HH:MM:SS or MM:SS depending on the hour
        if formatted_time.hour > 0:
            return formatted_time.strftime("%H:%M:%S")
        else:
            return formatted_time.strftime("%M:%S")

    def validate_frame_capture_interval(self, frame_rate, frame_capture_interval):
        min_interval = 1 / frame_rate
        if frame_capture_interval < min_interval:
            # Adjust to the nearest multiple of the minimum interval that is greater than the requested interval
            adjusted_interval = (int(frame_capture_interval / min_interval) + 1) * min_interval
            logging.warning(f"Frame capture interval {frame_capture_interval} is too short for the video frame rate. Adjusting to {adjusted_interval}.")
            return adjusted_interval
        return frame_capture_interval
    
    def prepare_frame_capture_timestamps(self, timestamp, video_duration, num_frame_captures, interval):
        """
        Prepare timestamps for frame capture based on the original timestamp, video duration,
        number of frame captures, and the interval between frame captures.

        For an even number of captures, the primary timestamp will be centered between two frames.
        For an odd number of captures, the primary timestamp will be the center of the captures.

        Args:
            timestamp (float): The original timestamp for the frame capture.
            video_duration (float): The total duration of the video.
            num_frame_captures (int): The number of frame captures to capture.
            interval (float): The interval between frame captures, already validated.

        Returns:
            list: A list of timestamps for frame capture.
        """
        timestamps = []
        half_count = num_frame_captures // 2

        # Calculate the start timestamp differently for even and odd numbers of captures
        if num_frame_captures % 2 == 0:
            # For even number of captures, offset the start timestamp so the primary timestamp is centered between two captures
            start_timestamp = timestamp - (interval * (half_count - 0.5))
        else:
            # For odd number of captures, the primary timestamp is the center
            start_timestamp = timestamp - (interval * half_count)

        # Generate timestamps
        for i in range(num_frame_captures):
            current_timestamp = start_timestamp + (i * interval)
            if self.is_timestamp_valid(current_timestamp, video_duration):
                timestamps.append(current_timestamp)

        # Remove duplicates and sort
        timestamps = sorted(list(set(timestamps)))

        return timestamps

    def create_frame_captures(self, timestamps, video_path):
        if not video_path or not Path(video_path).is_file():
            raise VideoProcessingError(f"Invalid video path: {video_path}")
        
        # Generate the frame_captures
        for i, ts in enumerate(timestamps, start=1):
            frame_capture_filename = Path(video_path).parent / f"{self.temp_uuid}_{i}.jpg"
            frame_capture_filename_str = str(frame_capture_filename)  # ffmpeg need Path to Str
            try:
                # Execute FFmpeg command to take a frame_capture
                (
                    ffmpeg
                    .input(video_path, ss=ts)
                    .output(frame_capture_filename_str, vframes=1) 
                    .global_args('-v', 'quiet')
                    .overwrite_output()
                    .run()
                )
                logging.debug(f"Frame capture saved at {frame_capture_filename_str} for timestamp {ts}")
                self.created_files.append(frame_capture_filename)  # Track the created file in case of cleanup
            except ffmpeg.Error as e:
                error_message = f"An error occurred while saving the frame capture at {frame_capture_filename_str} for timestamp {ts}: {e.stderr.decode().strip()}"
                logging.error(error_message)
                raise FileManagementError(error_message) from e

        # Log the creation of frame captures after all captures have been created
        logging.info(f"{len(timestamps)} frame captures created.")
                
    def calculate_time_offsets(self, timestamp, video_duration, start_offset_seconds, end_offset_seconds, start_audio_offset_seconds, end_audio_offset_seconds):
        # Calculate the start and end times for video trimming
        video_start_time = max(0, timestamp - start_offset_seconds)  # Ensure start time is not negative
        video_end_time = min(timestamp + end_offset_seconds, video_duration)  # Ensure end time does not exceed video duration
        
        # Calculate the start and end times for audio trimming
        audio_start_time = max(0, timestamp - start_audio_offset_seconds)  # Ensure start time is not negative
        audio_end_time = min(timestamp + end_audio_offset_seconds, video_duration)  # Ensure end time does not exceed video duration
        
        return video_start_time, video_end_time, audio_start_time, audio_end_time

    def build_file_paths(self,video_path):
        # Construct temporary file paths for the trimmed video and audio files
        output_dir = Path(video_path).parent  # Use the same directory as the source video
        trimmed_video_filename = output_dir / f"{Path(video_path).stem}_{self.temp_uuid}_trim.mp4"  # Name for trimmed video file
        trimmed_audio_filename = output_dir / f"{Path(video_path).stem}_{self.temp_uuid}_trim_audio.wav"  # Name for trimmed audio file
        return trimmed_video_filename, trimmed_audio_filename

    def run_ffmpeg_trim_video(self, video_path, video_start_time, video_end_time, trimmed_video_filename, short_edge_resolution, trim_only):
        # Get video information to determine if scaling is needed
        video_info = ffmpeg.probe(video_path)
        video_stream = next((stream for stream in video_info['streams'] if stream['codec_type'] == 'video'), None)
        width = int(video_stream['width'])
        height = int(video_stream['height'])
        
        logging.info(f"Original video resolution: width={width}, height={height}")
        # Determine the short edge and calculate the scaling factor while maintaining aspect ratio
        scale_filter = ''
        if min(width, height) > short_edge_resolution:
            if width > height:
                scale = f'scale=-2:{short_edge_resolution}'
                logging.debug(f"Applying scale filter for width: {scale}")
            else:
                scale = f'scale={short_edge_resolution}:-2'
                logging.debug(f"Applying scale filter: {scale}")
            scale_filter = scale

        # Update the logging statement to include trimming details
        trim_details = f"Trimming video from {self.format_seconds_to_hhmmss(video_start_time)} to {self.format_seconds_to_hhmmss(video_end_time)}"
        if not trim_only:
            trim_details += f" and applying scaling to maintain a short edge resolution of {short_edge_resolution} pixels."
        else:
            trim_details += ", without re-encoding (copy mode)."
        logging.info(trim_details + " Please wait...")
        
        try:
            logging.debug(f"FFmpeg command will run with the following scale filter: {scale_filter}")
            # Configure FFmpeg command for trimming and potentially scaling the video
            ffmpeg_command = (
                ffmpeg
                .input(video_path, ss=video_start_time, to=video_end_time)
            )

            if not trim_only:
                # Apply encoding options if not trim_only
                ffmpeg_command = ffmpeg_command.output(
                    str(trimmed_video_filename),
                    vf=scale_filter if scale_filter else None,
                    vcodec='libx264',
                    crf=23,
                    acodec='aac'
                )
            else:
                # Apply codec copy to avoid re-encoding
                ffmpeg_command = ffmpeg_command.output(
                    str(trimmed_video_filename),
                    vcodec='copy',
                    acodec='copy'
                )

            ffmpeg_command = ffmpeg_command.global_args('-v', 'quiet').overwrite_output().run()  
            logging.debug("finished ffmpeg instance")
            self.created_files.append(trimmed_video_filename)
        except ffmpeg.Error as e:
            error_message = f"FFmpeg video trimming error: {e.stderr.decode().strip()}"
            logging.error(error_message)
            raise FFmpegVideoTrimError(error_message) from e
        except Exception as e:
            logging.error(f"An unexpected error occurred during video trimming: {e}")
            raise
        finally:
            logging.debug("Exiting run_ffmpeg_trim_video method.")

    def run_ffmpeg_trim_audio(self, video_path, audio_start_time, audio_end_time, trimmed_audio_filename):
        try:
            # Configure FFmpeg command for extracting and trimming the audio
            ffmpeg_audio = (
                ffmpeg
                .input(video_path, ss=audio_start_time, to=audio_end_time)
                .output(str(trimmed_audio_filename), vn=None, acodec='pcm_s16le')
                .overwrite_output()
            )
            ffmpeg_audio.run()
            logging.debug(f"Trimmed audio saved at {trimmed_audio_filename}")
            self.created_files.append(trimmed_audio_filename)
        except ffmpeg.Error as e:
            error_message = f"FFmpeg audio trimming error: {e.stderr.decode().strip()}"
            logging.error(error_message)
            raise FileManagementError(error_message) from e
    
    def get_file_duration_and_size(self, file_path):
        try:
            file_info = ffmpeg.probe(str(file_path))
            duration_seconds = float(file_info['format']['duration'])
            
            duration_formatted = self.format_seconds_to_hhmmss(duration_seconds)

            file_size_bytes = Path(file_path).stat().st_size
            file_size_mb = round(file_size_bytes / (1024 * 1024), 2)  # Convert to MB and round to two decimal places

            return duration_formatted, file_size_mb
        except ffmpeg.Error as e:
            raise VideoProcessingError(f"Failed to get file info: {e}")
        
    def trim_video(self, video_path, timestamp, video_duration, config_obj):
        """
        Trim the video and audio using the calculated time offsets.

        Args:
            video_path (str): The path to the video file.
            timestamp (float): The timestamp at which to trim the video and audio.
            video_duration (float): The duration of the video.
            config_obj: The configuration object with necessary settings.

        Returns:
            A tuple containing the trimmed video duration in microseconds,
            and the filenames for the trimmed video and audio files.
        """
        # Extract necessary values from config_obj
        start_offset_seconds = config_obj.start_offset_seconds
        end_offset_seconds = config_obj.end_offset_seconds
        start_audio_offset_seconds = config_obj.start_audio_offset_seconds
        end_audio_offset_seconds = config_obj.end_audio_offset_seconds
        short_edge_resolution = config_obj.short_edge_resolution
        trim_only = config_obj.trim_only

        # Use the extracted values in the method calls
        video_start_time, video_end_time, audio_start_time, audio_end_time = self.calculate_time_offsets(
            timestamp, video_duration, start_offset_seconds, end_offset_seconds, start_audio_offset_seconds, end_audio_offset_seconds
        )

        # Build file paths for the trimmed video and audio files
        trimmed_video_filename, trimmed_audio_filename = self.build_file_paths(video_path)

        # Trim the video and audio using the calculated time offsets
        self.run_ffmpeg_trim_video(video_path, video_start_time, video_end_time, trimmed_video_filename, short_edge_resolution, trim_only)
        self.run_ffmpeg_trim_audio(video_path, audio_start_time, audio_end_time, trimmed_audio_filename)

        # Calculate the trimmed video duration in microseconds
        trimmed_duration_ms = (video_end_time - video_start_time) * 1000000
        return trimmed_duration_ms, trimmed_video_filename, trimmed_audio_filename


    def process_video(self, video_path, timestamp, config_obj):
        """
        Processes a video file by generating frame captures at defined intervals and trimming the video and audio at a specified timestamp.

        Parameters:
            video_path (str): Path to the video file to be processed.
            timestamp (float): Point in the video at which the trimming should commence.
            config_obj (object): Configuration object with settings required for video processing.

        Returns:
            tuple: Contains the file paths for the trimmed video and audio.

        Raises:
            VideoProcessingError: Raised if there's an issue during the video processing phase.
        """
        logging.info(f"Starting video processing for file: {video_path} with incident time @ {self.format_seconds_to_hhmmss(timestamp)}")
        video_duration, frame_rate = self.get_video_info(video_path)  # Assuming get_video_info returns a tuple (duration, frame_rate)
        if not self.is_timestamp_valid(timestamp, video_duration):
            raise VideoProcessingError(f"Invalid timestamp: {self.format_seconds_to_hhmmss(timestamp)} for video duration: {self.format_seconds_to_hhmmss(video_duration)}")

        # Validate and possibly adjust the frame capture interval
        validated_interval = self.validate_frame_capture_interval(frame_rate, config_obj.frame_capture_interval)
        
        # Use the validated interval to prepare frame capture timestamps
        timestamps = self.prepare_frame_capture_timestamps(
            timestamp, video_duration, config_obj.frame_capture_count, validated_interval
        )           
        logging.debug(f"Preprocessed timestamps for frame capture: {timestamps}")

        # Create frame captures for the preprocessed timestamps
        self.create_frame_captures(timestamps, video_path)
        logging.debug(f"Frame captures created for timestamps: {timestamps}")

        # Trim the video and audio based on the timestamp and configuration object
        trimmed_duration_ms, trimmed_video_filename, trimmed_audio_filename = self.trim_video(
            video_path, timestamp, video_duration, config_obj
        )

        logging.info(f"Trimmed video created successfully.")
        video_duration, video_size_mb = self.get_file_duration_and_size(trimmed_video_filename)
        audio_duration, audio_size_mb = self.get_file_duration_and_size(trimmed_audio_filename)
        
        logging.debug(f"Video file: {trimmed_video_filename}")
        logging.debug(f"Video Duration: {video_duration}")
        logging.debug(f"Video Filesize: {video_size_mb} MB")
        logging.debug(f"Audio file: {trimmed_audio_filename}")
        logging.debug(f"Audio Duration: {audio_duration}")
        logging.debug(f"Audio Filesize: {audio_size_mb} MB")
        logging.debug(f"Location in: {Path(video_path).parent}")

        return trimmed_video_filename, trimmed_audio_filename

