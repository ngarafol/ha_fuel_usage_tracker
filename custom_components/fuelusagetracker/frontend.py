"""Serve and auto-register the bundled Fuel Usage Tracker Lovelace card.

``async_setup_frontend`` is called from ``async_setup_entry`` and is idempotent:
every vehicle is a config entry, but the card is served and loaded only once.
"""

from __future__ import annotations

import logging
from pathlib import Path
from uuid import uuid4

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.components.lovelace import LOVELACE_DATA
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

CARD_FILENAME = "fuelusagetracker-card.js"
#: URL the browser loads, also the URL path the file is served under.
CARD_URL = f"/{DOMAIN}/{CARD_FILENAME}"
CARD_FILE = Path(__file__).parent / "frontend" / CARD_FILENAME

#: hass.data flag guarding the one-time registration.
DATA_CARD_REGISTERED = f"{DOMAIN}_card_registered"


async def async_setup_frontend(hass: HomeAssistant) -> None:
    """Serve the card and load it as an extra frontend module.

    ``add_extra_js_url`` inserts the URL into
    ``hass.data[DATA_EXTRA_MODULE_URL]`` (a ``UrlManager`` built by the frontend
    component's ``async_setup``), which the index template renders as
    ``<script type="module" src=...>``. The frontend component is a declared
    dependency of this integration, so it is always available here.
    """
    if hass.http is None:
        _LOGGER.debug("HTTP not set up; not serving the %s card", DOMAIN)
        return
    if hass.data.get(DATA_CARD_REGISTERED):
        return

    # A path that is new on every Home Assistant start: browsers and service
    # workers cannot answer it from an old (or broken) cache entry, which is what
    # kept the previous card alive — or made the module fail to load entirely.
    boot = uuid4().hex[:8]
    boot_url = f"/{DOMAIN}/fuelusagetracker-card-{boot}.js"
    # Claim the slot before the first await so concurrent entries cannot both
    # register (that put two boot URLs in the index).
    hass.data[DATA_CARD_REGISTERED] = boot_url
    await hass.http.async_register_static_paths(
        [
            # Stable alias: user-added resources and old links keep working.
            StaticPathConfig(CARD_URL, str(CARD_FILE), False),
            StaticPathConfig(boot_url, str(CARD_FILE), False),
        ]
    )
    add_extra_js_url(hass, boot_url)
    await _async_register_resource(hass, boot_url)


async def _async_register_resource(hass: HomeAssistant, url: str) -> None:
    """Register the card as a Lovelace resource as well.

    Dashboards load their resources explicitly, so this still works when a
    companion app serves a cached frontend shell that lacks the extra-module tag
    (the app then reported "Custom element does not exist"). The resource is
    updated in place on a version bump instead of piling up new entries; YAML
    resource mode has no storage collection and is covered by the module URL.
    """
    resources = getattr(hass.data.get(LOVELACE_DATA), "resources", None)
    if resources is None or not hasattr(resources, "async_create_item"):
        _LOGGER.warning(
            "Lovelace is not in storage resource mode, so the %s card could not be "
            "added to the dashboard resources automatically. Add this URL under "
            "Settings -> Dashboards -> Resources (type: JavaScript module), or to "
            "lovelace.resources in configuration.yaml for YAML mode: %s",
            DOMAIN,
            url,
        )
        return
    try:
        if not getattr(resources, "loaded", True):
            await resources.async_load()
        prefix = f"/{DOMAIN}/fuelusagetracker-card"
        current = None
        stale = []
        for item in resources.async_items():
            base = str(item.get("url", "")).split("?")[0]
            if base == CARD_URL or base.startswith(prefix):
                if current is None:
                    current = item
                else:
                    stale.append(item["id"])
        for item_id in stale:
            await resources.async_delete_item(item_id)
            _LOGGER.info("Removed a stale %s dashboard resource", DOMAIN)
        if current is None:
            await resources.async_create_item({"res_type": "module", "url": url})
            _LOGGER.info("Registered the %s card as a dashboard resource: %s", DOMAIN, url)
        elif current.get("url") != url:
            await resources.async_update_item(current["id"], {"url": url})
            _LOGGER.info("Updated the %s dashboard resource to %s", DOMAIN, url)
        else:
            _LOGGER.debug("The %s dashboard resource is already current", DOMAIN)
    except Exception:  # noqa: BLE001 - a resource hiccup must not block setup
        _LOGGER.warning("Could not register the %s dashboard resource", DOMAIN, exc_info=True)
