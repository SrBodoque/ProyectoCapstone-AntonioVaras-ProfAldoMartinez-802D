"""Contrato histórico 0.65 para regresiones simuladas; nunca escribe configuración."""

from src.config import load_detection_config


def baseline_detection_config():
    return {**load_detection_config(), "confidence_threshold": .65}
