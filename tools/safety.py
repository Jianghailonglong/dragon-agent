from __future__ import annotations

import ipaddress
import re
from pathlib import Path
from urllib.parse import urlparse


class ToolSafetyGuard:
    """
    Safety checks for tool execution:
    - Workspace boundary: file ops must stay within workspace
    - URL safety: web_fetch cannot access internal/private IPs (SSRF)
    - Repeated lookup: prevent infinite loops from repeated external queries
    """

    def __init__(self, workspace: str = ".", max_repeated_lookups: int = 5) -> None:
        self._workspace = Path(workspace).resolve()
        self._max_repeated = max_repeated_lookups
        self._lookup_counts: dict[str, int] = {}

    def check_workspace_boundary(self, tool_name: str, path: str) -> str | None:
        """
        Check if a file path is within the workspace.
        Returns error message if violated, None if safe.
        """
        if tool_name not in ("read_file", "write_file", "edit_file"):
            return None

        p = Path(path).resolve()
        if not str(p).startswith(str(self._workspace)):
            return f"Error: path '{path}' is outside workspace boundary."
        return None

    def check_url_safety(self, url: str) -> str | None:
        """
        Check if a URL is safe to fetch (no SSRF).
        Returns error message if violated, None if safe.
        """
        try:
            parsed = urlparse(url)
        except Exception:
            return "Error: invalid URL."

        hostname = parsed.hostname or ""

        # Block localhost
        if hostname in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
            return "Error: fetching from localhost is not allowed."

        # Block private/reserved IP ranges
        try:
            ip = ipaddress.ip_address(hostname)
            if ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_link_local:
                return f"Error: fetching from private/reserved IP '{hostname}' is not allowed."
        except ValueError:
            # hostname is a domain name, not an IP — check common internal patterns
            if hostname.endswith((".local", ".internal", ".corp", ".lan")):
                return f"Error: fetching from internal domain '{hostname}' is not allowed."

        # Block common metadata endpoints (cloud SSRF)
        if "169.254.169.254" in url or "metadata.google" in url:
            return "Error: fetching from cloud metadata endpoint is not allowed."

        return None

    def check_repeated_lookup(self, tool_name: str, args: dict) -> str | None:
        """
        Check if the same external query has been made too many times.
        Returns error message if violated, None if safe.
        """
        if tool_name not in ("web_search", "web_fetch", "exec"):
            return None

        # Build a key from the relevant args
        key_parts = [tool_name]
        if tool_name == "web_search":
            key_parts.append(args.get("query", ""))
        elif tool_name == "web_fetch":
            key_parts.append(args.get("url", ""))
        elif tool_name == "exec":
            key_parts.append(args.get("command", ""))

        key = "|".join(key_parts)
        self._lookup_counts[key] = self._lookup_counts.get(key, 0) + 1

        if self._lookup_counts[key] > self._max_repeated:
            return f"Error: repeated lookup detected ({self._lookup_counts[key]} times). Possible infinite loop."
        return None

    def reset_counts(self) -> None:
        """Reset all lookup counters."""
        self._lookup_counts.clear()

    def check_all(self, tool_name: str, args: dict) -> str | None:
        """Run all safety checks. Returns first error or None."""
        # Workspace boundary
        if "path" in args:
            err = self.check_workspace_boundary(tool_name, args["path"])
            if err:
                return err

        # URL safety
        if "url" in args:
            err = self.check_url_safety(args["url"])
            if err:
                return err

        # Repeated lookup
        err = self.check_repeated_lookup(tool_name, args)
        if err:
            return err

        return None
