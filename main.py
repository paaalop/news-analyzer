import os
import requests
import pymysql
import numpy as np
from bs4 import BeautifulSoup
from openai import OpenAI
from dotenv import load_dotenv
from numpy import dot
from numpy.linalg import norm

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
model_version = "gpt-4.1-mini"
embedding_model = "text-embedding-3-small"

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
subcategories_str = "\n".join(subcategories)

BASE_URL = "https://news.naver.com/section/"
HEADERS = {"User-Agent": "Mozilla/5.0"}
SID = "105"  # IT/과학
CATEGORY = "IT/과학"
ARTICLE_LIMIT = 20


# DB 중복 링크 불러오기
def load_existing_links_from_db():
    conn = pymysql.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT")),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
    )
    cursor = conn.cursor()
    cursor.execute("SELECT link FROM newsdata")
    links = {row[0] for row in cursor.fetchall()}
    cursor.close()
    conn.close()
    return links


# 기사 상세 내용 크롤링
def fetch_article_details(url):
    res = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(res.text, "html.parser")

    publish_time = soup.select_one("span.media_end_head_info_datestamp_time")
    journalist = soup.select_one("em.media_end_head_journalist_name")
    press = soup.select_one("span.media_end_head_top_logo_text")
    content_area = soup.select_one("div#newsct_article")

    content = (
        " ".join(
            p.get_text(strip=True)
            for p in content_area.find_all("p")
            if p.get_text(strip=True)
        )
        if content_area
        else ""
    )

    return {
        "publish_time": (
            publish_time["data-date-time"]
            if publish_time and publish_time.has_attr("data-date-time")
            else "Unknown"
        ),
        "journalist": journalist.get_text(strip=True) if journalist else "Unknown",
        "press": press.get_text(strip=True) if press else "Unknown",
        "content": content
        or (content_area.get_text(strip=True) if content_area else ""),
    }


# GPT 요약
import textwrap
from openai import OpenAI

client = OpenAI()  # 이미 생성해둔 객체면 필요 없음
model_version = "gpt-4o-mini"  # 사용 중인 모델


def gpt_summarize(text: str) -> str:
    prompt = textwrap.dedent(
        f"""
        다음은 뉴스 기사 전문이다. 이 내용을 한국어로 **핵심만 요약**하라.

        - 홍보성 문장, 배경 설명은 생략하고 **핵심 사실**만 남긴다.  
        - **최대 5문장**으로 요약하라.
        - 기사 스타일을 따라하지 말고 **객관적 요약문**으로 작성하라.
        기사 전문:
        {text}
    """
    ).strip()

    res = client.chat.completions.create(
        model=model_version,
        messages=[
            {"role": "system", "content": "너는 핵심 정보만 요약하는 뉴스 요약기다."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
    )

    # 결과에는 이미 LF가 들어 있으므로 그대로 반환
    return res.choices[0].message.content.strip()


# GPT 카테고리 분류
def gpt_classify(summary):
    prompt = f"""다음 뉴스 요약을 보고 정확히 아래 목록 중 하나의 세부 카테고리를 선택하라.
출력 형식: 카테고리: (이름만)

카테고리 목록:
{subcategories_str}

뉴스 요약:
{summary}
"""
    res = client.chat.completions.create(
        model=model_version,
        messages=[
            {"role": "system", "content": "카테고리를 분류하는 시스템이다."},
            {"role": "user", "content": prompt},
        ],
        temperature=0,
    )
    return res.choices[0].message.content.strip().split(":")[-1].strip()


# 임베딩
def get_embedding(text):
    try:
        res = client.embeddings.create(model=embedding_model, input=text)
        return np.array(res.data[0].embedding)
    except Exception as e:
        print(f"[임베딩 오류] {e}")
        return None


# 코사인 유사도 계산
def cosine_sim(v1, v2):
    return dot(v1, v2) / (norm(v1) * norm(v2))


# GPT 자극성/연관성 평가
def gpt_evaluate(title, content):
    prompt = f"""뉴스 제목: {title}
뉴스 본문: {content}

1. 제목의 자극성을 10점 만점으로 평가

형식:
자극성: (숫자)
"""
    res = client.chat.completions.create(
        model=model_version,
        messages=[
            {"role": "system", "content": "뉴스 평가 시스템이다."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
    )
    lines = res.choices[0].message.content.strip().split("\n")
    headline_score = int([l for l in lines if "자극성" in l][0].split(":")[1])
    relevance_score = (
        cosine_sim(get_embedding(title), get_embedding(content)) * 100
    )  # 0~1 범위를 0~10으로 변환
    return headline_score, int(relevance_score)


# DB 저장
def insert_to_db(articles):
    conn = pymysql.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT")),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
    )
    cursor = conn.cursor()

    insert_sql = """
    INSERT INTO newsdata (
        press, subcategory, title, link, publish_time,
        journalist, summary, headline_score, relevance_score
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    update_sql = """
    UPDATE newsdata
    SET summary = REGEXP_REPLACE(summary, '\\\\.[[:space:]]*', '.\\n\\n')
    WHERE id = LAST_INSERT_ID()
    """

    for a in articles:
        try:
            cursor.execute(
                insert_sql,
                (
                    a["언론사"],
                    a["세부카테고리"],
                    a["제목"],
                    a["URL"],
                    a["발행시간"],
                    a["기자"],
                    a["요약"],
                    int(a["자극성"]),
                    int(a["연관성"]),
                ),
            )
            cursor.execute(update_sql)
            print(f"DB 저장 완료: {a['제목']}")
        except Exception as e:
            print(f"DB 저장 실패: {e}")
            continue

    conn.commit()
    cursor.close()
    conn.close()


# 실행 메인
def main():
    existing_links = load_existing_links_from_db()
    soup = BeautifulSoup(
        requests.get(BASE_URL + SID, headers=HEADERS).text, "html.parser"
    )
    articles = soup.select("div.sa_text")

    new_articles = []

    for tag in articles:
        if len(new_articles) >= ARTICLE_LIMIT:
            break

        title_tag = tag.select_one("a.sa_text_title")
        if not title_tag:
            continue

        title = title_tag.get_text(strip=True)
        link = title_tag["href"]
        if link in existing_links:
            continue

        try:
            detail = fetch_article_details(link)
            if not detail["content"]:
                continue

            summary = gpt_summarize(detail["content"])
            category = gpt_classify(summary)
            headline_score, relevance_score = gpt_evaluate(title, detail["content"])

            new_articles.append(
                {
                    "언론사": detail["press"],
                    "세부카테고리": category,
                    "제목": title,
                    "URL": link,
                    "발행시간": detail["publish_time"],
                    "기자": detail["journalist"],
                    "요약": summary,
                    "자극성": headline_score,
                    "연관성": relevance_score,
                }
            )

            print(f"수집 완료: {title}")

        except Exception as e:
            print(f"에러 발생: {e}")
            continue

    insert_to_db(new_articles)
    print(f"\n총 {len(new_articles)}개 기사 DB 저장 완료")


if __name__ == "__main__":
    main()
