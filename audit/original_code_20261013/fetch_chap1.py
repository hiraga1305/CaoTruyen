import urllib.request
import ssl
from bs4 import BeautifulSoup

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

url = 'https://www.piaotia.com/html/16/16014/12033453.html'
headers = {'User-Agent': 'Mozilla/5.0'}

req = urllib.request.Request(url, headers=headers)
html = urllib.request.urlopen(req, context=ctx, timeout=10).read().decode('gbk', 'ignore')
soup = BeautifulSoup(html, 'html.parser')

h1 = soup.find('h1')
title = h1.text.strip() if h1 else "第1章 面试"

for s in soup.find_all(['script', 'style', 'a', 'table', 'div']):
    s.decompose()

raw_text = soup.get_text()
paragraphs = []
for p in raw_text.split('\xa0\xa0\xa0\xa0'):
    clean_p = p.strip()
    if clean_p and not clean_p.startswith('选择背景颜色') and not clean_p.startswith('选择字体大小') and not '飘天文学' in clean_p and not '上一章' in clean_p:
        paragraphs.append(clean_p)

with open('chap1_raw.txt', 'w', encoding='utf-8') as f:
    f.write(title + '\n\n')
    f.write('\n\n'.join(paragraphs))

print(f"Saved Chapter 1 raw: {len(paragraphs)} paragraphs, total {sum(len(p) for p in paragraphs)} chars.")
