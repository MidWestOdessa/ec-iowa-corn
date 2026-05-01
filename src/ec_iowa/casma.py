"""Crop-CASMA client: NASA SMAP weekly soil moisture via CSISS @ GMU.

Two-tap flow per (county, week, depth): WPS endpoint triggers server-side
computation, then the cached CSV becomes available. See handoff §3.5.

Implementation pending.
"""
from __future__ import annotations
