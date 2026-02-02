"""LLM 기반 파서 모듈 (GPT-4o-mini)"""

import json
import os
from typing import Any

from openai import OpenAI

from ..models.schema import (
    StudentData,
    GradesSection,
    NesinGrades,
    ExamRow,
    MockExamRow,
    SuneungScores,
    SusiCardSection,
    SusiApplication,
    SchoolSection,
    RoadmapSection,
    ResearchItem,
    SaenggibuSection,
    SaeteukExample,
    Evidence,
)


class LLMParser:
    """GPT-4o-mini 기반 파서"""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY가 필요합니다")
        self.client = OpenAI(api_key=self.api_key)
        self.model = "gpt-4o-mini"
        self.total_tokens = 0

    def parse_all(self, text: str, alias: str, source_file: str) -> StudentData:
        """전체 텍스트 파싱"""
        print("  [LLM] 성적 파싱 중...")
        grades = self._parse_grades(text)

        print("  [LLM] 수시카드 파싱 중...")
        susi_card = self._parse_susi_card(text)

        print("  [LLM] 학교특성 파싱 중...")
        school = self._parse_school(text)

        print("  [LLM] 탐구활동 파싱 중...")
        roadmap = self._parse_roadmap(text)

        print("  [LLM] 세특 파싱 중...")
        saenggibu = self._parse_saenggibu(text)

        print(f"  [LLM] 완료! 총 토큰: {self.total_tokens}")

        return StudentData(
            alias=alias,
            source_file=source_file,
            grades=grades,
            susi_card=susi_card,
            school=school,
            roadmap=roadmap,
            saenggibu=saenggibu,
            parsing_notes=[
                f"LLM 파싱 (GPT-4o-mini)",
                f"총 토큰 사용: {self.total_tokens}",
            ],
        )

    def _call_llm(self, system_prompt: str, user_prompt: str, max_tokens: int = 4096) -> dict:
        """LLM API 호출"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=max_tokens,
        )

        self.total_tokens += response.usage.total_tokens

        content = response.choices[0].message.content
        return json.loads(content)

    def _parse_grades(self, text: str) -> GradesSection:
        """성적 파싱"""
        system_prompt = """당신은 대입 합격 사례 PDF에서 성적 정보를 추출하는 전문가입니다.
주어진 텍스트에서 내신 성적, 모의고사 성적, 수능 성적을 추출하여 JSON으로 반환하세요.

반환 형식:
{
  "nesin": [
    {"term": "1-1", "subject": "국어", "grade": 2},
    {"term": "1-1", "subject": "영어", "grade": 1},
    ...
  ],
  "mock_exams": [
    {"date": "6월", "subject": "국어", "grade": 3, "percentile": 81},
    ...
  ],
  "suneung": {
    "korean": 4,
    "math": 2,
    "english": 2,
    "history": 1,
    "tamgu1": "정치와법",
    "tamgu1_grade": 2,
    "tamgu2": "사회문화",
    "tamgu2_grade": 1
  },
  "grade_type": "내신형" 또는 "수능형" 또는 "균형형"
}

