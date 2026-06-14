import logging
import traceback
import pandas as pd
from datetime import datetime, timezone, timedelta
# pyrefly: ignore [missing-import]
from jobspy import scrape_jobs
from db import save_jobs, extract_country

import urllib.parse
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
import requests
import time
import re
# pyrefly: ignore [missing-import]
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def scrape_weworkremotely(search_term, hours_old):
    """
    Custom scraper for We Work Remotely using BS4 search.
    """
    logger.info(f"Starting custom WWR search scrape for query: {search_term}")
    jobs = []
    try:
        url = "https://weworkremotely.com/remote-jobs/search"
        clean_term = search_term.lower().replace(" developer", "").replace(" engineer", "").strip()
        params = {"term": clean_term}
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        r = requests.get(url, params=params, headers=headers, timeout=15)
        if r.status_code != 200:
            logger.error(f"WWR search returned status code {r.status_code}")
            return []
            
        soup = BeautifulSoup(r.text, 'html.parser')
        listings = soup.select('li.new-listing-container')
        
        now = datetime.now()
        
        for li in listings:
            link_el = li.find('a', href=lambda h: h and '/remote-jobs/' in h and 'find-your-plan' not in h)
            if not link_el:
                continue
                
            job_url = "https://weworkremotely.com" + link_el['href']
            
            title_el = li.select_one('.new-listing__header__title__text')
            title = title_el.text.strip() if title_el else "Flutter Developer"
            
            company_el = li.select_one('.new-listing__company-name')
            company = "Unknown Company"
            if company_el:
                company = company_el.get_text(strip=True)
            
            location_el = li.select_one('.new-listing__company-headquarters')
            location = location_el.text.strip() if location_el else "Remote"
            
            categories_els = li.select('.new-listing__categories__category')
            job_type = "Full-time"
            candidate_loc = "Anywhere in the World"
            if categories_els:
                job_type = categories_els[0].text.strip()
                if len(categories_els) > 1:
                    candidate_loc = categories_els[1].text.strip()
            
            # Parse relative date, e.g. "16d" or "3h"
            date_el = li.select_one('.new-listing__header__icons__date')
            date_str = datetime.now().strftime('%Y-%m-%d')
            if date_el:
                relative_str = date_el.text.strip().lower()
                try:
                    m = re.match(r'(\d+)h', relative_str)
                    if m:
                        hours = int(m.group(1))
                        dt = now - timedelta(hours=hours)
                    else:
                        m = re.match(r'(\d+)d', relative_str)
                        if m:
                            days = int(m.group(1))
                            dt = now - timedelta(days=days)
                        else:
                            dt = now
                    
                    # Age check
                    delta = now - dt
                    age_hours = delta.total_seconds() / 3600
                    if age_hours > hours_old:
                        continue
                        
                    date_str = dt.strftime('%Y-%m-%d')
                except Exception as e:
                    logger.error(f"Error parsing relative date {relative_str}: {str(e)}")
                    
            description = f"Remote job posting at {company} on We Work Remotely. Candidate location constraint: {candidate_loc}."
            
            jobs.append({
                'site': 'weworkremotely',
                'title': title,
                'company': company,
                'location': f"{location} ({candidate_loc})",
                'country': 'Remote',
                'job_type': job_type,
                'date_posted': date_str,
                'min_amount': None,
                'max_amount': None,
                'currency': 'USD',
                'is_remote': True,
                'job_url': job_url,
                'description': description
            })
            
        logger.info(f"Custom WWR search scrape finished. Found {len(jobs)} matches.")
        return jobs
    except Exception as e:
        logger.error(f"Error scraping We Work Remotely Search: {str(e)}")
        logger.error(traceback.format_exc())
        return []

