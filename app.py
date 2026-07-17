import streamlit as st
import time
import io

from azure.cognitiveservices.vision.computervision import ComputerVisionClient
from azure.cognitiveservices.vision.computervision.models import OperationStatusCodes
from msrest.authentication import CognitiveServicesCredentials
import azure.cognitiveservices.speech as speechsdk

# =========================================================
# PAGE SETUP
# (Colors/fonts for widgets come from .streamlit/config.toml,
# so we only need a tiny bit of CSS here for the title.)
# =========================================================
st.set_page_config(page_title="Readify AI", page_icon="📖", layout="wide")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@600&family=Inter:wght@400;500;600&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .app-title { font-family: 'Cormorant Garamond', serif; font-size: 56px;
                 text-align: center; color: #1A4331; margin-bottom: 0; }
    .app-subtitle { text-align: center; color: #718096; font-size: 14px; margin-top: 4px; }
    .empty-box { text-align: center; color: #A0AEC0; padding-top: 100px; }
</style>
""", unsafe_allow_html=True)

# =========================================================
# AZURE SETUP
# =========================================================
try:
    # OCR (Computer Vision) resource
    ocr_endpoint = st.secrets["AZURE_OCR_ENDPOINT"]
    ocr_key = st.secrets["AZURE_OCR_KEY"]
    vision_client = ComputerVisionClient(ocr_endpoint, CognitiveServicesCredentials(ocr_key))

    # TTS (Speech) resource — separate endpoint & key
    tts_endpoint = st.secrets["AZURE_TTS_ENDPOINT"]
    tts_key = st.secrets["AZURE_TTS_KEY"]
except Exception:
    st.error("⚠️ Azure credentials not found. Please add them to your Streamlit secrets.")
    st.stop()

VOICES = {"Male": "en-US-ChristopherNeural", "Female": "en-US-JennyNeural"}


# =========================================================
# HELPER FUNCTIONS
# (Used by more than one tab, so we write them once here.)
# =========================================================
def extract_text_from_image(image_file):
    """Send an image to Azure OCR and return the text found in it."""
    response = vision_client.read_in_stream(io.BytesIO(image_file.read()), raw=True)
    operation_id = response.headers["Operation-Location"].split("/")[-1]

    result = vision_client.get_read_result(operation_id)
    while result.status in [OperationStatusCodes.running, OperationStatusCodes.not_started]:
        time.sleep(0.5)
        result = vision_client.get_read_result(operation_id)

    lines = []
    if result.status == OperationStatusCodes.succeeded:
        for page in result.analyze_result.read_results:
            for line in page.lines:
                lines.append(line.text)
    return "\n".join(lines)


def text_to_speech(text, voice_label, output_path):
    """Convert text into a .wav audio file using the chosen voice."""
    speech_config = speechsdk.SpeechConfig(subscription=tts_key, endpoint=tts_endpoint)
    speech_config.speech_synthesis_voice_name = VOICES[voice_label]
    audio_config = speechsdk.audio.AudioOutputConfig(filename=output_path)
    synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)
    synthesizer.speak_text_async(text).get()
    return open(output_path, "rb").read()


def empty_state(icon, message, height=300):
    """A simple placeholder box shown before the user has run anything."""
    with st.container(border=True, height=height):
        st.markdown(f"<div class='empty-box'>{icon}<br>{message}</div>", unsafe_allow_html=True)


# =========================================================
# HEADER
# =========================================================
st.markdown('<p class="app-title">Readify AI</p>', unsafe_allow_html=True)
st.markdown(
    '<p class="app-subtitle">Document Intelligence • Speech Synthesis • Image to Speech</p>',
    unsafe_allow_html=True,
)
st.divider()

tab1, tab2, tab3 = st.tabs(["📄 Document to Text", "🎙️ Text to Speech", "🔊 Image to Speech"])

# =========================================================
# TAB 1 — DOCUMENT TO TEXT (OCR)
# =========================================================
with tab1:
    left, right = st.columns([1, 1.4], gap="large")

    with left:
        st.subheader("Upload a document")
        image_file = st.file_uploader(
            "Upload an image", type=["png", "jpg", "jpeg"],
            label_visibility="collapsed", key="ocr_upload",
        )

        run_ocr = False
        if image_file:
            st.image(image_file, use_container_width=True)
            c1, c2 = st.columns(2)
            c1.metric("Size", f"{image_file.size / 1024:.1f} KB")
            c2.metric("Format", image_file.type.split("/")[-1].upper())
            run_ocr = st.button("✨ Extract Text", use_container_width=True, key="ocr_button")
        else:
            st.info("Upload a PNG or JPG image to get started.")

    with right:
        st.subheader("Extracted text")
        if run_ocr:
            with st.status("Reading your document...") as status:
                extracted_text = extract_text_from_image(image_file)
                status.update(label="Done!", state="complete")

            if extracted_text.strip():
                with st.container(border=True, height=300):
                    st.write(extracted_text)
                st.download_button(
                    "📥 Download as .txt", extracted_text,
                    file_name="extracted_text.txt", key="ocr_download",
                )
            else:
                st.warning("No text was found in this image.")
        else:
            empty_state("📄", "Extracted text will appear here")

# =========================================================
# TAB 2 — TEXT TO SPEECH (TTS)
# =========================================================
with tab2:
    left, right = st.columns([1.4, 1], gap="large")

    with left:
        st.subheader("Write your script")
        script = st.text_area(
            "Enter text", height=220, label_visibility="collapsed",
            placeholder="Type or paste text to convert to speech...",
        )
        voice_t2 = st.radio("Voice", list(VOICES.keys()), horizontal=True, key="voice_tab2")
        run_tts = st.button("🪄 Generate Speech", use_container_width=True, key="tts_button")

    with right:
        st.subheader("Audio output")
        if run_tts and not script.strip():
            st.warning("Please enter some text first.")
            empty_state("🎙️", "Your audio will appear here", height=260)
        elif run_tts:
            with st.status("Generating audio...") as status:
                audio_bytes = text_to_speech(script, voice_t2, "voice.wav")
                status.update(label="Done!", state="complete")

            st.success(f"Audio generated with the {voice_t2.lower()} voice.")
            st.audio(audio_bytes, format="audio/wav")
            st.download_button(
                "📥 Download Audio", audio_bytes,
                file_name="voice.wav", key="tts_download",
            )
        else:
            empty_state("🎙️", "Your audio will appear here", height=280)

# =========================================================
# TAB 3 — IMAGE TO SPEECH (OCR + TTS)
# =========================================================
with tab3:
    left, right = st.columns([1, 1.4], gap="large")

    with left:
        st.subheader("Upload a document to read aloud")
        image_file_t3 = st.file_uploader(
            "Upload an image", type=["png", "jpg", "jpeg"],
            label_visibility="collapsed", key="img2speech_upload",
        )

        run_i2s = False
        voice_t3 = "Male"
        if image_file_t3:
            st.image(image_file_t3, use_container_width=True)
            c1, c2 = st.columns(2)
            c1.metric("Size", f"{image_file_t3.size / 1024:.1f} KB")
            c2.metric("Format", image_file_t3.type.split("/")[-1].upper())
            voice_t3 = st.radio("Voice", list(VOICES.keys()), horizontal=True, key="voice_tab3")
            run_i2s = st.button("🔊 Read Document Aloud", use_container_width=True, key="i2s_button")
        else:
            st.info("Upload a PNG or JPG image to get started.")

    with right:
        st.subheader("Processed output")
        if run_i2s:
            with st.status("Reading document and generating audio...") as status:
                extracted_text_t3 = extract_text_from_image(image_file_t3)
                audio_bytes_t3 = None
                if extracted_text_t3.strip():
                    audio_bytes_t3 = text_to_speech(extracted_text_t3, voice_t3, "vision_to_voice.wav")
                status.update(label="Done!", state="complete")

            if not extracted_text_t3.strip():
                st.warning("No text was found in this image.")
            else:
                with st.container(border=True, height=180):
                    st.write(extracted_text_t3)
                st.success(f"Audio generated with the {voice_t3.lower()} voice.")
                st.audio(audio_bytes_t3, format="audio/wav")
                st.download_button(
                    "📥 Download Audio", audio_bytes_t3,
                    file_name="vision_to_voice.wav", key="i2s_download",
                )
        else:
            empty_state("⚙️", "Processed output will appear here")

# =========================================================
# FOOTER
# =========================================================
st.divider()
st.markdown(
    "<div style='text-align:center; color:#A0AEC0; font-size:12px;'>"
    "Made with ❤️ by Varad Petare &nbsp;•&nbsp; Powered by Microsoft Azure AI"
    "</div>",
    unsafe_allow_html=True,
)