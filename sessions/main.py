from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
import sys
import time
import traceback
from dataclasses import asdict, dataclass
from datetime import timedelta
from pathlib import Path

import cv2
import numpy as np

OUTPUT_ROOT = Path(r"C:\Users\cheyn\OneDrive\Documents\14. DND\alan_pas_riche\sessions")
WHISPER_MODEL = "medium"
WHISPER_DEVICE = "cuda"
WHISPER_COMPUTE_TYPE = "float32"
WHISPER_FALLBACK_CPU = True
WHISPER_CPU_COMPUTE_TYPE = "int8"
WHISPER_BEAM_SIZE = 5
LANGUAGE = "fr"
CUDNN_DIR = Path(r"C:\Program Files\NVIDIA\CUDNN\v9.28\bin\12.9\x64")

ANALYZE_EVERY_SECONDS = 1.0
CHANGE_THRESHOLD = 0.12
STABLE_THRESHOLD = 0.035
STABLE_FOR_SECONDS = 2.0
MIN_SECONDS_BETWEEN_SHOTS = 5.0
COMPARE_WIDTH = 480
DETECTION_ROI = None
SAVE_ONLY_ROI = False
SCREENSHOT_EXTENSION = ".jpg"
JPEG_QUALITY = 92
IMAGE_DEVICE = "cuda"  # cuda : FFmpeg/NVDEC ; cpu : OpenCV

