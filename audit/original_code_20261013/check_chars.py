import urllib.request
from bs4 import BeautifulSoup
import re

req = urllib.request.Request('https://truyenc.net/truyen/ta-mo-phong-truong-sinh-lo-truyen-full/chuong-2', headers={'User-Agent': 'Mozilla/5.0'})
html = urllib.request.urlopen(req).read().decode('utf-8', 'ignore')
soup = BeautifulSoup(html, 'html.parser')
txt = soup.find('article').get_text()

# Find characters that are not standard Vietnamese alphabet, numbers, spaces, or basic punctuation
vietnamese_chars = "a-zA-Z0-9ÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚÝàáâãèéêìíòóôõùúýĂăĐđĨĩŨũƠơƯưẠạẢảẤấẦầẨẩẪẫẬậẮắẰằẲẳẴẵẶặẸẹẺẻẼẽẾếỀềỂểỄễỆệỈỉỊịỌọỎỏỐốỒồỔổỖỗỘộỚớỜờỞởỠỡỢợỤụỦủỨứỪừỬửỮữỰựỲỳỴỵỶỷỸỹ"
allowed_punct = r"\s.,;:!?'\"()\[\]{}\-–—_/"

pattern = f"[^{vietnamese_chars}{allowed_punct}]"
weird = set(re.findall(pattern, txt))
print("Weird chars:", weird)
print("Representations:", [c.encode('utf-8') for c in weird])
