"""
NCB Field Companion — Presumptive Colorimetric Drug Screening Tool
--------------------------------------------------------------------
A Streamlit field app featuring a robust, glare-resistant colorimetry 
engine, CIELAB database-driven naming, automated text-to-speech, and 
professional PDF forensic report generation.
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
    """Returns the current date & time formatted for Indian Standard Time[cite: 1]."""
    return datetime.now(IST).strftime("%d-%m-%Y | %I:%M:%S %p")


# =====================================================================
# 2. VOICE ANNOUNCEMENT (TEXT-TO-SPEECH)
# =====================================================================
def talk_back(text):
    """
    Speaks the given text aloud using the browser's built-in speech engine[cite: 1].
    Embeds a fresh random ID per call to force re-execution.
    """
    call_id = uuid.uuid4().hex
    safe_text = text.replace('"', "'").replace("\n", " ")

    components.html(
        f"""
        <script>
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
# 3. ROBUST COLOR SCIENCE & EXTRACTION PIPELINE
# =====================================================================
def extract_stable_roi_lab(img, lighting_boost):
    """
    Extracts color from the ROI with outlier rejection (filtering out 
    glare highlights and dark shadows via percentile clipping) to 
    guarantee stable and accurate readings regardless of ambient light.
    """
    h, w, _ = img.shape
    half = min(25, h // 2, w // 2)
    if half < 1:
        return None, None

    # Extract Region of Interest (ROI) from center[cite: 1]
    roi = img[h // 2 - half : h // 2 + half, w // 2 - half : w // 2 + half]
    
    # Apply brightness adjustment safely[cite: 1]
    roi_float = roi.astype(np.float32) * lighting_boost
    roi_float = np.clip(roi_float, 0, 255).astype(np.uint8)
    
    # Convert ROI directly to Lab space for perceptual filtering
    roi_lab = cv2.cvtColor(roi_float, cv2.COLOR_BGR2Lab)
    pixels_lab = roi_lab.reshape(-1, 3)
    
    # Outlier rejection: Remove top 10% brightest (glare) and bottom 10% darkest (shadows)
    l_channel = pixels_lab[:, 0]
    if len(l_channel) > 10:
        p10, p90 = np.percentile(l_channel, 10), np.percentile(l_channel, 90)
        valid_pixels = pixels_lab[(l_channel >= p10) & (l_channel <= p90)]
        if len(valid_pixels) == 0:
            valid_pixels = pixels_lab
    else:
        valid_pixels = pixels_lab
        
    # Take median Lab values of valid pixels for high stability
    median_lab = np.median(valid_pixels, axis=0)
    l, a, b = median_lab.astype(float)
    
    # Convert OpenCV Lab scale back to standard CIE scale[cite: 1]
    scaled_lab = [round(l * (100 / 255), 1), round(a - 128, 1), round(b - 128, 1)]
    
    # Convert median Lab back to BGR/RGB for visual display and HEX mapping
    single_lab_pixel = np.uint8([[ [l, a, b] ]])
    single_bgr = cv2.cvtColor(single_lab_pixel, cv2.COLOR_Lab2BGR)[0][0]
    rgb = single_bgr[::-1]
    
    return scaled_lab, rgb


def get_robust_color_name(lab_val, db):
    """
    Names the color dynamically by finding the closest matching target 
    from the loaded reagent database, aligning results with chemical standards.
    """
    if not db:
        return "Analyzed Shade"
    
    best_name = "Unidentified Tint"
    min_dist = float("inf")
    
    for k, v in db.items():
        t_lab = v.get("target_lab")
        if t_lab:
            # Calculate CIE Lab Euclidean distance
            dist = np.sqrt(np.sum((np.array(lab_val) - np.array(t_lab)) ** 2))
            if dist < min_dist:
                min_dist = dist
                best_name = v.get("color_name", v.get("target_compound", "Matched Shade"))
                
    # If the measured shade is too far from any known reagent target
    if min_dist > 50.0:
        return "Non-Target / Blank Reaction"
        
    return best_name


# =====================================================================
# 4. PDF REPORT GENERATION
# =====================================================================
PDF_NAVY = colors.HexColor("#002F6C")
PDF_ROW_ALT = colors.HexColor("#F1F5F9")
PDF_BORDER = colors.HexColor("#CBD5E1")
PDF_TEXT = colors.HexColor("#111827")
PDF_GREEN = colors.HexColor("#0F7B3C")
PDF_AMBER = colors.HexColor("#B45309")
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
    try:
        fill = colors.HexColor(hex_code)
    except Exception:
        fill = colors.grey
    swatch = Table([[""]], colWidths=[36], rowHeights=[16])
    swatch.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), fill),
        ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#334155")),
    ]))
    return swatch


def _pdf_footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(PDF_MUTED)
    canvas.drawString(40, 25, "CONFIDENTIAL - Presumptive field screening record. For official use only[cite: 1].")
    canvas.drawRightString(letter[0] - 40, 25, f"Page {doc.page}")
    canvas.restoreState()


