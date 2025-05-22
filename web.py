from flask import Flask, render_template_string, request
import json
from collections import defaultdict

app = Flask(__name__)

# JSON 파일 로드
with open("네이버뉴스데이터.json", "r", encoding="utf-8") as f:
    articles = json.load(f)

# 세부카테고리 리스트
subcategories = [
    "인공지능",
    "반도체/하드웨어",
    "모바일/통신",
    "소프트웨어/인터넷",
    "과학일반/기술",
]

# 세부카테고리별 기사 인덱스 저장
grouped_articles = defaultdict(list)
for idx, article in enumerate(articles):
    sub = article.get("세부카테고리", "기타")
    grouped_articles[sub].append((idx, article))

# HTML 템플릿
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

# 기사 상세 페이지는 이전과 동일
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
       <strong>카테고리:</strong> {{ article['카테고리'] }} / {{ article.get('세부카테고리', '미분류') }}<br>
       <strong>발행시간:</strong> {{ article['발행시간'] }}<br>
       <strong>기자:</strong> {{ article['기자'] }}</p>
    <p><strong>요약:</strong> {{ article['요약'] }}</p>
    <hr>
    <iframe src="{{ article['URL'] }}" width="100%" height="800px"></iframe>
    <br><a href="/">← 목록으로 돌아가기</a>
</body>
</html>
"""

@app.route("/")
def index():
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
    if 0 <= idx < len(articles):
        return render_template_string(article_template, article=articles[idx])
    return "기사 없음", 404

if __name__ == '__main__':
    app.run(debug=True)
