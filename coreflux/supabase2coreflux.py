import os
import json
import ssl
import argparse

from dotenv import load_dotenv
from supabase import create_client
import paho.mqtt.client as mqtt

load_dotenv()
print("Supabase URL:", os.getenv("SUPABASE_URL"))

key = os.getenv("SUPABASE_KEY", "")

print("Chave configurada:", bool(key))
print("Tipo de chave:", (
    "sb_secret" if key.startswith("sb_secret_")
    else "sb_publishable" if key.startswith("sb_publishable_")
    else "JWT/Outro"
))


# Configuração Supabase
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

# Configuração Coreflux
MQTT_HOST = os.environ["MQTT_HOST"]
MQTT_PORT = int(os.getenv("MQTT_PORT", "8883"))
MQTT_USERNAME = os.environ["MQTT_USERNAME"]
MQTT_PASSWORD = os.environ["MQTT_PASSWORD"]

TOPIC = "cidade-alerta/ocorrencias/novas"


def obter_ocorrencia():
    supabase = create_client(
        SUPABASE_URL,
        SUPABASE_KEY
    )

    response = (
        supabase.table("issues")
        .select(
            "id,title,description,category,"
            "address,city,created_at"
        )
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )

    if not response.data:
        raise RuntimeError(
            "Nenhuma ocorrência acessível no Supabase."
        )

    return response.data[0]


def converter_ocorrencia(issue):
    return {
        "id": issue["id"],
        "categoria": issue["category"],
        "titulo": issue["title"],
        "descricao": issue.get("description") or "",
        "localizacao": issue.get("city") or "",
        "prioridade": "media"
    }


def publicar_coreflux(ocorrencia):
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2
    )

    client.username_pw_set(
        MQTT_USERNAME,
        MQTT_PASSWORD
    )

    client.tls_set(
        cert_reqs=ssl.CERT_REQUIRED,
        tls_version=ssl.PROTOCOL_TLS_CLIENT
    )

    client.connect(MQTT_HOST, MQTT_PORT, 60)
    client.loop_start()

    try:
        # Publicar apenas após estabelecer sessão MQTT
        import time

        for _ in range(100):
            if client.is_connected():
                break
            time.sleep(0.1)

        if not client.is_connected():
            raise RuntimeError(
                "Não foi possível ligar à Coreflux."
            )

        info = client.publish(
            TOPIC,
            json.dumps(
                ocorrencia,
                ensure_ascii=False
            ),
            qos=1
        )

        info.wait_for_publish(timeout=10)

        if not info.is_published():
            raise RuntimeError(
                "A publicação MQTT não foi confirmada."
            )

        print("Ocorrência publicada na Coreflux!")

    finally:
        client.disconnect()
        client.loop_stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--publish",
        action="store_true",
        help="Publicar a ocorrência na Coreflux"
    )

    args = parser.parse_args()

    ocorrencia = ocorrencia = {
    "id": "TEST-SUPABASE-001",
    "categoria": "Iluminação Pública",
    "titulo": "Teste de integração",
    "descricao": "Candeeiro avariado numa rua fictícia",
    "localizacao": "Localização de teste",
    "prioridade": "media"
}


    print("Ocorrência preparada:")
    print(json.dumps(
        ocorrencia,
        indent=2,
        ensure_ascii=False
    ))

    if args.publish:
        publicar_coreflux(ocorrencia)
    else:
        print(
            "\nModo de teste: nenhuma mensagem "
            "foi publicada."
        )
