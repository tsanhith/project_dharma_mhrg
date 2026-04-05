# Email Bridge Setup Instructions

To enable the Real Email & Calendar Bridge, you need to set up Google Cloud OAuth credentials and obtain a Refresh Token for the Gmail API.

## Step 1: Create a Google Cloud Project
1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Click **Select a project** > **New Project**. Name it `Dharma-Secretary`.
3. Give it a few seconds to create, then select it.

## Step 2: Enable the Gmail API
1. In the sidebar, go to **APIs & Services** > **Library**.
2. Search for "Gmail API" and click it.
3. Click **Enable**.

## Step 3: Configure OAuth Consent Screen
1. Go to **APIs & Services** > **OAuth consent screen**.
2. Select **External** (if you don't have a Google Workspace) and click Create.
3. Fill in the required fields (App name: Dharma, User support email, Developer contact email).
4. Go to **Scopes** and add `https://www.googleapis.com/auth/gmail.readonly`.
5. Go to **Test users** and add your own email address. (Important so you can test without publishing).

## Step 4: Create Credentials
1. Go to **APIs & Services** > **Credentials**.
2. Click **Create Credentials** > **OAuth client ID**.
3. Select **Desktop app** (or Web application if you plan to host this). Name it "Dharma Secretary".
4. Once created, you will get a **Client ID** and **Client Secret**. Add these to your `.env` file!

## Step 5: Get a Refresh Token
Run the `utils/get_refresh_token.py` script provided in this directory. 
It will open a browser window asking you to log in and grant permissions. Focus on the console output: it will spit out a **Refresh Token**. Add this to your `.env`.

Now, the Secretary Agent will read from your live inbox instead of the mock dictionary!