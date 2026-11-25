"""
Cloud Function

Se activa automáticamente cuando se sube un archivo a un bucket de
Cloud Storage (evento google.cloud.storage.object.v1.finalized).

Qué hace:
  1. Extrae metadatos del archivo: nombre, tamaño y tipo.
  2. Registra cada evento en Cloud Logging con logs (INFO / WARNING / ERROR).
  3. Manejo de errores: valida el evento, registra el
     fallo con traceback y lo propaga para que Pub/Sub / Cloud
     Functions lo reintente.

Despliegue y pruebas: ver README.md en esta misma carpeta.
"""

import json
import logging
import traceback

import functions_framework

import os

from datetime import datetime, timezone

import functions_framework
import google.auth
from googleapiclient.discovery import build


APPS_SCRIPT_URL = os.environ.get("APPS_SCRIPT_URL", "")
AUTH_TOKEN = os.environ.get("AUTH_TOKEN", "")

# ID del Sheet donde se registran los archivos. En local va en .env
# (SPREADSHEET_ID). En GCP va como variable de entorno en el deploy.
# Es solo la parte entre /d/ y /edit de la URL del Sheet.
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID", "")
SHEET_NAME = os.environ.get("SHEET_NAME", "Sheet1")

# Logging estructurado: Cloud Logging recoge stdout y lo indexa.
# Nivel INFO en producción; DEBUG solo para pruebas locales.
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("process-file-upload")


def _event_attr(cloud_event, name, default):
    """Lee id/type del evento, sea un objeto falso, un CloudEvent real
    (donde van en _attributes) o un dict."""
    value = getattr(cloud_event, name, None)
    if value:
        return value
    attrs = getattr(cloud_event, "_attributes", None)
    if isinstance(attrs, dict) and attrs.get(name):
        return attrs[name]
    if isinstance(cloud_event, dict):
        return cloud_event.get(name, default)
    return default

def _safe_int(value, field_name, event_id):
    """Convierte tamaño a int; si viene mal, loguea WARNING y devuelve None."""
    if value is None:
        logger.warning(
            json.dumps(
                {
                    "event": "metadata_missing",
                    "event_id": event_id,
                    "field": field_name,
                    "message": f"Campo '{field_name}' ausente en el evento",
                }
            )
        )
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        logger.warning(
            json.dumps(
                {
                    "event": "metadata_invalid",
                    "event_id": event_id,
                    "field": field_name,
                    "value": str(value),
                    "message": f"Campo '{field_name}' no es un número válido",
                }
            )
        )
        return None


def extract_metadata(data, event_id):
    """Extrae y valida los metadatos del evento de Storage.

    Devuelve un dict con los metadatos, o lanza ValueError si
    faltan los campos mínimos (bucket y nombre).
    """
    if not isinstance(data, dict):
        raise ValueError(f"El evento no trae un dict válido: {type(data).__name__}")

    name = data.get("name")

    if not name:
        raise ValueError("No se puede identificar el nombre del archivo")

    size = _safe_int(data.get("size"), "size", event_id)

    metadata = {
        "name": name,
        "size_bytes": size,
        "size_kb": round(size / 1024, 2) if size is not None else None,
        "content_type": data.get("contentType", "application/octet-stream"),
    }

    # Advertencia: un archivo sin tipo no bloquea el flujo, pero sí se registra el evento.
    if not data.get("contentType"):
        logger.warning(
            json.dumps(
                {
                    "event": "metadata_missing",
                    "event_id": event_id,
                    "field": "contentType",
                    "name": name,
                    "message": "Sin contentType; se asume application/octet-stream",
                }
            )
        )

    return metadata


