from flask import Flask, render_template_string, request
import json

app = Flask(__name__)

# JSON 파일 로드
with open("네이버뉴스데이터.json", "r", encoding="utf-8") as f:
    articles = json.load(f)

# 전체 기사 리스트 페이지 템플릿
list_template = """
<!DOCTYPE html>
<html>
<head>
    <title>네이버 뉴스 목록</title>
</head>
<body>
    <h1>📰 네이버 뉴스 목록</h1>
    <ul>
    {% for article in articles %}
        <li>
            <a href="/article/{{ loop.index0 }}">{{ article['제목'] }}</a><br>
            <small>{{ article['요약'] }}</small>
        </li>
    {% endfor %}
    </ul>

</body>
</html>
"""

# 개별 기사 페이지 템플릿
article_template = """
<!DOCTYPE html>
<html>
<head>
    <title>{{ article['제목'] }}</title>
</head>
<body>
    <h1>{{ article['제목'] }}</h1>
    <p><strong>자극성(10점):</strong> {{ article['자극성(10점)'] }}<br>
        <strong>연관성(100점):</strong> {{ article['연관성(100점)'] }}</p>
    <p><strong>언론사:</strong> {{ article['언론사'] }}<br>
       <strong>카테고리:</strong> {{ article['카테고리'] }}<br>
       <strong>발행시간:</strong> {{ article['발행시간'] }}<br>
       <strong>기자:</strong> {{ article['기자'] }}</p>
    <p><strong>요약:</strong> {{ article['요약'] }}</p>
    <hr>
    <iframe src="{{ article['URL'] }}" width="100%" height="800px" style="border:none;"></iframe>
    <br><a href="/">← 돌아가기</a>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(list_template, articles=articles)

@app.route("/article/<int:idx>")
def show_article(idx):
    if 0 <= idx < len(articles):
        return render_template_string(article_template, article=articles[idx])
    return "기사 없음", 404

if __name__ == '__main__':
    app.run(debug=True)