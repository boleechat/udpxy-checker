import os
import base64
import requests

EMAIL = os.environ["FOFA_EMAIL"]
KEY = os.environ["FOFA_API_KEY"]
QUERY = 'body="udp/" && port="5555"'  # 可根据你测试时 FOFA 搜索页面微调
PAGE_SIZE = 100
MAX_PAGES = 1  # 免费用户最多一页

UDP_PATH = "/udp/239.45.3.209:5140"

def fofa_search(query, page):
    b64_query = base64.b64encode(query.encode()).decode()
    url = f"https://fofa.info/api/v1/search?email={EMAIL}&key={KEY}&qbase64={b64_query}&page={page}&size={PAGE_SIZE}&fields=host"
    r = requests.get(url)
    if r.status_code == 200:
        return r.json().get("results", [])
    else:
        print("请求失败", r.status_code, r.text)
        return []

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
    all_hosts = set()
    for page in range(1, MAX_PAGES + 1):
        print(f"🔍 FOFA 第 {page} 页（免费接口）...")
        results = fofa_search(QUERY, page)
        if not results:
            break
        for host in results:
            all_hosts.add(host)

    print(f"\n🌐 共获取到 {len(all_hosts)} 个 udpxy 服务")

    alive_links = []
    for host in all_hosts:
        full_url = f"{host}{UDP_PATH}"
        if is_link_alive(full_url):
            alive_links.append(full_url)

    with open("valid_udpxy.txt", "w", encoding="utf-8") as f:
        for link in alive_links:
            f.write(link + "\n")

    print(f"\n✅ 最终可用链接 {len(alive_links)} 条，已写入 valid_udpxy.txt")

if __name__ == "__main__":
    main()
