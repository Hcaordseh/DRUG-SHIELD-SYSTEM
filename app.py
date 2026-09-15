"""
NCB Field Companion - Forensic Color Screening Tool
-----------------------------------------------------
A Streamlit application for field officers to perform a preliminary
colorimetric (reagent) screening test on a sample and cross-check the
resulting color against a known reagent database.

NOTE: This tool provides a PRELIMINARY field indication only.
All results must be confirmed through proper laboratory analysis.
"""

import streamlit as st
import cv2
import numpy as np
import hashlib
import json
import os
import time
import pytz
from datetime import datetime

# ============================================================
# CONFIGURATION
# ============================================================
DB_FILE = "reagents.json"
IST = pytz.timezone("Asia/Kolkata")

# Built-in forensic color reference palette
# (name -> RGB). Used to describe the detected shade in plain language.
COLOR_PALETTE = {
    "Pure White": (255, 255, 255), "Ivory": (255, 255, 240), "Silver": (192, 192, 192),
    "Dark Gray": (169, 169, 169), "Jet Black": (15, 15, 15), "Deep Crimson": (153, 0, 0),
    "Bright Red": (255, 0, 0), "Maroon": (128, 0, 0), "Blood Orange": (255, 69, 0),
    "Golden Yellow": (255, 215, 0), "Amber": (255, 191, 0), "Olive Green": (128, 128, 0),
    "Emerald Green": (80, 200, 120), "Forest Green": (34, 139, 34), "Deep Cyan": (0, 139, 139),
    "Cobalt Blue": (0, 71, 171), "Royal Blue": (65, 105, 225), "Navy Blue": (0, 0, 128),
    "Indigo": (75, 0, 130), "Deep Purple": (128, 0, 128), "Violet": (238, 130, 238),
    "Magenta": (255, 0, 255), "Pink": (255, 192, 203), "Brown": (139, 69, 19),
    "Tan": (210, 180, 140), "Slate": (112, 128, 144), "Pale Blue": (173, 216, 230),
}


# ============================================================
# HELPER FUNCTIONS
# ============================================================
def get_india_time():
    """Return the current time in India (IST) as a formatted string."""
    return datetime.now(IST).strftime("%d-%m-%Y | %I:%M:%S %p")


def talk_back(text: str):
    """
    Announce text using the browser's built-in speech synthesis.

    A unique 'nonce' (timestamp) is embedded as a comment on every call.
    This guarantees the injected HTML/JS is never byte-identical between
    calls, which forces Streamlit to reload the component and re-run the
    script every single time (fixing the "only works once" issue where
    an unchanged component was not being re-executed on repeat clicks).
    """
    nonce = int(time.time() * 1000)
    safe_text = text.replace('"', "'").replace("\n", " ")

    st.components.v1.html(
        f"""
        <script>
        // nonce:{nonce} -- ensures this block is treated as new content
        window.speechSynthesis.cancel();
        var msg = new SpeechSynthesisUtterance("{safe_text}");
        msg.lang = 'en-IN';
        msg.pitch = 1;
        msg.rate = 0.9;
        window.speechSynthesis.speak(msg);
        </script>
        """,
        height=0,
    )


def get_universal_name(rgb) -> str:
    """
     Match an RGB value to the closest named color in COLOR_PALETTE.
     Falls back to a neutral description for gray/black/white tones.
    """
                                       
    r, g, b = int(rgb[0]), int(rgb[1]), int(rgb[2])

    # Neutral tone check (R, G, B values very close together)
    diff = max(r, g, b) - min(r, g, b)
    if diff < 15:
        if r > 200:
            return "Off-White"
        if r < 40:
            return "Charcoal Black"
        return "Neutral Gray"

    # Closest match by Euclidean distance in RGB space
    best_match, min_dist = "Unknown Shade", float("inf")
    for name, ref_rgb in COLOR_PALETTE.items():
        dist = np.sqrt(sum((c1 - c2) ** 2 for c1, c2 in zip(ref_rgb, (r, g, b))))
        if dist < min_dist:
            min_dist, best_match = dist, name

    return best_match


def rgb_to_lab_scaled(rgb):
    """Convert an RGB triplet to standard CIELAB (L: 0-100, a/b: -128 to 127)."""
    pixel_rgb = np.uint8([[rgb]])
    pixel_lab = cv2.cvtColor(pixel_rgb, cv2.COLOR_RGB2Lab)
    l, a, b = pixel_lab[0][0].astype(float)
    return [round(l * (100 / 255), 1), round(a - 128, 1), round(b - 128, 1)]


