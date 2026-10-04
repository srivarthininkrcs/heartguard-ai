from flask import Flask, render_template, request, jsonify, send_file
import uuid
from datetime import datetime
import sqlite3
import os
import json

from twilio.rest import Client

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from io import BytesIO


# =========================================================
# FLASK APP
# =========================================================

app = Flask(__name__)


# =========================================================
# TWILIO SETTINGS
# Emergency WhatsApp alert ONLY
# =========================================================

TWILIO_SID = os.environ.get("TWILIO_SID")
TWILIO_TOKEN = os.environ.get("TWILIO_TOKEN")
TWILIO_NUMBER = os.environ.get("TWILIO_NUMBER")

client = (
    Client(TWILIO_SID, TWILIO_TOKEN)
    if TWILIO_SID and TWILIO_TOKEN
    else None
)


# =========================================================
# DATABASE
# =========================================================

def init_db():
    conn = sqlite3.connect("database.db")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            risk INTEGER,
            status TEXT,
            time TEXT
        )
    """)

    conn.commit()
    conn.close()


init_db()


# =========================================================
# DEFAULT DATA
# =========================================================

latest = {
    "name": "--",
    "phone": "--",
    "age": "--",
    "sex": "--",
    "heart_rate": 0,
    "bp": "--",
    "spo2": 0,
    "temperature": 0,
    "respiratory_rate": 0,
    "risk": 0,
    "status": "WAITING",
    "time": "--",
    "doctor_response": "",
    "doctor_response_time": ""
}


# =========================================================
# TEMPORARY PATIENT RECORDS
# =========================================================

patients_records = {}


# =========================================================
# PHONE NUMBER FORMAT
# =========================================================

def format_whatsapp_number(phone):

    if not phone:
        return None

    phone = str(phone).strip()

    phone = (
        phone
        .replace(" ", "")
        .replace("-", "")
        .replace("(", "")
        .replace(")", "")
    )

    if phone.startswith("+91"):
        return phone

    elif phone.startswith("91") and len(phone) == 12:
        return "+" + phone

    elif len(phone) == 10 and phone.isdigit():
        return "+91" + phone

    else:
        print("INVALID PHONE NUMBER:", phone)
        return None


# =========================================================
# SEND TWILIO WHATSAPP ALERT
# ONLY HIGH RISK
# =========================================================

def send_whatsapp_alert(phone, risk):

    print("----------------------------------------")
    print("WHATSAPP ALERT PROCESS STARTED")
    print("ORIGINAL PHONE:", phone)

    if not client:
        print("TWILIO CLIENT NOT CONNECTED")
        print("----------------------------------------")
        return False

    if not TWILIO_NUMBER:
        print("TWILIO_NUMBER NOT FOUND")
        print("----------------------------------------")
        return False

    whatsapp_number = format_whatsapp_number(phone)

    if not whatsapp_number:
        print("INVALID PATIENT PHONE NUMBER")
        print("----------------------------------------")
        return False

    print("FORMATTED PATIENT NUMBER:", whatsapp_number)
    print("TWILIO SENDER:", TWILIO_NUMBER)

    try:

        message = client.messages.create(
            from_=f"whatsapp:{TWILIO_NUMBER}",
            to=f"whatsapp:{whatsapp_number}",
            content_sid="HXb5b62575e6e4ff6129ad7c8efe1f983e",
            content_variables=json.dumps({
                "1": datetime.now().strftime("%d/%m/%Y"),
                "2": f"HeartGuard AI Risk: {risk}%"
            })
        )

        print("WHATSAPP SENT SUCCESSFULLY")
        print("MESSAGE SID:", message.sid)
        print("----------------------------------------")

        return True

    except Exception as e:

        print("WHATSAPP ERROR:", str(e))
        print("----------------------------------------")

        return False


# =========================================================
# MONITOR
# =========================================================

@app.route("/monitor", methods=["GET", "POST"])
def monitor():

    patient_id = request.args.get("patient_id")

    if not patient_id:
        patient_id = uuid.uuid4().hex

    # =====================================================
    # POST - START LIVE ASSESSMENT
    # =====================================================

    if request.method == "POST":

        patient_id = request.form.get("patient_id")

        if not patient_id:
            patient_id = uuid.uuid4().hex

        # -------------------------------------------------
        # GET FORM VALUES
        # -------------------------------------------------

        name = request.form.get("name", "--")
        phone = request.form.get("phone", "--")
        age = request.form.get("age", "--")
        sex = request.form.get("sex", "--")

        hr = int(request.form.get("heart_rate", 0))
        bp = request.form.get("bp", "--")
        spo2 = int(request.form.get("spo2", 0))
        temp = float(request.form.get("temperature", 0))
        rr = int(request.form.get("respiratory_rate", 0))

        # -------------------------------------------------
        # SYSTOLIC BP
        # -------------------------------------------------

        try:
            sys_bp = int(bp.split("/")[0])
        except:
            sys_bp = 0

        # -------------------------------------------------
        # RISK CALCULATION
        # -------------------------------------------------

        risk = 0

        if hr < 60 or hr > 100:
            risk += 20

        if sys_bp >= 140:
            risk += 25

        if spo2 < 95:
            risk += 30

        if temp < 36 or temp > 37.5:
            risk += 15

        if rr < 12 or rr > 20:
            risk += 10

        risk = min(risk, 100)

        # -------------------------------------------------
        # RISK STATUS
        # -------------------------------------------------

        if risk >= 50:
            status = "HIGH RISK"
        else:
            status = "LOW RISK"

        # -------------------------------------------------
        # CURRENT PATIENT DATA
        # -------------------------------------------------

        patient_data = {
            "name": name,
            "phone": phone,
            "age": age,
            "sex": sex,
            "heart_rate": hr,
            "bp": bp,
            "spo2": spo2,
            "temperature": temp,
            "respiratory_rate": rr,
            "risk": risk,
            "status": status,
            "time": datetime.now().strftime("%H:%M:%S"),
            "doctor_response": "",
            "doctor_response_time": ""
        }

        # -------------------------------------------------
        # UPDATE LATEST
        # -------------------------------------------------

        latest.clear()
        latest.update(patient_data)

        # -------------------------------------------------
        # SAVE PATIENT RECORD
        # -------------------------------------------------

        patients_records[patient_id] = patient_data.copy()

        # -------------------------------------------------
        # TWILIO WHATSAPP ALERT
        # ONLY HIGH RISK
        # -------------------------------------------------

        if risk >= 50:

            print("")
            print("HIGH RISK DETECTED")
            print("PATIENT NAME:", name)
            print("PATIENT PHONE:", phone)
            print("PATIENT ID:", patient_id)
            print("RISK:", risk)

            send_whatsapp_alert(phone, risk)

        else:

            print("")
            print("LOW RISK - WHATSAPP ALERT NOT SENT")

        # -------------------------------------------------
        # DATABASE
        # -------------------------------------------------

        conn = sqlite3.connect("database.db")

        conn.execute(
            """
            INSERT INTO patients
            (name, risk, status, time)
            VALUES (?, ?, ?, ?)
            """,
            (
                name,
                risk,
                status,
                patient_data["time"]
            )
        )

        conn.commit()
        conn.close()

    # -----------------------------------------------------
    # RETURN MONITOR PAGE
    # -----------------------------------------------------

    return render_template(
        "monitor.html",
        data=patients_records.get(patient_id, latest),
        patient_id=patient_id
    )


# =========================================================
# DETAILS
# =========================================================

@app.route("/details")
def details():

    return render_template(
        "details.html",
        data=latest
    )


# =========================================================
# EMERGENCY PAGE
# =========================================================

@app.route("/emergency")
def emergency():

    patient_id = request.args.get("patient_id")

    data = None

    if patient_id:
        data = patients_records.get(patient_id)

    if data is None:
        data = latest

    print("----------------------------------------")
    print("EMERGENCY PAGE")
    print("PATIENT ID:", patient_id)
    print("PATIENT PHONE:", data.get("phone"))
    print("----------------------------------------")

    return render_template(
        "emergency.html",
        data=data,
        patient_id=patient_id
    )


# =========================================================
# DOCTOR RESPONSE
# SAVE + SEND WHATSAPP
# =========================================================

@app.route("/doctor-response", methods=["POST"])
def doctor_response():

    # Supports JSON from remote_monitor.html
    # and form data if used by another page.

    data = request.get_json(silent=True)

    if data is None:
        data = request.form.to_dict()

    patient_id = data.get("patient_id")

    treatment = str(
        data.get("message", "")
    ).strip()

    # -----------------------------------------------------
    # Validate patient ID
    # -----------------------------------------------------

    if not patient_id:

        return jsonify({
            "success": False,
            "message": "Patient ID missing"
        }), 400

    # -----------------------------------------------------
    # Validate treatment
    # -----------------------------------------------------

    if not treatment:

        return jsonify({
            "success": False,
            "message": "Please enter treatment or medical advice"
        }), 400

    # -----------------------------------------------------
    # Find exact patient
    # -----------------------------------------------------

    patient_data = patients_records.get(patient_id)

    if not patient_data:

        return jsonify({
            "success": False,
            "message": "Patient not found"
        }), 404

    # -----------------------------------------------------
    # SAVE DOCTOR RESPONSE
    # -----------------------------------------------------

    patient_data["doctor_response"] = treatment

    patient_data["doctor_response_time"] = (
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )

    patients_records[patient_id] = patient_data

    # -----------------------------------------------------
    # CREATE MONITORING LINK
    # -----------------------------------------------------

    monitoring_link = (
    "https://heartguard-ai-1-5puu.onrender.com"
    + "/remote-monitor?patient_id="
    + str(patient_id)
)
    # -----------------------------------------------------
    # PATIENT PHONE NUMBER
    # -----------------------------------------------------

    phone = str(
        patient_data.get("phone", "")
    ).strip()

    # -----------------------------------------------------
    # SEND WHATSAPP
    # -----------------------------------------------------

    whatsapp_sent = False

    if phone:

        try:

            whatsapp_number = phone

            # Convert 10 digit Indian number to +91
            if whatsapp_number.startswith("0"):
                whatsapp_number = whatsapp_number[1:]

            if (
                len(whatsapp_number) == 10
                and whatsapp_number.isdigit()
            ):
                whatsapp_number = "+91" + whatsapp_number

            elif (
                whatsapp_number.startswith("91")
                and len(whatsapp_number) == 12
            ):
                whatsapp_number = "+" + whatsapp_number

            elif not whatsapp_number.startswith("+"):
                whatsapp_number = "+" + whatsapp_number

            whatsapp_body = (
                "HeartGuard AI\n\n"
                "Doctor Response:\n"
                + treatment
                + "\n\n"
                "Patient Monitoring Link:\n"
                + monitoring_link
            )

            client.messages.create(
                from_=f"whatsapp:{TWILIO_NUMBER}",
                to=f"whatsapp:{whatsapp_number}",
                body=whatsapp_body
            )

            whatsapp_sent = True

            print("----------------------------------------")
            print("WHATSAPP RESPONSE SENT")
            print("PATIENT ID:", patient_id)
            print("PHONE:", whatsapp_number)
            print("MONITORING LINK:", monitoring_link)
            print("----------------------------------------")

        except Exception as e:

            print("----------------------------------------")
            print("WHATSAPP SEND ERROR")
            print("ERROR:", e)
            print("----------------------------------------")

    # -----------------------------------------------------
    # RESPONSE
    # -----------------------------------------------------

    return jsonify({

        "success": True,

        "message":
            "Doctor response saved and WhatsApp sent successfully"
            if whatsapp_sent
            else
            "Doctor response saved, but WhatsApp could not be sent",

        "doctor_response":
            treatment,

        "doctor_response_time":
            patient_data["doctor_response_time"],

        "monitoring_link":
            monitoring_link,

        "whatsapp_sent":
            whatsapp_sent
    })


# =========================================================
# HEALTH DATA
# =========================================================

@app.route("/health-data")
def health_data():

    patient_id = request.args.get("patient_id")

    if not patient_id:

        return jsonify({
            "status": "WAITING"
        })

    data = patients_records.get(patient_id)

    if not data:

        return jsonify({
            "name": "--",
            "phone": "--",
            "age": "--",
            "sex": "--",
            "heart_rate": 0,
            "bp": "--",
            "spo2": 0,
            "temperature": 0,
            "respiratory_rate": 0,
            "risk": 0,
            "status": "WAITING",
            "time": "--",
            "doctor_response": "",
            "doctor_response_time": ""
        })

    return jsonify(data)


# =========================================================
# REMOTE MONITORING
# =========================================================

@app.route("/remote-monitor")
def remote_monitor():

    patient_id = request.args.get("patient_id")

    if not patient_id:
        return "Patient ID is missing", 400

    data = patients_records.get(patient_id)

    if not data:
        return "Patient data not found", 404

    return render_template(
        "remote_monitor.html",
        data=data,
        patient_id=patient_id
    )


# =========================================================
# RISK TREND
# =========================================================

@app.route("/risk-trend")
def risk_trend():

    conn = sqlite3.connect("database.db")

    rows = conn.execute(
        """
        SELECT risk
        FROM patients
        ORDER BY id DESC
        LIMIT 7
        """
    ).fetchall()

    conn.close()

    return jsonify([
        int(r[0])
        for r in rows[::-1]
    ])


# =========================================================
# DOWNLOAD REPORT
# =========================================================

@app.route("/download-report")
def download_report():

    patient_id = request.args.get("patient_id")

    if patient_id:
        d = patients_records.get(patient_id)
    else:
        d = latest

    if not d:
        return "Patient data not found", 404

    buf = BytesIO()

    pdf = canvas.Canvas(
        buf,
        pagesize=A4
    )

    w, h = A4

    # -----------------------------------------------------
    # DARK BACKGROUND
    # -----------------------------------------------------

    pdf.setFillColor(
        colors.HexColor("#061426")
    )

    pdf.rect(
        0,
        0,
        w,
        h,
        fill=1
    )

    # -----------------------------------------------------
    # TITLE
    # -----------------------------------------------------

    pdf.setFillColor(colors.white)

    pdf.setFont(
        "Helvetica-Bold",
        20
    )

    pdf.drawString(
        30,
        h - 45,
        "HEARTGUARD AI"
    )

    pdf.setFont(
        "Helvetica-Bold",
        16
    )

    pdf.drawString(
        30,
        h - 70,
        "HEART RISK ASSESSMENT REPORT"
    )

    # -----------------------------------------------------
    # PATIENT
    # -----------------------------------------------------

    pdf.setFont(
        "Helvetica",
        10
    )

    pdf.drawString(
        30,
        h - 100,
        f"Patient: {d['name']}"
    )

    pdf.drawString(
        220,
        h - 100,
        f"Age: {d['age']}"
    )

    pdf.drawString(
        320,
        h - 100,
        f"Sex: {d['sex']}"
    )

    # -----------------------------------------------------
    # RISK
    # -----------------------------------------------------

    pdf.setFillColor(
        colors.HexColor("#0D1D32")
    )

    pdf.roundRect(
        30,
        h - 240,
        250,
        120,
        10,
        fill=1
    )

    pdf.setFillColor(colors.white)

    pdf.setFont(
        "Helvetica-Bold",
        14
    )

    pdf.drawString(
        50,
        h - 145,
        "AI Risk Prediction"
    )

    risk = int(d["risk"])

    pdf.setFont(
        "Helvetica-Bold",
        32
    )

    if risk >= 50:

        pdf.setFillColor(
            colors.HexColor("#FF4757")
        )

    else:

        pdf.setFillColor(
            colors.HexColor("#00E676")
        )

    pdf.drawString(
        100,
        h - 190,
        f"{risk}%"
    )

    pdf.setFont(
        "Helvetica-Bold",
        13
    )

    pdf.drawString(
        100,
        h - 215,
        d["status"]
    )

    # -----------------------------------------------------
    # HEALTH PARAMETERS
    # -----------------------------------------------------

    pdf.setFillColor(colors.white)

    pdf.setFont(
        "Helvetica-Bold",
        13
    )

    pdf.drawString(
        310,
        h - 145,
        "Health Parameters"
    )

    pdf.setFont(
        "Helvetica",
        10
    )

    y = h - 165

    vitals = [
        f"Heart Rate: {d['heart_rate']} bpm",
        f"Blood Pressure: {d['bp']}",
        f"SpO2: {d['spo2']} %",
        f"Temperature: {d['temperature']} C",
        f"Respiratory Rate: {d['respiratory_rate']} /min"
    ]

    for item in vitals:

        pdf.drawString(
            310,
            y,
            item
        )

        y -= 18

    # -----------------------------------------------------
    # HEART IMAGE
    # -----------------------------------------------------

    pdf.setFillColor(colors.white)

    pdf.setFont(
        "Helvetica-Bold",
        13
    )

    pdf.drawString(
        55,
        485,
        "3D Heart Visualization"
    )

    heart = os.path.join(
        app.root_path,
        "static",
        "heart3d.png"
    )

    if os.path.exists(heart):

        pdf.drawImage(
            ImageReader(heart),
            55,
            300,
            width=170,
            height=170,
            preserveAspectRatio=True,
            mask="auto"
        )

    # -----------------------------------------------------
    # ECG
    # -----------------------------------------------------

    pdf.setFillColor(colors.white)

    pdf.setFont(
        "Helvetica-Bold",
        13
    )

    pdf.drawString(
        310,
        570,
        "Key Risk Factors"
    )

    pdf.drawString(
        260,
        440,
        "Live ECG Monitor"
    )

    pdf.setStrokeColor(
        colors.HexColor("#00E676")
    )

    pdf.setLineWidth(2)

    path = pdf.beginPath()

    for i in range(300):

        x = 260 + i
        p = i % 60
        y_ecg = 400

        if 20 <= p < 25:
            y_ecg = 425

        elif 25 <= p < 30:
            y_ecg = 375

        elif 30 <= p < 35:
            y_ecg = 415

        if i == 0:
            path.moveTo(x, y_ecg)
        else:
            path.lineTo(x, y_ecg)

    pdf.drawPath(path)

    # -----------------------------------------------------
    # SUGGESTIONS
    # -----------------------------------------------------

    pdf.setFillColor(colors.white)

    pdf.setFont(
        "Helvetica-Bold",
        13
    )

    pdf.drawString(
        30,
        260,
        "AI Suggestions"
    )

    pdf.setFont(
        "Helvetica",
        10
    )

    pdf.drawString(
        40,
        240,
        "Regular health monitoring"
    )

    pdf.drawString(
        40,
        222,
        "Maintain balanced nutrition"
    )

    pdf.drawString(
        40,
        204,
        "Adequate rest and hydration"
    )

    # -----------------------------------------------------
    # ALERT
    # -----------------------------------------------------

    pdf.setFont(
        "Helvetica-Bold",
        13
    )

    pdf.drawString(
        30,
        165,
        "Recent Alert"
    )

    pdf.setFont(
        "Helvetica",
        10
    )

    pdf.drawString(
        40,
        145,
        d["status"]
    )

    pdf.drawString(
        40,
        128,
        f"Last Assessment: {d['time']}"
    )

    # -----------------------------------------------------
    # RISK TREND
    # -----------------------------------------------------

    pdf.setFillColor(colors.white)

    pdf.setFont(
        "Helvetica-Bold",
        13
    )

    pdf.drawString(
        310,
        165,
        "Risk Trend"
    )

    conn = sqlite3.connect("database.db")

    rows = conn.execute(
        """
        SELECT risk
        FROM patients
        ORDER BY id DESC
        LIMIT 7
        """
    ).fetchall()

    conn.close()

    values = [
        int(x[0])
        for x in rows[::-1]
    ]

    pdf.setFont(
        "Helvetica",
        7
    )

    for n in range(0, 101, 25):

        y_graph = 45 + n * 0.9

        pdf.setStrokeColor(
            colors.HexColor("#244A70")
        )

        pdf.line(
            300,
            y_graph,
            555,
            y_graph
        )

        pdf.setFillColor(colors.white)

        pdf.drawString(
            280,
            y_graph - 2,
            f"{n}%"
        )

    # -----------------------------------------------------
    # TREND GRAPH
    # -----------------------------------------------------

    if values:

        path = pdf.beginPath()

        path.moveTo(
            305,
            45 + values[0] * 0.9
        )

        for i in range(1, len(values)):

            path.lineTo(
                305 + i * 38,
                45 + values[i] * 0.9
            )

        pdf.setStrokeColor(
            colors.HexColor("#FF4757")
        )

        pdf.setLineWidth(3)

        pdf.drawPath(path)

        for i, value in enumerate(values):

            x = 305 + i * 38
            y_graph = 45 + value * 0.9

            pdf.setFillColor(
                colors.HexColor("#FF4757")
            )

            pdf.circle(
                x,
                y_graph,
                4,
                fill=1
            )

            pdf.setFillColor(colors.white)

            pdf.setFont(
                "Helvetica-Bold",
                8
            )

            pdf.drawString(
                x - 8,
                y_graph + 8,
                f"{value}%"
            )

    # -----------------------------------------------------
    # FOOTER
    # -----------------------------------------------------

    pdf.setFillColor(
        colors.HexColor("#00E676")
    )

    pdf.setFont(
        "Helvetica-Bold",
        9
    )

    pdf.drawString(
        30,
        35,
        "HeartGuard AI • Smart Heart Monitoring"
    )

    pdf.save()

    buf.seek(0)

    return send_file(
        buf,
        as_attachment=True,
        download_name="HeartGuard_AI_Report.pdf",
        mimetype="application/pdf"
    )


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():

    patient_id = uuid.uuid4().hex

    blank_data = {
        "name": "--",
        "phone": "--",
        "age": "--",
        "sex": "--",
        "heart_rate": 0,
        "bp": "--",
        "spo2": 0,
        "temperature": 0,
        "respiratory_rate": 0,
        "risk": 0,
        "status": "WAITING",
        "time": "--",
        "doctor_response": "",
        "doctor_response_time": ""
    }

    return render_template(
        "monitor.html",
        data=blank_data,
        patient_id=patient_id
    )


# =========================================================
# DASHBOARD
# =========================================================

@app.route("/dashboard")
def dashboard():

    total = len(patients_records)

    high = sum(
        1
        for p in patients_records.values()
        if p["status"] == "HIGH RISK"
    )

    low = sum(
        1
        for p in patients_records.values()
        if p["status"] == "LOW RISK"
    )

    return render_template(
        "dashboard.html",
        total=total,
        high=high,
        low=low
    )


# =========================================================
# RUN APP
# =========================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=int(
            os.environ.get(
                "PORT",
                5000
            )
        )
    )