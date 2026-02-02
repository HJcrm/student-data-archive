"""학교 특성 섹션 파싱 모듈 - 개선된 버전"""

import re

from ..models.schema import Evidence, SchoolSection


class SchoolParser:
    """학교 특성 파서"""

    # 학교 유형
    SCHOOL_TYPES = {
        '일반고': ['일반고', '일반계고'],
        '특목고': ['특목고', '과학고', '외고', '외국어고', '국제고', '예고', '예술고'],
        '자사고': ['자사고', '자율형사립고'],
        '자공고': ['자공고', '자율형공립고'],
        '영재학교': ['영재학교', '영재고'],
    }

    def parse(self, text: str) -> SchoolSection:
        """학교 특성 섹션 파싱"""
        section = SchoolSection()

        # 학교특성 섹션 추출
        school_text = self._extract_school_section(text)
        if not school_text:
            school_text = text

        # 필드별 파싱
        section.region = self._extract_field(school_text, '소재지역')
        section.school_type = self._extract_school_type(school_text)
        section.school_name = self._extract_field(school_text, '학교명')
        section.atmosphere = self._extract_atmosphere(school_text)
        section.competition_level = self._extract_competition(school_text)
        section.special_programs = self._extract_programs(school_text)

        return section

    def _extract_school_section(self, text: str) -> str | None:
        """학교특성 섹션만 추출"""
        lines = text.split('\n')

        start_idx = None
        end_idx = None

        for i, line in enumerate(lines):
            line_stripped = line.strip()
            if '학교특성' in line_stripped or '학교 특성' in line_stripped:
                start_idx = i
            elif start_idx and any(kw in line_stripped for kw in ['로드맵', '핵심탐구', '[p76]', '1. 합격']):
                end_idx = i
                break

        if start_idx:
            end_idx = end_idx or min(start_idx + 100, len(lines))
            return '\n'.join(lines[start_idx:end_idx])

        return None

    def _extract_field(self, text: str, field_name: str) -> str | None:
        """필드 값 추출 (필드명 다음 줄)"""
        lines = text.split('\n')

        for i, line in enumerate(lines):
            if field_name in line.strip():
                # 같은 줄에 값이 있는 경우
                parts = line.split(field_name)
                if len(parts) > 1 and parts[1].strip():
                    return parts[1].strip()

                # 다음 줄에 값이 있는 경우
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if next_line and len(next_line) < 50:
                        return next_line

        return None

    def _extract_school_type(self, text: str) -> str | None:
        """학교 유형 추출"""
        # 직접 필드 추출
        field_value = self._extract_field(text, '학교유형')
        if field_value:
            for school_type, keywords in self.SCHOOL_TYPES.items():
                if any(kw in field_value for kw in keywords):
                    return school_type
            return field_value

        # 텍스트에서 찾기
        for school_type, keywords in self.SCHOOL_TYPES.items():
            for keyword in keywords:
                if keyword in text:
                    return school_type

        return None

    def _extract_atmosphere(self, text: str) -> str | None:
        """학교 분위기 추출"""
        lines = text.split('\n')

        # 분위기정도 찾기
        for i, line in enumerate(lines):
            if '분위기정도' in line or '분위기 정도' in line:
                # 점수 추출
                score_match = re.search(r'(\d+\.?\d*)\s*/\s*(\d+\.?\d*)', line)
                if score_match:
                    return f"{score_match.group(1)}/{score_match.group(2)}"

        # 분위기 설명 추출
        atmosphere_keywords = []
        if '경쟁' in text and '치열' in text:
            atmosphere_keywords.append('경쟁적')
        if '자율' in text or '자유' in text:
            atmosphere_keywords.append('자율적')
        if '협력' in text or '협동' in text:
            atmosphere_keywords.append('협력적')

        if atmosphere_keywords:
            return ', '.join(atmosphere_keywords)

        return None

    def _extract_competition(self, text: str) -> str | None:
        """경쟁 수준 추출"""
        # 상위권 경쟁 관련 문구 찾기
        if '상위권경쟁이치열' in text or '상위권 경쟁이 치열' in text:
            return '상위권 경쟁 치열'
        if '경쟁이심' in text:
            return '높음'

        return None

    def _extract_programs(self, text: str) -> list[str]:
        """특별 프로그램 추출"""
        programs = []

        # 교내프로그램 섹션에서 추출
        lines = text.split('\n')
        in_program_section = False

        for line in lines:
            line = line.strip()

            if '교내프로그램' in line:
                in_program_section = True
                continue

            if in_program_section:
                # 구체적인 프로그램명 찾기
                program_patterns = [
                    r'(독서마라톤)',
                    r'(민주주의.*?발표회)',
                    r'(진로.*?박람회)',
                    r'(멘토링)',
                    r'(".*?")',
                    r'(탐구보고서)',
                ]

                for pattern in program_patterns:
                    matches = re.findall(pattern, line)
                    for match in matches:
                        if match not in programs:
                            programs.append(match)

                # 새 섹션 시작시 종료
                if any(kw in line for kw in ['개인특성', '선택과목', '1학년', '2학년', '3학년']):
                    break

        return programs[:5]
