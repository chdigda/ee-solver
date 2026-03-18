# ⚡ EE-Solver

전기공학 문제를 풀어주는 웹앱. Gemini AI + MCP 수학 계산기 조합.

회로도 이미지를 올리면 회로를 분석하고, 모든 수치 계산은 sympy로 정확하게 처리한다.

## 기능

- 텍스트 질문 / 이미지(회로도) 인식
- Gemini Function Calling → sympy 수학 엔진 (정확한 계산)
- 단계별 풀이 + 사용 법칙 표시
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

### 4-A. 웹앱 실행

```bash
uvicorn server:app --port 8100
```

브라우저에서 http://localhost:8100 접속

### 4-B. CLI 실행

```bash
# 텍스트만
python solve.py "옴의 법칙을 설명해줘"

# 이미지 포함
python solve.py "이 회로에서 전류를 구해라" --image 회로.jpg
```

## 구조

```
ee-solver/
├── server.py            # FastAPI 웹 서버
├── solve.py             # CLI 진입점
├── gemini_client.py     # Gemini API + Function Calling + tool loop
├── config.py            # 설정 (dotenv)
├── mcp_calculator/      # sympy 기반 수학 도구 (5개)
│   ├── __init__.py
│   └── server.py
├── static/
│   └── index.html       # 웹 UI
├── requirements.txt
├── .env.example         # 환경 설정 템플릿
└── ARCHITECTURE.md      # 아키텍처 문서
```

## 기술 스택

| 항목 | 기술 |
|------|------|
| LLM | Google Gemini |
| 수학 엔진 | sympy (MCP 도구) |
| 백엔드 | FastAPI |
| 프론트엔드 | Vanilla HTML/JS + KaTeX |