def load_reagent_db():
    """
    Safely load the reagent database. Returns an empty dict (with a
    warning shown to the user) if the file is missing or corrupted,
    instead of crashing the app.
    """
    if not os.path.exists(DB_FILE):
        return {}
    try:
        with open(DB_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        st.warning(f"⚠️ Reagent database '{DB_FILE}' could not be read. Skipping match check.")
        return {}


def analyze_image(image_bytes: bytes, brightness: float):
    """
    Decode the captured image, sample the center region, and compute
    the detected color's name, HEX code, and CIELAB values.
    Returns None if the image could not be decoded.
    """
    file_bytes = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
    if img is None:
        return None

    h, w = img.shape[:2]
    half = min(15, h // 2, w // 2)  # keep the sample box safely inside small images
    cy, cx = h // 2, w // 2
    roi = img[cy - half: cy + half, cx - half: cx + half]

    avg_bgr = np.clip(np.mean(roi, axis=(0, 1)) * brightness, 0, 255)
    center_rgb = avg_bgr[::-1]  # BGR -> RGB

    hex_val = "#%02x%02x%02x" % (int(center_rgb[0]), int(center_rgb[1]), int(center_rgb[2]))
    lab_val = rgb_to_lab_scaled(center_rgb)
    name_val = get_universal_name(center_rgb)

    return {
        "rgb": [int(v) for v in center_rgb],
        "hex": hex_val,
        "lab": lab_val,
        "name": name_val,
    }


def check_reagent_match(lab_value, db):
    """
    Compare the detected CIELAB value against every entry in the reagent
    database and return the first match within tolerance, if any.
    """
    for entry in db.values():
        target_lab = entry.get("target_lab")
        if not target_lab:
            continue
        distance = np.sqrt(np.sum((np.array(lab_value) - np.array(target_lab)) ** 2))
        if distance < entry.get("tolerance_de", 25.0):
            return {
                "compound": entry.get("target_compound", "Unknown compound"),
                "section": entry.get("ndps_section", "N/A"),
            }
    return None


def build_report(officer_id, case_ref, result, match):
    """Build a clean, professional plain-text report for download."""
    lines = [
        "=" * 50,
        "NCB FIELD COMPANION - FORENSIC SCREENING REPORT",
        "=" * 50,
        f"Officer ID   : {officer_id}",
        f"Case Ref.    : {case_ref}",
        f"Date & Time  : {get_india_time()} (IST)",
        "-" * 50,
        "OPTICAL ANALYSIS",
        f"Detected Shade : {result['name']}",
        f"HEX Code       : {result['hex'].upper()}",
        f"RGB Value      : {tuple(result['rgb'])}",
        f"CIELAB (L,a,b) : {tuple(result['lab'])}",
        "-" * 50,
        "REAGENT CROSS-CHECK",
    ]

    if match:
        lines.append(f"Result         : POSSIBLE MATCH FOUND")
        lines.append(f"Compound       : {match['compound']}")
        lines.append(f"NDPS Provision : {match['section']}")
    else:
        lines.append("Result         : No reagent match found in database.")

    lines += [
        "-" * 50,
        "DISCLAIMER: This is a preliminary field screening result only.",
        "It must be confirmed through certified laboratory analysis before",
        "being relied upon for any legal or evidentiary purpose.",
        "=" * 50,
    ]
    return "\n".join(lines)


# ============================================================
# PAGE SETUP & STYLING
# ============================================================
st.set_page_config(page_title="NCB Smart Shield", page_icon="⚖️", layout="centered")

st.markdown("""
    <style>
    div.stButton > button {
        width: 100%;
        border-radius: 10px;
        height: 3.2em;
        font-weight: 600;
        background-color: #002F6C;
        color: white;
        border: 1px solid #4E9F3D;
        transition: 0.2s ease-in-out;
    }
    div.stButton > button:hover {
        background-color: #003d8f;
        border: 1px solid #6fd97a;
        color: white;
    }
    div.stDownloadButton > button {
        width: 100%;
        border-radius: 10px;
        height: 3.2em;
        font-weight: 600;
        background-color: #4E9F3D;
        color: white;
        border: none;
    }
    .result-card {
        background: #1E1E1E;
        padding: 25px;
        border-radius: 15px;
        margin-bottom: 12px;
    }
    .result-title {
        margin: 0;
        color: white;
        font-size: 2.2em;
    }
    .result-sub {
        margin: 4px 0 0 0;
        color: #AAAAAA;
        font-size: 1.05em;
    }
    .result-lab {
        margin: 6px 0 0 0;
        color: #4E9F3D;
        font-weight: 600;
    }
    </style>
""", unsafe_allow_html=True)

st.title("⚖️ NCB Field Companion")
st.caption(f"Forensic Screening Tool  |  {get_india_time()} IST")

# ============================================================
# SIDEBAR - CASE DETAILS
# ============================================================
with st.sidebar:
    st.header("📋 Case Details")
    off_id = st.text_input("Officer ID", "NCB-OFF-442")
    case_ref = st.text_input("Case No.", "F.No-" + datetime.now(IST).strftime("%Y/%m/%d"))
    st.divider()
    lighting_boost = st.slider("Brightness Adjustment", 0.8, 1.5, 1.0, step=0.05)
    st.caption("Increase this if the capture environment is dim.")
    st.divider()
    st.caption("⚠️ Field screening only. Not a substitute for lab confirmation.")

# ============================================================
# STEP 1 - CAPTURE
# ============================================================
st.subheader("1️⃣ Optical Evidence Capture")
camera_img = st.camera_input("Place the sample vial/strip in the center of the frame")

# ============================================================
# STEP 2 - PROCESS (only re-run analysis when the image or brightness changes)
# ============================================================
if camera_img is not None:
    image_bytes = camera_img.getvalue()
    capture_signature = hashlib.md5(image_bytes + str(lighting_boost).encode()).hexdigest()

    if st.session_state.get("capture_signature") != capture_signature:
        result = analyze_image(image_bytes, lighting_boost)

        if result is None:
            st.error("❌ Could not process the captured image. Please retake the photo.")
        else:
            db = load_reagent_db()
            match = check_reagent_match(result["lab"], db)

            speech = f"Detected shade is {result['name']}. "
            speech += (
                f"Possible match: {match['compound']}." if match
                else "No reagent match found."
            )

            # Persist everything needed for later reruns (Repeat Audio / Report)
            st.session_state["capture_signature"] = capture_signature
            st.session_state["result"] = result
            st.session_state["match"] = match
            st.session_state["speech"] = speech
            st.session_state["just_analyzed"] = True

# ============================================================
# STEP 3 - DISPLAY RESULTS (persists across reruns via session_state)
# ============================================================
if "result" in st.session_state:
    result = st.session_state["result"]
    match = st.session_state["match"]
    speech = st.session_state["speech"]

    st.write("### 2️⃣ Forensic Analysis")
    st.markdown(f"""
        <div class="result-card" style="border-left:12px solid {result['hex']};">
            <h1 class="result-title">{result['name']}</h1>
            <p class="result-sub">HEX: <b>{result['hex'].upper()}</b></p>
            <p class="result-lab">CIELAB: L:{result['lab'][0]}  a:{result['lab'][1]}  b:{result['lab'][2]}</p>
        </div>
    """, unsafe_allow_html=True)

    with st.expander("🔬 View raw technical data"):
        st.write(f"**RGB:** {tuple(result['rgb'])}")
        st.write(f"**CIELAB:** {tuple(result['lab'])}")

    if match:
        st.success(f"⚖️ **POSSIBLE MATCH:** {match['compound']}")
        st.info(f"📜 **NDPS Provision:** {match['section']}")
    else:
        st.warning("No reagent match found for this sample in the current database.")

    # Auto-play audio only right after a fresh capture (not on every rerun)
    if st.session_state.get("just_analyzed"):
        talk_back(speech)
        st.session_state["just_analyzed"] = False

    st.write("### 3️⃣ Actions")
    col1, col2 = st.columns(2)

    with col1:
        if st.button("🔊 Repeat Audio"):
            talk_back(speech)

    with col2:
        report_text = build_report(off_id, case_ref, result, match)
        file_name = f"NCB_Report_{datetime.now(IST).strftime('%Y%m%d_%H%M%S')}.txt"
        st.download_button(
            label="📄 Generate Report",
            data=report_text,
            file_name=file_name,
            mime="text/plain",
        )

    st.divider()
else:
    st.info("Capture a photo above to begin the analysis.")
