"""수시카드 섹션 파싱 모듈 - 개선된 버전"""

import re

from ..models.schema import Evidence, SusiApplication, SusiCardSection
from ..extractor.table_parser import ParsedTable


class SusiParser:
    """수시카드 파서"""

    # 대학명 패턴 (정확한 매칭)
    UNIV_PATTERN = re.compile(r'^([가-힣]+대학교?(?:\([가-힣]+\))?)$')

    # 전형 유형 키워드
    ADMISSION_KEYWORDS = [
        '학생부교과', '학생부종합', '교과전형', '종합전형',
        '학종', '논술', '실기', '특기자',
        '지역균형', '기회균형', '농어촌', '저소득층',
        '학교추천', '학교장추천', '추천형', '일반전형',
        '계열적합', '학과모집', '교과', '종합',
    ]

    # 결과 키워드
    RESULT_PATTERNS = [
        (re.compile(r'최초합격'), '최초합격'),
        (re.compile(r'추가합격.*?(\d+차)?'), '추가합격'),
        (re.compile(r'불합격.*?(\d+차)?'), '불합격'),
        (re.compile(r'예비'), '예비'),
    ]

    # 무시할 패턴
    IGNORE_PATTERNS = [
        r'^\d+$',  # 숫자만
        r'^2025\s*생기부',
        r'^일반고내신',
        r'등급.*경영학과',
        r'합격선배',
        r'^\[p\d+\]',
    ]

    def parse(self, text: str, tables: list[ParsedTable] | None = None) -> SusiCardSection:
        """수시카드 섹션 파싱"""
        section = SusiCardSection()

        # 수시카드 섹션 추출
        susi_text = self._extract_susi_section(text)
        if not susi_text:
            return section

        # 라인 기반 파싱
        section.applications = self._parse_from_lines(susi_text)

        # 최종 선택 탐지
        section.final_choice = self._detect_final_choice(text, section.applications)

        return section

    def _extract_susi_section(self, text: str) -> str | None:
        """수시카드 섹션만 추출"""
        lines = text.split('\n')

        start_idx = None
        end_idx = None

        for i, line in enumerate(lines):
            line_stripped = line.strip()
            if '수시카드' in line_stripped or '수시 카드' in line_stripped:
                start_idx = i + 1
            elif start_idx and any(kw in line_stripped for kw in ['학교특성', '학교 특성', '5.', '[p75]', '[p76]']):
                end_idx = i
                break

        if start_idx:
            end_idx = end_idx or len(lines)
            return '\n'.join(lines[start_idx:end_idx])

        return None

    def _parse_from_lines(self, text: str) -> list[SusiApplication]:
        """라인 기반 파싱 (4줄 단위: 대학, 학과, 전형, 결과)"""
        applications = []
        lines = [l.strip() for l in text.split('\n') if l.strip()]

        # 무시할 라인 필터링
        filtered_lines = []
        for line in lines:
            should_ignore = False
            for pattern in self.IGNORE_PATTERNS:
                if re.search(pattern, line):
                    should_ignore = True
                    break
            if not should_ignore:
                filtered_lines.append(line)

        # 4줄 단위로 파싱
        i = 0
        while i < len(filtered_lines):
            # 대학명 찾기
            univ_match = self.UNIV_PATTERN.match(filtered_lines[i])
            if univ_match:
                university = univ_match.group(1)

                # 다음 3줄 확인
                if i + 3 < len(filtered_lines):
                    department = filtered_lines[i + 1]
                    admission_type = filtered_lines[i + 2]
                    result_line = filtered_lines[i + 3]

                    # 학과명 검증 (대학명이 아니어야 함)
                    if self.UNIV_PATTERN.match(department):
                        i += 1
                        continue

                    # 전형 검증
                    if not any(kw in admission_type for kw in self.ADMISSION_KEYWORDS):
                        # 전형이 아니면 스킵
                        i += 1
                        continue

                    # 결과 파싱
                    result = self._parse_result(result_line)

                    applications.append(SusiApplication(
                        university=university,
                        department=department,
                        admission_type=admission_type,
                        result=result,
                        evidence=Evidence(raw_text=f"{university} {department}")
                    ))

                    i += 4
                    continue

            i += 1

        return applications

    def _parse_result(self, text: str) -> str:
        """결과 파싱"""
        for pattern, result_type in self.RESULT_PATTERNS:
            if pattern.search(text):
                return text  # 원본 텍스트 유지 (추가 정보 포함)

        # 간단한 키워드 매칭
        if '합격' in text:
            return text
        if '불합격' in text or '탈락' in text:
            return text
        if '예비' in text:
            return text

        return text

    def _detect_final_choice(self, text: str, applications: list[SusiApplication]) -> str | None:
        """최종 선택 대학 탐지"""
        # "최종등록대학" 패턴 찾기
        lines = text.split('\n')
        for i, line in enumerate(lines):
            if '최종등록대학' in line or '최종 등록 대학' in line:
                # 다음 줄이 대학명
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if self.UNIV_PATTERN.match(next_line) or '대학' in next_line:
                        return next_line

        # 합격한 대학 중 마지막 선택 (추가합격 우선)
        accepted = [app for app in applications if '합격' in app.result and '불합격' not in app.result]
        if accepted:
            # 추가합격이 있으면 그것이 최종
            for app in reversed(accepted):
                if '추가합격' in app.result:
                    return app.university
            return accepted[-1].university

        return None
