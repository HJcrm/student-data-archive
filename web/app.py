"""FastAPI 웹 애플리케이션"""

import sys
from pathlib import Path

# 프로젝트 루트를 path에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional

from rag.report_generator import ReportGenerator
from rag.searcher import RAGSearcher

app = FastAPI(title="생기부 로드맵 RAG 시스템")

# 템플릿 설정
templates_dir = Path(__file__).parent / "templates"
templates_dir.mkdir(exist_ok=True)
templates = Jinja2Templates(directory=str(templates_dir))

# 정적 파일
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# RAG 컴포넌트
metadata_dir = Path(__file__).parent.parent / "data" / "metadata"


def get_report_generator(enable_formatting: bool = True) -> ReportGenerator:
    """ReportGenerator 인스턴스 생성"""
    return ReportGenerator(
        metadata_dir=str(metadata_dir),
        enable_formatting=enable_formatting
    )


class SearchRequest(BaseModel):
    nesin_range: str
    school_type: str = "일반고"
    major_field: str
    top_k: int = 3
    enable_formatting: bool = True  # 텍스트 띄어쓰기 교정 활성화


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """메인 페이지"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/search")
async def search(req: SearchRequest):
    """RAG 검색 API"""
    try:
        generator = get_report_generator(enable_formatting=req.enable_formatting)
        report = generator.generate(
            nesin_range=req.nesin_range,
            school_type=req.school_type,
            major_field=req.major_field,
            top_k=req.top_k
        )

        # 결과를 JSON으로 변환
        result = {
            "success": True,
            "query": report.query_info,
            "insights": report.key_insights,
            "recommended_subjects": report.recommended_subjects,
            "similar_students": [
                {
                    "university": s.university,
                    "department": s.department,
                    "nesin_average": s.nesin_average,
                    "match_score": s.match_score,
                }
                for s in report.similar_students
            ],
            "roadmap": report.roadmap_by_term,
            "generated_at": report.generated_at
        }

        return JSONResponse(result)

    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.post("/api/report/html")
async def get_report_html(req: SearchRequest):
    """HTML 레포트 생성"""
    try:
        generator = get_report_generator(enable_formatting=req.enable_formatting)
        report = generator.generate(
            nesin_range=req.nesin_range,
            school_type=req.school_type,
            major_field=req.major_field,
            top_k=req.top_k
        )

        html_content = generator.to_html(report)
        return JSONResponse({"success": True, "html": html_content})

    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.post("/api/report/markdown")
async def get_report_markdown(req: SearchRequest):
    """마크다운 레포트 생성"""
    try:
        generator = get_report_generator(enable_formatting=req.enable_formatting)
        report = generator.generate(
            nesin_range=req.nesin_range,
            school_type=req.school_type,
            major_field=req.major_field,
            top_k=req.top_k
        )

        markdown_content = generator.to_markdown(report)
        return JSONResponse({"success": True, "markdown": markdown_content})

    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.get("/api/stats")
async def get_stats():
    """데이터 통계"""
    try:
        searcher = RAGSearcher(metadata_dir=str(metadata_dir))
        return JSONResponse({
            "success": True,
            "total_students": len(searcher.students),
            "total_research": len(searcher.research),
            "total_saeteuk": len(searcher.saeteuk),
        })
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
