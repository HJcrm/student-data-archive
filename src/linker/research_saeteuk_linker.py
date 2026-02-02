"""탐구-세특 연결 모듈"""

import re
from dataclasses import dataclass

from ..models.schema import ResearchItem, SaeteukExample, LinkedResearch


@dataclass
class SubjectGroup:
    """과목 그룹"""
    name: str
    members: set[str]


class ResearchSaeteukLinker:
    """탐구 활동과 세특을 연결하는 클래스"""

    # 과목 유사성 그룹
    SUBJECT_GROUPS = [
        SubjectGroup('물리', {'물리', '물리학', '물리학I', '물리학II', '물리1', '물리2'}),
        SubjectGroup('화학', {'화학', '화학I', '화학II', '화학1', '화학2'}),
        SubjectGroup('생명과학', {'생명과학', '생명과학I', '생명과학II', '생명1', '생명2', '생물'}),
        SubjectGroup('지구과학', {'지구과학', '지구과학I', '지구과학II', '지구1', '지구2'}),
        SubjectGroup('수학', {'수학', '수학I', '수학II', '미적분', '확률과통계', '기하', '수1', '수2'}),
        SubjectGroup('국어', {'국어', '문학', '독서', '화법과작문', '언어와매체'}),
        SubjectGroup('영어', {'영어', '영어I', '영어II', '영어회화', '영어독해와작문'}),
        SubjectGroup('사회', {'사회', '통합사회', '사회문화', '정치와법', '경제'}),
        SubjectGroup('윤리', {'윤리', '생활과윤리', '윤리와사상'}),
        SubjectGroup('지리', {'지리', '한국지리', '세계지리'}),
        SubjectGroup('역사', {'역사', '한국사', '세계사', '동아시아사'}),
        SubjectGroup('과학탐구', {'과학', '통합과학', '과학탐구실험'}),
    ]

    def __init__(self):
        self.subject_to_group: dict[str, str] = {}
        self._build_subject_map()

    def _build_subject_map(self):
        """과목명 → 그룹명 매핑 구축"""
        for group in self.SUBJECT_GROUPS:
            for member in group.members:
                self.subject_to_group[member.lower()] = group.name
                # 레벨 표시 제거 버전도 추가
                base = re.sub(r'[IⅠⅡ12]+$', '', member).strip().lower()
                if base:
                    self.subject_to_group[base] = group.name

    def link(
        self,
        researches: list[ResearchItem],
        saeteuks: list[SaeteukExample]
    ) -> tuple[list[LinkedResearch], list[str], list[str]]:
        """탐구와 세특 연결

        Returns:
            - linked: 연결된 항목들
            - unlinked_researches: 연결 안 된 탐구 ID 목록
            - unlinked_saeteuks: 연결 안 된 세특 ID 목록
        """
        linked = []
        used_researches = set()
        used_saeteuks = set()

        # 모든 조합에 대해 매칭 점수 계산
        candidates = []
        for research in researches:
            if not research.id:
                continue
            for saeteuk in saeteuks:
                if not saeteuk.id:
                    continue
                score, reason = self._calculate_match_score(research, saeteuk)
                if score > 0:
                    candidates.append((score, reason, research.id, saeteuk.id))

        # 점수 높은 순으로 정렬
        candidates.sort(key=lambda x: -x[0])

        # 탐욕적 매칭 (각 항목은 한 번만 연결)
        for score, reason, research_id, saeteuk_id in candidates:
            if research_id in used_researches or saeteuk_id in used_saeteuks:
                continue

            linked.append(LinkedResearch(
                research_id=research_id,
                saeteuk_id=saeteuk_id,
                match_score=score,
                match_reason=reason
            ))
            used_researches.add(research_id)
            used_saeteuks.add(saeteuk_id)

        # 연결 안 된 항목들
        all_research_ids = {r.id for r in researches if r.id}
        all_saeteuk_ids = {s.id for s in saeteuks if s.id}

        unlinked_researches = list(all_research_ids - used_researches)
        unlinked_saeteuks = list(all_saeteuk_ids - used_saeteuks)

        return linked, unlinked_researches, unlinked_saeteuks

    def _calculate_match_score(
        self,
        research: ResearchItem,
        saeteuk: SaeteukExample
    ) -> tuple[float, str]:
        """매칭 점수 계산

        Returns:
            (score, reason) - 점수와 매칭 근거
        """
        score = 0.0
        reasons = []

        # 1. 학기 일치 (+0.3)
        term_match = self._check_term_match(research.term, saeteuk.term)
        if term_match == 'exact':
            score += 0.3
            reasons.append('같은 학기')
        elif term_match == 'adjacent':
            score += 0.1
            reasons.append('인접 학기')

        # 2. 과목 일치 (+0.4 또는 +0.25)
        subject_match = self._check_subject_match(research.subject, saeteuk.subject)
        if subject_match == 'exact':
            score += 0.4
            reasons.append('같은 과목')
        elif subject_match == 'similar':
            score += 0.25
            reasons.append('유사 과목')

        # 3. 키워드/내용 유사도 (+0.3)
        content_score = self._check_content_similarity(research, saeteuk)
        if content_score > 0:
            score += content_score
            reasons.append(f'내용 유사 ({int(content_score * 100)}%)')

        # 최종 점수 정규화 (0-1)
        score = min(score, 1.0)

        reason = ', '.join(reasons) if reasons else '연결 불가'
        return score, reason

    def _check_term_match(self, term1: str | None, term2: str | None) -> str:
        """학기 일치 확인"""
        if not term1 or not term2:
            return 'none'

        # 정규화: "1-1", "1학년1학기" 등을 (학년, 학기) 튜플로
        def normalize_term(t: str) -> tuple[int, int] | None:
            match = re.search(r'([1-3])[-학년]?\s*([1-2])', t)
            if match:
                return int(match.group(1)), int(match.group(2))
            return None

        t1 = normalize_term(term1)
        t2 = normalize_term(term2)

        if not t1 or not t2:
            return 'none'

        if t1 == t2:
            return 'exact'

        # 인접 학기: 같은 학년 또는 학기 차이가 1
        year_diff = abs(t1[0] - t2[0])
        sem_diff = abs(t1[1] - t2[1])

        if year_diff == 0 and sem_diff == 1:  # 같은 학년, 다른 학기
            return 'adjacent'
        if year_diff == 1 and (t1[1] == 2 and t2[1] == 1 or t1[1] == 1 and t2[1] == 2):
            # 1학년 2학기 → 2학년 1학기 같은 경우
            return 'adjacent'

        return 'none'

    def _check_subject_match(self, subj1: str | None, subj2: str | None) -> str:
        """과목 일치 확인"""
        if not subj1 or not subj2:
            return 'none'

        # 정규화
        s1 = subj1.lower().strip()
        s2 = subj2.lower().strip()

        # 정확히 일치
        if s1 == s2:
            return 'exact'

        # 그룹으로 일치 확인
        group1 = self.subject_to_group.get(s1)
        group2 = self.subject_to_group.get(s2)

        # 레벨 제거 후 재시도
        s1_base = re.sub(r'[IⅠⅡ12]+$', '', s1).strip()
        s2_base = re.sub(r'[IⅠⅡ12]+$', '', s2).strip()

        if s1_base == s2_base:
            return 'exact'

        group1 = group1 or self.subject_to_group.get(s1_base)
        group2 = group2 or self.subject_to_group.get(s2_base)

        if group1 and group2 and group1 == group2:
            return 'similar'

        return 'none'

    def _check_content_similarity(
        self,
        research: ResearchItem,
        saeteuk: SaeteukExample
    ) -> float:
        """내용 유사도 확인 (키워드 기반)"""
        # 탐구 키워드 수집
        research_keywords = set()
        if research.keywords:
            research_keywords.update(kw.lower() for kw in research.keywords)
        if research.title:
            # 제목에서 주요 단어 추출
            words = re.findall(r'[가-힣]{2,}', research.title)
            research_keywords.update(w.lower() for w in words if len(w) >= 2)

        # 세특 키워드 수집
        saeteuk_keywords = set()
        if saeteuk.highlights:
            saeteuk_keywords.update(hl.lower() for hl in saeteuk.highlights)
        if saeteuk.content:
            # 내용에서 주요 단어 추출
            words = re.findall(r'[가-힣]{2,}', saeteuk.content)
            saeteuk_keywords.update(w.lower() for w in words if len(w) >= 2)

        if not research_keywords or not saeteuk_keywords:
            return 0.0

        # Jaccard 유사도
        intersection = research_keywords & saeteuk_keywords
        union = research_keywords | saeteuk_keywords

        if not union:
            return 0.0

        # 최대 0.3점
        similarity = len(intersection) / len(union)
        return min(similarity * 0.5, 0.3)
