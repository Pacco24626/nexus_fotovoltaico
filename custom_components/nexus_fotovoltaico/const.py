"""Costanti dell'integrazione Nexus Fotovoltaico."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "nexus_fotovoltaico"
PLATFORMS: list[Platform] = [Platform.SENSOR]

CONF_NOME = "nome"
CONF_ENTITA = "entita"
CONF_RIFERIMENTO = "riferimento"
CONF_SEGNO_RETE = "segno_rete"
CONF_SEGNO_BATTERIA = "segno_batteria"

NOME_PREDEFINITO = "Fotovoltaico"
# Potenza (W) oltre la quale il flusso disegnato non corre piu' veloce.
RIFERIMENTO_PREDEFINITO = 3000

IMMISSIONE_POSITIVA = "immissione_positiva"
PRELIEVO_POSITIVO = "prelievo_positivo"
CONVENZIONI_RETE = [IMMISSIONE_POSITIVA, PRELIEVO_POSITIVO]
CARICA_POSITIVA = "carica_positiva"
SCARICA_POSITIVA = "scarica_positiva"
CONVENZIONI_BATTERIA = [CARICA_POSITIVA, SCARICA_POSITIVA]

VERSI_RETE = ["immissione", "prelievo", "fermo"]
VERSI_BATTERIA = ["carica", "scarica", "fermo"]

RUOLO_MAPPA = "mappa_fotovoltaico"

CARD_URL_BASE = "/nexus_fotovoltaico"
CARD_FILE = "nexus-fotovoltaico-card.js"
