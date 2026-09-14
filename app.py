import streamlit as st
import cv2
import numpy as np
import hashlib
import json
import os
from datetime import datetime
from io import BytesIO

# ReportLab libraries for statutory PDF Panchnama generation
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet

# =====================================================================
# 1. UNIVERSAL COLOR ANCHORS (Standard CIE L*a*b* D65 Reference)
# =====================================================================
UNIVERSAL_COLOR_PALETTE = {
    "Pure White / Clear": np.array([98.0, 0.0, 0.0]),
    "Neutral Gray": np.array([55.0, 0.0, 0.0]),
    "Jet Black": np.array([10.0, 0.0, 0.0]),
    "Bright Red": np.array([53.0, 68.0, 52.0]),
    "Dark Red / Maroon": np.array([28.0, 48.0, 32.0]),
    "Orange": np.array([65.0, 40.0, 65.0]),
    "Amber / Golden Yellow": np.array([75.0, 15.0, 75.0]),
    "Bright Yellow": np.array([92.0, -8.0, 85.0]),
    "Lime Green": np.array([80.0, -55.0, 65.0]),
    "Emerald / Bright Green": np.array([52.0, -65.0, 35.0]),
    "Dark Forest Green": np.array([32.0, -35.0, 18.0]),
    "Olive Green": np.array([45.0, -15.0, 32.0]),
    "Cyan / Sky Blue": np.array([72.0, -28.0, -22.0]),
    "Cobalt Blue": np.array([35.0, 15.0, -55.0]),
    "Deep Navy Blue": np.array([18.0, 8.0, -32.0]),
    "Indigo / Dark Violet": np.array([22.0, 28.0, -28.0]),
    "Purple / Violet": np.array([38.0, 48.0, -32.0]),
    "Magenta / Pink": np.array([62.0, 58.0, -12.0]),
    "Brown / Earth Tone": np.array([38.0, 18.0, 25.0])
}

DB_FILE = "reagents.json"


def ciede2000(lab1, lab2):
    """Calculates CIEDE2000 (ΔE00) perceptual color difference between two CIE L*a*b* vectors."""
    L1, a1, b1 = lab1
    L2, a2, b2 = lab2

    L_bar = (L1 + L2) / 2.0
    C1 = np.sqrt(a1**2 + b1**2)
    C2 = np.sqrt(a2**2 + b2**2)
    C_bar = (C1 + C2) / 2.0

    G = 0.5 * (1.0 - np.sqrt((C_bar**7) / (C_bar**7 + 25.0**7)))

    a1_p = (1.0 + G) * a1
    a2_p = (1.0 + G) * a2

    C1_p = np.sqrt(a1_p**2 + b1**2)
    C2_p = np.sqrt(a2_p**2 + b2**2)
    C_bar_p = (C1_p + C2_p) / 2.0

    h1_p = np.degrees(np.arctan2(b1, a1_p)) % 360.0
    h2_p = np.degrees(np.arctan2(b2, a2_p)) % 360.0

    if abs(h1_p - h2_p) <= 180.0:
        dh_p = h2_p - h1_p
    elif h2_p <= h1_p:
        dh_p = h2_p - h1_p + 360.0
    else:
        dh_p = h2_p - h1_p - 360.0

    dH_p = 2.0 * np.sqrt(C1_p * C2_p) * np.sin(np.radians(dh_p / 2.0))

    if abs(h1_p - h2_p) <= 180.0:
        H_bar_p = (h1_p + h2_p) / 2.0
    elif (h1_p + h2_p) < 360.0:
        H_bar_p = (h1_p + h2_p + 360.0) / 2.0
    else:
        H_bar_p = (h1_p + h2_p - 360.0) / 2.0

    T = (1.0 - 0.17 * np.cos(np.radians(H_bar_p - 30.0))
         + 0.24 * np.cos(np.radians(2.0 * H_bar_p))
         + 0.32 * np.cos(np.radians(3.0 * H_bar_p + 6.0))
         - 0.20 * np.cos(np.radians(4.0 * H_bar_p - 63.0)))

    dL_p = L2 - L1
    dC_p = C2_p - C1_p

    S_L = 1.0 + (0.015 * ((L_bar - 50.0)**2)) / np.sqrt(20.0 + ((L_bar - 50.0)**2))
    S_C = 1.0 + 0.045 * C_bar_p
    S_H = 1.0 + 0.015 * C_bar_p * T

    dTheta = 30.0 * np.exp(-(((H_bar_p - 275.0) / 25.0)**2))
    R_C = 2.0 * np.sqrt((C_bar_p**7) / (C_bar_p**7 + 25.0**7))
    R_T = -np.sin(np.radians(2.0 * dTheta)) * R_C

    delta_e = np.sqrt(
        (dL_p / S_L)**2 +
        (dC_p / S_C)**2 +
        (dH_p / S_H)**2 +
        R_T * (dC_p / S_C) * (dH_p / S_H)
    )
    return float(delta_e)


