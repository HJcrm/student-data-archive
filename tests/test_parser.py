"""파서 테스트"""

import pytest
from src.models.schema import StudentData, ExamRow, SusiApplication
from src.parser.section_detector import SectionDetector, SectionType
from src.parser.grades_parser import GradesParser
from src.parser.susi_parser import SusiParser
from src.parser.school_parser import SchoolParser
from src.parser.roadmap_parser import RoadmapParser
from src.parser.saenggibu_parser import SaenggibuParser
from src.linker.research_saeteuk_linker import ResearchSaeteukLinker
from src.reporter.markdown_generator import MarkdownGenerator


class TestSectionDetector:
    """섹션 탐지기 테스트"""

    def test_detect_grades_section(self):
        text = "[p1] 학생 소개\n[p2] 성적 유형: 내신형\n내신 성적 분석"
        detector = SectionDetector(text)
        sections = detector.detect_sections()

        grades_sections = [s for s in sections if s.section_type == SectionType.GRADES]
        assert len(grades_sections) >= 1

    def test_detect_susi_section(self):
        text = "[p1] 학생 소개\n[p2] 수시카드\n지원 결과 분석"
        detector = SectionDetector(text)
        sections = detector.detect_sections()

        susi_sections = [s for s in sections if s.section_type == SectionType.SUSI_CARD]
        assert len(susi_sections) >= 1

    def test_page_number_extraction(self):
        text = "[p1] 첫 페이지\n[p2] 두 번째 페이지\n[p3] 세 번째 페이지"
        detector = SectionDetector(text)

        assert detector._get_page_at_position(0) == 1
        assert detector._get_page_at_position(20) == 2


class TestGradesParser:
    """성적 파서 테스트"""

    def test_detect_grade_type(self):
        parser = GradesParser()

        assert parser._detect_grade_type("내신형 학생") == "내신형"
        assert parser._detect_grade_type("수능 중심") == "수능형"
        assert parser._detect_grade_type("내신과 수능 균형") == "균형형"

    def test_parse_nesin_from_text(self):
        parser = GradesParser()
        text = "1학년 1학기 국어 2등급, 수학 1등급"

        rows = parser._parse_nesin_from_text(text)

        assert len(rows) >= 1
        # 국어 또는 수학이 파싱되었는지 확인
        subjects = [r.subject for r in rows]
        assert any(s in ["국어", "수학"] for s in subjects)


class TestSusiParser:
    """수시카드 파서 테스트"""

    def test_parse_from_text(self):
        parser = SusiParser()
        text = "서울대학교 경영학과 학생부종합 합격"

        apps = parser._parse_from_text(text)

        assert len(apps) >= 1
        assert apps[0].university == "서울대학교"
        assert apps[0].result == "합격"

    def test_normalize_result(self):
        parser = SusiParser()

        assert parser._normalize_result("최초합격") == "합격"
        assert parser._normalize_result("불합격") == "불합격"
        assert parser._normalize_result("예비 3번") == "예비"


class TestSchoolParser:
    """학교 파서 테스트"""

    def test_extract_region(self):
        parser = SchoolParser()

        assert parser._extract_region("서울 지역 소재") == "서울"
        assert parser._extract_region("경기도 성남시") == "경기"

    def test_extract_school_type(self):
        parser = SchoolParser()

        assert parser._extract_school_type("일반고 출신") == "일반고"
        assert parser._extract_school_type("과학고 졸업") == "특목고"


class TestRoadmapParser:
    """로드맵 파서 테스트"""

    def test_extract_term(self):
        parser = RoadmapParser()

        assert parser._extract_term("1학년 2학기 탐구") == "1-2"
        assert parser._extract_term("2-1 프로젝트") == "2-1"

    def test_extract_keywords(self):
        parser = RoadmapParser()

        keywords = parser._extract_keywords("주제 (인공지능, 딥러닝)")
        assert "인공지능" in keywords or "딥러닝" in keywords


class TestSaenggibuParser:
    """세특 파서 테스트"""

    def test_extract_highlights(self):
        parser = SaenggibuParser()

        highlights = parser._extract_highlights("실험을 통한 **탐구 활동** 수행")
        assert len(highlights) >= 1


class TestResearchSaeteukLinker:
    """연결기 테스트"""

    def test_term_match(self):
        linker = ResearchSaeteukLinker()

        assert linker._check_term_match("1-1", "1-1") == "exact"
        assert linker._check_term_match("1-1", "1-2") == "adjacent"
        assert linker._check_term_match("1-1", "3-1") == "none"

    def test_subject_match(self):
        linker = ResearchSaeteukLinker()

        assert linker._check_subject_match("화학", "화학") == "exact"
        assert linker._check_subject_match("화학I", "화학II") == "similar"
        assert linker._check_subject_match("국어", "수학") == "none"


class TestMarkdownGenerator:
    """마크다운 생성기 테스트"""

    def test_generate_header(self):
        generator = MarkdownGenerator()
        data = StudentData(
            alias="테스트학생",
            source_file="test.pdf",
        )

        header = generator._generate_header(data)

        assert "테스트학생" in header
        assert "test.pdf" in header


class TestStudentDataModel:
    """StudentData 모델 테스트"""

    def test_create_minimal(self):
        data = StudentData(
            alias="학생A",
            source_file="input.pdf",
        )

        assert data.alias == "학생A"
        assert data.grades is not None
        assert data.susi_card is not None

    def test_exam_row_validation(self):
        row = ExamRow(
            term="1-1",
            subject="국어",
            grade=2,
        )

        assert row.grade == 2

    def test_susi_application(self):
        app = SusiApplication(
            university="서울대학교",
            department="경영학과",
            admission_type="학생부종합",
            result="합격",
        )

        assert app.university == "서울대학교"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
