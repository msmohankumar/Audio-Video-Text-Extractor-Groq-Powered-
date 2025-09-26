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
        raise RuntimeError(f"ffmpeg audio extraction failed: {process.stderr.decode()}")
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
        raise RuntimeError(f"Audio compression failed: {process.stderr.decode()}")

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
        raise RuntimeError(f"Video compression failed: {process.stderr.decode()}")

def get_media_duration(input_path):
    # ffprobe returns duration in seconds
    command = [
        "ffprobe", "-v", "error", "-show_entries",
        "format=duration", "-of",
        "default=noprint_wrappers=1:nokey=1", input_path
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe error: {result.stderr.decode()}")
    return float(result.stdout.strip())

def split_media(input_path, max_chunk_bytes=MAX_UPLOAD_SIZE_BYTES):
    file_size = os.path.getsize(input_path)
    duration = get_media_duration(input_path)

    num_chunks = max(1, int(file_size / max_chunk_bytes) + 1)
    chunk_duration = duration / num_chunks

    chunks = []
    for i in range(num_chunks):
        start = i * chunk_duration
        actual_duration = min(chunk_duration, duration - start)

        chunk_path = tempfile.mktemp(suffix=Path(input_path).suffix)
        command = [
            "ffmpeg",
            "-y",
            "-i", input_path,
            "-ss", str(start),
            "-t", str(actual_duration),
            "-c", "copy",
            chunk_path
        ]
        proc = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if proc.returncode != 0:
            raise RuntimeError(f"Chunk splitting failed: {proc.stderr.decode()}")
        chunks.append(chunk_path)
    return chunks

def transcribe_file_chunked(input_path):
    chunks = split_media(input_path)
    combined_text = ""
    for chunk_path in chunks:
        suffix = Path(chunk_path).suffix.lower()
        audio_path = chunk_path
        if suffix in [".mp4", ".mov", ".m4v"]:
            audio_path = chunk_path.replace(suffix, "_audio.wav")
            command = [
                "ffmpeg", "-y", "-i", chunk_path,
                "-vn",
                "-acodec", "pcm_s16le",
                "-ac", "1",
                "-ar", "16000",
                audio_path
            ]
            proc = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if proc.returncode != 0:
                raise RuntimeError(f"Audio extraction failed: {proc.stderr.decode()}")

        text = transcribe_audio_groq(audio_path)
        combined_text += text + "\n"

        os.remove(chunk_path)
        if audio_path != chunk_path and os.path.exists(audio_path):
            os.remove(audio_path)

    return combined_text

st.markdown("""
Upload an audio or video file for transcription.

Large files will be automatically split into chunks for processing.
""")

ffmpeg_installed = check_ffmpeg()

if not ffmpeg_installed:
    st.warning("⚠️ ffmpeg is NOT installed or not accessible. Audio extraction from video files and splitting will not work. Please upload smaller audio files directly.")

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
    suffix = Path(uploaded_file.name).suffix.lower()
    # Save the uploaded file temporarily to check size
    temp_upload_path = os.path.join(UPLOAD_DIR, "temp_upload" + suffix)
    with open(temp_upload_path, "wb") as f:
        f.write(uploaded_file.read())

    file_size = os.path.getsize(temp_upload_path)

    if file_size > MAX_UPLOAD_SIZE_BYTES and ffmpeg_installed:
        # Compress file first
        compressed_filename = f"{Path(uploaded_file.name).stem}_compressed{suffix}"
        compressed_path = os.path.join(UPLOAD_DIR, compressed_filename)
        try:
            if suffix in [".mp3", ".wav", ".m4a", ".aac"]:
                compress_audio(temp_upload_path, compressed_path)
            elif suffix in [".mp4", ".mov", ".m4v"]:
                compress_video(temp_upload_path, compressed_path)
            else:
                st.error("Unsupported file type for compression.")
                compressed_path = temp_upload_path

            if os.path.getsize(compressed_path) > MAX_UPLOAD_SIZE_BYTES:
                st.warning(f"File still larger than {MAX_UPLOAD_SIZE_MB} MB after compression, will be split automatically.")
            save_path = compressed_path
        except Exception as e:
            st.error(f"Compression failed: {e}")
            save_path = temp_upload_path
    else:
        save_path = temp_upload_path

    try:
        # Transcribe in chunks
        transcription_text = transcribe_file_chunked(save_path)
        # Save uploaded file permanently
        permanent_name = f"{Path(uploaded_file.name).stem}_{int(os.path.getmtime('.'))}{suffix}"
        permanent_path = os.path.join(UPLOAD_DIR, permanent_name)
        os.rename(save_path, permanent_path)
        if temp_upload_path != save_path and os.path.exists(temp_upload_path):
            os.remove(temp_upload_path)

        st.success("Transcription complete!")
        st.text_area("📄 Extracted Text:", transcription_text, height=300)
        st.download_button("Download Transcript as TXT", transcription_text, file_name=f"{Path(permanent_name).stem}_transcript.txt")
    except Exception as e:
        st.error(f"Error during processing: {e}")

def transcribe_file_chunked(input_path):
    # This function defined above is repeated here for completeness
    chunks = split_media(input_path)
    combined_text = ""
    for chunk_path in chunks:
        suffix = Path(chunk_path).suffix.lower()
        audio_path = chunk_path
        if suffix in [".mp4", ".mov", ".m4v"]:
            audio_path = chunk_path.replace(suffix, "_audio.wav")
            command = [
                "ffmpeg", "-y", "-i", chunk_path,
                "-vn",
                "-acodec", "pcm_s16le",
                "-ac", "1",
                "-ar", "16000",
                audio_path
            ]
            proc = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if proc.returncode != 0:
                raise RuntimeError(f"Audio extraction failed: {proc.stderr.decode()}")

        text = transcribe_audio_groq(audio_path)
        combined_text += text + "\n"

        os.remove(chunk_path)
        if audio_path != chunk_path and os.path.exists(audio_path):
            os.remove(audio_path)

    return combined_text

def split_media(input_path, max_chunk_bytes=MAX_UPLOAD_SIZE_BYTES):
    file_size = os.path.getsize(input_path)
    duration = get_media_duration(input_path)

    num_chunks = max(1, int(file_size / max_chunk_bytes) + 1)
    chunk_duration = duration / num_chunks

    chunks = []
    for i in range(num_chunks):
        start = i * chunk_duration
        actual_duration = min(chunk_duration, duration - start)

        chunk_path = tempfile.mktemp(suffix=Path(input_path).suffix)
        command = [
            "ffmpeg",
            "-y",
            "-i", input_path,
            "-ss", str(start),
            "-t", str(actual_duration),
            "-c", "copy",
            chunk_path
        ]
        proc = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if proc.returncode != 0:
            raise RuntimeError(f"Chunk splitting failed: {proc.stderr.decode()}")
        chunks.append(chunk_path)
    return chunks

def get_media_duration(input_path):
    command = [
        "ffprobe", "-v", "error", "-show_entries",
        "format=duration", "-of",
        "default=noprint_wrappers=1:nokey=1", input_path
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe error: {result.stderr.decode()}")
    return float(result.stdout.strip())
