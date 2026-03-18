"""EE-Solver API 서버.

JSON 스키마 기반 REST API + 웹 GUI 제공.

실행:
    uvicorn server:app --port 8100 --reload
"""

import base64

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from pydantic import BaseModel

from config import GEMINI_API_KEY
from gemini_client import (
    calculation_log,
    solution_steps,
    solve_text,
    solve_with_image_bytes,
)

app = FastAPI(title="EE-Solver", description="전기공학 문제 풀이 API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 정적 파일 서빙
STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ── JSON 스키마 정의 ──────────────────────────────────────

class SolveRequest(BaseModel):
    question: str
    image: str | None = None       # base64 인코딩 이미지 (선택)
    mime_type: str = "image/png"   # 이미지 MIME 타입


class SolveResponse(BaseModel):
    success: bool
    answer: str
    solution_steps: list[str] = []
    calculations: list[dict] = []
    error: str | None = None


# ── 엔드포인트 ────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index():
    """메인 페이지 서빙."""
    index_file = STATIC_DIR / "index.html"
    return index_file.read_text(encoding="utf-8")


@app.get("/health")
async def health():
    """헬스체크."""
    return {"status": "ok", "api_key_set": bool(GEMINI_API_KEY)}


@app.post("/solve", response_model=SolveResponse)
async def solve(req: SolveRequest):
    """문제 풀이 API (JSON).

    입력: {"question": "...", "image": "base64...", "mime_type": "image/png"}
    출력: {"success": true, "answer": "...", "calculations": [...]}
    """
    try:
        if req.image:
            image_bytes = base64.b64decode(req.image)
            answer = solve_with_image_bytes(req.question, image_bytes, req.mime_type)
        else:
            answer = solve_text(req.question)

        return SolveResponse(
            success=True,
            answer=answer,
            solution_steps=list(solution_steps),
            calculations=list(calculation_log),
        )
    except Exception as e:
        return SolveResponse(
            success=False,
            answer="",
            error=str(e),
        )
