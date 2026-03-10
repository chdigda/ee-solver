"""EE-Solver 웹 서버.

FastAPI + 정적 파일 서빙으로 웹앱 GUI 제공.

실행:
    uvicorn server:app --port 8100 --reload
"""

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from config import GEMINI_API_KEY
from gemini_client import (
    calculation_log,
    solve_text,
    solve_with_image_bytes,
)

app = FastAPI(title="EE-Solver", description="전기공학 문제 풀이 웹앱")

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


@app.get("/", response_class=HTMLResponse)
async def index():
    """메인 페이지 서빙."""
    index_file = STATIC_DIR / "index.html"
    return index_file.read_text(encoding="utf-8")


@app.get("/health")
async def health():
    """헬스체크."""
    return {"status": "ok", "api_key_set": bool(GEMINI_API_KEY)}


@app.post("/solve")
async def solve(
    question: str = Form(...),
    image: UploadFile | None = File(None),
):
    """문제 풀이 API.

    - question: 질문 텍스트 (필수)
    - image: 회로도 이미지 파일 (선택)
    """
    try:
        if image and image.filename:
            image_bytes = await image.read()
            mime_type = image.content_type or "image/png"
            answer = solve_with_image_bytes(question, image_bytes, mime_type)
        else:
            answer = solve_text(question)

        return {
            "success": True,
            "answer": answer,
            "calculations": list(calculation_log),
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "answer": "",
            "calculations": [],
        }
