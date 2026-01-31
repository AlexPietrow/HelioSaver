from heliosaver import save_images_by_date_png, SOURCE_IDS

dates = [
    "2014-01-01T23:59:59Z",
    "2015-06-10T12:30:00Z",
]

out = save_images_by_date_png(
    dates=dates,
    source_id=SOURCE_IDS["SDO_AIA_1600"],
    base_output_path="./images_by_date",
)

print(out)
