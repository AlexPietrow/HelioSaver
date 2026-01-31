from heliosaver import process_helioviewer_fits, SOURCE_IDS

dates = [
    "2014-01-01T23:59:59Z",
    "2015-06-10T12:30:00Z",
    "2016-03-20T05:45:15Z",
]

out = process_helioviewer_fits(
    dates=dates,
    source_id=SOURCE_IDS["SDO_HMI_continuum"],
    output_path="./fits_data",
)

print(out)
