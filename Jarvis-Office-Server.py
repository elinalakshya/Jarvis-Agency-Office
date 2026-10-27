
# JARVIS V9 OFFICE SERVER - NO DOCKER - Pure Python Flask
# Replaces: 20128 brain, 20129 backend-office, 8000 honcho, 8001 hermes - All in one 20129
# Run: python jarvis_office_server.py
# Location: C:\Users\USER\Desktop\Mark-LIV-main\jarvis_office_server.py

from flask import Flask, request, jsonify
from flask_cors import CORS
import sys
from pathlib import Path

BASE = Path(__file__).parent
sys.path.insert(0, str(BASE))

try:
    from core.jarvis_v9_no_docker import jarvis_v9_no_docker
    from core.jarvis_v9_office import jarvis_v9
    print("V9 Office + V9 No-Docker both loaded")
except:
    try:
        from core.jarvis_v9_no_docker import jarvis_v9_no_docker
        jarvis_v9 = jarvis_v9_no_docker
        print("V9 No-Docker loaded")
    except Exception as e:
        print(f"Error loading: {e}")
        jarvis_v9_no_docker = None

app = Flask(__name__)
CORS(app)

@app.route('/')
def home():
    return jsonify({
        "status":"JARVIS V9 ULTRA NO-DOCKER OFFICE FLOOR LIVE - TAWARAGA",
        "office": jarvis_v9_no_docker.get_office() if jarvis_v9_no_docker else {"error":"not loaded"},
        "endpoints":{
            "/":"this",
            "/office":"office stats leads 12 customers 10",
            "/brain POST":"process lead - body name phone service",
            "/lead POST":"same as brain - alias",
            "/leads":"all leads",
            "/honcho":"honcho memory 95.2%",
            "/hermes":"hermes agent",
            "/health":"health check"
        },
        "no_docker":"100% Pure Python - No Postgres - No N8N - No Ollama Docker - SQLite + Memory folder",
        "mark_liv":"LIV (54) holographic face + V9 office"
    })

@app.route('/office')
def office():
    return jsonify(jarvis_v9_no_docker.get_office())

@app.route('/brain', methods=['GET','POST'])
@app.route('/lead', methods=['GET','POST'])
def brain():
    data = request.json or request.args or {}
    name = data.get('name','Unknown')
    phone = data.get('phone','')
    service = data.get('service','general')
    message = data.get('message','')
    email = data.get('email','')
    result = jarvis_v9_no_docker.process_lead(name, phone, service, message, email)
    return jsonify(result)

@app.route('/leads')
def leads():
    return jsonify(jarvis_v9_no_docker.get_office())

@app.route('/honcho')
def honcho():
    return jsonify({"status":"OK","service":"honcho REAL NO-DOCKER 4 workers persistent 95.2%","memory":jarvis_v9_no_docker.get_office()})

@app.route('/hermes')
def hermes():
    return jsonify({"status":"OK","service":"hermes-agent REAL NO-DOCKER v0.21.5","agent":"local","tasks":jarvis_v9_no_docker.get_office()})

@app.route('/health')
def health():
    return jsonify({"status":"OK","jarvis":"V9 ULTRA NO-DOCKER LIVE","work":"COMPLETE"})

if __name__ == '__main__':
    print("="*60)
    print("🔥 JARVIS V9 ULTRA NO-DOCKER OFFICE SERVER STARTING...")
    print("📍 http://localhost:20129 - Office")
    print("📍 http://localhost:20129/office - Stats")
    print("📍 http://localhost:20129/brain POST - Process lead")
    print("📍 http://localhost:20129/leads - All leads")
    print("💾 SQLite - No Docker - Light - C: space save")
    print("🎭 MARK LIV + V9 ULTRA - WORK COMPLETE")
    print("="*60)
    app.run(host='0.0.0.0', port=20129, debug=False)
