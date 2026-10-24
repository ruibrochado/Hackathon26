import os, ssl, time
from dotenv import load_dotenv
import paho.mqtt.client as mqtt

load_dotenv()

ACTIONS = ['''DEFINE ACTION HotspotRouter
ON TOPIC "cidade-alerta/ocorrencias/novas" DO
    SET "cell" WITH (GET JSON "celula" IN PAYLOAD AS STRING)
    SET "cat" WITH (GET JSON "categoria_slug" IN PAYLOAD AS STRING)
    PUBLISH TOPIC "cidade-alerta/celulas/" + {cell} + "/" + {cat} + "/nova" WITH PAYLOAD''',

'''DEFINE ACTION HotspotCounter
ON TOPIC "cidade-alerta/celulas/+/+/nova" DO
    SET "cell" WITH TOPIC POSITION 3
    SET "cat" WITH TOPIC POSITION 4
    SET "count" WITH (GET TOPIC "cidade-alerta/celulas/+/+/contagem" AS INT)
    SET "count" WITH ({count} + 1)
    KEEP TOPIC "cidade-alerta/celulas/" + {cell} + "/" + {cat} + "/contagem" WITH {count}
    IF {count} == 3 THEN
        PUBLISH TOPIC "cidade-alerta/hotspots/" + {cell} + "/" + {cat} WITH {count}''']

def on_message(c, u, msg):
    print("RESPOSTA:", msg.payload.decode())

c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
c.username_pw_set(os.environ["MQTT_USERNAME"], os.environ["MQTT_PASSWORD"])
c.tls_set(cert_reqs=ssl.CERT_REQUIRED)
c.on_message = on_message
c.connect(os.environ["MQTT_HOST"], int(os.getenv("MQTT_PORT", "8883")), 60)
c.loop_start()
time.sleep(1)
c.subscribe("$SYS/Coreflux/Command/Output")

for action in ACTIONS:
    c.publish("$SYS/Coreflux/Command", "-addAction " + action, qos=1)
    time.sleep(2)

time.sleep(2)
c.loop_stop()
