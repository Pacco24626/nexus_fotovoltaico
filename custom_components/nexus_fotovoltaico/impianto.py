"""L'impianto: segue le entita' collegate e tiene i valori calcolati.

Non legge niente dall'inverter: lavora solo sulle entita' che Home Assistant ha
gia'. Quando una di queste cambia ricalcola verso della rete, verso della
batteria e autoconsumo, e avvisa i sensori solo se il risultato e' cambiato.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.entity_registry import EVENT_ENTITY_REGISTRY_UPDATED
from homeassistant.helpers.event import async_track_state_change_event

from .const import (
    CARICA_POSITIVA,
    CONF_ENTITA,
    CONF_RIFERIMENTO,
    CONF_SEGNO_BATTERIA,
    CONF_SEGNO_RETE,
    CONVENZIONI_BATTERIA,
    CONVENZIONI_RETE,
    IMMISSIONE_POSITIVA,
    RIFERIMENTO_PREDEFINITO,
    RUOLO_MAPPA,
)
from .logica import autoconsumo, rinomina, verso_batteria, verso_rete


class Impianto:
    """Un impianto fotovoltaico configurato."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.derivate: dict[str, Any] = {"verso_rete": None, "verso_batteria": None, "autoconsumo": None}
        self._ascoltatori: list[Callable[[], None]] = []
        self._annulla: list[Callable[[], None]] = []

    # -------------------------------------------------------------------------
    @property
    def configurazione(self) -> dict[str, Any]:
        return {**self.entry.data, **self.entry.options}

    @property
    def entita(self) -> dict[str, str]:
        return dict(self.configurazione.get(CONF_ENTITA) or {})

    @property
    def opzioni(self) -> dict[str, Any]:
        conf = self.configurazione
        try:
            riferimento = float(conf.get(CONF_RIFERIMENTO, RIFERIMENTO_PREDEFINITO))
        except (TypeError, ValueError):
            riferimento = float(RIFERIMENTO_PREDEFINITO)
        segno_rete = conf.get(CONF_SEGNO_RETE)
        segno_batteria = conf.get(CONF_SEGNO_BATTERIA)
        return {
            CONF_RIFERIMENTO: riferimento if riferimento > 0 else float(RIFERIMENTO_PREDEFINITO),
            CONF_SEGNO_RETE: segno_rete if segno_rete in CONVENZIONI_RETE else IMMISSIONE_POSITIVA,
            CONF_SEGNO_BATTERIA: segno_batteria if segno_batteria in CONVENZIONI_BATTERIA else CARICA_POSITIVA,
        }

    @property
    def attributi(self) -> dict[str, Any]:
        """Quello che serve alla card. Oggetti nuovi a ogni lettura: HA confronta
        gli attributi con una copia superficiale e non vedrebbe le modifiche sul posto."""
        return {
            "ruolo": RUOLO_MAPPA,
            "nome": self.entry.title,
            "entita": self.entita,
            "opzioni": self.opzioni,
            "derivate": dict(self.derivate),
        }

    # -------------------------------------------------------------------------
    async def async_start(self) -> None:
        ids = sorted(set(self.entita.values()))
        if ids:
            self._annulla.append(async_track_state_change_event(self.hass, ids, self._al_cambio))
        self._annulla.append(self.hass.bus.async_listen(EVENT_ENTITY_REGISTRY_UPDATED, self._al_registro))
        self._ricalcola()

    async def async_stop(self) -> None:
        while self._annulla:
            self._annulla.pop()()

    @callback
    def async_add_listener(self, azione: Callable[[], None]) -> Callable[[], None]:
        self._ascoltatori.append(azione)

        def rimuovi() -> None:
            if azione in self._ascoltatori:
                self._ascoltatori.remove(azione)

        return rimuovi

    # -------------------------------------------------------------------------
    def _grezzo(self, entity_id: str) -> str | None:
        stato = self.hass.states.get(entity_id)
        return None if stato is None else stato.state

    def _ricalcola(self) -> bool:
        entita = self.entita
        opzioni = self.opzioni
        letture = {slot: self._grezzo(entity_id) for slot, entity_id in entita.items()}
        nuove = {
            "verso_rete": verso_rete(letture["scambio_rete"], opzioni[CONF_SEGNO_RETE])
            if "scambio_rete" in letture
            else None,
            "verso_batteria": verso_batteria(letture["batteria"], opzioni[CONF_SEGNO_BATTERIA])
            if "batteria" in letture
            else None,
            "autoconsumo": autoconsumo(letture, opzioni[CONF_SEGNO_RETE]),
        }
        if nuove == self.derivate:
            return False
        self.derivate = nuove
        return True

    @callback
    def _al_cambio(self, _evento: Event) -> None:
        if self._ricalcola():
            for azione in list(self._ascoltatori):
                azione()

    @callback
    def _al_registro(self, evento: Event) -> None:
        """Un'entita' collegata rinominata: si aggiorna il collegamento, non si perde."""
        dati = evento.data
        if dati.get("action") != "update" or "old_entity_id" not in dati:
            return
        nuove = rinomina(self.entita, dati["old_entity_id"], dati["entity_id"])
        if nuove is None:
            return
        self.hass.config_entries.async_update_entry(
            self.entry, options={**self.entry.options, CONF_ENTITA: nuove}
        )
