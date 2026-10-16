from flask import Flask, request, jsonify
from flask_cors import CORS
import joblib
import pandas as pd
import sqlite3
from scipy import integrate
import traceback
import bcrypt
import google.generativeai as genai
import os
from pathlib import Path
import traceback as _traceback


app = Flask(__name__)

# Attempt to load a simple env file (KEY=VALUE lines) in the backend folder
def load_local_env(filename="env"):
    p = Path(__file__).resolve().parent / filename
    if not p.exists():
        return
    try:
        with p.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                # Only set if not already in environment
                os.environ.setdefault(key, val)
    except Exception:
        pass


# Load `backend/env` if present so keys like GEMINI_API_KEY are available
load_local_env()

# ===============================
# Battery parameters
# ===============================
Qn = 2.0
R = 0.5
Vmin = 2.5
Vmax = 4.2

# ===============================
# Database helper
# ===============================
def get_db():
    db_path = Path(__file__).resolve().parent / "database.db"
    return sqlite3.connect(str(db_path), check_same_thread=False)

# ===============================
# Lazy-loaded ML model
# ===============================
model = None
last_model_load_error = None

def get_model():
    global model, last_model_load_error
    if model is not None:
        return model
    try:
        model = joblib.load("battery_rul_model.pkl")
        last_model_load_error = None
        return model
    except Exception:
        last_model_load_error = traceback.format_exc()
        return None

# ===============================
# AUTH APIs
# ===============================
@app.route("/register", methods=["POST", "OPTIONS"])
def register():
    if request.method == "OPTIONS":
        # CORS preflight
        return '', 204
    data = request.json
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"error": "Email and password required"}), 400

    hashed_pw = bcrypt.hashpw(password.encode(), bcrypt.gensalt())

    try:
        db = get_db()
        db.execute(
            "INSERT INTO users (email, password) VALUES (?, ?)",
            (email, hashed_pw)
        )
        db.commit()
        return jsonify({"message": "User registered successfully"})
    except sqlite3.IntegrityError:
        return jsonify({"error": "User already exists"}), 409
    except Exception as e:
        # return traceback for easier debugging (only in dev)
        return jsonify({"error": "Database write failed", "details": _traceback.format_exc()}), 500


@app.route("/login", methods=["POST"])
def login():
    data = request.json
    email = data.get("email")
    password = data.get("password")
    if not email or not password:
        return jsonify({"error": "Email and password required"}), 400

    try:
        db = get_db()
        cur = db.cursor()
        cur.execute("SELECT password FROM users WHERE email=?", (email,))
        row = cur.fetchone()

        if not row:
            return jsonify({"error": "Invalid credentials"}), 401

        stored_pw = row[0]
        # Ensure stored_pw is bytes
        if isinstance(stored_pw, memoryview):
            stored_pw = stored_pw.tobytes()

        if not bcrypt.checkpw(password.encode(), stored_pw):
            return jsonify({"error": "Invalid credentials"}), 401

        return jsonify({"message": "Login successful"})
    except Exception:
        return jsonify({"error": "Login failed", "details": _traceback.format_exc()}), 500

@app.route("/logout", methods=["POST"])
def logout():
    return jsonify({"message": "Logout successful"})

    

# ===============================
# BATTERY PREDICTION API
# ===============================
@app.route("/predict", methods=["POST"])
def predict():
    m = get_model()
    if m is None:
        return jsonify({
            "error": "Model load failed",
            "details": last_model_load_error
        }), 500

    payload = request.get_json() if request.is_json else request.form.to_dict()

    data = pd.DataFrame({
        'Cycle_Index': [payload.get('Cycle_Index')],
        'Discharge Time (s)': [payload.get('Discharge Time (s)')],
        'Decrement 3.6-3.4V (s)': [payload.get('Decrement 3.6-3.4V (s)')],
        'Max. Voltage Dischar. (V)': [payload.get('Max. Voltage Dischar. (V)')],
        'Min. Voltage Charg. (V)': [payload.get('Min. Voltage Charg. (V)')],
        'Time at 4.15V (s)': [payload.get('Time at 4.15V (s)')],
        'Time constant current (s)': [payload.get('Time constant current (s)')],
        'Charging time (s)': [payload.get('Charging time (s)')]
    })

    # Convert to numeric
    for col in data.columns:
        data[col] = pd.to_numeric(data[col], errors="coerce")

    prediction = m.predict(data)[0]

    # Battery calculations
    I = prediction / R
    SoE = (Qn - I) / Qn
    SoC = max(0, min(100, SoE * 100))   # FIXED
    Voc = Vmax - (Vmax - Vmin) * SoE
    SoH = Voc / Vmax

    return jsonify({
        "prediction": float(prediction),
        "SoE": round(float(SoE), 4),
        "SoH": round(float(SoH), 4),
        "SoC": round(float(SoC), 2)
    })


# ===============================
# CHATBOT API
# ===============================
# Use environment variable for the Gemini API key (guarded)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model_gemini = genai.GenerativeModel("gemini-2.5-flash-lite")
    except Exception:
        model_gemini = None
else:
    model_gemini = None
@app.route("/chat", methods=["POST"])
def chatbot():
    data = request.get_json()
    user_message = data.get("message", "").strip()

    if not user_message:
        return jsonify({"reply": "Please ask a valid battery-related question."})

    if model_gemini is None:
        return jsonify({
            "reply": "Chatbot is not configured. GEMINI_API_KEY is missing or invalid.",
            "error": "GEMINI_API_KEY not set"
        }), 503

    try:
        prompt = f"""
        You are an expert battery assistant.
        Answer clearly in 4 to 6 sentences.
        Do not use symbols or bullet points.
        Focus on lithium-ion battery health, RUL, SoH, and charging practices.

        User question:
        {user_message}
        """

        response = model_gemini.generate_content(prompt)

        # Response object shape may vary; attempt to access text safely
        reply = getattr(response, 'text', None)
        if reply is None:
            # fall back to dict-like access
            try:
                reply = response['candidates'][0]['output'][0]
            except Exception:
                reply = str(response)

        reply = reply.strip()

        return jsonify({"reply": reply})

    except Exception as e:
        return jsonify({
            "reply": "Sorry, I am unable to respond right now.",
            "error": str(e)
        }), 500



# ===============================
# RUN SERVER
# ===============================
if __name__ == "__main__":
    # Apply CORS globally after all routes are registered
    from flask_cors import CORS
    CORS(app, supports_credentials=True)
    app.run(debug=True)
