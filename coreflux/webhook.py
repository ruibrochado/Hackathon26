import os
import json
import ssl
import time
import hmac
import re
import unicodedata

from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from dotenv import load_dotenv

import paho.mqtt.client as mqtt


# Carregar configurações
load_dotenv(Path(__file__).resolve().parent / ".env")

app = FastAPI(title="Cidade Alerta - Coreflux")

MQTT_HOST = os.environ["MQTT_HOST"]
MQTT_PORT = int(os.getenv("MQTT_PORT", "8883"))
MQTT_USERNAME = os.environ["MQTT_USERNAME"]
MQTT_PASSWORD = os.environ["MQTT_PASSWORD"]

WEBHOOK_SECRET = os.environ["WEBHOOK_SECRET"]

TOPIC = "cidade-alerta/ocorrencias/novas"


# Formato do webhook Supabase
class SupabaseWebhook(BaseModel):
    type: str
    table: str
    schema: str
    record: dict
    old_record: dict | None = None


def slug(texto):
    """Texto seguro para usar num segmento de topic MQTT."""
    s = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_") or "outros"


def calcular_celula(issue):
    """Célula de ~100 m (3 casas decimais), igual à coluna grid_cell do Supabase."""
    try:
        lat = float(issue["latitude"])
        lng = float(issue["longitude"])
        return f"{lat:.3f}_{lng:.3f}"
    except (KeyError, TypeError, ValueError):
        return "sem_local"


def converter_ocorrencia(issue):
    """Converter os campos do Supabase para a Coreflux."""

    return {
        "id": issue["id"],
        "categoria": issue["category"],
        "categoria_slug": slug(issue["category"]),
        "celula": calcular_celula(issue),
        "titulo": issue["title"],
        "descricao": issue.get("description") or "",
        "localizacao": issue.get("city") or "",
        "prioridade": "media"
    }


def publicar_mqtt(ocorrencia):
    """Publicar ocorrência no broker Coreflux Cloud."""

    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2
    )

    client.username_pw_set(
        MQTT_USERNAME,
        MQTT_PASSWORD
    )

    client.tls_set(
        cert_reqs=ssl.CERT_REQUIRED
    )

    try:
        client.connect(
            MQTT_HOST,
            MQTT_PORT,
            60
        )

        client.loop_start()

        for _ in range(100):
            if client.is_connected():
                break

            time.sleep(0.1)

        if not client.is_connected():
            raise RuntimeError("Ligação MQTT não estabelecida")

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
            raise RuntimeError("Publicação MQTT não confirmada")

    finally:
        client.disconnect()
        client.loop_stop()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/webhook/ocorrencias")
def receber_ocorrencia(
    payload: SupabaseWebhook,
    x_webhook_secret: str | None = Header(default=None)
):

    # Validar autorização
    if (
        not x_webhook_secret
        or not hmac.compare_digest(
            x_webhook_secret,
            WEBHOOK_SECRET
        )
    ):
        raise HTTPException(
            status_code=401,
            detail="Não autorizado"
        )

    # Validar origem lógica do evento
    if (
        payload.type != "INSERT"
        or payload.schema != "public"
        or payload.table != "issues"
    ):
        raise HTTPException(
            status_code=400,
            detail="Evento inválido"
        )

    issue = payload.record

    # Validar campos obrigatórios
    if not all(
        isinstance(issue.get(field), str) and issue[field]
        for field in ("id", "title", "category")
    ):
        raise HTTPException(
            status_code=422,
            detail="Campos obrigatórios em falta"
        )

    ocorrencia = converter_ocorrencia(issue)

    try:
        publicar_mqtt(ocorrencia)

    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Não foi possível publicar na Coreflux"
        )

    return {
        "success": True,
        "issue_id": ocorrencia["id"],
        "message": "Ocorrência enviada à Coreflux"
    }