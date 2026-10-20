import urllib.request
from bs4 import BeautifulSoup

def get_chapter(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    html = urllib.request.urlopen(req).read().decode('utf-8', 'ignore')
    soup = BeautifulSoup(html, 'html.parser')
    
    title_elem = soup.find('h2', class_='current-chapter')
    title = title_elem.text.strip().upper() if title_elem else "CHƯƠNG"
    
    content_div = soup.find('div', class_='truyen')
    if content_div:
        for br in content_div.find_all('br'):
            br.replace_with('\n')
        paragraphs = content_div.get_text().split('\n\n')
        paragraphs = [p.strip() for p in paragraphs if p.strip()]
    else:
        paragraphs = []
        
    next_a = soup.find('a', class_='next')
    next_url = next_a['href'] if next_a and next_a.has_attr('href') else None
    
    return title, paragraphs, next_url

url = 'https://metruyenchuvn.org/ta-mo-phong-truong-sinh-lo-dich/chuong-1-nI_v99lx!2Xc'
t, p, n = get_chapter(url)
print("Title:", t.encode('ascii', 'ignore'))
print("Paragraphs len:", len(p))
if p: print("First p:", p[0].encode('ascii', 'ignore')[:50])
print("Next URL:", n)
