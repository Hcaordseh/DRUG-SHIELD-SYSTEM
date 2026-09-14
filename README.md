# 🔬 DRUG-SHIELD: Universal Field Colorimetric Assayer

**DRUG-SHIELD** is a Streamlit-powered forensic colorimeter and reagent intelligence companion designed to assist field interdiction teams in accurately analyzing chemical drug spot-tests. By standardizing color analysis through CIE $L^*a^*b^*$ metrics and CIEDE2000 calculations, DRUG-SHIELD removes human subjective error under varying lighting conditions.

---

## ✨ Key Features

* **📷 Dual-ROI Camera Capture:** Captures and aligns a reference white card and test vial simultaneously.
* **☀️ Dynamic White Balance:** Utilizes median-based channel normalization to neutralize ambient shadows and light glare.
* **🎨 Perceptual CIEDE2000 Color Matching:** Calculates true human-eye perceptual color differences ($\Delta E_{00}$) rather than raw RGB/Euclidean distances.
* **📄 Automated Panchnama PDF Generation:** Automatically outputs tamper-evident, court-admissible field seizure certificates via ReportLab.
* **🔒 Cryptographic SHA-256 Sealing:** Stamps digital evidence with a cryptographic fingerprint combining image data, timestamp, and spatial coordinates (Section 63, BSA 2023).
* **➕ Dynamic Reagent Registration:** In-app calibration tool to expand `reagents.json` with new reagent color profiles without rewriting code.

---

## 🛠️ Tech Stack

* **Frontend / Framework:** [Streamlit](https://streamlit.io/)
* **Computer Vision:** [OpenCV (cv2)](https://opencv.org/)
* **Numerical Computing:** [NumPy](https://numpy.org/)
* **PDF Document Engine:** [ReportLab](https://www.reportlab.com/)
* **Security & Integrity:** Standard Python `hashlib` (SHA-256)

---

## 📂 Project Structure

```text
├── app.py              # Main Streamlit application file
├── reagents.json       # Database storing reagent target L*a*b* coordinates
├── requirements.txt   # Python dependency list
└── README.md           # Project documentation
