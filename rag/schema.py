"""RAG 시스템용 데이터 스키마"""

from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field
from enum import Enum


class GradeType(str, Enum):
    """성적 유형"""
    NESIN = "내신형"
    SUNEUNG = "수능형"
    BALANCED = "균형형"


class GradeRange(str, Enum):
    """등급대"""
    GRADE_1 = "1등급대"
    GRADE_2 = "2등급대"
    GRADE_3 = "3등급대"
    GRADE_4 = "4등급대"
    GRADE_5_PLUS = "5등급이상"


class UniversityTier(str, Enum):
    """대학 티어"""
    SKY = "SKY"
    TOP_SEOUL = "인서울상위"
    MID_SEOUL = "인서울"
    LOCAL_TOP = "지방거점"
    OTHER = "기타"


class MajorField(str, Enum):
    """계열"""
    BUSINESS_ECON = "경영/경제"
    HUMANITIES = "인문"
    SOCIAL = "사회"
    NATURAL = "자연"
    ENGINEERING = "공학"
    MEDICAL = "의약"
    ARTS = "예체능"
    EDUCATION = "교육"
    OTHER = "기타"


class SchoolType(str, Enum):
    """학교 유형"""
    GENERAL = "일반고"
    AUTONOMOUS_PRIVATE = "자사고"
    SPECIALIZED = "특목고"
    GIFTED = "영재고"
    OTHER = "기타"


class CompetitionLevel(str, Enum):
    """경쟁 수준"""
    HIGH = "높음"
    MEDIUM = "보통"
    LOW = "낮음"


# ============================================================
# 핵심 데이터 모델
# ============================================================

class StudentProfile(BaseModel):
    """학생 프로필 (검색/필터링용 라벨)"""

    id: str = Field(..., description="고유 식별자")
    source_file: str = Field(..., description="원본 PDF 파일명")

    # 성적 지표
    grade_type: Optional[GradeType] = Field(None, description="성적 유형")
    nesin_average: Optional[float] = Field(None, description="내신 평균 등급")
    nesin_range: Optional[GradeRange] = Field(None, description="내신 등급대")

    # 진학 정보
    final_university: Optional[str] = Field(None, description="최종 진학 대학")
    final_department: Optional[str] = Field(None, description="최종 진학 학과")
    university_tier: Optional[UniversityTier] = Field(None, description="대학 티어")

    # 계열 정보
    major_field: Optional[MajorField] = Field(None, description="계열")

    # 학교 특성
    school_name: Optional[str] = Field(None, description="학교명")
    school_type: Optional[SchoolType] = Field(None, description="학교 유형")
    school_region: Optional[str] = Field(None, description="학교 지역")
    competition_level: Optional[CompetitionLevel] = Field(None, description="경쟁 수준")

    # 추가 정보
    overall_theme: Optional[str] = Field(None, description="전체 테마")

    class Config:
        use_enum_values = True


class ResearchActivity(BaseModel):
    """탐구활동 (RAG 검색 대상)"""

    id: str = Field(..., description="고유 식별자")
    student_id: str = Field(..., description="학생 프로필 ID")

    # 시기 정보
    term: str = Field(..., description="학기 (1-1, 1-2, 2-1, 2-2, 3-1)")
    grade: int = Field(..., description="학년 (1, 2, 3)")
    semester: int = Field(..., description="학기 (1, 2)")

    # 활동 정보
    subject: str = Field(..., description="과목명")
    title: str = Field(..., description="탐구 주제")
    description: Optional[str] = Field(None, description="상세 설명")

    # 분류
    keywords: list[str] = Field(default_factory=list, description="키워드")

    # 연결 정보
    linked_saeteuk_id: Optional[str] = Field(None, description="매칭된 세특 ID")

    # RAG용 텍스트 (임베딩 생성용)
    rag_text: Optional[str] = Field(None, description="RAG 검색용 통합 텍스트")

    class Config:
        use_enum_values = True


class SaeteukExample(BaseModel):
    """세특 예시 (RAG 검색 대상)"""

    id: str = Field(..., description="고유 식별자")
    student_id: str = Field(..., description="학생 프로필 ID")

    # 과목 정보
    subject: str = Field(..., description="과목명")
    term: Optional[str] = Field(None, description="학기 (추정)")

    # 내용
    content: str = Field(..., description="세특 전체 내용")
    highlights: list[str] = Field(default_factory=list, description="핵심 포인트")

    # 연결 정보
    linked_research_ids: list[str] = Field(default_factory=list, description="매칭된 탐구활동 ID")

    # RAG용 텍스트
    rag_text: Optional[str] = Field(None, description="RAG 검색용 통합 텍스트")

    class Config:
        use_enum_values = True


class RAGDocument(BaseModel):
    """RAG 통합 문서 (하나의 합격 사례)"""

    profile: StudentProfile
    research_activities: list[ResearchActivity] = Field(default_factory=list)
    saeteuk_examples: list[SaeteukExample] = Field(default_factory=list)

    # 메타데이터
    created_at: Optional[str] = Field(None, description="생성 시간")

    def get_filter_metadata(self) -> dict:
        """ChromaDB 필터링용 메타데이터 반환"""
        return {
            "student_id": self.profile.id,
            "grade_type": self.profile.grade_type,
            "nesin_range": self.profile.nesin_range,
            "university_tier": self.profile.university_tier,
            "major_field": self.profile.major_field,
            "school_type": self.profile.school_type,
            "school_region": self.profile.school_region,
        }


# ============================================================
# 검색 결과 모델
# ============================================================

class SearchResult(BaseModel):
    """검색 결과"""

    document_id: str
    score: float
    document_type: str  # "research" | "saeteuk"
    content: str
    metadata: dict

    # 원본 데이터 참조
    student_profile: Optional[StudentProfile] = None
    research: Optional[ResearchActivity] = None
    saeteuk: Optional[SaeteukExample] = None


class RoadmapRequest(BaseModel):
    """로드맵 생성 요청"""

    current_grade: int = Field(..., description="현재 학년")
    target_grade_range: GradeRange = Field(..., description="목표 등급대")
    major_field: MajorField = Field(..., description="희망 계열")
    school_type: SchoolType = Field(..., description="학교 유형")
    interests: list[str] = Field(default_factory=list, description="관심 분야")

    class Config:
        use_enum_values = True


class RoadmapResponse(BaseModel):
    """로드맵 생성 응답"""

    roadmap: dict  # 학년별 로드맵
    reference_cases: list[dict]  # 참고 합격 사례
    recommended_activities: list[dict]  # 추천 탐구활동
