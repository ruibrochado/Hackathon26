import json
import os
import ssl

from dotenv import load_dotenv
import paho.mqtt.client as mqtt

load_dotenv()

BROKER = os.environ["MQTT_HOST"]
PORT = int(os.getenv("MQTT_PORT", "8883"))
USERNAME = os.environ["MQTT_USERNAME"]
PASSWORD = os.environ["MQTT_PASSWORD"]

TOPIC = "cidade-alerta/ocorrencias/novas"


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print("✅ Ligado à Coreflux Cloud!")
    else:
        print(f"❌ Ligação MQTT rejeitada: {reason_code}")


client = mqtt.Client(
    mqtt.CallbackAPIVersion.VERSION2
)

client.username_pw_set(
    USERNAME,
    PASSWORD
)

# MQTT sobre TLS
client.tls_set(
    cert_reqs=ssl.CERT_REQUIRED,
    tls_version=ssl.PROTOCOL_TLS_CLIENT
)

client.on_connect = on_connect

print("A ligar à Coreflux Cloud...")

client.connect(BROKER, PORT, 60)
client.loop_start()

try:
    # Esperar pela confirmação da ligação MQTT
    import time

    for _ in range(50):
        if client.is_connected():
            break
        time.sleep(0.1)

    if not client.is_connected():
        raise RuntimeError("Não foi possível estabelecer a sessão MQTT.")

    ocorrencia = {
        "id": "TEST-CLOUD-001",
        "categoria": "Iluminação Pública",
        "descricao": "Candeeiro avariado junto a uma escola",
        "localizacao": "Porto",
        "prioridade": "media"
    }

    info = client.publish(
        TOPIC,
        json.dumps(ocorrencia, ensure_ascii=False),
        qos=1
    )

    info.wait_for_publish(timeout=10)

    if info.is_published():
        print("✅ Ocorrência enviada para a Coreflux!")
    else:
        print("❌ Não foi confirmada a publicação.")

finally:
    client.disconnect()
    client.loop_stop()
