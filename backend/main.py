from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from firebase_admin import firestore

# Firestore 연결 객체 가져오기
from firebase_db import db

# Gemini 호출 함수 가져오기
from gemini_service import ask_gemini


app = FastAPI(title="학습시간 데이터 기반 AI 비서 API")


# =========================
# CORS 설정
# =========================
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================
# Firestore 컬렉션 이름
# =========================
COLLECTION_NAME = "study_records"
CONVERSATION_COLLECTION = "conversations"


# =========================
# 요청 모델
# =========================
class DataCreate(BaseModel):
    date: str
    subject: str
    minutes: int
    memo: Optional[str] = None


class DataUpdate(BaseModel):
    date: Optional[str] = None
    subject: Optional[str] = None
    minutes: Optional[int] = None
    memo: Optional[str] = None


class ConversationCreate(BaseModel):
    user_message: str
    ai_message: Optional[str] = None
    ai_response: Optional[str] = None


class AIRequest(BaseModel):
    message: str = "내 학습 데이터를 분석해줘."


# =========================
# 공통 함수
# =========================

# Pydantic v1/v2 호환용
def model_to_dict(model, **kwargs):
    if hasattr(model, "model_dump"):
        return model.model_dump(**kwargs)
    return model.dict(**kwargs)


# Firestore Timestamp 등을 JSON 응답 가능하게 변환
def serialize_record(data: dict):
    result = {}

    for key, value in data.items():
        if hasattr(value, "isoformat"):
            result[key] = value.isoformat()
        else:
            result[key] = value

    return result


# 숫자 변환 보조 함수
def to_int(value, default=0):
    try:
        if value is None:
            return default
        return int(value)
    except Exception:
        return default


# 대화 기록 데이터 필드 통일
def normalize_conversation_data(data: dict):
    """
    프론트에서 ai_message 또는 ai_response 어떤 이름을 써도 동작하게
    두 필드를 모두 맞춰주는 함수
    """
    ai_text = data.get("ai_message") or data.get("ai_response") or ""

    messages = data.get("messages", [])

    if not ai_text and isinstance(messages, list):
        for message in messages:
            if message.get("role") == "assistant":
                ai_text = message.get("content", "")
                break

    user_text = data.get("user_message", "")

    if not user_text and isinstance(messages, list):
        for message in messages:
            if message.get("role") == "user":
                user_text = message.get("content", "")
                break

    data["user_message"] = user_text
    data["ai_message"] = ai_text
    data["ai_response"] = ai_text

    return data


# 대화 기록 저장 함수
def save_conversation(user_message: str, ai_message: str, summary: Optional[dict] = None):
    doc_ref = db.collection(CONVERSATION_COLLECTION).document()

    save_data = {
        "user_message": user_message,
        "ai_message": ai_message,
        "ai_response": ai_message,
        "messages": [
            {
                "role": "user",
                "content": user_message
            },
            {
                "role": "assistant",
                "content": ai_message
            }
        ],
        "summary": summary or {},
        "created_at": firestore.SERVER_TIMESTAMP,
        "updated_at": firestore.SERVER_TIMESTAMP
    }

    doc_ref.set(save_data)

    return doc_ref.id


# 학습 데이터 요약 계산 함수
def calculate_summary(records: list):
    if len(records) == 0:
        return {
            "period": None,
            "count": 0,
            "metrics": {
                "total": 0,
                "average": 0,
                "max": 0,
                "min": 0
            },
            "trend": "데이터가 부족합니다.",
            "subject_summary": {}
        }

    sorted_records = sorted(records, key=lambda x: x.get("date", ""))

    dates = [record.get("date", "") for record in sorted_records]

    values = [
        to_int(record.get("minutes", 0), 0)
        for record in sorted_records
    ]

    total = sum(values)
    count = len(values)
    average = round(total / count, 2) if count > 0 else 0
    max_value = max(values) if values else 0
    min_value = min(values) if values else 0

    period = f"{dates[0]} ~ {dates[-1]}" if dates else None

    subject_summary = {}

    for record in sorted_records:
        subject = record.get("subject") or "기타"
        minutes = to_int(record.get("minutes", 0), 0)

        if subject not in subject_summary:
            subject_summary[subject] = 0

        subject_summary[subject] += minutes

    if count >= 6:
        first_avg = sum(values[:3]) / 3
        last_avg = sum(values[-3:]) / 3

        if last_avg > first_avg:
            trend = "최근 학습 시간이 증가하는 추세입니다."
        elif last_avg < first_avg:
            trend = "최근 학습 시간이 감소하는 추세입니다."
        else:
            trend = "최근 학습 시간이 비슷하게 유지되고 있습니다."
    else:
        trend = "추세를 판단하기에는 데이터가 조금 부족합니다."

    return {
        "period": period,
        "count": count,
        "metrics": {
            "total": total,
            "average": average,
            "max": max_value,
            "min": min_value
        },
        "trend": trend,
        "subject_summary": subject_summary
    }


