import json
import traceback
import requests

URL = "http://localhost:8000/health"


def main():
    try:
        resp = requests.get(URL, timeout=5)
        print("status_code=", resp.status_code)
        try:
            body = resp.json()
        except Exception:
            body = resp.text
        print("body=", json.dumps(body, ensure_ascii=False, indent=2) if not isinstance(body, str) else body)
    except Exception:
        print("ERROR during HTTP call:")
        traceback.print_exc()


if __name__ == "__main__":
    main()
