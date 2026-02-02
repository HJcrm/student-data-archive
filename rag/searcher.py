"""RAG 검색 시스템 - 유사 합격자 탐구 로드맵 검색"""

import json
from pathlib import Path
from typing import Optional
from dataclasses import dataclass


@dataclass
class SearchQuery:
    """검색 쿼리"""
    nesin_range: str  # "1등급대", "2등급대", "3등급대", "4등급대"
    school_type: str  # "일반고", "자사고", "특목고", "자공고"
    major_field: str  # "경영/경제", "인문", "사회", "어문", "교육"


@dataclass
class SearchResult:
    """검색 결과"""
    student_id: str
    university: str
    department: str
    nesin_average: float
    school_type: str
    major_field: str
    match_score: float  # 매칭 점수 (0~1)
    research_activities: list  # 시기별 탐구활동
    saeteuk_examples: list  # 세특 예시


class RAGSearcher:
    """RAG 기반 합격자 검색"""

    def __init__(self, metadata_dir: str = "data/metadata"):
        self.metadata_dir = Path(metadata_dir)
        self._load_data()

    def _load_data(self):
        """데이터 로드"""
        with open(self.metadata_dir / "students.json", "r", encoding="utf-8") as f:
            self.students = json.load(f)

        with open(self.metadata_dir / "research.json", "r", encoding="utf-8") as f:
            self.research = json.load(f)

        with open(self.metadata_dir / "saeteuk.json", "r", encoding="utf-8") as f:
            self.saeteuk = json.load(f)

        # 학생 ID별 인덱스 생성
        self.student_map = {s["id"]: s for s in self.students}

        # 학생별 탐구활동 그룹핑
        self.research_by_student = {}
        for r in self.research:
            sid = r["student_id"]
            if sid not in self.research_by_student:
                self.research_by_student[sid] = []
            self.research_by_student[sid].append(r)

        # 학생별 세특 그룹핑
        self.saeteuk_by_student = {}
        for s in self.saeteuk:
            sid = s["student_id"]
            if sid not in self.saeteuk_by_student:
                self.saeteuk_by_student[sid] = []
            self.saeteuk_by_student[sid].append(s)

    def search(
        self,
        nesin_range: str,
        school_type: str,
        major_field: str,
        top_k: int = 3
    ) -> list[SearchResult]:
        """유사 합격자 검색"""
        query = SearchQuery(
            nesin_range=nesin_range,
            school_type=school_type,
            major_field=major_field
        )

        # 각 학생별 매칭 점수 계산
        scored_students = []
        for student in self.students:
            score = self._calculate_match_score(student, query)
            if score > 0:
                scored_students.append((student, score))

        # 점수순 정렬
        scored_students.sort(key=lambda x: x[1], reverse=True)

        # 상위 K개 결과 반환
        results = []
        for student, score in scored_students[:top_k]:
            result = self._build_result(student, score)
            results.append(result)

        return results

    def _calculate_match_score(self, student: dict, query: SearchQuery) -> float:
        """매칭 점수 계산 (0~1)"""
        score = 0.0
        weights = {
            "major_field": 0.5,  # 계열 매칭이 가장 중요
            "nesin_range": 0.3,  # 등급대
            "school_type": 0.2   # 학교 유형
        }

        # 계열 매칭
        if student.get("major_field"):
            if self._match_major_field(student["major_field"], query.major_field):
                score += weights["major_field"]

        # 등급대 매칭
        if student.get("nesin_range"):
            nesin_score = self._match_nesin_range(
                student["nesin_range"], query.nesin_range
            )
            score += weights["nesin_range"] * nesin_score

        # 학교 유형 매칭
        if student.get("school_type"):
            if self._match_school_type(student["school_type"], query.school_type):
                score += weights["school_type"]

        return score

    def _match_major_field(self, student_field: str, query_field: str) -> bool:
        """계열 매칭"""
        # 정확히 일치
        if student_field == query_field:
            return True

        # 유사 계열 그룹
        similar_groups = [
            ["경영/경제", "경영", "경제", "상경"],
            ["인문", "어문", "국문", "문학"],
            ["사회", "사회과학", "정치", "행정"],
        ]

        for group in similar_groups:
            if student_field in group and query_field in group:
                return True

        return False

    def _match_nesin_range(self, student_range: str, query_range: str) -> float:
        """등급대 매칭 점수 (0~1)"""
        range_order = ["1등급대", "2등급대", "3등급대", "4등급대", "5등급대"]

        try:
            student_idx = range_order.index(student_range)
            query_idx = range_order.index(query_range)
            diff = abs(student_idx - query_idx)

            if diff == 0:
                return 1.0
            elif diff == 1:
                return 0.5  # 1등급 차이
            else:
                return 0.2  # 2등급 이상 차이

        except ValueError:
            return 0.0

    def _match_school_type(self, student_type: str, query_type: str) -> bool:
        """학교 유형 매칭"""
        if student_type == query_type:
            return True

        # 일반고 계열 묶기
        general_types = ["일반고", "자공고"]
        if student_type in general_types and query_type in general_types:
            return True

        return False

    def _build_result(self, student: dict, score: float) -> SearchResult:
        """검색 결과 구성"""
        student_id = student["id"]

        # 탐구활동 가져오기 (학기순 정렬)
        research_list = self.research_by_student.get(student_id, [])
        research_list = sorted(research_list, key=lambda x: x.get("term", ""))

        # 세특 가져오기
        saeteuk_list = self.saeteuk_by_student.get(student_id, [])

        return SearchResult(
            student_id=student_id,
            university=student.get("final_university", ""),
            department=student.get("final_department", ""),
            nesin_average=student.get("nesin_average", 0),
            school_type=student.get("school_type", ""),
            major_field=student.get("major_field", ""),
            match_score=score,
            research_activities=research_list,
            saeteuk_examples=saeteuk_list
        )

    def _find_matching_saeteuk(self, research: dict, saeteuk_list: list) -> Optional[dict]:
        """탐구활동과 매칭되는 세특 찾기"""
        research_subject = research.get("subject", "").lower()
        research_term = research.get("term", "")

        best_match = None
        best_score = 0

        for saeteuk in saeteuk_list:
            saeteuk_subject = saeteuk.get("subject", "").lower()
            score = 0

            # 과목명 매칭
            if research_subject and saeteuk_subject:
                # 정확히 일치
                if research_subject in saeteuk_subject or saeteuk_subject in research_subject:
                    score += 10
                # 유사 과목 (예: 영어, 영어독해작문)
                elif self._similar_subject(research_subject, saeteuk_subject):
                    score += 5

            if score > best_score:
                best_score = score
                best_match = saeteuk

        return best_match if best_score > 0 else None

    def _similar_subject(self, subj1: str, subj2: str) -> bool:
        """유사 과목 판단"""
        subject_groups = [
            ["영어", "영어독해", "영어작문", "영어회화"],
            ["수학", "수학1", "수학2", "미적분", "확률과통계", "기하"],
            ["국어", "문학", "독서", "화법과작문", "언어와매체"],
            ["과학", "물리", "화학", "생명", "지구과학", "통합과학"],
            ["사회", "한국사", "세계사", "동아시아사", "정치", "경제", "사회문화"],
            ["진로", "진로활동", "진로탐구"],
        ]

        for group in subject_groups:
            matches1 = any(g in subj1 for g in group)
            matches2 = any(g in subj2 for g in group)
            if matches1 and matches2:
                return True
        return False

    def format_roadmap(self, result: SearchResult) -> str:
        """로드맵 포맷팅"""
        lines = []
        lines.append(f"\n{'='*60}")
        lines.append(f"합격자: {result.university} {result.department}")
        lines.append(f"내신: {result.nesin_average:.2f}등급 | 학교: {result.school_type} | 계열: {result.major_field}")
        lines.append(f"매칭 점수: {result.match_score:.1%}")
        lines.append(f"{'='*60}")

        # 시기별 탐구활동 그룹핑
        by_term = {}
        for r in result.research_activities:
            term = r.get("term", "미상")
            if term not in by_term:
                by_term[term] = []
            by_term[term].append(r)

        lines.append("\n[시기별 탐구 로드맵]")
        for term in sorted(by_term.keys()):
            lines.append(f"\n  {term}학기:")
            for r in by_term[term]:
                subject = r.get("subject", "")
                title = r.get("title", "")
                lines.append(f"    - [{subject}] {title}")

        # 세특 예시
        lines.append("\n[세특 예시]")
        for i, s in enumerate(result.saeteuk_examples, 1):
            subject = s.get("subject", "미상")
            content = s.get("content", "")
            # 내용 미리보기 (200자)
            preview = content[:200] + "..." if len(content) > 200 else content
            lines.append(f"\n  {i}. [{subject}]")
            lines.append(f"     {preview}")

            # 하이라이트
            highlights = s.get("highlights", [])
            if highlights:
                lines.append(f"     핵심: {', '.join(highlights[:3])}")

        return "\n".join(lines)

    def format_roadmap_with_linked_saeteuk(self, result: SearchResult) -> str:
        """탐구활동별 세특 연결하여 로드맵 포맷팅"""
        lines = []
        lines.append(f"\n{'='*70}")
        lines.append(f"  합격자: {result.university} {result.department}")
        lines.append(f"  내신: {result.nesin_average:.2f}등급 | 학교: {result.school_type} | 계열: {result.major_field}")
        lines.append(f"  매칭 점수: {result.match_score:.1%}")
        lines.append(f"{'='*70}")

        # 시기별 탐구활동 그룹핑
        by_term = {}
        for r in result.research_activities:
            term = r.get("term", "미상")
            if term not in by_term:
                by_term[term] = []
            by_term[term].append(r)

        # 사용된 세특 추적
        used_saeteuk_ids = set()

        lines.append("\n[학년별 탐구 로드맵 + 세특 예시]")

        for term in sorted(by_term.keys()):
            grade = term.split("-")[0] if "-" in term else term
            lines.append(f"\n{'─'*70}")
            lines.append(f"  📚 {term}학기")
            lines.append(f"{'─'*70}")

            for r in by_term[term]:
                subject = r.get("subject", "")
                title = r.get("title", "")

                lines.append(f"\n  ▶ [{subject}] {title}")

                # 해당 탐구와 매칭되는 세특 찾기
                matching_saeteuk = self._find_matching_saeteuk(r, result.saeteuk_examples)
                if matching_saeteuk and matching_saeteuk.get("id") not in used_saeteuk_ids:
                    used_saeteuk_ids.add(matching_saeteuk.get("id"))
                    saeteuk_subject = matching_saeteuk.get("subject", "")
                    content = matching_saeteuk.get("content", "")
                    preview = content[:300] + "..." if len(content) > 300 else content

                    lines.append(f"\n    ┌─ 세특 예시 [{saeteuk_subject}]")
                    # 내용을 줄바꿈하여 보기 좋게 표시
                    wrapped = self._wrap_text(preview, width=60, indent="    │ ")
                    lines.append(wrapped)

                    highlights = matching_saeteuk.get("highlights", [])
                    if highlights:
                        lines.append(f"    └─ 핵심: {', '.join(highlights[:3])}")
                    else:
                        lines.append("    └─────────────────────────────")

        # 매칭되지 않은 세특 표시
        unmatched = [s for s in result.saeteuk_examples if s.get("id") not in used_saeteuk_ids]
        if unmatched:
            lines.append(f"\n{'─'*70}")
            lines.append("  📝 추가 세특 예시")
            lines.append(f"{'─'*70}")
            for s in unmatched[:3]:  # 최대 3개만
                subject = s.get("subject", "")
                content = s.get("content", "")[:200] + "..."
                lines.append(f"\n  [{subject}]")
                lines.append(f"    {content}")

        return "\n".join(lines)

    def _wrap_text(self, text: str, width: int = 60, indent: str = "") -> str:
        """텍스트 줄바꿈"""
        words = text.replace("\n", " ").split()
        lines = []
        current_line = indent

        for word in words:
            if len(current_line) + len(word) + 1 <= width + len(indent):
                current_line += word + " "
            else:
                lines.append(current_line.rstrip())
                current_line = indent + word + " "

        if current_line.strip():
            lines.append(current_line.rstrip())

        return "\n".join(lines)

    def search_and_print(
        self,
        nesin_range: str,
        school_type: str,
        major_field: str,
        top_k: int = 3,
        show_linked: bool = True
    ):
        """검색 후 결과 출력"""
        print(f"\n[검색 조건]")
        print(f"  등급대: {nesin_range}")
        print(f"  학교유형: {school_type}")
        print(f"  희망계열: {major_field}")

        results = self.search(nesin_range, school_type, major_field, top_k)

        if not results:
            print("\n매칭되는 합격자가 없습니다.")
            return

        print(f"\n[검색 결과] {len(results)}명의 유사 합격자")

        for result in results:
            if show_linked:
                print(self.format_roadmap_with_linked_saeteuk(result))
            else:
                print(self.format_roadmap(result))


def main():
    """테스트 실행"""
    searcher = RAGSearcher()

    # 테스트 검색
    searcher.search_and_print(
        nesin_range="2등급대",
        school_type="일반고",
        major_field="경영/경제"
    )


if __name__ == "__main__":
    main()
