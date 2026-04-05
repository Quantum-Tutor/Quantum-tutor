"""
test_multimodal_vision_parser.py
Tests del MultimodalVisionParser — incluyendo test de degradación honesta (hardening 2026-04-05)
"""
import os
from multimodal_vision_parser import MultimodalVisionParser
from unittest.mock import patch


def test_multimodal_parser_uses_first_key_from_gemini_api_keys(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEYS", "PRIMARY_KEY,SECONDARY_KEY")

    with patch("google.genai.Client"):
        parser = MultimodalVisionParser()

    assert parser.api_key == "PRIMARY_KEY"


def test_multimodal_parser_falls_back_to_empty_key_when_env_missing(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEYS", raising=False)

    parser = MultimodalVisionParser()

    assert parser.api_key == ""


# =============================================================================
# SECURITY / INTEGRITY TEST — hardening 2026-04-05
# =============================================================================

def test_vision_parser_returns_degraded_not_mock_when_no_api(monkeypatch):
    """Sin API key, el parser debe retornar una señal honesta de degradación,
    NO datos mock fabricados que parecen reales para el estudiante.
    """
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEYS", raising=False)

    parser = MultimodalVisionParser()
    assert parser.client is None  # sin cliente

    result = parser.parse_derivation_image("imagen_inexistente.png")

    assert isinstance(result, list)
    assert len(result) == 1, "Degraded response debe tener exactamente 1 elemento"

    step = result[0]
    assert step["error_flag"] is True, "Degraded response debe marcar error_flag=True"
    assert step["confidence"] == 0.0, "Degraded response debe tener confidence=0.0"
    assert step["step"] == 0, "Degraded response debe tener step=0"
    assert "no está disponible" in step["error_reason"].lower() or \
           "no esta disponible" in step["error_reason"].lower(), \
        f"error_reason debe indicar indisponibilidad, got: {step['error_reason']}"

    # Verificar que NO son datos mock fabricados (el mock antiguo tenía 4 pasos con LaTeX real)
    assert step["latex"] == "", f"Degraded response no debe tener LaTeX fabricado, got: {step['latex']}"


def test_vision_parser_returns_degraded_when_gemini_raises(monkeypatch, tmp_path):
    """Si Gemini lanza excepción durante el análisis, se debe degradar honestamente."""
    monkeypatch.setenv("GEMINI_API_KEYS", "FAKE_KEY")

    # Crear imagen de prueba mínima
    test_image = tmp_path / "test_image.png"
    test_image.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

    with patch("google.genai.Client") as mock_client:
        instance = mock_client.return_value
        instance.models.generate_content.side_effect = Exception("API Error 500")

        parser = MultimodalVisionParser()
        parser.client = instance

        result = parser.parse_derivation_image(str(test_image))

    # Aunque el archivo existe y el cliente existe, Gemini falla → degradar honestamente
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["error_flag"] is True
    assert result[0]["confidence"] == 0.0