@functions_framework.cloud_event
def on_file_upload(cloud_event):
    """Entry point de la Cloud Function.

    cloud_event.data trae el payload del evento de Storage, por ejemplo:
    {
      "bucket": "turing-pruebas-2026-archivos",
      "name": "factura-001.pdf",
      "size": "24576",
      "contentType": "application/pdf",
      "timeCreated": "2026-11-23T17:00:00.000Z",
      ...
    }
    """
    event_id = getattr(cloud_event, "id", "sin-id")
    event_type = getattr(cloud_event, "type", "desconocido")

    logger.info(
        json.dumps(
            {
                "event": "file_upload_received",
                "event_id": event_id,
                "event_type": event_type,
                "message": "Evento de subida recibido, iniciando procesamiento",
            }
        )
    )

    try:
        data = cloud_event.data
        if data is None:
            raise ValueError("El evento llegó sin datos (cloud_event.data es None)")

        metadata = extract_metadata(data, event_id)

        # Aquí iría el procesamiento real del archivo
        # (leerlo con google-cloud-storage, validarlo, moverlo, etc.).
        # Por ahora solo se registra, que es lo que pide la prueba.
        logger.info(
            json.dumps(
                {
                    "event": "file_metadata_extracted",
                    "event_id": event_id,
                    "message": "Metadatos extraídos correctamente",
                    **metadata,
                }
            )
        )

        # Registrar la metadata directo en Sheets, sin Apps Script.
        registrar_en_sheet(metadata, event_id)
        
        logger.info(
            json.dumps(
                {
                    "event": "file_upload_processed",
                    "event_id": event_id,
                    "name": metadata["name"],
                    "message": "Archivo procesado con éxito",
                }
            )
        )


        return metadata

    except ValueError as exc:
        # Error de validación: datos incompletos o malformados.
        # Se loguea con contexto y se propaga para reintento / alerta.
        logger.error(
            json.dumps(
                {
                    "event": "validation_error",
                    "event_id": event_id,
                    "event_type": event_type,
                    "error": str(exc),
                    "message": "Evento inválido, no se pudo procesar el archivo",
                }
            )
        )
        raise

    except Exception as exc:  # noqa: BLE001 - se quiere capturar todo y loguearlo
        # Error inesperado: se registra el traceback completo.
        logger.error(
            json.dumps(
                {
                    "event": "processing_error",
                    "event_id": event_id,
                    "event_type": event_type,
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                    "traceback": traceback.format_exc(),
                    "message": "Error inesperado procesando la subida",
                }
            )
        )
        raise

def registrar_en_sheet(metadata, event_id):
    """Escribe la metadata directo en Google Sheets con la API de Sheets.

    Usa la cuenta de servicio de la función (ADC). El Sheet debe estar
    compartido con esa cuenta de servicio como Editor.
    Columnas: A ID | B Nombre | C Tamaño | D Tipo.
    El ID ascendente se calcula leyendo la columna A.

    No lanza excepción si falla: se loguea el error y el procesamiento
    del archivo sigue, para no reintentar todo el evento por un fallo
    del Sheet.
    """
    if not SPREADSHEET_ID:
        logger.warning(
            json.dumps(
                {
                    "event": "sheets_skipped",
                    "event_id": event_id,
                    "message": "SPREADSHEET_ID no configurada, no se registra nada",
                }
            )
        )
        return

    try:
        creds, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )
        service = build("sheets", "v4", credentials=creds)
        values_api = service.spreadsheets().values()

        # ID ascendente: mayor ID en columna A + 1. Si está vacía, 1.
        result = values_api.get(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{SHEET_NAME}!A2:A",
        ).execute()
        ids = [
            int(v[0])
            for v in result.get("values", [])
            if v and str(v[0]).isdigit()
        ]
        next_id = max(ids) + 1 if ids else 1

        row = [
            next_id,
            metadata.get("name", ""),
            metadata.get("size_bytes") if metadata.get("size_bytes") is not None else "",
            metadata.get("content_type", ""),
        ]

        values_api.append(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{SHEET_NAME}!A:H",
            valueInputOption="USER_ENTERED",
            body={"values": [row]},
        ).execute()

        logger.info(
            json.dumps(
                {
                    "event": "sheets_row_added",
                    "event_id": event_id,
                    "row_id": next_id,
                    "name": metadata.get("name"),
                }
            )
        )
    except Exception as exc:  # noqa: BLE001
        logger.error(
            json.dumps(
                {
                    "event": "sheets_error",
                    "event_id": event_id,
                    "error": str(exc),
                }
            )
        )