- 등급은 1-9 사이 정수
- 찾을 수 없는 값은 null
- 내신은 주요 과목(국어, 영어, 수학, 사회, 과학)과 평균만 추출"""

        user_prompt = f"다음 텍스트에서 성적 정보를 추출하세요:\n\n{text[:8000]}"

        try:
            result = self._call_llm(system_prompt, user_prompt)
        except Exception as e:
            print(f"    [경고] 성적 파싱 실패: {e}")
            return GradesSection()

        # 변환
        nesin = NesinGrades()
        for row in result.get("nesin", []):
            if row.get("subject") and row.get("grade") is not None:
                grade_val = row["grade"]
                # 정수 등급만 허용 (소수점 평균은 제외)
                if isinstance(grade_val, float) and grade_val != int(grade_val):
                    continue  # 평균값(1.78 등)은 스킵
                nesin.rows.append(ExamRow(
                    term=row.get("term", "미상"),
                    subject=row["subject"],
                    grade=int(grade_val),
                ))

        mock_exams = []
        for row in result.get("mock_exams", []):
            if row.get("subject"):
                mock_exams.append(MockExamRow(
                    date=row.get("date"),
                    subject=row["subject"],
                    grade=row.get("grade"),
                    percentile=row.get("percentile"),
                ))

        suneung = None
        su_data = result.get("suneung")
        if su_data and any(su_data.get(k) for k in ["korean", "math", "english"]):
            suneung = SuneungScores(
                korean=su_data.get("korean"),
                math=su_data.get("math"),
                english=su_data.get("english"),
                history=su_data.get("history"),
                tamgu1=su_data.get("tamgu1"),
                tamgu1_grade=su_data.get("tamgu1_grade"),
                tamgu2=su_data.get("tamgu2"),
                tamgu2_grade=su_data.get("tamgu2_grade"),
            )

        return GradesSection(
            nesin=nesin,
            mock_exams=mock_exams,
            suneung=suneung,
            grade_type=result.get("grade_type"),
        )

    def _parse_susi_card(self, text: str) -> SusiCardSection:
        """수시카드 파싱"""
        system_prompt = """당신은 대입 합격 사례 PDF에서 수시 지원 정보를 추출하는 전문가입니다.
주어진 텍스트에서 수시 지원 내역을 추출하여 JSON으로 반환하세요.

반환 형식:
{
  "applications": [
    {
      "university": "서울대학교",
      "department": "경영학과",
      "admission_type": "학생부종합(일반전형)",
      "result": "불합격(1차탈락)"
    },
    ...
  ],
  "final_choice": "고려대학교"
}

- 대학명, 학과명, 전형명, 결과를 정확히 추출
- 최종 등록/선택한 대학 표시
- "일반고내신" 등 불필요한 텍스트는 제외"""

        # 수시카드 섹션만 추출
        susi_start = text.find("수시카드")
        susi_end = text.find("학교특성") if "학교특성" in text else susi_start + 2000
        susi_text = text[susi_start:susi_end] if susi_start != -1 else text[:3000]

        user_prompt = f"다음 텍스트에서 수시 지원 정보를 추출하세요:\n\n{susi_text}"

        try:
            result = self._call_llm(system_prompt, user_prompt)
        except Exception as e:
            print(f"    [경고] 수시카드 파싱 실패: {e}")
            return SusiCardSection()

        applications = []
        for app in result.get("applications", []):
            if app.get("university") and app.get("department"):
                applications.append(SusiApplication(
                    university=app["university"],
                    department=app["department"],
                    admission_type=app.get("admission_type", "미상"),
                    result=app.get("result", "미상"),
                ))

        return SusiCardSection(
            applications=applications,
            final_choice=result.get("final_choice"),
        )

    def _parse_school(self, text: str) -> SchoolSection:
        """학교특성 파싱"""
        system_prompt = """당신은 대입 합격 사례 PDF에서 학교 정보를 추출하는 전문가입니다.
주어진 텍스트에서 학교 특성을 추출하여 JSON으로 반환하세요.

반환 형식:
{
  "region": "용인시",
  "school_type": "일반고",
  "school_name": "OO고등학교",
  "atmosphere": "상위권 경쟁 치열, 수시 중심",
  "competition_level": "높음",
  "special_programs": ["독서마라톤", "탐구보고서", "멘토링"]
}"""

        school_start = text.find("학교특성")
        school_end = text.find("로드맵") if "로드맵" in text else school_start + 3000
        school_text = text[school_start:school_end] if school_start != -1 else ""

        if not school_text:
            return SchoolSection()

        user_prompt = f"다음 텍스트에서 학교 정보를 추출하세요:\n\n{school_text}"

        try:
            result = self._call_llm(system_prompt, user_prompt)
        except Exception as e:
            print(f"    [경고] 학교특성 파싱 실패: {e}")
            return SchoolSection()

        return SchoolSection(
            region=result.get("region"),
            school_type=result.get("school_type"),
            school_name=result.get("school_name"),
            atmosphere=result.get("atmosphere"),
            competition_level=result.get("competition_level"),
            special_programs=result.get("special_programs", []),
        )

    def _parse_roadmap(self, text: str) -> RoadmapSection:
        """로드맵/탐구활동 파싱"""
        system_prompt = """당신은 대입 합격 사례 PDF에서 탐구활동 정보를 추출하는 전문가입니다.
