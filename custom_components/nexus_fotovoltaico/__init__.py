"""Integrazione Nexus Fotovoltaico: il sinottico animato di pannelli, casa e rete.

Non parla con l'inverter: collega entita' che Home Assistant ha gia'
(produzione, consumo, scambio con la rete, batteria...), ne ricava verso della
rete, verso della batteria e autoconsumo, e pubblica la mappa che la card usa
per disegnare e animare l'impianto.

La card la serve e la registra l'integrazione: nessuna risorsa da aggiungere a
mano, e l'URL porta la versione, cosi' dopo un aggiornamento il browser ricarica
il file invece di usare quello in cache.
"""

from __future__ import annotations

import logging
import os

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.loader import async_get_integration

from .const import CARD_FILE, CARD_URL_BASE, DOMAIN, PLATFORMS
from .impianto import Impianto

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Configura un impianto fotovoltaico."""
    await _async_registra_card(hass)

    impianto = Impianto(hass, entry)
    await impianto.async_start()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = impianto

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_ricarica))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    scaricato = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if scaricato:
        impianto: Impianto = hass.data[DOMAIN].pop(entry.entry_id)
        await impianto.async_stop()
    return scaricato


async def _async_ricarica(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


# -----------------------------------------------------------------------------
# Card Lovelace
# -----------------------------------------------------------------------------
async def _async_registra_card(hass: HomeAssistant) -> None:
    """Serve la card e la registra come risorsa, una volta sola per avvio."""
    dominio = hass.data.setdefault(DOMAIN, {})
    if dominio.get("card_registrata"):
        return

    www = os.path.join(os.path.dirname(__file__), "www")
    if not await hass.async_add_executor_job(os.path.isdir, www):
        _LOGGER.warning("Cartella www assente: la card non verra' servita")
        return

    try:
        await hass.http.async_register_static_paths([StaticPathConfig(CARD_URL_BASE, www, False)])
    except RuntimeError as err:
        _LOGGER.debug("Percorso statico gia' registrato: %s", err)

    integrazione = await async_get_integration(hass, DOMAIN)
    url = f"{CARD_URL_BASE}/{CARD_FILE}?v={integrazione.version}"

    if hass.is_running:
        await _async_registra_risorsa(hass, url)
    else:
        async def _dopo_avvio(_event) -> None:
            await _async_registra_risorsa(hass, url)

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _dopo_avvio)

    dominio["card_registrata"] = True


async def _async_registra_risorsa(hass: HomeAssistant, url: str) -> None:
    """Registra la card come risorsa Lovelace.

    E' l'unico meccanismo che Lovelace attende prima di disegnare: con il solo
    add_extra_js_url la plancia puo' disegnare prima che la card sia definita e
    mostrare «Custom element doesn't exist». Il ripiego resta per chi ha Lovelace
    in modalita' YAML, dove le risorse non si scrivono da codice.
    """
    lovelace = hass.data.get("lovelace")
    risorse = getattr(lovelace, "resources", None)
    if risorse is None and isinstance(lovelace, dict):
        risorse = lovelace.get("resources")
    if risorse is None:
        add_extra_js_url(hass, url)
        return

    try:
        await risorse.async_get_info()
        esistente = next((r for r in risorse.async_items() if CARD_FILE in r.get("url", "")), None)
        if esistente is None:
            await risorse.async_create_item({"res_type": "module", "url": url})
            _LOGGER.info("Risorsa Lovelace della card creata: %s", url)
        elif esistente.get("url") != url:
            await risorse.async_update_item(esistente["id"], {"url": url})
            _LOGGER.info("Risorsa Lovelace della card aggiornata: %s", url)
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning(
            "Impossibile registrare la risorsa Lovelace (%s). Aggiungila a mano come modulo JavaScript: %s",
            err,
            url,
        )
        add_extra_js_url(hass, url)
