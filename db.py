import sqlite3
import os
import hashlib
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jobs.db")

# Vercel has a read-only filesystem except for /tmp.
# If running on Vercel, put the SQLite db in /tmp.
if os.environ.get('VERCEL') == '1':
    DB_PATH = "/tmp/jobs.db"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def extract_country(location_str):
    """
    Utility helper to normalize and extract country from location strings.
    """
    if not location_str:
        return "Global"
    loc = location_str.lower()
    if "remote" in loc:
        return "Remote"
    if "india" in loc or "bengaluru" in loc or "pune" in loc or "mumbai" in loc or "hyderabad" in loc or "chennai" in loc or "noida" in loc:
        return "India"
    if "united states" in loc or "usa" in loc or "united states of america" in loc or " san francisco" in loc or " new york" in loc or " los angeles" in loc:
        return "United States"
    # Match standalone 'us' code
    loc_parts = [p.strip() for p in loc.split(',')]
    if 'us' in loc_parts or 'usa' in loc_parts:
        return "United States"
        
    if "united kingdom" in loc or "uk" in loc or "london" in loc or "england" in loc or "scotland" in loc:
        return "United Kingdom"
    if "canada" in loc or "toronto" in loc or "vancouver" in loc or "montreal" in loc:
        return "Canada"
    if "germany" in loc or "berlin" in loc or "munich" in loc or "hamburg" in loc or "frankfurt" in loc:
        return "Germany"
    if "australia" in loc or "sydney" in loc or "melbourne" in loc or "brisbane" in loc:
        return "Australia"
    if "bangladesh" in loc or "dhaka" in loc or "chittagong" in loc:
        return "Bangladesh"
    if "united arab emirates" in loc or "uae" in loc or "dubai" in loc or "abu dhabi" in loc:
        return "United Arab Emirates"
    if "singapore" in loc:
        return "Singapore"
        
    # Standard fallback: fetch trailing token after comma
    if len(loc_parts) > 1:
        country_candidate = loc_parts[-1]
        if len(country_candidate) > 2:
            return country_candidate.title()
            
    return "Global"