def scrape_remoteok(search_term, hours_old):
    """
    Custom JSON scraper for RemoteOK API.
    """
    logger.info(f"Starting custom RemoteOK API scrape for query: {search_term}")
    jobs = []
    try:
        # RemoteOK API supports tag filtering. Let's use search term as tag.
        tag = urllib.parse.quote_plus(search_term.lower().replace(" developer", "").replace(" engineer", ""))
        url = f"https://remoteok.com/api?tag={tag}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code != 200:
            logger.error(f"RemoteOK API returned status code {r.status_code}")
            return []
            
        data = r.json()
        # The first item is a legal warning disclaimer, skip it
        if not isinstance(data, list) or len(data) <= 1:
            return []
            
        now = datetime.now()
        
        for item in data[1:]:
            epoch = item.get('date') # RemoteOK returns unix timestamp as string/int
            if not epoch:
                continue
                
            # Filter age
            try:
                dt = datetime.fromtimestamp(int(epoch))
                delta = now - dt
                age_hours = delta.total_seconds() / 3600
                if age_hours > hours_old:
                    continue
                date_str = dt.strftime('%Y-%m-%d')
            except Exception:
                date_str = datetime.now().strftime('%Y-%m-%d')
                
            title = item.get('position', 'Flutter Developer')
            company = item.get('company', 'Unknown Company')
            description = item.get('description', '')
            job_url = item.get('url', '')
            tags = item.get('tags', [])
            
            # Strict relevance check to filter out unrelated featured jobs or general feeds
            title_lower = title.lower()
            tags_lower = [t.lower() for t in tags if isinstance(t, str)]
            
            # Support comma-separated queries (e.g. "flutter, mobile")
            search_keywords = [k.strip().lower() for k in search_term.split(',') if k.strip()]
            
            matches_search = False
            for kw in search_keywords:
                # If keyword is in the title, or matches any of the tags
                if kw in title_lower or any(kw in t for t in tags_lower):
                    matches_search = True
                    break
                    
            if not matches_search:
                continue
            
            # Check salary numbers if available
            min_sal = item.get('salary_min')
            max_sal = item.get('salary_max')
            
            jobs.append({
                'site': 'remoteok',
                'title': title,
                'company': company,
                'location': item.get('location') or 'Remote',
                'country': 'Remote',
                'job_type': 'Full-time',
                'date_posted': date_str,
                'min_amount': float(min_sal) if min_sal else None,
                'max_amount': float(max_sal) if max_sal else None,
                'currency': 'USD',
                'is_remote': True,
                'job_url': job_url,
                'description': description
            })
            
        logger.info(f"Custom RemoteOK API scrape finished. Found {len(jobs)} matches.")
        return jobs
    except Exception as e:
        logger.error(f"Error scraping RemoteOK API: {str(e)}")
        logger.error(traceback.format_exc())
        return []

def scrape_remotive(search_term, hours_old):
    """
    Custom JSON scraper for Remotive API.
    """
    logger.info(f"Starting custom Remotive API scrape for query: {search_term}")
    jobs = []
    try:
        tag = urllib.parse.quote_plus(search_term)
        url = f"https://remotive.com/api/remote-jobs?search={tag}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code != 200:
            logger.error(f"Remotive API returned status code {r.status_code}")
            return []
            
        data = r.json()
        job_list = data.get('jobs', [])
        
        now = datetime.now(timezone.utc)
        
        for item in job_list:
            pub_date_str = item.get('publication_date')
            if not pub_date_str:
                continue
                
            try:
                if 'Z' in pub_date_str:
                    dt = datetime.fromisoformat(pub_date_str.replace('Z', '+00:00'))
                elif '+' in pub_date_str:
                    parts = pub_date_str.split('+')
                    dt = datetime.fromisoformat(parts[0] + '+' + parts[1])
                else:
                    dt = datetime.fromisoformat(pub_date_str).replace(tzinfo=timezone.utc)
                    
                delta = now - dt
                age_hours = delta.total_seconds() / 3600
                if age_hours > hours_old:
                    continue
                date_str = dt.strftime('%Y-%m-%d')
            except Exception as e:
                logger.error(f"Error parsing date {pub_date_str}: {str(e)}")
                date_str = datetime.now().strftime('%Y-%m-%d')
                
            title = item.get('title', 'Flutter Developer')
            company = item.get('company_name', 'Unknown Company')
            description = item.get('description', '')
            job_url = item.get('url', '')
            
            jobs.append({
                'site': 'remotive',
                'title': title,
                'company': company,
                'location': item.get('candidate_required_location') or 'Remote',
                'country': 'Remote',
                'job_type': item.get('job_type') or 'Full-time',
                'date_posted': date_str,
                'min_amount': None,
                'max_amount': None,
                'currency': 'USD',
                'is_remote': True,
                'job_url': job_url,
                'description': description
            })
            
        logger.info(f"Custom Remotive API scrape finished. Found {len(jobs)} matches.")
        return jobs
    except Exception as e:
        logger.error(f"Error scraping Remotive API: {str(e)}")
        logger.error(traceback.format_exc())
        return []

