# Gemini 모델 선택 기능 설계

날짜: 2026-04-07
상태: 승인됨

## 배경

EE-Solver는 현재 단일 Gemini 모델을 사용한다 (`config.py`의 `GEMINI_MODEL` 환경 변수). 사용자가 두 가지 모델 — `gemini-3-flash-preview`와 `gemini-3.1-flash-lite-preview` — 의 응답 품질을 비교하면서 작업하고 싶어한다.

`gemini-3.1-flash-lite-preview`는 빠르지만 응답 품질이 낮고, `gemini-3-flash-preview`가 더 정확하다는 것이 사용자의 평가다. 매번 환경 변수를 바꾸고 서버를 재시작하지 않고도 모델을 전환할 수 있어야 한다.

## 목표

- 웹 UI에서 드롭다운으로 모델을 즉시 전환할 수 있다.
- 기본 모델은 `gemini-3-flash-preview`다.
- 외부 API 호출자(n8n, 안드로이드 등)도 동일한 메커니즘으로 모델을 지정할 수 있다 — 단, 지금 구현 작업은 웹 UI에 집중하고, API는 호환 가능한 구조만 갖춰둔다.
- 잘못된 모델명을 받으면 조용히 fallback하지 않고 명시적 에러를 낸다.

## 비목표 (YAGNI)

- 모델별 표시명/설명/가격 메타데이터: 모델명을 그대로 노출한다.
- 모델 추가/삭제 관리 UI: 코드 상수로 관리한다.
- 사용자별 기본 모델 서버 저장: 브라우저 localStorage로 충분하다.
- CLI(`solve.py`)의 `--model` 플래그: 현재 작업 범위 밖. 필요해지면 별도로 추가.

## 설계

### 변경 파일

**1. `config.py`** — 사용 가능한 모델 목록과 디폴트 정의

```python
AVAILABLE_MODELS = ["gemini-3-flash-preview", "gemini-3.1-flash-lite-preview"]
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")
```

**2. `gemini_client.py`** — `solve_text`, `solve_with_image_bytes`, `solve_with_rag` 세 함수에 `model: str | None = None` 파라미터 추가. 내부에서 `model or GEMINI_MODEL`을 사용해 `genai.GenerativeModel(...)`에 전달.

**3. `server.py`**

- `SolveRequest`에 `model: str | None = None` 필드 추가
- `/solve` 엔드포인트에서 검증: `req.model`이 `None`도 아니고 `AVAILABLE_MODELS`에도 없으면 400 에러 반환
- `req.model`을 `solve_*` 함수들에 전달
- 새 엔드포인트 `GET /models`:
  ```json
  {"models": ["gemini-3-flash-preview", "gemini-3.1-flash-lite-preview"], "default": "gemini-3-flash-preview"}
  ```

**4. `static/index.html`**

- 질문 textarea 위에 `<select id="model-select">` 드롭다운 추가
- 페이지 로드 시 `GET /models`를 fetch해서 옵션을 동적으로 채움 (서버가 진실 공급원)
- localStorage 키 `ee-solver-model`로 마지막 선택 기억
- 페이지 로드 시 localStorage 값이 있고 사용 가능 목록에 포함되면 그 값으로 초기화, 아니면 서버의 `default` 사용
- `/solve` POST의 body에 `model` 필드 포함

**5. `env.example`** — `GEMINI_MODEL=gemini-3-flash-preview`로 되돌림 (현재 `gemini-3.1-flash-lite-preview`로 돼있음)

### 검증 정책

- API가 받은 `model`이 `AVAILABLE_MODELS`에 없으면 **400 에러**, body는 `{"success": false, "error": "unknown model: <name>", ...}`
- `model`이 `None`이면 디폴트 (`GEMINI_MODEL`) 사용
- 조용한 fallback은 하지 않는다 — 사용자 의도와 다른 모델로 답하면 디버깅이 어려워지기 때문.

### 호환성

- `SolveRequest.model`은 **선택적 필드**라 기존 호출자(n8n 워크플로우 등)는 영향 없음
- `GET /models`는 신규 엔드포인트라 기존 동작에 영향 없음
- env.example의 변경은 새 사용자 신규 설치에만 영향. 기존 사용자의 `.env`는 그대로.

### 데이터 흐름

```
[브라우저 드롭다운 onChange]
  ↓ localStorage.setItem('ee-solver-model', value)
[POST /solve]
  ↓ JSON body { question, image, ..., model: "gemini-3-flash-preview" }
[server.py: SolveRequest 검증]
  ↓ AVAILABLE_MODELS에 없으면 400
[gemini_client.solve_*(question=..., model=...)]
  ↓ genai.GenerativeModel(model or GEMINI_MODEL)
[Gemini API]
```

### 페이지 로드 시 모델 초기화 흐름

```
1. fetch GET /models → { models: [...], default: "..." }
2. <select>를 models로 채움
3. localStorage['ee-solver-model'] 확인
4. localStorage 값이 models에 포함됨? → select.value = 그 값
5. 아니면 → select.value = default
```

## 에러 처리

- **잘못된 모델명** (서버 검증): 400 + `{"success": false, "answer": "", "error": "unknown model: <name>"}`
- **유효한 모델명인데 Gemini API가 reject** (예: 모델이 일시적으로 unavailable): 기존 try/except 경로로 500 + 에러 메시지
- **`/models` 호출 실패** (드롭다운이 채워지지 않는 경우): 드롭다운에 fallback 옵션 두 개를 하드코딩 — 페이지가 완전히 망가지지 않도록. 콘솔에 경고 출력.

## 테스트 계획

수동 테스트 (이 프로젝트는 자동 테스트가 없다):

- **드롭다운 동작**: 페이지 로드 → 두 옵션 보임, 디폴트 = `gemini-3-flash-preview`
- **localStorage 기억**: `gemini-3.1-flash-lite-preview` 선택 → 새로고침 → 그 값이 유지됨
- **각 모델 호출**: 두 모델 다 선택해서 실제 응답이 다른지 확인 (기본 산수 문제로 충분)
- **API 직접 호출**: curl로 `model` 필드 포함/미포함 둘 다 호출
- **API 잘못된 모델**: curl로 `"model": "gpt-4"` 보내서 400 받는지 확인
- **`GET /models`**: curl로 호출해서 응답 형식 확인

## 작업량 추정

작은 작업. 5개 파일, 각각 짧은 변경. 대부분은 한 줄 추가 + 통합.

## 미해결 항목

없음.
