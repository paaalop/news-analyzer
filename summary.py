import json
from datetime import datetime, timedelta
from openai import OpenAI
import os
import mysql.connector
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# 어제 날짜
today = datetime.now()
yesterday = today - timedelta(days=1)
yesterday_str = yesterday.strftime("%Y-%m-%d")

# DB
conn = mysql.connector.connect(
    host="localhost",
    user="youth",
    password="youth",
    database="youthdb"
)
cursor = conn.cursor()

#기사 제목들 불러오기
sql = """
SELECT title FROM newsdata
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
titles = [f"{i+1}. {title}" for i, (title,) in enumerate(rows)]
prompt = (
   "다음은 하루 동안의 기술 뉴스 기사 요약들이다. "
    "가장 많이 언급된 주제 순서대로 정리하여 하루의 뉴스 트렌드를 요약해.하루 동안의 기술 뉴스 트렌드를 정리하면 다음과 같습니다:와 같은 문구는 작성하지 말고 기사 요약내용만 작성해. 각 요약 앞에는 순서대로 숫자를 입력해\n\n"
    + "\n\n".join(titles)
)

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {"role": "system", "content": "너는 훌륭한 IT 뉴스 요약가야."},
        {"role": "user", "content": prompt}
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
