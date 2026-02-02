"""마크다운 레포트 생성 모듈"""

from ..models.schema import StudentData


class MarkdownGenerator:
    """마크다운 레포트 생성기"""

    NOT_SPECIFIED = "PDF에 명시 없음"

    def generate(self, data: StudentData) -> str:
        """전체 레포트 생성"""
        sections = [
            self._generate_header(data),
            self._generate_grades_section(data),
            self._generate_susi_section(data),
            self._generate_school_section(data),
            self._generate_roadmap_section(data),
            self._generate_saenggibu_section(data),
            self._generate_linked_section(data),
            self._generate_summary_section(data),
        ]

        return "\n\n---\n\n".join(filter(None, sections))

    def _generate_header(self, data: StudentData) -> str:
        """헤더 생성"""
        lines = [
            f"# 합격 사례 분석: {data.alias}",
            "",
            f"- **원본 파일**: {data.source_file}",
        ]

        if data.susi_card.final_choice:
            lines.append(f"- **최종 진학**: {data.susi_card.final_choice}")

        if data.grades.grade_type:
            lines.append(f"- **성적 유형**: {data.grades.grade_type}")

        return "\n".join(lines)

    def _generate_grades_section(self, data: StudentData) -> str:
        """성적 섹션 생성"""
        lines = ["## 1. 성적 정보"]

        # 내신 성적
        lines.append("\n### 내신 성적")
        if data.grades.nesin.rows:
            lines.append("\n| 학기 | 과목 | 등급 | 원점수 |")
            lines.append("|------|------|------|--------|")
            for row in data.grades.nesin.rows[:20]:  # 최대 20개
                grade = str(row.grade) if row.grade else "-"
                score = str(row.raw_score) if row.raw_score else "-"
                lines.append(f"| {row.term} | {row.subject} | {grade} | {score} |")

            if data.grades.nesin.overall_average:
                lines.append(f"\n**전체 평균 등급**: {data.grades.nesin.overall_average}")

            if data.grades.nesin.subject_averages:
                lines.append("\n**과목별 평균**:")
                for subj, avg in data.grades.nesin.subject_averages.items():
                    lines.append(f"- {subj}: {avg}")
        else:
            lines.append(f"\n{self.NOT_SPECIFIED}")

        # 모의고사
        lines.append("\n### 모의고사 성적")
        if data.grades.mock_exams:
            lines.append("\n| 시기 | 과목 | 등급 | 백분위 |")
            lines.append("|------|------|------|--------|")
            for row in data.grades.mock_exams[:10]:
                date = row.date or "-"
                grade = str(row.grade) if row.grade else "-"
                pct = f"{row.percentile}%" if row.percentile else "-"
                lines.append(f"| {date} | {row.subject} | {grade} | {pct} |")
        else:
            lines.append(f"\n{self.NOT_SPECIFIED}")

        # 수능
        lines.append("\n### 수능 성적")
        if data.grades.suneung:
            su = data.grades.suneung
            items = []
            if su.korean:
                items.append(f"- 국어: {su.korean}등급")
            if su.math:
                items.append(f"- 수학: {su.math}등급")
            if su.english:
                items.append(f"- 영어: {su.english}등급")
            if su.history:
                items.append(f"- 한국사: {su.history}등급")
            if su.tamgu1:
                items.append(f"- {su.tamgu1}: {su.tamgu1_grade}등급")
            if su.tamgu2:
                items.append(f"- {su.tamgu2}: {su.tamgu2_grade}등급")

            if items:
                lines.append("")
                lines.extend(items)
            else:
                lines.append(f"\n{self.NOT_SPECIFIED}")
        else:
            lines.append(f"\n{self.NOT_SPECIFIED}")

        return "\n".join(lines)

    def _generate_susi_section(self, data: StudentData) -> str:
        """수시카드 섹션 생성"""
        lines = ["## 2. 수시 지원 결과"]

        if data.susi_card.applications:
            lines.append("\n| 대학 | 학과 | 전형 | 결과 |")
            lines.append("|------|------|------|------|")
            for app in data.susi_card.applications:
                lines.append(f"| {app.university} | {app.department} | {app.admission_type} | {app.result} |")

            if data.susi_card.final_choice:
                lines.append(f"\n**최종 선택**: {data.susi_card.final_choice}")

            if data.susi_card.strategy_notes:
                lines.append(f"\n**지원 전략**: {data.susi_card.strategy_notes}")
        else:
            lines.append(f"\n{self.NOT_SPECIFIED}")

        return "\n".join(lines)

    def _generate_school_section(self, data: StudentData) -> str:
        """학교 특성 섹션 생성"""
        lines = ["## 3. 학교 특성"]

        school = data.school
        items = []

        if school.school_name:
            items.append(f"- **학교명**: {school.school_name}")
        if school.region:
            items.append(f"- **지역**: {school.region}")
        if school.school_type:
            items.append(f"- **유형**: {school.school_type}")
        if school.atmosphere:
            items.append(f"- **분위기**: {school.atmosphere}")
        if school.competition_level:
            items.append(f"- **경쟁 수준**: {school.competition_level}")
        if school.special_programs:
            items.append(f"- **특별 프로그램**: {', '.join(school.special_programs)}")

        if items:
            lines.append("")
            lines.extend(items)
        else:
            lines.append(f"\n{self.NOT_SPECIFIED}")

        return "\n".join(lines)

    def _generate_roadmap_section(self, data: StudentData) -> str:
        """로드맵 섹션 생성"""
        lines = ["## 4. 생기부 로드맵"]

        roadmap = data.roadmap

        # 전체 테마
        if roadmap.overall_theme:
            lines.append(f"\n**전체 테마**: {roadmap.overall_theme}")

        # 학년별 전략
        if roadmap.yearly_strategies:
            lines.append("\n### 학년별 전략")
            for year, strategy in roadmap.yearly_strategies.items():
                lines.append(f"\n**{year}**")
                lines.append(f"{strategy}")

        # Top 탐구
        if roadmap.top_researches:
            lines.append("\n### 핵심 탐구 활동")
            for i, research in enumerate(roadmap.top_researches, 1):
                lines.append(f"\n**{i}. {research.title}**")
                if research.term:
                    lines.append(f"- 시기: {research.term}")
                if research.subject:
                    lines.append(f"- 과목: {research.subject}")
                if research.description:
                    lines.append(f"- 설명: {research.description}")
                if research.keywords:
                    lines.append(f"- 키워드: {', '.join(research.keywords)}")

        if not roadmap.yearly_strategies and not roadmap.top_researches:
            lines.append(f"\n{self.NOT_SPECIFIED}")

        return "\n".join(lines)

    def _generate_saenggibu_section(self, data: StudentData) -> str:
        """세특 섹션 생성"""
        lines = ["## 5. 세특 예시"]

        saenggibu = data.saenggibu

        if saenggibu.saeteuk_examples:
            for example in saenggibu.saeteuk_examples:
                lines.append(f"\n### {example.subject}")
                if example.term:
                    lines.append(f"*{example.term}*")
                lines.append("")
                lines.append(f"> {example.content}")
                if example.highlights:
                    lines.append(f"\n**핵심 포인트**: {', '.join(example.highlights)}")
        else:
            lines.append(f"\n{self.NOT_SPECIFIED}")

        # 합격 포인트
        lines.append("\n### 합격 포인트")
        if saenggibu.acceptance_points:
            for i, point in enumerate(saenggibu.acceptance_points, 1):
                lines.append(f"{i}. {point}")
        else:
            lines.append(self.NOT_SPECIFIED)

        return "\n".join(lines)

    def _generate_linked_section(self, data: StudentData) -> str:
        """탐구-세특 연결 섹션 생성"""
        lines = ["## 6. 탐구-세특 연결 분석"]

        saenggibu = data.saenggibu

        if saenggibu.linked_researches:
            lines.append("\n### 연결된 항목")
            lines.append("\n| 탐구 ID | 세특 ID | 매칭 점수 | 연결 근거 |")
            lines.append("|---------|---------|-----------|-----------|")
            for link in saenggibu.linked_researches:
                score = f"{link.match_score:.0%}"
                lines.append(f"| {link.research_id[:12]}... | {link.saeteuk_id[:12]}... | {score} | {link.match_reason} |")
        else:
            lines.append("\n연결된 항목 없음")

        if saenggibu.unlinked_researches:
            lines.append(f"\n### 연결 안 된 탐구: {len(saenggibu.unlinked_researches)}개")

        if saenggibu.unlinked_saeteuks:
            lines.append(f"\n### 연결 안 된 세특: {len(saenggibu.unlinked_saeteuks)}개")

        return "\n".join(lines)

    def _generate_summary_section(self, data: StudentData) -> str:
        """요약 섹션 생성"""
        lines = ["## 7. 파싱 정보"]

        # 통계
        stats = []
        stats.append(f"- 내신 기록: {len(data.grades.nesin.rows)}개")
        stats.append(f"- 모의고사 기록: {len(data.grades.mock_exams)}개")
        stats.append(f"- 수시 지원: {len(data.susi_card.applications)}개")
        stats.append(f"- 탐구 활동: {len(data.roadmap.top_researches)}개")
        stats.append(f"- 세특 예시: {len(data.saenggibu.saeteuk_examples)}개")

        lines.append("")
        lines.extend(stats)

        # 파싱 메모
        if data.parsing_notes:
            lines.append("\n### 파싱 메모")
            for note in data.parsing_notes:
                lines.append(f"- {note}")

        return "\n".join(lines)
