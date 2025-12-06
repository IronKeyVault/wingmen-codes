#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Synk BunnyCDN edge IPs til en FMC Dynamic Object (External Attributes > Dynamic Object)
- Henter IPv4 (og valgfrit IPv6) fra Bunny
- Opretter Dynamic Object ved behov (objectType=IP)
- Diff'er og laver add/remove via /object/dynamicobjectmappings
- Ingen deploy nødvendig (dynamic objects opdateres on-the-fly)

Miljøvariabler:
  WINGPY_FMC_BASE_URL   e.g. https://fmc.example.com
  WINGPY_FMC_USERNAME
  WINGPY_FMC_PASSWORD

  FMC_DYNAMIC_NAME      e.g. BunnyCDN_Dynamic
  INCLUDE_IPV6          (optional "true"/"false", default: false)
  VERIFY_SSL            (optional "true"/"false", default: true)
  DRY_RUN               (optional "true"/"false", default: false)
  CHUNK_SIZE            (optional int, default: 500)  # hvor mange IPs pr. batch ved add/remove
"""

import os
import sys
import json
import ipaddress
import logging
from typing import List, Set, Iterable
import requests
from xml.etree import ElementTree as ET

from wingpy import CiscoFMC  # WingPy FMC-klient

#loader .env fil
from dotenv import load_dotenv
load_dotenv()  # Indlæser .env filen

# DEBUG: Print for at se om .env bliver indlæst
print(f"DEBUG: FMC_BASE_URL = {os.getenv('WINGPY_FMC_BASE_URL')}")
print(f"DEBUG: FMC_USERNAME = {os.getenv('WINGPY_FMC_USERNAME')}")
print(f"DEBUG: FMC_GROUP_NAME = {os.getenv('FMC_GROUP_NAME')}")
print(f"DEBUG: Current working directory = {os.getcwd()}")

BUNNY_IPV4_URL = "https://bunnycdn.com/api/system/edgeserverlist"
BUNNY_IPV6_URL = "https://bunnycdn.com/api/system/edgeserverlist/ipv6"

# ---------- logging ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
)
log = logging.getLogger("bunny2fmc_dynamic")

def env_bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "y")

VERIFY_SSL = env_bool("VERIFY_SSL", True)
INCLUDE_IPV6 = env_bool("INCLUDE_IPV6", False)
DRY_RUN = env_bool("DRY_RUN", False)
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "500"))

FMC_BASE_URL = os.getenv("WINGPY_FMC_BASE_URL")
FMC_USERNAME = os.getenv("WINGPY_FMC_USERNAME")
FMC_PASSWORD = os.getenv("WINGPY_FMC_PASSWORD")
FMC_DYNAMIC_NAME = os.getenv("FMC_DYNAMIC_NAME")

if not all([FMC_BASE_URL, FMC_USERNAME, FMC_PASSWORD, FMC_DYNAMIC_NAME]):
    log.error("Manglende miljøvariabler: WINGPY_FMC_BASE_URL, WINGPY_FMC_USERNAME, WINGPY_FMC_PASSWORD, FMC_DYNAMIC_NAME")
    sys.exit(2)

# ---------- Bunny fetch ----------
def _parse_possible_formats(body: str) -> List[str]:
    """Bunny returnerer i dag XML ArrayOfstring; håndter også JSON og plaintext."""
    # XML
    try:
        root = ET.fromstring(body)
        vals = [el.text.strip() for el in root.findall(".//{*}string") if el.text]
        if vals:
            return vals
    except ET.ParseError:
        pass
    # JSON
    try:
        data = json.loads(body)
        if isinstance(data, list):
            return [str(x).strip() for x in data if str(x).strip()]
    except json.JSONDecodeError:
        pass
    # Plaintext fallback
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

# ---------- FMC helpers via WingPy ----------
def get_all(fmc: CiscoFMC, path: str) -> List[dict]:
    """Pagineret GET for listeendpoints (offset/limit)."""
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
    # GET all dynamic objects, filter by name
    list_path = "/api/fmc_config/v1/domain/{domainUUID}/object/dynamicobjects"
    items = get_all(fmc, list_path)
    obj = next((it for it in items if it.get("name") == name), None)
    if obj:
        return obj

    # Create with objectType IP
    payload = {
        "type": "DynamicObject",
        "name": name,
        "objectType": "IP",  # vigtigt: Dynamic Object for IP-mappings
        "description": description or "Managed automatically from BunnyCDN edge server list.",
    }
    if DRY_RUN:
        log.info("[DRY_RUN] Ville oprette Dynamic Object '%s'.", name)
        # returner en “fake” dict så resten kan simuleres
        return {"id": "DRYRUN-ID", "name": name, "type": "DynamicObject", "objectType": "IP"}

    create_path = "/api/fmc_config/v1/domain/{domainUUID}/object/dynamicobjects"
    r = fmc.post(create_path, data=payload)
    r.raise_for_status()
    return r.json()

def get_current_mappings(fmc: CiscoFMC, obj_id: str) -> Set[str]:
    """
    GET /object/dynamicobjects/{objectId}/mappings
    Returnerer typisk en liste over nuværende IP/CIDR strings.
    """
    path = "/api/fmc_config/v1/domain/{domainUUID}/object/dynamicobjects/{objectId}/mappings"
    r = fmc.get(path, path_params={"objectId": obj_id})
    r.raise_for_status()
    data = r.json() or {}

    # API’er/udgaver kan returnere {"mappings":[ "1.2.3.4", "10.0.0.0/24", ... ]}
    # eller {"items":[ ... ]}; håndter begge.
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

    # Fallback: prøv at tolke hele body som liste
    if isinstance(data, list):
        return set(str(x).strip() for x in data if str(x).strip())
    return set()

def post_mappings_update(fmc: CiscoFMC, add: List[str], remove: List[str], obj_id: str):
    """
    POST /object/dynamicobjectmappings med "add"/"remove" strukturer.
    Payload-format dokumenteret i Cisco Live materialer. :contentReference[oaicite:1]{index=1}
    """
    if DRY_RUN:
        log.info("[DRY_RUN] Ville ADD %d og REMOVE %d mappings.", len(add), len(remove))
        return

    endpoint = "/api/fmc_config/v1/domain/{domainUUID}/object/dynamicobjectmappings"

    # Send i batches, så store lister ikke bliver for tunge
    for batch in chunked(add, CHUNK_SIZE):
        payload = {
            "add": [{
                "mappings": batch,
                "dynamicObject": {"id": obj_id}
            }]
        }
        r = fmc.post(endpoint, data=payload)
        r.raise_for_status()
        log.info("Tilføjede %d mappings.", len(batch))

    for batch in chunked(remove, CHUNK_SIZE):
        payload = {
            "remove": [{
                "mappings": batch,
                "dynamicObject": {"id": obj_id}
            }]
        }
        r = fmc.post(endpoint, data=payload)
        r.raise_for_status()
        log.info("Fjernede %d mappings.", len(batch))

def main():
    # 1) Hent Bunny IP'er
    bunny_nets = fetch_bunny_ips(INCLUDE_IPV6)
    log.info("Bunny: %d netværk", len(bunny_nets))

    # 2) Forbind til FMC (WingPy håndterer token/domainUUID)
    fmc = CiscoFMC(
        base_url=FMC_BASE_URL,
        username=FMC_USERNAME,
        password=FMC_PASSWORD,
        verify=VERIFY_SSL,
    )

    # 3) Find/opret Dynamic Object
    desc = "Dynamic Object auto-managed from BunnyCDN edge server list."
    dyn = find_or_create_dynamic_object(fmc, FMC_DYNAMIC_NAME, description=desc)
    dyn_id = dyn["id"]
    log.info("Dynamic Object: %s (id=%s)", FMC_DYNAMIC_NAME, dyn_id)

    # 4) Hent nuværende mappings og diff
    current = get_current_mappings(fmc, dyn_id)
    desired = bunny_nets

    to_add = sorted(desired - current)
    to_remove = sorted(current - desired)

    log.info("Current: %d, Desired: %d, +Add: %d, -Remove: %d",
             len(current), len(desired), len(to_add), len(to_remove))

    if not to_add and not to_remove:
        log.info("Ingen ændring nødvendig.")
        return

    # 5) Udfør opdateringer (ingen deploy nødvendig)
    post_mappings_update(fmc, to_add, to_remove, dyn_id)
    log.info("Færdig.")

if __name__ == "__main__":
    main()
