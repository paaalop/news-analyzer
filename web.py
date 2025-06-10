from flask import Flask, render_template, request, abort
import pymysql
import os

app = Flask(__name__)

#설정 상수
SUBCATEGORIES = [
    "전체", "모바일", "인터넷/SNS", "통신/뉴미디어", "IT일반",
    "과학일반", "보안/해킹", "컴퓨터", "게임/리뷰"
]
ARTICLES_PER_PAGE = 10

#DB 연결
def get_db_connection():
    return pymysql.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT")),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME")
    )

#DB에서 기사 가져오기
def get_articles_from_db(category, page, per_page=10, query=None, field=None):
    conn = get_db_connection()
    cur = conn.cursor(pymysql.cursors.DictCursor)
    offset = (page - 1) * per_page

    base_query = "SELECT * FROM newsdata"
    count_query = "SELECT COUNT(*) FROM newsdata"
    where_clauses = []
    params = []

    if category != "전체":
        where_clauses.append("subcategory = %s")
        params.append(category)

    if query and field in ("title", "journalist", "summary", "press"):
        where_clauses.append(f"{field} LIKE %s")
        params.append(f"%{query}%")


    where_sql = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""

    final_query = f"{base_query}{where_sql} ORDER BY publish_time DESC LIMIT %s OFFSET %s"
    final_count_query = f"{count_query}{where_sql}"

    cur.execute(final_query, params + [per_page, offset])
    articles = cur.fetchall()

    cur.execute(final_count_query, params)
    total_articles = cur.fetchone()['COUNT(*)']

    cur.close()
    conn.close()

    for article in articles:
        relevance = article.get("relevance_score", 0)
        stimulus = article.get("headline_score", 0)
        article["relevance_hue"] = 120 * ((relevance - 70) / 30) if relevance > 70 else 0
        article["stimulus_hue"] = 120 - (stimulus / 10) * 120

    return articles, total_articles



#DB에서 특정 기사 정보 가져오기
def get_article_by_id(article_id):
    conn = get_db_connection()
    cur = conn.cursor(pymysql.cursors.DictCursor)
    cur.execute("""
        SELECT *
        FROM newsdata
        WHERE id = %s
    """, (article_id,))
    article = cur.fetchone()
    cur.close()
    conn.close()
    return article

#메인 목록 페이지
@app.route("/")
def index():
    category = request.args.get("category", SUBCATEGORIES[0])
    page = int(request.args.get("page", 1))
    query = request.args.get("query")
    field = request.args.get("field")

    articles, total_articles = get_articles_from_db(category, page, ARTICLES_PER_PAGE, query, field)
    total_pages = (total_articles + ARTICLES_PER_PAGE - 1) // ARTICLES_PER_PAGE

    return render_template("index.html",
                           subcategories=SUBCATEGORIES,
                           selected_category=category,
                           selected_articles=enumerate(articles),
                           current_page=page,
                           total_pages=total_pages)

#상세 페이지
@app.route("/article/<int:article_id>")
def show_article(article_id):
    article = get_article_by_id(article_id)
    if article:
        return render_template("article.html",
                               article=article,
                               subcategories=SUBCATEGORIES,
                               selected_category="기사 보기")
    return "기사를 찾을 수 없습니다.", 404

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
