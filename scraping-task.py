import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, urldefrag, urlunparse
import time
import csv
import re

# ========================================
# 設定
# ========================================


start_url = "https://www.musashino-u.ac.jp/"


domain = urlparse(start_url).netloc.lower()


csv_filename = "musashino_sitemap.csv"


WAIT_SECONDS = 2


site_map = {}


todo = [start_url]


visited = set()


seen_keys = set()


headers = {
    "User-Agent": "SitemapResearch/1.0 (educational research)"
}


# ========================================
# URLの正規化
# ========================================

def normalize_url(url):
    """
    URLの表記を統一する。

    ・#section などを除去
    ・スキームとドメイン名を小文字に統一
    ・デフォルトポートを除去
    ・空のパスを / に統一
    ・ルート以外のパス末尾の / を除去
    ・クエリパラメータは保持
    """


    url, _ = urldefrag(url)

    parsed = urlparse(url)

    if parsed.scheme.lower() not in ("http", "https"):
        return None


    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()


    if scheme == "https" and netloc.endswith(":443"):
        netloc = netloc[:-4]
    elif scheme == "http" and netloc.endswith(":80"):
        netloc = netloc[:-3]


    path = parsed.path or "/"


    if path != "/":
        path = path.rstrip("/")


    return urlunparse((
        scheme,
        netloc,
        path,
        parsed.params,
        parsed.query,
        ""
    ))


# ========================================
# 重複判定用のキーを作成
# ========================================

def get_duplicate_key(url):
    """
    ページ番号や年などの違いを無視して、
    重複判定用のキーを作成する。

    実際にアクセスするURLは変更しない。
    """

    normalized_url = normalize_url(url)

    if not normalized_url:
        return None

    parsed = urlparse(normalized_url)


    parts = [
        part for part in parsed.path.split("/")
        if part
    ]

    normalized_parts = []
    i = 0

    while i < len(parts):
        part = parts[i]


        if (
            part.lower() == "page"
            and i + 1 < len(parts)
            and parts[i + 1].isdigit()
        ):
            i += 2
            continue


        if re.fullmatch(r"(19|20)\d{2}", part):
            i += 1
            continue

        normalized_parts.append(part)
        i += 1


    normalized_path = "/" + "/".join(normalized_parts)

    if not normalized_parts:
        normalized_path = "/"


    return (
        parsed.scheme.lower(),
        parsed.netloc.lower(),
        normalized_path.rstrip("/") or "/"
    )


start_url = normalize_url(start_url)
todo = [start_url]


# ========================================
# Webサイトの取得
# ========================================

start_time = time.time()

with requests.Session() as session:
    session.headers.update(headers)

    while todo:


        url = todo.pop(0)


        if not url or url in visited:
            continue


        if urlparse(url).netloc.lower() != domain:
            continue


        duplicate_key = get_duplicate_key(url)


        if not duplicate_key:
            continue


        if duplicate_key in seen_keys:
            print(f"重複スキップ: {url}")
            continue


        seen_keys.add(duplicate_key)


        visited.add(url)

        try:

            time.sleep(WAIT_SECONDS)


            response = session.get(
                url,
                timeout=15,
                allow_redirects=True
            )


            response.raise_for_status()


            final_url = normalize_url(response.url)


            if (
                not final_url
                or urlparse(final_url).netloc.lower() != domain
            ):
                print(f"対象外のリダイレクト先: {response.url}")
                continue


            final_key = get_duplicate_key(final_url)

            if final_key in site_map:
                continue


            content_type = response.headers.get(
                "Content-Type", ""
            )

            if "text/html" not in content_type.lower():
                continue

            # ========================================
            # HTML解析・文字化け対策
            # ========================================


            soup = BeautifulSoup(
                response.content,
                "html.parser"
            )


            if soup.title:
                title = soup.title.get_text(strip=True)
            else:
                title = ""


            site_map[final_url] = title


            elapsed = time.time() - start_time


            print(
                f"取得成功: {len(site_map)}ページ | "
                f"経過時間: {elapsed / 60:.1f}分 | "
                f"{final_url} | {title}"
            )

            # ========================================
            # ページ内のリンクを取得
            # ========================================

            for a_tag in soup.find_all("a", href=True):


                link = urljoin(final_url, a_tag["href"])

                # URLを正規化
                link = normalize_url(link)


                if not link:
                    continue

                parsed = urlparse(link)


                if parsed.netloc.lower() != domain:
                    continue


                link_key = get_duplicate_key(link)

                if not link_key:
                    continue


                if (
                    link not in visited
                    and link_key not in seen_keys
                    and all(
                        get_duplicate_key(queued_url) != link_key
                        for queued_url in todo
                    )
                ):
                    todo.append(link)

        except requests.RequestException as e:
            print(f"取得失敗: {url} / {e}")

        except Exception as e:
            print(f"処理エラー: {url} / {e}")


# ========================================
# CSVファイルに保存
# ========================================

with open(
    csv_filename,
    "w",
    newline="",
    encoding="utf-8-sig"
) as f:

    writer = csv.writer(f)


    writer.writerow(["URL", "Title"])


    for url, title in site_map.items():
        writer.writerow([url, title])


# ========================================
# 結果を表示
# ========================================

elapsed = time.time() - start_time

print("\n========================================")
print("サイトマップの取得が完了しました！")
print("========================================")
print(f"取得したページ数: {len(site_map)}")
print(f"経過時間: {elapsed / 60:.1f}分")
print(f"保存先: {csv_filename}")