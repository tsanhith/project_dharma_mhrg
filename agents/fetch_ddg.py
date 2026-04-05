import sys
import asyncio
import json
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

async def search_jobs(query):
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        page = await b.new_page(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36')
        
        url = f"https://html.duckduckgo.com/html/?q={query}"
        await page.goto(url, wait_until='domcontentloaded')
        html = await page.content()
        await b.close()

        soup = BeautifulSoup(html, 'html.parser')
        jobs = []
        for result in soup.find_all('div', class_='result'):
            a = result.find('a', class_='result__url')
            t = result.find('h2', class_='result__title')
            s = result.find('a', class_='result__snippet')
            
            if not a or not t: continue
            
            link = a.get('href', '')
            # Clean up tracking duckduckgo url if necessary, but usually class result__url has actual url
            
            title = t.text.strip()
            snippet = s.text.strip() if s else ''
            
            if 'ad_domain' in link: continue # skip ads
            
            # Very basic extraction: 
            # Duckduckgo usually formats as "Software Engineer - Company - LinkedIn"
            
            jobs.append({
                'url': link,
                'title': title, # Will refine in python
                'snippet': snippet,
                'companyName': 'Unknown (See Link)'
            })
            
        print(json.dumps(jobs))

if __name__ == '__main__':
    query = sys.argv[1] if len(sys.argv) > 1 else "site:linkedin.com/jobs/view/ software engineer"
    asyncio.run(search_jobs(query))
