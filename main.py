import requests
from bs4 import BeautifulSoup
import os
import json
from openai import OpenAI
from dotenv import load_dotenv

# OpenAI키설정
load_dotenv()  # .env 파일 불러오기
client = os.getenv("OPENAI_API_KEY")

# 카테고리
categories = {
    "정치": "100",
    "경제": "101",
    "사회": "102",
    "생활/문화": "103",
    "세계": "104",
    "IT/과학": "105"
}

base_url = "https://news.naver.com/section/"
headers = {"User-Agent": "Mozilla/5.0"}
json_file = "네이버뉴스데이터.json"

# 링크 중복 검사
existing_links = set()
if os.path.exists(json_file):
    with open(json_file, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
            for article in data:
                existing_links.add(article["URL"])
        except json.JSONDecodeError:
            data = []
else:
    data = []

# 크롤링 범위 묻기
print("카테고리:")
for name in categories:
    print(f"- {name}")

choice = input("카테고리와 기사 수를 입력하세요 (예: 정치,10): ")
try:
    selected_category, count_str = [x.strip() for x in choice.split(",")]
    sid = categories.get(selected_category)
    count = int(count_str)
except:
    print("잘못 입력하셨습니다다.")
    exit()

if not sid:
    print("카테고리를 다시 확인하세요.")
    exit()

# 링크 수집
url = base_url + sid
res = requests.get(url, headers=headers)
soup = BeautifulSoup(res.text, "html.parser")

articles = soup.select("div.sa_text")
print(f"[{selected_category}] 총 기사 수: {len(articles)}")

# 기사 처리
new_articles = []
for i in articles:
    if len(new_articles) >= count:
        break

    title_tag = i.select_one("a.sa_text_title")
    if not title_tag:
        continue

    title = title_tag.get_text(strip=True)
    link = title_tag["href"]
    if link in existing_links:
        print(f"중복: {title}")
        continue

    try:
        article_res = requests.get(link, headers=headers)
        article_soup = BeautifulSoup(article_res.text, "html.parser")

        # 작성시간
        time_tag = article_soup.select_one("span.media_end_head_info_datestamp_time")
        publish_time = time_tag["data-date-time"] if time_tag and time_tag.has_attr("data-date-time") else "Unknown"

        # 기자
        journalist_tag = article_soup.select_one("em.media_end_head_journalist_name")
        journalist = journalist_tag.get_text(strip=True) if journalist_tag else "Unknown"

        # 언론사
        press_tag = article_soup.select_one("span.media_end_head_top_logo_text")
        press = press_tag.get_text(strip=True) if press_tag else "Unknown"

        # 본문
        content_area = article_soup.select_one("div#newsct_article")
        if not content_area:
            print(f"본문 없음")
            continue

        paragraphs = content_area.find_all("p")
        content_text = " ".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
        if not content_text:
            content_text = content_area.get_text(strip=True)

        # GPT로 요약
        prompt = f"다음 뉴스 기사를 한국어로 핵심만 간단히 요약해:\n\n{content_text}"
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "뉴스 요약 시스템이다. 사용자가 입력한 기사를 핵심내용으로 요약해."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5,
        )

        summary = response.choices[0].message.content.strip()

        # 자극성, 연관성 평가
        prompt_eval = f"뉴스 제목: {title}\n\n뉴스 본문: {content_text}\n\n1. 이 제목의 자극성을 10점 만점으로 평가해 다른 문자 없이 '자극성 :(점수)'로만 표현해줘. (점수가 높을수록 자극적. 보통의 자극도일 경우 5점으로 해줘)2. 이 제목이 뉴스 본문과 얼마나 연관 있는지 100점 만점으로 평가해 다른 문자 없이 '연관성 :(점수)'로만 표현해. 1번 2번 답은 줄을 바꿔서 출력해줘줘"
        response_eval = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "넌 뉴스 제목을 분석,평가하는 시스템이다."},
                {"role": "user", "content": prompt_eval}
            ],
            temperature=0.3,
        )
        eval_text = response_eval.choices[0].message.content.strip()

        headline_score = ""
        relevance_score = ""
        for line in eval_text.split("\n"):
            if "자극성" in line:
                headline_score = line.split(":")[-1].strip()
            elif "연관성" in line:
                relevance_score = line.split(":")[-1].strip()

        new_articles.append({
            "언론사": press,
            "카테고리": selected_category,
            "제목": title,
            "URL": link,
            "발행시간": publish_time,
            "기자": journalist,
            "요약": summary,
            "자극성(10점)": headline_score,
            "연관성(100점)": relevance_score
        })

        print(f"수집 및 요약 완료: {title}")

    except Exception as e:
        print(f"에러 발생: {e}")
        continue

# 저장하기
data.extend(new_articles)
with open(json_file, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"\n총 {len(new_articles)}개 기사 저장 완료 (파일: {json_file})")
