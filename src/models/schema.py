"""Pydantic 모델 정의 - JSON 스키마"""

from typing import Optional
from pydantic import BaseModel, Field


class Evidence(BaseModel):
    """근거 정보 (페이지 번호 등)"""
    page: Optional[int] = None
    raw_text: Optional[str] = None


class ExamRow(BaseModel):
    """내신 성적 행"""
    term: str = Field(..., description="학기 (예: '1-1', '2-2')")
    subject: str = Field(..., description="과목명")
    grade: Optional[int] = Field(None, ge=1, le=9, description="등급 (1-9)")
    raw_score: Optional[float] = Field(None, description="원점수")
    average: Optional[float] = Field(None, description="평균")
    std_dev: Optional[float] = Field(None, description="표준편차")
    evidence: Optional[Evidence] = None


class NesinGrades(BaseModel):
    """내신 성적 전체"""
    rows: list[ExamRow] = Field(default_factory=list)
    overall_average: Optional[float] = Field(None, description="전체 평균 등급")
    subject_averages: dict[str, float] = Field(default_factory=dict, description="과목별 평균 등급")


class MockExamRow(BaseModel):
    """모의고사 성적 행"""
    date: Optional[str] = Field(None, description="시험 날짜 (예: '2023년 6월')")
    grade_level: Optional[int] = Field(None, ge=1, le=3, description="학년")
    subject: str = Field(..., description="과목명")
    grade: Optional[int] = Field(None, ge=1, le=9, description="등급")
    percentile: Optional[float] = Field(None, description="백분위")
    standard_score: Optional[int] = Field(None, description="표준점수")
    evidence: Optional[Evidence] = None


class SuneungScores(BaseModel):
    """수능 성적"""
    korean: Optional[int] = Field(None, description="국어 등급")
    math: Optional[int] = Field(None, description="수학 등급")
    english: Optional[int] = Field(None, description="영어 등급")
    history: Optional[int] = Field(None, description="한국사 등급")
    tamgu1: Optional[str] = Field(None, description="탐구1 과목")
    tamgu1_grade: Optional[int] = Field(None, description="탐구1 등급")
    tamgu2: Optional[str] = Field(None, description="탐구2 과목")
    tamgu2_grade: Optional[int] = Field(None, description="탐구2 등급")
    second_language: Optional[str] = Field(None, description="제2외국어/한문")
    second_language_grade: Optional[int] = Field(None, description="제2외국어 등급")
    evidence: Optional[Evidence] = None


class GradesSection(BaseModel):
    """성적 섹션 전체"""
    nesin: NesinGrades = Field(default_factory=NesinGrades)
    mock_exams: list[MockExamRow] = Field(default_factory=list)
    suneung: Optional[SuneungScores] = None
    grade_type: Optional[str] = Field(None, description="성적 유형 (내신형/수능형/균형형)")


class SusiApplication(BaseModel):
    """수시 지원 내역"""
    university: str = Field(..., description="대학명")
    department: str = Field(..., description="학과명")
    admission_type: str = Field(..., description="전형명")
    result: str = Field(..., description="결과 (합격/불합격/예비)")
    notes: Optional[str] = Field(None, description="비고")
    evidence: Optional[Evidence] = None


class SusiCardSection(BaseModel):
    """수시카드 섹션"""
    applications: list[SusiApplication] = Field(default_factory=list)
    final_choice: Optional[str] = Field(None, description="최종 선택 대학")
    strategy_notes: Optional[str] = Field(None, description="전략 메모")


class SchoolSection(BaseModel):
    """학교 특성 섹션"""
    region: Optional[str] = Field(None, description="지역")
    school_type: Optional[str] = Field(None, description="학교 유형 (일반고/특목고/자사고 등)")
    school_name: Optional[str] = Field(None, description="학교명")
    atmosphere: Optional[str] = Field(None, description="학교 분위기")
    competition_level: Optional[str] = Field(None, description="경쟁 수준")
    special_programs: list[str] = Field(default_factory=list, description="특별 프로그램")
    evidence: Optional[Evidence] = None


class ResearchItem(BaseModel):
    """탐구 활동 항목"""
    id: Optional[str] = Field(None, description="탐구 ID (연결용)")
    term: Optional[str] = Field(None, description="학기")
    subject: Optional[str] = Field(None, description="관련 과목")
    title: str = Field(..., description="탐구 주제")
    description: Optional[str] = Field(None, description="탐구 내용 설명")
    keywords: list[str] = Field(default_factory=list, description="핵심 키워드")
    evidence: Optional[Evidence] = None


class RoadmapSection(BaseModel):
    """생기부 로드맵 섹션"""
    yearly_strategies: dict[str, str] = Field(default_factory=dict, description="학년별 전략")
    top_researches: list[ResearchItem] = Field(default_factory=list, description="Top 10 핵심 탐구")
    overall_theme: Optional[str] = Field(None, description="전체 테마/방향성")
    evidence: Optional[Evidence] = None


class SaeteukExample(BaseModel):
    """세특 예시"""
    id: Optional[str] = Field(None, description="세특 ID (연결용)")
    term: Optional[str] = Field(None, description="학기")
    subject: str = Field(..., description="과목명")
    content: str = Field(..., description="세특 내용")
    highlights: list[str] = Field(default_factory=list, description="강조 포인트")
    evidence: Optional[Evidence] = None


class LinkedResearch(BaseModel):
    """탐구-세특 연결 정보"""
    research_id: str
    saeteuk_id: str
    match_score: float = Field(..., ge=0, le=1, description="매칭 점수")
    match_reason: str = Field(..., description="매칭 근거")


class SaenggibuSection(BaseModel):
    """세특/생기부 섹션"""
    saeteuk_examples: list[SaeteukExample] = Field(default_factory=list)
    acceptance_points: list[str] = Field(default_factory=list, description="합격 포인트")
    linked_researches: list[LinkedResearch] = Field(default_factory=list)
    unlinked_researches: list[str] = Field(default_factory=list, description="연결 실패한 탐구 ID")
    unlinked_saeteuks: list[str] = Field(default_factory=list, description="연결 실패한 세특 ID")


class StudentData(BaseModel):
    """학생 전체 데이터 (최종 출력 스키마)"""
    alias: str = Field(..., description="학생 별칭")
    source_file: str = Field(..., description="원본 PDF 파일명")
    grades: GradesSection = Field(default_factory=GradesSection)
    susi_card: SusiCardSection = Field(default_factory=SusiCardSection)
    school: SchoolSection = Field(default_factory=SchoolSection)
    roadmap: RoadmapSection = Field(default_factory=RoadmapSection)
    saenggibu: SaenggibuSection = Field(default_factory=SaenggibuSection)
    parsing_notes: list[str] = Field(default_factory=list, description="파싱 과정 메모")