주어진 텍스트에서 핵심 탐구활동을 추출하여 JSON으로 반환하세요.

반환 형식:
{
  "yearly_strategies": {
    "1학년": "기초 다지기, 진로 탐색",
    "2학년": "심화 탐구, 전공 관련 활동",
    "3학년": "심화 연구, 포트폴리오 완성"
  },
  "top_researches": [
    {
      "term": "3-1",
      "subject": "세계지리",
      "title": "러시아-우크라이나 전쟁이 세계 곡물시장에 미친 영향"
    },
    ...
  ],
  "overall_theme": "경영/경제 분야 심화 탐구"
}

- 핵심 탐구활동 최대 10개 추출
- 학기, 과목, 주제 정확히 기재"""

        user_prompt = f"다음 텍스트에서 탐구활동 정보를 추출하세요:\n\n{text[:10000]}"

        try:
            result = self._call_llm(system_prompt, user_prompt)
        except Exception as e:
            print(f"    [경고] 로드맵 파싱 실패: {e}")
            return RoadmapSection()

        researches = []
        for i, r in enumerate(result.get("top_researches", [])[:10]):
            if r.get("title"):
                researches.append(ResearchItem(
                    id=f"research_{i+1:03d}",
                    term=r.get("term"),
                    subject=r.get("subject"),
                    title=r["title"],
                ))

        return RoadmapSection(
            yearly_strategies=result.get("yearly_strategies", {}),
            top_researches=researches,
            overall_theme=result.get("overall_theme"),
        )

    def _parse_saenggibu(self, text: str) -> SaenggibuSection:
        """세특/합격포인트 파싱 - 각 세특을 개별 추출"""
        import re

        # "탐구활동.*기재" 패턴으로 세특 섹션들 찾기
        pattern = r'탐구활동.*?기재'
        matches = list(re.finditer(pattern, text))

        examples = []
        acceptance_points = []

        if matches:
            # 각 세특 섹션을 개별적으로 처리
            for i, match in enumerate(matches):
                start = match.start()
                # 다음 세특 섹션 또는 텍스트 끝까지
                if i + 1 < len(matches):
                    end = matches[i + 1].start()
                else:
                    end = len(text)

                section_text = text[start:end]

                # 개별 세특 추출
                result = self._extract_single_saeteuk(section_text, i + 1)
                if result:
                    examples.append(result)

            # 합격 포인트는 전체 텍스트에서 추출
            acceptance_points = self._extract_acceptance_points(text)
        else:
            # 패턴 못 찾으면 기존 방식 사용
            examples, acceptance_points = self._parse_saenggibu_fallback(text)

        return SaenggibuSection(
            saeteuk_examples=examples,
            acceptance_points=acceptance_points,
        )

    def _extract_subject_from_text(self, section_text: str) -> str:
        """텍스트에서 과목명 직접 추출 (영역 칼럼에서)"""
        import re

        # "세부능력및특기사항" 또는 "세부능력 및 특기사항" 이후의 과목명 찾기
        pattern = r'세부능력\s*및?\s*특기사항\s*\n?(.+?)(?:\n[가-힣]{2,}에서|[가-힣]{2,}에서|\n\n)'
        match = re.search(pattern, section_text, re.DOTALL)

        if match:
            subject_raw = match.group(1).strip()
            # 줄바꿈으로 분리된 과목명 합치기 (예: "영어\n독해와\n작문" -> "영어독해와작문")
            subject = re.sub(r'\s+', '', subject_raw)
            # 첫 번째 줄만 과목명인 경우 처리
            lines = subject_raw.split('\n')
            if lines:
                # 과목명은 보통 짧음 (20자 이내)
                subject_parts = []
                for line in lines:
                    line = line.strip()
                    if line and len(line) < 15:
                        subject_parts.append(line)
                    else:
                        break
                if subject_parts:
                    return ''.join(subject_parts)

        # 폴백: 간단한 패턴으로 시도
        lines = section_text.split('\n')
        for i, line in enumerate(lines):
            if '세부능력' in line and i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if next_line and len(next_line) < 20:
                    return next_line

        return "미상"

    def _extract_single_saeteuk(self, section_text: str, index: int) -> SaeteukExample | None:
        """개별 세특 추출"""
        # 과목명은 텍스트에서 직접 추출
        subject = self._extract_subject_from_text(section_text)

        system_prompt = """주어진 텍스트에서 세특(세부능력특기사항) 내용만 추출하여 JSON으로 반환하세요.

