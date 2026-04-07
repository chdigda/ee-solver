# Gemini 모델 선택 기능 구현 Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 웹 UI에서 두 가지 Gemini 모델(`gemini-3-flash-preview`, `gemini-3.1-flash-lite-preview`)을 즉시 전환할 수 있게 한다. API 호환성을 함께 챙겨두지만 노출은 웹 UI에 집중한다.

**Architecture:** `config.py`에 모델 화이트리스트를 두고, `gemini_client.py`의 풀이 함수들에 `model` 파라미터를 끝까지 전파한다. `server.py`의 `/solve`가 모델명을 검증한 뒤 전달하고, 새 `GET /models` 엔드포인트가 사용 가능 모델 목록을 노출한다. 웹 UI는 페이지 로드 시 `/models`로 옵션을 채우고 localStorage로 마지막 선택을 기억한다.

**Tech Stack:** Python 3, FastAPI, Pydantic v2, google-genai, Vanilla JS + KaTeX

**관련 spec:** [docs/superpowers/specs/2026-04-07-gemini-model-selection-design.md](../specs/2026-04-07-gemini-model-selection-design.md)

**테스트 전략:** 이 프로젝트는 자동 테스트가 없다. 각 task는 수동 verification으로 종료한다. 새로운 테스트 인프라(pytest 등) 도입은 이 plan의 범위가 아니다.

---

## 파일 구조

작업 대상 5개 파일:

| 파일 | 역할 | 변경 종류 |
|---|---|---|
| `config.py` | 모델 화이트리스트, 디폴트 모델 정의 | 수정 |
| `env.example` | 신규 사용자용 디폴트 환경 변수 템플릿 | 수정 |
| `gemini_client.py` | 풀이 함수들이 동적으로 모델을 받아 호출 | 수정 |
| `server.py` | API 필드 추가, 검증, `/models` 엔드포인트 | 수정 |
| `static/index.html` | 드롭다운 UI + JS 통합 | 수정 |

각 task는 독립적으로 동작 상태를 유지한다 (이전 task만 끝나면 서버는 항상 부팅 가능).

---

## Task 1: config.py + env.example — 모델 화이트리스트와 디폴트

**목표:** 사용 가능 모델 리스트와 디폴트를 한 곳에서 관리하도록 상수를 도입한다. 이 task만 끝난 시점에서는 아직 아무것도 이 상수를 사용하지 않지만, 서버는 정상 부팅 가능하다.

**Files:**
- Modify: `config.py:11-12`
- Modify: `env.example:4`

- [ ] **Step 1: `config.py` 수정**

`config.py`의 11~12번째 줄 (Gemini 설정 부분) 을 다음과 같이 바꿈:

```python
# Gemini API 설정
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# 사용 가능한 모델 화이트리스트.
# 새 모델을 추가하려면 이 리스트에 모델명을 추가하기만 하면 된다.
AVAILABLE_MODELS = [
    "gemini-3-flash-preview",
    "gemini-3.1-flash-lite-preview",
]

# 디폴트 모델. 환경 변수로 오버라이드 가능.
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")
```

기존 `GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-pro")` 줄을 위로 교체하는 것이다.

- [ ] **Step 2: `env.example` 수정**

`env.example`의 4번째 줄을 수정한다 (현재 `gemini-3.1-flash-lite-preview`로 되어 있음):

```
# 여기에 본인의 Gemini API 키를 입력하세요
# https://aistudio.google.com/apikey 에서 발급
GEMINI_API_KEY=네 키를 넣으세요.
GEMINI_MODEL=gemini-3-flash-preview
```

- [ ] **Step 3: import 검증**

`.venv` 활성화 후 다음을 실행:

```bash
cd /home/cocapanic/다운로드/project/ee-solver
.venv/bin/python -c "from config import AVAILABLE_MODELS, GEMINI_MODEL; print('models:', AVAILABLE_MODELS); print('default:', GEMINI_MODEL)"
```

기대 출력:
```
models: ['gemini-3-flash-preview', 'gemini-3.1-flash-lite-preview']
default: gemini-3-flash-preview
```

(`.env`에 `GEMINI_MODEL`이 다른 값으로 설정돼 있으면 그 값이 우선한다 — 그 경우 `.env`를 잠시 비활성화하거나 해당 줄을 주석 처리하고 재실행해서 디폴트가 동작하는지 확인.)

- [ ] **Step 4: 커밋**

