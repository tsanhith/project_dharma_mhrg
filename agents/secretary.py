import os
import json
import base64
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from database.db import SessionLocal
from database.models import JobPipeline, JobStatus
from groq import Groq

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

load_dotenv()

# Initialize Groq client
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def get_gmail_service():
    """Builds and returns the Gmail API service using .env credentials."""
    creds = Credentials(
        token=None,
        refresh_token=os.getenv("GOOGLE_REFRESH_TOKEN"),
        client_id=os.getenv("GOOGLE_CLIENT_ID"),
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
        token_uri="https://oauth2.googleapis.com/token"
    )
    return build('gmail', 'v1', credentials=creds)

def fetch_emails_for_company(company_name: str) -> list[dict]:
    """
    Fetches emails from Gmail matching the company name.
    Useful for recruiters who don't message from the main domain, 
    but mention the company in the subject or body.
    """
    try:
        service = get_gmail_service()
        # Search for recent emails mentioning the company
        query = f'"{company_name}" newer_than:7d'
        
        results = service.users().messages().list(userId='me', q=query, maxResults=5).execute()
        messages = results.get('messages', [])
        
        parsed_emails = []
        for msg in messages:
            txt = service.users().messages().get(userId='me', id=msg['id'], format='full').execute()
            payload = txt['payload']
            headers = payload.get('headers', [])
            
            subject = "No Subject"
            for header in headers:
                if header['name'] == 'Subject':
                    subject = header['value']
                    break
                    
            body = "No Body"
            # Very simple body extraction
            try:
                parts = payload.get('parts', [])
                if not parts:
                    data = payload['body']['data']
                else:
                    data = parts[0]['body']['data']
                body = base64.urlsafe_b64decode(data).decode('utf-8')
            except Exception as e:
                pass
                
            parsed_emails.append({
                "subject": subject,
                "body": body[:500] # truncate for LLM window
            })
            
        return parsed_emails
    except Exception as e:
        print(f"[SECRETARY] Error fetching real emails: {e}")
        return []

def classify_email(email_subject: str, email_body: str) -> str:
    """
    Uses Groq LLM to classify an employer email into one of four categories:
    REJECTED, INTERVIEW, ASSESSMENT, or UNKNOWN
    """
    prompt = f"""
    You are an AI assistant helping a job seeker classify incoming emails from employers.
    Given the Subject and Body of the email, categorize it strictly into ONE of the following tags:
    - INTERVIEW: If they are asking for a phone screen, interview, or a chat.
    - ASSESSMENT: If they are assigning a coding test, HireVue, or take-home assignment.
    - REJECTED: If it's a standard rejection email.
    - UNKNOWN: If it's just an automated "we received your application" or standard newsletter, or none of the above.
    
    Email Subject: {email_subject}
    Email Body: {email_body}
    
    Respond ONLY with the exact tag word (INTERVIEW, ASSESSMENT, REJECTED, or UNKNOWN). Do not include any other text.
    """

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant", # Fast classification is perfect for 8B
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=10
        )
        classification = response.choices[0].message.content.strip().upper()
        
        # Validation step to ensure the string perfectly maps to the enum
        if classification in ["INTERVIEW", "ASSESSMENT", "REJECTED"]:
            return classification
        return "UNKNOWN"
    except Exception as e:
        print(f"[SECRETARY] LLM Error: {e}")
        return "UNKNOWN"

def run_secretary():
    """
    Main function to poll 'inbox', classify responses, and update the DB.
    """
    print("[SECRETARY] Waking up to check inbox...")
    db: Session = SessionLocal()
    
    try:
        # We only check emails for jobs we've already applied to
        applied_jobs = db.query(JobPipeline).filter(JobPipeline.status == JobStatus.APPLIED).all()
        
        if not applied_jobs:
            print("[SECRETARY] No 'APPLIED' jobs found. Going back to sleep.")
            return

        for job in applied_jobs:
            if not job.company:
                continue
                
            print(f"[SECRETARY] Scanning real inbox for matches: {job.company}")
            emails = fetch_emails_for_company(job.company)
            
            for email in emails:
                print(f"   -> Found email: '{email['subject']}'")
                decision = classify_email(email["subject"], email["body"])
                
                if decision != "UNKNOWN":
                    print(f"      [!] Classified as: {decision}. Updating tracker.")
                    
                    if decision == "REJECTED":
                        job.status = JobStatus.REJECTED
                    elif decision == "INTERVIEW":
                        job.status = JobStatus.INTERVIEW
                    elif decision == "ASSESSMENT":
                        job.status = JobStatus.ASSESSMENT
                        
                    db.commit()
                    # Only process the most meaningful email
                    break 
                else:
                    print("      [-] Ignored (Automated/No Action needed)")

    except Exception as e:
        print(f"[SECRETARY] Error during inbox check: {str(e)}")
        db.rollback()
    finally:
        db.close()
        print("[SECRETARY] Finished inbox sweep.")

if __name__ == "__main__":
    run_secretary()