반환 형식:
{
  "content": "세특 전체 내용 (원문 그대로, 요약 금지)",
  "highlights": ["핵심 키워드1", "핵심 키워드2"]
}

중요:
- content에는 세특 내용 전체를 원문 그대로 복사
- 절대 요약하거나 줄이지 말 것
- "합격포인트" 이전까지의 모든 내용 포함
- 과목명은 제외하고 내용만 추출"""

        user_prompt = f"다음 텍스트에서 세특 내용을 JSON으로 추출하세요 (원문 전체를 content에 포함):\n\n{section_text[:4000]}"

        try:
            result = self._call_llm(system_prompt, user_prompt, max_tokens=2048)
            if result.get("content"):
                return SaeteukExample(
                    id=f"saeteuk_{index:03d}",
                    subject=subject,  # 텍스트에서 직접 추출한 과목명 사용
                    content=result["content"],
                    highlights=result.get("highlights", []),
                )
        except Exception as e:
            print(f"    [경고] 세특 {index} 추출 실패: {e}")

        return None

    def _extract_acceptance_points(self, text: str) -> list[str]:
        """합격 포인트 추출"""
        # 합격포인트 섹션 찾기
        pos = text.find("합격포인트")
        if pos == -1:
            pos = text.find("합격 포인트")
        if pos == -1:
            return []

        section_text = text[pos:pos+2000]

        system_prompt = """주어진 텍스트에서 합격 포인트를 추출하여 JSON으로 반환하세요.

반환 형식:
{
  "acceptance_points": ["포인트1", "포인트2", ...]
}"""

        user_prompt = f"다음 텍스트에서 합격 포인트를 JSON으로 추출하세요:\n\n{section_text}"

        try:
            result = self._call_llm(system_prompt, user_prompt, max_tokens=1024)
            return result.get("acceptance_points", [])
        except:
            return []

    def _parse_saenggibu_fallback(self, text: str) -> tuple[list, list]:
        """폴백: 기존 방식으로 세특 파싱"""
        system_prompt = """세특과 합격 포인트를 추출하여 JSON으로 반환하세요.

반환 형식:
{
  "saeteuk_examples": [{"subject": "과목명", "content": "전체 내용", "highlights": []}],
  "acceptance_points": ["포인트1", ...]
}"""

        saeteuk_text = text[len(text)//3:]
        if len(saeteuk_text) > 10000:
            saeteuk_text = saeteuk_text[:10000]

        try:
            result = self._call_llm(system_prompt, f"JSON으로 추출:\n{saeteuk_text}", max_tokens=4096)
            examples = []
            for i, ex in enumerate(result.get("saeteuk_examples", [])):
                if ex.get("subject") and ex.get("content"):
                    examples.append(SaeteukExample(
                        id=f"saeteuk_{i+1:03d}",
                        subject=ex["subject"],
                        content=ex["content"],
                        highlights=ex.get("highlights", []),
                    ))
            return examples, result.get("acceptance_points", [])
        except:
            return [], []
