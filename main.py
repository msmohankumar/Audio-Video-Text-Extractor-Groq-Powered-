import streamlit as st
import os
from pathlib import Path
from transcription import transcribe_audio_groq
import subprocess

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

st.set_page_config(page_title="🎤 Audio & Video Text Extractor", page_icon="🎙️", layout="wide")
st.title("🎤 Audio & Video Text Extractor (Groq Powered)")

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
        "-vn",
        "-acodec", "pcm_s16le",
        "-ac", "1",
        "-ar", "16000",
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

# Sidebar: files saved with "Use for Transcription" buttons
st.sidebar.header("Saved Files (Click to Use)")

def list_uploaded_files():
    files = sorted(Path(UPLOAD_DIR).glob("*"), key=os.path.getmtime, reverse=True)
    return [file_path for file_path in files]

uploaded_files = list_uploaded_files()

for file_path in uploaded_files:
    st.sidebar.write(f"**{file_path.name}**")
    if st.sidebar.button(f"Use {file_path.name} for Transcription", key=f"use_{file_path.name}"):
        with open(file_path, "rb") as f:
            file_bytes = f.read()
        st.session_state["selected_file"] = {
            "name": file_path.name,
            "data": file_bytes
        }
        st.experimental_rerun()

st.markdown("---")

# File uploader with drag and drop support
uploaded_file = st.file_uploader(
    "Drag & drop or click to upload file",
    type=["mp3", "wav", "m4a", "aac", "mp4", "mov", "m4v"],
    key="file_uploader",
)

# Use session_state file if sidebar selected
if "selected_file" in st.session_state and st.session_state["selected_file"] is not None:
    name = st.session_state["selected_file"]["name"]
    data = st.session_state["selected_file"]["data"]
    file_like = st.session_state["selected_file"]
    file_obj = st.file_uploader(
        "Processing selected file...",
        type=["mp3", "wav", "m4a", "aac", "mp4", "mov", "m4v"],
        key="selected_file_uploader",
        disabled=True,
        accept_multiple_files=False
    )
    # Hack: Use hidden streamer because file_uploader doesn't accept bytes directly
    uploaded_file = st.session_state["selected_file"]

if uploaded_file is not None:
    # Save uploaded or selected file to disk
    if isinstance(uploaded_file, dict):
        name = uploaded_file["name"]
        data = uploaded_file["data"]
        save_path = os.path.join(UPLOAD_DIR, name)
        with open(save_path, "wb") as f:
            f.write(data)
    else:
        name = uploaded_file.name
        save_path = os.path.join(UPLOAD_DIR, name)
        with open(save_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

    suffix = Path(save_path).suffix.lower()

    try:
        if suffix in [".mp4", ".mov", ".m4v"]:
            st.video(save_path)
            if ffmpeg_installed:
                st.info("Extracting audio from video...")
                audio_path = extract_audio_from_video(save_path)
                st.audio(audio_path)

                with st.spinner("Transcribing extracted audio..."):
                    transcript = transcribe_audio_groq(audio_path)
                    if transcript:
                        st.success("Transcription complete!")
                        st.text_area("📄 Extracted Text:", transcript, height=300)
                        st.download_button("Download Transcript as TXT", transcript,
                                           file_name=f"{Path(save_path).stem}_transcript.txt")
                    else:
                        st.warning("No transcription returned.")
            else:
                st.warning("Audio extraction requires ffmpeg which is not available. Please upload audio files directly.")

        elif suffix in [".mp3", ".wav", ".m4a", ".aac"]:
            st.audio(save_path)
            with st.spinner("Transcribing audio with Groq API..."):
                transcript = transcribe_audio_groq(save_path)
                if transcript:
                    st.success("Transcription complete!")
                    st.text_area("📄 Extracted Text:", transcript, height=300)
                    st.download_button("Download Transcript as TXT", transcript,
                                       file_name=f"{Path(save_path).stem}_transcript.txt")
                else:
                    st.warning("No transcription returned.")
        else:
            st.error("Unsupported file type. Please upload a supported audio or video file.")
    except Exception as e:
        st.error(f"Error during processing: {e}")
