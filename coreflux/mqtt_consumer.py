import os
import json
import ssl
import uuid
import logging
import re
import html
import unicodedata

from pathlib import Path
from datetime import datetime, timezone

import httpx
import paho.mqtt.client as mqtt
from dotenv import load_dotenv
from supabase import create_client


# ==========================================
# CONFIGURAÇÃO
# ==========================================

load_dotenv(Path(__file__).resolve().parent / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

MQTT_HOST = os.environ["MQTT_HOST"]
MQTT_PORT = int(os.getenv("MQTT_PORT", "8883"))
MQTT_USERNAME = os.environ["MQTT_USERNAME"]
MQTT_PASSWORD = os.environ["MQTT_PASSWORD"]

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

MQTT_TOPIC = "cidade-alerta/departamentos/+"
MQTT_TOPIC_HOTSPOTS = "cidade-alerta/hotspots/+/+"

# Alerta por email: usa a edge function "resend-email" do Supabase
HOTSPOT_ALERT_EMAIL = os.getenv("HOTSPOT_ALERT_EMAIL")

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)


# ==========================================
# PROCESSAR MENSAGENS
# ==========================================

def processar_ocorrencia(topic, payload):

    try:
        ocorrencia = json.loads(payload)

        issue_id = ocorrencia.get("id")

        # Validar identificador
        if not issue_id:
            logging.warning(
                "Mensagem ignorada: sem ID."
            )
            return

        try:
            issue_id = str(uuid.UUID(str(issue_id)))
        except (ValueError, TypeError, AttributeError):
            logging.warning(
                "Mensagem ignorada: ID não é UUID válido."
            )
            return

        # Identificar departamento pelo topic
        department = topic.rsplit("/", 1)[-1]

        departamentos_validos = {
            "obras",
            "infraestruturas",
            "ambiente",
            "eletricidade",
            "transito",
            "limpeza",
            "triagem"
        }

        if department not in departamentos_validos:
            logging.warning(
                "Departamento desconhecido: %s",
                department
            )
            return

        logging.info(
            "Ocorrência %s → Departamento: %s",
            issue_id,
            department
        )

        # Preparar dados para o Supabase
        resultado = {
            "issue_id": issue_id,
            "department": department,
            "priority": ocorrencia.get("prioridade"),
            "processing_status": "classified",
            "processed_at": datetime.now(
                timezone.utc
            ).isoformat()
        }

        # Inserir ou atualizar resultado
        response = (
            supabase
            .table("issue_automation_results")
            .upsert(
                resultado,
                on_conflict="issue_id"
            )
            .execute()
        )

        logging.info(
            "Resultado guardado no Supabase: %s",
            issue_id
        )

    except json.JSONDecodeError:
        logging.error("Payload MQTT não é JSON válido.")

    except Exception:
        logging.exception(
            "Erro ao processar mensagem MQTT."
        )


# ==========================================
# HOTSPOTS
# ==========================================

def slug(texto):
    """Mesmo slug usado no webhook.py (tem de ser igual)."""
    s = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_") or "outros"


def enviar_alerta_hotspot(celula, categoria, linhas):
    """Enviar email ao município a avisar que foi detetado um hotspot."""

    if not HOTSPOT_ALERT_EMAIL:
        logging.warning(
            "Email de hotspot não enviado: falta HOTSPOT_ALERT_EMAIL no .env."
        )
        return

    primeira = linhas[0]
    cidade = primeira.get("city") or "—"
    morada = primeira.get("address") or "—"
    nome_categoria = primeira.get("category") or categoria
    mapa = (
        "https://www.google.com/maps?q="
        f"{primeira.get('latitude')},{primeira.get('longitude')}"
    )

    itens = "".join(
        f"<li>{html.escape(l.get('title') or 'Sem título')}</li>"
        for l in linhas
    )

    agora = datetime.now().strftime("%d/%m/%Y às %H:%M")

    corpo = f"""
    <div style="font-family:Arial,Helvetica,sans-serif;max-width:560px;margin:0 auto;border:2px solid #d32f2f;border-radius:12px;overflow:hidden;">
      <div style="background:#d32f2f;color:#ffffff;padding:20px 24px;text-align:center;">
        <div style="font-size:14px;letter-spacing:2px;font-weight:bold;">🚨 ALERTA AUTOMÁTICO</div>
        <div style="font-size:28px;font-weight:bold;margin-top:6px;">HOTSPOT DETETADO</div>
      </div>

      <div style="padding:24px;text-align:center;">
        <div style="font-size:64px;font-weight:bold;color:#d32f2f;line-height:1;">{len(linhas)}</div>
        <div style="font-size:18px;margin-top:4px;">reports de <b>{html.escape(nome_categoria)}</b><br>na <b>mesma zona</b></div>

        <div style="background:#fff3f3;border-radius:8px;padding:14px;margin:20px 0;text-align:left;">
          📍 <b>{html.escape(morada)}</b><br>
          🏙️ {html.escape(cidade)}
        </div>

        <a href="{mapa}" style="display:inline-block;background:#d32f2f;color:#ffffff;text-decoration:none;font-weight:bold;font-size:16px;padding:14px 28px;border-radius:8px;">
          VER NO MAPA
        </a>

        <div style="text-align:left;margin-top:24px;">
          <b>Reports agrupados:</b>
          <ul style="margin-top:6px;">{itens}</ul>
        </div>

        <div style="background:#fff8e1;border-left:4px solid #f9a825;padding:12px;text-align:left;margin-top:16px;">
          <b>⚠️ Ação recomendada:</b> várias pessoas reportaram o mesmo problema no mesmo local.
          A prioridade destes reports foi elevada automaticamente — intervenção urgente aconselhada.
        </div>
      </div>

      <div style="background:#f5f5f5;color:#666;font-size:12px;padding:12px;text-align:center;">
        Detetado em tempo real pela Cidade Alerta com Coreflux · {agora}
      </div>
    </div>
    """

    try:
        resposta = httpx.post(
            f"{SUPABASE_URL}/functions/v1/resend-email",
            headers={
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "apikey": SUPABASE_KEY,
                "Content-Type": "application/json",
            },
            json={
                "to": HOTSPOT_ALERT_EMAIL,
                "subject": f"🚨 HOTSPOT: {len(linhas)} reports de {nome_categoria} na mesma zona ({cidade})",
                "html": corpo,
            },
            timeout=20,
        )
        if resposta.status_code >= 300:
            logging.error("resend-email falhou: %s %s", resposta.status_code, resposta.text)
        else:
            logging.info("Email de hotspot enviado para %s", HOTSPOT_ALERT_EMAIL)
    except Exception:
        logging.exception("Erro ao enviar email de hotspot.")


