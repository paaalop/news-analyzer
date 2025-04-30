import requests
from bs4 import BeautifulSoup


def get_article_links(section_url, max_articles=5):
    headers = {"User-Agent": "Mozilla/5.0"}
    res = requests.get(section_url, headers=headers)
    soup = BeautifulSoup(res.text, "html.parser")

    links = []
    for tag in soup.select("a[data-link-name='article']"):
        href = tag.get("href")
        if (
            href
            and href.startswith("https://www.theguardian.com/")
            and href not in links
        ):
            links.append(href)
        if len(links) >= max_articles:
            break
    return links


def get_article_content(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    res = requests.get(url, headers=headers)
    soup = BeautifulSoup(res.text, "html.parser")

    try:
        title = soup.find("h1").get_text(strip=True)
    except:
        title = "(제목 없음)"

    # 본문이 들어있는 실제 selector 수정
    paragraphs = soup.select("div[data-gu-name='body'] p") or soup.select(
        "div.article-body-commercial-selector p"
    )
    content = "\n".join(p.get_text(strip=True) for p in paragraphs)
    return {"title": title, "content": content, "url": url}


def main():
    tech_links = get_article_links("https://www.theguardian.com/uk/technology")
    sci_links = get_article_links("https://www.theguardian.com/science")
    all_links = tech_links + sci_links

    all_articles = []

    if not all_links:
        print("⚠️ 기사 링크를 하나도 찾지 못했습니다.")
        return

    for link in all_links:
        article = get_article_content(link)
        all_articles.append(article)

        print(f"\n[제목] {article['title']}")
        print(f"[링크] {article['url']}")
        print(f"[본문 요약] {article['content'][:200]}...")
        print("-" * 80)

    # ✅ 여기서 텍스트 파일로 저장
    with open("guardian_articles.txt", "w", encoding="utf-8") as f:
        for article in all_articles:
            f.write(f"제목: {article['title']}\n")
            f.write(f"링크: {article['url']}\n")
            f.write(f"본문:\n{article['content']}\n")
            f.write("="*100 + "\n")

    print("\n📝 기사들이 'guardian_articles.txt'에 저장되었습니다!")

if __name__ == "__main__":
    main()
