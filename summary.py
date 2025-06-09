import os
import pymysql
import numpy as np
from dotenv import load_dotenv
from datetime import datetime, timedelta
from openai import OpenAI
from numpy import dot
from numpy.linalg import norm

# 환경 설정
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
model_version = "gpt-4.1-mini"
embedding_model = "text-embedding-3-small"

# 날짜
today = datetime.now()
yesterday = today - timedelta(days=1)
yesterday_str = yesterday.strftime("%Y-%m-%d")

# DB 연결
conn = pymysql.connect(
    host=os.getenv("DB_HOST"),
    port=int(os.getenv("DB_PORT")),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    database=os.getenv("DB_NAME")
)
cursor = conn.cursor()

# summary 불러오기
cursor.execute("SELECT summary FROM newsdata WHERE publish_time LIKE %s", (f"{yesterday_str}%",))
rows = cursor.fetchall()

if not rows:
    print("기사 없음.")
    exit()

summaries = [row[0] for row in rows]

# 임베딩/유사도
def get_embedding(text):
    try:
        res = client.embeddings.create(model=embedding_model, input=text)
        return np.array(res.data[0].embedding)
    except Exception as e:
        print(f"[임베딩 오류] {e}")
        return None

def cosine_sim(v1, v2):
    return dot(v1, v2) / (norm(v1) * norm(v2))

# 군집화
clusters = []
for i, summary in enumerate(summaries):
    print(f"[{i+1}/{len(summaries)}] 군집화 중...")
    emb = get_embedding(summary)
    if emb is None:
        continue

    matched = False
    for cluster in clusters:
        sim = cosine_sim(emb, cluster["embedding"])
        if sim >= 0.85:
            # GPT 확인
            prompt = f"""다음 두 뉴스 요약이 같은 주제를 다루는 경우 1, 다르면 0을 출력하라. 그 외 설명은 쓰지 마라.

요약1:
{cluster['summary']}

요약2:
{summary}
"""
            try:
                res = client.chat.completions.create(
                    model=model_version,
                    messages=[
                        {"role": "system", "content": "같은 주제면 1, 다르면 0만 출력하는 시스템이다."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0
                )
                result = res.choices[0].message.content.strip()
                if result == "1":
                    cluster["count"] += 1
                    cluster["extras"].append(summary)
                    matched = True
                    break
            except Exception as e:
                print(f"[GPT 오류] {e}")
                continue

    if not matched:
        clusters.append({"summary": summary, "embedding": emb, "count": 1, "extras": []})

# 대표 요약문 리스트 생성
clusters.sort(key=lambda x: x["count"], reverse=True)
cluster_texts = [
    f"({c['count']}회 언급) {c['summary']}"
    for c in clusters
]

# 2차 GPT 요약 프롬프트
report_prompt = f"""다음은 하루 동안의 기술 뉴스 대표 요약문 리스트다.
각 문장은 비슷한 뉴스들을 하나로 묶은 것이다.
이 목록을 5~7개의 상위 주제 범주로 묶고,
각 범주에 주제 제목을 붙인 뒤, 관련된 요약문을 2~3개씩 <ul><li> 형식으로 HTML로 출력하라.

출력 예시:

<h3>1. AI 반도체 (11건)</h3>
<ul>
  <li>삼성, AI 가속기 발표</li>
  <li>인텔, 엣지 AI 칩 발표</li>
</ul>

마지막에 하루 전체 흐름 요약을 <p><strong>오늘 요약:</strong> ...</p> 형식으로 작성해라.

{chr(10).join(cluster_texts)}
"""

res = client.chat.completions.create(
    model=model_version,
    messages=[
        {"role": "system", "content": "넌 뉴스 리포트를 작성하는 시스템이다."},
        {"role": "user", "content": report_prompt}
    ],
    temperature=0.4
)

final_summary = res.choices[0].message.content.strip()

# summarydata 저장
try:
    sql = """
    INSERT INTO summarydata (summary_date, summary)
    VALUES (%s, %s)
    ON DUPLICATE KEY UPDATE summary = VALUES(summary)
    """
    cursor.execute(sql, (yesterday_str, final_summary))
    conn.commit()
    print("최종 요약 저장 완료")
except Exception as e:
    print(f"[DB 저장 에러] {e}")

cursor.close()
conn.close()
