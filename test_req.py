
import requests
from bs4 import BeautifulSoup
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124 Safari/537.36'}
r = requests.get('https://html.duckduckgo.com/html/?q=site:linkedin.com/jobs/view/+software+engineer', headers=headers)
soup = BeautifulSoup(r.text, 'html.parser')
links = []
for el in soup.find_all('a', class_='result__url'):
    links.append(el.get('href'))
for el in soup.find_all('div', class_='result'):
    h2 = el.find('h2', class_='result__title')
    a = el.find('a', class_='result__url')
    if a and h2:
        print(a.get('href'), h2.text.strip()[:40])
print('Total links:', len(links))

