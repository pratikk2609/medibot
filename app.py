from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
import os

load_dotenv()

app = Flask(__name__)

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///appointments.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Appointment model
class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(120), nullable=False)
    specialist = db.Column(db.String(120), nullable=False)
    date = db.Column(db.String(20), nullable=False)
    time = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(120), nullable=True)

with app.app_context():
    db.create_all()

# Dummy in-memory session tracking
user_sessions = {}

# Doctor specialties
available_doctors = [
    "General Physician", "Pediatrician", "Dentist", "Cardiologist",
    "Dermatologist", "Neurologist", "Orthopedic Surgeon", "ENT Specialist",
    "Psychiatrist", "Gynecologist", "Ophthalmologist"
]

# Email sender
def send_email(to_email, subject, body):
    sender_email = os.getenv("EMAIL_USER")  # Replace with your Gmail
    sender_password = os.getenv("EMAIL_PASS")  # Replace with your App Password

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'html'))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)
        print("✅ Email sent to", to_email)
    except Exception as e:
        print("❌ Error sending email:", str(e))

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    user_msg = request.json.get("message").strip()
    session_id = request.remote_addr

    if session_id not in user_sessions:
        user_sessions[session_id] = {"state": "idle"}

    session = user_sessions[session_id]

    # Show appointments
    if "appointments" in user_msg or "bookings" in user_msg or "show" in user_msg:
        appts = Appointment.query.filter_by(user_id=session_id).all()
        if not appts:
            return jsonify({"response": "📭 You have no appointments booked yet."})
        response = "📅 Your appointments:\n\n"
        for i, appt in enumerate(appts, 1):
            response += f"{i}. {appt.specialist} on {appt.date} at {appt.time}\n"
        return jsonify({"response": response})

    elif "book" in user_msg or "appointment" in user_msg:
        session["state"] = "booking_specialist"
        doc_list = "\n".join([f"{i+1}. {doc}" for i, doc in enumerate(available_doctors)])
        return jsonify({"response": f"Which specialist do you need?\n\n{doc_list}"})

    elif session["state"] == "booking_specialist":
        session["specialist"] = user_msg
        session["state"] = "booking_date"
        return jsonify({"response": f"What date would you like to book the {user_msg.title()} for? (e.g., 2025-04-10)"})

    elif session["state"] == "booking_date":
        session["date"] = user_msg
        session["state"] = "booking_time"
        return jsonify({"response": "Great! At what time? (e.g., 3:30 PM)"})

    elif session["state"] == "booking_time":
        session["time"] = user_msg
        session["state"] = "booking_email"
        return jsonify({"response": "Please enter your email so we can send a confirmation."})

    elif session["state"] == "booking_email":
        session["email"] = user_msg
        appt = Appointment(
            user_id=session_id,
            specialist=session["specialist"],
            date=session["date"],
            time=session["time"],
            email=session["email"]
        )
        db.session.add(appt)
        db.session.commit()

        # Send confirmation email
        email_body = f"""
        <h2>🩺 Appointment Confirmation</h2>
        <p><strong>Specialist:</strong> {appt.specialist}</p>
        <p><strong>Date:</strong> {appt.date}</p>
        <p><strong>Time:</strong> {appt.time}</p>
        <p>Thank you for using MediBot!</p>
        """
        send_email(appt.email, "✅ Your Appointment is Confirmed", email_body)

        session["state"] = "idle"
        return jsonify({
            "response": f"✅ Appointment booked with {appt.specialist} on {appt.date} at {appt.time}.\n📧 A confirmation email has been sent to {appt.email}."
        })

    else:
        return jsonify({
            "response": "👋 Hi! I can help you book doctor appointments.\nTry typing 'book appointment' or 'show appointments'."
        })

if __name__ == "__main__":
    app.run(debug=True)
