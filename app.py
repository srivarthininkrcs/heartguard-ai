from flask import Flask, render_template, request, jsonify
import uuid
from datetime import datetime
import sqlite3
import os
from twilio.rest import Client
from flask import send_file
from reportlab.pdfgen import canvas
from io import BytesIO
from reportlab.lib.styles import getSampleStyleSheet
styles = getSampleStyleSheet()

TWILIO_SID = os.environ.get("TWILIO_SID")
TWILIO_TOKEN = os.environ.get("TWILIO_TOKEN")
TWILIO_NUMBER = os.environ.get("TWILIO_NUMBER")

client = Client(TWILIO_SID, TWILIO_TOKEN) if TWILIO_SID and TWILIO_TOKEN else None
    
app = Flask(__name__)

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
    "time": "--"
}

patients_records = {}

@app.route("/monitor", methods=["GET", "POST"])
def monitor():

    if request.method == "POST":
        patient_id = request.form["patient_id"]
        hr = int(request.form["heart_rate"])
        bp = request.form["bp"]
        spo2 = int(request.form["spo2"])
        temp = float(request.form["temperature"])
        rr = int(request.form["respiratory_rate"])

        sys_bp = int(bp.split("/")[0])

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

        status = "HIGH RISK" if risk >= 50 else "LOW RISK"
        
        latest.update({
            "name": request.form["name"],
            "phone": request.form["phone"],
            "age": request.form["age"],
            "sex": request.form["sex"],
            "heart_rate": hr,
            "bp": bp,
            "spo2": spo2,
            "temperature": temp,
            "respiratory_rate": rr,
            "risk": risk,
            "status": status,
            "time": datetime.now().strftime("%H:%M:%S")
        })
        patients_records[patient_id] = latest.copy()

        # Emergency SMS
        if risk >= 50:

            if not client:
                print("TWILIO CLIENT NOT CONNECTED")

            else:
                try:
                    message = client.messages.create(
                       body=f"🚨 HEARTGUARD AI ALERT 🚨\nPatient: {latest['name']}\nRisk: {risk}%\nStatus: {status}",
                       from_=TWILIO_NUMBER,
                       to=latest["phone"]
                )

                    print("SMS SENT:", message.sid)

                except Exception as e:
                    print("SMS ERROR:", e)
        conn = sqlite3.connect("database.db")
        conn.execute(
            "INSERT INTO patients (name, risk, status, time) VALUES (?, ?, ?, ?)",
            (latest["name"], risk, status, latest["time"])
        )
        conn.commit()
        conn.close()

    return render_template(
        "monitor.html",
        data=latest,
        patient_id=patient_id
    )

@app.route("/details")
def details():
    return render_template("details.html", data=latest)

@app.route("/emergency")
def emergency():
    return render_template("emergency.html", data=latest)

@app.route("/health-data")
def health_data():
    patient_id = request.args.get("patient_id")

    # Remote page uses patient_id
    if patient_id:
        data = patients_records.get(patient_id)

        if data is not None:
            return jsonify(data)

    # Main monitoring page uses latest
    return jsonify(latest)

@app.route("/remote-monitor")
def remote_monitor():
    patient_id = request.args.get("patient_id")

    data = patients_records.get(patient_id)

    if data is None:
        data = {
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
            "time": "--"
        }

    return render_template(
        "remote_monitor.html",
        data=data,
        patient_id=patient_id
    )



@app.route("/risk-trend")
def risk_trend():
    conn = sqlite3.connect("database.db")
    rows = conn.execute(
        "SELECT risk FROM patients ORDER BY id DESC LIMIT 7"
    ).fetchall()
    conn.close()
    return jsonify([int(r[0]) for r in rows[::-1]])

