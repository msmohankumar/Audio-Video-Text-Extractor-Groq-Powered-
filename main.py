import streamlit as st
import os
from pathlib import Path
from transcription import transcribe_audio_groq

st.set_page_config(page_title="🎤 Audio & Video Transcription", page_icon="🎙️", layout="centered")

st.title("🎤 Audio & Video Text Extractor (Groq Powered)")
st.markdown("""
Upload an audio file (mp3, wav) for instant transcription.

If you upload a video file (mp4, mov), audio extraction requires `ffmpeg`, which is not available in this environment.
Please extract audio externally and upload the audio file instead.
""")

uploaded_file = st.file_uploader("Choose file", type=["mp3", "wav", "mp4", "mov"])

if uploaded_file:
    os.makedirs("inputs", exist_ok=True)
    input_path = os.path.join("inputs", uploaded_file.name)
    with open(input_path, "wb") as f:
        f.write(uploaded_file.read())

    suffix = Path(input_path).suffix.lower()

    # Previews
    if suffix in [".mp4", ".mov"]:
        st.video(input_path)
        st.warning("Audio extraction from video requires `ffmpeg`, which is not installed. Please upload audio files directly.")
    elif suffix in [".mp3", ".wav"]:
        st.audio(input_path)

        # Transcribe audio directly
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
