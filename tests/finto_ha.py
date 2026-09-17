"""Un Home Assistant finto, quanto basta per provare integrazione e config flow.

Si iniettano moduli con i soli nomi che l'integrazione importa: stati con i
loro ascoltatori, bus, registro delle entita', selettori, sezioni dei moduli e
una SensorEntity che registra le scritture. voluptuous e' finto anche lui: gli
schemi si leggono (chiavi, predefiniti, valori suggeriti), non si validano.
"""

from __future__ import annotations

import os
import sys
import types


def _modulo(nome: str, **attributi):
    m = types.ModuleType(nome)
    for chiave, valore in attributi.items():
        setattr(m, chiave, valore)
    sys.modules[nome] = m
    genitore, _, figlio = nome.rpartition(".")
    if genitore and genitore in sys.modules:
        setattr(sys.modules[genitore], figlio, m)
    return m


def callback(funzione):
    return funzione


# --- voluptuous ---------------------------------------------------------------
class _Marcatore(str):
    def __new__(cls, nome, default=None, description=None):
        s = super().__new__(cls, nome)
        s.default = default
        s.description = description
        return s


class Required(_Marcatore):
    pass


class Optional(_Marcatore):
    pass


class Schema(dict):
    pass


_modulo("voluptuous", Schema=Schema, Required=Required, Optional=Optional)


# --- core -----------------------------------------------------------------------
class State:
    def __init__(self, entity_id: str, state: str, attributes: dict | None = None) -> None:
        self.entity_id = entity_id
        self.state = state
        self.attributes = dict(attributes or {})


class Event:
    def __init__(self, event_type: str, data: dict) -> None:
        self.event_type = event_type
        self.data = data


class _Platform(str):
    SENSOR = "sensor"


class _EntityCategory(str):
    DIAGNOSTIC = "diagnostic"


class _UnitOfTemperature(str):
    CELSIUS = "°C"


class _UnitOfPower(str):
    WATT = "W"


EVENT_ENTITY_REGISTRY_UPDATED = "entity_registry_updated"

_modulo("homeassistant")
_modulo(
    "homeassistant.const",
    EVENT_HOMEASSISTANT_STARTED="homeassistant_started",
    Platform=_Platform,
    MATCH_ALL="*",
    PERCENTAGE="%",
    EntityCategory=_EntityCategory,
    UnitOfTemperature=_UnitOfTemperature,
    UnitOfPower=_UnitOfPower,
)
_modulo("homeassistant.core", Event=Event, HomeAssistant=object, State=State, callback=callback)


# --- config entries e moduli ----------------------------------------------------
class ConfigFlow:
    def __init_subclass__(cls, domain=None, **kw):
        super().__init_subclass__(**kw)
        cls.DOMAIN = domain

    def async_show_form(self, step_id, data_schema=None, errors=None):
        return {"type": "form", "step_id": step_id, "schema": data_schema, "errors": errors or {}}

    def async_create_entry(self, title=None, data=None):
        return {"type": "create_entry", "title": title, "data": data}


class OptionsFlow:
    def async_show_form(self, step_id, data_schema=None, errors=None):
        return {"type": "form", "step_id": step_id, "schema": data_schema, "errors": errors or {}}

    def async_create_entry(self, title=None, data=None):
        return {"type": "create_entry", "data": data}


_modulo(
    "homeassistant.config_entries",
    ConfigEntry=object,
    ConfigFlow=ConfigFlow,
    ConfigFlowResult=dict,
    OptionsFlow=OptionsFlow,
)


class section:  # noqa: N801  (stesso nome di Home Assistant)
    def __init__(self, schema, options=None) -> None:
        self.schema = schema
        self.options = {"collapsed": False, **(options or {})}


_modulo("homeassistant.data_entry_flow", section=section)


# --- helpers ----------------------------------------------------------------------
_modulo("homeassistant.helpers")


class VoceRegistro:
    def __init__(self, entity_id: str, platform: str, unique_id: str | None = None) -> None:
        self.entity_id = entity_id
        self.platform = platform
        self.unique_id = unique_id


class Registro:
    def __init__(self) -> None:
        self.entities: dict[str, VoceRegistro] = {}
        self.rimosse: list[str] = []

    def aggiungi(self, entity_id: str, platform: str, unique_id: str | None = None) -> None:
        self.entities[entity_id] = VoceRegistro(entity_id, platform, unique_id)

    def async_get_entity_id(self, dominio: str, piattaforma: str, unique_id: str):
        for voce in self.entities.values():
            if voce.platform == piattaforma and voce.unique_id == unique_id and voce.entity_id.startswith(dominio + "."):
                return voce.entity_id
        return None

    def async_remove(self, entity_id: str) -> None:
        self.entities.pop(entity_id, None)
        self.rimosse.append(entity_id)


_modulo(
    "homeassistant.helpers.entity_registry",
    EVENT_ENTITY_REGISTRY_UPDATED=EVENT_ENTITY_REGISTRY_UPDATED,
    async_get=lambda hass: hass.registro,
)


def async_track_state_change_event(hass, entity_ids, azione):
    voce = (set(entity_ids), azione)
    hass.stati.ascoltatori.append(voce)

    def annulla():
        if voce in hass.stati.ascoltatori:
            hass.stati.ascoltatori.remove(voce)

    return annulla


_modulo("homeassistant.helpers.event", async_track_state_change_event=async_track_state_change_event)


class _Config(dict):
    def __init__(self, **kw):
        super().__init__(**kw)


class EntitySelector:
    def __init__(self, config):
        self.config = config


