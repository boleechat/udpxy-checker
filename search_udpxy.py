import re
import requests
from bs4 import BeautifulSoup

# 固定频道
TARGET_UDP = "/udp/239.45.3.209:5140"
SEARCH_QUERY = f'"{TARGET_UDP}"'
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}
BING_URL = "https://www.bing.com/search?q=" + SEARCH_QUERY

def extract_links(html):
    soup = BeautifulSoup(html, "html.parser")
    links = []
    for a in soup.find_all("a", href=True):
        url = a["href"]
        if TARGET_UDP in url:
            m = re.search(r'https?://[^"' + "'" + r'\s<>]+/udp/239\.45\.3\.209:5140', url)
            if m:
                links.append(m.group(0))
    return list(set(links))

def is_link_alive(url):
    try:
        r = requests.get(url, timeout=5, stream=True)
        if r.status_code == 200:
            print(f"[✅] 可用: {url}")
            return True
    except:
        pass
    print(f"[❌] 不可用: {url}")
    return False

def main():
    print("正在搜索 Bing...")
    r = requests.get(BING_URL, headers=HEADERS)
    if r.status_code != 200:
        print("搜索失败")
        return

    raw_links = extract_links(r.text)
    print(f"共提取到 {len(raw_links)} 个链接")

    alive_links = []
    for link in raw_links:
        if is_link_alive(link):
            alive_links.append(link)

    with open("valid_udpxy.txt", "w", encoding="utf-8") as f:
        for link in alive_links:
            f.write(link + "\n")

    print(f"\n✅ 共 {len(alive_links)} 个可用链接，已写入 valid_udpxy.txt")

if __name__ == "__main__":
    main()
