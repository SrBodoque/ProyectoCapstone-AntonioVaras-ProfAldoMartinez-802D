"""Observación local de ReID: falla explícita, sin copiar el algoritmo ni guardar vectores.

Los callbacks se añaden al YOLO recién cargado, antes de que model.track registre
los callbacks oficiales. Solo dos métodos de ESA instancia se envuelven para
validar sus entradas/salidas; siempre se delega la extracción y asociación reales.
No se parchean clases, módulos ni archivos de Ultralytics.
"""

import logging
from pathlib import Path

LOGGER = logging.getLogger(__name__)
EXPECTED_VERSION = "8.4.163"


def _runtime():
    import ultralytics
    from ultralytics.trackers.bot_sort import BOTSORT
    if ultralytics.__version__ != EXPECTED_VERSION:
        raise RuntimeError(f"ReID requiere Ultralytics {EXPECTED_VERSION}; versión efectiva: "
                           f"{ultralytics.__version__}. No se cambia el entorno automáticamente.")
    return BOTSORT


def _device(value):
    value = str(value)
    return "cuda:0" if value == "cuda" else value


def _valid_feature(value):
    # Los BOTrack oficiales reciben arrays NumPy en CPU. No se copian ni registran.
    import numpy as np
    return (isinstance(value, np.ndarray) and value.ndim == 1 and value.size > 0
            and value.dtype.kind == "f" and bool(np.isfinite(value).all())
            and bool(np.any(value != 0)))


def _check_features(items):
    for item in items:
        if not all(_valid_feature(getattr(item, field, None)) for field in ("curr_feat", "smooth_feat")):
            raise RuntimeError("ReID no produjo características válidas de apariencia; tracking detenido.")


