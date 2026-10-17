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
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.entity_registry import EVENT_ENTITY_REGISTRY_UPDATED
from homeassistant.helpers.event import async_track_state_change_event

from .const import (
    CARICA_POSITIVA,
    CONF_ENTITA,
    DOMAIN,
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
        self._sparite: list[str] = []

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
        # Il ritiro puo' essere successo mentre Home Assistant era spento: qui
        # non c'e' nessun evento da aspettare, si guarda e basta.
        self._avvisa()

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

    def _senza_entita(self) -> list[str]:
        """Le voci la cui entita' non e' piu' nel registro di Home Assistant.

        Si guarda il REGISTRO, non gli stati. All'avvio un'entita' puo' non
        avere ancora uno stato - MQTT che non e' pronto - e un avviso li'
        sarebbe un falso allarme che insegna a ignorare gli avvisi. Dal
        registro una voce sparisce solo quando viene tolta davvero: dalla
        V0.8.63 e' il gateway che ritira le entita' dell'energia quando il
        modulo viene spento. Un'entita' DISABILITATA dall'utente resta nel
        registro, quindi non fa scattare niente: e' una sua scelta.
        """
        registro = er.async_get(self.hass)
        return sorted(
            chiave for chiave, entity_id in self.entita.items()
            if registro.async_get(entity_id) is None
        )

    @callback
    def _avvisa(self) -> None:
        """Apre o chiude l'avviso sulle voci rimaste senza entita'.

        Un messaggio solo, che le elenca tutte: col modulo energia spento
        spariscono insieme, obbligatoria compresa, e due messaggi diversi per
        lo stesso fatto sarebbero due cose da leggere invece di una.

        Non si sgancia niente da solo: una voce di configurazione e' di chi ha
        installato, e toglierla di nascosto gli leverebbe anche il modo di
        accorgersi che l'impianto e' cambiato. Se l'entita' torna, il
        collegamento e' ancora al suo posto e l'avviso si chiude da se'.
        """
        sparite = self._senza_entita()
        if sparite == self._sparite:
            return
        self._sparite = sparite
        chiave = f"entita_sparite_{self.entry.entry_id}"
        if not sparite:
            ir.async_delete_issue(self.hass, DOMAIN, chiave)
            return
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            chiave,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="entita_sparite",
            translation_placeholders={
                "nome": self.entry.title,
                "voci": ", ".join(sparite),
            },
        )

    @callback
    def _al_cambio(self, _evento: Event) -> None:
        if self._ricalcola():
            for azione in list(self._ascoltatori):
                azione()

    @callback
    def _al_registro(self, evento: Event) -> None:
        """Il registro si muove: un rinomino si segue, una sparizione si dice.

        Sono due cose diverse e vanno tenute diverse: chi rinomina un'entita'
        vuole che il collegamento la segua, chi se la vede togliere vuole
        saperlo.
        """
        dati = evento.data
        azione = dati.get("action")
        if azione in ("remove", "create") and dati.get("entity_id") in set(self.entita.values()):
            self._avvisa()
            return
        if azione != "update" or "old_entity_id" not in dati:
            return
        nuove = rinomina(self.entita, dati["old_entity_id"], dati["entity_id"])
        if nuove is None:
            return
        self.hass.config_entries.async_update_entry(
            self.entry, options={**self.entry.options, CONF_ENTITA: nuove}
        )