def scrape_himalayas(search_term, hours_old):
    """
    Custom JSON scraper for Himalayas API.
    """
    logger.info(f"Starting custom Himalayas API scrape for query: {search_term}")
    jobs = []
    try:
        url = "https://himalayas.app/jobs/api/search"
        params = {"q": search_term}
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        r = requests.get(url, params=params, headers=headers, timeout=15)
        if r.status_code != 200:
            logger.error(f"Himalayas API returned status code {r.status_code}")
            return []
            
        data = r.json()
        job_list = data.get('jobs', [])
        now = datetime.now(timezone.utc)
        
        for item in job_list:
            pub_epoch = item.get('pubDate')
            if not pub_epoch:
                continue
                
            try:
                dt = datetime.fromtimestamp(int(pub_epoch), tz=timezone.utc)
                delta = now - dt
                age_hours = delta.total_seconds() / 3600
                if age_hours > hours_old:
                    continue
                date_str = dt.strftime('%Y-%m-%d')
            except Exception as e:
                logger.error(f"Error parsing date {pub_epoch}: {str(e)}")
                date_str = datetime.now().strftime('%Y-%m-%d')
                
            title = item.get('title', 'Flutter Developer')
            company = item.get('companyName', 'Unknown Company')
            description = item.get('description', '')
            job_url = item.get('applicationLink') or item.get('link')
            
            if not job_url:
                continue
                
            loc_restrictions = item.get('locationRestrictions', [])
            location_str = ", ".join(loc_restrictions) if loc_restrictions else "Remote"
            
            jobs.append({
                'site': 'himalayas',
                'title': title,
                'company': company,
                'location': location_str,
                'country': 'Remote',
                'job_type': item.get('employmentType') or 'Full-time',
                'date_posted': date_str,
                'min_amount': float(item.get('minSalary')) if item.get('minSalary') else None,
                'max_amount': float(item.get('maxSalary')) if item.get('maxSalary') else None,
                'currency': item.get('currency') or 'USD',
                'is_remote': True,
                'job_url': job_url,
                'description': description
            })
            
        logger.info(f"Custom Himalayas API scrape finished. Found {len(jobs)} matches.")
        return jobs
    except Exception as e:
        logger.error(f"Error scraping Himalayas API: {str(e)}")
        logger.error(traceback.format_exc())
        return []

GOOGLE_REDIRECTS = {
    'instahyre': 'instahyre.com',
    'wellfound': 'wellfound.com',
    'cutshort': 'cutshort.io',
    'hirist': 'hirist.tech',
    'iimjobs': 'iimjobs.com',
    'theladders': 'theladders.com',
    'simplify': 'simplify.jobs',
    'flexjobs': 'flexjobs.com',
    'remoteco': 'remote.co',
    'internshala': 'internshala.com',
    'unstop': 'unstop.com'
}

def run_scrape_for_site(site, search_term, location, is_remote, hours_old, results_wanted, country_indeed="USA"):
    """
    Runs jobspy for a single site and returns a list of standardized job dictionaries.
    """
    logger.info(f"Starting scrape for site: {site} | query: {search_term} | location: {location}")
    try:
        # Call scrape_jobs for a single site
        # We wrap in a try-except to avoid one failing site crashing the whole run
        df = scrape_jobs(
            site_name=[site],
            search_term=search_term,
            location=location,
            is_remote=is_remote,
            hours_old=hours_old,
            results_wanted=results_wanted,
            country_indeed=country_indeed
        )
        
        if df is None or df.empty:
            logger.info(f"No jobs returned for site: {site}")
            return []
            
        logger.info(f"Successfully scraped {len(df)} jobs from {site}")
        return parse_jobspy_df(df, site)
        
    except Exception as e:
        logger.error(f"Error scraping {site}: {str(e)}")
        logger.error(traceback.format_exc())
        return []

