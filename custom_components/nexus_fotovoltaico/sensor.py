"""Sensori: la mappa per la card, autoconsumo e versi di rete e batteria.

Un sensore calcolato nasce solo se ha da dove calcolare: senza scambio con la
rete niente «Verso rete», senza batteria niente «Verso batteria». Se una fonte
viene tolta da «Configura», il sensore che ne dipendeva sparisce dal registro
invece di restare li' non disponibile per sempre.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import MATCH_ALL, PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, VERSI_BATTERIA, VERSI_RETE
from .impianto import Impianto

ICONE_RETE = {
    "immissione": "mdi:transmission-tower-export",
    "prelievo": "mdi:transmission-tower-import",
    "fermo": "mdi:transmission-tower",
}
ICONE_BATTERIA = {
    "carica": "mdi:battery-arrow-up",
    "scarica": "mdi:battery-arrow-down",
    "fermo": "mdi:battery",
}


def sensori_per(impianto: Impianto) -> list[SensorEntity]:
    """I sensori che questo impianto sa calcolare, dalla mappa sempre presente in poi."""
    entita = impianto.entita
    sensori: list[SensorEntity] = [MappaSensor(impianto)]
    if "scambio_rete" in entita or "consumo" in entita:
        sensori.append(AutoconsumoSensor(impianto))
    if "scambio_rete" in entita:
        sensori.append(VersoReteSensor(impianto))
    if "batteria" in entita:
        sensori.append(VersoBatteriaSensor(impianto))
    return sensori


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    impianto: Impianto = hass.data[DOMAIN][entry.entry_id]
    sensori = sensori_per(impianto)

    registro = er.async_get(hass)
    presenti = {sensore.unique_id for sensore in sensori}
    for chiave in ("autoconsumo", "verso_rete", "verso_batteria"):
        unique_id = f"{entry.entry_id}_{chiave}"
        if unique_id in presenti:
            continue
        entity_id = registro.async_get_entity_id("sensor", DOMAIN, unique_id)
        if entity_id:
            registro.async_remove(entity_id)

    async_add_entities(sensori)


class _SensoreImpianto(SensorEntity):
    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, impianto: Impianto, chiave: str) -> None:
        self._impianto = impianto
        self._attr_translation_key = chiave
        self._attr_unique_id = f"{impianto.entry.entry_id}_{chiave}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, impianto.entry.entry_id)},
            name=impianto.entry.title,
            manufacturer="Automatic Systems",
            model="Sinottico fotovoltaico",
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self._impianto.async_add_listener(self.async_write_ha_state))


class MappaSensor(_SensoreImpianto):
    """Stato: quante entita' sono collegate. Attributi: tutto quello che serve alla card."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:transit-connection-variant"
    _unrecorded_attributes = frozenset({MATCH_ALL})

    def __init__(self, impianto: Impianto) -> None:
        super().__init__(impianto, "mappa")

    @property
    def native_value(self) -> int:
        return len(self._impianto.entita)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self._impianto.attributi


class AutoconsumoSensor(_SensoreImpianto):
    """La quota di produzione che resta in casa. Di notte e' sconosciuta, non zero."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 0
    _attr_icon = "mdi:home-lightning-bolt-outline"

    def __init__(self, impianto: Impianto) -> None:
        super().__init__(impianto, "autoconsumo")

    @property
    def native_value(self) -> float | None:
        return self._impianto.derivate.get("autoconsumo")


class VersoReteSensor(_SensoreImpianto):
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = VERSI_RETE

    def __init__(self, impianto: Impianto) -> None:
        super().__init__(impianto, "verso_rete")

    @property
    def native_value(self) -> str | None:
        return self._impianto.derivate.get("verso_rete")

    @property
    def icon(self) -> str:
        return ICONE_RETE.get(self.native_value or "", "mdi:transmission-tower")


class VersoBatteriaSensor(_SensoreImpianto):
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = VERSI_BATTERIA

    def __init__(self, impianto: Impianto) -> None:
        super().__init__(impianto, "verso_batteria")

    @property
    def native_value(self) -> str | None:
        return self._impianto.derivate.get("verso_batteria")

    @property
    def icon(self) -> str:
        return ICONE_BATTERIA.get(self.native_value or "", "mdi:battery")
