"""기존 파싱 데이터를 RAG 스키마로 변환"""

import json
import hashlib
import re
from pathlib import Path
from datetime import datetime
from typing import Optional

from .schema import (
    StudentProfile,
    ResearchActivity,
    SaeteukExample,
    RAGDocument,
    GradeType,
    GradeRange,
    UniversityTier,
    MajorField,
    SchoolType,
    CompetitionLevel,
)


class DataConverter:
    """기존 JSON 데이터 → RAG 스키마 변환기"""

    # 대학 티어 매핑
    UNIVERSITY_TIERS = {
        "SKY": ["서울대학교", "연세대학교", "고려대학교"],
        "인서울상위": ["성균관대학교", "한양대학교", "중앙대학교", "경희대학교", "한국외국어대학교", "서울시립대학교", "이화여자대학교"],
        "인서울": ["건국대학교", "동국대학교", "홍익대학교", "국민대학교", "숭실대학교", "세종대학교", "단국대학교", "광운대학교"],
        "지방거점": ["부산대학교", "경북대학교", "전남대학교", "전북대학교", "충남대학교", "충북대학교", "강원대학교", "제주대학교"],
    }

    # 계열 키워드 매핑 (우선순위 순서: 구체적인 것 먼저)
    MAJOR_FIELD_KEYWORDS = [
        ("의약", ["의예", "의학과", "치의예", "치의학", "한의예", "한의학", "약학", "간호", "수의예", "수의학"]),
        ("공학", ["컴퓨터", "소프트웨어", "전자", "전기", "기계", "화공", "건축", "토목", "산업공학", "반도체", "신소재", "재료", "데이터", "융합", "환경공학", "에너지"]),
        ("자연", ["수학", "물리", "화학", "생명과학", "생물", "지구과학", "천문", "대기과학"]),
        ("교육", ["교육", "사범"]),
        ("인문", ["국어국문", "영어영문", "중어중문", "일어일문", "사학", "철학", "문학", "언어", "한문"]),
        ("사회", ["정치", "외교", "행정", "사회학", "심리", "사회복지", "언론", "미디어", "법학"]),
        ("경영/경제", ["경영", "경제", "금융", "회계", "무역", "국제통상", "세무", "재무", "상경"]),
        ("예체능", ["미술", "음악", "체육", "디자인", "연극", "영화"]),
    ]

    def __init__(self):
        self.converted_documents: list[RAGDocument] = []

    def convert_file(self, json_path: Path) -> RAGDocument:
        """단일 JSON 파일 변환"""
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 학생 ID 생성
        student_id = self._generate_id(data.get("alias", json_path.stem))

        # 학생 프로필 변환
        profile = self._convert_profile(data, student_id)

        # 탐구활동 변환
        research_activities = self._convert_research_activities(data, student_id)

        # 세특 변환
        saeteuk_examples = self._convert_saeteuk_examples(data, student_id)

        # 탐구-세특 연결 정보 반영
        self._link_research_saeteuk(data, research_activities, saeteuk_examples)

        doc = RAGDocument(
            profile=profile,
            research_activities=research_activities,
            saeteuk_examples=saeteuk_examples,
            created_at=datetime.now().isoformat(),
        )

        self.converted_documents.append(doc)
        return doc

    def _generate_id(self, base: str) -> str:
        """고유 ID 생성"""
        hash_input = f"{base}_{datetime.now().isoformat()}"
        return hashlib.md5(hash_input.encode()).hexdigest()[:12]

    def _convert_profile(self, data: dict, student_id: str) -> StudentProfile:
        """학생 프로필 변환"""
        grades = data.get("grades", {})
        susi_card = data.get("susi_card", {})
        school = data.get("school", {})
        roadmap = data.get("roadmap", {})

        # 내신 평균 계산
        nesin_avg = self._calculate_nesin_average(grades.get("nesin", {}))
        nesin_range = self._get_grade_range(nesin_avg)

        # 성적 유형
        grade_type = self._parse_grade_type(grades.get("grade_type"))

        # 최종 진학 정보
        final_univ = susi_card.get("final_choice")
        final_dept = self._get_final_department(susi_card)
        univ_tier = self._get_university_tier(final_univ)

        # 계열 추론
        major_field = self._infer_major_field(final_dept, roadmap.get("overall_theme"))

        # 학교 정보
        school_type = self._parse_school_type(school.get("school_type"))
        competition = self._parse_competition_level(school.get("competition_level"))

        return StudentProfile(
            id=student_id,
            source_file=data.get("source_file", ""),
            grade_type=grade_type,
            nesin_average=nesin_avg,
            nesin_range=nesin_range,
            final_university=final_univ,
            final_department=final_dept,
            university_tier=univ_tier,
            major_field=major_field,
            school_name=school.get("school_name"),
            school_type=school_type,
            school_region=school.get("region"),
            competition_level=competition,
            overall_theme=roadmap.get("overall_theme"),
        )

    def _calculate_nesin_average(self, nesin: dict) -> Optional[float]:
        """내신 평균 계산"""
        rows = nesin.get("rows", [])
        if not rows:
            return None

        grades = [r.get("grade") for r in rows if r.get("grade")]
        if not grades:
            return None

        return round(sum(grades) / len(grades), 2)

    def _get_grade_range(self, avg: Optional[float]) -> Optional[str]:
        """등급대 계산"""
        if avg is None:
            return None
        if avg < 1.5:
            return GradeRange.GRADE_1.value
        elif avg < 2.5:
            return GradeRange.GRADE_2.value
        elif avg < 3.5:
            return GradeRange.GRADE_3.value
        elif avg < 4.5:
            return GradeRange.GRADE_4.value
        else:
            return GradeRange.GRADE_5_PLUS.value

    def _parse_grade_type(self, grade_type: Optional[str]) -> Optional[str]:
        """성적 유형 파싱"""
        if not grade_type:
            return None
        if "내신" in grade_type:
            return GradeType.NESIN.value
        elif "수능" in grade_type:
            return GradeType.SUNEUNG.value
        elif "균형" in grade_type:
            return GradeType.BALANCED.value
        return grade_type

    def _get_final_department(self, susi_card: dict) -> Optional[str]:
        """최종 진학 학과 추출"""
        final_univ = susi_card.get("final_choice")
        if not final_univ:
            return None

        for app in susi_card.get("applications", []):
            if app.get("university") == final_univ:
                result = app.get("result", "")
                if "합격" in result:
                    return app.get("department")
        return None

    def _get_university_tier(self, univ: Optional[str]) -> Optional[str]:
        """대학 티어 분류"""
        if not univ:
            return None

        for tier, universities in self.UNIVERSITY_TIERS.items():
            for u in universities:
                if u in univ or univ in u:
                    return tier
        return UniversityTier.OTHER.value

    def _infer_major_field(self, dept: Optional[str], theme: Optional[str]) -> Optional[str]:
        """계열 추론 (우선순위 기반)"""
        search_text = f"{dept or ''} {theme or ''}".lower()

        for field, keywords in self.MAJOR_FIELD_KEYWORDS:
            for keyword in keywords:
                if keyword.lower() in search_text:
                    return field

        return MajorField.OTHER.value

    def _parse_school_type(self, school_type: Optional[str]) -> Optional[str]:
        """학교 유형 파싱"""
        if not school_type:
            return None
        if "일반" in school_type:
            return SchoolType.GENERAL.value
        elif "자사" in school_type or "자율" in school_type:
            return SchoolType.AUTONOMOUS_PRIVATE.value
        elif "특목" in school_type or "외고" in school_type or "과학" in school_type:
            return SchoolType.SPECIALIZED.value
        elif "영재" in school_type:
            return SchoolType.GIFTED.value
        return school_type

    def _parse_competition_level(self, level: Optional[str]) -> Optional[str]:
        """경쟁 수준 파싱"""
        if not level:
            return None
        level_lower = level.lower()
        if "높" in level or "치열" in level or "상위" in level or "경쟁" in level:
            return CompetitionLevel.HIGH.value
        elif "보통" in level or "중" in level:
            return CompetitionLevel.MEDIUM.value
        elif "낮" in level:
            return CompetitionLevel.LOW.value
        # 기본값: 높음으로 처리 (대부분의 합격 사례가 경쟁이 있는 학교)
        return CompetitionLevel.HIGH.value

    def _convert_research_activities(self, data: dict, student_id: str) -> list[ResearchActivity]:
        """탐구활동 변환"""
        roadmap = data.get("roadmap", {})
        researches = roadmap.get("top_researches", [])

        activities = []
        for i, r in enumerate(researches):
            term = r.get("term") or ""  # None이면 빈 문자열
            grade, semester = self._parse_term(term)

            # RAG용 텍스트 생성
            rag_text = self._create_research_rag_text(r)

            # 키워드 추출
            keywords = self._extract_keywords(r.get("title", "") or "")

            activity = ResearchActivity(
                id=r.get("id", f"research_{i+1:03d}"),
                student_id=student_id,
                term=term,
                grade=grade,
                semester=semester,
                subject=r.get("subject") or "",
                title=r.get("title") or "",
                description=r.get("description"),
                keywords=keywords,
                linked_saeteuk_id=None,  # 나중에 연결
                rag_text=rag_text,
            )
            activities.append(activity)

        return activities

    def _parse_term(self, term: str) -> tuple[int, int]:
        """학기 문자열 파싱 (예: '2-1' -> (2, 1))"""
        if not term:
            return 0, 0
        match = re.match(r"(\d)-(\d)", str(term))
        if match:
            return int(match.group(1)), int(match.group(2))
        return 0, 0

    def _create_research_rag_text(self, research: dict) -> str:
        """탐구활동 RAG 검색용 텍스트 생성"""
        parts = []
        if research.get("title"):
            parts.append(f"탐구주제: {research['title']}")
        if research.get("subject"):
            parts.append(f"과목: {research['subject']}")
        if research.get("term"):
            parts.append(f"시기: {research['term']}")
        if research.get("description"):
            parts.append(f"설명: {research['description']}")
        return " | ".join(parts)

    def _extract_keywords(self, text: str) -> list[str]:
        """텍스트에서 키워드 추출 (간단한 규칙 기반)"""
        # 주요 키워드 사전
        keyword_dict = [
            "경영", "경제", "금융", "투자", "기업", "마케팅", "ESG", "탄소",
            "환경", "기후", "에너지", "반도체", "AI", "인공지능", "데이터",
            "정치", "외교", "사회", "복지", "법", "정책", "무역", "글로벌",
            "수학", "통계", "과학", "기술", "의료", "건강", "심리", "교육",
        ]

        found = []
        for kw in keyword_dict:
            if kw in text:
                found.append(kw)
        return found[:5]  # 최대 5개

    def _convert_saeteuk_examples(self, data: dict, student_id: str) -> list[SaeteukExample]:
        """세특 예시 변환"""
        saenggibu = data.get("saenggibu", {})
        examples = saenggibu.get("saeteuk_examples", [])

        saeteuks = []
        for i, ex in enumerate(examples):
            # RAG용 텍스트 생성
            rag_text = self._create_saeteuk_rag_text(ex)

            saeteuk = SaeteukExample(
                id=ex.get("id", f"saeteuk_{i+1:03d}"),
                student_id=student_id,
                subject=ex.get("subject", ""),
                term=ex.get("term"),
                content=ex.get("content", ""),
                highlights=ex.get("highlights", []),
                linked_research_ids=[],  # 나중에 연결
                rag_text=rag_text,
            )
            saeteuks.append(saeteuk)

        return saeteuks

    def _create_saeteuk_rag_text(self, saeteuk: dict) -> str:
        """세특 RAG 검색용 텍스트 생성"""
        parts = []
        if saeteuk.get("subject"):
            parts.append(f"과목: {saeteuk['subject']}")
        if saeteuk.get("content"):
            # 내용이 너무 길면 앞부분만 사용 (임베딩 효율)
            content = saeteuk["content"][:1000]
            parts.append(f"내용: {content}")
        if saeteuk.get("highlights"):
            parts.append(f"핵심: {', '.join(saeteuk['highlights'])}")
        return " | ".join(parts)

    def _link_research_saeteuk(
        self,
        data: dict,
        research_activities: list[ResearchActivity],
        saeteuk_examples: list[SaeteukExample]
    ):
        """탐구-세특 연결 정보 반영"""
        linked = data.get("saenggibu", {}).get("linked_researches", [])

        # ID 매핑 생성
        research_map = {r.id: r for r in research_activities}
        saeteuk_map = {s.id: s for s in saeteuk_examples}

        for link in linked:
            research_id = link.get("research_id", "")
            saeteuk_id = link.get("saeteuk_id", "")

            # 부분 매칭 (ID가 축약된 경우)
            for rid, research in research_map.items():
                if research_id in rid or rid in research_id:
                    for sid, saeteuk in saeteuk_map.items():
                        if saeteuk_id in sid or sid in saeteuk_id:
                            research.linked_saeteuk_id = sid
                            if rid not in saeteuk.linked_research_ids:
                                saeteuk.linked_research_ids.append(rid)

    def convert_directory(self, input_dir: Path, output_dir: Path) -> list[RAGDocument]:
        """디렉토리 내 모든 JSON 파일 변환"""
        json_files = list(input_dir.glob("*_data.json"))
        print(f"[변환] {len(json_files)}개 파일 발견")

        documents = []
        for json_path in json_files:
            try:
                print(f"  변환 중: {json_path.name}")
                doc = self.convert_file(json_path)
                documents.append(doc)
            except Exception as e:
                print(f"  [오류] {json_path.name}: {e}")

        # 결과 저장
        self._save_converted_data(documents, output_dir)

        return documents

    def _save_converted_data(self, documents: list[RAGDocument], output_dir: Path):
        """변환된 데이터 저장"""
        output_dir.mkdir(parents=True, exist_ok=True)

        # 학생 프로필
        profiles = [doc.profile.model_dump() for doc in documents]
        with open(output_dir / "students.json", "w", encoding="utf-8") as f:
            json.dump(profiles, f, ensure_ascii=False, indent=2)

        # 탐구활동
        all_research = []
        for doc in documents:
            for r in doc.research_activities:
                all_research.append(r.model_dump())
        with open(output_dir / "research.json", "w", encoding="utf-8") as f:
            json.dump(all_research, f, ensure_ascii=False, indent=2)

        # 세특
        all_saeteuk = []
        for doc in documents:
            for s in doc.saeteuk_examples:
                all_saeteuk.append(s.model_dump())
        with open(output_dir / "saeteuk.json", "w", encoding="utf-8") as f:
            json.dump(all_saeteuk, f, ensure_ascii=False, indent=2)

        # 통합 문서
        all_docs = [doc.model_dump() for doc in documents]
        with open(output_dir / "rag_documents.json", "w", encoding="utf-8") as f:
            json.dump(all_docs, f, ensure_ascii=False, indent=2)

        print(f"\n[저장 완료]")
        print(f"  - students.json: {len(profiles)}개 프로필")
        print(f"  - research.json: {len(all_research)}개 탐구활동")
        print(f"  - saeteuk.json: {len(all_saeteuk)}개 세특")
        print(f"  - rag_documents.json: 통합 문서")
