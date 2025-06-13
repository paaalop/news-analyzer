import os
import pymysql
import numpy as np
from dotenv import load_dotenv
from datetime import datetime, timedelta
from openai import OpenAI
from numpy import dot
from numpy.linalg import norm

# --- 환경 설정 ---
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
model_version = "gpt-4.1-mini"
embedding_model = "text-embedding-3-small"

# --- 날짜 설정 ---
today = datetime.now()
yesterday = today - timedelta(days=1)
yesterday_str = yesterday.strftime("%Y-%m-%d")
print(f"분석 날짜: {yesterday_str}")

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
    print("DB 연결 성공")
except Exception as e:
    print(f"DB 연결 실패: {e}")
    exit()

# --- 뉴스 요약 불러오기 ---
cursor.execute("SELECT summary FROM newsdata WHERE publish_time LIKE %s", (f"{yesterday_str}%",))
rows = cursor.fetchall()
summaries = [row[0] for row in rows]
print(f"총 {len(summaries)}개의 요약문 로딩 완료")

if not summaries:
    print("기사 없음")
    exit()

# --- 임베딩 함수 ---
def get_embedding(text):
    try:
        res = client.embeddings.create(model=embedding_model, input=text)
        return np.array(res.data[0].embedding)
    except Exception as e:
        print(f"[임베딩 오류] {e}")
        return None

def cosine_sim(v1, v2):
    return dot(v1, v2) / (norm(v1) * norm(v2))

# --- 군집화 ---
clusters = []
emb_matrix = []  # 전체 클러스터 임베딩 벡터 모음

for i, summary in enumerate(summaries):
    print(f"[{i+1}/{len(summaries)}] 군집화 중")
    emb = get_embedding(summary)
    if emb is None:
        print(f"[{i+1}] 임베딩 실패 → 건너뜀")
        continue

    if not clusters:
        clusters.append({"summary": summary, "embedding": emb, "count": 1, "extras": []})
        emb_matrix.append(emb)
        continue

    emb_matrix_np = np.array(emb_matrix)
    norms = np.linalg.norm(emb_matrix_np, axis=1)
    target_norm = norm(emb)
    sims = np.dot(emb_matrix_np, emb) / (norms * target_norm)

    best_index = np.argmax(sims)
    best_sim = sims[best_index]
    print(f" - 최고 유사도: {best_sim:.3f}")

    if best_sim >= 0.75:
        clusters[best_index]["count"] += 1
        clusters[best_index]["extras"].append(summary)
    else:
        clusters.append({"summary": summary, "embedding": emb, "count": 1, "extras": []})
        emb_matrix.append(emb)
        print(f" - 새 클러스터 생성 (총 {len(clusters)}개)")

# --- 클러스터 정렬 ---
clusters.sort(key=lambda x: x["count"], reverse=True)
print(f"총 {len(clusters)}개 클러스터 생성 완료")

# --- 대표 요약 2~3개만 사용한 입력 구성 ---
cluster_texts = []
for c in clusters:
    all_summaries = [c["summary"]] + c["extras"]
    top_examples = all_summaries[:3]
    lines = '\n'.join(f"- {s}" for s in top_examples)
    cluster_texts.append(f"({c['count']}건)\n{lines}")

report_prompt = f"""
다음은 하루 동안 수집된 총 {sum(c['count'] for c in clusters)}건의 기술 뉴스 기사 요약이다.

각 클러스터는 동일한 주제를 다루는 기사 묶음이다.

요구사항:
1. 이 클러스터들을 5~7개의 상위 주제로 묶고, 각 주제에 제목을 붙여라.
2. 각 주제 옆에는 해당 클러스터들의 총 기사 수를 괄호에 표시하라.
3. 각 주제는 <h3> 태그로 제목을 명확하게 구분하고, 아래에는 대표 요약문 2~3개를 <ul><li>로 출력하라.
4. 전체 기사 요약은 생략하고, 대표 요약만 출력해도 된다.
5. 마지막에 하루 전체 요약을 <p><strong>오늘 요약:</strong> ...</p> 형식으로 작성하라.

입력:

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
    print("최종 요약 생성 완료")
except Exception as e:
    print(f"[GPT 최종 요약 실패] {e}")
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
    print("최종 요약 DB 저장 성공")
except Exception as e:
    print(f"[DB 저장 실패] {e}")

cursor.close()
conn.close()
print("프로세스 종료")