# AI 분석 공통 함수
def make_ai_analysis(request: AIRequest):
    docs = db.collection(COLLECTION_NAME).stream()

    records = []

    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        records.append(data)

    if len(records) == 0:
        raise HTTPException(
            status_code=400,
            detail="분석할 학습 데이터가 없습니다. 먼저 /api/data로 학습 데이터를 추가해주세요."
        )

    sorted_records = sorted(records, key=lambda x: x.get("date", ""))
    summary = calculate_summary(sorted_records)

    recent_records = sorted_records[-50:]

    record_text = ""

    for record in recent_records:
        record_text += (
            f"- 날짜: {record.get('date', '')}, "
            f"과목: {record.get('subject', '')}, "
            f"학습시간: {to_int(record.get('minutes', 0), 0)}분, "
            f"메모: {record.get('memo', '')}\n"
        )

    prompt = f"""
너는 학생의 학습시간 데이터를 분석해주는 AI 학습 코치야.
아래 Firestore 학습 데이터를 바탕으로 친절하고 구체적으로 분석해줘.

중요한 규칙:
- 반드시 제공된 학습 데이터와 요약 정보를 근거로 답변해.
- 데이터에 없는 내용은 단정하지 마.
- 학생이 바로 실천할 수 있는 조언을 해줘.
- 한국어로 답변해.

[사용자 질문]
{request.message}

[학습 데이터 요약]
- 기간: {summary["period"]}
- 기록 개수: {summary["count"]}
- 총 학습 시간: {summary["metrics"]["total"]}분
- 평균 학습 시간: {summary["metrics"]["average"]}분
- 최대 학습 시간: {summary["metrics"]["max"]}분
- 최소 학습 시간: {summary["metrics"]["min"]}분
- 추세: {summary["trend"]}
- 과목별 학습 시간: {summary["subject_summary"]}

[최근 학습 기록]
{record_text}

[답변 방식]
1. 전체 학습 패턴 요약
2. 과목별 분석
3. 부족하거나 개선할 점
4. 앞으로의 추천 학습 계획
5. 학생에게 해주는 격려 메시지
"""

    try:
        answer = ask_gemini(prompt)

        conversation_id = save_conversation(
            user_message=request.message,
            ai_message=answer,
            summary=summary
        )

        return {
            "message": request.message,
            "summary": summary,
            "answer": answer,
            "ai_message": answer,
            "ai_response": answer,
            "conversation_id": conversation_id
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Gemini 분석 중 오류가 발생했습니다: {str(e)}"
        )


# =========================
# 기본 API
# =========================
@app.get("/")
def home():
    return {
        "message": "학습시간 데이터 기반 AI 비서 API입니다.",
        "docs": "/docs"
    }


@app.get("/api/firestore-test")
def firestore_test():
    doc_ref = db.collection("test").document("connection")

    doc_ref.set({
        "message": "Firestore 연결 성공!"
    })

    doc = doc_ref.get()

    return {
        "success": True,
        "data": doc.to_dict()
    }


# =========================
# Gemini AI API
# =========================

@app.post("/api/ai/test")
def test_gemini(request: AIRequest):
    try:
        answer = ask_gemini(request.message)

        return {
            "message": request.message,
            "answer": answer,
            "ai_message": answer,
            "ai_response": answer
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Gemini 호출 중 오류가 발생했습니다: {str(e)}"
        )


@app.post("/api/ai/analyze")
def analyze_study_data(request: AIRequest = AIRequest()):
    return make_ai_analysis(request)


@app.post("/api/chat")
def chat(request: AIRequest = AIRequest()):
    return make_ai_analysis(request)


# =========================
# 학습 데이터 API
# =========================

@app.post("/api/data")
def create_data(data: DataCreate):
    new_data = model_to_dict(data)

    doc_ref = db.collection(COLLECTION_NAME).document()

    save_data = {
        **new_data,
        "created_at": firestore.SERVER_TIMESTAMP,
        "updated_at": firestore.SERVER_TIMESTAMP
    }

    doc_ref.set(save_data)

    saved_doc = doc_ref.get()
    saved_data = saved_doc.to_dict()
    saved_data["id"] = doc_ref.id

    return {
        "message": "데이터가 Firestore에 추가되었습니다.",
        "data": serialize_record(saved_data)
    }


