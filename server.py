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
from gemini_client import solve_text, solve_with_image_bytes, solve_with_rag

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

# index.html 캐싱 (매 요청마다 파일 읽기 방지)
_INDEX_HTML = (STATIC_DIR / "index.html").read_text(encoding="utf-8")


# ── JSON 스키마 정의 ──────────────────────────────────────

class SolveRequest(BaseModel):
    question: str
    image: str | None = None       # base64 인코딩 이미지 (선택)
    mime_type: str = "image/png"   # 이미지 MIME 타입
    rag_context: list[str] = []    # n8n RAG 노드에서 보내주는 강의자료 컨텍스트
    rag_enabled: bool = True       # RAG 컨텍스트 주입 on/off


class SolveResponse(BaseModel):
    success: bool
    answer: str
    solution_steps: list[str] = []
    calculations: list[dict] = []
    rag_used: bool = False
    error: str | None = None


# ── 엔드포인트 ────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index():
    """메인 페이지 서빙."""
    return _INDEX_HTML


@app.get("/health")
async def health():
    """헬스체크. n8n에서 서버 상태 확인용."""
    return {"status": "ok", "api_key_set": bool(GEMINI_API_KEY)}


@app.get("/schema")
async def schema():
    """입출력 JSON 스키마 반환. n8n 연동 시 필드 매핑 참고용."""
    return {
        "input": SolveRequest.model_json_schema(),
        "output": SolveResponse.model_json_schema(),
    }


@app.post("/solve", response_model=SolveResponse)
async def solve(req: SolveRequest):
    """문제 풀이 API (JSON).

    n8n HTTP Request 노드에서 호출:
    - question + image → 기본 풀이
    - question + image + rag_context → 강의자료 기반 풀이
    """
    try:
        # RAG 컨텍스트 결정
        rag_context = req.rag_context if req.rag_enabled and req.rag_context else None

        # 이미지 디코딩
        image_bytes = base64.b64decode(req.image) if req.image else None

        # 풀이 실행
        if rag_context:
            result = solve_with_rag(
                question=req.question,
                rag_context=rag_context,
                image_bytes=image_bytes,
                mime_type=req.mime_type,
            )
        elif image_bytes:
            result = solve_with_image_bytes(req.question, image_bytes, req.mime_type)
        else:
            result = solve_text(req.question)

        return SolveResponse(
            success=True,
            answer=result.answer,
            solution_steps=result.solution_steps,
            calculations=result.calculation_log,
            rag_used=rag_context is not None,
        )
    except Exception as e:
        return SolveResponse(
            success=False,
            answer="",
            error=str(e),
        )
