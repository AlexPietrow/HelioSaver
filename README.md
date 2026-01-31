# heliosaver

**heliosaver** is a lightweight Python package for programmatic access to the  
[Helioviewer](https://helioviewer.org) image archive, enabling reproducible download and conversion of solar imagery into analysis-ready formats.

The package provides a minimal, scriptable interface to:

- query the *closest available observation* for a given time and instrument,
- download Helioviewer JP2 image data and associated XML metadata,
- convert imagery and metadata into **FITS files** with populated headers, and
- optionally export images as **PNG** files organized by observation date.

`heliosaver` is designed for situations where large amounts of data are needed quickly and where a reduced storage footprint is advantageous. It is well suited for rapid tests, exploratory analyses, and the initial construction of databases before full-resolution or mission-archive data are downloaded and used. Typical use cases include prototyping, context-image generation, and statistical studies where absolute photometric precision is not critical, such as estimating filling factors, morphological classification, or large-scale temporal coverage.

---

## Installation

Install directly from GitHub:

```bash
pip install git+https://github.com/AlexPietrow/heliosaver.git
```

For development or local modification:

```bash
git clone https://github.com/AlexPietrow/heliosaver.git
cd heliosaver
pip install -e .
```

Python ≥ 3.9 is required.

---

## Supported data products

`heliosaver` works with any Helioviewer `sourceId`.

For convenience, the package ships with a curated mapping of commonly used instruments and channels:

```python
heliosaver.SOURCE_IDS
```

This includes (among others):

- **SDO / AIA** (EUV and UV channels)
- **SDO / HMI** (continuum, magnetograms)
- **SOHO / EIT and LASCO**
- **STEREO / SECCHI**
- **IRIS / SJI**
- **GONG H-α**
- **Solar Orbiter / EUI**
- **GOES / SUVI**
- **RHESSI imaging products**

The mapping is provided purely as a convenience layer; internally, `heliosaver` always operates on explicit numeric `sourceId` values.

---

## Examples

### Download JP2 imagery and write FITS files

```python
from heliosaver import process_helioviewer_fits, SOURCE_IDS

dates = [
    "2014-01-01T23:59:59Z",
    "2015-06-10T12:30:00Z",
]

process_helioviewer_fits(
    dates=dates,
    source_id=SOURCE_IDS["SDO_HMI_continuum"],
    output_path="./fits_data",
)
```

This workflow:

1. queries Helioviewer for the closest available image to each timestamp,
2. downloads the corresponding JP2 image and XML metadata,
3. decodes the JP2 image into a NumPy array,
4. translates all XML metadata into FITS header keywords, and
5. writes a FITS file containing the image and metadata.

---

## Save PNG images grouped by date

```python
from heliosaver import save_images_by_date_png, SOURCE_IDS

dates = [
    "2014-01-01T23:59:59Z",
    "2015-06-10T12:30:00Z",
]

save_images_by_date_png(
    dates=dates,
    source_id=SOURCE_IDS["SDO_AIA_1600"],
    base_output_path="./images_by_date",
)
```

PNG images are written into `YYYY-MM-DD/` folders for easy browsing or outreach use.

---

## Command-line interface

`heliosaver` installs a small CLI for quick access:

```bash
heliosaver fits --source-id 18 --out ./fits --date 2014-01-01T23:59:59Z
heliosaver png  --source-id 15 --out ./png  --date 2014-01-01T23:59:59Z
```

Multiple `--date` arguments may be supplied.

---

## FITS headers

All metadata returned by the Helioviewer JP2 XML header is translated into FITS header keywords.

- FITS keyword length limits (8 characters) are respected.
- Keyword collisions are resolved automatically by suffixing.
- Non-numeric values are sanitized to remain FITS-compliant.

The raw XML header may optionally be stored alongside the FITS file.

---

## Intended use cases

- Solar image time series assembly  
- Context imagery for spectroscopy and slit instruments  
- Multi-instrument comparison workflows  
- Archival of Helioviewer-derived data products  
- Teaching and outreach material generation  

---

## Citing heliosaver

If you use `heliosaver` in a scientific publication, please cite the original data products accessed through Helioviewer and acknowledge this package as a data-access utility.

A dedicated reference paper for `heliosaver` is not yet available.
