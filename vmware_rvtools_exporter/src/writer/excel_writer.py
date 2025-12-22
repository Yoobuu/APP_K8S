from openpyxl import Workbook


def write_excel(out_path, schemas, data_by_sheet, sheet_order):
    workbook = Workbook()
    default_sheet = workbook.active
    workbook.remove(default_sheet)

    for sheet_name in sheet_order:
        headers = schemas[sheet_name]
        worksheet = workbook.create_sheet(title=sheet_name)
        worksheet.append(headers)

        for row in data_by_sheet.get(sheet_name, []):
            worksheet.append([row.get(header, "") for header in headers])

    workbook.save(out_path)
