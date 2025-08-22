from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import google.generativeai as genai
import json
from dotenv import load_dotenv
import os
import pymysql

load_dotenv()

# Configure Gemini
gemini_key = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=gemini_key)

# Flask setup
app = Flask(__name__, static_folder=".", static_url_path="")
CORS(app)

# MySQL connection function
def get_db_connection():
    return pymysql.connect(
        host=os.getenv("MYSQL_HOST"),
        port=int(os.getenv("MYSQL_PORT", 26615)),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD"),
        database=os.getenv("MYSQL_DB"),
        cursorclass=pymysql.cursors.DictCursor,
        ssl={"ssl": {}}  # required by Aiven
    )

# ---------------- Serve Frontend Pages ----------------
@app.route("/")
def index():
    return send_from_directory(".", "Web_Interface.html")

@app.route("/All_BMIS.html")
def all_reports_page():
    
    return send_from_directory(".", "All_BMIS.html")

@app.route("/Analysis_BMI.html")
def analysis_page():
    return send_from_directory(".", "Analysis_BMI.html")

# ---------------- API: Add BMI report ----------------
@app.route("/bmi/add", methods=["POST"])
def add_bmi_report():
    try:
        name = request.form.get('name')
        weight = float(request.form.get('weight'))
        height = float(request.form.get('height'))
        bmi = weight / (height * height)

        # Prompt for Gemini
        prompt = f"""
        You are a BMI health report generator.
        Return ONLY valid JSON. No explanations. No markdown.
        {{
          "name": "{name}",
          "weight": {weight},
          "height": {height},
          "bmi": {bmi:.2f},
          "bmi_status": "string",
          "diet_suggestion": "string",
          "workout_suggestion": "string"
        }}
        """

        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(prompt)

        raw_text = response.text.strip()

        # Clean JSON if wrapped in ```json ... ```
        if raw_text.startswith("```"):
            raw_text = raw_text.strip("`").strip()
            if raw_text.lower().startswith("json"):
                raw_text = raw_text[4:].strip()

        try:
            bmi_report = json.loads(raw_text)
        except json.JSONDecodeError as e:
            return jsonify({
                "status": "failed",
                "error": "Invalid JSON from Gemini",
                "raw_response": raw_text,
                "details": str(e)
            })

        # Save into MySQL
        conn = get_db_connection()
        with conn.cursor() as cursor:
            sql = """
            INSERT INTO bmi_reports (name, weight, height, bmi, bmi_status, diet_suggestion, workout_suggestion)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(sql, (
                bmi_report["name"],
                bmi_report["weight"],
                bmi_report["height"],
                bmi_report["bmi"],
                bmi_report["bmi_status"],
                bmi_report["diet_suggestion"],
                bmi_report["workout_suggestion"]
            ))
        conn.commit()
        conn.close()

        return jsonify({"status": "success", "bmi_report": bmi_report})

    except Exception as e:
        return jsonify({"status": "failed", "error": str(e)})

# ---------------- API: Get all BMI reports ----------------
@app.route("/bmi/all", methods=["GET"])
def get_all_bmi_reports():
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM bmi_reports ORDER BY created_at DESC")
            rows = cursor.fetchall()
        conn.close()
        return jsonify(rows)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ---------------- Run ----------------
if __name__ == "__main__":
    app.run(port=5000, debug=True, host="0.0.0.0")