```bash
git add config.py env.example
git commit -m "config: AVAILABLE_MODELS 화이트리스트 추가, 디폴트 모델을 gemini-3-flash-preview로 변경"
```

---

## Task 2: gemini_client.py — 풀이 함수에 model 파라미터 전파

**목표:** 세 개의 공개 풀이 함수와 그 호출 체인 전체에 `model: str | None = None` 파라미터를 흘려서, 호출자가 매 호출마다 모델을 선택할 수 있게 한다. 호환성을 위해 `None`이면 `GEMINI_MODEL` 디폴트를 사용한다. 이 task만으로는 아직 외부에 노출되지 않지만, 기존 동작은 깨지지 않는다.

**Files:**
- Modify: `gemini_client.py:245-348` (다섯 함수)

**작업 함수 목록 (호출 순서):**
1. `_tool_loop(response, contents, result)` → `model` 추가
2. `_solve(contents)` → `model` 추가, `_tool_loop`에 전달
3. `solve_text(question)` → `model` 추가, `_solve`에 전달
4. `solve_with_image_bytes(question, image_bytes, mime_type)` → `model` 추가, `_solve`에 전달
5. `solve_with_image(question, image_path)` → `model` 추가, `solve_with_image_bytes`에 전달
6. `solve_with_rag(question, rag_context, image_bytes, mime_type)` → `model` 추가, `_solve`에 전달

(주: `genai.Client` 자체는 모델과 무관하므로 재생성 불필요. 모델은 매 `client.models.generate_content` 호출 시 인자로 전달된다.)

- [ ] **Step 1: `_tool_loop` 함수 수정**

`gemini_client.py:245-280`의 `_tool_loop` 함수 전체를 다음으로 교체:

```python
def _tool_loop(response, contents: list, result: SolveResult, model: str) -> str:
    """Gemini 응답에 tool_call이 있으면 실행 후 재전달하는 루프."""
    max_iterations = 20

    for i in range(max_iterations):
        parts = response.candidates[0].content.parts
        function_calls = [p for p in parts if p.function_call]

        if not function_calls:
            return response.text

        contents.append(response.candidates[0].content)

        response_parts = []
        for part in function_calls:
            fc = part.function_call
            tool_result = _execute_tool_call(fc, result)
            response_parts.append(
                genai.types.Part.from_function_response(
                    name=fc.name,
                    response={"result": tool_result},
                )
            )

        contents.append(
            genai.types.Content(role="user", parts=response_parts)
        )

        response = client.models.generate_content(
            model=model,
            contents=contents,
            config=_GEMINI_CONFIG,
        )

    print(f"[warning] tool loop exhausted after {max_iterations} iterations")
    return response.text or ""
```

변경 핵심:
- 시그니처에 `model: str` 추가 (필수 인자 — `_solve`에서 항상 채워서 전달함)
- `client.models.generate_content(model=GEMINI_MODEL, ...)` → `client.models.generate_content(model=model, ...)`

- [ ] **Step 2: `_solve` 함수 수정**

`gemini_client.py:283-294`의 `_solve` 함수 전체를 다음으로 교체:

```python
def _solve(contents: list, model: str | None = None) -> SolveResult:
    """공통 풀이 로직. contents를 Gemini에 전달하고 tool loop를 실행한다."""
    result = SolveResult()
    selected_model = model or GEMINI_MODEL

    response = client.models.generate_content(
        model=selected_model,
        contents=contents,
        config=_GEMINI_CONFIG,
    )
    result.answer = _tool_loop(response, contents, result, selected_model)
    result.solution_steps = _parse_steps(result.answer)
    return result
```

변경 핵심:
- 시그니처에 `model: str | None = None` 추가
- `selected_model = model or GEMINI_MODEL`로 디폴트 fallback
- 두 곳 모두 `selected_model` 사용 (직접 호출 + `_tool_loop`에 전달)

- [ ] **Step 3: `solve_text` 함수 수정**

`gemini_client.py:297-299`의 `solve_text` 함수 전체를 다음으로 교체:

```python
def solve_text(question: str, model: str | None = None) -> SolveResult:
    """텍스트 질문을 Gemini에 전달하고 답변을 받는다."""
    return _solve([question], model=model)
```

- [ ] **Step 4: `solve_with_image` 함수 수정**

`gemini_client.py:302-306`의 `solve_with_image` 함수 전체를 다음으로 교체:

```python
def solve_with_image(
    question: str, image_path: str, model: str | None = None
) -> SolveResult:
    """텍스트 질문 + 이미지 파일을 Gemini에 전달한다."""
    path = Path(image_path)
    mime_type = mimetypes.guess_type(path.name)[0] or "image/png"
    return solve_with_image_bytes(question, path.read_bytes(), mime_type, model=model)
```

