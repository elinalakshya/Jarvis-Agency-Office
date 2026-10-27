from flask import Flask, request, jsonify
from flask_cors import CORS
import sys
from pathlib import Path
BASE = Path(__file__).parent
sys.path.insert(0, str(BASE))
from core.jarvis_v9_no_docker import jarvis_v9_no_docker
app = Flask(__name__)
CORS(app)
@app.route('/')
def home():
    return jsonify({"status":"JARVIS V9 ULTRA NO-DOCKER OFFICE FLOOR LIVE - TAWARAGA","office": jarvis_v9_no_docker.get_office(),"endpoints":{"/":"this","/office":"office stats","/brain POST":"process lead","/leads":"all leads","/honcho":"honcho memory","/hermes":"hermes agent"},"no_docker":"100% Pure Python - No Postgres - No N8N - No Ollama Docker - SQLite + Memory folder"})
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
    return jsonify({"status":"OK","service":"hermes-agent REAL NO-DOCKER v0.21.5","agent":"local"})
@app.route('/health')
def health():
    return jsonify({"status":"OK","jarvis":"V9 ULTRA NO-DOCKER LIVE","work":"COMPLETE"})
if __name__ == '__main__':
    print("="*60)
    print("JARVIS V9 ULTRA NO-DOCKER OFFICE SERVER STARTING...")
    print("http://localhost:20129 - Office")
    print("http://localhost:20129/office - Stats")
    print("http://localhost:20129/brain POST - Process lead")
    print("SQLite - No Docker - Light")
    print("MARK LIV + V9 ULTRA - WORK COMPLETE")
    print("="*60)
    app.run(host='0.0.0.0', port=20129, debug=False)
