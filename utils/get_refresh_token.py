import os
import google.oauth2.credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# The scope for minimal read access to Gmail
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def get_refresh_token():
    print("WARNING: This script requires GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET to be in your .env or system environment.")
    
    # Needs to be a JSON file or use env vars wrapped into dict
    client_config = {
        "installed": {
            "client_id": os.environ.get("GOOGLE_CLIENT_ID", ""),
            "client_secret": os.environ.get("GOOGLE_CLIENT_SECRET", ""),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }
    
    try:
        flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
        creds = flow.run_local_server(port=0)
        print("\n\n=== SUCCESS ===")
        print(f"Refresh Token: {creds.refresh_token}")
        print("Add this to your .env file as GOOGLE_REFRESH_TOKEN.\n\n")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    from dotenv import load_dotenv
    load_dotenv()
    get_refresh_token()