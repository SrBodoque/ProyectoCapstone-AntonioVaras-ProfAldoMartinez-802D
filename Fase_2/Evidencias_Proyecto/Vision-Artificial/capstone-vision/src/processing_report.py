"""Presentación de resultados existentes; sin inferencia ni escritura de archivos."""

from pathlib import Path

from .saved_results import ResultsError, load_case, number


def _text(value):
    return str(value) if value is not None else "no registrado"


def format_processing_report(directory, summary):
    directory = Path(directory)
    lines = [f"Resultados: {directory}", f"Estado del lote: {summary.get('status', 'no registrado')}"]
    total_frames, total_ms = 0, 0.0
    measured_cases = 0
    results = summary.get("results", [])
    states = {}
    for result in results:
        state = result.get("status", "no registrado")
        states[state] = states.get(state, 0) + 1
        lines.append("")
        identifier = result.get("case_id", "")
        if not isinstance(identifier, str) or not identifier or identifier in (".", "..") or Path(identifier).name != identifier or any(c in identifier for c in ("/", "\\", ":")):
            lines.append("ADVERTENCIA: identificador de caso inválido; no se abrirán rutas externas.")
            continue
        try:
            case = load_case(directory / identifier)
        except (OSError, ResultsError) as exc:
            lines.extend((f"Caso {identifier}: {state} | frames registrados: {result.get('frames_processed', 'N/D')}",
                          f"ADVERTENCIA: informe detallado no disponible: {exc}"))
            if result.get("error"):
                lines.append(f"Error: {result['error']}")
            continue
        meta = case.metadata
        config = meta.get("configuration") or {}
        if not isinstance(config, dict):
            config = {}
        video = meta.get("video") or {}
        model = config.get("model")
        tracker = config.get("tracker_parameters") or {}
        tracker = tracker.get("tracker_type") if isinstance(tracker, dict) else None
        name = str(meta.get("input_path", identifier)).replace("\\", "/").rsplit("/", 1)[-1]
        mode, device = meta.get("mode"), meta.get("device_effective")
        processed = meta.get("frames_processed")
        expected = video.get("reported_frames")
        with_tracks = sum(bool(frame.tracks) for frame in case.frames.values())
        without_ids = [len(frame.detections) + len(frame.untracked) for frame in case.frames.values()]
        elapsed = meta.get("elapsed_ms")
        valid_time = number(elapsed) and elapsed > 0
        valid_frames = type(processed) is int and processed >= 0
        seconds = f"{elapsed / 1000:.3f} s" if valid_time else "N/D"
        fps = f"{processed * 1000 / elapsed:.2f}" if valid_time and valid_frames else "N/D"
        lines.extend((f"Video: {name}", f"Estado: {state} | modo: {_text(mode)}",
                      f"Modelo: {_text(model)} | tracker: {_text(tracker) if mode == 'tracking' else 'no aplica'}",
                      f"Dispositivo efectivo: {_text(device)}" +
                      (f" | GPU: {_text(config.get('device_name'))}" if isinstance(device, str) and device.startswith('cuda:') else ""),
                      f"Fotogramas procesados / esperados: {_text(processed)} / {_text(expected)}",
                      f"Fotogramas con tracks: {with_tracks}",
                      f"Detecciones sin ID: {sum(without_ids)} cajas en {sum(n > 0 for n in without_ids)} fotogramas",
                      f"Tiempo total del caso (incluye carga y E/S): {seconds}",
                      f"Rendimiento de procesamiento: {fps} frames/s (no son FPS de cámara)",
                      f"Directorio del caso: {case.directory}"))
        for message in case.notices.messages:
            lines.append(f"ADVERTENCIA: {message}")
        if case.notices.count > len(case.notices.messages):
            lines.append(f"Advertencias registradas: {case.notices.count} (muestra limitada).")
        if result.get("error") or meta.get("error"):
            lines.append(f"Error: {result.get('error') or meta.get('error')}")
        if state != "completed" and meta.get("termination_reason"):
            lines.append(f"Terminación: {meta['termination_reason']}")
        if valid_time and valid_frames:
            total_frames += processed
            total_ms += elapsed
            measured_cases += 1
    global_fps = f"{total_frames * 1000 / total_ms:.2f}" if total_ms > 0 else "N/D"
    lines.extend(("", f"Resumen global: {len(results)} videos informados | estados: {states}",
                  f"Casos no procesados: {len(summary.get('not_processed', []))}",
                  f"Rendimiento global de procesamiento: {global_fps} frames/s "
                  f"sobre suma de tiempos de {measured_cases} casos con medición válida.",
                  "Los tracks e IDs temporales no representan un conteo real de personas."))
    if summary.get("error"):
        lines.append(f"Error del lote: {summary['error']}")
    return "\n".join(lines)


def print_processing_report(directory, summary):
    # Un fallo de presentación no altera el estado ni el código de salida del procesamiento.
    try:
        text = format_processing_report(directory, summary)
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        text = f"Resultados: {directory}\nEstado: {summary.get('status')}\nADVERTENCIA: informe no disponible: {exc}"
    print(text)
