#!/usr/bin/env python3
"""Audit the isolated MOT environment without downloading models or data."""

from __future__ import annotations

import argparse
import importlib
import importlib.metadata
import json
import logging
import os
import platform
import shutil
import sys
from pathlib import Path
from typing import Any


LOGGER = logging.getLogger("check_mot_environment")
PROJECT_ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("YOLO_CONFIG_DIR", str(PROJECT_ROOT / ".cache"))
REQUIRED_PACKAGES = {
    "torch": "torch",
    "torchvision": "torchvision",
    "ultralytics": "ultralytics",
    "deep-sort-realtime": "deep_sort_realtime.deepsort_tracker",
    "opencv-python": "cv2",
    "numpy": "numpy",
    "scipy": "scipy",
    "pandas": "pandas",
    "tqdm": "tqdm",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Check the motpose Python packages, CUDA access, DeepSORT embedder, "
            "and FFmpeg availability without downloading a YOLO model."
        )
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        help="Optional path for the complete machine-readable audit result.",
    )
    parser.add_argument(
        "--allow-cpu",
        action="store_true",
        help="Do not fail solely because CUDA is unavailable.",
    )
    parser.add_argument(
        "--allow-missing-ffmpeg",
        action="store_true",
        help="Do not fail solely because the FFmpeg CLI is unavailable.",
    )
    return parser.parse_args()


def package_version(distribution: str) -> str:
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return "not-installed"


def audit_packages() -> tuple[dict[str, dict[str, Any]], list[str]]:
    packages: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    for distribution, module_name in REQUIRED_PACKAGES.items():
        version = package_version(distribution)
        try:
            importlib.import_module(module_name)
            import_ok = True
            error = None
        except Exception as exc:  # Import failures can include binary ABI errors.
            import_ok = False
            error = f"{type(exc).__name__}: {exc}"
            errors.append(f"{distribution}: {error}")
        packages[distribution] = {
            "version": version,
            "import_ok": import_ok,
            "error": error,
        }
    return packages, errors


def audit_cuda() -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    result: dict[str, Any] = {
        "available": False,
        "torch_built_cuda": None,
        "cudnn_version": None,
        "device_name": None,
        "device_capability": None,
        "tensor_smoke_test": False,
    }
    try:
        import torch

        result["torch_built_cuda"] = torch.version.cuda
        result["cudnn_version"] = torch.backends.cudnn.version()
        result["available"] = torch.cuda.is_available()
        if result["available"]:
            result["device_name"] = torch.cuda.get_device_name(0)
            result["device_capability"] = list(torch.cuda.get_device_capability(0))
            tensor = torch.tensor([1.0, 2.0], device="cuda")
            result["tensor_smoke_test"] = tensor.sum().item() == 3.0
    except Exception as exc:
        errors.append(f"CUDA smoke test: {type(exc).__name__}: {exc}")
    return result, errors


def audit_deepsort(cuda_available: bool) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    result = {"initialized": False, "embedder": "mobilenet", "embedder_gpu": cuda_available}
    try:
        from deep_sort_realtime.deepsort_tracker import DeepSort

        DeepSort(
            max_age=30,
            n_init=3,
            nn_budget=100,
            max_cosine_distance=0.2,
            max_iou_distance=0.7,
            embedder="mobilenet",
            embedder_gpu=cuda_available,
        )
        result["initialized"] = True
    except Exception as exc:
        errors.append(f"DeepSORT initialization: {type(exc).__name__}: {exc}")
    return result, errors


def main() -> int:
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    packages, errors = audit_packages()
    cuda, cuda_errors = audit_cuda()
    errors.extend(cuda_errors)
    deepsort, deepsort_errors = audit_deepsort(bool(cuda["available"]))
    errors.extend(deepsort_errors)
    ffmpeg_path = shutil.which("ffmpeg")

    packages_ok = all(item["import_ok"] for item in packages.values())
    cuda_ok = bool(cuda["available"] and cuda["tensor_smoke_test"])
    ffmpeg_ok = ffmpeg_path is not None
    strict_ready = packages_ok and deepsort["initialized"] and cuda_ok and ffmpeg_ok
    ready = (
        packages_ok
        and deepsort["initialized"]
        and (cuda_ok or args.allow_cpu)
        and (ffmpeg_ok or args.allow_missing_ffmpeg)
    )

    report = {
        "python": {
            "version": platform.python_version(),
            "executable": sys.executable,
            "conda_environment": Path(sys.prefix).name,
        },
        "packages": packages,
        "cuda": cuda,
        "deepsort": deepsort,
        "ffmpeg": {"available": ffmpeg_ok, "path": ffmpeg_path},
        "strict_ready_for_video_experiment": strict_ready,
        "ready_under_selected_policy": ready,
        "errors": errors,
    }

    rendered = json.dumps(report, indent=2, ensure_ascii=False)
    print(rendered)
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(rendered + "\n", encoding="utf-8")

    if not ffmpeg_ok:
        LOGGER.warning("FFmpeg CLI is unavailable; strict T02 prerequisites are not satisfied.")
    if not ready:
        LOGGER.error("MOT environment does not satisfy all requested execution prerequisites.")
        return 1
    LOGGER.info("MOT environment satisfies the requested execution prerequisites.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
