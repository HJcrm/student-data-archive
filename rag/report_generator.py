"""생기부 로드맵 레포트 생성기"""

from dataclasses import dataclass
from typing import Optional
from datetime import datetime
from .searcher import RAGSearcher, SearchResult
from .text_formatter import TextFormatter


@dataclass
class RoadmapReport:
    """로드맵 레포트"""
    query_info: dict
    similar_students: list[SearchResult]
    roadmap_by_term: dict
    recommended_subjects: list[str]
    key_insights: list[str]
    generated_at: str


class ReportGenerator:
    """RAG 기반 생기부 로드맵 레포트 생성기"""

    def __init__(self, metadata_dir: str = "data/metadata", enable_formatting: bool = True):
        self.searcher = RAGSearcher(metadata_dir=metadata_dir)
        self.enable_formatting = enable_formatting
        self.formatter = TextFormatter() if enable_formatting else None

    def generate(
        self,
        nesin_range: str,
        school_type: str,
        major_field: str,
        top_k: int = 3
    ) -> RoadmapReport:
        """레포트 생성"""
        # 유사 합격자 검색
        results = self.searcher.search(nesin_range, school_type, major_field, top_k)

        # 시기별 탐구활동 통합
        roadmap = self._merge_roadmaps(results)

        # 추천 과목 추출
        subjects = self._extract_recommended_subjects(results)

        # 핵심 인사이트 도출
        insights = self._generate_insights(results, nesin_range, major_field)

        return RoadmapReport(
            query_info={
                "nesin_range": nesin_range,
                "school_type": school_type,
                "major_field": major_field,
            },
            similar_students=results,
            roadmap_by_term=roadmap,
            recommended_subjects=subjects,
            key_insights=insights,
            generated_at=datetime.now().strftime("%Y-%m-%d %H:%M")
        )

    def _merge_roadmaps(self, results: list[SearchResult]) -> dict:
        """여러 합격자의 로드맵을 시기별로 통합"""
        merged = {}
        terms = ["1-1", "1-2", "2-1", "2-2", "3-1", "3-2"]

        for term in terms:
            merged[term] = {
                "research_topics": [],
                "saeteuk_examples": []
            }

        for result in results:
            # 탐구활동 수집
            for r in result.research_activities:
                term = r.get("term", "")
                if term in merged:
                    topic = {
                        "subject": r.get("subject", ""),
                        "title": r.get("title", ""),
                        "student": f"{result.university} {result.department}",
                        "nesin": result.nesin_average
                    }
                    merged[term]["research_topics"].append(topic)

            # 세특 예시 수집
            for s in result.saeteuk_examples:
                # 세특은 특정 학기에 배정하기 어려우므로 과목별로 분류
                subject = s.get("subject", "")
                content = s.get("content", "")
                highlights = s.get("highlights", [])

                # 학년 추정 (과목명에서)
                term = self._guess_term_from_subject(subject)
                if term and term in merged:
                    saeteuk = {
                        "subject": subject,
                        "content": content[:500] + "..." if len(content) > 500 else content,
                        "highlights": highlights[:5],
                        "student": f"{result.university}"
                    }
                    merged[term]["saeteuk_examples"].append(saeteuk)

        # 중복 제거 및 정렬
        for term in terms:
            # 탐구활동 중복 제거 (제목 기준)
            seen_titles = set()
            unique_topics = []
            for t in merged[term]["research_topics"]:
                title_key = t["title"][:30]
                if title_key not in seen_titles:
                    seen_titles.add(title_key)
                    unique_topics.append(t)
            merged[term]["research_topics"] = unique_topics[:5]  # 최대 5개

            # 세특 중복 제거
            seen_subjects = set()
            unique_saeteuk = []
            for s in merged[term]["saeteuk_examples"]:
                if s["subject"] not in seen_subjects:
                    seen_subjects.add(s["subject"])
                    unique_saeteuk.append(s)
            merged[term]["saeteuk_examples"] = unique_saeteuk[:3]  # 최대 3개

        # OpenAI로 텍스트 포맷팅 적용
        if self.enable_formatting and self.formatter:
            merged = self._format_roadmap_texts(merged)

        return merged

    def _format_roadmap_texts(self, merged: dict) -> dict:
        """로드맵 텍스트 포맷팅 (띄어쓰기 교정)"""
        print("[텍스트 포맷팅 중...]")

        # 모든 세특 내용 수집
        all_contents = []
        content_locations = []  # (term, index) 저장

        for term, data in merged.items():
            for i, saeteuk in enumerate(data["saeteuk_examples"]):
                content = saeteuk.get("content", "")
                if content and len(content) > 20:
                    all_contents.append(content)
                    content_locations.append((term, i))

        # 일괄 포맷팅
        if all_contents:
            try:
                formatted_contents = self.formatter.format_batch(all_contents)

                # 포맷팅된 내용 적용
                for idx, (term, i) in enumerate(content_locations):
                    if idx < len(formatted_contents):
                        merged[term]["saeteuk_examples"][i]["content"] = formatted_contents[idx]

                print(f"  - {len(all_contents)}개 세특 포맷팅 완료")
            except Exception as e:
                print(f"  - 포맷팅 오류: {e}")

        return merged

    def _guess_term_from_subject(self, subject: str) -> Optional[str]:
        """과목명에서 학기 추정"""
        # 학년 표시가 있는 경우
        if "1학년" in subject or "1학기" in subject:
            return "1-1"
        if "2학년" in subject:
            return "2-1"
        if "3학년" in subject:
            return "3-1"

        # 일반적인 과목 매핑
        subject_term_map = {
            "통합과학": "1-1",
            "통합사회": "1-1",
            "한국사": "1-2",
            "경제": "2-2",
            "정치와법": "2-2",
            "세계지리": "3-1",
            "진로": "2-1",
            "사회문화": "2-2",
            "생활과윤리": "3-1",
        }

        for key, term in subject_term_map.items():
            if key in subject:
                return term

        return "2-1"  # 기본값

    def _extract_recommended_subjects(self, results: list[SearchResult]) -> list[str]:
        """추천 과목 추출"""
        subject_count = {}

        for result in results:
            for r in result.research_activities:
                subject = r.get("subject", "")
                if subject:
                    subject_count[subject] = subject_count.get(subject, 0) + 1

            for s in result.saeteuk_examples:
                subject = s.get("subject", "")
                if subject:
                    subject_count[subject] = subject_count.get(subject, 0) + 1

        # 빈도순 정렬
        sorted_subjects = sorted(subject_count.items(), key=lambda x: x[1], reverse=True)
        return [s[0] for s in sorted_subjects[:10]]

    def _generate_insights(
        self,
        results: list[SearchResult],
        nesin_range: str,
        major_field: str
    ) -> list[str]:
        """핵심 인사이트 도출"""
        insights = []

        if not results:
            return ["매칭되는 합격자 데이터가 없습니다."]

        # 평균 내신
        avg_nesin = sum(r.nesin_average for r in results) / len(results)
        insights.append(f"유사 합격자 평균 내신: {avg_nesin:.2f}등급")

        # 합격 대학 분포
        universities = [r.university for r in results]
        univ_set = set(universities)
        insights.append(f"합격 대학: {', '.join(univ_set)}")

        # 공통 탐구 키워드
        all_titles = []
        for r in results:
            for act in r.research_activities:
                all_titles.append(act.get("title", ""))

        # 자주 등장하는 키워드 추출
        keywords = self._extract_keywords(all_titles)
        if keywords:
            insights.append(f"자주 등장하는 탐구 키워드: {', '.join(keywords[:5])}")

        # 계열별 특성
        if major_field == "경영/경제":
            insights.append("경영/경제 계열은 시사 이슈 연계, 데이터 분석, 정책 제안형 탐구가 효과적입니다.")
        elif major_field == "사회":
            insights.append("사회 계열은 사회 문제 분석, 설문/면접 연구, 제도 개선안 제시가 효과적입니다.")
        elif major_field == "인문":
            insights.append("인문 계열은 텍스트 분석, 비교 연구, 철학적 고찰이 효과적입니다.")

        return insights

    def _extract_keywords(self, titles: list[str]) -> list[str]:
        """제목에서 키워드 추출"""
        word_count = {}
        stopwords = {"통한", "대한", "관한", "위한", "따른", "미치는", "영향", "분석", "연구", "탐구", "의", "와", "과", "및", "을", "를", "이", "가"}

        for title in titles:
            words = title.replace(",", " ").replace(".", " ").split()
            for word in words:
                if len(word) >= 2 and word not in stopwords:
                    word_count[word] = word_count.get(word, 0) + 1

        sorted_words = sorted(word_count.items(), key=lambda x: x[1], reverse=True)
        return [w[0] for w in sorted_words[:10]]

    def to_markdown(self, report: RoadmapReport) -> str:
        """마크다운 형식 레포트 생성"""
        lines = []

        # 헤더
        lines.append("# 📚 맞춤형 생기부 로드맵 레포트")
        lines.append(f"\n생성일: {report.generated_at}")
        lines.append("")

        # 검색 조건
        lines.append("## 📋 분석 조건")
        lines.append(f"- **내신 등급대**: {report.query_info['nesin_range']}")
        lines.append(f"- **학교 유형**: {report.query_info['school_type']}")
        lines.append(f"- **희망 계열**: {report.query_info['major_field']}")
        lines.append("")

        # 핵심 인사이트
        lines.append("## 💡 핵심 인사이트")
        for insight in report.key_insights:
            lines.append(f"- {insight}")
        lines.append("")

        # 추천 과목
        lines.append("## 📖 추천 탐구 과목")
        lines.append(", ".join(report.recommended_subjects[:8]))
        lines.append("")

        # 유사 합격자
        lines.append("## 🎓 유사 합격자 사례")
        for i, student in enumerate(report.similar_students, 1):
            lines.append(f"\n### {i}. {student.university} {student.department}")
            lines.append(f"- 내신: {student.nesin_average:.2f}등급")
            lines.append(f"- 매칭 점수: {student.match_score:.0%}")
        lines.append("")

        # 학기별 로드맵
        lines.append("## 📅 학기별 탐구 로드맵")

        term_names = {
            "1-1": "1학년 1학기",
            "1-2": "1학년 2학기",
            "2-1": "2학년 1학기",
            "2-2": "2학년 2학기",
            "3-1": "3학년 1학기",
            "3-2": "3학년 2학기",
        }

        for term, name in term_names.items():
            data = report.roadmap_by_term.get(term, {})
            topics = data.get("research_topics", [])
            saeteuks = data.get("saeteuk_examples", [])

            if topics or saeteuks:
                lines.append(f"\n### 📌 {name}")

                if topics:
                    lines.append("\n**추천 탐구 주제:**")
                    for t in topics:
                        lines.append(f"- [{t['subject']}] {t['title']}")
                        lines.append(f"  - 출처: {t['student']} (내신 {t['nesin']:.1f}등급)")

                if saeteuks:
                    lines.append("\n**세특 예시:**")
                    for s in saeteuks:
                        lines.append(f"\n> **[{s['subject']}]** ({s['student']})")
                        lines.append(f"> {s['content'][:300]}...")
                        if s['highlights']:
                            lines.append(f"> ")
                            lines.append(f"> 🔑 핵심: {', '.join(s['highlights'][:3])}")

        lines.append("")
        lines.append("---")
        lines.append("*이 레포트는 RAG 시스템을 통해 유사 합격자 데이터를 분석하여 생성되었습니다.*")

        return "\n".join(lines)

    def to_html(self, report: RoadmapReport) -> str:
        """HTML 형식 레포트 생성"""
        html = []

        html.append("""
        <div class="report">
            <h1>📚 맞춤형 생기부 로드맵 레포트</h1>
            <p class="generated-at">생성일: {generated_at}</p>
        """.format(generated_at=report.generated_at))

        # 검색 조건
        html.append("""
            <section class="query-info">
                <h2>📋 분석 조건</h2>
                <ul>
                    <li><strong>내신 등급대:</strong> {nesin_range}</li>
                    <li><strong>학교 유형:</strong> {school_type}</li>
                    <li><strong>희망 계열:</strong> {major_field}</li>
                </ul>
            </section>
        """.format(**report.query_info))

        # 핵심 인사이트
        html.append('<section class="insights"><h2>💡 핵심 인사이트</h2><ul>')
        for insight in report.key_insights:
            html.append(f'<li>{insight}</li>')
        html.append('</ul></section>')

        # 추천 과목
        html.append('<section class="subjects"><h2>📖 추천 탐구 과목</h2>')
        html.append('<div class="subject-tags">')
        for subj in report.recommended_subjects[:8]:
            html.append(f'<span class="tag">{subj}</span>')
        html.append('</div></section>')

        # 유사 합격자
        html.append('<section class="similar-students"><h2>🎓 유사 합격자 사례</h2>')
        html.append('<div class="student-cards">')
        for student in report.similar_students:
            html.append(f"""
                <div class="student-card">
                    <h3>{student.university} {student.department}</h3>
                    <p>내신: {student.nesin_average:.2f}등급 | 매칭: {student.match_score:.0%}</p>
                </div>
            """)
        html.append('</div></section>')

        # 학기별 로드맵
        html.append('<section class="roadmap"><h2>📅 학기별 탐구 로드맵</h2>')

        term_names = {
            "1-1": "1학년 1학기", "1-2": "1학년 2학기",
            "2-1": "2학년 1학기", "2-2": "2학년 2학기",
            "3-1": "3학년 1학기", "3-2": "3학년 2학기",
        }

        for term, name in term_names.items():
            data = report.roadmap_by_term.get(term, {})
            topics = data.get("research_topics", [])
            saeteuks = data.get("saeteuk_examples", [])

            if topics or saeteuks:
                html.append(f'<div class="term-section"><h3>📌 {name}</h3>')

                if topics:
                    html.append('<div class="topics"><h4>추천 탐구 주제</h4><ul>')
                    for t in topics:
                        html.append(f"""
                            <li>
                                <strong>[{t['subject']}]</strong> {t['title']}
                                <span class="source">({t['student']})</span>
                            </li>
                        """)
                    html.append('</ul></div>')

                if saeteuks:
                    html.append('<div class="saeteuks"><h4>세특 예시</h4>')
                    for s in saeteuks:
                        html.append(f"""
                            <div class="saeteuk-card">
                                <div class="saeteuk-header">
                                    <strong>[{s['subject']}]</strong>
                                    <span class="source">{s['student']}</span>
                                </div>
                                <p class="saeteuk-content">{s['content'][:400]}...</p>
                                <div class="highlights">
                                    🔑 {', '.join(s['highlights'][:3]) if s['highlights'] else ''}
                                </div>
                            </div>
                        """)
                    html.append('</div>')

                html.append('</div>')

        html.append('</section>')
        html.append('</div>')

        return "\n".join(html)
