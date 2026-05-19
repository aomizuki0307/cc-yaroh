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

def _mask(s: str) -> str:
    return f"{s[:6]}...{s[-4:]}" if len(s) > 10 else "***"

print(f"\nNew tokens obtained for @cc_yaroh (masked — copy from your terminal's scroll buffer):")
print(f"  X_OAUTH_ACCESS_TOKEN      prefix={_mask(at)}")
print(f"  X_OAUTH_ACCESS_TOKEN_SECRET prefix={_mask(ats)}")
print()
print("Run the following to update GitHub Secrets (values are in your terminal scroll buffer above):")
print("  gh secret set X_OAUTH_ACCESS_TOKEN")
print("  gh secret set X_OAUTH_ACCESS_TOKEN_SECRET")
print()
print("Full values (store securely, do not share):")
print(f"  AT : {at}")
print(f"  ATS: {ats}")
