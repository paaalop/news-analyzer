import os
import pymysql
import datetime
import certifi
from dotenv import load_dotenv
from flask import Flask, render_template, request

load_dotenv()

SUBCATEGORIES = [
    "전체", "모바일", "인터넷/SNS", "통신/뉴미디어", "IT일반",
    "과학일반", "보안/해킹", "컴퓨터", "게임/리뷰"
]
ARTICLES_PER_PAGE = 10

def create_app():
    app = Flask(__name__)

    press_logos = {}
    with open("app/logo_data.txt", "r", encoding="utf-8") as f:
        raw_data = f.read()

    for line in raw_data.splitlines():
        if " : " in line:
            name, url = line.split(" : ", 1)
            press_logos[name.strip()] = url.strip()

    def get_db_connection():
        try:
            return pymysql.connect(
                host=os.getenv("DB_HOST"),
                port=int(os.getenv("DB_PORT", 4000)),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                database=os.getenv("DB_NAME"),
                ssl={'ca': certifi.where()}
            )
        except Exception as e:
            print(f"Database Connection Error: {e}")
            raise e


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
            relevance = (article.get("relevance_score", 0) / 75) * 100
            if relevance > 100:
                relevance = 100
            elif relevance < 0:
                relevance = 0
            article["relevance_score"] = int(relevance)
            stimulus = article.get("headline_score", 0)
            article["relevance_hue"] = 120 * ((relevance) / 100)
            article["stimulus_hue"] = 120 - (stimulus / 10) * 120

        return articles, total_articles

    def get_article_by_id(article_id):
        conn = get_db_connection()
        cur = conn.cursor(pymysql.cursors.DictCursor)
        cur.execute("SELECT * FROM newsdata WHERE id = %s", (article_id,))
        article = cur.fetchone()
        cur.close()
        conn.close()
        if article:
            relevance = (article.get("relevance_score", 0) / 75) * 100
            if relevance > 100:
                relevance = 100
            elif relevance < 0:
                relevance = 0
            article["relevance_score"] = int(relevance)
            stimulus = article.get("headline_score", 0)
            article["relevance_hue"] = 120 * ((relevance) / 100)
            article["stimulus_hue"] = 120 - (stimulus / 10) * 120
        return article
    
    def get_summary_from_db(): #데이터베이스에서 요약 가져오기 추가했습니다
        conn = get_db_connection()
        cur = conn.cursor(pymysql.cursors.DictCursor)
        cur.execute("""
            SELECT summary_date, summary
            FROM summarydata
            ORDER BY summary_date DESC
        """)
        summary_data = cur.fetchall()
        cur.close()
        conn.close()
        return summary_data


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
                               total_pages=total_pages,
                               query=query,#query랑 field를 만들어 놓고 반환을 안했기 때문에 index.html에ㅐ서 주소필드에 적용하지 못함함
                               field=field,
                               press_logos=press_logos)

    @app.route("/article/<int:article_id>")
    def show_article(article_id):
        article = get_article_by_id(article_id)
        if article:
            return render_template("article.html",
                                   article=article,
                                   subcategories=SUBCATEGORIES,
                                   selected_category="기사 보기")
        return "기사를 찾을 수 없습니다.", 404
    
    @app.route("/summary")
    def summary():
        date = request.args.get("date")
        summary_data = get_summary_from_db()
        selected_summary = None
        if date:
            for item in summary_data:
                if str(item["summary_date"]) == date:#flask 이슈;;
                    selected_summary = item
                    break
        else:
            # 기본적으로 가장 최신일자를 띄우도록 해놨음니다
            if summary_data:
                selected_summary = summary_data[0]
                date = selected_summary["summary_date"]

        return render_template("summary.html",
                            summary_data=summary_data,
                            selected_summary=selected_summary,
                            selected_date=date,                      
                            subcategories=SUBCATEGORIES,
                            selected_category="어제 요약"
                            )

    @app.route("/home")
    def home():
        conn = get_db_connection()
        cur = conn.cursor(pymysql.cursors.DictCursor)

        home_articles = {}
        today = datetime.datetime.now().date()

        for cat in SUBCATEGORIES[1:9]:
            cur.execute("""
                SELECT * FROM newsdata 
                WHERE subcategory = %s AND DATE(publish_time) = %s
                ORDER BY relevance_score DESC LIMIT 1
            """, (cat, today))
            relevance_top = cur.fetchone()

            cur.execute("""
                SELECT * FROM newsdata 
                WHERE subcategory = %s AND DATE(publish_time) = %s
                ORDER BY headline_score DESC LIMIT 1
            """, (cat, today))
            stimulus_top = cur.fetchone()

            articles = []
            if relevance_top:
                articles.append(relevance_top)
            if stimulus_top and (not relevance_top or stimulus_top["id"] != relevance_top["id"]):
                articles.append(stimulus_top)

            home_articles[cat] = articles

        cur.close()
        conn.close()

        return render_template("home.html",
                            subcategories=SUBCATEGORIES,
                            selected_category="홈",
                            home_articles=home_articles)


    return app
