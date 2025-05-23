from flask import Flask, render_template_string, request
import json
from collections import defaultdict

app = Flask(__name__)

# 새로운 세부카테고리 리스트
subcategories = [
    "모바일",
    "인터넷/SNS",
    "통신/뉴미디어",
    "IT일반",
    "과학일반",
    "보안/해킹",
    "컴퓨터",
    "게임/리뷰"
]

# 매 요청마다 JSON 파일을 다시 로드하는 함수
def load_articles():
    with open("네이버뉴스데이터.json", "r", encoding="utf-8") as f:
        return json.load(f)

# 기사들을 세부카테고리 기준으로 그룹화하는 함수
def group_articles(articles):
    grouped = defaultdict(list)
    for idx, article in enumerate(articles):
        sub = article.get("세부카테고리", "기타")
        grouped[sub].append((idx, article))
    return grouped

# 메인 페이지 템플릿
main_template = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>네이버 뉴스</title>
    <style>
        body { font-family: sans-serif; margin: 0; padding: 0; }
        nav {
            background-color: #333;
            padding: 10px;
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
        }
        nav a {
            color: white;
            text-decoration: none;
            padding: 8px 16px;
            border-radius: 4px;
        }
        nav a.active {
            background-color: #ff9800;
        }
        .container {
            padding: 20px;
        }
        h2 {
            margin-top: 0;
        }
        ul { list-style: none; padding-left: 0; }
        li { margin-bottom: 10px; }
        small { color: #555; }
    </style>
</head>
<body>
    <nav>
        {% for sub in subcategories %}
            <a href="/?category={{ sub }}" class="{{ 'active' if selected_category == sub else '' }}">{{ sub }}</a>
        {% endfor %}
    </nav>
    <div class="container">
        <h2>{{ selected_category }} </h2>
        {% if selected_articles %}
            <ul>
                {% for idx, article in selected_articles %}
                    <li>
                        <a href="/article/{{ idx }}">{{ article['제목'] }}</a><br>
                        <small>{{ article['요약'] }}</small>
                    </li>
                {% endfor %}
            </ul>
        {% else %}
            <p>해당 카테고리의 기사가 없습니다.</p>
        {% endif %}
    </div>
</body>
</html>
"""

# 기사 상세 페이지 템플릿
article_template = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{{ article['제목'] }}</title>
    <style>
        body { font-family: sans-serif; padding: 20px; }
        iframe { border: none; margin-top: 20px; }
        a { display: inline-block; margin-top: 20px; }
    </style>
</head>
<body>
    <h1>{{ article['제목'] }}</h1>
    <p><strong>자극성(10점):</strong> {{ article['자극성(10점)'] }}<br>
       <strong>연관성(100점):</strong> {{ article['연관성(100점)'] }}</p>
    <p><strong>언론사:</strong> {{ article['언론사'] }}<br>
       <strong>카테고리:</strong> {{ article.get('세부카테고리', '미분류') }}<br>
       <strong>발행시간:</strong> {{ article['발행시간'] }}<br>
       <strong>기자:</strong> {{ article['기자'] }}</p>
    <p><strong>요약:</strong> {{ article['요약'] }}</p>
    <hr>
    <br><a href="/">← 목록으로 돌아가기</a>
</body>
</html>
"""

@app.route("/")
def index():
    articles = load_articles()
    grouped_articles = group_articles(articles)
    selected_category = request.args.get("category", subcategories[0])
    selected_articles = grouped_articles.get(selected_category, [])
    return render_template_string(
        main_template,
        subcategories=subcategories,
        selected_category=selected_category,
        selected_articles=selected_articles
    )

@app.route("/article/<int:idx>")
def show_article(idx):
    articles = load_articles()
    if 0 <= idx < len(articles):
        return render_template_string(article_template, article=articles[idx])
    return "기사 없음", 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
