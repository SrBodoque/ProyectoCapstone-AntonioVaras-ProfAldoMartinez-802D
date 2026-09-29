"""Formato y disponibilidad CPU/CUDA compartidos; PyTorch se importa al usarlo."""

import re
from dataclasses import dataclass
from importlib import import_module


def validate_device_format(device: str) -> None:
    """Validación sintáctica sin importar IA ni consultar hardware."""
    if device == "cpu":
        return
    if (isinstance(device, str) and re.fullmatch(r"cuda:(0|[1-9][0-9]{0,9})", device)
            and int(device[5:]) <= 2**31 - 1):
        return
    raise ValueError("device debe ser 'cpu' o 'cuda:N', con N entero no negativo "
                     "sin ceros iniciales y dentro del rango de 32 bits.")


def load_torch():
    try:
        return import_module("torch")
    except Exception as exc:
        raise RuntimeError(f"No se pudo cargar PyTorch: {exc}. Revisa .venv y las "
                           "dependencias instaladas; el selector no instala paquetes.") from exc


@dataclass(frozen=True)
class InferenceDevice:
    device: str
    name: str


@dataclass(frozen=True)
class DeviceInventory:
    devices: tuple[InferenceDevice, ...]
    cuda_build: str | None
    cuda_available: bool
    cuda_count: int
    notices: tuple[str, ...] = ()


def _cuda_state(torch):
    # No inferir disponibilidad a partir del nombre físico o del sufijo del wheel.
    return torch.version.cuda, torch.cuda.is_available(), torch.cuda.device_count()


def discover_devices(torch_module=None) -> DeviceInventory:
    """Enumera GPUs visibles para PyTorch. La elegida se prueba antes de guardar."""
    devices = [InferenceDevice("cpu", "CPU")]
    try:
        torch = torch_module if torch_module is not None else load_torch()
        build, available, count = _cuda_state(torch)
    except Exception as exc:
        return DeviceInventory(tuple(devices), None, False, 0,
                               (f"No se pudo consultar CUDA: {exc}. "
                                "CPU puede configurarse; ejecutar inferencia requiere PyTorch funcional.",))
    notices = []
    if not available:
        notices.append("CUDA no está disponible para la instalación actual de PyTorch. "
                       "Solo se ofrece CPU.")
        if build is None:
            notices.append("torch.version.cuda es None: esta instalación no incluye un build CUDA.")
    else:
        for index in range(count):
            try:
                name = torch.cuda.get_device_name(index)
                devices.append(InferenceDevice(f"cuda:{index}", name))
            except Exception as exc:
                notices.append(f"No se ofrece cuda:{index}: no se pudo consultar la GPU ({exc}).")
    return DeviceInventory(tuple(devices), build, available, count, tuple(notices))


def validate_device(device: str, *, torch_module=None, probe: bool = True) -> None:
    """Rechaza CUDA no utilizable; nunca sustituye el dispositivo por CPU."""
    validate_device_format(device)
    if device == "cpu":
        return
    try:
        torch = torch_module if torch_module is not None else load_torch()
        build, available, count = _cuda_state(torch)
        index = int(device[5:])
        if not available or index >= count:
            raise RuntimeError(f"CUDA disponible: {available}; GPUs CUDA: {count}; "
                               f"CUDA build: {build}.")
        if probe:
            # Una operación real y pequeña detecta fallos que torch.device no detecta.
            tensor = torch.ones(1, device=device)
            tensor.add_(1)
            torch.cuda.synchronize(index)
            if tensor.item() != 2:
                raise RuntimeError("La comprobación CUDA devolvió un resultado inesperado.")
    except Exception as exc:
        raise RuntimeError(
            f"El dispositivo configurado '{device}' no está disponible o no es utilizable. "
            f"{exc} No se cambiará a CPU automáticamente. "
            "Ejecute: python -m src.device_selector"
        ) from exc
