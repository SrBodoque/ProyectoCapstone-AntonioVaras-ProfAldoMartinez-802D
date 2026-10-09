"""Comparación experimental: python -m src.track_fast. No cambia el baseline."""

from . import track

FASTTRACK_CONFIG = "config/fasttrack_capstone.yaml"


def main() -> int:
    return track.main(tracker_config=FASTTRACK_CONFIG, tracker_label="FastTracker")


if __name__ == "__main__":
    raise SystemExit(main())
