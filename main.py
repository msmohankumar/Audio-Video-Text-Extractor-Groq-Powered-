import streamlit as st
import os
from pathlib import Path
from transcription import transcribe_audio_groq
import subprocess
import tempfile

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

MAX_UPLOAD_SIZE_MB = 10
MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024

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

def compress_audio(input_path, output_path):
    command = [
        "ffmpeg", "-y", "-i", input_path,
        "-vn",
        "-b:a", "64k",
        "-ar", "16000",
        output_path
    ]
    process = subprocess.run(command, capture_output=True, text=True)
    if process.returncode != 0:
        raise RuntimeError(f"Audio compression failed: {process.stderr}")

def compress_video(input_path, output_path):
    command = [
        "ffmpeg", "-y", "-i", input_path,
        "-vcodec", "libx264",
        "-crf", "28",
        "-preset", "fast",
        "-acodec", "aac",
        "-b:a", "96k",
        output_path
    ]
    process = subprocess.run(command, capture_output=True, text=True)
    if process.returncode != 0:
        raise RuntimeError(f"Video compression failed: {process.stderr}")

def convert_audio(input_path, target_format):
    suffix = "." + target_format
    output_fd, output_path = tempfile.mkstemp(suffix=suffix)
    os.close(output_fd)
    if target_format == "mp3":
        command = [
            "ffmpeg", "-y", "-i", input_path,
            "-vn",
            "-ab", "192k",
            "-ar", "44100",
            output_path
        ]
    elif target_format == "wav":
        command = [
            "ffmpeg", "-y", "-i", input_path,
            "-vn",
            "-acodec", "pcm_s16le",
            "-ac", "1",
            "-ar", "16000",
            output_path
        ]
    else:
        raise ValueError(f"Unsupported audio format: {target_format}")

    process = subprocess.run(command, capture_output=True, text=True)
    if process.returncode != 0:
        os.remove(output_path)
        raise RuntimeError(f"Audio conversion to {target_format} failed: {process.stderr}")
    return output_path

def convert_video(input_path, target_format):
    suffix = "." + target_format
    output_fd, output_path = tempfile.mkstemp(suffix=suffix)
    os.close(output_fd)
    command = [
        "ffmpeg", "-y", "-i", input_path,
        "-c:v", "copy",
        "-c:a", "aac",
        output_path
    ]
    process = subprocess.run(command, capture_output=True, text=True)
    if process.returncode != 0:
        os.remove(output_path)
        raise RuntimeError(f"Video conversion to {target_format} failed: {process.stderr}")
    return output_path

ffmpeg_installed = check_ffmpeg()

st.markdown("""
Upload an audio or video file for transcription.

If ffmpeg is available, audio will be extracted automatically from videos for transcription.
""")

if not ffmpeg_installed:
    st.warning("⚠️ ffmpeg is NOT installed or not accessible. Audio extraction from video files will not work. Please upload audio files directly.")

st.sidebar.header("Uploaded Files")

def list_uploaded_files():
    files = sorted(Path(UPLOAD_DIR).glob("*"), key=os.path.getmtime, reverse=True)
    return [file_path for file_path in files]

uploaded_files = list_uploaded_files()

for file_path in uploaded_files:
    st.sidebar.markdown(f"**{file_path.name}**")
    suffix = file_path.suffix.lower()

    if suffix in [".mp4", ".mov", ".m4v"]:
        st.sidebar.video(str(file_path))
        format_options = ["mp4", "mov"]
    elif suffix in [".mp3", ".wav", ".m4a", ".aac"]:
        st.sidebar.audio(str(file_path))
        format_options = ["mp3", "wav"]
    else:
        st.sidebar.write("Unsupported file format for preview")
        format_options = []

    if format_options:
        chosen_format = st.sidebar.selectbox(
            "Select download format",
            options=format_options,
            index=format_options.index(suffix[1:]) if suffix[1:] in format_options else 0,
            key=f"format_{file_path.name}"
        )

        try:
            if chosen_format in ["mp3", "wav"]:
                converted_file = convert_audio(str(file_path), chosen_format)
            elif chosen_format in ["mp4", "mov"]:
                converted_file = convert_video(str(file_path), chosen_format)
            else:
                converted_file = str(file_path)

            with open(converted_file, "rb") as f:
                mime_type = "audio/mpeg" if chosen_format in ["mp3", "wav"] else "video/mp4"
                st.sidebar.download_button(
                    label=f"Download as {chosen_format.upper()}",
                    data=f,
                    file_name=f"{file_path.stem}.{chosen_format}",
                    mime=mime_type
                )
            os.remove(converted_file)
        except Exception as e:
            st.sidebar.error(f"Conversion error: {e}")

    if st.sidebar.button(f"Delete {file_path.name}", key=f"del_{file_path.name}"):
        try:
            os.remove(file_path)
            st.sidebar.success(f"Deleted {file_path.name}")
            try:
                st.experimental_rerun()
            except AttributeError:
                import os
                os._exit(00)
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
    initial_size = uploaded_file.size
    suffix = Path(uploaded_file.name).suffix.lower()

    if initial_size > MAX_UPLOAD_SIZE_BYTES and ffmpeg_installed:
        # Temporarily save uploaded file
        temp_input_path = os.path.join(UPLOAD_DIR, "temp_upload" + suffix)
        with open(temp_input_path, "wb") as f:
            f.write(uploaded_file.read())

        compressed_filename = f"{Path(uploaded_file.name).stem}_compressed{suffix}"
        save_path = os.path.join(UPLOAD_DIR, compressed_filename)

        try:
            if suffix in [".mp3", ".wav", ".m4a", ".aac"]:
                compress_audio(temp_input_path, save_path)
            elif suffix in [".mp4", ".mov", ".m4v"]:
                compress_video(temp_input_path, save_path)
            else:
                st.error("Unsupported file type for compression.")
                save_path = temp_input_path

            compressed_size = os.path.getsize(save_path)
            if compressed_size > MAX_UPLOAD_SIZE_BYTES:
                st.warning(f"File is still larger than {MAX_UPLOAD_SIZE_MB} MB after compression ({compressed_size / (1024*1024):.2f} MB). Consider using a smaller file.")
        except Exception as e:
            st.error(f"Compression failed: {e}")
            save_path = temp_input_path

        if temp_input_path != save_path and os.path.exists(temp_input_path):
            os.remove(temp_input_path)

    else:
        save_path = os.path.join(UPLOAD_DIR, uploaded_file.name)
        with open(save_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

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
