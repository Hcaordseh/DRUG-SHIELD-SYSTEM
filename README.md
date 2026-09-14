**DRUG-SHIELD** is an AI-assisted, digital optical colorimeter designed for law enforcement officers and forensic field personnel. It automates chemical reagent test analysis, eliminating human color perception bias when identifying suspected controlled substances on-site.

### Core Capabilities

* **Glare-Resistant Optical Processing:** Crops dual Regions of Interest (ROI) for a white reference card and the liquid sample vial, applying median-based channel scaling to correct ambient lighting variances.
* **Perceptual CIEDE2000 Match Engine:** Converts optical data into standardized CIE $L^*a^*b^*$ coordinates and calculates the CIEDE2000 ($\Delta E_{00}$) perceptual distance to identify color shades and matched scheduled narcotics.
* **Statutory PDF Panchnama Generation:** Auto-generates court-admissible seizure certificates complete with timestamp, simulated GPS coordinates, matching metrics, and legal qualifications under the NDPS Act, 1985 & BSA, 2023.
* **Cryptographic Evidence Sealing:** Generates an immutable SHA-256 hash combining the raw image buffer, timestamp, and location data to maintain an unbroken chain of custody.
* **Field Reagent Calibrator:** Includes an admin panel to dynamically register newly scanned color profiles into `reagents.json` on the fly.

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
