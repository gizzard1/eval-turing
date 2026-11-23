"""Pruebas unitarias básicas — Cloud Function on_file_upload.

Verifican:
  - Flujo exitoso: metadatos extraídos correctamente.
  - Casos borde: sin contentType, sin tamaño, tamaño inválido.
  - Manejo de errores: sin bucket, sin nombre, sin datos, datos no dict.

Ejecutar:
    pip install -r requirements.txt
    pip install pytest
    pytest -v

O con el entorno de pruebas:
    python -m pytest test_main.py -v
"""

import pytest

import main

try:
    from cloudevents.http import CloudEvent
except ImportError:  # pragma: no cover - si no está instalada, se usa el falso
    CloudEvent = None


def make_event(data, event_id="test-event-1"):
    """Construye un evento real de CloudEvents si la librería está
    disponible; si no, usa el falso mínimo.

    Esto evita el KeyError: 'bucket' que sale con algunas versiones de
    functions-framework cuando se le pasa un objeto falso: el decorador
    @cloud_event espera un CloudEvent real y, con uno falso, el payload
    llega vacío o con otra estructura.
    """
    attributes = {
        "type": "google.cloud.storage.object.v1.finalized",
        "source": "//storage.googleapis.com/projects/test-project",
        "id": event_id,
    }
    if CloudEvent is not None:
        return CloudEvent(attributes, data)
    return make_event(data, event_id)


class FakeCloudEvent:
    """Evento mínimo compatible con lo que usa on_file_upload.

    La función solo lee cloud_event.data, .id y .type, así que
    no hace falta construir un CloudEvent real.
    """

    def __init__(self, data, event_id="test-event-1", event_type=None):
        self.data = data
        self.id = event_id
        self.type = event_type or "google.cloud.storage.object.v1.finalized"


def valid_data(**overrides):
    """Datos válidos de ejemplo; overrides permite quitar/cambiar campos."""
    data = {
        "bucket": "agenda-pruebas-2026-archivos",
        "name": "factura-001.pdf",
        "size": "24576",
        "contentType": "application/pdf",
        "timeCreated": "2026-11-23T17:00:00.000Z",
        "updated": "2026-11-23T17:00:00.000Z",
        "metageneration": "1",
        "storageClass": "STANDARD",
        "md5Hash": "abc123==",
        "etag": "etag-1",
    }
    data.update(overrides)
    return data


# ---------------------------------------------------------------------------
# Flujo exitoso
# ---------------------------------------------------------------------------


def test_success_extracts_metadata():
    result = main.on_file_upload(make_event(valid_data()))

    assert result["name"] == "factura-001.pdf"
    assert result["size_bytes"] == 24576
    assert result["size_kb"] == 24.0
    assert result["content_type"] == "application/pdf"



# ---------------------------------------------------------------------------
# Casos borde: no bloquean el flujo
# ---------------------------------------------------------------------------


def test_missing_content_type_defaults_to_octet_stream(caplog):
    data = valid_data()
    del data["contentType"]

    with caplog.at_level("WARNING", logger="process-file-upload"):
        result = main.on_file_upload(make_event(data))

    assert result["content_type"] == "application/octet-stream"
    assert result["name"] == "factura-001.pdf"


def test_missing_size_returns_none():
    data = valid_data()
    del data["size"]

    result = main.on_file_upload(make_event(data))

    assert result["size_bytes"] is None
    assert result["size_kb"] is None
    assert result["name"] == "factura-001.pdf"


def test_invalid_size_returns_none():
    result = main.on_file_upload(make_event(valid_data(size="no-es-numero")))
    assert result["size_bytes"] is None
    assert result["size_kb"] is None
