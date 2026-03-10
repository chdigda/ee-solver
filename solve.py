"""EE-Solver CLI 진입점.

사용법:
    python solve.py "옴의 법칙을 설명해줘"
    python solve.py "이 회로에서 전류를 구해라" --image circuit.png
"""

import argparse
import sys

from pathlib import Path

from config import GEMINI_API_KEY, RESULT_FILE
from gemini_client import calculation_log, solve_text, solve_with_image


def save_result(answer: str) -> None:
    """결과를 output/result.md에 저장한다."""
    RESULT_FILE.write_text(answer, encoding="utf-8")
    print(f"\n📄 결과 저장: {RESULT_FILE}")


def main() -> None:
    parser = argparse.ArgumentParser(description="EE-Solver: 전기공학 문제 풀이")
    parser.add_argument("question", help="풀이할 질문")
    parser.add_argument("--image", "-i", help="회로도 이미지 파일 경로")

    args = parser.parse_args()

    # API 키 확인
    if not GEMINI_API_KEY:
        print("❌ GEMINI_API_KEY가 설정되지 않았습니다.")
        print("   .env 파일에 GEMINI_API_KEY=your_key 를 추가하세요.")
        sys.exit(1)

    print(f"🔍 질문: {args.question}")
    if args.image:
        if not Path(args.image).exists():
            print(f"❌ 이미지 파일을 찾을 수 없습니다: {args.image}")
            sys.exit(1)
        print(f"🖼️  이미지: {args.image}")
    print("⏳ Gemini에 질문 중...\n")

    try:
        if args.image:
            answer = solve_with_image(args.question, args.image)
        else:
            answer = solve_text(args.question)
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        sys.exit(1)

    # 터미널 출력
    print("=" * 60)
    print(answer)
    print("=" * 60)

    # MCP 계산 기록 출력
    if calculation_log:
        print(f"\n📊 MCP 계산 기록 ({len(calculation_log)}건):")
        for i, log in enumerate(calculation_log, 1):
            print(f"  {i}. {log['tool']}({log['args']}) → {log['result']}")

    # 파일 저장
    save_result(answer)


if __name__ == "__main__":
    main()
