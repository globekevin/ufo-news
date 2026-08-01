"""Test extracting real source URLs from Google News pages"""
import requests, re, json
from bs4 import BeautifulSoup

url = 'https://news.google.com/rss/articles/CBMiywFBVV95cUxNX1RCMEctdzlQUVViNk84LVRsRVlYSWZlMlBIelNNQWVRUlhXYU9mTGNIZTV1d0dhSHRmamJqaXBpVEp5SlNkaUJHUXJfWXVaV2dXWkMzMWlGaDFiZl9zVlBWVFdzZGFHTk9GdF8zQjhiTGI0TTFNVVRnMmhqZ3h2aGo1UGpGVTlqbFZGQTZ4MGZWSXotLTllUDBhSzdrRk13YzhWX01pSFlxM1h3bGNOR3lJa0JpZGthQTVCeW5hSEtKNmpyZ1ZsZ3VmVQ?oc=5'

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
})
resp = session.get(url, timeout=15)
soup = BeautifulSoup(resp.content, 'lxml')

# 1. Try canonical link
canonical = soup.find('link', rel='canonical')
if canonical:
    print(f'1. Canonical: {canonical.get("href")}')

# 2. Try all meta content for external URLs
for meta in soup.find_all('meta'):
    content = meta.get('content', '')
    if content.startswith('http') and 'google' not in content and len(content) > 30:
        print(f'2. Meta URL: {content[:120]}')

# 3. Try JSON-LD
for script in soup.find_all('script', type='application/ld+json'):
    try:
        data = json.loads(script.string)
        print(f'3. JSON-LD keys: {list(data.keys()) if isinstance(data, dict) else "not dict"}')
        for k, v in (data.items() if isinstance(data, dict) else []):
            if isinstance(v, str) and v.startswith('http') and 'google' not in v:
                print(f'   {k}: {v[:120]}')
    except: pass

# 4. Try data attributes with URLs
for el in soup.find_all(attrs={'data-url': True}):
    url_val = el.get('data-url', '')
    if 'http' in url_val and 'google' not in url_val:
        print(f'4. data-url: {url_val[:120]}')

# 5. Search ALL text in script tags for article URLs
all_script_text = ''
for script in soup.find_all('script'):
    if script.string:
        all_script_text += script.string + '\n'

# Pattern: URLs that contain article-related domains
urls = re.findall(r'https?://(?:www\.)?[a-zA-Z0-9.-]+/[^"\s\'<>]+', all_script_text)
seen = set()
for u in urls:
    domain = re.search(r'https?://(?:www\.)?([^/]+)', u)
    if domain:
        dom = domain.group(1)
        if dom not in ('news.google.com', 'www.google.com', 'googleads.g.doubleclick.net',
                       'fonts.googleapis.com', 'fonts.gstatic.com', 'www.googletagmanager.com',
                       'schema.org', 'www.w3.org'):
            if u not in seen:
                seen.add(u)
                print(f'5. External URL: {u[:150]}')

# 6. Print top-level structure
print(f'\n6. Page title: {soup.title.string if soup.title else "none"}')
print(f'7. Body text preview: {soup.body.get_text(strip=True)[:200] if soup.body else "none"}')
