"""Dataset inventory/audit only; no inference and no mutation of input datasets."""

import argparse
import configparser
import json
import math
import re
import tarfile
import zipfile
from xml.etree.ElementTree import ParseError
from pathlib import Path

from .dataset_annotations import ranges, read_caviar, read_mot, read_oxford, summarize
from .video_source import VideoSource, file_sha256

SCHEMA_VERSION = 1
STATES = ("READY", "NEEDS_ADAPTER", "NEEDS_VERIFICATION", "NOT_EVALUABLE", "EXPLORATORY")
CASES = (
    ("MOT17-02", "dev/MOT17-02.mp4", "mot17", "MOT17-02"),
    ("MOT17-04", "dev/MOT17-04.mp4", "mot17", "MOT17-04"),
    ("PETS09-S2L1", "dev/PETS09-S2L1.mp4", "mot15", "PETS09-S2L1"),
    ("OxfordTownCentre", "dev/TownCentreXVID.mp4", "oxford", "TownCentre"),
    ("CAVIAR-EnterExitCrossingPaths1cor", "dev/CAVIAR-EnterExitCrossingPaths1cor.mp4", "caviar", "EnterExitCrossingPaths1cor"),
    ("CAVIAR-OneLeaveShopReenter1cor", "dev/CAVIAR-OneLeaveShopReenter1cor.mp4", "caviar", "OneLeaveShopReenter1cor"),
    ("prueba_01", "exploratory/prueba_01.mp4", "exploratory", "prueba_01"),
)


def snapshot(root):
    """Hash every regular input except explicitly ignored incomplete downloads.

    Relative paths and content hashes only: no mtime, runtime or wall-clock noise.
    Symbolic links and Windows junctions are refused (including directories).
    """
    root = Path(root).resolve()
    if not root.is_dir():
        raise ValueError(f"Dataset directory does not exist: {root}")
    result = {}
    for p in sorted(root.rglob("*")):
        if p.is_symlink() or p.is_junction() or not p.resolve().is_relative_to(root):
            raise ValueError(f"Dataset links are not supported: {p}")
        if p.is_file() and not p.name.endswith(".part"):
            before = p.stat()
            digest = file_sha256(p)
            after = p.stat()
            if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                raise RuntimeError(f"Input changed during hash: {p}")
            result[p.relative_to(root).as_posix()] = {"bytes": after.st_size, "sha256": digest}
    return result


def _zip_bytes(archive, name):
    """Read one member without extraction; reject ambiguous and oversize entries."""
    matches = [i for i in archive.infolist() if i.filename == name]
    if len(matches) != 1:
        raise ValueError(f"Missing or duplicate ZIP member: {name}")
    if matches[0].file_size > 64 * 1024 * 1024:
        raise ValueError(f"ZIP member exceeds 64 MiB: {name}")
    return archive.read(matches[0])  # zipfile verifies CRC when the member is read.


def _seqinfo(data):
    c = configparser.ConfigParser()
    c.read_string(data.decode("utf-8-sig"))
    s = c["Sequence"]
    values = {"name": s["name"], "width": s.getint("imWidth"), "height": s.getint("imHeight"),
              "fps": s.getfloat("frameRate"), "frames": s.getint("seqLength")}
    if not all(math.isfinite(values[k]) and values[k] > 0 for k in ("width", "height", "fps", "frames")):
        raise ValueError("Invalid seqinfo dimensions, FPS or length")
    return values


