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

ffmpeg_installed = check_ffmpeg()

st.markdown("""
Upload an audio file (mp3, wav) for instant transcription.

If you upload a video file (mp4, mov), audio extraction requires `ffmpeg`.
""")

if not ffmpeg_installed:
    st.warning("⚠️ ffmpeg is NOT installed or not accessible. Audio extraction from video files will not work. Please upload audio files directly.")

uploaded_file = st.file_uploader("Choose file", type=["mp3", "wav", "mp4", "mov"])

if uploaded_file:
    os.makedirs("inputs", exist_ok=True)
    input_path = os.path.join("inputs", uploaded_file.name)
    with open(input_path, "wb") as f:
        f.write(uploaded_file.read())

    suffix = Path(input_path).suffix.lower()

    if suffix in [".mp4", ".mov"]:
        st.video(input_path)
        if not ffmpeg_installed:
            st.warning("Audio extraction from video requires `ffmpeg`, which is not available. Please upload audio files directly.")
        else:
            st.info("ffmpeg detected. You can implement audio extraction here if desired.")

    elif suffix in [".mp3", ".wav"]:
        st.audio(input_path)
        with st.spinner("Transcribing audio with Groq API..."):
            try:
                transcript = transcribe_audio_groq(input_path)
                if transcript:
                    st.success("Transcription complete!")
                    st.text_area("📄 Extracted Text:", transcript, height=300)
                    st.download_button("Download Transcript as TXT", transcript,
                                       file_name=f"{Path(uploaded_file.name).stem}_transcript.txt")
                else:
                    st.warning("No transcription returned.")
            except Exception as e:
                st.error(f"Transcription failed: {e}")
    else:
        st.error("Unsupported file type. Please upload mp3, wav, mp4, or mov files.")
