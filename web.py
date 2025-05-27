from flask import Flask, render_template, request
import json
import os
from collections import defaultdict, OrderedDict

app = Flask(__name__)

# --- 설정 상수 ---
SUBCATEGORIES = [
    "모바일", "인터넷/SNS", "통신/뉴미디어", "IT일반",
    "과학일반", "보안/해킹", "컴퓨터", "게임/리뷰"
]
RELEVANCE_THRESHOLD = 70
ARTICLES_PER_PAGE = 10

# --- 전역 변수 ---
ARTICLES, SUMMARY_DATA = [], []
last_articles_mtime, last_summary_mtime = 0, 0

# --- 파일 로딩 유틸 ---
def load_articles():
    try:
        with open("articles.json", encoding="utf-8") as f:
            raw_articles = json.load(f)
            for idx, article in enumerate(raw_articles):
                article["연관성(100점)"] = int(article.get("연관성(100점)", 0))
                article["자극성(10점)"] = int(article.get("자극성(10점)", 0))
                article["relevance_hue"] = 120 * ((article["연관성(100점)"] - 70) / 30) if article["연관성(100점)"] > 70 else 0
                article["stimulus_hue"] = 120 - (article["자극성(10점)"] / 10) * 120
            return sorted(raw_articles, key=lambda a: a.get("발행시간", ""), reverse=True)
    except Exception as e:
        print(f"[오류] articles.json 로드 실패: {e}")
        return []

def load_summary():
    try:
        with open("summary.json", encoding="utf-8") as f:
            summary = json.load(f, object_pairs_hook=OrderedDict)
            return sorted(summary, key=lambda item: list(item.keys())[0], reverse=True)
    except Exception as e:
        print(f"[오류] summary.json 로드 실패: {e}")
        return []

def load_if_modified():
    global ARTICLES, SUMMARY_DATA, last_articles_mtime, last_summary_mtime

    try:
        mtime = os.path.getmtime("articles.json")
        if mtime != last_articles_mtime:
            last_articles_mtime = mtime
            ARTICLES = load_articles()

        mtime = os.path.getmtime("summary.json")
        if mtime != last_summary_mtime:
            last_summary_mtime = mtime
            SUMMARY_DATA = load_summary()
    except Exception as e:
        print(f"[오류] mtime 확인 실패: {e}")

# --- 데이터 유틸 ---
def get_grouped_articles():
    grouped = defaultdict(list)
    for idx, article in enumerate(ARTICLES):
        sub = article.get("세부카테고리", "기타")
        grouped[sub].append((idx, article))
    return grouped

def get_paginated_articles(category, page, per_page):
    grouped = get_grouped_articles()
    articles = grouped.get(category, [])
    total_pages = (len(articles) + per_page - 1) // per_page
    start, end = (page - 1) * per_page, page * per_page
    return articles[start:end], total_pages

# --- 라우팅 ---
@app.route("/")
def index():
    load_if_modified()
    category = request.args.get("category", SUBCATEGORIES[0])
    page = int(request.args.get("page", 1))
    paginated, total_pages = get_paginated_articles(category, page, ARTICLES_PER_PAGE)
    return render_template("index.html", subcategories=SUBCATEGORIES,
                           selected_category=category,
                           selected_articles=paginated,
                           current_page=page,
                           total_pages=total_pages)

@app.route("/summary")
def summary():
    load_if_modified()
    return render_template("summary.html", subcategories=SUBCATEGORIES,
                           selected_category="오늘의 뉴스",
                           summary_data=SUMMARY_DATA)

@app.route("/article/<int:idx>")
def show_article(idx):
    load_if_modified()
    if 0 <= idx < len(ARTICLES):
        return render_template("article.html", article=ARTICLES[idx],
                               subcategories=SUBCATEGORIES,
                               selected_category="기사 보기")
    return "기사를 찾을 수 없습니다.", 404

# --- 앱 실행 ---
if __name__ == "__main__":
    ARTICLES = load_articles()
    SUMMARY_DATA = load_summary()
    app.run(host="0.0.0.0", port=5000, debug=True)