def annotations(root, kind, original):
    if kind.startswith("mot"):
        version = int(kind[3:])
        path = root / f"annotations/MOT/MOT{version}Labels.zip"
        variants = [f"{original}-{s}" for s in ("DPM", "FRCNN", "SDP")] if version == 17 else [original]
        info = []
        payloads = []
        with zipfile.ZipFile(path) as z:
            prefix = "train/" if version == 17 else "MOT15Labels/train/"
            for variant in variants:
                member = f"{prefix}{variant}/gt/gt.txt"
                raw = _zip_bytes(z, member)
                # BytesIO lets hashlib hash a member without inventing a filesystem path.
                import hashlib
                meta = _seqinfo(_zip_bytes(z, f"{prefix}{variant}/seqinfo.ini"))
                if meta["name"] != variant:
                    raise ValueError("seqinfo name does not match ZIP sequence")
                info.append({"member": member, "sha256": hashlib.sha256(raw).hexdigest(), "sequence": meta})
                payloads.append(raw)
        same = all(raw == payloads[0] for raw in payloads)
        return read_mot(payloads[0].decode("utf-8-sig"), version=version), {
            "path": path.relative_to(root).as_posix(), "format": f"MOT{version}",
            "selected_member": info[0]["member"], "variants": info,
            "variant_ground_truth_identical": same,
            "annotation_dimensions": [info[0]["sequence"]["width"], info[0]["sequence"]["height"]],
            "expected_frames": info[0]["sequence"]["frames"], "expected_fps": info[0]["sequence"]["fps"],
            "variants_are_independent_sequences": False}
    if kind == "oxford":
        path = root / "annotations/OxfordTownCentre/TownCentre-groundtruth.top"
        ci = root / "annotations/OxfordTownCentre/TownCentre-calibration.ci"
        # Inspect calibration text; no calibration/homography is implemented here.
        calibration = dict(line.split("=", 1) for line in ci.read_text().splitlines() if "=" in line) if ci.exists() else {}
        return read_oxford(path.read_text(encoding="utf-8-sig")), {
            "path": path.relative_to(root).as_posix(), "format": "Oxford_TOP_12_candidate",
            "expected_frames": None, "annotation_dimensions": None, "expected_fps": None,
            "calibration_path": ci.relative_to(root).as_posix() if ci.exists() else None,
            "calibration_fields": {k.strip(): v.strip() for k, v in calibration.items()},
            "body_boxes_estimated_from_heads": "reported_by_original_project_description; verify before evaluation",
            "coordinate_origin_verified": False}
    xml = "ceecp1gt.xml" if original == "EnterExitCrossingPaths1cor" else "colsr1gt.xml"
    path = root / "annotations/CAVIAR" / xml
    parsed = read_caviar(path.read_text(encoding="utf-8-sig"))
    if parsed.sequence_name != original:
        raise ValueError("CAVIAR dataset name does not match expected sequence")
    return parsed, {"path": path.relative_to(root).as_posix(), "format": "CAVIAR_CVML_XML",
        "annotation_dimensions": [384, 288], "expected_frames": max(parsed.explicit_frames, default=-1) + 1,
        "expected_fps": 25, "groups_are_person_detections": False,
        "source_tar": f"source/CAVIAR/{original}.tar.gz", "source_mpg": f"source/CAVIAR/{original}.mpg",
        "coordinate_origin_verified": False}


def _reference_jpegs(path, original):
    """Read archive images in memory; never extract to a dataset directory."""
    result = {}
    with tarfile.open(path, "r:gz") as archive:
        for member in archive:
            if not member.isfile():
                continue
            match = re.fullmatch(re.escape(original) + r"(\d+)\.jpg", Path(member.name).name)
            if not match:
                continue
            index = int(match[1])
            if index in result or member.size > 4 * 1024 * 1024:
                raise ValueError("Duplicate or oversize reference JPEG")
            with archive.extractfile(member) as stream:
                result[index] = stream.read()
    if not result:
        raise ValueError("No reference JPEGs found in CAVIAR archive")
    return result


def probe_video(path, *, reference_tar=None, original=None):
    """Reuse Stage 1 VideoSource; sequential full decode with optional image check."""
    import cv2
    import numpy as np
    reference_error = None
    try:
        refs = _reference_jpegs(reference_tar, original) if reference_tar and reference_tar.is_file() else {}
    except (OSError, ValueError, tarfile.TarError) as exc:
        refs = {}
        reference_error = f"{type(exc).__name__}: {exc}"
    error_sum = 0.0
    error_max = 0.0
    compared = 0
    incompatible = []
    dimensions = set()
    fallback = 0
    timestamps = []
    duplicate_adjacent = 0
    previous = None
    offset_errors = {i: [] for i in range(-2, 3)}
    sample_indices = {0, len(refs)//4, len(refs)//2, 3*len(refs)//4, len(refs)-1} if refs else set()
    with VideoSource(path) as source:
        for packet in source:
            frame = packet.frame
            dimensions.add((frame.shape[1], frame.shape[0]))
            if previous is not None and np.array_equal(previous, frame):
                duplicate_adjacent += 1
            previous = frame
            if packet.timestamp_source != "opencv":
                fallback += 1
            timestamps.append(packet.timestamp_ms)
            if packet.index in refs:
                ref = cv2.imdecode(np.frombuffer(refs[packet.index], dtype=np.uint8), cv2.IMREAD_COLOR)
                if ref is None or ref.shape != frame.shape:
                    incompatible.append(packet.index)
                else:
                    mae = float(cv2.absdiff(frame, ref).mean())
                    error_sum += mae
                    error_max = max(error_max, mae)
                    compared += 1
            if packet.index in sample_indices:
                for offset in offset_errors:
                    raw = refs.get(packet.index + offset)
                    ref = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR) if raw else None
                    if ref is not None and ref.shape == frame.shape:
                        offset_errors[offset].append(float(cv2.absdiff(frame, ref).mean()))
        result = dict(source.metadata)
        fps = result["reported_fps"]
        result.update({"decoded_frames": source.frames_read, "decode_status": source.status,
            "decode_reason": source.reason, "observed_dimensions": sorted(dimensions),
            "duration_seconds_nominal": source.frames_read / fps if fps else None,
            "timestamp_fallback_frames": fallback,
            "timestamp_first_ms": timestamps[0] if timestamps else None,
            "timestamp_last_ms": timestamps[-1] if timestamps else None,
            "identical_adjacent_decoded_frames": duplicate_adjacent,
            "pts_integrity_certified": False})
    if reference_error:
        result["source_image_comparison_error"] = reference_error
    if refs:
        result["source_image_comparison"] = {"reference_frames": len(refs), "compared_frames": compared,
            "reference_index_ranges": ranges(refs),
            "incompatible_frames": incompatible, "mean_absolute_pixel_error": error_sum/compared if compared else None,
            "max_frame_mean_absolute_pixel_error": error_max if compared else None,
            "offset_probe_mean_errors": {str(k): sum(v)/len(v) if v else None for k, v in offset_errors.items()},
            "caveat": "Compression permits nonzero error. Offset probes are samples, not proof of identity or complete people labels."}
    return result


