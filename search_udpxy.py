import re
import requests
from bs4 import BeautifulSoup

TARGET_UDP = "/udp/239.45.3.209:5140"
SEARCH_QUERY = f'"{TARGET_UDP}"'
HEADERS = {
    "User-Agent": "Mozilla/5.0"
}
BING_URL = "https://www.bing.com/search?q=" + SEARCH_QUERY

def extract_links_from_html(html):
    soup = BeautifulSoup(html, "html.parser")
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("http") and not href.startswith("/"):
            links.append(href)
    return list(set(links))

def extract_udpxy_from_content(content):
    # 匹配 http/https + /udp/239.45.3.209:5140
    pattern = r'https?://[^\s"\'<>]+/udp/239\.45\.3\.209:5140'
    return re.findall(pattern, content)

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
    print("🔎 正在搜索 Bing...")
    r = requests.get(BING_URL, headers=HEADERS)
    if r.status_code != 200:
        print("搜索失败")
        return

    search_page = r.text
    result_links = extract_links_from_html(search_page)
    print(f"🔗 提取到搜索结果链接 {len(result_links)} 个")

    found_udpxy = set()

    for link in result_links:
        try:
            res = requests.get(link, headers=HEADERS, timeout=8)
            if res.status_code == 200:
                udpxy_links = extract_udpxy_from_content(res.text)
                for u in udpxy_links:
                    found_udpxy.add(u)
        except:
            pass

    print(f"📡 共找到可能的 udpxy 链接：{len(found_udpxy)}")

    alive = []
    for link in found_udpxy:
        if is_link_alive(link):
            alive.append(link)

    with open("valid_udpxy.txt", "w", encoding="utf-8") as f:
        for link in alive:
            f.write(link + "\n")

    print(f"\n✅ 最终可用链接：{len(alive)} 条，已写入 valid_udpxy.txt")

if __name__ == "__main__":
    main()
