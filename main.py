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

# Sidebar: List saved files with playback, download and delete buttons
st.sidebar.header("Uploaded Files")

def list_uploaded_files():
    files = sorted(Path(UPLOAD_DIR).glob("*"), key=os.path.getmtime, reverse=True)
    file_list = []
    for file_path in files:
        file_list.append(str(file_path))
    return file_list

uploaded_files = list_uploaded_files()

for file_path_str in uploaded_files:
    file_path = Path(file_path_str)
    file_suffix = file_path.suffix.lower()
    
    st.sidebar.markdown(f"**{file_path.name}**")
    
    if file_suffix in [".mp4", ".mov", ".m4v"]:
        st.sidebar.video(str(file_path))
    elif file_suffix in [".mp3", ".wav", ".m4a", ".aac"]:
        st.sidebar.audio(str(file_path))
    else:
        st.sidebar.write("Unsupported file format for preview")

    st.sidebar.download_button("Download File", str(file_path), file_name=file_path.name)

    # Delete button
    if st.sidebar.button(f"Delete {file_path.name}", key=f"del_{file_path.name}"):
        try:
            os.remove(file_path)
            st.sidebar.success(f"Deleted {file_path.name}")
            st.experimental_rerun()  # Refresh to update file list after deletion
        except Exception as e:
            st.sidebar.error(f"Failed to delete {file_path.name}: {e}")

st.markdown("---")

uploaded_file = st.file_uploader(
    "Choose file",
    type=[
        "mp3", "wav", "m4a", "aac", "mp4", "mov", "m4v"
    ]
)

if uploaded_file:
    unique_name = f"{Path(uploaded_file.name).stem}_{int(os.path.getmtime('.'))}{Path(uploaded_file.name).suffix}"
    save_path = os.path.join(UPLOAD_DIR, unique_name)
    with open(save_path, "wb") as f:
        f.write(uploaded_file.read())

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
