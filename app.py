"""
NCB Field Companion — Presumptive Colorimetric Drug Screening Tool
--------------------------------------------------------------------
A Streamlit field app that:
  1. Captures a photo of a reagent-treated sample via the device camera.
  2. Reads the colour that developed in the sample and names/measures it.
  3. Cross-checks that colour against a local reagent database (reagents.json).
  4. Announces the result out loud and lets the officer download a
     detailed, professional PDF report of the finding.

NOTE: The camera capture and colour-extraction logic (ROI crop, brightness
adjustment, RGB -> Lab conversion, nearest-colour lookup) is intentionally
left exactly as in the original version — only reliability guards were
added around it. Everything else (UI, PDF report, voice playback) has been
refactored for a cleaner, more professional and more reliable experience.
"""

import streamlit as st
import cv2
import numpy as np
import hashlib
import json
import os
import uuid
import pytz
from datetime import datetime
from io import BytesIO
import streamlit.components.v1 as components

# --- PDF report libraries ---
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle


# =====================================================================
# 1. CONFIGURATION
# =====================================================================
DB_FILE = "reagents.json"
IST = pytz.timezone("Asia/Kolkata")


def get_india_time():
    """Returns the current date & time formatted for Indian Standard Time."""
    return datetime.now(IST).strftime("%d-%m-%Y | %I:%M:%S %p")


