# EE-Solver

전기공학 문제 풀이 API 서버. Gemini AI + MCP 계산기 조합.

회로도 이미지와 문제를 JSON으로 보내면, 단계별 풀이와 정확한 수치 계산 결과를 JSON으로 돌려준다.
n8n 워크플로우, Android 앱, 웹 브라우저 등 JSON을 보낼 수 있는 모든 클라이언트에서 사용 가능.

## 기능

- 텍스트 질문 / 이미지(회로도) 인식 (Gemini 멀티모달)
- Gemini Function Calling → sympy 수학 엔진 (정밀 계산)
- 단계별 풀이 + 사용 법칙 표시
- RAG 강의자료 컨텍스트 주입 (on/off 전환)
- JSON 스키마 기반 입출력 (n8n 등 외부 도구 연동)
- 웹 UI (다크테마, 수식 렌더링, 이미지 드래그앤드롭/붙여넣기)

## 빠른 시작

### 1. API 키 준비

[Google AI Studio](https://aistudio.google.com/apikey)에서 Gemini API 키를 발급받는다.

### 2. 설치

```bash
cd ee-solver
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. 환경 설정

```bash
cp .env.example .env
# .env 파일을 열어서 GEMINI_API_KEY에 본인 키 입력
```

### 4. 실행

```bash
uvicorn server:app --port 8100
```

브라우저에서 http://localhost:8100 접속

### 5. API 호출 예시

```bash
# 기본 호출
curl -X POST http://localhost:8100/solve \
  -H "Content-Type: application/json" \
  -d '{
    "question": "10V 전원에 2옴과 3옴 직렬저항이 연결되어 있다. 전류를 구해라"
  }'

# RAG 강의자료 포함 호출
curl -X POST http://localhost:8100/solve \
  -H "Content-Type: application/json" \
  -d '{
    "question": "테브난 등가회로를 구해라",
    "rag_context": ["테브난 정리: 임의의 선형 2단자 회로는 Vth와 Rth로 등가변환 가능"],
    "rag_enabled": true
  }'
```

**응답:**
```json
{
  "success": true,
  "answer": "전류는 2A입니다. ...",
  "solution_steps": ["1. 옴의 법칙 적용: V=IR", "2. I = 10/5 = 2A"],
  "calculations": [
    {"tool": "calculate", "args": {"expression": "10/5"}, "result": "2"}
  ],
  "rag_used": false,
  "error": null
}
```

### CLI 실행 (개발용)

```bash
# 텍스트만
python solve.py "옴의 법칙을 설명해줘"

# 이미지 포함
python solve.py "이 회로에서 전류를 구해라" --image 회로.jpg
```

## 구조

```
ee-solver/
├── server.py            # FastAPI 서버 (JSON API + 웹 GUI)
├── solve.py             # CLI 진입점
├── gemini_client.py     # Gemini API + Function Calling + tool loop + RAG 주입
├── config.py            # 설정 (dotenv)
├── mcp_calculator/      # sympy 기반 수학 도구 (5개)
│   ├── __init__.py
│   └── server.py
├── static/
│   └── index.html       # 웹 UI
├── n8n/                 # n8n 워크플로우 템플릿
│   ├── workflow_template.json
│   └── workflow_with_rag.json
├── requirements.txt
├── .env.example         # 환경 설정 템플릿
└── ARCHITECTURE.md      # 아키텍처 문서
```

## n8n 연동

`n8n/` 폴더에 Import 가능한 워크플로우 템플릿이 있다.

1. n8n에서 Import workflow → `workflow_template.json` 선택
2. HTTP Request 노드의 URL을 ee-solver 서버 주소로 설정
3. 실행

RAG 포함 워크플로우는 `workflow_with_rag.json` 사용. 벡터DB 노드를 직접 설정해야 한다.

## 기술 스택

| 항목 | 기술 |
|------|------|
| LLM | Google Gemini 2.5 Pro |
| 수학 엔진 | sympy (MCP 도구) |
| 백엔드 | FastAPI + Uvicorn |
| 프론트엔드 | Vanilla HTML/JS + KaTeX |
| 데이터 형식 | JSON (base64 이미지 포함) |
| 외부 연동 | n8n HTTP Request 노드 |
| 모바일 | Android APK (예정) |
