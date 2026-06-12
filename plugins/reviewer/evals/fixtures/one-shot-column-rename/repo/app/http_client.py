"""Shared outbound HTTP client — timeout set once at construction."""

import httpx

client = httpx.Client(base_url="https://partner.example.com", timeout=10.0)
