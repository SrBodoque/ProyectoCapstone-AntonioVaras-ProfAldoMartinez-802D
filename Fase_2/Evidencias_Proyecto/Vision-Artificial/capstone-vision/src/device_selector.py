"""Seleccionar y persistir CPU/CUDA: python -m src.device_selector."""

import json
import logging
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from .config import DETECTION_CONFIG_PATH, load_detection_config
from .devices import (DEVICE_LOCAL_PATH, InferenceDevice, discover_devices,
                      load_device_preference, load_torch, validate_device)

LOGGER = logging.getLogger(__name__)


def choose_device(devices: tuple[InferenceDevice, ...]) -> str | None:
    """Las opciones del menú se traducen a identificadores CPU/CUDA inequívocos."""
    if not devices:
        raise ValueError("No hay dispositivos para seleccionar.")
    while True:
        answer = input("Seleccione dispositivo (q para cancelar): ").strip()
        if answer.lower() == "q":
            return None
        try:
            option = int(answer)
        except ValueError:
            option = -1
        if 0 <= option < len(devices):
            return devices[option].device
        print(f"Selección inválida. Elija una opción entre 0 y {len(devices) - 1}, o q.")


def save_device(device: str, path: Path = DEVICE_LOCAL_PATH) -> dict[str, str]:
    """Valida hardware y guarda solo la preferencia local, incluso si estaba rota."""
    validate_device(device)
    updated = {"device": device}
    temporary = None
    try:
        with NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", dir=path.parent,
            prefix=f".{path.name}.", suffix=".tmp", delete=False,
        ) as stream:
            temporary = Path(stream.name)
            json.dump(updated, stream, ensure_ascii=False, allow_nan=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        if load_device_preference(temporary) != device:
            raise RuntimeError("La configuración temporal no coincide con la selección.")
        os.replace(temporary, path)
        saved = load_device_preference(path)
        if saved != device:
            raise RuntimeError("No se pudo verificar la configuración guardada.")
        return updated
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main(path: Path = DEVICE_LOCAL_PATH, base_path: Path = DETECTION_CONFIG_PATH) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        config = load_detection_config(base_path)
        print("CAPSTONE - Selector de dispositivo de inferencia")
        print(f"Configuración base: {config['device']}", flush=True)
        try:
            preference = load_device_preference(path)
            print(f"Preferencia local: {preference or 'no configurada'}")
        except ValueError as exc:
            LOGGER.warning("Preferencia local inválida: %s; una selección nueva puede reemplazarla.", exc)
        torch = load_torch()  # Si el import falla, no ofrecer una instalación rota como utilizable.
        inventory = discover_devices(torch)
        print("Dispositivos disponibles:")
        for option, entry in enumerate(inventory.devices):
            label = "CPU" if entry.device == "cpu" else f"{entry.device.upper()} - {entry.name}"
            print(f"[{option}] {label}")
        for notice in inventory.notices:
            print(notice)
        device = choose_device(inventory.devices)
        if device is None:
            print("Selección cancelada; la configuración no se modificó.")
            return 0
        save_device(device, path)
        print(f"Dispositivo seleccionado: {device}")
        print(f"Preferencia local guardada y verificada en {path}.")
        return 0
    except EOFError:
        print("Entrada finalizada; la configuración no se modificó.")
        return 1
    except KeyboardInterrupt:
        print("\nSelector interrumpido.")
        return 130
    except (OSError, ValueError, RuntimeError) as exc:
        LOGGER.error("No se pudo completar la selección: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
