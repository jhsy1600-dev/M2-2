from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional

app = FastAPI(title="Study Time AI Assistant API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------
# 데이터 모델
# -----------------------------

class StudyRecordCreate(BaseModel):
    date: str = Field(..., example="2026-09-25")
    subject: str = Field(..., example="수학")
    minutes: int = Field(..., example=90)
    memo: Optional[str] = Field(None, example="미분 문제 풀이")


class StudyRecordUpdate(BaseModel):
    date: Optional[str] = Field(None, example="2026-09-25")
    subject: Optional[str] = Field(None, example="영어")
    minutes: Optional[int] = Field(None, example=60)
    memo: Optional[str] = Field(None, example="단어 암기")


# -----------------------------
# 임시 데이터 저장소
# 나중에 Firebase로 바꿀 예정
# -----------------------------

study_records = []
next_id = 1


# -----------------------------
# 기본 확인 API
# -----------------------------

@app.get("/")
def root():
    return {
        "message": "Study Time AI Assistant API is running"
    }


@app.get("/health")
def health_check():
    return {
        "status": "ok"
    }


# -----------------------------
# 학습 기록 추가
# -----------------------------

@app.post("/records")
def create_record(record: StudyRecordCreate):
    global next_id

    new_record = {
        "id": next_id,
        "date": record.date,
        "subject": record.subject,
        "minutes": record.minutes,
        "memo": record.memo
    }

    study_records.append(new_record)
    next_id += 1

    return {
        "message": "학습 기록이 추가되었습니다.",
        "data": new_record
    }


# -----------------------------
# 학습 기록 전체 조회
# -----------------------------

@app.get("/records")
def get_records():
    return {
        "count": len(study_records),
        "data": study_records
    }


# -----------------------------
# 특정 학습 기록 조회
# -----------------------------

@app.get("/records/{record_id}")
def get_record(record_id: int):
    for record in study_records:
        if record["id"] == record_id:
            return {
                "data": record
            }

    raise HTTPException(status_code=404, detail="해당 학습 기록을 찾을 수 없습니다.")


# -----------------------------
# 학습 기록 수정
# -----------------------------

@app.put("/records/{record_id}")
def update_record(record_id: int, updated_record: StudyRecordUpdate):
    for record in study_records:
        if record["id"] == record_id:
            if updated_record.date is not None:
                record["date"] = updated_record.date
            if updated_record.subject is not None:
                record["subject"] = updated_record.subject
            if updated_record.minutes is not None:
                record["minutes"] = updated_record.minutes
            if updated_record.memo is not None:
                record["memo"] = updated_record.memo

            return {
                "message": "학습 기록이 수정되었습니다.",
                "data": record
            }

    raise HTTPException(status_code=404, detail="해당 학습 기록을 찾을 수 없습니다.")


# -----------------------------
# 학습 기록 삭제
# -----------------------------

@app.delete("/records/{record_id}")
def delete_record(record_id: int):
    for record in study_records:
        if record["id"] == record_id:
            study_records.remove(record)
            return {
                "message": "학습 기록이 삭제되었습니다.",
                "data": record
            }

    raise HTTPException(status_code=404, detail="해당 학습 기록을 찾을 수 없습니다.")


# -----------------------------
# 학습 시간 요약 API
# -----------------------------

@app.get("/summary")
def get_summary():
    total_minutes = sum(record["minutes"] for record in study_records)

    subject_summary = {}

    for record in study_records:
        subject = record["subject"]
        minutes = record["minutes"]

        if subject not in subject_summary:
            subject_summary[subject] = 0

        subject_summary[subject] += minutes

    return {
        "total_records": len(study_records),
        "total_minutes": total_minutes,
        "total_hours": round(total_minutes / 60, 2),
        "subject_summary": subject_summary
    }