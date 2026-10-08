import firebase_admin
from firebase_admin import credentials, firestore
from pathlib import Path

# 현재 파일이 있는 backend 폴더 경로
BASE_DIR = Path(__file__).resolve().parent

# 서비스 계정 키 파일 경로
KEY_PATH = BASE_DIR / "serviceAccountKey.json"

# Firebase 앱 초기화
if not firebase_admin._apps:
    cred = credentials.Certificate(str(KEY_PATH))
    firebase_admin.initialize_app(cred)

# Firestore DB 객체
db = firestore.client()