"""ByteTrack Recovery experimental: candidatos débiles, altas de confianza alta."""

from . import track

RECOVERY_CONFIG = "config/bytetrack_recovery_capstone.yaml"
RECOVERY_LABEL = "ByteTrack Recovery (Experimental)"
RECOVERY_CONFIDENCE = 0.10


def main() -> int:
    return track.main(tracker_config=RECOVERY_CONFIG, tracker_label=RECOVERY_LABEL,
                      tracking_confidence_override=RECOVERY_CONFIDENCE)


if __name__ == "__main__":
    raise SystemExit(main())
