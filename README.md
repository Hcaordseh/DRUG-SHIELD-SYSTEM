### `README.md`
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

```

## 🚀 Quickstart Guide (Local Installation)

### 1. Prerequisites

Ensure you have **Python 3.9+** installed on your system.

### 2. Clone the Repository

```bash
git clone [https://github.com/your-username/drug-shield.git](https://github.com/your-username/drug-shield.git)
cd drug-shield

```

### 3. Create a Virtual Environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate

```

### 4. Install Dependencies

```bash
pip install -r requirements.txt

```

### 5. Run the Streamlit Application

```bash
streamlit run app.py

```

Open your browser at `http://localhost:8501`.

---

## 📦 Streamlit Cloud Deployment

To host this application for public access (enabling mobile browser camera support over HTTPS):

1. **Push Code to GitHub:** Ensure `app.py`, `reagents.json`, and `requirements.txt` are committed to a public or private GitHub repository.
2. **`requirements.txt` Configuration:** Verify your dependencies include:
```text
streamlit
opencv-python-headless
numpy
reportlab

```


*(Note: Use `opencv-python-headless` to avoid missing server display library errors on Linux).*
3. **Deploy via Streamlit Cloud:**
* Go to [share.streamlit.io](https://share.streamlit.io/).
* Select **New app** > Select your **Repository**, **Branch** (`main`), and set **Main file path** to `app.py`.
* Click **Deploy!**



---

## 📖 How to Use

1. **Capture:** Point the camera so that the white reference card falls within the **Blue Box (Left)** and the reagent vial falls within the **Green Box (Right)**.
2. **Inspect:** View the real-time CIE $L^*a^*b^*$ coordinates, matched chemical profile, confidence score, and statutory classification.
3. **Export:** Click **Download Statutory Panchnama (PDF)** to generate the official seizure certificate.
4. **Calibrate (Admin):** Expand the bottom panel to save unrecognized shades directly into `reagents.json` for future automated matching.

```

```
