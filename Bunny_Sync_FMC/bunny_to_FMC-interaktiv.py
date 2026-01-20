#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Synk BunnyCDN edge IPs til en FMC Dynamic Object (External Attributes > Dynamic Object)
- Henter IPv4 (og valgfrit IPv6) fra Bunny
- Opretter Dynamic Object ved behov (objectType=IP)
- Diff'er og laver add/remove via /object/dynamicobjectmappings
- Ingen deploy nødvendig (dynamic objects opdateres on-the-fly)
"""

import sys
import json
import ipaddress
import logging
from typing import List, Set, Iterable
import requests
from xml.etree import ElementTree as ET
from wingpy import CiscoFMC  # WingPy FMC-klient

# ---------- logging ----------
logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")
log = logging.getLogger("bunny2fmc_dynamic")

# ---------- PROMPTS ----------
FMC_BASE_URL = input("Indtast FMC Base URL (fx https://192.168.3.122): ").strip()
FMC_USERNAME = input("Indtast FMC Username: ").strip()
FMC_PASSWORD = input("Indtast FMC Password: ").strip()
FMC_DYNAMIC_NAME = input("Indtast Dynamic Object Name (fx BunnyCDN_Dynamic): ").strip()

BUNNY_IPV4_URL = input("Indtast BunnyCDN IPv4 URL (default: https://bunnycdn.com/api/system/edgeserverlist): ").strip() or "https://bunnycdn.com/api/system/edgeserverlist"
BUNNY_IPV6_URL = input("Indtast BunnyCDN IPv6 URL (default: https://bunnycdn.com/api/system/edgeserverlist/ipv6): ").strip() or "https://bunnycdn.com/api/system/edgeserverlist/ipv6"

# Hardcoded defaults
INCLUDE_IPV6 = False
VERIFY_SSL = False
DRY_RUN = False
CHUNK_SIZE = 500

# ---------- DEBUG ----------
print("\nDEBUG KONFIGURATION:")
print(f"FMC_BASE_URL = {FMC_BASE_URL}")
print(f"FMC_USERNAME = {FMC_USERNAME}")
print(f"FMC_DYNAMIC_NAME = {FMC_DYNAMIC_NAME}")
print(f"BUNNY_IPV4_URL = {BUNNY_IPV4_URL}")
print(f"BUNNY_IPV6_URL = {BUNNY_IPV6_URL}")
print(f"INCLUDE_IPV6 = {INCLUDE_IPV6}, VERIFY_SSL = {VERIFY_SSL}, DRY_RUN = {DRY_RUN}, CHUNK_SIZE = {CHUNK_SIZE}\n")

# ---------- Bunny fetch ----------
def _parse_possible_formats(body: str) -> List[str]:
    """Bunny returnerer i dag XML ArrayOfstring; håndter også JSON og plaintext."""
    try:
        root = ET.fromstring(body)
        vals = [el.text.strip() for el in root.findall(".//{*}string") if el.text]
        if vals:
            return vals
    except ET.ParseError:
        pass
    try:
        data = json.loads(body)
        if isinstance(data, list):
            return [str(x).strip() for x in data if str(x).strip()]
    except json.JSONDecodeError:
        pass
    return [ln.strip() for ln in body.splitlines() if ln.strip()]

def fetch_bunny_ips(include_ipv6: bool) -> Set[str]:
    sess = requests.Session()
    ips: Set[str] = set()
    endpoints = [BUNNY_IPV4_URL] + ([BUNNY_IPV6_URL] if include_ipv6 else [])
    for url in endpoints:
        log.info("Henter %s", url)
        r = sess.get(url, timeout=60, verify=VERIFY_SSL, headers={"Accept": "application/xml, application/json, text/plain"})
        r.raise_for_status()
        for c in _parse_possible_formats(r.text):
            try:
                if "/" in c:
                    net = ipaddress.ip_network(c, strict=False)
                else:
                    ip = ipaddress.ip_address(c)
                    net = ipaddress.ip_network(f"{ip}/{32 if ip.version == 4 else 128}", strict=False)
                ips.add(str(net))
            except ValueError:
                log.warning("Ignorerer ugyldig Bunny-post: %r", c)
    if not ips:
        raise RuntimeError("Ingen IP’er hentet fra Bunny")
    return ips

# ---------- FMC helpers ----------
def get_all(fmc: CiscoFMC, path: str) -> List[dict]:
    items: List[dict] = []
    offset = 0
    limit = 1000
    while True:
        r = fmc.get(path + f"?offset={offset}&limit={limit}&expanded=false")
        r.raise_for_status()
        data = r.json() or {}
        batch = data.get("items", [])
        items.extend(batch)
        if len(batch) < limit:
            break
        offset += limit
    return items

def chunked(iterable: Iterable[str], size: int) -> Iterable[List[str]]:
    buf = []
    for x in iterable:
        buf.append(x)
        if len(buf) == size:
            yield buf
            buf = []
    if buf:
        yield buf

def find_or_create_dynamic_object(fmc: CiscoFMC, name: str, description: str = "") -> dict:
    list_path = "/api/fmc_config/v1/domain/{domainUUID}/object/dynamicobjects"
    items = get_all(fmc, list_path)
    obj = next((it for it in items if it.get("name") == name), None)
    if obj:
        return obj
    payload = {
        "type": "DynamicObject",
        "name": name,
        "objectType": "IP",
        "description": description or "Managed automatically from BunnyCDN edge server list.",
    }
    if DRY_RUN:
        log.info("[DRY_RUN] Ville oprette Dynamic Object '%s'.", name)
        return {"id": "DRYRUN-ID", "name": name, "type": "DynamicObject", "objectType": "IP"}
    create_path = "/api/fmc_config/v1/domain/{domainUUID}/object/dynamicobjects"
    r = fmc.post(create_path, data=payload)
    r.raise_for_status()
    return r.json()

def get_current_mappings(fmc: CiscoFMC, obj_id: str) -> Set[str]:
    path = "/api/fmc_config/v1/domain/{domainUUID}/object/dynamicobjects/{objectId}/mappings"
    r = fmc.get(path, path_params={"objectId": obj_id})
    r.raise_for_status()
    data = r.json() or {}
    if isinstance(data, dict):
        if "mappings" in data and isinstance(data["mappings"], list):
            return set(str(x).strip() for x in data["mappings"] if str(x).strip())
        if "items" in data and isinstance(data["items"], list):
            out = set()
            for it in data["items"]:
                if isinstance(it, str):
                    out.add(it.strip())
                elif isinstance(it, dict) and "value" in it:
                    out.add(str(it["value"]).strip())
            return out
    if isinstance(data, list):
        return set(str(x).strip() for x in data if str(x).strip())
    return set()

def post_mappings_update(fmc: CiscoFMC, add: List[str], remove: List[str], obj_id: str):
    if DRY_RUN:
        log.info("[DRY_RUN] Ville ADD %d og REMOVE %d mappings.", len(add), len(remove))
        return
    endpoint = "/api/fmc_config/v1/domain/{domainUUID}/object/dynamicobjectmappings"
    for batch in chunked(add, CHUNK_SIZE):
        payload = {"add": [{"mappings": batch, "dynamicObject": {"id": obj_id}}]}
        r = fmc.post(endpoint, data=payload)
        r.raise_for_status()
        log.info("Tilføjede %d mappings.", len(batch))
    for batch in chunked(remove, CHUNK_SIZE):
        payload = {"remove": [{"mappings": batch, "dynamicObject": {"id": obj_id}}]}
        r = fmc.post(endpoint, data=payload)
        r.raise_for_status()
        log.info("Fjernede %d mappings.", len(batch))

def main():
    bunny_nets = fetch_bunny_ips(INCLUDE_IPV6)
    log.info("Bunny: %d netværk", len(bunny_nets))
    fmc = CiscoFMC(base_url=FMC_BASE_URL, username=FMC_USERNAME, password=FMC_PASSWORD, verify=VERIFY_SSL)
    desc = "Dynamic Object auto-managed from BunnyCDN edge server list."
    dyn = find_or_create_dynamic_object(fmc, FMC_DYNAMIC_NAME, description=desc)
    dyn_id = dyn["id"]
    log.info("Dynamic Object: %s (id=%s)", FMC_DYNAMIC_NAME, dyn_id)
    current = get_current_mappings(fmc, dyn_id)
    desired = bunny_nets
    to_add = sorted(desired - current)
    to_remove = sorted(current - desired)
    log.info("Current: %d, Desired: %d, +Add: %d, -Remove: %d", len(current), len(desired), len(to_add), len(to_remove))
    if not to_add and not to_remove:
        log.info("Ingen ændring nødvendig.")
        return
    post_mappings_update(fmc, to_add, to_remove, dyn_id)
    log.info("Færdig.")

if __name__ == "__main__":
    main()