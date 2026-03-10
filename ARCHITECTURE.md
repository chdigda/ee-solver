# EE-Solver 아키텍처 문서

## 개요

전기공학부 문제를 풀어주는 시스템.
n8n 파이프라인의 구성요소로 동작하며, 강의자료 RAG + Gemini + MCP 계산기를 조합한다.

---

## 시스템 구성도

```
┌─────────────────── n8n 워크플로우 ───────────────────┐
│                                                       │
│  [입력 노드]     [RAG 노드]        [ee-solver 호출]   │
│   문제+이미지 ──▶ LLM #1 ────────▶ HTTP Request ──▶ ──┼──▶ ee-solver API
│                  (임베딩/검색)      rag_context 포함   │       │
│                                                       │       │
│  [출력 노드] ◀── 후처리 ◀──────── JSON 응답 ◀────────┼───────┘
│   최종 답변                                           │
└───────────────────────────────────────────────────────┘

┌─────────────────── ee-solver ────────────────────────┐
│                                                       │
│  FastAPI Server                                       │
│   │                                                   │
│   ├─ Prompt Builder (RAG 컨텍스트 주입)               │
│   ├─ LLM #2: Gemini API (문제 풀이)                  │
│   └─ MCP Calculator Server (수치 계산)                │
│                                                       │
└───────────────────────────────────────────────────────┘
```

---

## LLM 역할 정의

### LLM #1: n8n RAG 전처리 (n8n 내부)

| 항목 | 내용 |
|------|------|
| 위치 | n8n 워크플로우 내부 |
| 모델 | 자유 선택 (Gemini, OpenAI 등 n8n에서 지원하는 것) |
| 역할 | 강의자료에서 문제 풀이에 필요한 내용 검색/추출 |

**하는 일:**
1. 사용자 질문을 받는다
2. 벡터DB(Pinecone, Qdrant 등)에서 관련 강의자료 청크를 검색한다
3. 검색된 청크를 `rag_context` 필드에 담아 ee-solver에 전달한다

**입력:**
```json
{
  "question": "이 회로에서 테브난 등가회로를 구하시오",
  "image": "base64..."
}
```

**출력 (ee-solver로 보내는 것):**
```json
{
  "question": "이 회로에서 테브난 등가회로를 구하시오",
  "image": "base64...",
  "rag_context": [
    "테브난 정리: 임의의 선형 2단자 회로는 하나의 전압원 Vth와 직렬저항 Rth로...",
    "테브난 등가저항 구하기: 독립전원을 제거하고 단자에서 본 등가저항..."
  ],
  "rag_enabled": true
}
```

---

### LLM #2: Gemini (ee-solver 내부, 메인 풀이 엔진)

| 항목 | 내용 |
|------|------|
| 위치 | ee-solver 서버 내부 |
| 모델 | `gemini-2.5-pro` |
| 역할 | 전기공학 문제 풀이 (텍스트 + 이미지 이해 + 도구 사용) |

**하는 일:**
1. 시스템 프롬프트 + RAG 컨텍스트(선택) + 사용자 문제 + 이미지를 받는다
2. 강의자료를 참고하여 풀이 전략을 세운다
3. **모든 수치 계산은 직접 하지 않고** MCP Calculator tool_call을 발행한다
4. 계산 결과를 받아 풀이를 이어간다
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

[RAG 컨텍스트 - rag_enabled=true일 때만]
--- 참고 강의자료 ---
{rag_context 내용}
---

[사용자]
{question}
{image}
```

**Tool 정의 (Gemini Function Calling):**
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
1. Gemini에 프롬프트 전송
2. 응답 확인
   ├─ tool_call 있음 → MCP Calculator에 계산 요청 → 결과를 Gemini에 다시 전달 → 2로
   └─ tool_call 없음 → 최종 답변 → 종료
```

---

### MCP Calculator Server (LLM 아님, 도구 서버)

| 항목 | 내용 |
|------|------|
| 위치 | ee-solver와 함께 실행 (별도 프로세스, stdio transport) |
| 엔진 | Python sympy |
| 역할 | 정확한 수학 계산 제공 |

**하는 일:**
- Gemini의 tool_call을 받아 sympy로 정확하게 계산
- 부동소수점 오류 없이 기호 연산 가능
- 복소수, 행렬, 미적분, 방정식 풀이 지원

---

## Phase별 구현 상세

### Phase 1: Gemini 텍스트 호출

**목표:** Gemini API 연동, 텍스트 질문 → 답변 확인

**구현:**
- `gemini_client.py`: Gemini API 호출 (텍스트만)
- `solve.py`: CLI 진입점

**확인 방법:**
```bash
python solve.py "옴의 법칙을 설명해줘"
```
→ 터미널 출력 + `output/result.md` 저장

**파일:**
```
ee-solver/
├── solve.py
├── gemini_client.py
├── config.py
└── output/
```

---

### Phase 2: 이미지 지원

**목표:** 회로도 사진을 Gemini에 전달하여 문제 풀이

**구현:**
- `gemini_client.py` 수정: 이미지 Part 추가
- `solve.py` 수정: `--image` 인자 추가

