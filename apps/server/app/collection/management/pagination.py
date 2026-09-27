"""
Pagination Handler.
Supports page number, offset/limit, cursor, and next_url pagination strategies.
"""

from typing import Dict, Any, Optional, List
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse


class PaginationHandler:
    """
    Computes subsequent pagination query parameters or target URLs based on source config.
    """

    @staticmethod
    def get_next_request_params(
        strategy: str,
        current_page: int,
        page_size: int,
        cursor: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Generates query parameters for the next page based on strategy.
        """
        cfg = config or {}
        strat = strategy.lower().strip()

        if strat == "page_number" or strat == "page":
            page_param = cfg.get("page_param", "page")
            size_param = cfg.get("size_param", "per_page")
            return {
                page_param: current_page + 1,
                size_param: page_size,
            }

        elif strat == "offset_limit" or strat == "offset":
            offset_param = cfg.get("offset_param", "offset")
            limit_param = cfg.get("limit_param", "limit")
            return {
                offset_param: current_page * page_size,
                limit_param: page_size,
            }

        elif strat == "cursor":
            cursor_param = cfg.get("cursor_param", "cursor")
            return {
                cursor_param: cursor or "",
                cfg.get("limit_param", "limit"): page_size,
            }

        return {}

    @staticmethod
    def extract_next_url(
        response_json: Any,
        headers: Optional[Dict[str, str]] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        Attempts to extract next page URL from JSON payload or Link header.
        """
        cfg = config or {}
        next_key = cfg.get("next_url_key", "next")

        # 1. From JSON body
        if isinstance(response_json, dict):
            # Check direct key (e.g. "next", "next_page", "next_url")
            for k in [next_key, "next_page", "next_url"]:
                if k in response_json and isinstance(response_json[k], str):
                    return response_json[k]
            # Check nested links e.g. links.next
            if "links" in response_json and isinstance(response_json["links"], dict):
                if "next" in response_json["links"] and isinstance(response_json["links"]["next"], str):
                    return response_json["links"]["next"]
            if "pagination" in response_json and isinstance(response_json["pagination"], dict):
                if "next_url" in response_json["pagination"]:
                    return response_json["pagination"]["next_url"]

        # 2. From Link header
        if headers:
            link_header = headers.get("link") or headers.get("Link")
            if link_header and 'rel="next"' in link_header:
                for part in link_header.split(","):
                    if 'rel="next"' in part:
                        url_segment = part.split(";")[0].strip()
                        if url_segment.startswith("<") and url_segment.endswith(">"):
                            return url_segment[1:-1]

        return None
