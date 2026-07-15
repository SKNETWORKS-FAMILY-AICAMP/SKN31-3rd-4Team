from langgraph.checkpoint.sqlite import SqliteSaver
import sqlite3
import uuid
import json

memory = SqliteSaver.from_conn_string("checkpoints.db")

def get_db_connection():
    DB_NAME = "patient.db"
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

#! Patient table
def create_patient_table():
    conn = get_db_connection()
    conn.execute("""
    CREATE TABLE IF NOT EXISTS patient (
        patient_id TEXT PRIMARY KEY,
        thread_id TEXT UNIQUE NOT NULL,
        name TEXT,
        age INTEGER,
        gender TEXT,
        is_pregnant INTEGER,
        drug TEXT,
        ingredient_code TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()

#!Create Patient
def create_patient(
    name:str,
    age: int,
    gender: str,
    is_pregnant: bool,
    drug: str,
    ingredient_code: str
):
    conn = get_db_connection()
    try:
        patient_id = str(uuid.uuid4())
        thread_id = str(uuid.uuid4())

        conn.execute(
            """
            INSERT INTO patient(
                patient_id,
                thread_id,
                name,
                age,
                gender,
                is_pregnant,
                drug,
                ingredient_code
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                patient_id,
                thread_id,
                name,
                age,
                gender,
                int(is_pregnant),
                drug,
                ingredient_code
            )
        )
        conn.commit()
        
        # 💡 중요: 저장된 환자 정보를 딕셔너리 형태로 반환합니다.
        return {
            "patient_id": patient_id,
            "thread_id": thread_id,
            "name":name,
            "age": age,
            "gender": gender,
            "is_pregnant": is_pregnant,
            "drug": drug,
            "ingredient_code": ingredient_code
        }
        
    except Exception as e:
        print("에러:", e)
        return None  # 에러 발생 시 None 반환
    finally:
        conn.close()