- [ ] **Step 5: `solve_with_image_bytes` 함수 수정**

`gemini_client.py:309-317`의 `solve_with_image_bytes` 함수 전체를 다음으로 교체:

```python
def solve_with_image_bytes(
    question: str,
    image_bytes: bytes,
    mime_type: str,
    model: str | None = None,
) -> SolveResult:
    """텍스트 질문 + 이미지 바이트를 Gemini에 전달한다."""
    contents = [
        genai.types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
        question,
    ]
    return _solve(contents, model=model)
```

- [ ] **Step 6: `solve_with_rag` 함수 수정**

`gemini_client.py:320-348`의 `solve_with_rag` 함수 전체를 다음으로 교체:

```python
def solve_with_rag(
    question: str,
    rag_context: list[str],
    image_bytes: bytes | None = None,
    mime_type: str = "image/png",
    model: str | None = None,
) -> SolveResult:
    """n8n RAG 파이프라인에서 받은 강의자료 컨텍스트를 포함하여 풀이한다.

    rag_context를 프롬프트 앞에 주입하고, 이미지가 있으면 함께 전달한다.
    """
    # RAG 컨텍스트를 텍스트 블록으로 조립
    rag_block = (
        "--- 참고 강의자료 (아래 내용을 풀이에 활용해라) ---\n"
        + "\n\n".join(rag_context)
        + "\n--- 강의자료 끝 ---\n\n"
    )

    contents = []

    # 이미지가 있으면 먼저 추가
    if image_bytes:
        contents.append(
            genai.types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
        )

    # RAG 컨텍스트 + 질문
    contents.append(rag_block + question)

    return _solve(contents, model=model)
```

- [ ] **Step 7: 시그니처 검증**

```bash
cd /home/cocapanic/다운로드/project/ee-solver
.venv/bin/python -c "
import inspect
from gemini_client import solve_text, solve_with_image, solve_with_image_bytes, solve_with_rag
for f in [solve_text, solve_with_image, solve_with_image_bytes, solve_with_rag]:
    print(f.__name__, inspect.signature(f))
"
```

기대 출력 (각 함수 시그니처에 `model` 키워드가 보여야 함):
```
solve_text (question: str, model: str | None = None) -> gemini_client.SolveResult
solve_with_image (question: str, image_path: str, model: str | None = None) -> gemini_client.SolveResult
solve_with_image_bytes (question: str, image_bytes: bytes, mime_type: str, model: str | None = None) -> gemini_client.SolveResult
solve_with_rag (question: str, rag_context: list[str], image_bytes: bytes | None = None, mime_type: str = 'image/png', model: str | None = None) -> gemini_client.SolveResult
```

- [ ] **Step 8: 기존 호출자 (server.py) 영향 확인**

`server.py`는 아직 model 인자를 전달하지 않지만, 모든 추가 인자가 키워드 + 디폴트값이라 깨질 게 없다. 서버 import만 확인:

```bash
.venv/bin/python -c "from server import app; print('server import OK')"
```

기대 출력:
```
server import OK
```

- [ ] **Step 9: 커밋**

```bash
git add gemini_client.py
git commit -m "gemini_client: 풀이 함수들에 model 파라미터 전파"
```

---

## Task 3: server.py — SolveRequest 모델 필드, 검증, /models 엔드포인트

**목표:** REST API를 통해 모델 선택을 받을 수 있도록 한다. 잘못된 모델은 400으로 거부, 옳은 모델은 `gemini_client`에 전달, 새 `GET /models` 엔드포인트가 화이트리스트와 디폴트를 반환한다. 이 task가 끝난 시점부터 curl로 직접 검증 가능하다.

**Files:**
- Modify: `server.py:1-122` (전반적으로 손대지만 핵심은 import, SolveRequest, solve handler, 새 endpoint)

- [ ] **Step 1: import 수정**

`server.py:18`의 import 줄을 다음으로 교체:

```python
from config import AVAILABLE_MODELS, GEMINI_API_KEY, GEMINI_MODEL
```

(`AVAILABLE_MODELS`와 `GEMINI_MODEL` 추가)

- [ ] **Step 2: `SolveRequest`에 model 필드 추가**

`server.py:41-46`의 `SolveRequest` 클래스 전체를 다음으로 교체:

