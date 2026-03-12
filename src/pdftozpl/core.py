from __future__ import annotations

import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

DEFAULT_DPI = 280
DEFAULT_THRESHOLD = 186
_CANCELLED = False


class PdfToZplError(RuntimeError):
    pass


@dataclass(frozen=True)
class ZplConfig:
    dpi: int = DEFAULT_DPI
    threshold: int = DEFAULT_THRESHOLD
    origin_x: int = 0
    origin_y: int = 0


def install_signal_handlers() -> None:
    def _handle_sigterm(_signum: int, _frame: object) -> None:
        global _CANCELLED
        _CANCELLED = True
        print("INFO: Job cancelled", file=sys.stderr)

    signal.signal(signal.SIGTERM, _handle_sigterm)
    signal.signal(signal.SIGPIPE, signal.SIG_IGN)


def parse_cups_options(option_string: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for token in shlex.split(option_string or ""):
        if "=" in token:
            key, value = token.split("=", 1)
            parsed[key.replace("-", "_")] = value
        else:
            parsed[token.replace("-", "_")] = "true"
    return parsed


def make_config(dpi: int = DEFAULT_DPI, threshold: int = DEFAULT_THRESHOLD, origin_x: int = 0, origin_y: int = 0) -> ZplConfig:
    if dpi <= 0:
        raise PdfToZplError("DPI must be positive")
    if not 0 <= threshold <= 255:
        raise PdfToZplError("Threshold must be between 0 and 255")
    return ZplConfig(dpi=dpi, threshold=threshold, origin_x=origin_x, origin_y=origin_y)


def convert_pdf_to_zpl(pdf_path: Path, output, config: ZplConfig, copies: int = 1) -> None:
    _require_tool("pdfinfo")
    _require_tool("pdftoppm")
    page_count = _read_page_count(pdf_path)
    with tempfile.TemporaryDirectory(prefix="pdftozpl-") as tmpdir:
        for page in range(1, page_count + 1):
            if _CANCELLED:
                break
            print(f"INFO: Rasterizing page {page}/{page_count} at {config.dpi} DPI", file=sys.stderr)
            pgm_path = _render_page(pdf_path, page, config.dpi, Path(tmpdir))
            width, height, max_value, raster, bytes_per_sample = _read_pgm(pgm_path)
            row_bytes, total_bytes, hex_data = _pack_bits(width, height, max_value, raster, bytes_per_sample, config.threshold)
            output.write(_build_label(width, height, row_bytes, total_bytes, hex_data, config.origin_x, config.origin_y, copies))
            print(f"PAGE: {page} {copies}", file=sys.stderr)


def _build_label(width: int, height: int, row_bytes: int, total_bytes: int, hex_data: str, origin_x: int, origin_y: int, copies: int) -> str:
    return (
        f"^XA\n"
        f"^PW{width + max(0, origin_x)}\n"
        f"^LL{height + max(0, origin_y)}\n"
        f"^LH0,0\n"
        f"^FO{origin_x},{origin_y}\n"
        f"^GFA,{total_bytes},{total_bytes},{row_bytes},{hex_data}\n"
        f"^FS\n"
        f"^PQ{max(1, copies)},0,1,N\n"
        f"^XZ\n"
    )


def _require_tool(name: str) -> None:
    if shutil.which(name) is None:
        raise PdfToZplError(f"Required executable not found in PATH: {name}")


def _read_page_count(pdf_path: Path) -> int:
    try:
        result = subprocess.run(["pdfinfo", str(pdf_path)], check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        raise PdfToZplError(exc.stderr.strip() or exc.stdout.strip() or "pdfinfo failed") from exc
    match = re.search(r"^Pages:\s+(\d+)\s*$", result.stdout, re.MULTILINE)
    if not match:
        raise PdfToZplError("Unable to determine PDF page count")
    return int(match.group(1))


def _render_page(pdf_path: Path, page: int, dpi: int, workdir: Path) -> Path:
    prefix = workdir / f"page-{page}"
    command = [
        "pdftoppm",
        "-gray",
        "-r",
        str(dpi),
        "-f",
        str(page),
        "-l",
        str(page),
        "-singlefile",
        str(pdf_path),
        str(prefix),
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise PdfToZplError(result.stderr.strip() or f"pdftoppm failed for page {page}")
    pgm_path = prefix.with_suffix(".pgm")
    if not pgm_path.exists():
        raise PdfToZplError(f"Expected raster output not found: {pgm_path}")
    return pgm_path


def _read_pgm(path: Path) -> tuple[int, int, int, bytes, int]:
    with path.open("rb") as handle:
        magic = _read_pnm_token(handle)
        if magic != b"P5":
            raise PdfToZplError(f"Unsupported raster format: {magic!r}")
        width = int(_read_pnm_token(handle))
        height = int(_read_pnm_token(handle))
        max_value = int(_read_pnm_token(handle))
        bytes_per_sample = 1 if max_value < 256 else 2
        raster = handle.read(width * height * bytes_per_sample)
    if len(raster) != width * height * bytes_per_sample:
        raise PdfToZplError(f"Raster data size mismatch for {path}")
    return width, height, max_value, raster, bytes_per_sample


def _read_pnm_token(handle) -> bytes:
    token = bytearray()
    while True:
        char = handle.read(1)
        if not char:
            raise PdfToZplError("Unexpected end of PNM header")
        if char == b"#":
            handle.readline()
            continue
        if char not in b" \t\r\n":
            token.extend(char)
            break
    while True:
        char = handle.read(1)
        if not char or char in b" \t\r\n":
            break
        if char == b"#":
            handle.readline()
            break
        token.extend(char)
    return bytes(token)


def _pack_bits(width: int, height: int, max_value: int, raster: bytes, bytes_per_sample: int, threshold: int) -> tuple[int, int, str]:
    row_bytes = (width + 7) // 8
    packed = bytearray(row_bytes * height)
    offset = 0
    threshold_scaled = threshold * max_value
    for y in range(height):
        row_offset = y * row_bytes
        for x in range(width):
            if bytes_per_sample == 1:
                sample = raster[offset]
                offset += 1
            else:
                sample = int.from_bytes(raster[offset:offset + 2], "big")
                offset += 2
            if sample * 255 <= threshold_scaled:
                packed[row_offset + (x // 8)] |= 1 << (7 - (x % 8))
    return row_bytes, len(packed), packed.hex().upper()