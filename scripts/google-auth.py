#!/usr/bin/env python3
"""One-time Google Calendar authorization — RUN ON A MACHINE WITH A BROWSER
(your laptop), NOT the headless Pi.

1. Put your OAuth client JSON (Desktop app, from Google Cloud console) at
   config/google/client_secret.json
2. Run:  python scripts/google-auth.py
   → a browser opens; approve read-only Calendar access.
3. It writes config/google/token.json. Then:  ./scripts/deploy-to-pi.sh …
   copies config/google/ to the Pi. Restart peekabot-core and it syncs.
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
GDIR = ROOT / "config" / "google"
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


def main() -> None:
    GDIR.mkdir(parents=True, exist_ok=True)
    cs = GDIR / "client_secret.json"
    if not cs.exists():
        sys.exit(
            f"Missing {cs}\n"
            "Download your OAuth client (Desktop app) JSON from Google Cloud "
            "console and save it there, then re-run."
        )
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        sys.exit("pip install google-auth-oauthlib google-api-python-client google-auth")

    flow = InstalledAppFlow.from_client_secrets_file(str(cs), SCOPES)
    creds = flow.run_local_server(port=0)          # opens the browser
    (GDIR / "token.json").write_text(creds.to_json())
    print(f"\n✓ wrote {GDIR / 'token.json'}")
    print("Now: enable calendar in the dashboard, run ./scripts/deploy-to-pi.sh, "
          "and `sudo systemctl restart peekabot-core` on the Pi.")


if __name__ == "__main__":
    main()
