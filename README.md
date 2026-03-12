## PdfToZpl

Small CUPS filter utility for printing PDFs on a **CAB MACH2/300** on **Linux** by converting PDF pages to monochrome images and embedding them into **ZPL `^GF`** commands.

This project is for **Linux**. On **Windows**, CAB provides a **GDI driver** for this printer, so this workaround is not the target use case there.

The motivation is simple: there is no usable native Linux driver for MACH2/300, but the existing **CAB MACH4/300** setup can be reused if the job stream is converted to ZPL first.

Official CAB Linux driver downloads:

- `https://www.cab.de/en/support/support-downloads/?gruppierung=5&kategorie=28&produkt=375`

## How it works

1. CUPS submits a PDF job to `pdftozpl-filter`.
2. The filter renders each PDF page to a lossless grayscale image using `pdftoppm`.
3. The image is thresholded to 1-bit black/white.
4. The packed bitmap is emitted as ZPL `^GFA`.

Default raster DPI is **280**.

## Requirements

- Python 3.11+
- CUPS
- Poppler tools:
  - `pdftoppm`
  - `pdfinfo`

## Install the filter

Use the supplied deploy script:

- `sudo PREFIX=/usr CUPS_FILTER_DIR=/usr/lib/cups/filter CUPS_MIME_DIR=/usr/share/cups/mime CUPS_MODEL_DIR=/usr/share/ppd/cups-raster/cab packaging/cups/install.sh`

The install script copies:

- the Python package
- the `pdftozpl-filter` CUPS filter
- the CUPS MIME conversion file
- `cabma2300.ppd`

For GUI-based printer setup on this Linux system, the important PPD destination is:

- `/usr/share/ppd/cups-raster/cab`

That is where the existing CAB Linux drivers are installed, and placing `cabma2300.ppd` there makes it much more likely that CUPS GUI tools will list it alongside the official CAB entries.

Then refresh CUPS so the new filter and PPD are picked up:

- `sudo systemctl restart cups`

You can verify that the PPD is visible to CUPS with:

- `lpinfo -m | grep -i cabma2300`

## Two ways to integrate with CUPS

### Option 1: manual filter setup

Install the filter as above, then add the filter mapping to the PPD you want to use:

- `*cupsFilter2: "application/pdf application/vnd.cups-raw 50 pdftozpl-filter"`

This tells CUPS to pass PDF jobs through `pdftozpl-filter`, which outputs raw ZPL for the printer.

### Option 2: use the supplied dedicated MACH2/300 PPD

This repository includes:

- `cabma2300.ppd`

- `cabma2300.ppd` is a small MACH2/300-branded PPD intended for this project.

It already contains:

- `*cupsFilter2: "application/pdf application/vnd.cups-raw 50 pdftozpl-filter"`

If you use this PPD, install the printer with that file as the driver/PPD.

In other words, for MACH2/300 on Linux, the practical workflow is:

- deploy `pdftozpl-filter`
- use `cabma2300.ppd`
- print PDFs normally through CUPS

## Notes on printer options

Most of the vendor PPD options are not important for this project, because the real payload sent to the printer is generated ZPL image data.

For that reason, a **dedicated minimal MACH2/300 PPD** is cleaner than relying on a MACH4/300-derived vendor PPD.

Why a dedicated PPD may be better:

- less confusing for users
- easier to brand as MACH2/300
- only the relevant paper/label defaults need to remain
- avoids carrying a large number of irrelevant vendor options

## Useful filter options

The filter accepts these CUPS options:

- `pdftozpl-dpi=280`
- `pdftozpl-threshold=186`
- `pdftozpl-origin-x=0`
- `pdftozpl-origin-y=0`

Equivalent aliases with `zpl-...` also work.

## Manual test example

- `PYTHONPATH=src python3 packaging/cups/filter/pdftozpl-filter 1 user "Test Job" 1 "pdftozpl-dpi=280" sample.pdf > out.zpl`

## Recommendation

Use `cabma2300.ppd` as the default supplied PPD for MACH2/300.

## License

This project is free to use, copy, modify, and redistribute.

It is provided **as is**, without warranties or conditions of any kind.

See `LICENSE` for the full text.