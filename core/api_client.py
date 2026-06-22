import logging
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


logger = logging.getLogger(__name__)


class APIClient:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.session = self._build_session()
        logger.debug("API client initialized for base URL %s.", base_url)

    def _build_session(self) -> requests.Session:
        session = requests.Session()
        
        # Advanced Retry Config
        retry = Retry(
            total=4,            # Cap maximum combined attempts
            connect=3,          # Specifically allow up to 3 retries on connection timeouts
            read=3,             # Allow up to 3 retries on read timeouts
            backoff_factor=3,   # Wait times: 3s, 6s, 12s, 24s...
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["POST", "GET"],
            raise_on_status=False
        )
        
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "Content-Type": "application/json"
        })
        logger.debug("HTTP session configured with retry policy.")
        return session

    def set_bearer_token(self, token: str) -> None:
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        logger.debug("Bearer token attached to API session.")

    def post(self, endpoint: str, payload: dict | list) -> requests.Response:
        url = f"{self.base_url}{endpoint}"
        logger.info("POST %s", endpoint)
        response = self.session.post(url, json=payload, timeout=10)
        logger.info("POST %s completed with status %s.", endpoint, response.status_code)
        return response