```python
class SolveRequest(BaseModel):
    question: str
    image: str | None = None       # base64 인코딩 이미지 (선택)
    mime_type: str = "image/png"   # 이미지 MIME 타입
    rag_context: list[str] = []    # n8n RAG 노드에서 보내주는 강의자료 컨텍스트
    rag_enabled: bool = True       # RAG 컨텍스트 주입 on/off
    model: str | None = None       # 사용할 Gemini 모델. None이면 서버 디폴트.
```

- [ ] **Step 3: `/models` 엔드포인트 추가**

`server.py:78`의 `/schema` 엔드포인트 정의 직후 (즉 `@app.get("/schema")` 함수 아래, `@app.post("/solve")` 위) 에 다음 블록을 삽입:

```python
@app.get("/models")
async def models():
    """사용 가능한 Gemini 모델 목록과 디폴트 모델 반환.

    웹 UI 드롭다운이 페이지 로드 시 호출한다.
    """
    return {
        "models": AVAILABLE_MODELS,
        "default": GEMINI_MODEL,
    }
```

- [ ] **Step 4: `/solve` 핸들러에 검증 + 모델 전달 로직 추가**

`server.py:81-121`의 `solve` 함수 전체를 다음으로 교체:

```python
@app.post("/solve", response_model=SolveResponse)
async def solve(req: SolveRequest):
    """문제 풀이 API (JSON).

    n8n HTTP Request 노드에서 호출:
    - question + image → 기본 풀이
    - question + image + rag_context → 강의자료 기반 풀이
    - model 필드로 사용 모델 지정 (생략 시 서버 디폴트)
    """
    # 모델 검증 (조용히 fallback하면 디버깅 어려움)
    if req.model is not None and req.model not in AVAILABLE_MODELS:
        return SolveResponse(
            success=False,
            answer="",
            error=f"unknown model: {req.model}. available: {AVAILABLE_MODELS}",
        )

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
                model=req.model,
            )
        elif image_bytes:
            result = solve_with_image_bytes(
                req.question, image_bytes, req.mime_type, model=req.model
            )
        else:
            result = solve_text(req.question, model=req.model)

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
```

변경 핵심:
- 첫 부분에서 모델 화이트리스트 검증 (try 블록 밖) — Gemini API 호출 전에 거부
- 세 호출 분기 모두에 `model=req.model` 전달

- [ ] **Step 5: 서버 부팅 검증**

```bash
cd /home/cocapanic/다운로드/project/ee-solver
.venv/bin/python -c "from server import app; print('server import OK')"
```

기대 출력:
```
server import OK
```

- [ ] **Step 6: 서버 실행**

새 터미널 (또는 백그라운드)에서:

```bash
cd /home/cocapanic/다운로드/project/ee-solver
.venv/bin/uvicorn server:app --port 8100
```

다음 task들이 끝날 때까지 계속 실행된다. 서버가 부팅되면 `Application startup complete.` 같은 메시지가 보인다.

- [ ] **Step 7: `/models` 엔드포인트 검증**

```bash
curl -s http://localhost:8100/models
```

기대 출력 (정확히):
```json
{"models":["gemini-3-flash-preview","gemini-3.1-flash-lite-preview"],"default":"gemini-3-flash-preview"}
```

- [ ] **Step 8: 잘못된 모델명에 대한 400 검증**

```bash
curl -s -X POST http://localhost:8100/solve \
  -H "Content-Type: application/json" \
  -d '{"question":"1+1","model":"gpt-4"}'
```

기대 출력에 다음이 포함:
```
"success":false
"unknown model: gpt-4"
```

(중요: 이 호출은 Gemini API를 부르지 않고 검증 단계에서 거부되므로, 실제 API 키 없이도 동작한다.)

- [ ] **Step 9: 모델 필드 없이 호출 (디폴트 사용 경로)**

이 단계는 실제 `GEMINI_API_KEY`가 설정돼 있을 때만 의미가 있다. 키가 있으면:

```bash
curl -s -X POST http://localhost:8100/solve \
  -H "Content-Type: application/json" \
  -d '{"question":"1+1을 계산해줘"}'
```

기대: `"success":true`, 답변에 "2" 포함. (API 키 없이는 `success:false` + Gemini 에러 메시지가 나오지만, 검증 로직은 통과했다는 점에서 기대 동작이다.)

- [ ] **Step 10: 커밋**

```bash
git add server.py
git commit -m "server: /models 엔드포인트 추가, SolveRequest에 model 필드 + 검증"
```

---

