"""대입 합격자 사례 PDF 파서 - CLI 진입점"""

import json
import os
from pathlib import Path

import typer

from config import OUTPUT_DIR
from src.extractor.pdf_reader import PDFReader
from src.extractor.table_parser import TableParser
from src.parser.section_detector import SectionDetector, SectionType
from src.parser.grades_parser import GradesParser
from src.parser.susi_parser import SusiParser
from src.parser.school_parser import SchoolParser
from src.parser.roadmap_parser import RoadmapParser
from src.parser.saenggibu_parser import SaenggibuParser
from src.linker.research_saeteuk_linker import ResearchSaeteukLinker
from src.reporter.markdown_generator import MarkdownGenerator
from src.models.schema import StudentData

app = typer.Typer(help="대입 합격자 사례 PDF 파서")


def parse_pdf_regex(full_text: str, pdf_path: Path) -> StudentData:
    """정규식 기반 파싱"""
    table_parser = TableParser(pdf_path)

    grades = GradesParser(table_parser).parse(full_text)
    susi_card = SusiParser().parse(full_text)
    school = SchoolParser().parse(full_text)
    roadmap = RoadmapParser().parse(full_text)
    saenggibu = SaenggibuParser().parse(full_text)

    # 연결
    linker = ResearchSaeteukLinker()
    linked, unlinked_r, unlinked_s = linker.link(
        roadmap.top_researches,
        saenggibu.saeteuk_examples
    )
    saenggibu.linked_researches = linked
    saenggibu.unlinked_researches = unlinked_r
    saenggibu.unlinked_saeteuks = unlinked_s

    return StudentData(
        alias=pdf_path.stem,
        source_file=pdf_path.name,
        grades=grades,
        susi_card=susi_card,
        school=school,
        roadmap=roadmap,
        saenggibu=saenggibu,
        parsing_notes=["정규식 기반 파싱"],
    )


def parse_pdf_llm(full_text: str, pdf_path: Path, api_key: str) -> StudentData:
    """LLM 기반 파싱"""
    from src.parser.llm_parser import LLMParser

    parser = LLMParser(api_key=api_key)
    data = parser.parse_all(
        text=full_text,
        alias=pdf_path.stem,
        source_file=pdf_path.name,
    )

    # 연결
    linker = ResearchSaeteukLinker()
    linked, unlinked_r, unlinked_s = linker.link(
        data.roadmap.top_researches,
        data.saenggibu.saeteuk_examples
    )
    data.saenggibu.linked_researches = linked
    data.saenggibu.unlinked_researches = unlinked_r
    data.saenggibu.unlinked_saeteuks = unlinked_s

    return data


def save_outputs(data: StudentData, output_dir: Path) -> tuple[Path, Path]:
    """JSON과 마크다운 파일 저장"""
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / f"{data.alias}_data.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data.model_dump(), f, ensure_ascii=False, indent=2)

    md_generator = MarkdownGenerator()
    md_content = md_generator.generate(data)
    md_path = output_dir / f"{data.alias}_report.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    return json_path, md_path


@app.command()
def main(
    pdf_path: Path = typer.Argument(
        ...,
        help="입력 PDF 파일 경로",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    output_dir: Path = typer.Option(
        OUTPUT_DIR,
        "--output-dir", "-o",
        help="출력 디렉토리",
    ),
    start_page: int = typer.Option(
        None,
        "--start", "-s",
        help="시작 페이지 (1-indexed)",
    ),
    end_page: int = typer.Option(
        None,
        "--end", "-e",
        help="끝 페이지 (1-indexed, inclusive)",
    ),
    use_llm: bool = typer.Option(
        False,
        "--llm",
        help="GPT-4o-mini LLM 파서 사용",
    ),
    api_key: str = typer.Option(
        None,
        "--api-key",
        envvar="OPENAI_API_KEY",
        help="OpenAI API 키",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose", "-v",
        help="상세 출력",
    ),
):
    """대입 합격자 사례 PDF를 파싱하여 JSON과 마크다운 레포트를 생성합니다."""

    print(f"\n[PDF 파싱 시작] {pdf_path.name}")
    if use_llm:
        print("  모드: LLM (GPT-4o-mini)")
    else:
        print("  모드: 정규식 기반")

    if start_page and end_page:
        print(f"  범위: {start_page}-{end_page} 페이지")

    print()

    try:
        # PDF 텍스트 추출
        print("  텍스트 추출 중...")
        with PDFReader(pdf_path) as reader:
            if start_page and end_page:
                full_text = reader.extract_page_range(start_page, end_page)
            else:
                full_text = reader.extract_with_markers()

        # 파싱
        print("  파싱 중...")
        if use_llm:
            if not api_key:
                print("\n[오류] --llm 옵션 사용시 OPENAI_API_KEY가 필요합니다")
                print("  환경변수로 설정하거나 --api-key 옵션을 사용하세요")
                raise typer.Exit(1)
            data = parse_pdf_llm(full_text, pdf_path, api_key)
        else:
            data = parse_pdf_regex(full_text, pdf_path)

        # 저장
        print("  파일 저장 중...")
        json_path, md_path = save_outputs(data, output_dir)

        # 결과 출력
        print("\n[완료]")
        print(f"  JSON: {json_path}")
        print(f"  Report: {md_path}")

        if verbose:
            print("\n[파싱 통계]")
            print(f"  - 내신 기록: {len(data.grades.nesin.rows)}개")
            print(f"  - 모의고사: {len(data.grades.mock_exams)}개")
            print(f"  - 수능: {'있음' if data.grades.suneung else '없음'}")
            print(f"  - 수시 지원: {len(data.susi_card.applications)}개")
            print(f"  - 탐구 활동: {len(data.roadmap.top_researches)}개")
            print(f"  - 세특 예시: {len(data.saenggibu.saeteuk_examples)}개")
            print(f"  - 합격 포인트: {len(data.saenggibu.acceptance_points)}개")

            if data.parsing_notes:
                print("\n[파싱 메모]")
                for note in data.parsing_notes:
                    print(f"  - {note}")

        print()

    except FileNotFoundError as e:
        print(f"\n[오류] {e}\n")
        raise typer.Exit(1)
    except Exception as e:
        print(f"\n[파싱 오류] {e}\n")
        if verbose:
            import traceback
            traceback.print_exc()
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
