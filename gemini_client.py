"""Gemini API 클라이언트 모듈.

Phase 1: 텍스트 질문 → Gemini → 텍스트 답변
Phase 2: 이미지(회로도) 지원 추가
Phase 3: Function Calling + MCP Calculator tool loop
"""

import mimetypes
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
너는 전기공학 문제 풀이 전문가다.

규칙:
- 모든 수치 계산은 반드시 제공된 도구(calculate, solve_equation 등)를 사용해라.
  절대 암산하지 마라.
- 풀이 과정을 단계별로 보여줘라.
- 사용한 법칙/정리의 이름을 명시해라.
- 최종 답은 명확하게 표시해라.
"""

# 계산 기록 저장
calculation_log: list[dict] = []


def _get_config() -> genai.types.GenerateContentConfig:
    """Gemini 호출용 공통 설정을 반환한다."""
    return genai.types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        tools=[genai.types.Tool(function_declarations=TOOL_DECLARATIONS)],
    )


def _execute_tool_call(function_call) -> str:
    """Gemini의 tool_call을 받아 MCP 도구 함수를 실행한다."""
    func_name = function_call.name
    func_args = dict(function_call.args) if function_call.args else {}

    func = TOOL_FUNCTIONS.get(func_name)
    if not func:
        return f"알 수 없는 도구: {func_name}"

    result = func(**func_args)

    # 계산 기록 저장
    calculation_log.append({
        "tool": func_name,
        "args": func_args,
        "result": result,
    })
    print(f"  🔧 {func_name}({func_args}) → {result}")
    return result


def _tool_loop(response, contents: list) -> str:
    """Gemini 응답에 tool_call이 있으면 실행 후 재전달하는 루프.

    Returns:
        최종 텍스트 답변
    """
    max_iterations = 20

    for _ in range(max_iterations):
        # 모든 parts에서 function_call 찾기
        parts = response.candidates[0].content.parts
        function_calls = [p for p in parts if p.function_call]

        if not function_calls:
            # tool_call 없음 → 최종 답변
            return response.text

        # 모델 응답을 contents에 추가
        contents.append(response.candidates[0].content)

        # 모든 tool_call 실행 후 응답 전달
        response_parts = []
        for part in function_calls:
            fc = part.function_call
            tool_result = _execute_tool_call(fc)
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
            model=GEMINI_MODEL,
            contents=contents,
            config=_get_config(),
        )

    return response.text


def solve_text(question: str) -> str:
    """텍스트 질문을 Gemini에 전달하고 답변을 받는다 (도구 사용 포함)."""
    calculation_log.clear()

    contents = [question]
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=contents,
        config=_get_config(),
    )
    return _tool_loop(response, contents)


def solve_with_image(question: str, image_path: str) -> str:
    """텍스트 질문 + 이미지를 Gemini에 전달하고 답변을 받는다 (도구 사용 포함)."""
    calculation_log.clear()

    path = Path(image_path)
    mime_type = mimetypes.guess_type(path.name)[0] or "image/png"
    image_data = path.read_bytes()

    contents = [
        genai.types.Part.from_bytes(data=image_data, mime_type=mime_type),
        question,
    ]
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=contents,
        config=_get_config(),
    )
    return _tool_loop(response, contents)


def solve_with_image_bytes(
    question: str, image_bytes: bytes, mime_type: str
) -> str:
    """텍스트 질문 + 이미지 바이트를 Gemini에 전달한다 (웹 업로드용)."""
    calculation_log.clear()

    contents = [
        genai.types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
        question,
    ]
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=contents,
        config=_get_config(),
    )
    return _tool_loop(response, contents)