## Task 4: static/index.html — 드롭다운 UI + /models fetch + localStorage

**목표:** 웹 UI 상단에 모델 선택 드롭다운을 추가하고, 페이지 로드 시 `/models`로 옵션을 채우며, 사용자 선택을 localStorage로 기억한 후 `/solve` 호출 body에 포함시킨다. 이 task가 끝난 시점에 기능이 사용자에게 노출된다.

**Files:**
- Modify: `static/index.html` (CSS 한 블록 추가, HTML 한 블록 추가, JS 두 곳 추가)

- [ ] **Step 1: 드롭다운용 CSS 추가**

`static/index.html`에서 `.input-section` 스타일 정의 (대략 59~65줄) 직후, `.question-input` 정의 직전에 다음 블록을 삽입:

```css
    .model-select-row {
      display: flex;
      align-items: center;
      gap: 0.75rem;
      margin-bottom: 1rem;
    }
    .model-select-label {
      font-size: 0.85rem;
      color: var(--text-muted);
      font-weight: 500;
    }
    .model-select {
      flex: 1;
      max-width: 320px;
      background: var(--bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 0.5rem 0.75rem;
      color: var(--text);
      font-size: 0.85rem;
      font-family: 'JetBrains Mono', 'Fira Code', monospace;
      cursor: pointer;
      transition: border-color 0.2s;
    }
    .model-select:focus {
      outline: none;
      border-color: var(--primary);
    }
```

- [ ] **Step 2: 드롭다운 HTML 추가**

`static/index.html`의 `<textarea class="question-input" ...>` 바로 위에 다음 블록을 삽입 (대략 303줄 직전):

```html
      <div class="model-select-row">
        <label class="model-select-label" for="modelSelect">모델</label>
        <select class="model-select" id="modelSelect">
          <option value="">로딩 중...</option>
        </select>
      </div>

```

(끝에 빈 줄 한 칸 포함 — `<textarea>` 와 시각적으로 분리)

- [ ] **Step 3: JS 변수 선언 추가**

`static/index.html`에서 `const calcItems = document.getElementById('calcItems');` 줄 (대략 363줄) 바로 다음 줄에 다음을 추가:

```javascript
    const modelSelect = document.getElementById('modelSelect');
    const MODEL_STORAGE_KEY = 'ee-solver-model';
```

- [ ] **Step 4: 모델 목록 로드 함수 추가**

`static/index.html`에서 `let selectedFile = null;` 줄 (대략 365줄) 바로 다음 빈 줄에 다음 함수 블록을 추가:

```javascript

    // ── 모델 목록 로드 ──
    async function loadModels() {
      // 서버 호출 실패 시 사용할 fallback (페이지가 망가지지 않도록)
      const FALLBACK_MODELS = [
        'gemini-3-flash-preview',
        'gemini-3.1-flash-lite-preview',
      ];
      const FALLBACK_DEFAULT = 'gemini-3-flash-preview';

      let models = FALLBACK_MODELS;
      let defaultModel = FALLBACK_DEFAULT;

      try {
        const res = await fetch('/models');
        if (res.ok) {
          const data = await res.json();
          if (Array.isArray(data.models) && data.models.length > 0) {
            models = data.models;
            defaultModel = data.default || data.models[0];
          }
        } else {
          console.warn('GET /models failed, using fallback list');
        }
      } catch (err) {
        console.warn('GET /models error, using fallback list:', err);
      }

      // 드롭다운 채우기
      modelSelect.innerHTML = models
        .map((m) => `<option value="${m}">${m}</option>`)
        .join('');

      // localStorage에 저장된 마지막 선택이 현재 목록에 있으면 사용, 아니면 디폴트
      const stored = localStorage.getItem(MODEL_STORAGE_KEY);
      modelSelect.value = stored && models.includes(stored) ? stored : defaultModel;
    }

    // 이 <script> 태그는 body 끝에 있어 위쪽 DOM은 모두 파싱돼 있으므로 즉시 호출 가능
    loadModels();

```

- [ ] **Step 5: 드롭다운 변경 핸들러 등록**

`static/index.html`의 `// ── Ctrl+Enter 전송 ──` 주석 (대략 416줄) 바로 위에 다음 블록을 추가:

```javascript

    // ── 모델 변경 시 localStorage 저장 ──
    modelSelect.addEventListener('change', () => {
      if (modelSelect.value) {
        localStorage.setItem(MODEL_STORAGE_KEY, modelSelect.value);
      }
    });

```