@app.get("/api/data")
def get_data():
    docs = db.collection(COLLECTION_NAME).stream()

    records = []

    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        records.append(serialize_record(data))

    records = sorted(records, key=lambda x: x.get("date", ""))

    return {
        "count": len(records),
        "data": records
    }


@app.get("/api/data/summary")
def get_data_summary():
    docs = db.collection(COLLECTION_NAME).stream()

    records = []

    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        records.append(data)

    return calculate_summary(records)


@app.get("/api/data/{data_id}")
def get_data_detail(data_id: str):
    doc_ref = db.collection(COLLECTION_NAME).document(data_id)
    doc = doc_ref.get()

    if not doc.exists:
        raise HTTPException(status_code=404, detail="해당 데이터를 찾을 수 없습니다.")

    data = doc.to_dict()
    data["id"] = doc.id

    return serialize_record(data)


@app.put("/api/data/{data_id}")
def update_data(data_id: str, payload: DataUpdate):
    doc_ref = db.collection(COLLECTION_NAME).document(data_id)
    doc = doc_ref.get()

    if not doc.exists:
        raise HTTPException(status_code=404, detail="해당 데이터를 찾을 수 없습니다.")

    update_dict = model_to_dict(payload, exclude_unset=True)

    if len(update_dict) == 0:
        raise HTTPException(status_code=400, detail="수정할 데이터가 없습니다.")

    update_dict["updated_at"] = firestore.SERVER_TIMESTAMP

    doc_ref.update(update_dict)

    updated_doc = doc_ref.get()
    updated_data = updated_doc.to_dict()
    updated_data["id"] = updated_doc.id

    return {
        "message": "데이터가 Firestore에서 수정되었습니다.",
        "data": serialize_record(updated_data)
    }


@app.delete("/api/data/{data_id}")
def delete_data(data_id: str):
    doc_ref = db.collection(COLLECTION_NAME).document(data_id)
    doc = doc_ref.get()

    if not doc.exists:
        raise HTTPException(status_code=404, detail="해당 데이터를 찾을 수 없습니다.")

    deleted_data = doc.to_dict()
    deleted_data["id"] = doc.id

    doc_ref.delete()

    return {
        "message": "데이터가 Firestore에서 삭제되었습니다.",
        "deleted_data": serialize_record(deleted_data)
    }


# =========================
# 대화 기록 API
# =========================

@app.post("/api/conversations")
def create_conversation(conversation: ConversationCreate):
    new_conversation = model_to_dict(conversation)

    user_text = new_conversation.get("user_message", "")

    ai_text = (
        new_conversation.get("ai_message")
        or new_conversation.get("ai_response")
        or ""
    )

    doc_ref = db.collection(CONVERSATION_COLLECTION).document()

    save_data = {
        "user_message": user_text,
        "ai_message": ai_text,
        "ai_response": ai_text,
        "messages": [
            {
                "role": "user",
                "content": user_text
            },
            {
                "role": "assistant",
                "content": ai_text
            }
        ],
        "created_at": firestore.SERVER_TIMESTAMP,
        "updated_at": firestore.SERVER_TIMESTAMP
    }

    doc_ref.set(save_data)

    saved_doc = doc_ref.get()
    saved_data = saved_doc.to_dict()
    saved_data["id"] = saved_doc.id
    saved_data = normalize_conversation_data(saved_data)

    return {
        "message": "대화 기록이 Firestore에 저장되었습니다.",
        "data": serialize_record(saved_data)
    }


@app.get("/api/conversations")
def get_conversations():
    docs = db.collection(CONVERSATION_COLLECTION).stream()

    conversations = []

    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        data = normalize_conversation_data(data)
        conversations.append(serialize_record(data))

    conversations = sorted(
        conversations,
        key=lambda x: x.get("created_at", ""),
        reverse=True
    )

    return {
        "count": len(conversations),
        "data": conversations
    }

@app.delete("/api/conversations/{conversation_id}")
def delete_conversation(conversation_id: str):
    doc_ref = db.collection(CONVERSATION_COLLECTION).document(conversation_id)
    doc = doc_ref.get()

    if not doc.exists:
        raise HTTPException(status_code=404, detail="해당 대화 기록을 찾을 수 없습니다.")

    doc_ref.delete()

    return {
        "message": "대화 기록이 삭제되었습니다.",
        "id": conversation_id
    }


@app.get("/api/conversations/{conversation_id}")
def get_conversation_detail(conversation_id: str):
    doc_ref = db.collection(CONVERSATION_COLLECTION).document(conversation_id)
    doc = doc_ref.get()

    if not doc.exists:
        raise HTTPException(status_code=404, detail="해당 대화 기록을 찾을 수 없습니다.")

    data = doc.to_dict()
    data["id"] = doc.id
    data = normalize_conversation_data(data)