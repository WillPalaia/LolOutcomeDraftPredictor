import requests, re

def extract_latest_riot_key():
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36'}
        r = requests.get('https://lolesports.com/en-US', headers=headers, timeout=10)
        js_files = re.findall(r'src="([^"]+\.js)"', r.text)
        print(f"Found {len(js_files)} JS script bundles on lolesports.com")
        for js in js_files:
            if not js.startswith('http'):
                js = 'https://lolesports.com' + js
            r_js = requests.get(js, headers=headers, timeout=10)
            matches = re.findall(r'0TvQ[a-zA-Z0-9_-]{20,40}', r_js.text)
            if matches:
                print('Discovered API key from bundle:', matches[0])
                return matches[0]
    except Exception as e:
        print('Auto-discovery error:', e)
    return None

key = extract_latest_riot_key()
print("Final Key:", key)
