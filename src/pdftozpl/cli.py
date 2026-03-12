from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

from .core import DEFAULT_DPI, DEFAULT_THRESHOLD, PdfToZplError, convert_pdf_to_zpl, install_signal_handlers, make_config, parse_cups_options


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Convert a PDF into ZPL ^GF image labels.")
    parser.add_argument("input_pdf", help="Path to the input PDF")
    parser.add_argument("-o", "--output", help="Write ZPL to this file instead of stdout")
    parser.add_argument("--dpi", type=int, default=DEFAULT_DPI, help=f"Raster DPI (default: {DEFAULT_DPI})")
    parser.add_argument("--threshold", type=int, default=DEFAULT_THRESHOLD, help=f"Black/white threshold 0-255 (default: {DEFAULT_THRESHOLD})")
    parser.add_argument("--origin-x", type=int, default=0, help="^FO X offset in dots")
    parser.add_argument("--origin-y", type=int, default=0, help="^FO Y offset in dots")
    parser.add_argument("--copies", type=int, default=1, help="Number of copies per page")
    args = parser.parse_args(argv)
    install_signal_handlers()
    temp_input: Path | None = None
    try:
        config = make_config(args.dpi, args.threshold, args.origin_x, args.origin_y)
        input_path, temp_input = _resolve_cli_input(args.input_pdf)
        if args.output:
            with open(args.output, "w", encoding="ascii", newline="") as handle:
                convert_pdf_to_zpl(input_path, handle, config, copies=args.copies)
        else:
            convert_pdf_to_zpl(input_path, sys.stdout, config, copies=args.copies)
        return 0
    except PdfToZplError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    finally:
        if temp_input:
            temp_input.unlink(missing_ok=True)


def filter_main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) not in (5, 6):
        print("ERROR: Expected job-id user title copies options [file]", file=sys.stderr)
        return 1
    job_id, user, title, copies_text, options_text, *rest = args
    del job_id, user, title
    install_signal_handlers()
    temp_input: str | None = None
    try:
        options = parse_cups_options(options_text)
        config = make_config(
            _option_int(options, "zpl_dpi", "pdftozpl_dpi", default=DEFAULT_DPI),
            _option_int(options, "zpl_threshold", "pdftozpl_threshold", default=DEFAULT_THRESHOLD),
            _option_int(options, "zpl_origin_x", "pdftozpl_origin_x", default=0),
            _option_int(options, "zpl_origin_y", "pdftozpl_origin_y", default=0),
        )
        copies = max(1, int(copies_text)) if rest else 1
        input_path = Path(rest[0]) if rest else _stdin_to_pdf()
        temp_input = None if rest else str(input_path)
        convert_pdf_to_zpl(input_path, sys.stdout, config, copies=copies)
        return 0
    except (PdfToZplError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    finally:
        if temp_input:
            Path(temp_input).unlink(missing_ok=True)


def _stdin_to_pdf() -> Path:
    temp = tempfile.NamedTemporaryFile(prefix="pdftozpl-", suffix=".pdf", delete=False)
    with temp:
        shutil.copyfileobj(sys.stdin.buffer, temp)
    return Path(temp.name)


def _resolve_cli_input(input_pdf: str) -> tuple[Path, Path | None]:
    if input_pdf != "-":
        return Path(input_pdf), None
    temp_path = _stdin_to_pdf()
    return temp_path, temp_path


def _option_int(options: dict[str, str], *names: str, default: int) -> int:
    for name in names:
        value = options.get(name)
        if value is not None:
            return int(value)
    return default


if __name__ == "__main__":
    raise SystemExit(main())