"""학생 페이지 범위 찾기"""
from src.extractor.pdf_reader import PDFReader
from pathlib import Path
import re

pdf_path = Path(r'C:\Users\iamhj\Downloads\유니브클래스_2025_인문사회상경_생기부대백과 (1).pdf')

with PDFReader(pdf_path) as reader:
    total_pages = reader.page_count
    print(f'Total pages: {total_pages}')

    students = []
    current_student = None

    for page in range(72, min(total_pages, 300)):
        text = reader.extract_page_range(page, page)
        match = re.search(r'(\d+\.\d+)등급.*?([가-힣]+대학교?)\s*([가-힣]+학과|[가-힣]+학부)', text)
        if match:
            grade = match.group(1)
            univ = match.group(2)
            dept = match.group(3)
            key = f'{grade}_{univ}_{dept}'

            if current_student != key:
                if current_student and students:
                    students[-1]['end'] = page - 1
                students.append({
                    'start': page,
                    'grade': grade,
                    'univ': univ,
                    'dept': dept,
                    'key': key
                })
                current_student = key

    if students:
        students[-1]['end'] = min(total_pages - 1, 299)

    print(f'\nFound {len(students)} students\n')
    for i, s in enumerate(students[:15], 1):
        pages = s['end'] - s['start'] + 1
        print(f"{i}. [{s['start']}-{s['end']}] ({pages}p) {s['grade']} {s['univ']} {s['dept']}")
