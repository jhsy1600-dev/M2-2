from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
from firebase_admin import firestore

# Firestore 연결 객체 가져오기
from .firebase_db import db

app = FastAPI(title="학습시간 데이터 기반 AI 비서 API")

# Firestore 컬렉션 이름
COLLECTION_NAME = "study_records"
CONVERSATION_COLLECTION = "conversations"


# =========================
# 요청 모델
# =========================

# 학습 데이터 추가 요청 모델
class DataCreate(BaseModel):
    date: str
    subject: str
    minutes: int
    memo: Optional[str] = None


# 학습 데이터 수정 요청 모델
class DataUpdate(BaseModel):
    date: Optional[str] = None
    subject: Optional[str] = None
    minutes: Optional[int] = None
    memo: Optional[str] = None


# 대화 기록 추가 요청 모델
class ConversationCreate(BaseModel):
    user_message: str
    ai_message: Optional[str] = None


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


# =========================
# 기본 API
# =========================

@app.get("/")
def home():
    return {
        "message": "학습시간 데이터 기반 AI 비서 API입니다.",
        "docs": "/docs"
    }


# Firestore 연결 테스트 API
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
# 학습 데이터 API
# =========================

# 1. 데이터 추가
@app.post("/api/data")
def create_data(data: DataCreate):
    new_data = model_to_dict(data)

    # Firestore 문서 자동 ID 생성
    doc_ref = db.collection(COLLECTION_NAME).document()

    save_data = {
        **new_data,
        "created_at": firestore.SERVER_TIMESTAMP,
        "updated_at": firestore.SERVER_TIMESTAMP
    }

    doc_ref.set(save_data)

    # 저장된 데이터 다시 읽기
    saved_doc = doc_ref.get()
    saved_data = saved_doc.to_dict()
    saved_data["id"] = doc_ref.id

    return {
        "message": "데이터가 Firestore에 추가되었습니다.",
        "data": serialize_record(saved_data)
    }


# 2. 데이터 목록 조회
@app.get("/api/data")
def get_data():
    docs = db.collection(COLLECTION_NAME).stream()

    records = []

    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        records.append(serialize_record(data))

    # 날짜 기준 정렬
    records = sorted(records, key=lambda x: x.get("date", ""))

    return {
        "count": len(records),
        "data": records
    }


# 3. 데이터 요약
# 중요: /api/data/{data_id} 보다 위에 있어야 함
@app.get("/api/data/summary")
def get_data_summary():
    docs = db.collection(COLLECTION_NAME).stream()

    records = []

    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        records.append(data)

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

    # 날짜 기준 정렬
    sorted_records = sorted(records, key=lambda x: x.get("date", ""))

    dates = [record.get("date", "") for record in sorted_records]

    values = [
        record.get("minutes", 0)
        for record in sorted_records
    ]

    total = sum(values)
    count = len(values)
    average = round(total / count, 2)
    max_value = max(values)
    min_value = min(values)

    period = f"{dates[0]} ~ {dates[-1]}"

    # 과목별 합계
    subject_summary = {}

    for record in sorted_records:
        subject = record.get("subject", "기타")
        minutes = record.get("minutes", 0)

        if subject not in subject_summary:
            subject_summary[subject] = 0

        subject_summary[subject] += minutes

    # 간단한 최근 추세 분석
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


# 4. 특정 데이터 1개 조회
@app.get("/api/data/{data_id}")
def get_data_detail(data_id: str):
    doc_ref = db.collection(COLLECTION_NAME).document(data_id)
    doc = doc_ref.get()

    if not doc.exists:
        raise HTTPException(status_code=404, detail="해당 데이터를 찾을 수 없습니다.")

    data = doc.to_dict()
    data["id"] = doc.id

    return serialize_record(data)


# 5. 데이터 수정
@app.put("/api/data/{data_id}")
def update_data(data_id: str, update_data: DataUpdate):
    doc_ref = db.collection(COLLECTION_NAME).document(data_id)
    doc = doc_ref.get()

    if not doc.exists:
        raise HTTPException(status_code=404, detail="해당 데이터를 찾을 수 없습니다.")

    update_dict = model_to_dict(update_data, exclude_unset=True)

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


# 6. 데이터 삭제
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

# 1. 대화 기록 추가
@app.post("/api/conversations")
def create_conversation(conversation: ConversationCreate):
    new_conversation = model_to_dict(conversation)

    doc_ref = db.collection(CONVERSATION_COLLECTION).document()

    save_data = {
        **new_conversation,
        "created_at": firestore.SERVER_TIMESTAMP,
        "updated_at": firestore.SERVER_TIMESTAMP
    }

    doc_ref.set(save_data)

    saved_doc = doc_ref.get()
    saved_data = saved_doc.to_dict()
    saved_data["id"] = saved_doc.id

    return {
        "message": "대화 기록이 Firestore에 저장되었습니다.",
        "data": serialize_record(saved_data)
    }


# 2. 대화 기록 전체 조회
@app.get("/api/conversations")
def get_conversations():
    docs = db.collection(CONVERSATION_COLLECTION).stream()

    conversations = []

    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        conversations.append(serialize_record(data))

    # 최근 대화가 위로 오도록 정렬
    conversations = sorted(
        conversations,
        key=lambda x: x.get("created_at", ""),
        reverse=True
    )

    return {
        "count": len(conversations),
        "data": conversations
    }


# 3. 특정 대화 기록 삭제
@app.delete("/api/conversations/{conversation_id}")
def delete_conversation(conversation_id: str):
    doc_ref = db.collection(CONVERSATION_COLLECTION).document(conversation_id)
    doc = doc_ref.get()

    if not doc.exists:
        raise HTTPException(status_code=404, detail="해당 대화 기록을 찾을 수 없습니다.")

    deleted_data = doc.to_dict()
    deleted_data["id"] = doc.id

    doc_ref.delete()

    return {
        "message": "대화 기록이 삭제되었습니다.",
        "deleted_data": serialize_record(deleted_data)
    }


# 4. 전체 대화 기록 삭제
@app.delete("/api/conversations")
def delete_all_conversations():
    docs = db.collection(CONVERSATION_COLLECTION).stream()

    deleted_count = 0

    for doc in docs:
        doc.reference.delete()
        deleted_count += 1

    return {
        "message": "전체 대화 기록이 삭제되었습니다.",
        "deleted_count": deleted_count
    }