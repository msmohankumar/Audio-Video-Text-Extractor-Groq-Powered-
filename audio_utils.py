import ffmpeg
import os

def extract_audio_if_video(video_path):
    audio_path = os.path.splitext(video_path)[0] + ".wav"
    try:
        # Extract audio with mono channel, 16kHz sample rate wav
        ffmpeg.input(video_path).output(audio_path, format='wav', ac=1, ar='16000').run(overwrite_output=True, quiet=True)
        return audio_path
    except ffmpeg.Error:
        # If extraction fails, assume input is audio and return original path
        return video_path
