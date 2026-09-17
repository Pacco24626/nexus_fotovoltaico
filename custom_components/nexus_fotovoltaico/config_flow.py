"""Config flow: come si chiama l'impianto, quali entita' lo descrivono e come conta il contatore.

Le entita' si scelgono in tre sezioni (potenze, energie, accumulo) e il modulo
arriva gia' compilato con quelle riconosciute dal nome. La convenzione dello
scambio con la rete viene proposta guardando i valori di adesso: se produzione
meno consumo ha lo stesso segno dello scambio, il positivo e' l'immissione.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import section
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import selector

from .const import (
    CARICA_POSITIVA,
    CONF_ENTITA,
    CONF_NOME,
    CONF_RIFERIMENTO,
    CONF_SEGNO_BATTERIA,
    CONF_SEGNO_RETE,
    CONVENZIONI_BATTERIA,
    CONVENZIONI_RETE,
    DOMAIN,
    IMMISSIONE_POSITIVA,
    NOME_PREDEFINITO,
    RIFERIMENTO_PREDEFINITO,
)
from .logica import SEZIONI, SLOT, convenzione_proposta, entita_da_modulo, errori_entita, proposte

SEZIONE_CONVENZIONI = "convenzioni"
SEZIONE_ANIMAZIONE = "animazione"


def _proposte_da_hass(hass: HomeAssistant) -> dict[str, str]:
    """Le entita' proposte, escluse quelle create da questa stessa integrazione."""
    nostre = {
        voce.entity_id for voce in er.async_get(hass).entities.values() if voce.platform == DOMAIN
    }
    return proposte(hass.states.async_entity_ids(), escludi=nostre)


def _stato(hass: HomeAssistant, entity_id: str | None) -> str | None:
    stato = hass.states.get(entity_id) if entity_id else None
    return None if stato is None else stato.state


def _campi_entita(valori: Mapping[str, str], chiuse: tuple[str, ...]) -> dict[Any, Any]:
    """Le tre sezioni di entita', con i valori proposti (o gia' scelti) precompilati."""
    campi: dict[Any, Any] = {}
    for nome_sezione in SEZIONI:
        interno: dict[Any, Any] = {}
        for slot in (s for s in SLOT if s.sezione == nome_sezione):
            descrizione = {"suggested_value": valori[slot.chiave]} if valori.get(slot.chiave) else None
            marcatore = vol.Required if slot.obbligatorio else vol.Optional
            interno[marcatore(slot.chiave, description=descrizione)] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain=list(slot.domini))
            )
        campi[vol.Required(nome_sezione)] = section(
            vol.Schema(interno), {"collapsed": nome_sezione in chiuse}
        )
    return campi


def _sezione_convenzioni(segno_rete: str, segno_batteria: str) -> dict[Any, Any]:
    def scelta(opzioni: list[str], chiave: str) -> selector.SelectSelector:
        return selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=opzioni, translation_key=chiave, mode=selector.SelectSelectorMode.LIST
            )
        )

    return {
        vol.Required(SEZIONE_CONVENZIONI): section(
            vol.Schema(
                {
                    vol.Required(CONF_SEGNO_RETE, default=segno_rete): scelta(CONVENZIONI_RETE, CONF_SEGNO_RETE),
                    vol.Required(CONF_SEGNO_BATTERIA, default=segno_batteria): scelta(
                        CONVENZIONI_BATTERIA, CONF_SEGNO_BATTERIA
                    ),
                }
            ),
            {"collapsed": False},
        )
    }


def _convenzioni_da_modulo(dati: Mapping[str, Any], segno_rete: str, segno_batteria: str) -> dict[str, str]:
    scelte = dati.get(SEZIONE_CONVENZIONI) or {}
    rete = scelte.get(CONF_SEGNO_RETE, segno_rete)
    batteria = scelte.get(CONF_SEGNO_BATTERIA, segno_batteria)
    return {
        CONF_SEGNO_RETE: rete if rete in CONVENZIONI_RETE else IMMISSIONE_POSITIVA,
        CONF_SEGNO_BATTERIA: batteria if batteria in CONVENZIONI_BATTERIA else CARICA_POSITIVA,
    }


class NexusFotovoltaicoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Una voce per impianto: se ne possono configurare piu' d'uno."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errori: dict[str, str] = {}
        nome = NOME_PREDEFINITO
        segno_rete, segno_batteria = IMMISSIONE_POSITIVA, CARICA_POSITIVA

        if user_input is not None:
            entita = entita_da_modulo(user_input)
            nome = (user_input.get(CONF_NOME) or "").strip() or NOME_PREDEFINITO
            convenzioni = _convenzioni_da_modulo(user_input, segno_rete, segno_batteria)
            errori = errori_entita(entita)
            if not errori:
                return self.async_create_entry(title=nome, data={CONF_ENTITA: entita, **convenzioni})
            valori = entita
            segno_rete, segno_batteria = convenzioni[CONF_SEGNO_RETE], convenzioni[CONF_SEGNO_BATTERIA]
        else:
            valori = _proposte_da_hass(self.hass)
            proposta = convenzione_proposta(
                _stato(self.hass, valori.get("produzione")),
                _stato(self.hass, valori.get("consumo")),
                _stato(self.hass, valori.get("scambio_rete")),
            )
            segno_rete = proposta or IMMISSIONE_POSITIVA

        schema = vol.Schema(
            {
                vol.Required(CONF_NOME, default=nome): str,
                **_campi_entita(valori, chiuse=("accumulo",)),
                **_sezione_convenzioni(segno_rete, segno_batteria),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errori)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return NexusFotovoltaicoOptionsFlow()


class NexusFotovoltaicoOptionsFlow(OptionsFlow):
    """Entita', convenzioni e fondo scala si cambiano senza reinstallare."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        attuali = {**self.config_entry.data, **self.config_entry.options}
        errori: dict[str, str] = {}
        segno_rete = attuali.get(CONF_SEGNO_RETE, IMMISSIONE_POSITIVA)
        segno_batteria = attuali.get(CONF_SEGNO_BATTERIA, CARICA_POSITIVA)
        riferimento = attuali.get(CONF_RIFERIMENTO, RIFERIMENTO_PREDEFINITO)

        if user_input is not None:
            entita = entita_da_modulo(user_input)
            convenzioni = _convenzioni_da_modulo(user_input, segno_rete, segno_batteria)
            riferimento = (user_input.get(SEZIONE_ANIMAZIONE) or {}).get(CONF_RIFERIMENTO, riferimento)
            errori = errori_entita(entita)
            if not errori:
                return self.async_create_entry(
                    data={CONF_ENTITA: entita, **convenzioni, CONF_RIFERIMENTO: float(riferimento)}
                )
            valori = entita
            segno_rete, segno_batteria = convenzioni[CONF_SEGNO_RETE], convenzioni[CONF_SEGNO_BATTERIA]
        else:
            valori = dict(attuali.get(CONF_ENTITA) or {})

        schema = vol.Schema(
            {
                **_campi_entita(valori, chiuse=()),
                **_sezione_convenzioni(segno_rete, segno_batteria),
                vol.Required(SEZIONE_ANIMAZIONE): section(
                    vol.Schema(
                        {
                            vol.Required(CONF_RIFERIMENTO, default=float(riferimento)): selector.NumberSelector(
                                selector.NumberSelectorConfig(
                                    min=100,
                                    max=100000,
                                    step=100,
                                    mode=selector.NumberSelectorMode.BOX,
                                    unit_of_measurement="W",
                                )
                            )
                        }
                    ),
                    {"collapsed": True},
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema, errors=errori)