def evaluation_cases(manifest):
    """Fail closed. Future experiment selection MUST use this list, not dev/*.mp4."""
    return [c for c in manifest["sequences"] if c["status"] == "READY" and c["evaluation_ready"] is True
            and c["kind"] != "exploratory" and c["id"] != "prueba_01"
            and not c.get("video_path", "").startswith("exploratory/")
            and c["verification"]["temporal_alignment_verified"] is True
            and c["verification"]["evaluation_policy_verified"] is True]


def audit(root):
    root = Path(root).resolve()
    before = snapshot(root)
    cases = []
    for identifier, relative, kind, original in CASES:
        item = {"id": identifier, "kind": kind, "original_sequence": original,
            "recording_group": original, "video_path": relative, "video": None, "annotations": None,
            "status": "NEEDS_VERIFICATION", "evaluation_ready": False, "issues": [],
            "verification": {"temporal_alignment_verified": False, "evaluation_policy_verified": False,
                             "visual_review": "not_performed_by_this_command"}}
        cases.append(item)
        path = root / relative
        if not path.is_file():
            item["issues"].append("Video missing")
            item["status"] = "EXPLORATORY" if kind == "exploratory" else "NOT_EVALUABLE"
            continue
        item["video_asset"] = before.get(relative)
        reference = root / f"source/CAVIAR/{original}.tar.gz" if kind == "caviar" else None
        try:
            item["video"] = probe_video(path, reference_tar=reference, original=original)
        except (OSError, RuntimeError, ValueError, tarfile.TarError) as exc:
            item["issues"].append(f"Video/source decode: {type(exc).__name__}: {exc}")
        if kind == "exploratory":
            item["status"] = "EXPLORATORY"
            item["issues"].append("Visual/manual use only; tracker predictions and draft annotations are not GT")
            continue
        try:
            parsed, details = annotations(root, kind, original)
            video = item["video"] or {}
            expected = video.get("decoded_frames") or details["expected_frames"]
            dims = details["annotation_dimensions"]
            details["summary"] = summarize(parsed, expected, dims)
            details["source_asset"] = before.get(details["path"])
            item["annotations"] = details
            summary = details["summary"]
            if not parsed.records:
                item["status"] = "NOT_EVALUABLE"
                item["issues"].append("No valid individual annotations")
            if summary["invalid_rows"]:
                item["issues"].append(f"Malformed annotation rows: {summary['invalid_rows']} (not repaired)")
            if summary["duplicate_frame_id_pairs"]:
                item["issues"].append("Duplicate (frame, ID) annotations")
            if summary["frames_without_rows_ranges"] and not (
                    kind == 'caviar' and not summary['missing_explicit_xml_frame_ranges']
                    and not summary['invalid_rows']):
                item["issues"].append("Some decoded frames lack annotation rows; negative/excluded/truncated status needs interpretation")
            if summary["frames_outside_expected_ranges"]:
                item["issues"].append("Annotations extend beyond decoded video")
            if details.get("variant_ground_truth_identical") is False:
                item["issues"].append("MOT variants have different GT; cannot silently select one")
            if details["expected_frames"] and details["expected_frames"] != video.get("decoded_frames"):
                item["issues"].append("seqinfo/XML expected frame count does not match decoded video")
            if dims and video.get("width") and video.get("height"):
                scale = [video["width"]/dims[0], video["height"]/dims[1]]
                details["candidate_annotation_to_video_scale"] = scale
                if scale != [1.0, 1.0]:
                    item["issues"].append(f"Image size mismatch: candidate scale {scale}; crop/registration not verified")
            if details["expected_fps"] and video.get("reported_fps") and not math.isclose(details["expected_fps"], video["reported_fps"], rel_tol=1e-5):
                item["issues"].append("Annotation FPS does not match reported video FPS")
            if kind == "caviar":
                comparison = video.get("source_image_comparison")
                mpg = root / details["source_mpg"]
                if mpg.is_file():
                    try:
                        details["source_mpg_metadata"] = probe_video(mpg)
                    except (OSError, RuntimeError, ValueError) as exc:
                        item["issues"].append(f"CAVIAR source MPEG decode: {exc}")
                else:
                    item["issues"].append("CAVIAR source MPEG missing")
                item["issues"].append("CVML: preserve appearance, object IDs and explicit empty frames; resolve origin and ignore policy; moving-target labels may omit static people")
                if not comparison:
                    item["issues"].append("CAVIAR reference JPEGs unavailable or comparison not completed")
                elif comparison["compared_frames"] != video.get("decoded_frames") or comparison["reference_frames"] != video.get("decoded_frames"):
                    item["issues"].append("CAVIAR reference/video coverage mismatch")
            if kind == "oxford":
                item["issues"].append("TOP origin/body policy unverified; head/body validity are not visibility fractions; calibration is not GT")
                item["issues"].append("Video length cannot be inferred from last TOP row; existing annotation tail may be incomplete")
            item["issues"].append("Temporal registration and evaluation exclusions require documented verification; matching FPS/counts is insufficient")
        except (OSError, ValueError, KeyError, UnicodeError, zipfile.BadZipFile, configparser.Error, ParseError) as exc:
            item["issues"].append(f"Annotation read: {type(exc).__name__}: {exc}")
            item["status"] = "NOT_EVALUABLE" if isinstance(exc, FileNotFoundError) else "NEEDS_VERIFICATION"
        if item["video"] and item["video"]["decode_status"] != "completed":
            item["issues"].append("Video full decode incomplete or failed")
        # Automatic structural audit deliberately never promotes unverified inputs to READY.
    after = snapshot(root)
    if before != after:
        raise RuntimeError("Dataset contents changed during audit; no manifest may certify preservation")
    known = {relative for _, relative, _, _ in CASES}
    manifest = {"schema_version": SCHEMA_VERSION, "dataset_root": str(root),
        "audit_scope": "full_sequential_decode_no_inference", "original_inputs_unchanged": True,
        "input_inventory": before,
        "ignored_incomplete_downloads": sorted(p.relative_to(root).as_posix() for p in root.rglob('*.part')),
        "unregistered_mp4": sorted(p for p in before if p.lower().endswith('.mp4') and p not in known),
        "validation_split_files": sorted(p for p in before if p.startswith('validation/')),
        "states": list(STATES), "sequences": cases,
        "eligible_sequence_ids": [], "selection_rule": "Use evaluation_cases; never infer eligibility from directory"}
    manifest["eligible_sequence_ids"] = [c["id"] for c in evaluation_cases(manifest)]
    return manifest