class ReIDDiagnostics:
    """Solo conserva referencias de sesión y contadores; nunca copia embeddings."""

    def __init__(self, model, expected_device):
        self._botsort_type = _runtime()
        if getattr(model, "predictor", None) is not None:
            raise RuntimeError("ReID necesita un modelo nuevo por sesión para verificar los callbacks.")
        self.expected_device = _device(expected_device)
        self.engine = None
        self.effective_model = None
        self.features_verified = False
        self.association_verified = False
        self._batch_started = False
        self._detections_seen = False
        self._expected_features = 0
        self._extracted = 0
        self._associated = False
        self._had_tracks = False
        model.add_callback("on_predict_batch_start", self.on_batch_start)
        model.add_callback("on_predict_postprocess_end", self.before_association)
        LOGGER.info("Ultralytics efectivo: %s | ReID pendiente de inicialización real.", EXPECTED_VERSION)

    def _check_engine(self, predictor):
        engines = getattr(predictor, "trackers", ())
        if len(engines) != 1 or type(engines[0]) is not self._botsort_type:
            raise RuntimeError("El tracker efectivo no es una instancia oficial única de BoT-SORT.")
        engine = engines[0]
        if engine.args.tracker_type != "botsort" or engine.args.with_reid is not True:
            raise RuntimeError("BoT-SORT no tiene ReID activado; tracking detenido.")
        if not callable(getattr(engine, "encoder", None)):
            raise RuntimeError("El encoder ReID no se inicializó; comprueba los pesos oficiales de apariencia.")
        if _device(predictor.device) != self.expected_device:
            raise RuntimeError("El detector no usa el dispositivo efectivo seleccionado.")
        effective = engine.args.model
        if effective == "auto":
            # La rama nativa requiere el hook de características del detector.
            if getattr(predictor, "_hook", None) is None:
                raise RuntimeError("ReID auto no tiene hook de características del detector.")
        elif effective == "yolo26n-cls.pt":
            appearance = getattr(engine.encoder, "model", None)
            appearance_predictor = getattr(appearance, "predictor", None)
            checkpoint = getattr(appearance, "ckpt_path", "")
            if (appearance_predictor is None or not checkpoint
                    or Path(str(checkpoint)).name != effective
                    or getattr(appearance, "task", None) != "classify"):
                raise RuntimeError("No se pudo verificar el extractor de clasificación yolo26n-cls.pt inicializado.")
            if _device(appearance_predictor.device) != self.expected_device:
                raise RuntimeError("El encoder ReID no usa el dispositivo seleccionado; no se permite "
                                   "un cambio silencioso CPU/GPU. Revisa la instalación 8.4.163.")
        else:
            raise RuntimeError("ReID auto resolvió un modelo no admitido en este experimento.")
        return engine, effective

    def on_batch_start(self, predictor):
        engine, effective = self._check_engine(predictor)
        if self.engine is None:
            self.engine, self.effective_model = engine, effective
            self._observe(engine)
            LOGGER.info("BoT-SORT real verificado | Encoder ReID inicializado | Modelo ReID efectivo: %s | "
                        "Dispositivo detector/encoder: %s. Extracción y asociación aún pendientes.",
                        "características nativas del detector" if effective == "auto" else effective,
                        self.expected_device)
        elif engine is not self.engine or effective != self.effective_model:
            raise RuntimeError("La instancia o el modelo ReID cambió dentro de la sesión.")
        self._had_tracks = bool(engine.tracked_stracks or engine.lost_stracks)
        self._batch_started = True
        self._detections_seen = False
        self._expected_features = self._extracted = 0
        self._associated = False

    def before_association(self, predictor):
        if not self._batch_started or len(predictor.results) != 1:
            raise RuntimeError("No se pudo verificar el frame antes de la asociación ReID.")
        boxes = predictor.results[0].boxes
        if boxes is not None and boxes.is_track:
            raise RuntimeError("La comprobación ReID recibió tracks en vez de detecciones; orden de callbacks inválido.")
        self._expected_features = (int((boxes.conf >= self.engine.args.track_high_thresh).sum().item())
                                   if boxes is not None else 0)
        self._detections_seen = True

    def _observe(self, engine):
        init_track, get_dists = engine.init_track, engine.get_dists
        # Asegura que se delega a los métodos originales de la versión exigida.
        if (getattr(init_track, "__func__", None) is not self._botsort_type.init_track
                or getattr(get_dists, "__func__", None) is not self._botsort_type.get_dists):
            raise RuntimeError("Los métodos de BoT-SORT no corresponden a la implementación oficial.")

        def checked_init(results, *args, **kwargs):
            if not self._detections_seen:
                raise RuntimeError("No se observó la detección antes de extraer apariencia ReID.")
            items = init_track(results, *args, **kwargs)
            if len(items) != len(results):
                raise RuntimeError("ReID no devolvió una trayectoria con características por detección.")
            _check_features(items)
            self._extracted += len(items)
            return items

        def checked_dists(tracks, detections):
            _check_features(tracks)
            _check_features(detections)
            distances = get_dists(tracks, detections)
            if len(tracks) and len(detections):
                import numpy as np
                if (distances.shape != (len(tracks), len(detections))
                        or not np.isfinite(distances).all()):
                    raise RuntimeError("BoT-SORT devolvió distancias de asociación inválidas.")
                self._associated = True
            return distances

        engine.init_track = checked_init
        engine.get_dists = checked_dists

    def after_frame(self):
        if not self._batch_started or not self._detections_seen:
            raise RuntimeError("No se ejecutaron los controles ReID; tracking detenido.")
        if self._extracted != self._expected_features:
            raise RuntimeError("Las detecciones no llegaron al extractor ReID; tracking detenido.")
        if self._had_tracks and self._expected_features and not self._associated:
            raise RuntimeError("Había tracks y detecciones, pero no se verificó su asociación con apariencia ReID.")
        current = [t for t in self.engine.tracked_stracks if t.frame_id == self.engine.frame_id]
        _check_features(current)
        if self._extracted and not self.features_verified:
            self.features_verified = True
            LOGGER.info("ReID: extracción válida comprobada en detecciones; no se registran vectores.")
        if self._associated and not self.association_verified:
            self.association_verified = True
            LOGGER.info("ReID activo verificado: características válidas entregadas a la asociación "
                        "oficial BoT-SORT. Esto no demuestra una mejora de IDs.")
        self._batch_started = False
