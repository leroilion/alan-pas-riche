from __future__ import annotations

import argparse
import json
import re
import sys
import traceback
from dataclasses import asdict, dataclass
from datetime import timedelta
from pathlib import Path

import cv2
import numpy as np
from faster_whisper import WhisperModel


# ============================= CONFIGURATION =============================

OUTPUT_ROOT = Path(
    r"C:\Users\CheynetJeremy\Documents\personnel\pdf\alan_pas_riche\sessions"
)

WHISPER_MODEL = "medium"
WHISPER_DEVICE = "auto"
WHISPER_COMPUTE_TYPE = "auto"
LANGUAGE = "fr"

ANALYZE_EVERY_SECONDS = 1.0
CHANGE_THRESHOLD = 0.12
STABLE_THRESHOLD = 0.035
STABLE_FOR_SECONDS = 2.0
MIN_SECONDS_BETWEEN_SHOTS = 5.0
COMPARE_WIDTH = 480

# None = toute la vidéo. Exemple pour ignorer 20 % à droite :
# DETECTION_ROI = (0.0, 0.0, 0.80, 1.0)
DETECTION_ROI = None
SAVE_ONLY_ROI = False

SCREENSHOT_EXTENSION = ".jpg"
JPEG_QUALITY = 92

# ========================================================================


@dataclass
class ScreenshotInfo:
    filename: str
    timestamp_seconds: float
    timestamp: str
    difference: float


def timestamp(seconds: float) -> str:
    total = max(0, int(round(seconds)))
    td = timedelta(seconds=total)
    h = td.days * 24 + td.seconds // 3600
    m = (td.seconds % 3600) // 60
    s = td.seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def timestamp_filename(seconds: float) -> str:
    h, m, s = timestamp(seconds).split(":")
    return f"{h}h{m}m{s}s"


def date_from_filename(filename: str) -> str:
    match = re.search(r"(?<!\d)(\d{4}-\d{2}-\d{2})(?!\d)", filename)
    if not match:
        raise ValueError(f"Aucune date YYYY-MM-DD trouvée dans : {filename}")
    return match.group(1)


def resolve_video(name: str) -> Path:
    video = Path(name).expanduser()
    if not video.is_absolute():
        video = Path.cwd() / video
    if not video.is_file():
        raise FileNotFoundError(f"Vidéo introuvable : {video}")
    return video.resolve()


def crop_roi(frame):
    if DETECTION_ROI is None:
        return frame
    h, w = frame.shape[:2]
    x1, y1, x2, y2 = DETECTION_ROI
    return frame[int(y1 * h):int(y2 * h), int(x1 * w):int(x2 * w)]


def comparison_frame(frame):
    frame = crop_roi(frame)
    h, w = frame.shape[:2]
    if w > COMPARE_WIDTH:
        nh = max(1, int(h * COMPARE_WIDTH / w))
        frame = cv2.resize(
            frame, (COMPARE_WIDTH, nh), interpolation=cv2.INTER_AREA
        )
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return cv2.GaussianBlur(gray, (5, 5), 0)


def frame_difference(a, b) -> float:
    if a.shape != b.shape:
        b = cv2.resize(b, (a.shape[1], a.shape[0]))
    return float(np.mean(cv2.absdiff(a, b)) / 255.0)


def save_frame(frame, path: Path):
    image = crop_roi(frame) if SAVE_ONLY_ROI else frame
    if path.suffix.lower() in (".jpg", ".jpeg"):
        ok = cv2.imwrite(
            str(path), image, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY]
        )
    else:
        ok = cv2.imwrite(str(path), image)
    if not ok:
        raise RuntimeError(f"Impossible d'enregistrer {path}")


