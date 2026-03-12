#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
PREFIX="${PREFIX:-/usr/local}"
DESTDIR="${DESTDIR:-}"
PYTHON_BIN="${PYTHON_BIN:-$(command -v python3)}"

resolve_filter_dir() {
  if [[ -n "${CUPS_FILTER_DIR:-}" ]]; then
    printf '%s\n' "$CUPS_FILTER_DIR"
    return
  fi
  local candidates=(
    "${PREFIX}/lib/cups/filter"
    "${PREFIX}/libexec/cups/filter"
    "/usr/lib/cups/filter"
    "/usr/libexec/cups/filter"
  )
  local candidate
  for candidate in "${candidates[@]}"; do
    if [[ -d "${DESTDIR}${candidate}" || "$candidate" == "${PREFIX}/lib/cups/filter" || "$candidate" == "${PREFIX}/libexec/cups/filter" ]]; then
      printf '%s\n' "$candidate"
      return
    fi
  done
}

resolve_mime_dir() {
  if [[ -n "${CUPS_MIME_DIR:-}" ]]; then
    printf '%s\n' "$CUPS_MIME_DIR"
    return
  fi
  local candidates=(
    "${PREFIX}/share/cups/mime"
    "/usr/share/cups/mime"
  )
  local candidate
  for candidate in "${candidates[@]}"; do
    if [[ -d "${DESTDIR}${candidate}" || "$candidate" == "${PREFIX}/share/cups/mime" ]]; then
      printf '%s\n' "$candidate"
      return
    fi
  done
}

resolve_model_dir() {
  if [[ -n "${CUPS_MODEL_DIR:-}" ]]; then
    printf '%s\n' "$CUPS_MODEL_DIR"
    return
  fi
  local candidates=(
    "/usr/share/ppd/cups-raster/cab"
    "${PREFIX}/share/ppd/cups-raster/cab"
    "/usr/share/cups/model"
    "${PREFIX}/share/cups/model"
  )
  local candidate
  for candidate in "${candidates[@]}"; do
    if [[ -d "${DESTDIR}${candidate}" || "$candidate" == "${PREFIX}/share/ppd/cups-raster/cab" || "$candidate" == "${PREFIX}/share/cups/model" ]]; then
      printf '%s\n' "$candidate"
      return
    fi
  done
}

FILTER_DIR="$(resolve_filter_dir)"
MIME_DIR="$(resolve_mime_dir)"
MODEL_DIR="$(resolve_model_dir)"
LIB_DIR="${PREFIX}/share/pdftozpl"
BIN_DIR="${PREFIX}/bin"

install -d "${DESTDIR}${FILTER_DIR}" "${DESTDIR}${MIME_DIR}" "${DESTDIR}${MODEL_DIR}" "${DESTDIR}${LIB_DIR}" "${DESTDIR}${BIN_DIR}"
rm -rf "${DESTDIR}${LIB_DIR}/pdftozpl"
cp -R "${ROOT_DIR}/src/pdftozpl" "${DESTDIR}${LIB_DIR}/pdftozpl"
install -m 0644 "${ROOT_DIR}/packaging/cups/pdftozpl.convs" "${DESTDIR}${MIME_DIR}/pdftozpl.convs"
install -m 0644 "${ROOT_DIR}/cabma2300.ppd" "${DESTDIR}${MODEL_DIR}/cabma2300.ppd"

cat > "${DESTDIR}${FILTER_DIR}/pdftozpl-filter" <<EOF
#!${PYTHON_BIN}
import sys
sys.path.insert(0, "${LIB_DIR}")
from pdftozpl.cli import filter_main

raise SystemExit(filter_main())
EOF
chmod 0755 "${DESTDIR}${FILTER_DIR}/pdftozpl-filter"

cat > "${DESTDIR}${BIN_DIR}/pdftozpl" <<EOF
#!${PYTHON_BIN}
import sys
sys.path.insert(0, "${LIB_DIR}")
from pdftozpl.cli import main

raise SystemExit(main())
EOF
chmod 0755 "${DESTDIR}${BIN_DIR}/pdftozpl"

cat <<EOF
Installed pdftozpl assets:
  Python package: ${DESTDIR}${LIB_DIR}/pdftozpl
  CLI wrapper:     ${DESTDIR}${BIN_DIR}/pdftozpl
  CUPS filter:     ${DESTDIR}${FILTER_DIR}/pdftozpl-filter
  CUPS mime convs: ${DESTDIR}${MIME_DIR}/pdftozpl.convs
  CUPS PPD:        ${DESTDIR}${MODEL_DIR}/cabma2300.ppd

Override locations with PREFIX, DESTDIR, CUPS_FILTER_DIR, CUPS_MIME_DIR, CUPS_MODEL_DIR, or PYTHON_BIN.
After deploying to a live system, reload/restart CUPS so it notices the new filter and MIME rule.
EOF