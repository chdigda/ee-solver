# EE-Solver 아키텍처 문서

## 개요

전기공학부 문제를 풀어주는 서비스.
JSON 스키마 기반 표준 입출력을 제공하여 n8n 등 외부 도구와 연동하며,
강의자료 RAG + Gemini + MCP 계산기를 조합한다.

---

## 시스템 구성도

```
[클라이언트]                      [ee-solver API]
 Android APK ──┐                 ┌──────────────────────────────────┐
 n8n HTTP ─────┼── JSON 요청 ──▶│  FastAPI Server                  │
 curl/웹 ──────┘                 │   │                              │
                                 │   ├─ Prompt Builder              │
                                 │   │   (시스템 프롬프트            │
                                 │   │    + RAG 컨텍스트 주입        │
                                 │   │    + 사용자 문제/이미지)      │
                                 │   │                              │
                                 │   ├─ LLM: Gemini 2.5 Pro        │
                                 │   │   (멀티모달 풀이 엔진)       │
                                 │   │   tool_call ──┐              │
                                 │   │              ▼              │
                                 │   └─ MCP Calculator Server      │
                                 │       (sympy 기반 정밀 계산)     │
                                 │                                  │
                                 └──────────┬───────────────────────┘
                                            │
                                       JSON 응답
                                            │
                                            ▼
                                  클라이언트에서 결과 확인
                                  (앱 화면 / n8n 후속 노드 / 터미널)
```

---

## n8n 연동 방식

ee-solver는 JSON 스키마 기반 REST API로 통신한다.
n8n, Android 앱, curl 등 JSON을 보낼 수 있는 모든 클라이언트에서 호출 가능하다.

### JSON 스키마 (입력 / 출력)

**입력 (POST /solve):**
```json
{
  "question": "이 회로에서 전류를 구해라",
  "image": "base64 인코딩 이미지 (선택)",
  "mime_type": "image/png"
}
```

**출력:**
```json
{
  "success": true,
  "answer": "전류는 2A입니다. ...(전체 마크다운 풀이)",
  "solution_steps": ["1. 옴의 법칙 적용: V=IR", "2. I = 10/5 = 2A"],
  "calculations": [
    {"tool": "calculate", "args": {"expression": "10/5"}, "result": "2"}
  ],
  "error": null
}
```

---

## LLM 역할 정의

### Gemini 2.5 Pro (ee-solver 내부, 메인 풀이 엔진)

| 항목 | 내용 |
|------|------|
| 위치 | ee-solver 서버 내부 |
| 모델 | `gemini-2.5-pro` |
| 역할 | 전기공학 문제 풀이 (텍스트 + 이미지 이해 + MCP 도구 사용) |

**하는 일:**
1. 시스템 프롬프트 + 사용자 문제 + 이미지 + Tool 정의를 받는다
2. 풀이 전략을 세운다
3. **모든 수치 계산은 직접 하지 않고** tool_call을 발행한다
4. MCP Calculator로부터 계산 결과를 받아 풀이를 이어간다
5. 최종 답변을 구조화하여 반환한다

**프롬프트 구조:**
```
[시스템]
너는 전기공학 문제 풀이 전문가다.
규칙:
- 모든 수치 계산은 반드시 제공된 도구(calculate, solve_equation 등)를 사용해라.
  절대 암산하지 마라.
- 풀이 과정을 단계별로 보여줘라.
- 사용한 법칙/정리의 이름을 명시해라.

[사용자]
{question}
{image}
```

**Tool 정의 (Gemini Function Calling → MCP로 실행):**
```
tools:
  - calculate(expression: str) → str
      수학 수식 계산. 예: "10 / (2 + 2)", "sqrt(3) * 5"

  - solve_equation(equation: str, variable: str) → str
      방정식 풀이. 예: equation="2*x + 3 = 7", variable="x"

  - matrix_op(operation: str, matrices: list) → str
      행렬 연산. operation: "multiply", "inverse", "determinant"

  - unit_convert(value: float, from_unit: str, to_unit: str) → str
      단위 변환. 예: value=1000, from="mA", to="A"

  - complex_calc(expression: str) → str
      복소수 연산. 예: "(3+4j) * (1-2j)"
```

**Gemini 호출 루프:**
```
1. Gemini에 프롬프트 전송 (텍스트 + 이미지 + tool 정의)
2. 응답 확인
   ├─ tool_call 있음 → MCP Calculator에 계산 요청
   │                  → 결과를 Gemini에 다시 전달
   │                  → 2로 반복
   └─ tool_call 없음 → 최종 답변 → 종료
```

---

### MCP Calculator Server (LLM 아님, 계산 도구 서버)

| 항목 | 내용 |
|------|------|
| 위치 | 현재: 같은 프로세스에서 직접 import 호출 |
| 예정 | 별도 프로세스, MCP stdio transport로 분리 |
| 엔진 | Python sympy |
| 역할 | Gemini의 tool_call을 받아 정확한 수학 계산 수행 |

