"""전체 학생 페이지 범위 찾기"""
from src.extractor.pdf_reader import PDFReader
from pathlib import Path
import re

pdf_path = Path(r'C:\Users\iamhj\Downloads\유니브클래스_2025_인문사회상경_생기부대백과 (1).pdf')

with PDFReader(pdf_path) as reader:
    students = []
    current = None

    for page in range(1, 285):
        text = reader.extract_page_range(page, page)
        match = re.search(r'(\d+\.\d+)등급.*?([가-힣]+대학교?)\s*([가-힣]+학과|[가-힣]+학부)', text)
        if match:
            key = f'{match.group(1)}_{match.group(2)}_{match.group(3)}'
            if current != key:
                if current and students:
                    students[-1]['end'] = page - 1
                students.append({
                    'start': page,
                    'grade': match.group(1),
                    'univ': match.group(2),
                    'dept': match.group(3),
                    'key': key
                })
                current = key

    if students:
        students[-1]['end'] = 284

    print(f'Found {len(students)} students total:\n')
    for i, s in enumerate(students, 1):
        pages = s['end'] - s['start'] + 1
        print(f"{i}. [{s['start']}-{s['end']}] ({pages}p) {s['grade']} {s['univ']} {s['dept']}")