@app.route("/download-report")
def download_report():
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.utils import ImageReader
    from io import BytesIO

    d = latest
    buf = BytesIO()
    w, h = A4
    pdf = canvas.Canvas(buf, pagesize=A4)

    # Dark background
    pdf.setFillColor(colors.HexColor("#061426"))
    pdf.rect(0, 0, w, h, fill=1)

    # Title
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 20)
    pdf.drawString(30, h-45, "HEARTGUARD AI")
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(30, h-70, "HEART RISK ASSESSMENT REPORT")

    # Patient
    pdf.setFont("Helvetica", 10)
    pdf.drawString(30, h-100, f"Patient: {d['name']}")
    pdf.drawString(220, h-100, f"Age: {d['age']}")
    pdf.drawString(320, h-100, f"Sex: {d['sex']}")

    # Risk
    pdf.setFillColor(colors.HexColor("#0D1D32"))
    pdf.roundRect(30, h-240, 250, 120, 10, fill=1)

    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(50, h-145, "AI Risk Prediction")

    risk = int(d["risk"])
    pdf.setFont("Helvetica-Bold", 32)
    pdf.setFillColor(
        colors.HexColor("#FF4757") if risk >= 50
        else colors.HexColor("#00E676")
    )
    pdf.drawString(100, h-190, f"{risk}%")

    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawString(100, h-215, d["status"])

    # Vitals
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawString(310, h-145, "Health Parameters")

    pdf.setFont("Helvetica", 10)
    y = h-165
    vitals = [
        f"Heart Rate: {d['heart_rate']} bpm",
        f"Blood Pressure: {d['bp']}",
        f"SpO2: {d['spo2']} %",
        f"Temperature: {d['temperature']} C",
        f"Respiratory Rate: {d['respiratory_rate']} /min"
    ]

    for item in vitals:
        pdf.drawString(310, y, item)
        y -= 18

    # Heart image
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawString(55, 485, "3D Heart Visualization")
    heart = os.path.join(app.root_path, "static", "heart3d.png")
    if os.path.exists(heart):
        pdf.drawImage(
            ImageReader(heart),
            55, 300,
            width=170,
            height=170,
            preserveAspectRatio=True,
            mask="auto"
        )

    # ECG
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawString(310, 570, "Key Risk Factors")
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawString(260, 440, "Live ECG Monitor")

    pdf.setStrokeColor(colors.HexColor("#00E676"))
    pdf.setLineWidth(2)

    path = pdf.beginPath()
    for i in range(300):
        x = 260 + i
        p = i % 60
        y = 400

        if 20 <= p < 25:
            y = 425
        elif 25 <= p < 30:
            y = 375
        elif 30 <= p < 35:
            y = 415

        if i == 0:
            path.moveTo(x, y)
        else:
            path.lineTo(x, y)

    pdf.drawPath(path)

    # Suggestions
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawString(30, 260, "AI Suggestions")

    pdf.setFont("Helvetica", 10)
    pdf.drawString(40, 240, "• Regular health monitoring")
    pdf.drawString(40, 222, "• Maintain balanced nutrition")
    pdf.drawString(40, 204, "• Adequate rest and hydration")

    # Alert
    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawString(30, 165, "Recent Alert")

    pdf.setFont("Helvetica", 10)
    pdf.drawString(40, 145, d["status"])
    pdf.drawString(40, 128, f"Last Assessment: {d['time']}")

    # Footer
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawString(310, 165, "Risk Trend")
    # Risk Trend
    conn = sqlite3.connect("database.db")
    rows = conn.execute(
        "SELECT risk FROM patients ORDER BY id DESC LIMIT 7"
    ).fetchall()
    conn.close()

    v = [int(x[0]) for x in rows[::-1]]

    # Grid + scale
    pdf.setFont("Helvetica", 7)
    pdf.setFillColor(colors.white)

    for n in range(0, 101, 25):
        y = 45 + n * 0.9
        pdf.setStrokeColor(colors.HexColor("#244A70"))
        pdf.line(300, y, 555, y)
        pdf.drawString(280, y-2, f"{n}%")

    # Trend
    if v:
        path = pdf.beginPath()
        path.moveTo(305, 45 + v[0]*0.9)

        for i in range(1, len(v)):
            path.lineTo(305 + i*38, 45 + v[i]*0.9)

        pdf.setStrokeColor(colors.HexColor("#FF4757"))
        pdf.setLineWidth(3)
        pdf.drawPath(path)

        # Points + values
        for i, value in enumerate(v):
            x = 305 + i*38
            y = 45 + value*0.9

            pdf.setFillColor(colors.HexColor("#FF4757"))
            pdf.circle(x, y, 4, fill=1)

        pdf.setFillColor(colors.white)
        pdf.setFont("Helvetica-Bold", 8)
        pdf.drawString(x-8, y+8, f"{value}%")
    pdf.setFillColor(colors.HexColor("#00E676"))
    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawString(30, 35, "HeartGuard AI • Smart Heart Monitoring")

    pdf.save()
    buf.seek(0)

    return send_file(
        buf,
        as_attachment=True,
        download_name="HeartGuard_AI_Report.pdf",
        mimetype="application/pdf"
    )

    return render_template("monitor.html", data=latest)

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
        "time": "--"
    }

    return render_template(
        "monitor.html",
        data=blank_data,
        patient_id=patient_id
    )

@app.route("/dashboard")
def dashboard():
    total = len(patients_records)

    high = sum(
        1 for p in patients_records.values()
        if p["status"] == "HIGH RISK"
    )

    low = sum(
        1 for p in patients_records.values()
        if p["status"] == "LOW RISK"
    )

    return render_template(
        "dashboard.html",
        total=total,
        high=high,
        low=low
    )

if __name__ == "__main__":
    app.run()