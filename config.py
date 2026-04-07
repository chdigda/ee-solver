"""EE-Solver 설정 모듈."""

import os
from pathlib import Path
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv(Path(__file__).parent / ".env")

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

# 출력 디렉토리
OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# 결과 파일 경로
RESULT_FILE = OUTPUT_DIR / "result.md"
