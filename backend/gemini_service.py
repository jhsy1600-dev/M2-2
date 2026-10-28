import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai


# 프로젝트 루트 경로
# 현재 파일 위치 예시: backend/gemini_service.py
BASE_DIR = Path(__file__).resolve().parent.parent

# .env 파일 로드
ENV_PATH = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH)

# Gemini API 키 가져오기
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY가 .env 파일에 설정되어 있지 않습니다.")

# Gemini 클라이언트 생성
client = genai.Client(api_key=GEMINI_API_KEY)

# 사용할 Gemini 모델
# 중요:
# 기존 코드의 "models/gemini-3.8-flash"에서 "models/"는 제거했습니다.
# 만약 모델 오류가 나면 "gemini-1.5-flash" 또는 사용 가능한 모델명으로 바꿔야 합니다.
MODEL_NAME = "gemini-3.8-flash"

print(f"현재 사용 중인 Gemini 모델: {MODEL_NAME}")


def ask_gemini(prompt: str) -> str:
    """
    main.py에서 만든 프롬프트를 Gemini에게 보내고 답변을 반환하는 함수
    """

    if not prompt or not prompt.strip():
        return "메시지가 비어 있습니다. 질문을 입력해주세요."

    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt
        )

        if hasattr(response, "text") and response.text:
            return response.text

        return "Gemini 응답이 비어 있습니다."

    except Exception as e:
        raise Exception(f"Gemini API 호출 중 오류가 발생했습니다: {str(e)}")