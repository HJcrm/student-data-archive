"""Vercel Serverless Function - FastAPI"""

import sys
import os
from pathlib import Path

# 프로젝트 루트 추가
root = Path(__file__).parent.parent
sys.path.insert(0, str(root))

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse
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

# 데이터 로드 (Vercel에서는 읽기 전용)
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


@app.get("/api/students")
async def get_students():
    """전체 학생 목록"""
    try:
        students = load_json("students.json")
        return JSONResponse({"success": True, "students": students})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.post("/api/search")
async def search(req: SearchRequest):
    """학생 검색"""
    try:
        students = load_json("students.json")

        # 내신 범위 파싱
        nesin_min, nesin_max = 0, 10
        if "1등급" in req.nesin_range:
            nesin_min, nesin_max = 1.0, 1.99
        elif "2등급" in req.nesin_range:
            nesin_min, nesin_max = 2.0, 2.99
        elif "3등급" in req.nesin_range:
            nesin_min, nesin_max = 3.0, 3.99
        elif "4등급" in req.nesin_range:
            nesin_min, nesin_max = 4.0, 4.99

        # 필터링
        filtered = []
        for s in students:
            nesin = s.get("nesin_average", 0)
            if nesin_min <= nesin <= nesin_max:
                # 계열 매칭 (간단한 키워드 매칭)
                dept = s.get("department", "").lower()
                field = req.major_field.lower()

                score = 0
                if field in dept or any(k in dept for k in field.split("/")):
                    score = 100
                elif "의" in dept and "의" in field:
                    score = 90
                elif "약" in dept and "약" in field:
                    score = 90

                if score > 0:
                    filtered.append({**s, "match_score": score})

        # 정렬 및 상위 k개
        filtered.sort(key=lambda x: x.get("match_score", 0), reverse=True)
        results = filtered[:req.top_k]

        return JSONResponse({
            "success": True,
            "query": {
                "nesin_range": req.nesin_range,
                "school_type": req.school_type,
                "major_field": req.major_field,
            },
            "students": results,
            "total_found": len(filtered),
        })
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


# Vercel serverless handler
handler = Mangum(app, lifespan="off")