**확인 방법:**
```bash
python solve.py "이 회로에서 전류를 구해라" --image circuit.png
```
→ 이미지를 인식한 풀이가 나오는지 확인

---

### Phase 3: MCP Calculator

**목표:** 모든 수치 계산을 MCP 서버 경유로 처리

**구현:**
- `mcp_calculator/server.py`: MCP 서버 (sympy 기반 5개 도구)
- `gemini_client.py` 수정: Function Calling + tool loop 추가

**확인 방법:**
```bash
python solve.py "10V 전원에 2옴과 3옴 직렬저항이 연결되어 있다. 전류를 구해라"
```
→ 풀이 중 `calculate("10 / (2 + 3)") = 2.0` 이 MCP 경유로 처리되는지 확인
→ `result.md`에 계산 과정 표시

**파일 추가:**
```
ee-solver/
├── mcp_calculator/
│   ├── __init__.py
│   └── server.py
```

---

### Phase 4: RAG 컨텍스트 주입

**목표:** 외부에서 받은 강의자료 컨텍스트를 프롬프트에 주입

**구현:**
- `prompt_builder.py`: 시스템 프롬프트 + RAG + 사용자 질문 조립
- `solve.py` 수정: `--rag-file` 인자 추가 (테스트용, JSON 파일로 RAG 데이터 주입)

**확인 방법:**
```bash
# RAG OFF
python solve.py "테브난 등가회로를 구해라" --image circuit.png

# RAG ON (강의자료 포함)
python solve.py "테브난 등가회로를 구해라" --image circuit.png --rag-file rag_sample.json
```
→ RAG on/off에 따른 답변 품질 차이 확인

**rag_sample.json 예시:**
```json
[
  "테브난 정리: 임의의 선형 2단자 회로는 하나의 전압원 Vth와 직렬저항 Rth로 등가 변환 가능하다.",
  "Vth 구하기: 부하를 제거하고 개방전압을 측정한다.",
  "Rth 구하기: 독립전원을 제거(전압원→단락, 전류원→개방)하고 단자에서 본 등가저항을 구한다."
]
```

---

### Phase 5: FastAPI 서버화

**목표:** n8n에서 HTTP로 호출 가능한 REST API

**구현:**
- `server.py`: FastAPI 앱
  - `POST /solve` — 문제 풀이
  - `GET /health` — 헬스체크

**확인 방법:**
```bash
# 서버 실행
uvicorn server:app --port 8100

# curl 테스트
curl -X POST http://localhost:8100/solve \
  -H "Content-Type: application/json" \
  -d '{
    "question": "전류를 구해라",
    "image": "base64...",
    "rag_context": ["옴의 법칙: V=IR"],
    "rag_enabled": true
  }'
```

**API 스펙:**
```
POST /solve
Request:
{
  "question": str,           # 필수
  "image": str | null,       # base64 인코딩 이미지 (선택)
  "rag_context": list[str],  # n8n에서 보내주는 RAG 데이터 (선택)
  "rag_enabled": bool        # RAG 주입 여부 (기본: true)
}

Response:
{
  "answer": str,              # 최종 답변
  "solution_steps": list[str],# 풀이 단계
  "calculations": list[dict], # MCP 계산 기록
  "rag_used": bool,           # RAG 사용 여부
  "rag_sources": list[str]    # 사용된 RAG 소스 요약
}
```

---

### Phase 6: 통합 테스트

**목표:** n8n end-to-end 동작 확인

**n8n 워크플로우 구성:**
```
[Webhook/Chat 트리거]
       │
       ▼
[강의자료 벡터DB 검색] ← LLM #1 (임베딩)
       │
       │ rag_context
       ▼
[HTTP Request: POST ee-solver/solve]
       │
       │ JSON 응답
       ▼
[응답 포맷팅] → 최종 답변 출력
```

**확인 방법:**
- n8n에서 실제 문제 입력 → 최종 답변이 나오는지 확인

---

## 최종 디렉토리 구조

```
ee-solver/
├── ARCHITECTURE.md          # 이 문서
├── server.py                # Phase 5: FastAPI 서버
├── solve.py                 # Phase 1~4: CLI 진입점
├── gemini_client.py         # Phase 1~3: Gemini API 호출 + tool loop
├── prompt_builder.py        # Phase 4: 프롬프트 조립
├── config.py                # API 키, 설정
├── mcp_calculator/          # Phase 3: MCP 계산기 서버
│   ├── __init__.py
│   └── server.py
├── output/                  # 결과 저장
│   └── result.md
├── rag_data/                # 테스트용 RAG 샘플
│   └── rag_sample.json
├── requirements.txt
└── .env                     # GEMINI_API_KEY
```

---

## 기술 스택

| 구성요소 | 기술 |
|----------|------|
| 언어 | Python 3.14 |
| LLM | Google Gemini 2.5 Pro |
| API 서버 | FastAPI + uvicorn |
| MCP | mcp python SDK (stdio transport) |
| 수학 엔진 | sympy |
| 파이프라인 | n8n (외부) |
| RAG | n8n 벡터DB (외부) |