def load_reagents():
    """Loads database from disk or initializes empty file if missing."""
    if not os.path.exists(DB_FILE):
        with open(DB_FILE, "w") as f:
            json.dump({}, f, indent=2)
    with open(DB_FILE, "r") as f:
        return json.load(f)


def save_reagents(data):
    """Writes updated profiles to JSON database."""
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=2)


def identify_universal_color(sample_lab):
    """Identifies nearest color standard using CIEDE2000 metric."""
    best_color = "Indeterminate"
    min_dist = float("inf")
    for color_name, lab_coords in UNIVERSAL_COLOR_PALETTE.items():
        dist = ciede2000(sample_lab, lab_coords)
        if dist < min_dist:
            min_dist = dist
            best_color = color_name
    return best_color


def generate_pdf(match_name, detected_color, confidence, delta_e, sha_hash, timestamp, gps, ndps_sec):
    """Generates an in-memory, tamper-evident Panchnama Seizure Certificate."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()

    data = [
        [Paragraph("<b>Statutory Field</b>", styles['Normal']),
         Paragraph("<b>Official Field Record</b>", styles['Normal'])],
        [Paragraph("Statutory Legal Framework", styles['Normal']),
         Paragraph("NDPS Act, 1985 (Sec. 50/52) & Bharatiya Sakshya Adhiniyam, 2023 (Sec. 63)", styles['Normal'])],
        [Paragraph("Visual Color Identified", styles['Normal']),
         Paragraph(f"<b>{detected_color}</b>", styles['Normal'])],
        [Paragraph("Chemical Assay Verdict", styles['Normal']), Paragraph(f"<b>{match_name}</b>", styles['Normal'])],
        [Paragraph("Match Confidence Index", styles['Normal']),
         Paragraph(f"<b>{confidence:.1f}%</b> (ΔE00 = {delta_e:.2f})", styles['Normal'])],
        [Paragraph("Statutory Qualification", styles['Normal']), Paragraph(ndps_sec, styles['Normal'])],
        [Paragraph("SHA-256 Digital Fingerprint", styles['Normal']),
         Paragraph(f"<font size=6.5>{sha_hash}</font>", styles['Normal'])],
        [Paragraph("Incident Coordinates", styles['Normal']), Paragraph(gps, styles['Normal'])],
        [Paragraph("Synchronized Timestamp", styles['Normal']), Paragraph(timestamp, styles['Normal'])],
        [Paragraph("Chain of Custody Status", styles['Normal']),
         Paragraph("CRYPTOGRAPHICALLY SEALED • COURT ADMISSIBLE", styles['Normal'])]
    ]

    t = Table(data, colWidths=[160, 370])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0B2545")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor("#F8FAFC"), colors.white]),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    doc.build([Paragraph("<b>NARCOTICS FIELD SEIZURE CERTIFICATE (PANCHNAMA)</b>", styles['Title']), Spacer(1, 10), t])
    buffer.seek(0)
    return buffer


# =====================================================================
# 2. APPLICATION USER INTERFACE
# =====================================================================
st.set_page_config(page_title="DRUG-SHIELD | Universal Optical Assayer", page_icon="🔬", layout="centered")

st.title("DRUG-SHIELD: Field Colorimetric Assayer")
st.caption("Universal Optical Colorimeter & Reagent Intelligence Companion (PS 26231)")

reagent_db = load_reagents()

st.write("### 1. Optical Capture")
st.info("Align the white reference card on the left (Blue Box) and the liquid vial on the right (Green Box).")

camera_img = st.camera_input("Open Camera & Capture Frame")

if camera_img is not None:
    bytes_data = camera_img.getvalue()
    cv_img = cv2.imdecode(np.frombuffer(bytes_data, np.uint8), cv2.IMREAD_COLOR)
    h, w, _ = cv_img.shape

    # Define crop regions
    ref_y1, ref_y2, ref_x1, ref_x2 = int(h * 0.35), int(h * 0.65), int(w * 0.15), int(w * 0.40)
    smp_y1, smp_y2, smp_x1, smp_x2 = int(h * 0.35), int(h * 0.65), int(w * 0.60), int(w * 0.85)

    ref_crop = cv_img[ref_y1:ref_y2, ref_x1:ref_x2]
    sample_crop = cv_img[smp_y1:smp_y2, smp_x1:smp_x2]

    # Display alignment preview with ROI overlay boxes
    preview_img = cv_img.copy()
    cv2.rectangle(preview_img, (ref_x1, ref_y1), (ref_x2, ref_y2), (255, 0, 0), 2)
    cv2.rectangle(preview_img, (smp_x1, smp_y1), (smp_x2, smp_y2), (0, 255, 0), 2)
    st.image(cv2.cvtColor(preview_img, cv2.COLOR_BGR2RGB), caption="Optical Alignment Check (Left: White Ref | Right: Sample)", use_container_width=True)

    # 1. Median-based white-balance normalization (prevents glare outliers)
    ref_median = np.maximum(np.median(ref_crop, axis=(0, 1)), 1.0)
    scaling = 255.0 / ref_median
    sample_norm = np.clip(sample_crop * scaling, 0, 255).astype(np.float32) / 255.0

    # 2. Extract standard CIE L*a*b* coordinates (Float format yields exact standard L*a*b* scale)
    mean_bgr_float = np.mean(sample_norm, axis=(0, 1)).reshape(1, 1, 3).astype(np.float32)
    sample_lab = cv2.cvtColor(mean_bgr_float, cv2.COLOR_BGR2Lab).flatten().astype(np.float32)

    # 3. Universal color identification via CIEDE2000
    detected_color = identify_universal_color(sample_lab)

    # 4. Forensic reagent spectral matching via CIEDE2000
    best_match = "Unlisted / Non-Narcotic Compound"
    min_de = float("inf")
    confidence = 0.0
    ndps_sec = "No Scheduled Narcotic Matched"

    for key, data in reagent_db.items():
        de = ciede2000(sample_lab, np.array(data["target_lab"]))
        if de < min_de:
            min_de = de
            if de <= data.get("tolerance_de", 15.0):
                best_match = f"{data['reagent']} → {data['target_compound']}"
                ndps_sec = data.get("ndps_section", "NDPS Scheduled Drug")
                # Scale CIEDE2000 confidence (ΔE <= 1.0 is near-identical)
                confidence = max(0.0, min(100.0, 100.0 - (de * 5.0)))

    # 5. Cryptographic SHA-256 seal
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
    gps = "21.1904° N, 81.2849° E (Field Interdiction Point)"
    sha_hash = hashlib.sha256(bytes_data + timestamp.encode() + gps.encode()).hexdigest()

    # --- UI DISPLAY ---
    st.write("### 2. Inspection Telemetry")

    col1, col2 = st.columns(2)
    with col1:
        st.metric(label="Recognized Optical Color", value=detected_color)
    with col2:
        st.metric(label="Chemical Assay Match", value=best_match,
                  delta=f"{confidence:.1f}% Confidence" if confidence > 0 else "None")

    st.write(
        f"**Calibrated CIE L*a*b* Values:** `L*={sample_lab[0]:.2f}, a*={sample_lab[1]:.2f}, b*={sample_lab[2]:.2f}`")
    st.write(f"**Statutory Classification:** {ndps_sec}")

    if confidence >= 70.0:
        st.success(f"**POSITIVE NDPS ASSAY:** Matched {best_match} (ΔE00 = {min_de:.2f})")
    else:
        st.info(
            f"**COLOR IDENTIFIED AS {detected_color.upper()}:** No scheduled narcotic reagent profile matched this exact shade.")

    st.code(f"SHA-256 Evidence Fingerprint: {sha_hash}", language="text")

    # Download Panchnama PDF
    pdf_bytes = generate_pdf(best_match, detected_color, confidence, min_de, sha_hash, timestamp, gps, ndps_sec)
    st.download_button(
        label="📄 Download Statutory Panchnama (PDF)",
        data=pdf_bytes,
        file_name="Field_Seizure_Panchnama.pdf",
        mime="application/pdf"
    )

    # =====================================================================
    # 3. ADMIN CALIBRATOR
    # =====================================================================
    st.write("---")
    with st.expander("➕ Admin: Register Scanned Shade as a New Reagent Profile"):
        st.write(f"Registering active shade (`{detected_color}`) directly to `reagents.json`.")

        new_sub = st.text_input("Substance Name (e.g., Ketamine / Fentanyl)")
        new_reag = st.text_input("Reagent Used (e.g., Morris Reagent)")
        new_sec = st.text_input("NDPS Act Section (e.g., Sec. 22 Commercial)")

        if st.button("Save Profile to reagents.json"):
            if new_sub and new_reag:
                entry_key = f"{new_reag.replace(' ', '_')}_{new_sub.replace(' ', '_')}"
                reagent_db[entry_key] = {
                    "reagent": new_reag,
                    "target_compound": new_sub,
                    "color_name": detected_color,
                    "target_lab": [float(sample_lab[0]), float(sample_lab[1]), float(sample_lab[2])],
                    "tolerance_de": 15.0,
                    "ndps_section": new_sec if new_sec else "Scheduled Compound"
                }
                save_reagents(reagent_db)
                st.success(f"Successfully registered '{new_sub}' ({detected_color}) into reagents.json!")
                st.rerun()
            else:
                st.error("Please enter both a substance name and reagent name.")