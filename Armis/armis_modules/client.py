import time
from datetime import datetime, timedelta, timezone
from typing import Generator

import requests
from tenacity import retry, stop_after_attempt, wait_exponential


class ArmisApiClient:
    TOKEN_REFRESH_MARGIN_SECONDS = 180  # refresh 3 minutes before expiry

    def __init__(self, instance_url: str, secret_key: str) -> None:
        self._instance_url = instance_url.rstrip("/")
        self._secret_key = secret_key
        self._token: str | None = None
        self._token_expires_at: datetime | None = None
        self._session = requests.Session()

    def _get_token(self) -> None:
        response = self._session.post(
            f"{self._instance_url}/api/v1/access_token/",
            data={"secret_key": self._secret_key},
        )
        response.raise_for_status()
        data = response.json()
        self._token = data["data"]["access_token"]
        expiration_str = data["data"]["expiration_utc"]
        self._token_expires_at = datetime.fromisoformat(expiration_str.replace("Z", "+00:00"))

    def _ensure_token(self) -> None:
        now = datetime.now(timezone.utc)
        if (
            self._token is None
            or self._token_expires_at is None
            or self._token_expires_at - timedelta(seconds=self.TOKEN_REFRESH_MARGIN_SECONDS) <= now
        ):
            self._get_token()

    @property
    def _auth_headers(self) -> dict:
        return {"Authorization": f"ApiToken {self._token}"}

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.1, min=0.1, max=1),
        reraise=True,
    )
    def _get_with_retry(self, path: str, params: dict | None = None) -> requests.Response:
        self._ensure_token()
        response = self._session.get(
            f"{self._instance_url}{path}",
            headers=self._auth_headers,
            params=params,
        )
        if response.status_code == 401:
            self._token = None
            response.raise_for_status()
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 60))
            time.sleep(retry_after)
            response.raise_for_status()
        response.raise_for_status()
        return response

    def get_alerts(self, time_frame_minutes: int, page_size: int = 100) -> Generator[dict, None, None]:
        aql = f'timeFrame:"{time_frame_minutes} minutes"'
        fields = (
            "alertId,title,description,severity,status,time,type,"
            "classification,deviceIds,activityUUIDs,affectedDevicesCount"
        )
        offset = 0
        while True:
            response = self._get_with_retry(
                "/api/v1/alerts/",
                params={"aql": aql, "orderBy": "time", "fields": fields, "length": page_size, "from": offset},
            )
            data = response.json()
            items = data["data"]["data"]
            for item in items:
                yield item
            if not data["data"]["next"] or len(items) == 0:
                break
            offset += len(items)

    def get_devices(self, time_frame_hours: int, page_size: int = 100) -> Generator[dict, None, None]:
        aql = f'timeFrame:"{time_frame_hours} hours"'
        fields = (
            "id,name,ipAddress,macAddress,type,category,operatingSystem,"
            "operatingSystemVersion,manufacturer,model,firstSeen,lastSeen,"
            "riskLevel,boundaries,businessImpact,purduLevel"
        )
        offset = 0
        while True:
            response = self._get_with_retry(
                "/api/v1/devices/",
                params={"aql": aql, "fields": fields, "length": page_size, "from": offset},
            )
            data = response.json()
            items = data["data"]["data"]
            for item in items:
                yield item
            if not data["data"]["next"] or len(items) == 0:
                break
            offset += len(items)

    def get_vulnerabilities(self, last_detected_after: str, page_size: int = 100) -> Generator[dict, None, None]:
        aql = f'lastDetected:">{last_detected_after}"'
        offset = 0
        while True:
            response = self._get_with_retry(
                "/api/v1/vulnerabilities/",
                params={"aql": aql, "length": page_size, "from": offset},
            )
            data = response.json()
            items = data["data"]["data"]
            for item in items:
                yield item
            if not data["data"]["next"] or len(items) == 0:
                break
            offset += len(items)

    # ------------------------------------------------------------------
    # Write helper (PATCH / POST with auth + retry)
    # ------------------------------------------------------------------

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.1, min=0.1, max=1),
        reraise=True,
    )
    def _write_with_retry(self, method: str, path: str, json_body: dict | None = None) -> requests.Response:
        self._ensure_token()
        response = self._session.request(
            method,
            f"{self._instance_url}{path}",
            headers=self._auth_headers,
            json=json_body,
        )
        if response.status_code == 401:
            self._token = None
            response.raise_for_status()
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 60))
            time.sleep(retry_after)
            response.raise_for_status()
        response.raise_for_status()
        return response

    # ------------------------------------------------------------------
    # Single-item lookups
    # ------------------------------------------------------------------

    def get_device(self, device_id: int) -> dict:
        """Return the full device record for *device_id*."""
        response = self._get_with_retry(f"/api/v1/devices/{device_id}/")
        return response.json()["data"]

    def get_alert(self, alert_id: int) -> dict:
        """Return the full alert record for *alert_id*."""
        response = self._get_with_retry(f"/api/v1/alerts/{alert_id}/")
        return response.json()["data"]

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search_devices(self, aql_query: str, max_results: int = 100) -> list[dict]:
        """Return up to *max_results* devices matching the ASQ *aql_query*."""
        fields = (
            "id,name,ipAddress,macAddress,type,category,operatingSystem,"
            "manufacturer,model,firstSeen,lastSeen,riskLevel"
        )
        results: list[dict] = []
        offset = 0
        page_size = min(100, max_results)
        while len(results) < max_results:
            remaining = max_results - len(results)
            response = self._get_with_retry(
                "/api/v1/devices/",
                params={
                    "aql": aql_query,
                    "fields": fields,
                    "length": min(page_size, remaining),
                    "from": offset,
                },
            )
            data = response.json()
            items = data["data"]["data"]
            results.extend(items)
            if not data["data"]["next"] or len(items) == 0:
                break
            offset += len(items)
        return results[:max_results]

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def update_alert_status(self, alert_id: int, status: str) -> dict:
        """Set the *status* of *alert_id* (Resolved | Suppressed | Unhandled)."""
        response = self._write_with_retry("PATCH", f"/api/v1/alerts/{alert_id}/", json_body={"status": status})
        return response.json()["data"]

    def tag_device(self, device_id: int, tags: list[str]) -> dict:
        """Attach *tags* to *device_id*."""
        response = self._write_with_retry("POST", f"/api/v1/devices/{device_id}/tags/", json_body={"tags": tags})
        return response.json()
