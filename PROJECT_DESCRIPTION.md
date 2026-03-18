# ?조

## 주제
Gemini AI 기반 전기공학 문제 풀이 서비스 (EE-Solver)

## 조장
김도은

## 조원
김휘중, 김민찬, 김현준

---

## 개요

회로도 사진과 문제를 입력받아 단계별 풀이와 정확한 수치 계산을 제공하는 AI 기반 서비스이다. Google Gemini의 멀티모달 기능으로 문제를 이해하고, MCP 기반 계산기로 정밀한 수치 연산을 수행한다. JSON 스키마 기반의 표준화된 입출력을 지원하여 n8n 등 외부 자동화 도구와 손쉽게 연동할 수 있으며, REST API와 Android 앱을 통해 실제 사용자에게 서비스를 제공한다. 향후 전기공학부 강의자료를 RAG(Retrieval-Augmented Generation)로 연동하여, 교수님의 강의 내용에 기반한 풀이를 제공할 계획이다.

---

## 시스템 구성

사용자가 문제(텍스트 및 회로도 이미지)를 입력하면, EE-Solver API 서버가 JSON 형식으로 요청을 수신한다. 요청에는 문제 본문, 이미지, 그리고 외부에서 전처리된 RAG 참고자료가 포함될 수 있다. Google Gemini 2.5 Pro가 이 정보를 종합하여 풀이를 수행하며, 모든 수치 계산(옴의 법칙, 행렬 연산, 복소수 계산 등)은 MCP(Model Context Protocol) 기반의 sympy 계산기 서버를 통해 처리하여 계산 정확도를 보장한다. 최종적으로 단계별 풀이 과정, 계산 결과, 참고한 강의 내용을 JSON으로 구조화하여 반환한다.

n8n과의 연동은 JSON 입출력 스키마를 통해 이루어진다. n8n 워크플로우에서 RAG 전처리 결과를 JSON으로 EE-Solver에 전달하고, EE-Solver의 JSON 응답을 후속 노드에서 자유롭게 가공할 수 있다.

---

## 핵심 기능

### 1. 멀티모달 문제 인식
핸드폰 카메라 또는 스크린샷으로 촬영한 회로도, 수식, 문제지를 이미지로 전송하면, Gemini의 멀티모달 기능을 통해 회로 구성요소와 문제 조건을 자동으로 인식한다.

### 2. 강의자료 RAG 연동
교수님의 강의자료(PDF, 노트 등)를 외부에서 벡터DB에 임베딩하고, 검색된 관련 이론(키르히호프 법칙, 테브난 정리, 노턴 정리 등)을 JSON 형태로 EE-Solver에 전달하면 풀이에 반영한다. RAG 기능은 on/off 전환이 가능하여, 순수 AI 풀이와 강의자료 기반 풀이를 비교할 수 있다.

### 3. MCP 기반 정밀 계산
LLM의 수치 계산 오류를 방지하기 위해 모든 연산을 MCP 프로토콜 기반 계산기 서버에 위임한다. sympy 엔진을 사용하여 기호 연산, 복소수 계산, 행렬 풀이, 단위 변환 등을 정확하게 수행한다.

### 4. JSON 스키마 기반 표준 입출력
입력과 출력이 명확한 JSON 스키마로 정의되어 있어, n8n 워크플로우의 HTTP Request 노드, 웹 프론트엔드, 모바일 앱 등 다양한 클라이언트에서 동일한 인터페이스로 호출할 수 있다.

---

## 입출력 스키마

### 입력 (POST /solve)
```json
{
  "question": "이 회로에서 테브난 등가회로를 구하시오",
  "image": "base64 인코딩된 이미지 (선택)",
  "mime_type": "image/png"
}
```

### 출력 (Response)
```json
{
  "success": true,
  "answer": "테브난 등가전압 Vth = 5V, 등가저항 Rth = 2.5옴 ...(전체 마크다운 풀이)",
  "solution_steps": [
    "1. 부하 저항 R3를 제거하고 개방 전압 Vth를 구한다.",
    "2. 전압 분배 법칙 적용: Vth = 10 × R2/(R1+R2) = 5V",
    "3. 독립전원 제거 후 등가저항: Rth = R1∥R2 = 2.5옴"
  ],
  "calculations": [
    {"tool": "calculate", "args": {"expression": "10 * 5 / (5 + 5)"}, "result": "5"},
    {"tool": "calculate", "args": {"expression": "1 / (1/5 + 1/5)"}, "result": "2.5"}
  ],
  "error": null
}
```

---

## 서비스 제공 방식

| 방식 | 설명 |
|------|------|
| REST API | FastAPI 기반 `/solve` 엔드포인트. JSON 스키마로 통신하여 n8n, 웹 등 외부 서비스에서 HTTP로 호출 |
| Android APK | 간단한 Android 앱에서 사진 촬영 → 문제 전송 → 풀이 결과 확인. 학생들이 일상적으로 사용 가능 |

---

## 기술 스택

| 구성요소 | 기술 | 비고 |
|----------|------|------|
| 언어 | Python 3.14 | |
| AI 모델 | Google Gemini 2.5 Pro | `google-genai` SDK, 멀티모달 + Function Calling |
| API 서버 | FastAPI + Uvicorn | Pydantic 모델로 JSON 스키마 정의 |
| 수학 계산 | sympy | 기호 연산, 복소수, 행렬, 방정식 |
| MCP | `mcp` python SDK + `FastMCP` | 현재 직접 호출, stdio 분리 예정 |
| 웹 GUI | HTML + CSS + JS | Marked.js (마크다운), KaTeX (수식 렌더링) |
| 데이터 형식 | JSON (base64 이미지 포함) | 입출력 Pydantic 스키마 |
| 외부 연동 | n8n HTTP Request 노드 | JSON 기반 파이프라인 |
| 모바일 | Android (Kotlin/Jetpack Compose) | 예정 |

---

## 개발 일정

| 단계 | 내용 | 상태 |
|------|------|------|
| Phase 1 | Gemini API 텍스트 호출 기본 동작 | ✅ 완료 |
| Phase 2 | 이미지(회로도) 입력 지원 | ✅ 완료 |
| Phase 3 | Calculator 서버 구축 (sympy, 직접 호출) | ✅ 완료 |
| Phase 4 | FastAPI 서버화 + 웹 GUI (JSON 스키마) | ✅ 완료 |
| Phase 5 | MCP stdio transport 분리 | 예정 |
| Phase 6 | n8n 연동 테스트 | 예정 |
| Phase 7 | Android APK 개발 | 예정 |

---

## 기대 효과

전기공학부 학생들이 회로 문제를 사진으로 찍어 전송하면, 강의자료에 기반한 정확한 단계별 풀이를 즉시 받아볼 수 있다. 단순 답만 제공하는 것이 아니라, 어떤 법칙을 적용했는지, 계산 과정이 어떻게 되는지를 명시하여 학습 보조 도구로 활용할 수 있다.