_DLL_HANDLES = []


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
        frame = cv2.resize(frame, (COMPARE_WIDTH, nh), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return cv2.GaussianBlur(gray, (5, 5), 0)


def frame_difference(a, b) -> float:
    if a.shape != b.shape:
        b = cv2.resize(b, (a.shape[1], a.shape[0]))
    return float(np.mean(cv2.absdiff(a, b)) / 255.0)


def save_frame(frame, path: Path):
    image = crop_roi(frame) if SAVE_ONLY_ROI else frame
    if path.suffix.lower() in (".jpg", ".jpeg"):
        ok = cv2.imwrite(str(path), image, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
    else:
        ok = cv2.imwrite(str(path), image)
    if not ok:
        raise RuntimeError(f"Impossible d'enregistrer {path}")


def video_metadata(video: Path):
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise RuntimeError(f"OpenCV ne peut pas ouvrir : {video}")
    try:
        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    finally:
        cap.release()
    if fps <= 0 or width <= 0 or height <= 0:
        raise RuntimeError("Métadonnées vidéo invalides")
    return fps, width, height, count / fps


def sampled_frames_cpu(video: Path, fps: float):
    """Lecture séquentielle OpenCV ; évite les seek répétés."""
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise RuntimeError(f"Impossible d'ouvrir : {video}")
    step = max(1, round(fps * ANALYZE_EVERY_SECONDS))
    index = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if index % step == 0:
                yield index / fps, frame
            index += 1
    finally:
        cap.release()


def sampled_frames_gpu(video: Path, width: int, height: int):
    """NVDEC via FFmpeg, puis échantillonnage et transfert des images vers le CPU.

    Nécessite un exécutable FFmpeg avec support CUDA/NVDEC.
    Les images BGR transmises à OpenCV sont en mémoire CPU.
    """
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("FFmpeg absent du PATH (requis pour NVDEC)")
    if ANALYZE_EVERY_SECONDS <= 0:
        raise ValueError("ANALYZE_EVERY_SECONDS doit être positif")
    frame_bytes = width * height * 3
    # stderr dans un fichier : évite de bloquer FFmpeg si le tampon se remplit.
    with tempfile.TemporaryFile(mode="w+b") as error_log:
        command = [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin",
            "-hwaccel", "cuda", "-i", str(video),
            "-vf", f"fps={1.0 / ANALYZE_EVERY_SECONDS:.12g}",
            "-f", "rawvideo", "-pix_fmt", "bgr24", "pipe:1",
        ]
        proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=error_log)
        completed = False
        index = 0
        try:
            while True:
                # read(n) sur un pipe peut retourner moins de n octets.
                chunks = []
                remaining = frame_bytes
                while remaining:
                    chunk = proc.stdout.read(remaining)
                    if not chunk:
                        break
                    chunks.append(chunk)
                    remaining -= len(chunk)
                if remaining == frame_bytes:
                    break
                if remaining:
                    raise RuntimeError("Image FFmpeg incomplète")
                frame = np.frombuffer(b"".join(chunks), dtype=np.uint8).reshape(
                    height, width, 3
                ).copy()
                yield index * ANALYZE_EVERY_SECONDS, frame
                index += 1
            code = proc.wait()
            if code != 0:
                error_log.seek(0)
                details = error_log.read().decode("utf-8", errors="replace")[-1500:]
                raise RuntimeError(f"FFmpeg NVDEC (code {code}) : {details}")
            completed = True
        finally:
            if not completed and proc.poll() is None:
                proc.kill()
            if proc.stdout:
                proc.stdout.close()
            proc.wait()


def extract_screenshots(video: Path, output_dir: Path, device: str = IMAGE_DEVICE):
    fps, width, height, duration = video_metadata(video)
    print(f"[images] FPS={fps:.2f}, durée={timestamp(duration)}")
    stable_needed = max(1, int(round(STABLE_FOR_SECONDS / ANALYZE_EVERY_SECONDS)))

    def run(current_device: str):
        print(f"[images] Décodage : {current_device.upper()}", flush=True)
        if current_device == "cuda":
            frames = sampled_frames_gpu(video, width, height)
        else:
            frames = sampled_frames_cpu(video, fps)

        # Les fichiers sont écrits dans un dossier temporaire pour ne pas
        # conserver des résultats partiels en cas de repli CPU.
        with tempfile.TemporaryDirectory(dir=output_dir, prefix="shots_tmp_") as tmp:
            shots_dir = Path(tmp)
            saved = []
            reference = previous = None
            candidate_frame = candidate_cmp = None
            candidate_time = candidate_diff = 0.0
            stable_count = 0
            last_saved = -1e9

            for t, frame in frames:
                cmpf = comparison_frame(frame)
                if reference is None:
                    reference = previous = cmpf
                    name = timestamp_filename(t) + SCREENSHOT_EXTENSION
                    save_frame(frame, shots_dir / name)
                    saved.append(ScreenshotInfo(name, t, timestamp(t), 0.0))
                    last_saved = t
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
                    if (stable_count >= stable_needed and
                            t - last_saved >= MIN_SECONDS_BETWEEN_SHOTS):
                        name = timestamp_filename(candidate_time) + SCREENSHOT_EXTENSION
                        save_frame(candidate_frame, shots_dir / name)
                        saved.append(ScreenshotInfo(
                            name, candidate_time, timestamp(candidate_time), candidate_diff
                        ))
                        print(f"[images] {timestamp(candidate_time)} -> {name} "
                              f"(diff={candidate_diff:.3f})")
                        reference = candidate_cmp.copy()
                        last_saved = candidate_time
                        candidate_frame = candidate_cmp = None
                        stable_count = 0
                else:
                    candidate_frame = candidate_cmp = None
                    stable_count = 0
                previous = cmpf

            if not saved:
                raise RuntimeError("Aucune image extraite")
            final_dir = output_dir / "screenshots"
            final_dir.mkdir(parents=True, exist_ok=True)
            for item in saved:
                (shots_dir / item.filename).replace(final_dir / item.filename)
            (output_dir / "screenshots.json").write_text(
                json.dumps([asdict(x) for x in saved], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            (output_dir / "screenshots.txt").write_text(
                "".join(f"{x.timestamp}  {x.filename}\n" for x in saved),
                encoding="utf-8",
            )
            print(f"[images] {len(saved)} screenshot(s) conservé(s).")

    if device == "cpu":
        run("cpu")
    else:
        try:
            run("cuda")
        except (RuntimeError, OSError) as exc:
            print(f"[images] NVDEC indisponible : {exc}")
            print("[images] Repli automatique sur CPU...")
            run("cpu")


def configure_cuda_dlls():
    if os.name != "nt" or not CUDNN_DIR.is_dir():
        return
    os.environ["PATH"] = str(CUDNN_DIR) + os.pathsep + os.environ.get("PATH", "")
    if hasattr(os, "add_dll_directory"):
        _DLL_HANDLES.append(os.add_dll_directory(str(CUDNN_DIR)))
    print(f"[whisper] cuDNN : {CUDNN_DIR}")


def transcribe(video: Path, output_dir: Path, model_name: str, device: str, compute_type: str, fallback_cpu: bool):
    import av
    from faster_whisper import WhisperModel

    if device in ("cuda", "auto"):
        configure_cuda_dlls()

    txt_path = output_dir / "transcription.txt"
    timed_path = output_dir / "transcription_timestamped.txt"
    json_path = output_dir / "transcription.json"
    with av.open(str(video)) as container:
        duration = float(container.duration / av.time_base) if container.duration else 0.0

    def run(current_device: str, current_compute: str):
        print(f"[whisper] Chargement : {model_name} ({current_device}, {current_compute})", flush=True)
        model = WhisperModel(model_name, device=current_device, compute_type=current_compute)
        segments_gen, info = model.transcribe(str(video), language=LANGUAGE, vad_filter=True, beam_size=WHISPER_BEAM_SIZE)
        tmp_txt = output_dir / "transcription.txt.part"
        tmp_timed = output_dir / "transcription_timestamped.txt.part"
        tmp_json = output_dir / "transcription.json.part"
        data_segments = []
        start_time = time.monotonic()
        with tmp_txt.open("w", encoding="utf-8") as plain, tmp_timed.open("w", encoding="utf-8") as timed:
            for segment in segments_gen:
                content = segment.text.strip()
                if not content:
                    continue
                entry = {"start": segment.start, "end": segment.end, "start_timestamp": timestamp(segment.start), "end_timestamp": timestamp(segment.end), "text": content}
                data_segments.append(entry)
                plain.write(content + "\n")
                timed.write(f"[{entry['start_timestamp']} --> {entry['end_timestamp']}] {content}\n")
                plain.flush()
                timed.flush()
                elapsed = time.monotonic() - start_time
                progress = min(100.0, segment.end / duration * 100.0) if duration > 0 else 0.0
                print(f"\r[whisper] {progress:5.1f}% | {timestamp(segment.end)} | écoulé : {timestamp(elapsed)} | segments : {len(data_segments)}", end="", flush=True)
        print()
        data = {"language": info.language, "language_probability": info.language_probability, "device": current_device, "compute_type": current_compute, "segments": data_segments}
        tmp_json.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp_txt.replace(txt_path)
        tmp_timed.replace(timed_path)
        tmp_json.replace(json_path)
        print(f"[whisper] Terminé : {len(data_segments)} segments en {timestamp(time.monotonic() - start_time)}")

    try:
        run(device, compute_type)
    except (RuntimeError, OSError) as exc:
        if not fallback_cpu or device == "cpu":
            raise
        print(f"\n[whisper] Échec GPU : {exc}")
        print("[whisper] Nouvelle tentative sur CPU depuis le début...")
        run("cpu", WHISPER_CPU_COMPUTE_TYPE)


def main():
    parser = argparse.ArgumentParser(description="Extraction D&D : Faster-Whisper + screenshots automatiques.")
    parser.add_argument("video", help='Vidéo à traiter, par exemple "2026-11-17 19-06-59.mp4".')
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--screenshots-only", action="store_true")
    modes.add_argument("--transcription-only", action="store_true")
    parser.add_argument("--image-device", choices=["cuda", "cpu"], default=IMAGE_DEVICE,
                        help="Décodage vidéo : cuda (NVDEC via FFmpeg) ou cpu (OpenCV)")
    parser.add_argument("--device", choices=["auto", "cuda", "cpu"], default=WHISPER_DEVICE)
    parser.add_argument("--compute-type", default=None, help="Ex. float32, int8, auto ; défaut selon device")
    parser.add_argument("--model", default=WHISPER_MODEL, help="Modèle Whisper : tiny, base, small, medium, large-v3...")
    parser.add_argument("--no-cpu-fallback", action="store_true", help="Ne pas réessayer sur CPU si CUDA échoue")
    args = parser.parse_args()
    compute_type = args.compute_type or (WHISPER_CPU_COMPUTE_TYPE if args.device == "cpu" else WHISPER_COMPUTE_TYPE)
    try:
        video = resolve_video(args.video)
        output = OUTPUT_ROOT / date_from_filename(video.name)
        output.mkdir(parents=True, exist_ok=True)
        print(f"Vidéo  : {video}")
        print(f"Sortie : {output}")
        if not args.transcription_only:
            extract_screenshots(video, output, args.image_device)
        if not args.screenshots_only:
            transcribe(video, output, args.model, args.device, compute_type, WHISPER_FALLBACK_CPU and not args.no_cpu_fallback)
        print(f"Terminé : {output}")
        return 0
    except KeyboardInterrupt:
        print("\nInterrompu par l'utilisateur.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"ERREUR : {exc}", file=sys.stderr)
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