def backfill_countries():
    """
    Iterates through all jobs in the database with null or empty countries and backfills them.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, location FROM jobs WHERE country IS NULL OR country = ''")
    rows = cursor.fetchall()
    
    if rows:
        print(f"Backfilling country fields for {len(rows)} existing jobs in database...")
        for row in rows:
            job_id = row['id']
            location = row['location']
            country = extract_country(location)
            cursor.execute("UPDATE jobs SET country = ? WHERE id = ?", (country, job_id))
        conn.commit()
    conn.close()

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            session_id TEXT DEFAULT 'default',
            site TEXT,
            title TEXT,
            company TEXT,
            location TEXT,
            country TEXT,
            job_type TEXT,
            date_posted TEXT,
            min_amount REAL,
            max_amount REAL,
            currency TEXT,
            is_remote INTEGER,
            job_url TEXT,
            description TEXT,
            status TEXT DEFAULT 'Not Applied',
            notes TEXT DEFAULT '',
            date_applied TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Run migration to add country column if database already exists
    try:
        cursor.execute("ALTER TABLE jobs ADD COLUMN country TEXT")
    except sqlite3.OperationalError:
        pass # Column already exists

    # Run migration to add session_id column if database already exists
    try:
        cursor.execute("ALTER TABLE jobs ADD COLUMN session_id TEXT DEFAULT 'default'")
    except sqlite3.OperationalError:
        pass # Column already exists
        
    conn.commit()
    conn.close()
    
    # Backfill country values
    backfill_countries()

def generate_job_id(title, company, job_url, session_id):
    # Create a unique ID from company, title, job url, and session_id to prevent duplicates per user
    raw_str = f"{company.strip().lower()}|{title.strip().lower()}|{job_url.strip()}|{session_id}"
    return hashlib.md5(raw_str.encode('utf-8')).hexdigest()

def save_jobs(jobs_list, session_id='default'):
    """
    Saves a list of dictionaries representing jobs into the DB.
    If a job already exists for this session_id, update its details but preserve status and notes.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    saved_count = 0
    new_count = 0

    for job in jobs_list:
        title = job.get('title', 'Unknown Title')
        company = job.get('company', 'Unknown Company')
        job_url = job.get('job_url', '')
        
        if not job_url:
            continue
            
        job_id = generate_job_id(title, company, job_url, session_id)
        
        # Check if job exists
        cursor.execute("SELECT status, notes, date_applied FROM jobs WHERE id = ?", (job_id,))
        row = cursor.fetchone()
        
        is_remote_val = 1 if job.get('is_remote') else 0
        
        if row is None:
            # New job
            cursor.execute("""
                INSERT INTO jobs (
                    id, session_id, site, title, company, location, country, job_type, date_posted, 
                    min_amount, max_amount, currency, is_remote, job_url, description
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job_id,
                session_id,
                job.get('site', 'unknown'),
                title,
                company,
                job.get('location', ''),
                job.get('country', ''),
                job.get('job_type', ''),
                job.get('date_posted', ''),
                job.get('min_amount'),
                job.get('max_amount'),
                job.get('currency', ''),
                is_remote_val,
                job_url,
                job.get('description', '')
            ))
            new_count += 1
        else:
            # Existing job - update information except status, notes, and date_applied
            cursor.execute("""
                UPDATE jobs SET
                    site = ?,
                    title = ?,
                    company = ?,
                    location = ?,
                    country = ?,
                    job_type = ?,
                    date_posted = ?,
                    min_amount = ?,
                    max_amount = ?,
                    currency = ?,
                    is_remote = ?,
                    job_url = ?,
                    description = ?
                WHERE id = ? AND session_id = ?
            """, (
                job.get('site', 'unknown'),
                title,
                company,
                job.get('location', ''),
                job.get('country', ''),
                job.get('job_type', ''),
                job.get('date_posted', ''),
                job.get('min_amount'),
                job.get('max_amount'),
                job.get('currency', ''),
                is_remote_val,
                job_url,
                job.get('description', ''),
                job_id,
                session_id
            ))
        saved_count += 1
            
    conn.commit()
    conn.close()
    return new_count, saved_count

def get_jobs(filters=None, session_id='default'):
    """
    Returns jobs based on filters like status, site, remote, search query, etc.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = "SELECT * FROM jobs"
    params = []
    where_clauses = ["session_id = ?"]
    params.append(session_id)
    
    if filters:
        if filters.get('status'):
            where_clauses.append("status = ?")
            params.append(filters['status'])
        if filters.get('site'):
            where_clauses.append("site = ?")
            params.append(filters['site'])
        if filters.get('country'):
            where_clauses.append("country = ?")
            params.append(filters['country'])
        if filters.get('is_remote') is not None:
            where_clauses.append("is_remote = ?")
            params.append(1 if filters['is_remote'] else 0)
        if filters.get('search'):
            where_clauses.append("(title LIKE ? OR company LIKE ? OR description LIKE ?)")
            search_param = f"%{filters['search']}%"
            params.extend([search_param, search_param, search_param])
            
    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)
        
    # Order by newest first
    query += " ORDER BY date_posted DESC, created_at DESC"
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    
    jobs_list = [dict(row) for row in rows]
    conn.close()
    return jobs_list

def update_job_status(job_id, status, notes=None, session_id='default'):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    date_applied = None
    if status == 'Applied':
        date_applied = datetime.now().strftime('%Y-%m-%d')
        
    if notes is not None:
        if status == 'Applied':
            cursor.execute("""
                UPDATE jobs 
                SET status = ?, notes = ?, date_applied = COALESCE(date_applied, ?) 
                WHERE id = ? AND session_id = ?
            """, (status, notes, date_applied, job_id, session_id))
        else:
            cursor.execute("""
                UPDATE jobs 
                SET status = ?, notes = ? 
                WHERE id = ? AND session_id = ?
            """, (status, notes, job_id, session_id))
    else:
        if status == 'Applied':
            cursor.execute("""
                UPDATE jobs 
                SET status = ?, date_applied = COALESCE(date_applied, ?) 
                WHERE id = ? AND session_id = ?
            """, (status, date_applied, job_id, session_id))
        else:
            cursor.execute("""
                UPDATE jobs 
                SET status = ? 
                WHERE id = ? AND session_id = ?
            """, (status, job_id, session_id))
            
    conn.commit()
    conn.close()

def get_stats(session_id='default'):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    stats = {}
    
    cursor.execute("SELECT COUNT(*) FROM jobs WHERE session_id = ?", (session_id,))
    stats['total'] = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM jobs WHERE is_remote = 1 AND session_id = ?", (session_id,))
    stats['remote'] = cursor.fetchone()[0]
    
    cursor.execute("SELECT status, COUNT(*) FROM jobs WHERE session_id = ? GROUP BY status", (session_id,))
    status_counts = cursor.fetchall()
    for row in status_counts:
        stats[row[0].lower().replace(' ', '_')] = row[1]
        
    # Fill in defaults if not present
    for s in ['not_applied', 'applied', 'interviewing', 'offer', 'rejected']:
        if s not in stats:
            stats[s] = 0
            
    conn.close()
    return stats

def clear_all_jobs(session_id='default'):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM jobs WHERE session_id = ?", (session_id,))
    conn.commit()
    conn.close()