def parse_jobspy_df(df, site_name):
    """
    Converts JobSpy DataFrame to standard dictionaries.
    Handles field normalization and date formats.
    """
    jobs = []
    
    # helper helper to safely extract fields
    def get_val(row, fields, default=None):
        for field in fields:
            if field in row and pd.notna(row[field]):
                return row[field]
            # check lowercase
            f_low = field.lower()
            if f_low in row and pd.notna(row[f_low]):
                return row[f_low]
            # check uppercase
            f_up = field.upper()
            if f_up in row and pd.notna(row[f_up]):
                return row[f_up]
        return default

    # Convert dataframe to records
    records = df.to_dict('records')
    
    for r in records:
        # Normalize date posted. If it's a string, keep it, if datetime, format it.
        raw_date = get_val(r, ['date_posted', 'date', 'posted'])
        date_str = ""
        if raw_date:
            if isinstance(raw_date, (datetime, pd.Timestamp)):
                date_str = raw_date.strftime('%Y-%m-%d')
            else:
                # String cleanup
                date_str = str(raw_date).split('T')[0].split(' ')[0]
        else:
            date_str = datetime.now().strftime('%Y-%m-%d')

        # Location parsing
        loc = get_val(r, ['location', 'formatted_location'])
        if not loc:
            city = get_val(r, ['city'])
            state = get_val(r, ['state'])
            country = get_val(r, ['country'])
            parts = [p for p in [city, state, country] if p]
            loc = ", ".join(parts) if parts else "Remote"

        # Construct direct apply URL if available
        job_url = get_val(r, ['job_url_direct', 'job_url', 'url', 'link'])
        
        job = {
            'site': site_name,
            'title': get_val(r, ['title', 'job_title'], 'Flutter Developer'),
            'company': get_val(r, ['company', 'company_name', 'organization'], 'Unknown Company'),
            'location': loc,
            'country': extract_country(loc),
            'job_type': get_val(r, ['job_type', 'employment_type'], 'Full-time'),
            'date_posted': date_str,
            'min_amount': get_val(r, ['min_amount', 'min_salary']),
            'max_amount': get_val(r, ['max_amount', 'max_salary']),
            'currency': get_val(r, ['currency'], 'USD'),
            'is_remote': get_val(r, ['is_remote', 'remote'], True),
            'job_url': job_url,
            'description': get_val(r, ['description', 'desc', 'body'], '')
        }
        
        if job['job_url']:
            jobs.append(job)
            
    return jobs

def scrape_and_save_all(search_term="Flutter Developer", location="Remote", is_remote=True, hours_old=72, results_per_site=25, sites=None, country_indeed="USA"):
    """
    Orchestrates scraping multiple sites and saves new findings to the database.
    Yields progress string for Server-Sent Events (SSE).
    """
    if not sites:
        sites = [
            'linkedin', 'google', 'zip_recruiter', 'indeed', 'glassdoor', 'bayt', 'naukri', 'bdjobs', 
            'weworkremotely', 'remoteok', 'remotive', 'himalayas', 'instahyre', 'wellfound', 'cutshort', 'hirist', 
            'iimjobs', 'theladders', 'simplify', 'flexjobs', 'remoteco', 'internshala', 'unstop'
        ]
        
    yield f"Starting search for '{search_term}' globally (last {hours_old} hours)...\n"
    
    all_jobs = []
    
    for site in sites:
        yield f"Scraping {site.upper()}...\n"
        if site == 'weworkremotely':
            site_jobs = scrape_weworkremotely(search_term, hours_old)
        elif site == 'remoteok':
            site_jobs = scrape_remoteok(search_term, hours_old)
        elif site == 'remotive':
            site_jobs = scrape_remotive(search_term, hours_old)
        elif site == 'himalayas':
            site_jobs = scrape_himalayas(search_term, hours_old)
        elif site in GOOGLE_REDIRECTS:
            domain = GOOGLE_REDIRECTS[site]
            query_term = f'"{search_term}" site:{domain}'
            site_jobs = run_scrape_for_site(
                site='google',
                search_term=query_term,
                location=location,
                is_remote=is_remote,
                hours_old=hours_old,
                results_wanted=results_per_site,
                country_indeed=country_indeed
            )
            # Rebrand the results under the specific board domain
            for job in site_jobs:
                job['site'] = site
        else:
            site_jobs = run_scrape_for_site(
                site=site,
                search_term=search_term,
                location=location,
                is_remote=is_remote,
                hours_old=hours_old,
                results_wanted=results_per_site,
                country_indeed=country_indeed
            )
            
        if site_jobs:
            all_jobs.extend(site_jobs)
            yield f"Found {len(site_jobs)} candidates on {site.upper()}.\n"
        else:
            yield f"No jobs found or access blocked on {site.upper()}.\n"
            
        # Small delay between sites to avoid triggering IP blocks/rate limits
        time.sleep(1.0)
            
    yield f"Scrape completed. Found {len(all_jobs)} total listings across all platforms.\n"
    
    if all_jobs:
        yield "Saving results and updating application tracker database...\n"
        new_count, saved_count = save_jobs(all_jobs)
        yield f"Finished database sync. Saved {saved_count} jobs total, including {new_count} newly discovered jobs!\n"
    else:
        yield "No jobs to save.\n"
