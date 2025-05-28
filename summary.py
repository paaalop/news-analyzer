import json
from datetime import datetime, timedelta
from openai import OpenAI
import os
from dotenv import load_dotenv
from math import ceil

# --- 환경 변수 및 경로 설정 ---
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
model_version = "gpt-4.1-mini"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
json_file = os.path.join(BASE_DIR, "articles.json")

# --- 기사 로딩 ---
with open(json_file, "r", encoding="utf-8") as f:
    articles = json.load(f)
print(f"총 {len(articles)}개의 기사 로딩 완료")

# --- 어제 날짜 필터링 ---
today = datetime.now()
yesterday = today - timedelta(days=1)
yesterday_str = yesterday.strftime("%Y-%m-%d")

filtered = [
    article for article in articles
    if article.get("발행시간", "").startswith(yesterday_str)
]

summaries = [article["요약"] for article in filtered if "요약" in article]

if not summaries:
    print("[!] 어제 날짜 기사 요약이 없습니다. 프로그램 종료.")
    exit()

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

summary_text = final_response.choices[0].message.content

# --- summary.json 저장 ---
summary_file = os.path.join(BASE_DIR, "summary.json")

try:
    with open(summary_file, "r", encoding="utf-8") as f:
        summary_data = json.load(f)
        if not isinstance(summary_data, list):
            raise ValueError("summary.json은 리스트 형식이어야 합니다.")
except (FileNotFoundError, ValueError, json.JSONDecodeError):
    summary_data = []

# 어제 날짜 요약 덮어쓰기
summary_data = [entry for entry in summary_data if yesterday_str not in entry]
summary_data.append({yesterday_str: summary_text})

with open(summary_file, "w", encoding="utf-8") as f:
    json.dump(summary_data, f, indent=2, ensure_ascii=False)

print(f"요약 저장 완료: {summary_file}")
