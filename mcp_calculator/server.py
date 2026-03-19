"""MCP Calculator Server — sympy 기반 수학 계산 도구 서버.

5개 도구 제공:
  - calculate: 수식 계산
  - solve_equation: 방정식 풀이
  - matrix_op: 행렬 연산
  - unit_convert: 단위 변환
  - complex_calc: 복소수 연산

실행: python -m mcp_calculator.server (stdio transport)
"""

import json
import re

import sympy as sp
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("ee-calculator")

# SI 접두사 배율 (모듈 레벨)
_PREFIX_MAP = {
    "T": 1e12, "G": 1e9, "M": 1e6, "k": 1e3, "": 1,
    "m": 1e-3, "u": 1e-6, "μ": 1e-6, "n": 1e-9, "p": 1e-12,
}
_SORTED_PREFIXES = sorted(
    (p for p in _PREFIX_MAP if p), key=len, reverse=True
)


def _parse_unit(unit_str: str) -> tuple[str, str]:
    """접두사와 기본 단위를 분리한다."""
    for prefix in _SORTED_PREFIXES:
        if unit_str.startswith(prefix):
            return prefix, unit_str[len(prefix):]
    return "", unit_str


# ── Tool 1: calculate ──────────────────────────────────────
@mcp.tool()
def calculate(expression: str) -> str:
    """수학 수식을 계산한다.

    Args:
        expression: 계산할 수식. 예: "10 / (2 + 3)", "sqrt(3) * 5", "sin(pi/6)"
    """
    try:
        result = sp.sympify(expression, rational=True)
        evaluated = result.evalf()
        if evaluated.is_real and evaluated == int(evaluated):
            return str(int(evaluated))
        return str(evaluated)
    except Exception as e:
        return f"계산 오류: {e}"


# ── Tool 2: solve_equation ─────────────────────────────────
@mcp.tool()
def solve_equation(equation: str, variable: str) -> str:
    """방정식을 풀어 변수의 값을 구한다.

    Args:
        equation: 방정식 문자열. 예: "2*x + 3 = 7", "x**2 - 4 = 0"
        variable: 풀 변수. 예: "x"
    """
    try:
        var = sp.Symbol(variable)
        # "a = b" → "a - (b)" 형태로 변환
        if "=" in equation:
            lhs, rhs = equation.split("=", 1)
            expr = sp.sympify(lhs.strip(), rational=True) - sp.sympify(
                rhs.strip(), rational=True
            )
        else:
            expr = sp.sympify(equation, rational=True)

        solutions = sp.solve(expr, var)
        if not solutions:
            return "해가 없습니다."
        return str(solutions)
    except Exception as e:
        return f"풀이 오류: {e}"


# ── Tool 3: matrix_op ─────────────────────────────────────
@mcp.tool()
def matrix_op(operation: str, matrices: str) -> str:
    """행렬 연산을 수행한다.

    Args:
        operation: "multiply", "inverse", "determinant", "add" 중 하나
        matrices: JSON 형식의 2D 배열 리스트. 예: "[[1,2],[3,4]]" 또는 "[[[1,2],[3,4]], [[5,6],[7,8]]]"
    """
    try:
        data = json.loads(matrices)

        if operation == "determinant":
            m = sp.Matrix(data)
            return str(m.det())

        elif operation == "inverse":
            m = sp.Matrix(data)
            return str(m.inv().tolist())

        elif operation == "multiply":
            if not isinstance(data[0][0], list):
                return "multiply는 두 개의 행렬이 필요합니다: [matrix1, matrix2]"
            m1 = sp.Matrix(data[0])
            m2 = sp.Matrix(data[1])
            return str((m1 * m2).tolist())

        elif operation == "add":
            if not isinstance(data[0][0], list):
                return "add는 두 개의 행렬이 필요합니다: [matrix1, matrix2]"
            m1 = sp.Matrix(data[0])
            m2 = sp.Matrix(data[1])
            return str((m1 + m2).tolist())

        else:
            return f"지원하지 않는 연산: {operation}"
    except Exception as e:
        return f"행렬 연산 오류: {e}"


# ── Tool 4: unit_convert ──────────────────────────────────
@mcp.tool()
def unit_convert(value: float, from_unit: str, to_unit: str) -> str:
    """단위 변환을 수행한다.

    Args:
        value: 변환할 값
        from_unit: 원래 단위. 예: "mA", "kV", "uF", "MHz"
        to_unit: 변환할 단위. 예: "A", "V", "F", "Hz"
    """
    try:
        from_prefix, from_base = _parse_unit(from_unit)
        to_prefix, to_base = _parse_unit(to_unit)

        if from_base != to_base:
            return f"단위 불일치: {from_base} ≠ {to_base}"

        from_scale = _PREFIX_MAP.get(from_prefix)
        to_scale = _PREFIX_MAP.get(to_prefix)
        if from_scale is None or to_scale is None:
            return f"알 수 없는 접두사: {from_prefix} 또는 {to_prefix}"

        result = value * from_scale / to_scale
        return f"{result} {to_unit}"
    except Exception as e:
        return f"단위 변환 오류: {e}"


# ── Tool 5: complex_calc ──────────────────────────────────
@mcp.tool()
def complex_calc(expression: str) -> str:
    """복소수 연산을 수행한다.

    Args:
        expression: 복소수 수식. 예: "(3+4j) * (1-2j)", "abs(3+4j)"
                    허수 단위는 j 또는 I 사용 가능
    """
    try:
        # 숫자 뒤의 j만 *I로 변환 (함수명 등의 j는 건드리지 않음)
        expr_str = re.sub(r'(\d)j\b', r'\1*I', expression)
        expr_str = re.sub(r'(\d)J\b', r'\1*I', expr_str)
        result = sp.sympify(expr_str, rational=True)
        result = sp.simplify(result)

        re_part = sp.re(result)
        im_part = sp.im(result)

        if im_part == 0:
            return str(re_part)
        elif re_part == 0:
            return f"{im_part}j"
        else:
            sign = "+" if im_part > 0 else "-"
            return f"{re_part} {sign} {abs(im_part)}j"
    except Exception as e:
        return f"복소수 연산 오류: {e}"


# ── 서버 실행 ──────────────────────────────────────────────
if __name__ == "__main__":
    mcp.run(transport="stdio")