def processar_hotspot(topic):
    """Marcar como hotspot as ocorrências da mesma célula e categoria."""

    try:
        partes = topic.split("/")
        # cidade-alerta / hotspots / <celula> / <categoria>
        if len(partes) != 4:
            logging.warning("Topic de hotspot inesperado: %s", topic)
            return

        celula, categoria = partes[2], partes[3]

        if celula in ("null", "sem_local", "") or categoria in ("null", ""):
            logging.warning("Hotspot ignorado (célula/categoria inválida): %s", topic)
            return

        linhas = (
            supabase
            .table("issues")
            .select("id,category,title,address,city,latitude,longitude,is_hotspot")
            .eq("grid_cell", celula)
            .neq("status", "archived")
            .execute()
            .data
        )

        do_hotspot = [
            linha
            for linha in linhas
            if slug(linha.get("category") or "") == categoria
        ]
        ids = [linha["id"] for linha in do_hotspot]
        novos = [linha for linha in do_hotspot if not linha.get("is_hotspot")]

        if ids:
            (
                supabase
                .table("issues")
                .update({"is_hotspot": True})
                .in_("id", ids)
                .execute()
            )

        # Só avisar quando o hotspot é novo (evita emails repetidos)
        if novos:
            enviar_alerta_hotspot(celula, categoria, do_hotspot)

        logging.info(
            "Hotspot %s/%s: %d ocorrências marcadas",
            celula,
            categoria,
            len(ids)
        )

    except Exception:
        logging.exception("Erro ao processar hotspot.")


# ==========================================
# EVENTOS MQTT
# ==========================================

def on_connect(
    client,
    userdata,
    flags,
    reason_code,
    properties
):

    if reason_code == 0:

        logging.info(
            "Ligado à Coreflux Cloud!"
        )

        client.subscribe(
            [
                (MQTT_TOPIC, 1),
                (MQTT_TOPIC_HOTSPOTS, 1)
            ]
        )

        logging.info(
            "À escuta de: %s e %s",
            MQTT_TOPIC,
            MQTT_TOPIC_HOTSPOTS
        )

    else:
        logging.error(
            "Falha na ligação MQTT: %s",
            reason_code
        )


def on_message(client, userdata, msg):

    logging.info(
        "Mensagem recebida em: %s",
        msg.topic
    )

    if msg.topic.startswith("cidade-alerta/hotspots/"):
        processar_hotspot(msg.topic)
        return

    processar_ocorrencia(
        msg.topic,
        msg.payload.decode("utf-8")
    )


# ==========================================
# INICIAR CONSUMIDOR
# ==========================================

def main():

    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"cidade-alerta-consumer-{uuid.uuid4().hex[:6]}"
    )

    client.username_pw_set(
        MQTT_USERNAME,
        MQTT_PASSWORD
    )

    client.tls_set(
        cert_reqs=ssl.CERT_REQUIRED,
        tls_version=ssl.PROTOCOL_TLS_CLIENT
    )

    client.on_connect = on_connect
    client.on_message = on_message

    logging.info(
        "A ligar ao broker Coreflux..."
    )

    client.connect(
        MQTT_HOST,
        MQTT_PORT,
        60
    )

    client.loop_forever()


if __name__ == "__main__":
    main()