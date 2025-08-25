from __future__ import annotations

import time
from typing import Iterable, List, Dict, Any, Optional

import requests

from .errors import raise_for_status


class ConfluenceClient:
    def __init__(self, base_url: str, pat: str, timeout: int = 15, retries: int = 3,
                 backoff: float = 0.5, verbose: bool = False):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.retries = retries
        self.backoff = backoff
        self.verbose = verbose
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {pat}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        })

    # ---------------- internal ----------------
    def _request(self, method: str, path: str, *, expected: Iterable[int] | None = None,
                 params: dict | None = None, json: dict | list | None = None) -> dict:
        url = f"{self.base_url}{path}" if path.startswith('/') else f"{self.base_url}/{path}"
        expected = set(expected or {200, 201})
        attempt = 0
        while True:
            attempt += 1
            try:
                resp = self.session.request(method, url, timeout=self.timeout, params=params, json=json)
            except requests.RequestException as e:
                if attempt <= self.retries:
                    time.sleep(self.backoff * (2 ** (attempt - 1)))
                    continue
                raise e

            if resp.status_code in expected:
                try:
                    return resp.json()
                except Exception:
                    return {"raw": resp.text, "status": resp.status_code}

            if resp.status_code in (429, 500, 502, 503, 504) and attempt <= self.retries:
                retry_after = resp.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else self.backoff * (2 ** (attempt - 1))
                if self.verbose:
                    print(f"retrying {method} {url} in {delay}s (status {resp.status_code})")
                time.sleep(delay)
                continue

            payload = {}
            try:
                payload = resp.json()
            except Exception:
                pass
            raise_for_status(resp.status_code, message=f"{method} {url}", payload=payload)

    def page_link(self, page_json: dict) -> str | None:
        """
        Build a direct link to the page from Confluence response.
        Works with Cloud and Server/DC APIs. Falls back to constructing from base_url + id.
        """
        if not page_json:
            return None

        links = page_json.get("_links", {}) or {}
        base_url = self.base_url.rstrip("/")

        # 1. Try base+webui (typical in responses)
        webui = links.get("webui")
        base = links.get("base")
        if webui:
            if base:
                return f"{base}{webui}"
            if webui.startswith("/"):
                return f"{base_url}{webui}"
            return f"{base_url}/{webui}"

        # 2. Try tinyui (short link) if available
        tinyui = links.get("tinyui")
        if tinyui:
            if tinyui.startswith("/"):
                return f"{base_url}{tinyui}"
            return f"{base_url}/{tinyui}"

        # 3. Construct manually from id + space
        page_id = page_json.get("id")
        space_key = None
        space_obj = page_json.get("space")
        if isinstance(space_obj, dict):
            space_key = space_obj.get("key")

        if page_id:
            if base_url.endswith("/wiki"):  # Atlassian Cloud
                if space_key:
                    return f"{base_url}/spaces/{space_key}/pages/{page_id}"
                return f"{base_url}/pages/{page_id}"
            else:  # Server / DC
                return f"{base_url}/pages/{page_id}"

        return None

    # ---------------- space / homepage ----------------
    def get_space_homepage(self, space_key: str) -> Optional[str]:
        """
        Return the homepage page ID for the given space key, or None if not set.
        """
        res = self._request(
            "GET",
            f"/rest/api/space/{space_key}",
            params={"expand": "homepage"},
        )
        home = res.get("homepage")
        return str(home.get("id")) if home and home.get("id") else None

    # ---------------- create/update ----------------
    def create_page(self, *, title: str, space_key: str, body_html: str,
                    parent_id: str | None = None, notify_watchers: bool = True) -> dict:
        payload = {
            "type": "page",
            "title": title,
            "space": {"key": space_key},
            "body": {"storage": {"value": body_html, "representation": "storage"}},
        }
        if parent_id:
            payload["ancestors"] = [{"id": str(parent_id)}]

        return self._request(
            "POST",
            "/rest/api/content",
            params={"notifyWatchers": str(bool(notify_watchers)).lower()},
            json=payload,
        )

    def get_page(self, page_id: str) -> dict:
        return self._request(
            "GET",
            f"/rest/api/content/{page_id}",
            params={"expand": "version,ancestors,body.storage,_links"},
        )

    def get_page_rendered_html(self, page_id: str, *, export: bool = True) -> str:
        """
        Get rendered HTML for display:
          - export=True → body.export_view (cleaner, printable)
          - export=False → body.view (standard web view)
        Returns HTML string.
        """
        expand = "body.export_view" if export else "body.view"
        res = self._request(
            "GET",
            f"/rest/api/content/{page_id}",
            params={"expand": expand},
        )
        body = res.get("body", {})
        key = "export_view" if export else "view"
        html = (body.get(key) or {}).get("value", "")
        return html or ""

    def find_page_by_title(self, title: str, space_key: str, parent_id: str | None = None) -> dict | None:
        res = self._request(
            "GET",
            "/rest/api/content",
            params={
                "type": "page",
                "spaceKey": space_key,
                "title": title,
                "expand": "ancestors,version,_links",
                "status": "current",  # ensure not archived
                "limit": 25,
            },
        )
        results = res.get("results", [])
        if not results:
            return None
        if parent_id is None:
            return results[0]
        for r in results:
            for anc in r.get("ancestors", []):
                if str(anc.get("id")) == str(parent_id):
                    return r
        return None

    def update_page(
        self,
        *,
        page_id: str,
        body_html: str,
        title: Optional[str] = None,
        minor_edit: bool = True,
        notify_watchers: bool = True,
        _retry: bool = True,
    ) -> dict:
        """
        Update a page's storage body (and optionally its title).
        - Fetches current page to get type + current version.
        - Increments version and PUTs to /rest/api/content/{id}.
        - Retries once on version conflict (409).
        """
        # 1) Fetch current for type/title/version
        current = self.get_page(page_id)
        current_version = int((current.get("version") or {}).get("number", 0))
        new_version = current_version + 1

        payload: Dict[str, Any] = {
            "id": str(page_id),
            "type": current.get("type", "page"),
            "title": title or current.get("title"),
            "version": {
                "number": new_version,
                "minorEdit": bool(minor_edit),
            },
            "body": {
                "storage": {
                    "value": body_html,
                    "representation": "storage",
                }
            },
        }

        try:
            return self._request(
                "PUT",
                f"/rest/api/content/{page_id}",
                params={"notifyWatchers": str(bool(notify_watchers)).lower()},
                json=payload,
                expected={200},
            )
        except Exception as e:
            # If a concurrent edit happened, Confluence returns 409.
            msg = str(e)
            if _retry and "409" in msg:
                if self.verbose:
                    print("Version conflict (409). Refetching and retrying once...")
                current = self.get_page(page_id)
                current_version = int((current.get("version") or {}).get("number", 0))
                payload["version"]["number"] = current_version + 1
                return self._request(
                    "PUT",
                    f"/rest/api/content/{page_id}",
                    params={"notifyWatchers": str(bool(notify_watchers)).lower()},
                    json=payload,
                    expected={200},
                )
            raise

    # ---------------- browsing helpers ----------------
    def list_pages_in_space(self, *, space_key: str, limit: int = 25, start: int = 0,
                            title_contains: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Flat listing (not a tree). Prefer using get_space_homepage() + list_children()
        if you want the hierarchical tree rooted at the space homepage.
        """
        params = {
            "type": "page",
            "spaceKey": space_key,
            "limit": max(1, min(limit, 100)),
            "start": max(0, start),
            "expand": "_links",
            "status": "current",   # filter out archived
        }
        if title_contains:
            params["title"] = title_contains  # server-side exact; we also filter client-side

        res = self._request("GET", "/rest/api/content", params=params)
        items = res.get("results", [])
        if title_contains:
            items = [i for i in items if title_contains.lower() in i.get("title", "").lower()]
        return items

    def list_children(self, *, page_id: str, limit: int = 25, start: int = 0) -> List[Dict[str, Any]]:
        params = {
            "limit": max(1, min(limit, 100)),
            "start": max(0, start),
            "expand": "_links",
            "status": "current",   # only live children
        }
        res = self._request("GET", f"/rest/api/content/{page_id}/child/page", params=params)
        return res.get("results", [])

    def list_all_children(self, *, page_id: str) -> List[Dict[str, Any]]:
        """
        Fetch ALL direct children of a page (handles pagination).
        """
        out: List[Dict[str, Any]] = []
        start = 0
        while True:
            chunk = self.list_children(page_id=page_id, limit=100, start=start)
            if not chunk:
                break
            out.extend(chunk)
            if len(chunk) < 100:
                break
            start += 100
        return out

    def search_cql(self, *, cql: str, limit: int = 25, start: int = 0) -> List[Dict[str, Any]]:
        """
        Use CQL to search for content. We normalize results into 'content' objects (id, title, _links).
        """
        params = {
            "cql": cql,
            "limit": max(1, min(limit, 100)),
            "start": max(0, start),
            "expand": "content._links",
        }
        res = self._request("GET", "/rest/api/search", params=params)
        results = []
        for r in res.get("results", []):
            content = r.get("content") or {}
            if content.get("type") == "page":
                results.append(content)
        return results
