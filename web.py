from flask import Flask, render_template, request
import json
from collections import defaultdict, OrderedDict # OrderedDict 임포트

app = Flask(__name__)

# --- 설정 상수 ---
SUBCATEGORIES = [
    "모바일", "인터넷/SNS", "통신/뉴미디어", "IT일반", "과학일반",
    "보안/해킹", "컴퓨터", "게임/리뷰",
]
RELEVANCE_THRESHOLD = 70 # 연관성 최하점 기준

# --- 전역 변수 초기화 ---
ARTICLES = []
SUMMARY_DATA = []

# --- 데이터 로딩 함수 ---
def load_data():
    """
    articles.json과 summary.json에서 데이터를 로드하고 전역 변수에 저장합니다.
    """
    global ARTICLES, SUMMARY_DATA

    # 기사 데이터 로드
    try:
        with open("articles.json", "r", encoding="utf-8") as f:
            raw_articles = json.load(f)
            # 점수 필드의 타입 변환 및 기본값 처리
            for article in raw_articles:
                try:
                    article['연관성(100점)'] = int(article.get('연관성(100점)', 0))
                except (ValueError, TypeError):
                    article['연관성(100점)'] = 0
                    print(f"경고: 연관성 점수 변환 실패 (기사 제목: {article.get('제목', '알 수 없는 기사')}). 기본값 0으로 설정합니다.")
                
                try:
                    article['자극성(10점)'] = int(article.get('자극성(10점)', 0))
                except (ValueError, TypeError):
                    article['자극성(10점)'] = 0
                    print(f"경고: 자극성 점수 변환 실패 (기사 제목: {article.get('제목', '알 수 없는 기사')}). 기본값 0으로 설정합니다.")
            ARTICLES = raw_articles
    except FileNotFoundError:
        print("articles.json 파일을 찾을 수 없습니다. 빈 데이터로 시작합니다.")
        ARTICLES = []
    except json.JSONDecodeError:
        print("articles.json 파일이 유효한 JSON 형식이 아닙니다. 빈 데이터로 시작합니다.")
        ARTICLES = []

    # 오늘의 뉴스 요약 데이터 로드
    try:
        with open("summary.json", "r", encoding="utf-8") as f:
            raw_summary = json.load(f, object_pairs_hook=OrderedDict) # JSON 순서 유지를 위해 OrderedDict 사용
            
            # 제공된 summary.json 형식에 맞게 리스트로 변환
            # [{"2025-05-27": "요약1"}, {"2025-05-28": "요약2"}]
            # 이 형식은 이미 리스트 안에 딕셔너리가 있는 형태이므로,
            # 추가적인 리스트 변환 로직은 필요 없습니다.
            # SUMMARY_DATA = raw_summary
            # 그러나 만약 {날짜: 요약} 형태의 딕셔너리였다면 아래와 같이 변환했을 것입니다.
            # if isinstance(raw_summary, dict):
            #     SUMMARY_DATA = [{"date": date, "summary": summary} for date, summary in raw_summary.items()]
            # else:
            SUMMARY_DATA = raw_summary # 현재 제공된 JSON 형식 그대로 사용

    except FileNotFoundError:
        print("summary.json 파일을 찾을 수 없습니다. 빈 데이터로 시작합니다.")
        SUMMARY_DATA = []
    except json.JSONDecodeError:
        print("summary.json 파일이 유효한 JSON 형식이 아닙니다. 빈 데이터로 시작합니다.")
        SUMMARY_DATA = []

# Flask 앱 컨텍스트에서 데이터 로드 (앱 시작 시 한 번 실행)
with app.app_context():
    load_data()

# 기사들을 카테고리별로 그룹화 (데이터 로드 후 수행)
GROUPED_ARTICLES = defaultdict(list)
if ARTICLES:
    for idx, article in enumerate(ARTICLES):
        sub = article.get("세부카테고리", "기타")
        GROUPED_ARTICLES[sub].append((idx, article))

# --- 라우팅 ---
@app.route("/")
def index():
    selected_category = request.args.get("category", SUBCATEGORIES[0])
    selected_articles = GROUPED_ARTICLES.get(selected_category, [])
    
    return render_template(
        "index.html", # index.html 템플릿 파일 사용
        subcategories=SUBCATEGORIES,
        selected_category=selected_category,
        selected_articles=selected_articles
    )


@app.route("/summary")
def summary():
    return render_template(
        "summary.html", # summary.html 템플릿 파일 사용
        subcategories=SUBCATEGORIES,
        selected_category="오늘의 뉴스",
        summary_data=SUMMARY_DATA
    )


@app.route("/article/<int:idx>")
def show_article(idx):
    if 0 <= idx < len(ARTICLES):
        return render_template(
            "article.html", # article.html 템플릿 파일 사용
            article=ARTICLES[idx],
            subcategories=SUBCATEGORIES,
            selected_category="기사 보기" # 메뉴바 active 표시용
        )
    return "기사를 찾을 수 없습니다.", 404


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)