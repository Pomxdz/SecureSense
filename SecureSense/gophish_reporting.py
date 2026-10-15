"""Report only to the configured Gophish phishing server, never an email URL."""
import os
from urllib.parse import urlsplit
import httpx


def report_to_gophish(rid):
    base = os.getenv('GOPHISH_PHISHING_URL', 'http://127.0.0.1/').rstrip('/')
    parsed = urlsplit(base)
    if (parsed.scheme not in ('http', 'https') or not parsed.netloc
            or parsed.username or parsed.password or parsed.query or parsed.fragment):
        raise ValueError('Invalid GOPHISH_PHISHING_URL configuration')
    # /report returns 204. Do not follow a redirect into a landing page (a click).
    with httpx.Client(timeout=10, follow_redirects=False, trust_env=False) as client:
        response = client.get(base + '/report', params={'rid': rid})
        if response.status_code != 204:
            raise ValueError('Gophish did not accept this report')
