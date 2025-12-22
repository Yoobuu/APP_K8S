import csv


def write_csv(csv_dir, schemas, data_by_sheet, sheet_order):
    for sheet_name in sheet_order:
        headers = schemas[sheet_name]
        csv_path = csv_dir / f"{sheet_name}.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(headers)
            for row in data_by_sheet.get(sheet_name, []):
                writer.writerow([row.get(header, "") for header in headers])
