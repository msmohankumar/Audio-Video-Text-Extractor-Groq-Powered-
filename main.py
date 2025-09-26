import streamlit as st
import os
from pathlib import Path
from transcription import transcribe_audio_groq
import subprocess

st.set_page_config(page_title="🎤 Audio & Video Transcription", page_icon="🎙️", layout="centered")

st.title("🎤 Audio & Video Text Extractor (Groq Powered)")

# Check if ffmpeg exists in environment
def check_ffmpeg():
    try:
        result = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
        return result.returncode == 0
    except Exception:
        return False

def extract_audio_from_video(video_path):
    audio_path = os.path.splitext(video_path)[0] + "_extracted.wav"
    command = [
        "ffmpeg",
        "-y",
        "-i", video_path,
        "-vn",            # no video
        "-acodec", "pcm_s16le",  # wav format
        "-ac", "1",            # mono channel
        "-ar", "16000",        # 16 kHz sample rate
        audio_path
    ]
    process = subprocess.run(command, capture_output=True, text=True)
    if process.returncode != 0:
        raise RuntimeError(f"ffmpeg audio extraction failed: {process.stderr}")
    return audio_path

ffmpeg_installed = check_ffmpeg()

st.markdown("""
Upload an audio or video file for transcription.

If ffmpeg is available, audio will be extracted automatically from videos for transcription.
""")

if not ffmpeg_installed:
    st.warning("⚠️ ffmpeg is NOT installed or not accessible. Audio extraction from video files will not work. Please upload audio files directly.")

# Extend to common audio/video formats from iPhone and others
uploaded_file = st.file_uploader(
    "Choose file",
    type=[
        # Audio formats
        "mp3", "wav", "m4a", "aac",
        # Video formats
        "mp4", "mov", "m4v"
    ]
)

if uploaded_file:
    os.makedirs("inputs", exist_ok=True)
    input_path = os.path.join("inputs", uploaded_file.name)
    with open(input_path, "wb") as f:
        f.write(uploaded_file.read())

    suffix = Path(input_path).suffix.lower()

    try:
        if suffix in [".mp4", ".mov", ".m4v"]:
            st.video(input_path)
            if ffmpeg_installed:
                st.info("Extracting audio from video...")
                audio_path = extract_audio_from_video(input_path)
                st.audio(audio_path)

                with st.spinner("Transcribing extracted audio..."):
                    transcript = transcribe_audio_groq(audio_path)
                    if transcript:
                        st.success("Transcription complete!")
                        st.text_area("📄 Extracted Text:", transcript, height=300)
                        st.download_button("Download Transcript as TXT", transcript,
                                           file_name=f"{Path(uploaded_file.name).stem}_transcript.txt")
                    else:
                        st.warning("No transcription returned.")
            else:
                st.warning("Audio extraction requires ffmpeg which is not available. Please upload audio files directly.")

        elif suffix in [".mp3", ".wav", ".m4a", ".aac"]:
            st.audio(input_path)
            with st.spinner("Transcribing audio with Groq API..."):
                transcript = transcribe_audio_groq(input_path)
                if transcript:
                    st.success("Transcription complete!")
                    st.text_area("📄 Extracted Text:", transcript, height=300)
                    st.download_button("Download Transcript as TXT", transcript,
                                       file_name=f"{Path(uploaded_file.name).stem}_transcript.txt")
                else:
                    st.warning("No transcription returned.")
        else:
            st.error("Unsupported file type. Please upload a supported audio or video file.")
    except Exception as e:
        st.error(f"Error during processing: {e}")