class NumberSelector:
    def __init__(self, config):
        self.config = config


class SelectSelector:
    def __init__(self, config):
        self.config = config


class _Modo:
    BOX = "box"
    SLIDER = "slider"
    LIST = "list"
    DROPDOWN = "dropdown"


_modulo(
    "homeassistant.helpers.selector",
    EntitySelector=EntitySelector,
    EntitySelectorConfig=_Config,
    NumberSelector=NumberSelector,
    NumberSelectorConfig=_Config,
    NumberSelectorMode=_Modo,
    SelectSelector=SelectSelector,
    SelectSelectorConfig=_Config,
    SelectSelectorMode=_Modo,
    SelectOptionDict=lambda **kw: dict(kw),
)


class DeviceInfo(dict):
    def __init__(self, **kw):
        super().__init__(**kw)


_modulo("homeassistant.helpers.device_registry", DeviceInfo=DeviceInfo)
_modulo("homeassistant.helpers.entity_platform", AddEntitiesCallback=object)
_modulo("homeassistant.helpers.config_validation", config_entry_only_config_schema=lambda dominio: None)


# --- sensori --------------------------------------------------------------------------
class SensorEntity:
    _attr_device_class = None
    _attr_icon = None

    def __init__(self) -> None:
        pass

    def async_on_remove(self, funzione) -> None:
        self.__dict__.setdefault("_da_rimuovere", []).append(funzione)

    def async_write_ha_state(self) -> None:
        self.__dict__["scritture"] = self.__dict__.get("scritture", 0) + 1

    def rimuovi(self) -> None:
        for funzione in self.__dict__.get("_da_rimuovere", []):
            funzione()

    @property
    def device_class(self):
        return self._attr_device_class

    @property
    def unique_id(self):
        return self._attr_unique_id


class _SensorDeviceClass:
    ENUM = "enum"
    TEMPERATURE = "temperature"
    TEMPERATURE_DELTA = "temperature_delta"
    POWER = "power"


class _SensorStateClass:
    MEASUREMENT = "measurement"


_modulo("homeassistant.components")
_modulo(
    "homeassistant.components.sensor",
    SensorEntity=SensorEntity,
    SensorDeviceClass=_SensorDeviceClass,
    SensorStateClass=_SensorStateClass,
)
_modulo("homeassistant.components.frontend", add_extra_js_url=lambda hass, url: None)
_modulo("homeassistant.components.http", StaticPathConfig=lambda *a, **k: None)
_modulo("homeassistant.loader", async_get_integration=None)


# --- hass ----------------------------------------------------------------------------
class Stati:
    def __init__(self) -> None:
        self._stati: dict[str, State] = {}
        self.ascoltatori: list = []

    def get(self, entity_id):
        return self._stati.get(entity_id)

    def async_entity_ids(self):
        return list(self._stati)

    def imposta(self, entity_id: str, stato: str, attributi: dict | None = None) -> None:
        vecchio = self._stati.get(entity_id)
        nuovo = State(entity_id, stato, attributi)
        self._stati[entity_id] = nuovo
        evento = Event("state_changed", {"entity_id": entity_id, "old_state": vecchio, "new_state": nuovo})
        for ids, azione in list(self.ascoltatori):
            if entity_id in ids:
                azione(evento)

    def rinomina(self, vecchio: str, nuovo: str) -> None:
        self._stati[nuovo] = self._stati.pop(vecchio)
        self._stati[nuovo].entity_id = nuovo


class Bus:
    def __init__(self) -> None:
        self.ascoltatori: list[tuple[str, object]] = []

    def async_listen(self, tipo, azione):
        voce = (tipo, azione)
        self.ascoltatori.append(voce)

        def annulla():
            if voce in self.ascoltatori:
                self.ascoltatori.remove(voce)

        return annulla

    def spara(self, tipo: str, dati: dict) -> None:
        for t, azione in list(self.ascoltatori):
            if t == tipo:
                azione(Event(tipo, dati))


class ConfigEntries:
    def __init__(self) -> None:
        self.aggiornamenti: list[tuple[object, dict]] = []

    def async_update_entry(self, entry, options=None):
        if options is not None:
            entry.options = dict(options)
        self.aggiornamenti.append((entry, dict(options or {})))
        return True


class Hass:
    def __init__(self) -> None:
        self.registro = Registro()
        self.stati = Stati()
        self.states = self.stati
        self.bus = Bus()
        self.config_entries = ConfigEntries()
        self.data: dict = {}


class Entry:
    def __init__(self, data: dict, options: dict | None = None, title: str = "Impianto", entry_id: str = "voce1") -> None:
        self.data = data
        self.options = options or {}
        self.title = title
        self.entry_id = entry_id


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "custom_components")))


# --- banco di prova ------------------------------------------------------------------
class Banco:
    def __init__(self, titolo: str) -> None:
        self.titolo = titolo
        self.passate = 0
        self.fallite: list[str] = []

    def sezione(self, testo: str) -> None:
        print(f"\n{testo}")

    def v(self, descrizione: str, condizione: bool) -> None:
        if condizione:
            self.passate += 1
            print(f"  ok   {descrizione}")
        else:
            self.fallite.append(descrizione)
            print(f"  NO   {descrizione}")

    def fine(self) -> None:
        totale = self.passate + len(self.fallite)
        if self.fallite:
            print(f"\n{self.titolo}: {self.passate}/{totale} superate")
            sys.exit(1)
        print(f"\n{self.titolo}: TUTTI I CONTROLLI SUPERATI ({totale})")
