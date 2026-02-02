"""성적 섹션 파싱 모듈 - 개선된 버전"""

import re
from typing import Optional

from ..models.schema import (
    Evidence,
    ExamRow,
    NesinGrades,
    MockExamRow,
    SuneungScores,
    GradesSection,
)
from ..extractor.table_parser import TableParser, ParsedTable


class GradesParser:
    """성적 섹션 파서"""

    # 내신 과목 목록
    NESIN_SUBJECTS = ['국어', '영어', '수학', '사회', '과학', '기타', '주요과목', '전과목']

    # 학기 헤더 패턴
    TERM_HEADERS = ['1-1', '1-2', '2-1', '2-2', '3-1', '3-2']

    # 모의고사/수능 과목 헤더
    EXAM_HEADERS = ['한국사', '국어', '수학', '영어', '탐구1', '탐구2']

    def __init__(self, table_parser: TableParser | None = None):
        self.table_parser = table_parser

    def parse(self, text: str, tables: list[ParsedTable] | None = None) -> GradesSection:
        """성적 섹션 파싱"""
        section = GradesSection()

        # 내신 성적 파싱 (라인 기반)
        section.nesin = self._parse_nesin_from_lines(text)

        # 모의고사 성적 파싱
        section.mock_exams = self._parse_mock_exams_from_lines(text)

        # 수능 성적 파싱
        section.suneung = self._parse_suneung_from_lines(text)

        # 성적 유형 추론
        section.grade_type = self._infer_grade_type(section)

        return section

    def _parse_nesin_from_lines(self, text: str) -> NesinGrades:
        """라인 기반 내신 성적 파싱"""
        nesin = NesinGrades()
        lines = text.split('\n')

        # "내신성적" 또는 "2. 내신성적" 찾기
        start_idx = None
        for i, line in enumerate(lines):
            if '내신성적' in line or '내신 성적' in line:
                start_idx = i
                break

        if start_idx is None:
            return nesin

        # 구분 헤더 찾기 (1-1, 1-2, 2-1, 2-2, 3-1)
        terms = []
        header_idx = None
        for i in range(start_idx, min(start_idx + 20, len(lines))):
            line = lines[i].strip()
            if line in self.TERM_HEADERS:
                # 연속된 학기 헤더 수집
                if not terms or (terms and i == header_idx + len(terms)):
                    if not terms:
                        header_idx = i
                    terms.append(line)

        if not terms:
            # 한 줄에 모든 학기가 있는 경우
            for i in range(start_idx, min(start_idx + 10, len(lines))):
                line = lines[i].strip()
                if '1-1' in line and '1-2' in line:
                    terms = ['1-1', '1-2', '2-1', '2-2', '3-1']
                    header_idx = i
                    break

        if not terms:
            return nesin

        # 과목별 성적 파싱
        current_subject = None
        subject_values = []

        for i in range(header_idx + len(terms), min(header_idx + 100, len(lines))):
            line = lines[i].strip()

            if not line:
                continue

            # 섹션 종료 감지
            if any(keyword in line for keyword in ['정시성적', '수시카드', '학교특성', '[p']):
                break

            # 과목명 확인
            if line in self.NESIN_SUBJECTS or line == '(국+영+수+탐)':
                if current_subject and subject_values:
                    self._add_nesin_rows(nesin, current_subject, terms, subject_values)
                current_subject = line if line != '(국+영+수+탐)' else '주요과목'
                subject_values = []
                continue

            # 숫자 값 확인 (등급 또는 평균)
            if current_subject:
                # 숫자, 소수점, 또는 - 인 경우
                if re.match(r'^[\d.-]+$', line) or line == '-':
                    subject_values.append(line)

        # 마지막 과목 처리
        if current_subject and subject_values:
            self._add_nesin_rows(nesin, current_subject, terms, subject_values)

        # 평균 계산
        if nesin.rows:
            grades = [r.grade for r in nesin.rows if r.grade is not None]
            if grades:
                nesin.overall_average = round(sum(grades) / len(grades), 2)

        return nesin

    def _add_nesin_rows(self, nesin: NesinGrades, subject: str, terms: list[str], values: list[str]):
        """내신 행 추가"""
        for i, term in enumerate(terms):
            if i < len(values):
                value = values[i]
                if value == '-':
                    continue

                try:
                    num_value = float(value)
                    # 1-9 범위면 등급, 아니면 평균 점수
                    if 1 <= num_value <= 9:
                        grade = int(num_value) if num_value == int(num_value) else None
                        nesin.rows.append(ExamRow(
                            term=term,
                            subject=subject,
                            grade=grade,
                            raw_score=num_value if grade is None else None,
                        ))
                except ValueError:
                    pass

    def _parse_mock_exams_from_lines(self, text: str) -> list[MockExamRow]:
        """모의고사 성적 라인 기반 파싱"""
        rows = []
        lines = text.split('\n')

        # 모의고사 섹션 찾기
        exam_sections = []
        for i, line in enumerate(lines):
            line = line.strip()
            if '6월모의고사' in line or '6월 모의고사' in line:
                exam_sections.append(('6월', i))
            elif '9월모의고사' in line or '9월 모의고사' in line:
                exam_sections.append(('9월', i))

        for exam_name, start_idx in exam_sections:
            rows.extend(self._parse_single_mock_exam(lines, start_idx, exam_name))

        return rows

    def _parse_single_mock_exam(self, lines: list[str], start_idx: int, exam_name: str) -> list[MockExamRow]:
        """단일 모의고사 파싱"""
        rows = []

        # 과목 헤더 위치 찾기
        subjects = []
        select_subjects = []
        percentiles = []
        grades = []

        phase = 'header'  # header -> select -> percentile -> grade

        for i in range(start_idx + 1, min(start_idx + 30, len(lines))):
            line = lines[i].strip()

            if not line:
                continue

            # 다음 섹션 시작 감지
            if any(kw in line for kw in ['9월모의고사', '수능성적', '수시카드', '[p']):
                break

            # 과목 헤더
            if line in self.EXAM_HEADERS:
                subjects.append(line)
                continue

            # 선택과목 행
            if line == '선택과목':
                phase = 'select'
                continue

            # 백분위 행
            if line == '백분위':
                phase = 'percentile'
                continue

            # 등급 행
            if line == '등급':
                phase = 'grade'
                continue

            # 값 수집
            if phase == 'select':
                if line == '-' or re.match(r'^[가-힣]+', line):
                    select_subjects.append(line)
            elif phase == 'percentile':
                if line == '-' or re.match(r'^\d+$', line):
                    percentiles.append(line)
            elif phase == 'grade':
                if re.match(r'^[1-9]$', line):
                    grades.append(line)

        # 행 생성
        for i, subj in enumerate(subjects):
            if i < len(grades):
                try:
                    grade = int(grades[i])
                    percentile = None
                    if i < len(percentiles) and percentiles[i] != '-':
                        percentile = float(percentiles[i])

                    select_subj = None
                    if i < len(select_subjects) and select_subjects[i] != '-':
                        select_subj = select_subjects[i]

                    rows.append(MockExamRow(
                        date=exam_name,
                        subject=subj,
                        grade=grade,
                        percentile=percentile,
                        evidence=Evidence(raw_text=f"{exam_name} {subj}: {grade}등급")
                    ))
                except (ValueError, IndexError):
                    pass

        return rows

    def _parse_suneung_from_lines(self, text: str) -> SuneungScores | None:
        """수능 성적 라인 기반 파싱"""
        lines = text.split('\n')

        # 수능성적 섹션 찾기
        start_idx = None
        for i, line in enumerate(lines):
            if '수능성적' in line or '수능 성적' in line:
                start_idx = i
                break

        if start_idx is None:
            return None

        suneung = SuneungScores()

        # 과목별 데이터 수집
        subjects = []
        select_subjects = []
        percentiles = []
        grades = []

        phase = 'header'

        for i in range(start_idx + 1, min(start_idx + 30, len(lines))):
            line = lines[i].strip()

            if not line:
                continue

            # 다음 섹션 시작
            if any(kw in line for kw in ['수시카드', '학교특성', '[p']):
                break

            # 과목 헤더
            if line in self.EXAM_HEADERS:
                subjects.append(line)
                continue

            if line == '선택과목':
                phase = 'select'
                continue
            if line == '백분위':
                phase = 'percentile'
                continue
            if line == '등급':
                phase = 'grade'
                continue

            if phase == 'select':
                if line == '-' or re.match(r'^[가-힣∙]+', line):
                    select_subjects.append(line)
            elif phase == 'percentile':
                if line == '-' or re.match(r'^\d+$', line):
                    percentiles.append(line)
            elif phase == 'grade':
                if re.match(r'^[1-9]$', line):
                    grades.append(line)

        # 매핑
        subject_map = {subj: i for i, subj in enumerate(subjects)}

        if '한국사' in subject_map and subject_map['한국사'] < len(grades):
            try:
                suneung.history = int(grades[subject_map['한국사']])
            except ValueError:
                pass

        if '국어' in subject_map and subject_map['국어'] < len(grades):
            try:
                suneung.korean = int(grades[subject_map['국어']])
            except ValueError:
                pass

        if '수학' in subject_map and subject_map['수학'] < len(grades):
            try:
                suneung.math = int(grades[subject_map['수학']])
            except ValueError:
                pass

        if '영어' in subject_map and subject_map['영어'] < len(grades):
            try:
                suneung.english = int(grades[subject_map['영어']])
            except ValueError:
                pass

        if '탐구1' in subject_map:
            idx = subject_map['탐구1']
            if idx < len(grades):
                try:
                    suneung.tamgu1_grade = int(grades[idx])
                except ValueError:
                    pass
            if idx < len(select_subjects) and select_subjects[idx] != '-':
                suneung.tamgu1 = select_subjects[idx]

        if '탐구2' in subject_map:
            idx = subject_map['탐구2']
            if idx < len(grades):
                try:
                    suneung.tamgu2_grade = int(grades[idx])
                except ValueError:
                    pass
            if idx < len(select_subjects) and select_subjects[idx] != '-':
                suneung.tamgu2 = select_subjects[idx]

        # 유효성 검사
        if any([suneung.korean, suneung.math, suneung.english, suneung.history]):
            return suneung

        return None

    def _infer_grade_type(self, section: GradesSection) -> str | None:
        """성적 유형 추론"""
        has_nesin = len(section.nesin.rows) > 0
        has_suneung = section.suneung is not None

        if has_nesin and has_suneung:
            return "균형형"
        elif has_nesin:
            return "내신형"
        elif has_suneung:
            return "수능형"

        return None
