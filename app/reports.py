from __future__ import annotations

import re


def month_filter(month: str) -> str:
    month = month.strip()
    if not month:
        return ""
    if not re.fullmatch(r"\d{4}-\d{2}", month):
        raise ValueError("Monat muss im Format JJJJ-MM angegeben werden.")
    return month


def csv_cell(value):
    if value is None:
        return ""
    text = str(value)
    return "'" + text if text[:1] in {"=", "+", "-", "@", "\t", "\r"} else text


def pdf_bytes(lines: list[str]) -> bytes:
    def pdf_text(value: str) -> str:
        return str(value).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    pages = [lines[index:index + 42] for index in range(0, max(1, len(lines)), 42)]
    objects = ["<< /Type /Catalog /Pages 2 0 R >>", "", "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    page_refs = []
    for page_lines in pages:
        content = ["BT", "/F1 11 Tf", "50 790 Td", "14 TL"]
        for line in page_lines:
            content.append(f"({pdf_text(line)}) Tj")
            content.append("T*")
        content.append("ET")
        stream = "\n".join(content).encode("latin-1", "replace")
        content_obj_num = len(objects) + 1
        objects.append(f"<< /Length {len(stream)} >>\nstream\n{stream.decode('latin-1')}\nendstream")
        page_obj_num = len(objects) + 1
        objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 3 0 R >> >> /Contents {content_obj_num} 0 R >>")
        page_refs.append(f"{page_obj_num} 0 R")
    objects[1] = f"<< /Type /Pages /Kids [{' '.join(page_refs)}] /Count {len(page_refs)} >>"
    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, obj in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{number} 0 obj\n{obj}\nendobj\n".encode("latin-1", "replace"))
    xref = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("ascii"))
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode("ascii"))
    return bytes(output)
