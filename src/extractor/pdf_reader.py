"""PDF 텍스트 추출 모듈"""

import re
from pathlib import Path
from dataclasses import dataclass

import fitz  # PyMuPDF


@dataclass
class PageContent:
    """페이지 내용"""
    page_num: int
    text: str
    raw_text: str


class PDFReader:
    """PDF에서 텍스트를 추출하는 클래스"""

    def __init__(self, pdf_path: str | Path):
        self.pdf_path = Path(pdf_path)
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF 파일을 찾을 수 없습니다: {pdf_path}")
        self.doc = fitz.open(str(self.pdf_path))

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        """문서 닫기"""
        if self.doc:
            self.doc.close()

    @property
    def page_count(self) -> int:
        """전체 페이지 수"""
        return len(self.doc)

    def extract_page(self, page_num: int) -> PageContent:
        """특정 페이지 텍스트 추출 (0-indexed)"""
        if page_num < 0 or page_num >= self.page_count:
            raise IndexError(f"페이지 번호가 범위를 벗어났습니다: {page_num}")

        page = self.doc[page_num]
        raw_text = page.get_text()
        normalized_text = self._normalize_text(raw_text)

        return PageContent(
            page_num=page_num + 1,  # 1-indexed로 반환
            text=normalized_text,
            raw_text=raw_text
        )

    def extract_all_pages(self) -> list[PageContent]:
        """모든 페이지 텍스트 추출"""
        return [self.extract_page(i) for i in range(self.page_count)]

    def extract_with_markers(self) -> str:
        """페이지 마커가 포함된 전체 텍스트 반환"""
        result = []
        for i in range(self.page_count):
            page_content = self.extract_page(i)
            result.append(f"[p{page_content.page_num}]")
            result.append(page_content.text)
        return "\n".join(result)

    def extract_page_range(self, start: int, end: int) -> str:
        """페이지 범위 텍스트 추출 (1-indexed, inclusive)"""
        result = []
        for i in range(start - 1, min(end, self.page_count)):
            page_content = self.extract_page(i)
            result.append(f"[p{page_content.page_num}]")
            result.append(page_content.text)
        return "\n".join(result)

    def _normalize_text(self, text: str) -> str:
        """텍스트 정규화"""
        # 연속된 공백을 하나로
        text = re.sub(r'[ \t]+', ' ', text)
        # 연속된 줄바꿈을 최대 2개로
        text = re.sub(r'\n{3,}', '\n\n', text)
        # 줄 앞뒤 공백 제거
        lines = [line.strip() for line in text.split('\n')]
        text = '\n'.join(lines)
        # 앞뒤 공백 제거
        return text.strip()

    def get_filename(self) -> str:
        """파일명 반환 (확장자 제외)"""
        return self.pdf_path.stem
