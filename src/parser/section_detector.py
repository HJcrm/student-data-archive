"""섹션 경계 탐지 모듈"""

import re
from dataclasses import dataclass
from enum import Enum


class SectionType(Enum):
    """섹션 유형"""
    GRADES = "grades"
    SUSI_CARD = "susi_card"
    SCHOOL = "school"
    ROADMAP = "roadmap"
    SAENGGIBU = "saenggibu"
    UNKNOWN = "unknown"


@dataclass
class SectionInfo:
    """섹션 정보"""
    section_type: SectionType
    start_page: int
    end_page: int | None
    start_pos: int  # 텍스트 내 시작 위치
    end_pos: int | None  # 텍스트 내 끝 위치
    title: str
    confidence: float  # 탐지 신뢰도 (0-1)


class SectionDetector:
    """섹션 경계 탐지기"""

    # 섹션별 키워드 패턴
    SECTION_PATTERNS = {
        SectionType.GRADES: [
            r'성적\s*유형',
            r'내신\s*(성적|등급)',
            r'모의고사\s*(성적|등급)',
            r'수능\s*(성적|점수)',
            r'정시\s*성적',
            r'학업\s*성적',
            r'교과\s*성적',
            r'석차\s*등급',
        ],
        SectionType.SUSI_CARD: [
            r'수시\s*카드',
            r'지원\s*결과',
            r'지원\s*현황',
            r'합격\s*현황',
            r'대학\s*지원',
            r'전형\s*결과',
        ],
        SectionType.SCHOOL: [
            r'학교\s*특성',
            r'학교\s*분위기',
            r'학교\s*정보',
            r'재학\s*학교',
            r'출신\s*학교',
            r'학교\s*유형',
        ],
        SectionType.ROADMAP: [
            r'로드맵',
            r'핵심\s*탐구',
            r'탐구\s*활동',
            r'학년별\s*전략',
            r'Top\s*\d+',
            r'주요\s*활동',
        ],
        SectionType.SAENGGIBU: [
            r'세특',
            r'세부\s*능력',
            r'특기\s*사항',
            r'생기부',
            r'학생부',
            r'합격\s*포인트',
            r'생활\s*기록부',
        ],
    }

    # 페이지 마커 패턴
    PAGE_MARKER_PATTERN = re.compile(r'\[p(\d+)\]')

    def __init__(self, text: str):
        self.text = text
        self.sections: list[SectionInfo] = []
        self._page_positions: dict[int, int] = {}  # page_num -> text position
        self._extract_page_positions()

    def _extract_page_positions(self):
        """페이지 마커 위치 추출"""
        for match in self.PAGE_MARKER_PATTERN.finditer(self.text):
            page_num = int(match.group(1))
            self._page_positions[page_num] = match.start()

    def _get_page_at_position(self, pos: int) -> int:
        """텍스트 위치에서 페이지 번호 찾기"""
        page = 1
        for page_num, page_pos in sorted(self._page_positions.items()):
            if page_pos <= pos:
                page = page_num
            else:
                break
        return page

    def detect_sections(self) -> list[SectionInfo]:
        """모든 섹션 탐지"""
        candidates = []

        for section_type, patterns in self.SECTION_PATTERNS.items():
            for pattern in patterns:
                for match in re.finditer(pattern, self.text, re.IGNORECASE):
                    page = self._get_page_at_position(match.start())
                    confidence = self._calculate_confidence(match, pattern)

                    candidates.append(SectionInfo(
                        section_type=section_type,
                        start_page=page,
                        end_page=None,
                        start_pos=match.start(),
                        end_pos=None,
                        title=match.group(0),
                        confidence=confidence
                    ))

        # 중복 제거 및 정렬
        self.sections = self._merge_candidates(candidates)

        # 끝 위치 계산
        self._calculate_end_positions()

        return self.sections

    def _calculate_confidence(self, match: re.Match, pattern: str) -> float:
        """매칭 신뢰도 계산"""
        confidence = 0.5

        # 줄 시작에 있으면 신뢰도 증가
        line_start = self.text.rfind('\n', 0, match.start())
        if line_start == -1:
            line_start = 0
        text_before = self.text[line_start:match.start()].strip()
        if not text_before or text_before.isdigit():
            confidence += 0.2

        # 긴 패턴 매치면 신뢰도 증가
        if len(match.group(0)) > 5:
            confidence += 0.1

        # 특정 키워드가 정확히 매치되면 신뢰도 증가
        if match.group(0) in ['수시카드', '세특', '로드맵', '학교 특성']:
            confidence += 0.2

        return min(confidence, 1.0)

    def _merge_candidates(self, candidates: list[SectionInfo]) -> list[SectionInfo]:
        """중복 후보 병합"""
        if not candidates:
            return []

        # 위치순 정렬
        candidates.sort(key=lambda x: x.start_pos)

        merged = []
        for candidate in candidates:
            # 같은 섹션 타입이 가까운 위치에 있으면 무시
            is_duplicate = False
            for existing in merged:
                if (existing.section_type == candidate.section_type and
                    abs(existing.start_pos - candidate.start_pos) < 200):
                    # 신뢰도 높은 것 유지
                    if candidate.confidence > existing.confidence:
                        merged.remove(existing)
                    else:
                        is_duplicate = True
                    break

            if not is_duplicate:
                merged.append(candidate)

        return merged

    def _calculate_end_positions(self):
        """각 섹션의 끝 위치 계산"""
        for i, section in enumerate(self.sections):
            if i < len(self.sections) - 1:
                next_section = self.sections[i + 1]
                section.end_pos = next_section.start_pos
                section.end_page = self._get_page_at_position(next_section.start_pos - 1)
            else:
                section.end_pos = len(self.text)
                section.end_page = max(self._page_positions.keys()) if self._page_positions else 1

    def get_section_text(self, section_type: SectionType) -> str | None:
        """특정 섹션의 텍스트 반환"""
        for section in self.sections:
            if section.section_type == section_type:
                if section.end_pos:
                    return self.text[section.start_pos:section.end_pos]
                return self.text[section.start_pos:]
        return None

    def get_section_info(self, section_type: SectionType) -> SectionInfo | None:
        """특정 섹션 정보 반환"""
        for section in self.sections:
            if section.section_type == section_type:
                return section
        return None

    def get_all_section_texts(self) -> dict[SectionType, str]:
        """모든 섹션 텍스트 반환"""
        result = {}
        for section in self.sections:
            if section.section_type not in result:
                text = self.get_section_text(section.section_type)
                if text:
                    result[section.section_type] = text
        return result