# =====================================================================
# 2. VOICE ANNOUNCEMENT (TEXT-TO-SPEECH)
# =====================================================================
def talk_back(text):
    """
    Speaks the given text aloud using the browser's built-in speech engine.

    FIX: Every call embeds a fresh random id in the component. Without this,
    clicking "Repeat Audio" a second time sent Streamlit the exact same HTML
    as before, so the browser treated it as unchanged and never re-ran the
    <script> tag — the audio would only ever play on the very first call.
    Making each call's HTML unique forces the component to re-render and the
    script to fire every single time.
    """
    call_id = uuid.uuid4().hex
    safe_text = text.replace('"', "'").replace("\n", " ")  # keep the JS string literal valid

    components.html(
        f"""
        <script>
        // unique-per-call id, ensures this component always re-executes: {call_id}
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


# =====================================================================
# 3. COLOR SCIENCE (UNCHANGED LOGIC — camera/colour pipeline untouched)
# =====================================================================
def get_universal_name(rgb):
    """Built-in naming engine: no external library required, zero failure."""
    r, g, b = int(rgb[0]), int(rgb[1]), int(rgb[2])

    colors_db = {
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

    best_match = "Unknown Shade"
    min_dist = float("inf")
    for name, c_rgb in colors_db.items():
        dist = np.sqrt((c_rgb[0] - r) ** 2 + (c_rgb[1] - g) ** 2 + (c_rgb[2] - b) ** 2)
        if dist < min_dist:
            min_dist = dist
            best_match = name

    # Fine-tuning for neutrals (if RGB values are very close together)
    diff = max(r, g, b) - min(r, g, b)
    if diff < 15:
        if r > 200:
            return "Off-White"
        if r < 40:
            return "Charcoal Black"
        return "Neutral Gray"

    return best_match


def rgb_to_lab_scaled(rgb):
    """Converts an RGB triplet to standard-scale CIE L*a*b* coordinates."""
    pixel_rgb = np.uint8([[rgb]])
    pixel_lab = cv2.cvtColor(pixel_rgb, cv2.COLOR_RGB2Lab)
    l, a, b = pixel_lab[0][0].astype(float)
    return [round(l * (100 / 255), 1), round(a - 128, 1), round(b - 128, 1)]


# =====================================================================
# 4. PDF REPORT GENERATION
# =====================================================================
# Kept in one place so contrast/legibility is easy to review and tune.
PDF_NAVY = colors.HexColor("#002F6C")
PDF_ROW_ALT = colors.HexColor("#F1F5F9")
PDF_BORDER = colors.HexColor("#CBD5E1")
PDF_TEXT = colors.HexColor("#111827")       # near-black — high contrast on white
PDF_GREEN = colors.HexColor("#0F7B3C")      # positive / confirmed match
PDF_AMBER = colors.HexColor("#B45309")      # no confident match found
PDF_MUTED = colors.HexColor("#64748B")

_styles = getSampleStyleSheet()
PDF_LABEL = ParagraphStyle("Label", parent=_styles["Normal"], fontName="Helvetica-Bold", fontSize=10, textColor=PDF_NAVY)
PDF_VALUE = ParagraphStyle("Value", parent=_styles["Normal"], fontName="Helvetica", fontSize=10, textColor=PDF_TEXT, leading=13)
PDF_MONO = ParagraphStyle("Mono", parent=_styles["Normal"], fontName="Courier", fontSize=9, textColor=PDF_TEXT, leading=12)
PDF_SECTION_HEAD = ParagraphStyle("SectionHead", parent=_styles["Normal"], fontName="Helvetica-Bold", fontSize=11, textColor=colors.white)
PDF_TITLE = ParagraphStyle("Title", parent=_styles["Title"], fontSize=18, textColor=PDF_NAVY, spaceAfter=2)
PDF_SUBTITLE = ParagraphStyle("Subtitle", parent=_styles["Normal"], fontSize=9, textColor=PDF_MUTED, alignment=1)
PDF_NOTE = ParagraphStyle("Note", parent=_styles["Normal"], fontSize=8.5, textColor=PDF_MUTED, fontName="Helvetica-Oblique")


def _pdf_section(title, rows, col_widths=(160, 340)):
    """One titled block of the report: a dark header bar + a bordered data table."""
    header = Table([[Paragraph(title, PDF_SECTION_HEAD)]], colWidths=[sum(col_widths)])
    header.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PDF_NAVY),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    body = Table(rows, colWidths=list(col_widths))
    body.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.6, PDF_BORDER),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, PDF_ROW_ALT]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return [header, body, Spacer(1, 12)]


def _pdf_color_swatch(hex_code):
    """A small filled box so the reader can visually verify the detected shade."""
    try:
        fill = colors.HexColor(hex_code)
    except Exception:
        fill = colors.grey  # never let a bad hex string break report generation
    swatch = Table([[""]], colWidths=[36], rowHeights=[16])
    swatch.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), fill),
        ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#334155")),
    ]))
    return swatch


def _pdf_footer(canvas, doc):
    """Drawn on every page: a confidentiality notice and the page number."""
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(PDF_MUTED)
    canvas.drawString(40, 25, "CONFIDENTIAL - Presumptive field screening record. For official use only.")
    canvas.drawRightString(letter[0] - 40, 25, f"Page {doc.page}")
    canvas.restoreState()


def generate_pdf(case_info, color_data, match_found, match_text, ndps_info, img_hash):
    """
    Builds a detailed, professional PDF screening report and returns it as
    raw bytes (ready to hand straight to st.download_button).

    Any unexpected error while building the document is raised to the
    caller so the UI can show a clear message instead of silently
    producing a broken/empty file.
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=letter,
        leftMargin=40, rightMargin=40, topMargin=40, bottomMargin=50,
    )

    elements = [
        Paragraph("NARCOTICS CONTROL BUREAU", PDF_TITLE),
        Paragraph("Field Presumptive Colorimetric Screening Report", PDF_SUBTITLE),
        Spacer(1, 14),
    ]

    # Section 1 — who / when / which case this record belongs to
    elements += _pdf_section("1. CASE REFERENCE", [
        [Paragraph("Officer ID", PDF_LABEL), Paragraph(str(case_info["officer"]), PDF_VALUE)],
        [Paragraph("Case Number", PDF_LABEL), Paragraph(str(case_info["case"]), PDF_VALUE)],
        [Paragraph("Timestamp (IST)", PDF_LABEL), Paragraph(str(case_info["time"]), PDF_VALUE)],
    ])

    # Section 2 — the optical result, with a live swatch, not just a name
    swatch_row = Table(
        [[Paragraph(color_data["name"], PDF_VALUE), _pdf_color_swatch(color_data["hex"])]],
        colWidths=[264, 40],
        style=TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]),
    )
    lab = color_data["lab"]
    elements += _pdf_section("2. COLORIMETRIC ANALYSIS", [
        [Paragraph("Detected Shade", PDF_LABEL), swatch_row],
        [Paragraph("HEX Code", PDF_LABEL), Paragraph(color_data["hex"], PDF_MONO)],
        [Paragraph("CIE L*a*b* Standards", PDF_LABEL),
         Paragraph(f"L: {lab[0]}&nbsp;&nbsp; a: {lab[1]}&nbsp;&nbsp; b: {lab[2]}", PDF_VALUE)],
    ])

    # Section 3 — the reagent match verdict and its legal basis
    verdict_color = PDF_GREEN if match_found else PDF_AMBER
    verdict_label = "PRESUMPTIVE MATCH FOUND" if match_found else "NO REAGENT MATCH FOUND"
    verdict_style = ParagraphStyle("Verdict", parent=PDF_VALUE, textColor=verdict_color, fontName="Helvetica-Bold")
    elements += _pdf_section("3. ANALYSIS RESULT", [
        [Paragraph("Status", PDF_LABEL), Paragraph(verdict_label, verdict_style)],
        [Paragraph("Finding", PDF_LABEL), Paragraph(str(match_text), PDF_VALUE)],
        [Paragraph("NDPS Provision", PDF_LABEL), Paragraph(str(ndps_info), PDF_VALUE)],
    ])

    # Section 4 — tamper-evidence / record integrity
    elements += _pdf_section("4. RECORD INTEGRITY", [
        [Paragraph("SHA-256 Image Hash", PDF_LABEL), Paragraph(str(img_hash), PDF_MONO)],
    ])

    elements.append(Spacer(1, 6))
    elements.append(Paragraph(
        "Note: This is an automated, presumptive field screening result based on a colour-reagent "
        "reaction. It is not a confirmatory laboratory finding. Confirmatory chemical analysis by an "
        "accredited forensic laboratory is required before this result can be relied upon as legal evidence.",
        PDF_NOTE,
    ))

    doc.build(elements, onFirstPage=_pdf_footer, onLaterPages=_pdf_footer)
    buffer.seek(0)
    return buffer.getvalue()