- [ ] **Step 6: `submitSolve`의 body에 model 추가**

`static/index.html`의 `submitSolve` 함수 안에서 (대략 452줄):

기존:
```javascript
      const body = { question };
      if (selectedFile) {
        body.image = await fileToBase64(selectedFile);
        body.mime_type = selectedFile.type || 'image/png';
      }
```

다음으로 교체:
```javascript
      const body = { question };
      if (modelSelect.value) {
        body.model = modelSelect.value;
      }
      if (selectedFile) {
        body.image = await fileToBase64(selectedFile);
        body.mime_type = selectedFile.type || 'image/png';
      }
```

- [ ] **Step 7: 브라우저에서 수동 검증 — 페이지 로드 + 드롭다운**

`http://localhost:8100`을 브라우저에서 새로고침. 다음을 확인:

1. 모델 드롭다운이 `질문` 입력칸 위에 보임
2. 드롭다운 옵션이 두 개: `gemini-3-flash-preview`, `gemini-3.1-flash-lite-preview`
3. 디폴트로 `gemini-3-flash-preview`가 선택됨
4. 브라우저 DevTools → Network 탭에서 새로고침하면 `GET /models` 요청이 200으로 보임

만약 1~3 중 어느 것이라도 깨지면 console에 에러가 있는지 확인. fallback 경로가 동작하면 옵션은 보여야 한다.

- [ ] **Step 8: 브라우저에서 수동 검증 — localStorage 기억**

1. 드롭다운에서 `gemini-3.1-flash-lite-preview` 선택
2. DevTools → Application → Local Storage → `http://localhost:8100`에서 `ee-solver-model` 키가 그 값으로 저장됨 확인
3. 페이지 새로고침 (F5)
4. 드롭다운이 여전히 `gemini-3.1-flash-lite-preview`로 선택돼있음 확인
5. 다시 `gemini-3-flash-preview`로 바꾸고 → 새로고침 → 그 값이 유지되는지 확인

- [ ] **Step 9: 브라우저에서 수동 검증 — 풀이 요청에 model 포함**

1. 질문 입력 (예: "1+1을 계산해줘")
2. DevTools → Network 탭 열어둔 상태로 `풀이 시작` 클릭
3. `POST /solve` 요청을 클릭 → Request Payload (또는 Request body) 에서 `model` 필드에 현재 드롭다운 값이 들어가 있는지 확인

(실제 응답이 성공하려면 `GEMINI_API_KEY`가 설정돼야 한다. 키가 없으면 응답은 실패하지만 요청 body에 `model` 필드가 있는지만 확인하면 이 step의 목적은 달성.)

- [ ] **Step 10: end-to-end 검증 (API 키 있을 때)**

`GEMINI_API_KEY`가 설정돼 있으면 두 모델로 같은 질문을 던져 응답 차이를 확인:

1. `gemini-3-flash-preview` 선택 → "옴의 법칙을 한 줄로 설명해줘" → 응답 받기
2. `gemini-3.1-flash-lite-preview` 선택 → 같은 질문 → 응답 받기
3. 두 응답이 (이상적으로는) 다르거나 적어도 둘 다 정상 응답해야 함

만약 둘 중 한 모델이 Gemini API 자체에서 reject되면 (모델명이 실존하지 않는 경우 등), `success: false` + Gemini 에러 메시지가 보임. 이 경우 모델명을 다시 확인.

- [ ] **Step 11: 커밋**

```bash
git add static/index.html
git commit -m "ui: 모델 선택 드롭다운 추가 (localStorage 기억 + /models fetch)"
```

---

## 완료 후

모든 task가 끝나면:

- [ ] 서버를 끄고 재시작해서 깨끗한 상태에서 한 번 더 페이지를 열고 드롭다운이 정상 동작하는지 확인
- [ ] `git log --oneline -5`로 4개 커밋이 모두 들어갔는지 확인
- [ ] 필요하면 README의 `기능` 섹션에 "모델 선택 (gemini-3-flash-preview / gemini-3.1-flash-lite-preview)" 한 줄 추가 — 이건 plan 외 작업이지만 자연스러운 후속 작업

## YAGNI 체크 (재확인)

이 plan에 들어가지 않은 것들:
- 모델별 표시명 / 가격 / 설명 메타데이터
- 모델 추가/삭제 관리 UI
- CLI(`solve.py`) `--model` 플래그
- 사용자별 디폴트 모델 서버 저장
- 자동 테스트 인프라 (pytest 등)

필요해지면 별도 plan으로 추가한다.
