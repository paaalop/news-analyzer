import json
from datetime import datetime, timedelta
from openai import OpenAI
import os
import pymysql
from dotenv import load_dotenv
from math import ceil

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
model_version = "gpt-4.1-mini"

# 어제 날짜
today = datetime.now()
yesterday = today - timedelta(days=1)
yesterday_str = yesterday.strftime("%Y-%m-%d")

# DB
conn = pymysql.connect(
    host="youthdb.cjuwyyqya00c.ap-southeast-2.rds.amazonaws.com",
    port=3306,
    user="admin",
    password="adminadmin",
    database="youthdb"
)
cursor = conn.cursor()

#기사 제목들 불러오기
sql = """
SELECT summary FROM newsdata
WHERE publish_time LIKE %s
"""
cursor.execute(sql, (f"{yesterday_str}%",))
rows = cursor.fetchall()

if not rows:
    print("어제 날짜 기사 제목이 없습니다.")
    cursor.close()
    conn.close()
    exit()

#요약 프롬프트 생성
summaries = [f"{i+1}. {summary}" for i, (summary,) in enumerate(rows)]

# --- 100개씩 나눠 요약 (map 단계) ---
CHUNK_SIZE = 100
num_chunks = ceil(len(summaries) / CHUNK_SIZE)
intermediate_summaries = []

for i in range(num_chunks):
    chunk = summaries[i * CHUNK_SIZE:(i + 1) * CHUNK_SIZE]
    chunk_prompt = (
        "다음은 하루 동안의 기술 뉴스 기사 요약들이다. "
        "가장 많이 언급된 주제 순서대로 정리해줘. 각 항목 앞에 숫자를 붙여줘:\n\n"
        + "\n\n".join(chunk)
    )

    print(f"[{i+1}/{num_chunks}] 청크 요약 중...")

    chunk_response = client.chat.completions.create(
        model=model_version,
        messages=[
            {"role": "system", "content": "너는 훌륭한 IT 뉴스 요약가야."},
            {"role": "user", "content": chunk_prompt}
        ],
        temperature=0.5
    )

    intermediate_summaries.append(chunk_response.choices[0].message.content)

# --- 최종 요약 (reduce 단계) ---
final_prompt = (
    "다음은 하루 동안의 기술 뉴스 요약 덩어리들이다. "
    "중복되는 주제를 묶고, 가장 많이 언급된 순서대로 요약해줘. 각 항목 앞에 숫자를 붙여줘:\n\n"
    + "\n\n".join(intermediate_summaries)
)

print("최종 요약 생성 중...")

final_response = client.chat.completions.create(
    model=model_version,
    messages=[
        {"role": "system", "content": "너는 훌륭한 IT 뉴스 요약가야."},
        {"role": "user", "content": final_prompt}
    ],
    temperature=0.5
)

summary_text = response.choices[0].message.content.strip()

# summarydata에 저장
try:
    sql_insert = """
    INSERT INTO summarydata (summary_date, summary)
    VALUES (%s, %s)
    ON DUPLICATE KEY UPDATE summary = VALUES(summary)
    """
    cursor.execute(sql_insert, (yesterday_str, summary_text))
    conn.commit()
    print("summarydata 저장 완료")
except Exception as e:
    print(f"DB 저장 중 에러: {e}")

cursor.close()
conn.close()
