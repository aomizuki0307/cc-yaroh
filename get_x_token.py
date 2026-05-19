"""Interactive PIN-based OAuth 1.0a flow — get fresh access tokens for @cc_yaroh.

Run:
    python get_x_token.py

Then visit the printed URL as @cc_yaroh, click Authorize, copy the PIN.
"""
import os
from pathlib import Path
from dotenv import load_dotenv
from requests_oauthlib import OAuth1Session

load_dotenv(Path(__file__).parent / ".env.x-growth")

ck = os.environ["X_OAUTH_CONSUMER_KEY"]
cs = os.environ["X_OAUTH_CONSUMER_SECRET"]

print(f"App key: {ck[:4]}...{ck[-4:]}")

# 1. Get a request token with oob (PIN) callback
oauth = OAuth1Session(ck, client_secret=cs, callback_uri="oob")
resp = oauth.fetch_request_token("https://api.x.com/oauth/request_token")
rt = resp["oauth_token"]
rt_secret = resp["oauth_token_secret"]

# 2. Print authorization URL — user must open this as @cc_yaroh
auth_url = oauth.authorization_url("https://api.x.com/oauth/authorize")
print(f"\nOpen this URL in a browser, log in as @cc_yaroh, and click Authorize:")
print(f"\n  {auth_url}\n")

# 3. Exchange PIN for access token
verifier = input("Paste the PIN here: ").strip()
oauth = OAuth1Session(
    ck,
    client_secret=cs,
    resource_owner_key=rt,
    resource_owner_secret=rt_secret,
    verifier=verifier,
)
tokens = oauth.fetch_access_token("https://api.x.com/oauth/access_token")
at = tokens["oauth_token"]
ats = tokens["oauth_token_secret"]

print(f"\nNew tokens for @cc_yaroh:")
print(f"  X_OAUTH_ACCESS_TOKEN={at}")
print(f"  X_OAUTH_ACCESS_TOKEN_SECRET={ats}")
print("\nUpdate .env.x-growth and GitHub Secrets with these values, then re-run test_auth.py")
