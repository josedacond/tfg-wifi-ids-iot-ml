# =============================================================================
#    TFG DASHBOARD — IoT Monitor + Alertas IDS + Control IPS
# =============================================================================

from flask import Flask, render_template, request, redirect, url_for, session
from flask_socketio import SocketIO
import paho.mqtt.client as mqtt
import json
import time
from functools import wraps

# =============================================================================
#                           CONFIGURACIÓN
# =============================================================================

MQTT_BROKER = "127.0.0.1"
MQTT_PORT = 1883
MQTT_TOPIC_SENSOR = "tfg/sensor1"
MQTT_TOPIC_ALERTA = "tfg/alerta"
MQTT_TOPIC_IPS_CONTROL = "tfg/ips_control"
MQTT_TOPIC_IPS_STATUS = "tfg/ips_status"

DASHBOARD_USER = "admin"
DASHBOARD_PASS = "tfg2026"

# =============================================================================
#                          FLASK + SOCKETIO
# =============================================================================

app = Flask(__name__)
app.secret_key = "clave_secreta_tfg_2026"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

sensor_state = {"connected": False, "last_seen": 0, "data": None}
security_state = {"status": "ok", "last_alert": None, "alert_count": 0}
ips_state = {"activo": False, "amenaza": False, "bssid": ""}

# =============================================================================
#                          AUTENTICACIÓN
# =============================================================================

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        if (request.form["username"] == DASHBOARD_USER and 
            request.form["password"] == DASHBOARD_PASS):
            session["logged_in"] = True
            return redirect(url_for("dashboard"))
        else:
            error = "Credenciales incorrectas"
    return render_template("login.html", error=error)

@app.route("/logout")
def logout():
    session.pop("logged_in", None)
    return redirect(url_for("login"))

# =============================================================================
#                             RUTAS
# =============================================================================

@app.route("/")
@login_required
def dashboard():
    return render_template("dashboard.html")

@app.route("/api/status")
@login_required
def api_status():
    if time.time() - sensor_state["last_seen"] > 5:
        sensor_state["connected"] = False
    return json.dumps({
        "sensor": sensor_state,
        "security": security_state,
        "ips": ips_state
    })

# =============================================================================
#                          MQTT → SOCKETIO
# =============================================================================

def on_mqtt_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print(f"[MQTT] Conectado al broker {MQTT_BROKER}")
        client.subscribe(MQTT_TOPIC_SENSOR)
        client.subscribe(MQTT_TOPIC_ALERTA)
        client.subscribe(MQTT_TOPIC_IPS_STATUS)
        print(f"[MQTT] Suscrito a: sensores, alertas, ips_status")
    else:
        print(f"[MQTT] Error de conexión, código: {rc}")

def on_mqtt_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        
        if msg.topic == MQTT_TOPIC_SENSOR:
            sensor_state["connected"] = True
            sensor_state["last_seen"] = time.time()
            sensor_state["data"] = payload
            socketio.emit("sensor_data", payload)
            
        elif msg.topic == MQTT_TOPIC_ALERTA:
            if payload.get("nivel") == "critico":
                security_state["status"] = "attack"
                security_state["last_alert"] = payload
                security_state["alert_count"] += 1
                print(f"[IDS] 🚨 ALERTA: {payload.get('tipo', '?').upper()}")
            else:
                security_state["status"] = "ok"
            
            socketio.emit("ids_alert", payload)
            
        elif msg.topic == MQTT_TOPIC_IPS_STATUS:
            ips_state["activo"] = payload.get("ips_activo", False)
            ips_state["amenaza"] = payload.get("amenaza", False)
            ips_state["bssid"] = payload.get("bssid", "")
            print(f"[IPS] Estado: activo={ips_state['activo']}, amenaza={ips_state['amenaza']}")
            
            socketio.emit("ips_status", ips_state)
            
    except Exception as e:
        print(f"[MQTT] Error: {e}")

mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
mqtt_client.on_connect = on_mqtt_connect
mqtt_client.on_message = on_mqtt_message

# =============================================================================
#              CONTROL IPS DESDE DASHBOARD (SocketIO → MQTT)
# =============================================================================

@socketio.on('ips_toggle')
def handle_ips_toggle(data):
    comando = data.get('comando', 'off')
    print(f"[Dashboard] IPS toggle: {comando}")
    payload = json.dumps({"comando": comando})
    mqtt_client.publish(MQTT_TOPIC_IPS_CONTROL, payload)

# =============================================================================
#                              MAIN
# =============================================================================

if __name__ == "__main__":
    print("\n" + "="*50)
    print("  TFG Dashboard — IoT Monitor + IDS + IPS")
    print("="*50)
    print(f"  MQTT Broker:  {MQTT_BROKER}:{MQTT_PORT}")
    print(f"  Sensores:     {MQTT_TOPIC_SENSOR}")
    print(f"  Alertas IDS:  {MQTT_TOPIC_ALERTA}")
    print(f"  Control IPS:  {MQTT_TOPIC_IPS_CONTROL}")
    print(f"  Login:        {DASHBOARD_USER} / {DASHBOARD_PASS}")
    print(f"  URL:          http://192.168.50.1:8080")
    print("="*50 + "\n")
    
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
    mqtt_client.loop_start()
    
    socketio.run(app, host="0.0.0.0", port=8080, allow_unsafe_werkzeug=True)
