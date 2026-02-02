"""테이블 파싱 및 복원 모듈"""

import re
from dataclasses import dataclass, field
from pathlib import Path

import pdfplumber


@dataclass
class TableCell:
    """테이블 셀"""
    text: str
    row: int
    col: int


@dataclass
class ParsedTable:
    """파싱된 테이블"""
    rows: list[list[str]] = field(default_factory=list)
    page_num: int = 0
    raw_data: list = field(default_factory=list)


class TableParser:
    """PDF 테이블 파싱 및 복원"""

    # 학기 패턴
    TERM_PATTERN = re.compile(r'([1-3])[-학년]?\s*([1-2])[-학기]?')

    # 등급 패턴
    GRADE_PATTERN = re.compile(r'([1-9])\s*등급')

    # 점수 패턴
    SCORE_PATTERN = re.compile(r'(\d{2,3})(?:\.\d+)?\s*점?')

    # 백분위 패턴
    PERCENTILE_PATTERN = re.compile(r'(\d{1,3})(?:\.\d+)?\s*%')

    # 과목명 사전
    SUBJECTS = {
        '국어', '수학', '영어', '한국사', '사회', '과학', '물리', '화학', '생명과학', '지구과학',
        '물리학', '화학I', '화학II', '생명과학I', '생명과학II', '지구과학I', '지구과학II',
        '물리학I', '물리학II', '통합과학', '과학탐구실험',
        '윤리와사상', '생활과윤리', '한국지리', '세계지리', '동아시아사', '세계사',
        '정치와법', '경제', '사회문화', '통합사회',
        '미적분', '확률과통계', '기하', '수학I', '수학II',
        '음악', '미술', '체육', '기술가정', '정보', '제2외국어', '한문',
        '일본어', '중국어', '독일어', '프랑스어', '스페인어', '아랍어', '베트남어', '러시아어'
    }

    # 과목 유사어 매핑 (정규화용)
    SUBJECT_ALIASES = {
        '물리': '물리학',
        '생명': '생명과학',
        '지구': '지구과학',
        '생윤': '생활과윤리',
        '윤사': '윤리와사상',
        '한지': '한국지리',
        '세지': '세계지리',
        '동사': '동아시아사',
        '세사': '세계사',
        '정법': '정치와법',
        '사문': '사회문화',
        '확통': '확률과통계',
        '기가': '기술가정',
    }

    def __init__(self, pdf_path: str | Path):
        self.pdf_path = Path(pdf_path)
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF 파일을 찾을 수 없습니다: {pdf_path}")

    def extract_tables(self, page_num: int | None = None) -> list[ParsedTable]:
        """테이블 추출"""
        tables = []

        with pdfplumber.open(str(self.pdf_path)) as pdf:
            if page_num is not None:
                pages = [pdf.pages[page_num - 1]] if page_num <= len(pdf.pages) else []
                page_nums = [page_num]
            else:
                pages = pdf.pages
                page_nums = list(range(1, len(pdf.pages) + 1))

            for page, pnum in zip(pages, page_nums):
                page_tables = page.extract_tables()
                for table_data in page_tables:
                    if table_data:
                        parsed = ParsedTable(
                            rows=self._clean_table_rows(table_data),
                            page_num=pnum,
                            raw_data=table_data
                        )
                        tables.append(parsed)

        return tables

    def _clean_table_rows(self, table_data: list) -> list[list[str]]:
        """테이블 행 정리"""
        cleaned = []
        for row in table_data:
            if row:
                cleaned_row = []
                for cell in row:
                    if cell is None:
                        cleaned_row.append('')
                    else:
                        # 줄바꿈과 공백 정리
                        text = str(cell).replace('\n', ' ').strip()
                        text = re.sub(r'\s+', ' ', text)
                        cleaned_row.append(text)
                # 빈 행이 아닌 경우만 추가
                if any(cell for cell in cleaned_row):
                    cleaned.append(cleaned_row)
        return cleaned

    def parse_term(self, text: str) -> tuple[int, int] | None:
        """학기 정보 추출 (학년, 학기)"""
        match = self.TERM_PATTERN.search(text)
        if match:
            return int(match.group(1)), int(match.group(2))
        return None

    def parse_grade(self, text: str) -> int | None:
        """등급 추출"""
        match = self.GRADE_PATTERN.search(text)
        if match:
            return int(match.group(1))
        # 단순 숫자인 경우 (1-9 범위)
        simple_match = re.match(r'^([1-9])$', text.strip())
        if simple_match:
            return int(simple_match.group(1))
        return None

    def parse_score(self, text: str) -> float | None:
        """점수 추출"""
        match = self.SCORE_PATTERN.search(text)
        if match:
            return float(match.group(1))
        return None

    def parse_percentile(self, text: str) -> float | None:
        """백분위 추출"""
        match = self.PERCENTILE_PATTERN.search(text)
        if match:
            return float(match.group(1))
        return None

    def find_subject(self, text: str) -> str | None:
        """과목명 찾기"""
        text = text.strip()

        # 정확히 일치
        if text in self.SUBJECTS:
            return text

        # 별칭 확인
        if text in self.SUBJECT_ALIASES:
            return self.SUBJECT_ALIASES[text]

        # 부분 일치
        for subject in self.SUBJECTS:
            if subject in text or text in subject:
                return subject

        return None

    def normalize_subject(self, subject: str) -> str:
        """과목명 정규화 (유사 과목 그룹화)"""
        # 기본 정규화
        subject = subject.strip()

        # 별칭 변환
        if subject in self.SUBJECT_ALIASES:
            subject = self.SUBJECT_ALIASES[subject]

        # 레벨 제거 (화학I, 화학II -> 화학)
        base_subject = re.sub(r'[IⅠⅡ12]+$', '', subject).strip()

        return base_subject if base_subject else subject

    def restore_broken_table(self, lines: list[str]) -> list[list[str]]:
        """깨진 테이블 복원 (휴리스틱 기반)"""
        rows = []
        current_row = []

        for line in lines:
            line = line.strip()
            if not line:
                if current_row:
                    rows.append(current_row)
                    current_row = []
                continue

            # 학기 정보로 시작하면 새 행
            if self.parse_term(line):
                if current_row:
                    rows.append(current_row)
                current_row = [line]
            # 과목명이면 같은 행에 추가
            elif self.find_subject(line):
                current_row.append(line)
            # 등급이나 점수면 같은 행에 추가
            elif self.parse_grade(line) or self.parse_score(line):
                current_row.append(line)
            else:
                current_row.append(line)

        if current_row:
            rows.append(current_row)

        return rows