def extract_screenshots(video: Path, output_dir: Path):
    shots_dir = output_dir / "screenshots"
    shots_dir.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise RuntimeError(f"OpenCV ne peut pas ouvrir : {video}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    duration = count / fps if fps else 0
    print(f"[images] FPS={fps:.2f}, durée={timestamp(duration)}")

    step = max(1, int(round(fps * ANALYZE_EVERY_SECONDS)))
    stable_needed = max(
        1, int(round(STABLE_FOR_SECONDS / ANALYZE_EVERY_SECONDS))
    )

    saved = []
    reference = previous = None
    candidate_frame = candidate_cmp = None
    candidate_time = candidate_diff = 0.0
    stable_count = 0
    last_saved = -1e9
    frame_index = 0

    while True:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        ok, frame = cap.read()
        if not ok:
            break
        t = frame_index / fps if fps else 0.0
        cmpf = comparison_frame(frame)

        if reference is None:
            reference = previous = cmpf
            name = timestamp_filename(t) + SCREENSHOT_EXTENSION
            save_frame(frame, shots_dir / name)
            saved.append(ScreenshotInfo(name, t, timestamp(t), 0.0))
            last_saved = t
            frame_index += step
            continue

        diff_ref = frame_difference(cmpf, reference)
        diff_prev = frame_difference(cmpf, previous)

        if diff_ref >= CHANGE_THRESHOLD:
            if candidate_frame is None or diff_prev > STABLE_THRESHOLD:
                stable_count = 0
            else:
                stable_count += 1
            candidate_frame = frame.copy()
            candidate_cmp = cmpf.copy()
            candidate_time = t
            candidate_diff = diff_ref

            if (
                stable_count >= stable_needed
                and t - last_saved >= MIN_SECONDS_BETWEEN_SHOTS
            ):
                name = timestamp_filename(candidate_time) + SCREENSHOT_EXTENSION
                save_frame(candidate_frame, shots_dir / name)
                saved.append(
                    ScreenshotInfo(
                        name,
                        candidate_time,
                        timestamp(candidate_time),
                        candidate_diff,
                    )
                )
                print(
                    f"[images] {timestamp(candidate_time)} -> {name} "
                    f"(diff={candidate_diff:.3f})"
                )
                reference = candidate_cmp.copy()
                last_saved = candidate_time
                candidate_frame = candidate_cmp = None
                stable_count = 0
        else:
            candidate_frame = candidate_cmp = None
            stable_count = 0

        previous = cmpf
        frame_index += step

    cap.release()

    (output_dir / "screenshots.json").write_text(
        json.dumps([asdict(x) for x in saved], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "screenshots.txt").write_text(
        "".join(f"{x.timestamp}  {x.filename}\n" for x in saved),
        encoding="utf-8",
    )
    print(f"[images] {len(saved)} screenshot(s) conservé(s).")


def transcribe(video: Path, output_dir: Path):
    print(f"[whisper] Chargement : {WHISPER_MODEL}")
    model = WhisperModel(
        WHISPER_MODEL,
        device=WHISPER_DEVICE,
        compute_type=WHISPER_COMPUTE_TYPE,
    )
    segments_gen, info = model.transcribe(
        str(video), language=LANGUAGE, vad_filter=True, beam_size=5
    )
    segments = list(segments_gen)

    texts = [s for s in segments if s.text.strip()]
    (output_dir / "transcription.txt").write_text(
        "".join(s.text.strip() + "\n" for s in texts), encoding="utf-8"
    )
    (output_dir / "transcription_timestamped.txt").write_text(
        "".join(
            f"[{timestamp(s.start)} --> {timestamp(s.end)}] {s.text.strip()}\n"
            for s in texts
        ),
        encoding="utf-8",
    )

    data = {
        "language": info.language,
        "language_probability": info.language_probability,
        "segments": [
            {
                "start": s.start,
                "end": s.end,
                "start_timestamp": timestamp(s.start),
                "end_timestamp": timestamp(s.end),
                "text": s.text.strip(),
            }
            for s in texts
        ],
    }
    (output_dir / "transcription.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[whisper] {len(texts)} segments.")


def main():
    parser = argparse.ArgumentParser(
        description="Extraction D&D : Faster-Whisper + screenshots automatiques."
    )
    parser.add_argument(
        "video",
        help='Nom de la vidéo située dans le dossier courant, par exemple "2026-09-29 19-01-48.mkv".',
    )
    parser.add_argument("--screenshots-only", action="store_true")
    parser.add_argument("--transcription-only", action="store_true")
    args = parser.parse_args()

    if args.screenshots_only and args.transcription_only:
        parser.error("Les deux modes exclusifs ne peuvent pas être utilisés ensemble.")

    try:
        video = resolve_video(args.video)
        session_date = date_from_filename(video.name)
        output = OUTPUT_ROOT / session_date
        output.mkdir(parents=True, exist_ok=True)

        print(f"Vidéo  : {video}")
        print(f"Sortie : {output}")

        if not args.transcription_only:
            extract_screenshots(video, output)
        if not args.screenshots_only:
            transcribe(video, output)

        print(f"Terminé : {output}")
        return 0
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(f"ERREUR : {exc}", file=sys.stderr)
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
