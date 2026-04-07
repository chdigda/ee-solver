"""Gemini API 클라이언트 모듈.

Phase 1: 텍스트 질문 → Gemini → 텍스트 답변
Phase 2: 이미지(회로도) 지원 추가
Phase 3: Function Calling + MCP Calculator tool loop
"""

import mimetypes
import re
from dataclasses import dataclass, field
from pathlib import Path

from google import genai

from config import GEMINI_API_KEY, GEMINI_MODEL
from mcp_calculator.server import (
    calculate,
    complex_calc,
    matrix_op,
    solve_equation,
    unit_convert,
)

# Gemini 클라이언트 초기화
client = genai.Client(api_key=GEMINI_API_KEY)

# MCP 도구 함수 매핑 (Gemini tool_call name → 실제 함수)
TOOL_FUNCTIONS = {
    "calculate": calculate,
    "solve_equation": solve_equation,
    "matrix_op": matrix_op,
    "unit_convert": unit_convert,
    "complex_calc": complex_calc,
}

# Gemini에 등록할 도구 정의
TOOL_DECLARATIONS = [
    genai.types.FunctionDeclaration(
        name="calculate",
        description="수학 수식을 계산한다. 예: '10 / (2 + 3)', 'sqrt(3) * 5', 'sin(pi/6)'",
        parameters={
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "계산할 수학 수식",
                }
            },
            "required": ["expression"],
        },
    ),
    genai.types.FunctionDeclaration(
        name="solve_equation",
        description="방정식을 풀어 변수의 값을 구한다. 예: equation='2*x + 3 = 7', variable='x'",
        parameters={
            "type": "object",
            "properties": {
                "equation": {
                    "type": "string",
                    "description": "방정식 문자열. 예: '2*x + 3 = 7'",
                },
                "variable": {
                    "type": "string",
                    "description": "풀 변수. 예: 'x'",
                },
            },
            "required": ["equation", "variable"],
        },
    ),
    genai.types.FunctionDeclaration(
        name="matrix_op",
        description="행렬 연산을 수행한다. operation: 'multiply', 'inverse', 'determinant', 'add'",
        parameters={
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "description": "연산 종류: multiply, inverse, determinant, add",
                },
                "matrices": {
                    "type": "string",
                    "description": "JSON 형식의 행렬 데이터. 예: '[[1,2],[3,4]]'",
                },
            },
            "required": ["operation", "matrices"],
        },
    ),
    genai.types.FunctionDeclaration(
        name="unit_convert",
        description="SI 단위 변환. 예: value=1000, from_unit='mA', to_unit='A'",
        parameters={
            "type": "object",
            "properties": {
                "value": {"type": "number", "description": "변환할 값"},
                "from_unit": {
                    "type": "string",
                    "description": "원래 단위. 예: 'mA', 'kV', 'uF'",
                },
                "to_unit": {
                    "type": "string",
                    "description": "변환할 단위. 예: 'A', 'V', 'F'",
                },
            },
            "required": ["value", "from_unit", "to_unit"],
        },
    ),
    genai.types.FunctionDeclaration(
        name="complex_calc",
        description="복소수 연산. 예: '(3+4j) * (1-2j)', 'abs(3+4j)'",
        parameters={
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "복소수 수식. 허수 단위는 j 사용",
                }
            },
            "required": ["expression"],
        },
    ),
]

# 시스템 프롬프트
SYSTEM_PROMPT = """\
You are a professor-level Electrical Engineering problem solver.
You handle all EE domains: circuit theory, electromagnetics, signals & systems, power engineering, and electronics.
Answer in Korean. Write all math formulas in LaTeX ($...$, $$...$$).

====== STEP-BY-STEP SOLVING PROCEDURE ======

You MUST follow these steps in order. Never skip a step.

Step 1 - Analyze the Problem
- List all Given values with units (e.g., $V_s = 10\\,\\text{V}$, $R_1 = 5\\,\\text{k}\\Omega$).
- State what you need to Find (e.g., "Find $I_2$ and $V_{out}$").
- If a circuit image is provided, read every component value, source polarity, node label, and ground symbol carefully. If any part is unclear, state what is ambiguous.

Step 2 - Choose a Strategy
- Decide which law/theorem to apply and explain WHY in one sentence.
- Strategy examples:
  - DC resistive: series/parallel simplification, Ohm's law, voltage/current divider
  - Complex DC: KVL/KCL simultaneous equations, node-voltage method, mesh-current method
  - Equivalent circuits: Thevenin / Norton (open-circuit voltage, equivalent resistance)
  - Superposition: activate one independent source at a time, sum responses
  - AC steady-state: phasor transform, impedance analysis, inverse transform
  - Transient: set initial conditions, solve ODE or use Laplace transform
  - Op-Amp: ideal conditions ($V^+ = V^-$, $I_{in} = 0$), KCL at input nodes
  - Power: $P = VI$, $P = I^2R$, $P = V^2/R$, power factor, complex power

Step 3 - Solve (show every substep)
- Number each substep (1, 2, 3, ...).
- State the law/theorem name when you apply it (e.g., Ohm's Law).
- Define every symbol on first use (e.g., "$R_1$: the 10 ohm resistor").
- Attach physical meaning and units to every intermediate result (e.g., "$I_1 = 2\\,\\text{A}$ (current through $R_1$)").

Step 4 - Verify
- Check at least one of the following:
  - KVL: loop voltage sum = 0
  - KCL: node current sum = 0
  - Power balance: supplied power = consumed power
  - Dimensional analysis: units are consistent
  - Sanity check: result is physically reasonable
- Use the calculator tools for verification calculations too.

Step 5 - Final Answer
- Present the final answer clearly in a box:
  $$\\boxed{\\text{Answer} = \\text{value}\\;\\text{unit}}$$
- If there are multiple answers, list all of them.

====== CALCULATION RULES (CRITICAL) ======

You have access to a Python/SymPy calculator through function-call tools.
NEVER do mental arithmetic. ALWAYS call a tool for ANY numerical computation.

Use the right tool for each job:
| Task | Tool | Example |
|------|------|---------|
| Arithmetic, powers, trig, roots | calculate | calculate("10 / (2 + 3)") |
| Solve equations / simultaneous eq. | solve_equation | solve_equation("2*x + 3 = 7", "x") |
| Matrix operations (node/mesh analysis) | matrix_op | matrix_op("inverse", "[[1,2],[3,4]]") |
| SI prefix conversion | unit_convert | unit_convert(4.7, "kOhm", "Ohm") |
| Complex number / phasor math | complex_calc | complex_calc("(3+4j) * (1-2j)") |

Tips:
- Convert all values to base SI units FIRST using unit_convert before plugging into formulas.
- For simultaneous equations, set up each equation with solve_equation, or use matrix_op for the matrix form [A][x] = [b].
- For AC phasors, use complex_calc for all impedance and phasor arithmetic.

====== RAG CONTEXT RULES ======

If reference lecture materials are provided:
- Prioritize the methods and formulas from the lecture materials.
- Follow the notation and terminology used in the materials.
- When citing, start with "강의자료에 따르면...".
"""

