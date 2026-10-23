"""BoT-SORT + ReID experimental; comparte el loop y la confianza general 0.65."""

from . import track

BOTSORT_CONFIG = "config/botsort_reid_capstone.yaml"
BOTSORT_LABEL = "BoT-SORT + ReID"


def main() -> int:
    return track.main(tracker_config=BOTSORT_CONFIG, tracker_label=BOTSORT_LABEL)


if __name__ == "__main__":
    raise SystemExit(main())
