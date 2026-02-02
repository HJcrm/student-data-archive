"""Vercel Serverless Function - FastAPI"""

import sys
import os
from pathlib import Path

# 프로젝트 루트 추가
root = Path(__file__).parent.parent
sys.path.insert(0, str(root))

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from mangum import Mangum
import json

app = FastAPI(title="생기부 로드맵 RAG API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 데이터 로드
DATA_DIR = root / "data" / "metadata"


def load_json(filename):
    filepath = DATA_DIR / filename
    if filepath.exists():
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


class SearchRequest(BaseModel):
    nesin_range: str
    school_type: str = "일반고"
    major_field: str
    top_k: int = 3
    enable_formatting: bool = False


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/stats")
async def get_stats():
    try:
        students = load_json("students.json")
        research = load_json("research.json")
        saeteuk = load_json("saeteuk.json")

        return JSONResponse({
            "success": True,
            "total_students": len(students),
            "total_research": len(research),
            "total_saeteuk": len(saeteuk),
        })
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


def search_students(nesin_range: str, school_type: str, major_field: str, top_k: int):
    """학생 검색 로직"""
    students = load_json("students.json")
    research_list = load_json("research.json")
    saeteuk_list = load_json("saeteuk.json")

    # 내신 범위 파싱
    nesin_min, nesin_max = 0, 10
    if "1등급" in nesin_range:
        nesin_min, nesin_max = 1.0, 1.99
    elif "2등급" in nesin_range:
        nesin_min, nesin_max = 2.0, 2.99
    elif "3등급" in nesin_range:
        nesin_min, nesin_max = 3.0, 3.99
    elif "4등급" in nesin_range:
        nesin_min, nesin_max = 4.0, 4.99

    # 필터링
    filtered = []
    for s in students:
        nesin = s.get("nesin_average") or 0
        if nesin_min <= nesin <= nesin_max:
            score = 50  # 기본 점수

            # 계열 매칭
            dept = (s.get("final_department") or "").lower()
            major = s.get("major_field") or ""
            field = major_field.lower()

            if field in dept or field in major.lower():
                score += 50
            elif any(k in dept for k in field.split("/")):
                score += 40

            filtered.append({**s, "match_score": score})

    # 정렬 및 상위 k개
    filtered.sort(key=lambda x: x.get("match_score", 0), reverse=True)
    results = filtered[:top_k]

    # 각 학생의 탐구활동과 세특 가져오기
    for student in results:
        sid = student.get("id")
        student["research"] = [r for r in research_list if r.get("student_id") == sid][:5]
        student["saeteuk"] = [s for s in saeteuk_list if s.get("student_id") == sid][:3]

    return results


@app.post("/api/search")
async def search(req: SearchRequest):
    """학생 검색 API"""
    try:
        results = search_students(
            req.nesin_range,
            req.school_type,
            req.major_field,
            req.top_k
        )

        return JSONResponse({
            "success": True,
            "query": {
                "nesin_range": req.nesin_range,
                "school_type": req.school_type,
                "major_field": req.major_field,
            },
            "students": results,
            "total_found": len(results),
        })
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.post("/api/report/html")
async def get_report_html(req: SearchRequest):
    """HTML 레포트 생성"""
    try:
        results = search_students(
            req.nesin_range,
            req.school_type,
            req.major_field,
            req.top_k
        )

        # HTML 생성
        html = generate_report_html(req, results)
        return JSONResponse({"success": True, "html": html})

    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.post("/api/report/markdown")
async def get_report_markdown(req: SearchRequest):
    """마크다운 레포트 생성"""
    try:
        results = search_students(
            req.nesin_range,
            req.school_type,
            req.major_field,
            req.top_k
        )

        # 마크다운 생성
        md = generate_report_markdown(req, results)
        return JSONResponse({"success": True, "markdown": md})

    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


def generate_report_html(req: SearchRequest, students: list) -> str:
    """HTML 레포트 생성"""
    html = f"""
    <div class="report">
        <h1>📚 맞춤 생기부 로드맵</h1>
        <p class="generated-at">검색 조건: {req.nesin_range} | {req.school_type} | {req.major_field}</p>

        <h2>🎯 유사 합격 사례 ({len(students)}명)</h2>
        <div class="student-cards">
    """

    for s in students:
        html += f"""
        <div class="student-card">
            <h3>{s.get('final_university', '미상')} {s.get('final_department', '')}</h3>
            <p>내신 {s.get('nesin_average', '?')}등급 | {s.get('school_type', '일반고')}</p>
        </div>
        """

    html += "</div>"

    # 탐구활동 섹션
    html += "<h2>📝 추천 탐구 주제</h2>"

    for s in students:
        research_list = s.get("research", [])
        if research_list:
            html += f"<h3>{s.get('final_university', '')} 합격생의 탐구활동</h3>"
            html += "<div class='topics'><ul>"
            for r in research_list[:5]:
                html += f"""
                <li>
                    <strong>[{r.get('term', '')}] {r.get('subject', '')}</strong><br>
                    {r.get('title', '')}
                </li>
                """
            html += "</ul></div>"

    # 세특 섹션
    html += "<h2>✍️ 세특 예시</h2>"

    for s in students:
        saeteuk_list = s.get("saeteuk", [])
        if saeteuk_list:
            html += f"<h3>{s.get('final_university', '')} 합격생</h3>"
            for st in saeteuk_list[:2]:
                content = st.get('content', '')[:500]
                if len(st.get('content', '')) > 500:
                    content += "..."
                html += f"""
                <div class="saeteuk-card">
                    <div class="saeteuk-header">
                        <strong>{st.get('subject', '')}</strong>
                    </div>
                    <div class="saeteuk-content">{content}</div>
                </div>
                """

    html += "</div>"
    return html


def generate_report_markdown(req: SearchRequest, students: list) -> str:
    """마크다운 레포트 생성"""
    md = f"""# 📚 맞춤 생기부 로드맵

**검색 조건**: {req.nesin_range} | {req.school_type} | {req.major_field}

---

## 🎯 유사 합격 사례 ({len(students)}명)

"""

    for s in students:
        md += f"- **{s.get('final_university', '미상')} {s.get('final_department', '')}** (내신 {s.get('nesin_average', '?')}등급)\n"

    md += "\n---\n\n## 📝 추천 탐구 주제\n\n"

    for s in students:
        research_list = s.get("research", [])
        if research_list:
            md += f"### {s.get('final_university', '')} 합격생\n\n"
            for r in research_list[:5]:
                md += f"- **[{r.get('term', '')}] {r.get('subject', '')}**: {r.get('title', '')}\n"
            md += "\n"

    md += "---\n\n## ✍️ 세특 예시\n\n"

    for s in students:
        saeteuk_list = s.get("saeteuk", [])
        if saeteuk_list:
            md += f"### {s.get('final_university', '')} 합격생\n\n"
            for st in saeteuk_list[:2]:
                md += f"**{st.get('subject', '')}**\n\n"
                md += f"> {st.get('content', '')[:500]}...\n\n"

    return md


# Vercel serverless handler
handler = Mangum(app, lifespan="off")