# =====================================================================
# 5. APPLICATION UI
# =====================================================================
st.set_page_config(page_title="NCB Smart Shield", page_icon="⚖️", layout="centered")

# --- Professional, minimal styling ---
st.markdown(
    """
    <style>
    div.stButton > button, div.stDownloadButton > button {
        width: 100%;
        border-radius: 12px;
        height: 3.4em;
        font-weight: 600;
        background-color: #002F6C;
        color: white;
        border: 1px solid #4E9F3D;
        transition: filter 0.15s ease-in-out;
    }
    div.stButton > button:hover, div.stDownloadButton > button:hover {
        filter: brightness(1.15);
        border: 1px solid #4E9F3D;
        color: white;
    }
    .result-card {
        background: #1E1E1E;
        padding: 25px;
        border-radius: 15px;
        margin-bottom: 10px;
    }
    .result-card h1 { margin: 0; color: white; font-size: 2.5em; }
    .result-card p { margin: 4px 0 0 0; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("⚖️ NCB Field Companion")
st.caption(f"Presumptive Forensic Colour Screening  |  {get_india_time()}")

with st.sidebar:
    st.header("📋 Case Records")
    off_id = st.text_input("Officer ID", "NCB-OFF-442")
    case_ref = st.text_input("Case No.", "F.No-" + datetime.now(IST).strftime("%Y/%m/%d"))
    st.divider()
    lighting_boost = st.slider("Brightness Adjustment", 0.8, 1.5, 1.0)
    st.caption("Adjust if the environment is too dark or too bright.")
    st.divider()
    st.caption("NCB Smart Shield v2.0 — Field Edition")

st.subheader("1. Optical Evidence Capture")
st.caption("Place the sample vial or test strip in the centre of the frame, then capture.")
camera_img = st.camera_input("Open camera & capture frame", label_visibility="collapsed")

if camera_img:
    # --- Decode the captured frame (camera/colour logic left unchanged) ---
    file_bytes = np.frombuffer(camera_img.getvalue(), np.uint8)
    img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)

    if img is None:
        # Reliability guard: a corrupted/undecodable frame should never crash the app.
        st.error("⚠️ Could not read the captured image. Please retake the photo.")
        st.stop()

    img_hash = hashlib.sha256(camera_img.getvalue()).hexdigest()[:16]

    # --- Colour extraction (identical 30x30 centre-crop logic as before) ---
    h, w, _ = img.shape
    half = min(15, h // 2, w // 2)  # reliability guard for unusually small frames
    if half < 1:
        st.error("⚠️ Captured frame is too small to analyse. Please retake the photo.")
        st.stop()

    roi = img[h // 2 - half : h // 2 + half, w // 2 - half : w // 2 + half]
    avg_bgr = np.mean(roi, axis=(0, 1)) * lighting_boost
    avg_bgr = np.clip(avg_bgr, 0, 255)

    center_rgb = avg_bgr[::-1]
    center_lab = rgb_to_lab_scaled(center_rgb)
    hex_val = "#%02x%02x%02x" % (int(center_rgb[0]), int(center_rgb[1]), int(center_rgb[2]))
    u_name = get_universal_name(center_rgb)

    # --- Result display ---
    st.write("### 2. Forensic Analysis")
    st.markdown(
        f"""
        <div class="result-card" style="border-left:12px solid {hex_val};">
            <h1>{u_name}</h1>
            <p style="color:#AAA; font-size: 1.2em;">HEX: <b>{hex_val.upper()}</b></p>
            <p style="color:#4E9F3D; font-weight:bold;">
                CIELAB Standards: L:{center_lab[0]}  a:{center_lab[1]}  b:{center_lab[2]}
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # --- Reagent database lookup ---
    match_found = False
    match_text = "No drug reagent match."
    ndps_provision = "N/A"

    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f:
                db = json.load(f)
        except (json.JSONDecodeError, OSError):
            # Reliability guard: a corrupted database file should warn, not crash.
            db = {}
            st.warning("⚠️ Reagent database file could not be read — skipping match lookup.")

        for k, v in db.items():
            t_lab = v.get("target_lab")
            if t_lab:
                dist = np.sqrt(np.sum((np.array(center_lab) - np.array(t_lab)) ** 2))
                if dist < v.get("tolerance_de", 25.0):
                    match_text = f"Consistent with {v['target_compound']}"
                    ndps_provision = v.get("ndps_section", "N/A")
                    st.success(f"⚖️ **POSS. MATCH:** {v['target_compound']}")
                    st.info(f"📜 **NDPS Provision:** {ndps_provision}")
                    match_found = True
                    break
    else:
        st.warning("⚠️ No reagent database (reagents.json) found — skipping match lookup.")

    # --- Voice announcement (spoken automatically on every new capture) ---
    speech = f"Detected shade is {u_name}. " + (
        f"Result is {match_text}" if match_found else "No drug match found."
    )
    talk_back(speech)

    st.write("### 3. Actions")
    col1, col2 = st.columns(2)

    with col1:
        # FIX: talk_back() now embeds a fresh id on every call, so this
        # reliably speaks again no matter how many times it is pressed.
        if st.button("🔊 Repeat Audio"):
            talk_back(speech)

    with col2:
        case_info = {"time": get_india_time(), "officer": off_id, "case": case_ref}
        color_data = {"name": u_name, "hex": hex_val.upper(), "lab": center_lab}

        try:
            pdf_bytes = generate_pdf(
                case_info, color_data, match_found, match_text, ndps_provision, img_hash
            )
            st.download_button(
                label="📄 Generate Report",
                data=pdf_bytes,  # raw bytes (not a buffer object) for reliable PDF recognition
                file_name=f"NCB_Report_{img_hash[:8]}.pdf",
                mime="application/pdf",
                key="download_ncb_report",
            )
        except Exception as exc:
            # Reliability guard: never let report generation silently fail —
            # this is exactly what made "Generate Report" appear broken before.
            st.error(f"⚠️ Could not generate the PDF report: {exc}")

    st.write("---")
    st.caption(
        "This is a presumptive field screening result only. Confirmatory laboratory "
        "analysis is required before use as legal evidence."
    )
