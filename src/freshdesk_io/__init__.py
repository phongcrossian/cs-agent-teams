"""Freshdesk I/O module — only module permitted to call Freshdesk API."""

from src.freshdesk_io.client import FreshdeskClient

__all__ = ["FreshdeskClient"]
