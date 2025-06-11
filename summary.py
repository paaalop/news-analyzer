import os
import pymysql
import numpy as np
import logging
from dotenv import load_dotenv
from datetime import datetime, timedelta
from openai import OpenAI
from numpy import dot
from numpy.linalg import norm

# --- 로깅 설정 ---
logging.basicConfig(
    filename="news_summary.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# --- 환경 설정 ---
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
model_version = "gpt-4.1-mini"
embedding_model = "text-embedding-3-small"

# --- 날짜 설정 ---
today = datetime.now()
yesterday = today - timedelta(days=1)
yesterday_str = yesterday.strftime("%Y-%m-%d")
logging.info(f"분석 날짜: {yesterday_str}")

# --- DB 연결 ---
try:
    conn = pymysql.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT")),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME")
    )
    cursor = conn.cursor()
    logging.info("DB 연결 성공")
except Exception as e:
    logging.error(f"DB 연결 실패: {e}")
    exit()

# --- 뉴스 요약 불러오기 ---
cursor.execute("SELECT summary FROM newsdata WHERE publish_time LIKE %s", (f"{yesterday_str}%",))
rows = cursor.fetchall()
summaries = [row[0] for row in rows]
logging.info(f"총 {len(summaries)}개의 요약문 로딩 완료")

if not summaries:
    logging.warning("기사 없음")
    exit()

# --- 임베딩 함수 ---
def get_embedding(text):
    try:
        res = client.embeddings.create(model=embedding_model, input=text)
        return np.array(res.data[0].embedding)
    except Exception as e:
        logging.error(f"[임베딩 오류] {e}")
        return None

def cosine_sim(v1, v2):
    return dot(v1, v2) / (norm(v1) * norm(v2))

# --- 군집화 ---
clusters = []
for i, summary in enumerate(summaries):
    logging.info(f"[{i+1}/{len(summaries)}] 군집화 중")
    emb = get_embedding(summary)
    if emb is None:
        logging.warning(f"[{i+1}] 임베딩 실패 → 건너뜀")
        continue

    matched = False
    for cluster in clusters:
        sim = cosine_sim(emb, cluster["embedding"])
        logging.info(f" - 유사도: {sim:.3f}")
        if sim >= 0.85:
            # GPT 검증
            prompt = f"""다음 두 뉴스 요약이 같은 주제를 다루는 경우 1, 다르면 0을 출력하라.

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
                logging.info(f" - GPT 판단: {result}")
                if result == "1":
                    cluster["count"] += 1
                    cluster["extras"].append(summary)
                    matched = True
                    break
            except Exception as e:
                logging.error(f"[GPT 판단 오류] {e}")
                continue

    if not matched:
        clusters.append({"summary": summary, "embedding": emb, "count": 1, "extras": []})
        logging.info(f" - 새 클러스터 생성 (총 {len(clusters)}개)")

# --- 클러스터 정렬 ---
clusters.sort(key=lambda x: x["count"], reverse=True)
logging.info(f"총 {len(clusters)}개 클러스터 생성 완료")

# --- 전체 요약 포함한 프롬프트 구성 ---
cluster_texts = []
for c in clusters:
    all_summaries = [c["summary"]] + c["extras"]
    lines = '\n'.join(f"- {s}" for s in all_summaries)
    cluster_texts.append(f"({c['count']}건)\n{lines}")

report_prompt = f"""다음은 하루 동안 수집된 총 {sum(c['count'] for c in clusters)}건의 기술 뉴스 요약문이다.

이 목록을 유사한 주제끼리 묶어 5~7개의 상위 주제로 분류하고,
각 주제마다 제목을 붙인 후, 관련된 모든 요약문을 빠짐없이 <ul><li> 형식으로 HTML로 출력하라.

각 주제별로 제목 옆 괄호 안에 총 뉴스 건수를 표기하라.
요약문은 절대로 생략하지 말고 전부 출력하라.

마지막에 하루 전체 흐름 요약을 <p><strong>오늘 요약:</strong> ...</p> 형식으로 작성하라.

{chr(10).join(cluster_texts)}
"""

# --- GPT 요청 ---
try:
    res = client.chat.completions.create(
        model=model_version,
        messages=[
            {"role": "system", "content": "넌 뉴스 리포트를 작성하는 시스템이다."},
            {"role": "user", "content": report_prompt}
        ],
        temperature=0.4
    )
    final_summary = res.choices[0].message.content.strip()
    logging.info("최종 요약 생성 완료")
except Exception as e:
    logging.error(f"[GPT 최종 요약 실패] {e}")
    exit()

# --- DB 저장 ---
try:
    sql = """
    INSERT INTO summarydata (summary_date, summary)
    VALUES (%s, %s)
    ON DUPLICATE KEY UPDATE summary = VALUES(summary)
    """
    cursor.execute(sql, (yesterday_str, final_summary))
    conn.commit()
    logging.info("최종 요약 DB 저장 성공")
except Exception as e:
    logging.error(f"[DB 저장 실패] {e}")

cursor.close()
conn.close()
logging.info("프로세스 종료")
