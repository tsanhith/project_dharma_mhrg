import asyncio
import json
import sys
import requests
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
import urllib.parse
from typing import List, Dict

# Fetch LinkedIn via Guest API (Fast)
def fetch_linkedin(query: str) -> List[Dict]:
    jobs = []
    encoded_query = urllib.parse.quote(query)
    # Get 2 pages
    for page in range(2):
        start = page * 10
        url = f'https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords={encoded_query}&location=Remote&start={start}'
        h = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        try:
            r = requests.get(url, headers=h, timeout=10)
            soup = BeautifulSoup(r.text, 'html.parser')
            for li in soup.find_all('li'):
                link = li.find('a', class_='base-card__full-link')
                title = li.find('h3', class_='base-search-card__title')
                company = li.find('h4', class_='base-search-card__subtitle')
                if link and title and company:
                    url_clean = link.get('href', '').split('?')[0]
                    jobs.append({
                        'url': url_clean,
                        'title': title.text.strip(),
                        'companyName': company.text.strip(),
                        'source': 'LinkedIn'
                    })
        except Exception:
            pass
    return jobs

# Fetch from Remotive (Fast, global remote jobs)
def fetch_remotive(query: str) -> List[Dict]:
    jobs = []
    url = f"https://remotive.com/api/remote-jobs?search={query}"
    try:
        r = requests.get(url, timeout=10)
        for j in r.json().get('jobs', [])[:15]:
            jobs.append({
                'url': j.get('url'),
                'title': j.get('title'),
                'companyName': j.get('company_name'),
                'source': 'Remotive'
            })
    except Exception:
        pass
    return jobs

# Fetch Indeed via Playwright
async def fetch_indeed_and_naukri(query: str) -> List[Dict]:
    jobs = []
    try:
        async with async_playwright() as p:
            b = await p.chromium.launch(headless=True)
            page = await b.new_page(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36',
                viewport={"width": 1280, "height": 720}
            )
            
            # --- Indeed ---
            try:
                indeed_url = f"https://www.indeed.com/jobs?q={urllib.parse.quote(query)}&l=Remote"
                await page.goto(indeed_url, wait_until='domcontentloaded', timeout=15000)
                await page.wait_for_timeout(2000) # Let it render
                html = await page.content()
                soup = BeautifulSoup(html, 'html.parser')
                
                for div in soup.find_all('td', class_='resultContent'):
                    title_elem = div.find('h2', class_='jobTitle')
                    company_elem = div.find('span', class_='companyName') or div.find('span', {'data-testid': 'company-name'})
                    if title_elem and company_elem:
                        a = title_elem.find('a')
                        if a and a.get('href'):
                            link = 'https://www.indeed.com' + a.get('href')
                            jobs.append({
                                'url': link,
                                'title': title_elem.text.strip(),
                                'companyName': company_elem.text.strip(),
                                'source': 'Indeed'
                            })
            except Exception:
                pass
                
            # --- Naukri ---
            try:
                naukri_url = f"https://www.naukri.com/{query.replace(' ', '-')}-jobs"
                await page.goto(naukri_url, wait_until='domcontentloaded', timeout=15000)
                await page.wait_for_timeout(2000)
                html = await page.content()
                soup = BeautifulSoup(html, 'html.parser')
                
                for div in soup.find_all('div', class_='srp-jobtuple-wrapper'):
                    a_title = div.find('a', class_='title')
                    a_comp = div.find('a', class_='comp-name')
                    if a_title and a_comp:
                        jobs.append({
                            'url': a_title.get('href'),
                            'title': a_title.text.strip(),
                            'companyName': a_comp.text.strip(),
                            'source': 'Naukri'
                        })
            except Exception:
                pass

            await b.close()
    except Exception:
        pass
        
    return jobs

async def main(query: str):
    # Run requests concurrently alongside Playwright
    loop = asyncio.get_event_loop()
    linkedin_jobs = await loop.run_in_executor(None, fetch_linkedin, query)
    remotive_jobs = await loop.run_in_executor(None, fetch_remotive, query)
    pw_jobs = await fetch_indeed_and_naukri(query)
    
    all_jobs = linkedin_jobs + remotive_jobs + pw_jobs
    print(json.dumps(all_jobs))

if __name__ == '__main__':
    query = sys.argv[1] if len(sys.argv) > 1 else "Software Engineer"
    asyncio.run(main(query))
