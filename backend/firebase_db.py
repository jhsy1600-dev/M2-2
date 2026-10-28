import os
import json
from pathlib import Path

import firebase_admin
from firebase_admin import credentials, firestore

if not firebase_admin._apps:
    firebase_service_account = (
        os.getenv("FIREBASE_CREDENTIALS")
        or os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY")
    )

    if firebase_service_account:
        service_account_info = json.loads(firebase_service_account)

        # private_key의 줄바꿈 처리
        if "private_key" in service_account_info:
            service_account_info["private_key"] = service_account_info["private_key"].replace("\\n", "\n")

        cred = credentials.Certificate(service_account_info)

    else:
        # 로컬 개발용 파일
        key_path = Path(__file__).parent / "serviceAccountKey.json"

        if not key_path.exists():
            raise FileNotFoundError(
                "Firebase 인증 정보가 없습니다. "
                "Render에서는 FIREBASE_CREDENTIALS 또는 FIREBASE_SERVICE_ACCOUNT_KEY 환경변수를 설정하세요."
            )

        cred = credentials.Certificate(str(key_path))

    firebase_admin.initialize_app(cred)

db = firestore.client()