# Gemini 호출 설정 (모듈 레벨에서 1회 생성)
_GEMINI_CONFIG = genai.types.GenerateContentConfig(
    system_instruction=SYSTEM_PROMPT,
    tools=[genai.types.Tool(function_declarations=TOOL_DECLARATIONS)],
)


@dataclass
class SolveResult:
    """풀이 결과를 담는 컨테이너. 요청별로 독립적."""
    answer: str = ""
    solution_steps: list[str] = field(default_factory=list)
    calculation_log: list[dict] = field(default_factory=list)


def _parse_steps(text: str) -> list[str]:
    """Gemini 응답에서 번호 매긴 풀이 단계를 추출한다."""
    steps = []
    step_pattern = re.compile(r"^\s*\**\s*(?:단계\s*)?\d+[\.\)]\**\s*:?\s*(.+)")

    for line in text.split("\n"):
        if step_pattern.match(line):
            step_text = line.strip().lstrip("*").strip()
            steps.append(step_text)

    return steps


def _execute_tool_call(function_call, result: SolveResult) -> str:
    """Gemini의 tool_call을 받아 MCP 도구 함수를 실행한다."""
    func_name = function_call.name
    func_args = dict(function_call.args) if function_call.args else {}

    func = TOOL_FUNCTIONS.get(func_name)
    if not func:
        return f"알 수 없는 도구: {func_name}"

    tool_result = func(**func_args)

    result.calculation_log.append({
        "tool": func_name,
        "args": func_args,
        "result": tool_result,
    })
    print(f"  [tool] {func_name}({func_args}) -> {tool_result}")
    return tool_result


def _extract_text_from_parts(parts: list) -> str:
    """parts에서 텍스트 조각을 안전하게 합쳐 반환한다."""
    text_chunks = [p.text for p in parts if getattr(p, "text", None)]
    return "\n".join(text_chunks).strip()


def _tool_loop(response, contents: list, result: SolveResult, model: str) -> str:
    """Gemini 응답에 tool_call이 있으면 실행 후 재전달하는 루프."""
    max_iterations = 20

    for i in range(max_iterations):
        candidates = response.candidates or []
        if not candidates:
            return response.text or "[모델이 후보 응답을 비워 반환했습니다.]"

        candidate = candidates[0]
        parts = (candidate.content.parts if candidate.content else None) or []
        function_calls = [p for p in parts if getattr(p, "function_call", None)]

        if not function_calls:
            if response.text:
                return response.text

            part_text = _extract_text_from_parts(parts)
            if part_text:
                return part_text

            finish_reason = getattr(candidate, "finish_reason", None)
            return (
                "[모델이 빈 응답을 반환했습니다. "
                f"finish_reason={finish_reason}]"
            )

        if candidate.content:
            contents.append(candidate.content)

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
    if response.text:
        return response.text

    candidates = response.candidates or []
    if not candidates:
        return ""

    parts = (candidates[0].content.parts if candidates[0].content else None) or []
    return _extract_text_from_parts(parts)


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


def solve_text(question: str, model: str | None = None) -> SolveResult:
    """텍스트 질문을 Gemini에 전달하고 답변을 받는다."""
    return _solve([question], model=model)


def solve_with_image(
    question: str, image_path: str, model: str | None = None
) -> SolveResult:
    """텍스트 질문 + 이미지 파일을 Gemini에 전달한다."""
    path = Path(image_path)
    mime_type = mimetypes.guess_type(path.name)[0] or "image/png"
    return solve_with_image_bytes(question, path.read_bytes(), mime_type, model=model)


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