**현재 구현 상태:**
- `mcp_calculator/server.py`에 `@mcp.tool()` 데코레이터로 MCP 도구 등록은 되어 있음
- 그러나 `gemini_client.py`에서 함수를 **직접 import**하여 호출 중 (MCP 프로토콜 미사용)
- 향후 MCP stdio transport로 분리하여 웹검색 등 추가 MCP 서버 연결 가능하도록 변경 예정

**Gemini ↔ Calculator 연동 흐름 (현재):**
```
Gemini: "10V에 2옴+3옴 직렬이면... tool_call: calculate('10/(2+3)')"
  ↓
gemini_client.py: tool_call 감지 → TOOL_FUNCTIONS에서 함수 찾아 직접 호출
  ↓
mcp_calculator/server.py: calculate() → sympy.sympify("10/(2+3)") → "2"
  ↓
gemini_client.py: 결과 "2"를 Gemini에 tool_response로 전달
  ↓
Gemini: "따라서 전류는 2A입니다."
```

---

---

## Phase별 구현 상세

### Phase 1: Gemini 텍스트 호출 ✅ 완료

**구현 파일:** `gemini_client.py`, `solve.py`, `config.py`

---

### Phase 2: 이미지 지원 ✅ 완료

**구현:** `gemini_client.py` — `solve_with_image()`, `solve_with_image_bytes()` 추가

---

### Phase 3: Calculator (sympy 직접 호출) ✅ 완료

**구현:** `mcp_calculator/server.py` — sympy 기반 5개 도구, `gemini_client.py` — Function Calling + tool loop

**현재 상태:** MCP 데코레이터 등록은 되어 있으나, 실제로는 Python 직접 import 호출

---

### Phase 4: FastAPI 서버화 + 웹 GUI ✅ 완료

**구현:** `server.py` — Pydantic 모델 기반 JSON API, `static/index.html` — 웹 GUI (KaTeX 수식 렌더링)

---

### Phase 5: MCP stdio 분리 ⬜ 예정

**목표:** Calculator를 MCP stdio transport로 분리. 향후 웹검색 등 추가 MCP 서버 연결 대비.

---

### Phase 6: n8n 연동 테스트 ⬜ 예정

**목표:** n8n 워크플로우에서 HTTP Request 노드로 ee-solver 호출 → 결과 확인

---

### Phase 7: Android APK ⬜ 예정

**목표:** 학생이 폰으로 사진 찍어 문제 풀이 요청.

**구현:** Kotlin/Jetpack Compose 앱 → ee-solver API 호출 → 결과 화면 표시

---

## 최종 디렉토리 구조

```
ee-solver/
├── ARCHITECTURE.md          # 이 문서
├── PROJECT_DESCRIPTION.md   # 프로젝트 설명서
├── server.py                # Phase 4: FastAPI 서버
├── solve.py                 # Phase 1~3: CLI 진입점
├── gemini_client.py         # Phase 1~3: Gemini API + tool loop
├── config.py                # API 키, 설정
├── mcp_calculator/          # Phase 3: MCP 계산기 서버
│   ├── __init__.py
│   └── server.py
├── static/                  # 웹 GUI
│   └── index.html
├── output/                  # 결과 저장
│   └── result.md
├── requirements.txt
└── .env                     # GEMINI_API_KEY
```

---

## 기술 스택

| 구성요소 | 기술 | 비고 |
|----------|------|------|
| 언어 | Python 3.14 | |
| LLM | Google Gemini 2.5 Pro (`google-genai` SDK) | 멀티모달 + Function Calling |
| API 서버 | FastAPI + Uvicorn | Pydantic 모델로 JSON 스키마 정의 |
| 수학 엔진 | sympy | 기호 연산, 복소수, 행렬, 방정식 |
| MCP | `mcp` python SDK + `FastMCP` | 현재 직접 호출, stdio 분리 예정 |
| 웹 GUI | HTML + CSS + JS (단일 파일) | Marked.js (마크다운), KaTeX (수식) |
| 데이터 형식 | JSON (base64 이미지 포함) | 입출력 스키마 Pydantic 정의 |
| 외부 연동 | n8n HTTP Request 노드 | JSON 스키마 기반 |
| 모바일 | Android (Kotlin/Jetpack Compose) | 예정 |

---

## TODO (향후 추가)

- [ ] MCP stdio transport 분리 (Calculator → 별도 프로세스)
- [ ] 웹검색 등 추가 MCP 서버 연결
- [ ] RAG 컨텍스트 주입: n8n에서 강의자료 벡터DB 검색 → `rag_context` 필드로 전달 → 프롬프트에 주입 (on/off 전환)
- [ ] `prompt_builder.py` 모듈 분리
- [ ] 응답에 `solution_steps` 필드 구조화 추가