def generate_pdf(case_info, color_data, match_found, match_text, ndps_info, img_hash):
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

    elements += _pdf_section("1. CASE REFERENCE", [
        [Paragraph("Officer ID", PDF_LABEL), Paragraph(str(case_info["officer"]), PDF_VALUE)],
        [Paragraph("Case Number", PDF_LABEL), Paragraph(str(case_info["case"]), PDF_VALUE)],
        [Paragraph("Timestamp (IST)", PDF_LABEL), Paragraph(str(case_info["time"]), PDF_VALUE)],
    ])

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

    verdict_color = PDF_GREEN if match_found else PDF_AMBER
    verdict_label = "PRESUMPTIVE MATCH FOUND" if match_found else "NO REAGENT MATCH FOUND"
    verdict_style = ParagraphStyle("Verdict", parent=PDF_VALUE, textColor=verdict_color, fontName="Helvetica-Bold")
    elements += _pdf_section("3. ANALYSIS RESULT", [
        [Paragraph("Status", PDF_LABEL), Paragraph(verdict_label, verdict_style)],
        [Paragraph("Finding", PDF_LABEL), Paragraph(str(match_text), PDF_VALUE)],
        [Paragraph("NDPS Provision", PDF_LABEL), Paragraph(str(ndps_info), PDF_VALUE)],
    ])

    elements += _pdf_section("4. RECORD INTEGRITY", [
        [Paragraph("SHA-256 Image Hash", PDF_LABEL), Paragraph(str(img_hash), PDF_MONO)],
    ])

    elements.append(Spacer(1, 6))
    elements.append(Paragraph(
        "Note: This is an automated, presumptive field screening result based on a colour-reagent "
        "reaction. It is not a confirmatory laboratory finding[cite: 1].",
        PDF_NOTE,
    ))

    doc.build(elements, onFirstPage=_pdf_footer, onLaterPages=_pdf_footer)
    buffer.seek(0)
    return buffer.getvalue()


# =====================================================================
# 5. APPLICATION UI
# =====================================================================
st.set_page_config(page_title="NCB Smart Shield", page_icon="⚖️", layout="centered")

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
    .result-card h1 { margin: 0; color: white; font-size: 2.2em; }
    .result-card p { margin: 4px 0 0 0; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("⚖️ NCB Field Companion")
st.caption(f"Presumptive Forensic Colour Screening (Robust Engine)  |  {get_india_time()}")

with st.sidebar:
    st.header("📋 Case Records")
    off_id = st.text_input("Officer ID", "NCB-OFF-442")
    case_ref = st.text_input("Case No.", "F.No-" + datetime.now(IST).strftime("%Y/%m/%d"))
    st.divider()
    lighting_boost = st.slider("Brightness Adjustment", 0.8, 1.5, 1.0)
    st.caption("Adjust if environment lighting impacts visibility[cite: 1].")
    st.divider()
    st.caption("NCB Smart Shield v2.1 — Robust Edition")

st.subheader("1. Optical Evidence Capture")
st.caption("Place the sample vial or test strip centrally in the camera frame, then capture[cite: 1].")
camera_img = st.camera_input("Open camera & capture frame", label_visibility="collapsed")

if camera_img:
    file_bytes = np.frombuffer(camera_img.getvalue(), np.uint8)
    img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)

    if img is None:
        st.error("⚠️ Could not read the captured image. Please retake the photo[cite: 1].")
        st.stop()

    img_hash = hashlib.sha256(camera_img.getvalue()).hexdigest()[:16]

    # --- Load Reagent Database First ---
    db = {}
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f:
                db = json.load(f)
        except (json.JSONDecodeError, OSError):
            db = {}
            st.warning("⚠️ Reagent database file could not be read.")

    # --- Extract stable ROI lab with outlier rejection ---
    center_lab, center_rgb = extract_stable_roi_lab(img, lighting_boost)
    if center_lab is None:
        st.error("⚠️ Captured frame is too small to analyse. Please retake the photo[cite: 1].")
        st.stop()

    hex_val = "#%02x%02x%02x" % (int(center_rgb[0]), int(center_rgb[1]), int(center_rgb[2]))
    u_name = get_robust_color_name(center_lab, db)

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

    # --- Reagent database match cross-check ---
    match_found = False
    match_text = "No drug reagent match."
    ndps_provision = "N/A"

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

    if not match_found:
        st.warning("⚠️ Measured shade does not fall within acceptable tolerance ($\Delta E$) for listed reagents.")

    # --- Voice announcement ---
    speech = f"Detected shade is {u_name}. " + (
        f"Result is {match_text}" if match_found else "No drug match found."
    )
    talk_back(speech)

    st.write("### 3. Actions")
    col1, col2 = st.columns(2)

    with col1:
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
                data=pdf_bytes,
                file_name=f"NCB_Report_{img_hash[:8]}.pdf",
                mime="application/pdf",
                key="download_ncb_report",
            )
        except Exception as exc:
            st.error(f"⚠️ Could not generate the PDF report: {exc}")

    st.write("---")
    st.caption(
        "This is a presumptive field screening result only. Confirmatory laboratory "
        "analysis is required before use as legal evidence[cite: 1]."
    )
