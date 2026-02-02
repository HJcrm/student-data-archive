"""생기부 로드맵 섹션 파싱 모듈 - 개선된 버전"""

import re
from uuid import uuid4

from ..models.schema import Evidence, ResearchItem, RoadmapSection


class RoadmapParser:
    """생기부 로드맵 파서"""

    # 학기 패턴
    TERM_PATTERN = re.compile(r'^([1-3])-([1-2])$')

    # 과목 목록
    SUBJECTS = [
        '국어', '문학', '독서', '화법과작문',
        '수학', '수학I', '수학II', '미적분', '확률과통계', '기하', '수학과제탐구',
        '영어', '영어I', '영어II', '영어독해와작문', '심화영어',
        '물리학', '물리학I', '물리학II', '화학', '화학I', '화학II',
        '생명과학', '생명과학I', '생명과학II', '지구과학', '지구과학I', '지구과학II',
        '통합과학', '과학탐구실험',
        '한국사', '세계사', '동아시아사', '세계지리', '한국지리',
        '경제', '정치와법', '사회문화', '사회문제탐구', '통합사회',
        '생활과윤리', '윤리와사상',
        '정보', '기술가정', '정보처리와관리',
        '음악', '미술', '체육',
        '진로', '자율', '동아리', '논술',
    ]

    # 무시할 라인 패턴
    IGNORE_PATTERNS = [
        r'^\d+$',
        r'^2025\s*생기부',
        r'^일반고내신',
        r'합격선배',
        r'^\[p\d+\]',
        r'^학기$',
        r'^과목$',
        r'^탐구주제제목$',
    ]

    def parse(self, text: str) -> RoadmapSection:
        """로드맵 섹션 파싱"""
        section = RoadmapSection()

        # 학년별 전략 추출
        section.yearly_strategies = self._extract_yearly_strategies(text)

        # 핵심 탐구활동 추출
        section.top_researches = self._extract_top_researches(text)

        # 전체 테마 추출
        section.overall_theme = self._extract_overall_theme(text)

        return section

    def _extract_yearly_strategies(self, text: str) -> dict[str, str]:
        """학년별 전략/활동 추출"""
        strategies = {}
        lines = text.split('\n')

        for i, line in enumerate(lines):
            line = line.strip()

            # "1학년", "2학년", "3학년" 패턴
            if line in ['1학년', '2학년', '3학년']:
                # 다음 줄들이 해당 학년의 활동
                activities = []
                for j in range(i + 1, min(i + 5, len(lines))):
                    next_line = lines[j].strip()
                    if next_line in ['1학년', '2학년', '3학년', '']:
                        break
                    if any(re.search(p, next_line) for p in self.IGNORE_PATTERNS):
                        continue
                    if len(next_line) > 10:
                        activities.append(next_line)

                if activities:
                    strategies[line] = ' / '.join(activities)

        return strategies

    def _extract_top_researches(self, text: str) -> list[ResearchItem]:
        """핵심 탐구활동 추출 (3줄 단위: 학기, 과목, 주제)"""
        researches = []
        lines = text.split('\n')

        # "핵심탐구활동" 또는 "Top 10" 섹션 찾기
        start_idx = None
        for i, line in enumerate(lines):
            if '핵심탐구활동' in line or 'Top 10' in line or '핵심 탐구' in line:
                start_idx = i + 1
                break

        if start_idx is None:
            # 2. 핵심탐구활동 형식도 확인
            for i, line in enumerate(lines):
                if '2.' in line and '핵심' in line and '탐구' in line:
                    start_idx = i + 1
                    break

        if start_idx is None:
            return researches

        # 헤더 건너뛰기 (학기, 과목, 탐구주제제목)
        for i in range(start_idx, min(start_idx + 5, len(lines))):
            line = lines[i].strip()
            if line == '탐구주제제목':
                start_idx = i + 1
                break

        # 3줄 단위로 파싱 (학기, 과목, 주제)
        i = start_idx
        while i < len(lines) and len(researches) < 15:
            line = lines[i].strip()

            # 섹션 종료
            if any(kw in line for kw in ['3.', '기타탐구', '1학년교과', '2학년교과', '3학년교과', '[p77]']):
                break

            # 학기 패턴 확인
            term_match = self.TERM_PATTERN.match(line)
            if term_match:
                term = line

                # 다음 줄: 과목
                if i + 1 < len(lines):
                    subject_line = lines[i + 1].strip()
                    subject = self._find_subject(subject_line)

                    # 다음 줄: 주제
                    if i + 2 < len(lines):
                        title = lines[i + 2].strip()

                        # 주제가 유효한지 확인
                        if len(title) > 5 and not self.TERM_PATTERN.match(title):
                            researches.append(ResearchItem(
                                id=f"research_{uuid4().hex[:8]}",
                                term=term,
                                subject=subject or subject_line,
                                title=title,
                                evidence=Evidence(raw_text=f"{term} {subject}: {title[:50]}")
                            ))
                            i += 3
                            continue

            i += 1

        return researches

    def _find_subject(self, text: str) -> str | None:
        """과목명 찾기"""
        text = text.strip()
        if text in self.SUBJECTS:
            return text

        # 부분 매칭
        for subject in self.SUBJECTS:
            if subject in text:
                return subject

        return None

    def _extract_overall_theme(self, text: str) -> str | None:
        """전체 테마 추출"""
        # 로드맵 관련 설명 찾기
        lines = text.split('\n')

        for i, line in enumerate(lines):
            if '로드맵' in line and i + 1 < len(lines):
                # 다음 줄들에서 테마 추출
                for j in range(i + 1, min(i + 5, len(lines))):
                    next_line = lines[j].strip()
                    if len(next_line) > 20 and '분야' in next_line:
                        return next_line[:100]

        return None
