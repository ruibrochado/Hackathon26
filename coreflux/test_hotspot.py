import json
import os
import ssl
import time
import uuid

from dotenv import load_dotenv
import paho.mqtt.client as mqtt

load_dotenv()

TOPIC_NOVAS = "cidade-alerta/ocorrencias/novas"

# Cada execução usa uma célula nova, porque o contador fica guardado no broker
CELULA = f"teste_{int(time.time())}"
CATEGORIA_SLUG = "buraco"


def on_connect(client, userdata, flags, reason_code, properties):
    print("Ligado:", reason_code)
    client.subscribe("cidade-alerta/hotspots/#", qos=1)
    client.subscribe("cidade-alerta/celulas/#", qos=1)


def on_message(client, userdata, msg):
    print(f"  <- {msg.topic}  {msg.payload.decode()[:80]}")


client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.username_pw_set(os.environ["MQTT_USERNAME"], os.environ["MQTT_PASSWORD"])
client.tls_set(cert_reqs=ssl.CERT_REQUIRED)
client.on_connect = on_connect
client.on_message = on_message
client.connect(os.environ["MQTT_HOST"], int(os.getenv("MQTT_PORT", "8883")), 60)
client.loop_start()
time.sleep(2)

print(f"Célula de teste: {CELULA}\n")

for i in range(1, 4):
    ocorrencia = {
        "id": str(uuid.uuid4()),
        "categoria": "Buraco na estrada",
        "categoria_slug": CATEGORIA_SLUG,
        "celula": CELULA,
        "titulo": f"Buraco de teste {i}",
        "descricao": "Teste de hotspot",
        "localizacao": "Porto",
        "prioridade": "media",
    }
    print(f"-> a enviar report {i}/3")
    client.publish(TOPIC_NOVAS, json.dumps(ocorrencia, ensure_ascii=False), qos=1)
    time.sleep(2)

print("\nÀ espera de resposta do broker...")
time.sleep(4)
client.loop_stop()
client.disconnect()
print(f"\nProcura por: cidade-alerta/hotspots/{CELULA}/{CATEGORIA_SLUG}")
