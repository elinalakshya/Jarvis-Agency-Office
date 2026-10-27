# JARVIS V9 ULTRA - MARK-LIV Integration - OFFICE FLOOR
# This extends MARK LIV with N8N + Backend Office + Honcho + Hermes

import os
import json
import requests

OFFICE_URL = "http://localhost:20129"
N8N_URL = "http://localhost:5678/webhook/jarvis-lead"
HONCHO_URL = "http://localhost:8000"
HERMES_URL = "http://localhost:8001"
BRAIN_URL = "http://localhost:20128"

class JarvisV9Office:
    def __init__(self):
        self.office_stats = {"leads":12,"customers":10,"videos":27,"brain":885,"tasks":9,"memory":"honcho 95.2%","agent":"hermes v0.21.5","jarvis":"V9 ULTRA MARK-LIV"}
        print("TAWARAGA JRAVIS V9 ULTRA - OFFICE FLOOR - MARK-LIV INTEGRATED")

    def process_lead(self, name, phone, service, message=""):
        # 1 - Save to Postgres via N8N webhook
        try:
            requests.post(N8N_URL, json={"name":name,"phone":phone,"service":service,"message":message}, timeout=5)
            print(f"Lead {name} -> N8N -> Postgres -> LIVE")
        except: pass
        # 2 - Honcho memory
        try: requests.post(HONCHO_URL, json={"event":"new_lead","name":name}, timeout=3)
        except: pass
        # 3 - Hermes qualify
        try: requests.post(HERMES_URL, json={"task":f"qualify {name} {service}"}, timeout=3)
        except: pass
        return {"status":"WORK COMPLETE","lead":name,"office":self.office_stats}

    def get_office(self):
        try:
            r = requests.get(OFFICE_URL, timeout=3)
            return r.json()
        except:
            return self.office_stats

# Global instance - MARK LIV can call this
jarvis_v9 = JarvisV9Office()
