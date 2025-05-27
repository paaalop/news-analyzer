import requests
from bs4 import BeautifulSoup
import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
model_version = "gpt-4.1-mini"

subcategories = [
    "모바일",
    "인터넷/SNS",
    "통신/뉴미디어",
    "IT일반",
    "과학일반",
    "보안/해킹",
    "컴퓨터",
    "게임/리뷰",
]

base_url = "https://news.naver.com/section/"
headers = {"User-Agent": "Mozilla/5.0"}
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
json_file = os.path.join(BASE_DIR, "articles.json")
selected_category = "IT/과학"
sid = "105"
count = 40

existing_keys = set()
data = []

if os.path.exists(json_file):
    with open(json_file, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
            for article in data:
                key = (article["URL"], article.get("발행시간", ""))
                existing_keys.add(key)
        except json.JSONDecodeError:
            data = []

url = base_url + sid
res = requests.get(url, headers=headers)
soup = BeautifulSoup(res.text, "html.parser")
articles = soup.select("div.sa_text")

print(f"[{selected_category}] 선택 기사 수: {count}")
new_articles = []

for i in articles:
    if len(new_articles) >= count:
        break

    title_tag = i.select_one("a.sa_text_title")
    if not title_tag:
        continue

    title = title_tag.get_text(strip=True)
    link = title_tag["href"]

    article_res = requests.get(link, headers=headers)
    article_soup = BeautifulSoup(article_res.text, "html.parser")

    time_tag = article_soup.select_one("span.media_end_head_info_datestamp_time")
    publish_time = (
        time_tag["data-date-time"]
        if time_tag and time_tag.has_attr("data-date-time")
        else "Unknown"
    )

    key = (link, publish_time)
    if key in existing_keys:
        print(f"중복 기사 건너뜀: {title}")
        continue

    journalist_tag = article_soup.select_one("em.media_end_head_journalist_name")
    journalist = journalist_tag.get_text(strip=True) if journalist_tag else "Unknown"

    press_tag = article_soup.select_one("span.media_end_head_top_logo_text")
    press = press_tag.get_text(strip=True) if press_tag else "Unknown"

    content_area = article_soup.select_one("div#newsct_article")
    if not content_area:
        print(f"본문 없음")
        continue

    paragraphs = content_area.find_all("p")
    content_text = " ".join(
        p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)
    )
    if not content_text:
        content_text = content_area.get_text(strip=True)

    prompt = f"다음 뉴스 기사를 한국어로 핵심만 간단히 요약해:\n\n{content_text}"
    response = client.chat.completions.create(
        model=model_version,
        messages=[
            {
                "role": "system",
                "content": "뉴스 요약 시스템이다. 사용자가 입력한 기사를 핵심내용으로 요약해.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.5,
    )
    summary = response.choices[0].message.content.strip()

    subcategories_str = "\n".join(subcategories)
    prompt_classify = f"""다음 뉴스 기사 요약을 읽고, 반드시 아래 8개의 세부 카테고리 중 하나를 골라 **정확히 그 이름만 사용해** 출력하라.
반드시 아래 목록 중 하나만 선택해야 하며, 다른 표현이나 유사어를 쓰지 마라.

출력 형식 (이외 다른 문자 금지):
카테고리: (선택된 카테고리 이름)

카테고리 목록:
{subcategories_str}

뉴스 요약:
{summary}
"""

    response_classify = client.chat.completions.create(
        model=model_version,
        messages=[
            {
                "role": "system",
                "content": "뉴스 기사 요약을 기반으로 세부 카테고리를 분류하는 시스템이다.",
            },
            {"role": "user", "content": prompt_classify},
        ],
        temperature=0,
    )
    classify_result = response_classify.choices[0].message.content.strip()
    subcategory = (
        classify_result.split(":")[-1].strip() if ":" in classify_result else "Unknown"
    )

    prompt_eval = f"""뉴스 제목: {title}

뉴스 본문:
{content_text}

다음 뉴스 제목과 본문을 바탕으로 두 가지 항목을 평가하라.

1. 제목의 자극성을 10점 만점으로 평가하되, 점수가 높을수록 자극적이며, 보통 수준일 경우 5점으로 평가하라.
2. 제목이 본문과 얼마나 관련 있는지를 100점 만점으로 평가하라.

출력 형식은 반드시 다음과 같이 정확히 두 줄로 작성하라.  
점수 외에는 설명, 기호, 문장 등을 포함하지 말고 아래 양식을 그대로 따를 것:

자극성: (숫자)
연관성: (숫자)
"""

    response_eval = client.chat.completions.create(
        model=model_version,
        messages=[
            {"role": "system", "content": "넌 뉴스 제목을 분석,평가하는 시스템이다."},
            {"role": "user", "content": prompt_eval},
        ],
        temperature=0,
    )
    eval_text = response_eval.choices[0].message.content.strip()

    headline_score = ""
    relevance_score = ""
    for line in eval_text.split("\n"):
        if "자극성" in line:
            headline_score = line.split(":")[-1].strip()
        elif "연관성" in line:
            relevance_score = line.split(":")[-1].strip()

    new_articles.append(
        {
            "언론사": press,
            "세부카테고리": subcategory,
            "제목": title,
            "URL": link,
            "발행시간": publish_time,
            "기자": journalist,
            "요약": summary,
            "자극성(10점)": headline_score,
            "연관성(100점)": relevance_score,
        }
    )

    print(f"수집 및 요약 완료: {title}")

# 저장
data.extend(new_articles)
with open(json_file, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"\n총 {len(new_articles)}개 기사 저장 완료 (파일: {json_file})")
