import logging
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

class APIClient:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.session = self._build_session()

    def _build_session(self) -> requests.Session:
        session = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["POST", "GET"]
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "Content-Type": "application/json"
        })
        return session

    def set_bearer_token(self, token: str) -> None:
        self.session.headers.update({"Authorization": f"Bearer {token}"})

    def post(self, endpoint: str, payload: dict | list) -> requests.Response:
        url = f"{self.base_url}{endpoint}"
        return self.session.post(url, json=payload, timeout=10)