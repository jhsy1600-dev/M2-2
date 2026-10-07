from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
from pathlib import Path
import json

app = FastAPI(title="학습시간 데이터 기반 AI 비서 API")

# 데이터 저장 파일 위치
DATA_FILE = Path(__file__).parent / "records.json"


# 데이터 추가 요청 모델
class DataCreate(BaseModel):
    date: str
    subject: str
    minutes: int
    memo: Optional[str] = None


# 데이터 수정 요청 모델
class DataUpdate(BaseModel):
    date: Optional[str] = None
    subject: Optional[str] = None
    minutes: Optional[int] = None
    memo: Optional[str] = None


# Pydantic v1/v2 호환용
def model_to_dict(model, **kwargs):
    if hasattr(model, "model_dump"):
        return model.model_dump(**kwargs)
    return model.dict(**kwargs)


# 파일에서 데이터 불러오기
def load_records():
    if not DATA_FILE.exists():
        return []

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []


# 파일에 데이터 저장하기
def save_records():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)


# 기존 records.json 데이터 불러오기
records = load_records()

# 기존 데이터 중 가장 큰 id 다음 번호부터 시작
next_id = max([record.get("id", 0) for record in records], default=0) + 1


@app.get("/")
def home():
    return {
        "message": "학습시간 데이터 기반 AI 비서 API입니다.",
        "docs": "/docs"
    }


# 1. 데이터 추가
@app.post("/api/data")
def create_data(data: DataCreate):
    global next_id

    new_data = model_to_dict(data)
    new_data["id"] = next_id
    next_id += 1

    records.append(new_data)
    save_records()

    return {
        "message": "데이터가 추가되었습니다.",
        "data": new_data
    }


# 2. 데이터 목록 조회
@app.get("/api/data")
def get_data():
    return {
        "count": len(records),
        "data": records
    }


# 3. 데이터 요약
# 중요: /api/data/{data_id} 보다 위에 있어야 함
@app.get("/api/data/summary")
def get_data_summary():
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
    sorted_records = sorted(records, key=lambda x: x["date"])

    dates = [record["date"] for record in sorted_records]

    # minutes 사용
    # 예전에 value로 저장된 데이터가 있으면 임시 호환
    values = [
        record.get("minutes", record.get("value", 0))
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
        minutes = record.get("minutes", record.get("value", 0))

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
def get_data_detail(data_id: int):
    for record in records:
        if record["id"] == data_id:
            return record

    raise HTTPException(status_code=404, detail="해당 데이터를 찾을 수 없습니다.")


# 5. 데이터 수정
@app.put("/api/data/{data_id}")
def update_data(data_id: int, update_data: DataUpdate):
    update_dict = model_to_dict(update_data, exclude_unset=True)

    for record in records:
        if record["id"] == data_id:
            record.update(update_dict)
            save_records()

            return {
                "message": "데이터가 수정되었습니다.",
                "data": record
            }

    raise HTTPException(status_code=404, detail="해당 데이터를 찾을 수 없습니다.")


# 6. 데이터 삭제
@app.delete("/api/data/{data_id}")
def delete_data(data_id: int):
    for record in records:
        if record["id"] == data_id:
            records.remove(record)
            save_records()

            return {
                "message": "데이터가 삭제되었습니다.",
                "deleted_data": record
            }

    raise HTTPException(status_code=404, detail="해당 데이터를 찾을 수 없습니다.")