def manifest_json(manifest):
    return json.dumps(manifest, ensure_ascii=False, allow_nan=False, sort_keys=True, indent=2) + "\n"


def write_manifest(path, manifest, root):
    """Only new outputs outside the entire input tree; no overwrite flag."""
    path, root = Path(path).resolve(), Path(root).resolve()
    if path.is_relative_to(root):
        raise ValueError("Output must be outside videos_testing; inputs are read-only")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(manifest_json(manifest))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read-only dataset audit, without inference")
    parser.add_argument("--datasets", type=Path, default=Path(__file__).resolve().parent.parent / "videos_testing")
    parser.add_argument("--output", type=Path, required=True, help="New JSON file outside videos_testing")
    args = parser.parse_args(argv)
    try:
        # Validate destination before expensive decoding and before any writes.
        if args.output.resolve().is_relative_to(args.datasets.resolve()) or args.output.exists():
            raise ValueError("Output must be new and outside the dataset directory")
        manifest = audit(args.datasets)
        write_manifest(args.output, manifest, args.datasets)
        for item in manifest["sequences"]:
            v = item["video"] or {}
            print(f"{item['id']}: {item['status']} | {v.get('decoded_frames', '?')} frames | {v.get('width', '?')}x{v.get('height', '?')} | {v.get('reported_fps', '?')} FPS")
            for issue in item["issues"]:
                print(f"  - {issue}")
        print(f"Eligible for objective evaluation: {manifest['eligible_sequence_ids']}")
        print(f"Manifest: {args.output.resolve()}")
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Audit error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
