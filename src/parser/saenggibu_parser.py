"""세특/생기부 섹션 파싱 모듈 - 개선된 버전"""

import re
from uuid import uuid4

from ..models.schema import Evidence, SaeteukExample, SaenggibuSection


class SaenggibuParser:
    """세특/생기부 파서"""

    # 과목 목록
    SUBJECTS = [
        '국어', '문학', '독서', '화법과작문', '언어와매체',
        '수학', '수학I', '수학II', '미적분', '확률과통계', '기하', '수학과제탐구',
        '영어', '영어I', '영어II', '영어독해와작문', '심화영어',
        '물리학', '물리학I', '물리학II', '화학', '화학I', '화학II',
        '생명과학', '생명과학I', '생명과학II', '지구과학', '지구과학I', '지구과학II',
        '통합과학', '과학탐구실험',
        '한국사', '세계사', '동아시아사', '세계지리', '한국지리',
        '경제', '정치와법', '사회문화', '사회문제탐구', '통합사회',
        '생활과윤리', '윤리와사상',
        '정보', '기술가정', '정보처리와관리',
        '음악', '미술', '체육', '논술',
        '진로', '자율', '동아리',
    ]

    # 무시할 패턴
    IGNORE_PATTERNS = [
        r'^\d+$',
        r'^2025\s*생기부',
        r'^일반고내신',
        r'합격선배',
        r'^\[p\d+\]',
    ]

    def parse(self, text: str) -> SaenggibuSection:
        """세특/생기부 섹션 파싱"""
        section = SaenggibuSection()

        # 세특 예시 추출
        section.saeteuk_examples = self._extract_saeteuk_examples(text)

        # 합격 포인트 추출
        section.acceptance_points = self._extract_acceptance_points(text)

        return section

    def _extract_saeteuk_examples(self, text: str) -> list[SaeteukExample]:
        """세특 예시 추출"""
        examples = []
        lines = text.split('\n')

        # "탐구활동생기부기재내용" 또는 "세부능력및특기사항" 섹션 찾기
        i = 0
        while i < len(lines):
            line = lines[i].strip()

            # 세특 섹션 시작 감지
            if '탐구활동생기부기재내용' in line or '생기부기재내용' in line:
                # 영역/과목 찾기
                subject = None
                content_lines = []

                # 다음 줄들 파싱
                j = i + 1
                while j < len(lines):
                    next_line = lines[j].strip()

                    # 다음 섹션 시작
                    if any(kw in next_line for kw in ['보여주고싶은역량', '합격선배의생기부분석', '합격포인트']):
                        break

                    # 영역 행
                    if next_line == '영역':
                        j += 1
                        continue

                    # 세부능력및특기사항 행
                    if next_line == '세부능력및특기사항':
                        j += 1
                        continue

                    # 과목명 확인
                    if next_line in self.SUBJECTS:
                        if subject and content_lines:
                            # 이전 과목 저장
                            content = ' '.join(content_lines)
                            if len(content) > 50:
                                examples.append(self._create_example(subject, content))
                        subject = next_line
                        content_lines = []
                        j += 1
                        continue

                    # 무시할 패턴
                    if any(re.search(p, next_line) for p in self.IGNORE_PATTERNS):
                        j += 1
                        continue

                    # 내용 수집
                    if len(next_line) > 10:
                        content_lines.append(next_line)

                    j += 1

                # 마지막 과목 저장
                if subject and content_lines:
                    content = ' '.join(content_lines)
                    if len(content) > 50:
                        examples.append(self._create_example(subject, content))

                i = j
                continue

            # 직접 과목명으로 시작하는 세특 찾기
            if line in self.SUBJECTS:
                subject = line
                content_lines = []

                j = i + 1
                while j < min(i + 30, len(lines)):
                    next_line = lines[j].strip()

                    # 종료 조건
                    if next_line in self.SUBJECTS:
                        break
                    if any(kw in next_line for kw in ['보여주고싶은역량', '합격포인트', '탐구활동생기부기재내용']):
                        break

                    if len(next_line) > 10 and not any(re.search(p, next_line) for p in self.IGNORE_PATTERNS):
                        content_lines.append(next_line)

                    j += 1

                if content_lines:
                    content = ' '.join(content_lines)
                    if len(content) > 50:
                        examples.append(self._create_example(subject, content))

                i = j
                continue

            i += 1

        return examples

    def _create_example(self, subject: str, content: str) -> SaeteukExample:
        """세특 예시 객체 생성"""
        # 내용 정리
        content = re.sub(r'\s+', ' ', content).strip()

        # 학기 추출
        term = None
        term_match = re.search(r'([1-3])-([1-2])', content)
        if term_match:
            term = term_match.group(0)

        # 하이라이트 추출
        highlights = self._extract_highlights(content)

        return SaeteukExample(
            id=f"saeteuk_{uuid4().hex[:8]}",
            term=term,
            subject=subject,
            content=content[:1500] if len(content) > 1500 else content,
            highlights=highlights,
            evidence=Evidence(raw_text=content[:200])
        )

    def _extract_highlights(self, content: str) -> list[str]:
        """하이라이트 포인트 추출"""
        highlights = []

        # 핵심 키워드 포함된 구문
        key_patterns = [
            r'([^.]*?탐구[^.]*)',
            r'([^.]*?분석[^.]*)',
            r'([^.]*?발표[^.]*)',
            r'([^.]*?연구[^.]*)',
            r'([^.]*?프로젝트[^.]*)',
        ]

        for pattern in key_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                match = match.strip()
                if 20 <= len(match) <= 100 and match not in highlights:
                    highlights.append(match)
                    if len(highlights) >= 3:
                        break
            if len(highlights) >= 3:
                break

        return highlights

    def _extract_acceptance_points(self, text: str) -> list[str]:
        """합격 포인트 추출"""
        points = []
        lines = text.split('\n')

        for i, line in enumerate(lines):
            line = line.strip()

            # "합격포인트" 키워드 찾기
            if '합격포인트' in line or '합격 포인트' in line:
                # 이전 줄들에서 포인트 설명 찾기 (→ 로 시작하는 경우)
                for j in range(max(0, i - 5), i):
                    prev_line = lines[j].strip()
                    if prev_line.startswith('→') or prev_line.startswith('->'):
                        point = prev_line.lstrip('→-> ').strip()
                        if len(point) > 20 and point not in points:
                            points.append(point)

                # 같은 줄에 포인트가 있는 경우
                if '!!' in line:
                    # 앞의 설명 부분 추출
                    for j in range(max(0, i - 3), i):
                        prev_line = lines[j].strip()
                        if '→' in prev_line or '->' in prev_line:
                            point = prev_line.split('→')[-1].split('->')[-1].strip()
                            if len(point) > 20 and point not in points:
                                points.append(point)

        # 중복 제거 및 정리
        unique_points = []
        for point in points:
            # 너무 짧거나 무의미한 것 제외
            if len(point) < 20:
                continue
            # 이미 있는 것과 유사하면 제외
            is_duplicate = False
            for existing in unique_points:
                if point in existing or existing in point:
                    is_duplicate = True
                    break
            if not is_duplicate:
                unique_points.append(point[:200])

        return unique_points[:10]
