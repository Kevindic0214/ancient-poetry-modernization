import requests
from bs4 import BeautifulSoup
import json
import time
import re

# 基本設定
BASE_TRANSLATION_URL = "https://fanti.dugushici.com/ancient_proses/1/prose_translations/{}"
BASE_ORIGINAL_URL = "https://fanti.dugushici.com/ancient_proses/{}"
HEADERS = {"User-Agent": "Mozilla/5.0"}

def parse_translation_page(trans_id):
    """
    解析翻譯頁面，回傳初步資料：
    - translation_id, title, original_id, translations (list), notes (list), translation_url
    """
    url = BASE_TRANSLATION_URL.format(trans_id)
    resp = requests.get(url, headers=HEADERS)
    if resp.status_code != 200:
        print(f"[跳過] ID {trans_id} HTTP {resp.status_code}")
        return None

    soup = BeautifulSoup(resp.text, "html.parser")
    # 1. 確認標題是否存在
    header = soup.select_one("div.section1 h1")
    if not header or "譯文及註釋" not in header.text:
        print(f"[跳過] ID {trans_id} 無『譯文及註釋』")
        return None

    # 2. 取得 breadcrumb 中的 title 和 original_id
    bc = soup.select("div.breadcrumbs a")
    title = bc[-1].text.replace("譯文及註釋", "").strip() if bc else f"詩詞_{trans_id}"
    match = re.search(r"/ancient_proses/(\d+)", bc[-2]['href']) if len(bc) >= 2 else None
    original_id = match.group(1) if match else None

    # 3. 抓 translations
    block = soup.select_one("div.shangxicont")
    translations = []
    if block:
        parsing = False
        for line in block.decode_contents().split("<br>"):
            txt = BeautifulSoup(line, "html.parser").text.strip()
            if not txt:
                continue
            if txt.startswith("譯文"):
                parsing = True
                continue
            if txt.startswith("註釋"):
                parsing = False
            if parsing:
                translations.append(txt)

    # 4. 抓 notes
    notes = []
    notes_header = block.find("strong", string=re.compile("註釋")) if block else None
    if notes_header:
        parent_p = notes_header.find_parent("p")
        if parent_p:
            for line in parent_p.decode_contents().split("<br>"):
                txt = BeautifulSoup(line, "html.parser").text.strip()
                if txt and not txt.startswith("作者"):
                    notes.append(txt)

    return {
        "translation_id": trans_id,
        "title": title,
        "original_id": original_id,
        "translations": translations,
        "notes": notes,
        "translation_url": url
    }

def parse_original_page(original_id):
    """
    解析原文頁面，回傳 original_text, author, dynasty
    """
    url = BASE_ORIGINAL_URL.format(original_id)
    resp = requests.get(url, headers=HEADERS)
    if resp.status_code != 200:
        print(f"[跳過] original_id {original_id} HTTP {resp.status_code}")
        return None

    soup = BeautifulSoup(resp.text, "html.parser")
    # 原文
    content_div = soup.select_one("div.content")
    original_text = content_div.get_text(separator="", strip=True) if content_div else ""
    # 作者
    author_tag = soup.select_one('[itemprop="author"] span[itemprop="name"]')
    author = author_tag.text.strip() if author_tag else ""
    # 朝代
    dynasty_tag = soup.select_one('[itemprop="dateCreated"]')
    dynasty = dynasty_tag.text.strip() if dynasty_tag else ""

    return {
        "original_text": original_text,
        "author": author,
        "dynasty": dynasty
    }

# 主程式
def main(start_id=1, end_id=5699, output_file="poetry_with_translation.jsonl"):
    seen_orig = set()
    with open(output_file, "w", encoding="utf-8") as fout:
        for trans_id in range(start_id, end_id + 1):
            data = parse_translation_page(trans_id)
            if not data or not data["translations"] or not data["original_id"]:
                continue
            if data["original_id"] in seen_orig:
                print(f"[跳過] 重複 original_id {data['original_id']}")
                continue

            orig_data = parse_original_page(data["original_id"])
            if not orig_data:
                continue

            # 合併
            record = {
                "translation_id": data["translation_id"],
                "original_id": data["original_id"],
                "title": data["title"],
                "dynasty": orig_data["dynasty"],
                "author": orig_data["author"],
                "original_text": orig_data["original_text"],
                "translations": data["translations"],
                "notes": data["notes"],
                "translation_url": data["translation_url"]
            }

            fout.write(json.dumps(record, ensure_ascii=False) + "\n")
            seen_orig.add(data["original_id"])
            print(f"[✓] 已儲存 original_id {data['original_id']} - {data['title']}")
            time.sleep(1)  # 避免被封

    print("✅ 全部完成，已輸出至", output_file)

if __name__ == "__main__":
    main()
