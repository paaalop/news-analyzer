import json
from datetime import datetime, timedelta
from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
json_file = os.path.join(BASE_DIR, "articles.json")

with open(json_file, "r", encoding="utf-8") as f:
    articles = json.load(f)
print(f"총 {len(articles)}개의 기사 로딩 완료")



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


prompt = (
    "다음은 하루 동안의 기술 뉴스 기사 요약들이다. "
    "가장 많이 언급된 주제 순서대로 정리하여 하루의 뉴스 트렌드를 요약해.하루 동안의 기술 뉴스 트렌드를 정리하면 다음과 같습니다:와 같은 문구는 작성하지 말고 기사 요약내용만 작성해. 각 요약 앞에는 순서대로 숫자를 입력해\n\n"
    + "\n\n".join(summaries)
)

print("ChatGPT API 요청 중...")
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {"role": "system", "content": "너는 훌륭한 IT 뉴스 요약가야."},
        {"role": "user", "content": prompt}
    ],
    temperature=0.5
)

summary_text = response.choices[0].message.content

summary_file = os.path.join(BASE_DIR, "summary.json")

try:
    with open(summary_file, "r", encoding="utf-8") as f:
        summary_data = json.load(f)
        if not isinstance(summary_data, list):
            raise ValueError("summary.json은 리스트 형식이어야 합니다.")
except (FileNotFoundError, ValueError, json.JSONDecodeError):
    summary_data = []

# 어제 날짜 요약 덮어쓰기 (기존에 있으면 제거)
summary_data = [entry for entry in summary_data if yesterday_str not in entry]
summary_data.append({yesterday_str: summary_text})

with open(summary_file, "w", encoding="utf-8") as f:
    json.dump(summary_data, f, indent=2, ensure_ascii=False)

print(f"요약 저장 완료: {summary_file}")

