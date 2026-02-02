"""RAG 시스템 CLI"""

import typer
from pathlib import Path

from .converter import DataConverter

app = typer.Typer(help="RAG 기반 생기부 로드맵 시스템")


@app.command()
def convert(
    input_dir: Path = typer.Option(
        Path("output"),
        "--input", "-i",
        help="입력 디렉토리 (파싱된 JSON 파일들)",
    ),
    output_dir: Path = typer.Option(
        Path("data/metadata"),
        "--output", "-o",
        help="출력 디렉토리 (RAG용 데이터)",
    ),
):
    """기존 파싱 데이터를 RAG 스키마로 변환"""
    print(f"\n[RAG 데이터 변환]")
    print(f"  입력: {input_dir}")
    print(f"  출력: {output_dir}\n")

    converter = DataConverter()
    documents = converter.convert_directory(input_dir, output_dir)

    print(f"\n[완료] {len(documents)}개 문서 변환됨")


@app.command()
def show(
    data_dir: Path = typer.Option(
        Path("data/metadata"),
        "--data", "-d",
        help="RAG 데이터 디렉토리",
    ),
):
    """변환된 데이터 요약 출력"""
    import json

    students_path = data_dir / "students.json"
    if not students_path.exists():
        print("[오류] 변환된 데이터가 없습니다. 먼저 'convert' 명령을 실행하세요.")
        raise typer.Exit(1)

    with open(students_path, "r", encoding="utf-8") as f:
        students = json.load(f)

    print(f"\n[RAG 데이터 요약]")
    print(f"  총 학생 수: {len(students)}명\n")

    for i, s in enumerate(students, 1):
        print(f"  {i}. {s.get('final_university', '미상')} {s.get('final_department', '')}")
        print(f"     - 내신: {s.get('nesin_average', '?')}등급 ({s.get('nesin_range', '?')})")
        print(f"     - 계열: {s.get('major_field', '?')}")
        print(f"     - 학교: {s.get('school_type', '?')} ({s.get('school_region', '?')})")
        print()


@app.command()
def index(
    data_dir: Path = typer.Option(
        Path("data/metadata"),
        "--data", "-d",
        help="RAG 메타데이터 디렉토리",
    ),
    db_dir: Path = typer.Option(
        Path("data/vectordb"),
        "--db",
        help="벡터 DB 저장 경로",
    ),
    api_key: str = typer.Option(
        None,
        "--api-key",
        envvar="OPENAI_API_KEY",
        help="OpenAI API 키",
    ),
):
    """벡터 임베딩 생성 및 인덱싱"""
    from .indexer import RAGIndexer

    print(f"\n[벡터 인덱싱]")
    print(f"  데이터: {data_dir}")
    print(f"  벡터DB: {db_dir}")

    indexer = RAGIndexer(api_key=api_key, db_path=str(db_dir))
    indexer.index_from_metadata(data_dir)


@app.command()
def search(
    nesin_range: str = typer.Option(
        ...,
        "--nesin", "-n",
        help="내신 등급대 (예: 1등급대, 2등급대, 3등급대)",
    ),
    school_type: str = typer.Option(
        "일반고",
        "--school", "-s",
        help="학교 유형 (일반고, 자사고, 특목고, 자공고)",
    ),
    major_field: str = typer.Option(
        ...,
        "--major", "-m",
        help="희망 계열 (경영/경제, 인문, 사회, 어문, 교육)",
    ),
    data_dir: Path = typer.Option(
        Path("data/metadata"),
        "--data", "-d",
        help="RAG 메타데이터 디렉토리",
    ),
    top_k: int = typer.Option(
        3,
        "--top", "-k",
        help="검색할 유사 합격자 수",
    ),
):
    """유사 합격자 검색 및 로드맵 제시"""
    from .searcher import RAGSearcher

    searcher = RAGSearcher(metadata_dir=str(data_dir))
    searcher.search_and_print(
        nesin_range=nesin_range,
        school_type=school_type,
        major_field=major_field,
        top_k=top_k
    )


@app.command()
def interactive(
    data_dir: Path = typer.Option(
        Path("data/metadata"),
        "--data", "-d",
        help="RAG 메타데이터 디렉토리",
    ),
):
    """인터랙티브 검색 모드"""
    from .searcher import RAGSearcher

    print("\n" + "="*60)
    print("  📚 RAG 기반 생기부 로드맵 검색 시스템")
    print("="*60)

    searcher = RAGSearcher(metadata_dir=str(data_dir))

    # 사용 가능한 옵션 표시
    print("\n[등급대 옵션] 1등급대, 2등급대, 3등급대, 4등급대")
    print("[학교유형 옵션] 일반고, 자사고, 특목고, 자공고")
    print("[희망계열 옵션] 경영/경제, 인문, 사회, 어문, 교육")
    print("\n종료하려면 'q' 입력\n")

    while True:
        try:
            print("-"*40)
            nesin = input("내신 등급대 입력: ").strip()
            if nesin.lower() == 'q':
                break

            school = input("학교 유형 입력 [일반고]: ").strip() or "일반고"
            if school.lower() == 'q':
                break

            major = input("희망 계열 입력: ").strip()
            if major.lower() == 'q':
                break

            top_k = input("검색 수 [2]: ").strip() or "2"

            searcher.search_and_print(
                nesin_range=nesin,
                school_type=school,
                major_field=major,
                top_k=int(top_k)
            )
            print()

        except KeyboardInterrupt:
            print("\n\n종료합니다.")
            break
        except Exception as e:
            print(f"\n오류: {e}\n")


if __name__ == "__main__":
    app()
