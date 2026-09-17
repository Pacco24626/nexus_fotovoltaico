"""Prove a tavolino del config flow e del flusso delle opzioni.

    python tests/test_config_flow.py
"""

from __future__ import annotations

import asyncio

import finto_ha  # noqa: F401
from finto_ha import Banco, Entry, Hass, section

from nexus_fotovoltaico.config_flow import NexusFotovoltaicoConfigFlow, NexusFotovoltaicoOptionsFlow

b = Banco("CONFIG FLOW")

FV = "sensor.nexus_t_energy_monitor_"
VERE = {
    "produzione": f"{FV}produzione_fotovoltaico",
    "consumo": f"{FV}consumo_abitazione",
    "scambio_rete": f"{FV}potenza_scambio_rete",
    "giornaliera": f"{FV}produzione_giornaliera",
    "prelevata": f"{FV}energia_prelevata_rete",
    "immessa": f"{FV}energia_immessa_rete",
    "batteria": f"{FV}potenza_accumulo_batteria",
    "soc": f"{FV}stato_carica_batteria_soc",
}


def hass_con(produzione="46", consumo="452", scambio="-406"):
    hass = Hass()
    for entity_id in VERE.values():
        hass.stati.imposta(entity_id, "0")
    hass.stati.imposta(VERE["produzione"], produzione)
    hass.stati.imposta(VERE["consumo"], consumo)
    hass.stati.imposta(VERE["scambio_rete"], scambio)
    return hass


def campi(schema):
    return {str(k): (k, v) for k, v in schema.items()}


def voce(risultato, sezione, nome):
    _, sez = campi(risultato["schema"])[sezione]
    return next(k for k in sez.schema if str(k) == nome)


def suggerito(risultato, sezione, nome):
    return (voce(risultato, sezione, nome).description or {}).get("suggested_value")


async def aperto(hass):
    flusso = NexusFotovoltaicoConfigFlow()
    flusso.hass = hass
    return flusso, await flusso.async_step_user()


async def main():
    b.sezione("1. Apertura del modulo, di notte come il 16/09")
    flusso, r = await aperto(hass_con())
    c = campi(r["schema"])
    b.v("modulo utente con nome «Fotovoltaico»", r["step_id"] == "user" and c["nome"][0].default == "Fotovoltaico")
    b.v("quattro sezioni", all(isinstance(c[s][1], section) for s in ("potenze", "energie", "accumulo", "convenzioni")))
    b.v("l'accumulo parte chiuso, le convenzioni aperte",
        c["accumulo"][1].options["collapsed"] and not c["convenzioni"][1].options["collapsed"])
    b.v("produzione proposta", suggerito(r, "potenze", "produzione") == VERE["produzione"])
    b.v("produzione obbligatoria, consumo facoltativo",
        type(voce(r, "potenze", "produzione")).__name__ == "Required" and type(voce(r, "potenze", "consumo")).__name__ == "Optional")
    b.v("convenzione proposta dai valori: positivo = immissione", voce(r, "convenzioni", "segno_rete").default == "immissione_positiva")
    selettore = c["convenzioni"][1].schema[voce(r, "convenzioni", "segno_rete")]
    b.v("le etichette della convenzione sono tradotte", selettore.config["translation_key"] == "segno_rete")

    _, r = await aperto(hass_con(scambio="406"))
    b.v("se il contatore conta al contrario la proposta si ribalta", voce(r, "convenzioni", "segno_rete").default == "prelievo_positivo")
    _, r = await aperto(hass_con(produzione="0", consumo="30", scambio="-30"))
    b.v("valori troppo piccoli: si propone la convenzione piu' comune", voce(r, "convenzioni", "segno_rete").default == "immissione_positiva")

    b.sezione("2. Invio")
    flusso, _ = await aperto(hass_con())
    r = await flusso.async_step_user({
        "nome": "Tetto",
        "potenze": {"produzione": VERE["produzione"], "consumo": VERE["consumo"], "scambio_rete": VERE["scambio_rete"]},
        "energie": {"giornaliera": VERE["giornaliera"]},
        "accumulo": {"batteria": "", "soc": ""},
        "convenzioni": {"segno_rete": "prelievo_positivo", "segno_batteria": "carica_positiva"},
    })
    b.v("voce creata col nome scelto", r["type"] == "create_entry" and r["title"] == "Tetto")
    b.v("entita' in piano e convenzioni nei dati", r["data"] == {
        "entita": {"produzione": VERE["produzione"], "consumo": VERE["consumo"], "scambio_rete": VERE["scambio_rete"], "giornaliera": VERE["giornaliera"]},
        "segno_rete": "prelievo_positivo",
        "segno_batteria": "carica_positiva",
    })
    flusso, _ = await aperto(hass_con())
    r = await flusso.async_step_user({"nome": "", "potenze": {"produzione": VERE["produzione"]}, "convenzioni": {"segno_rete": "inventata"}})
    b.v("convenzione sconosciuta: quella comune", r["data"]["segno_rete"] == "immissione_positiva")
    b.v("nome vuoto: «Fotovoltaico»", r["title"] == "Fotovoltaico")

    b.sezione("3. Errori")
    flusso, _ = await aperto(hass_con())
    r = await flusso.async_step_user({"nome": "X", "potenze": {"consumo": VERE["consumo"]}, "convenzioni": {"segno_rete": "prelievo_positivo"}})
    b.v("senza produzione il modulo torna con l'errore", r["type"] == "form" and r["errors"] == {"base": "manca_produzione"})
    b.v("la convenzione scelta resta scelta", voce(r, "convenzioni", "segno_rete").default == "prelievo_positivo")
    r = await flusso.async_step_user({"nome": "X", "potenze": {"produzione": VERE["produzione"], "consumo": VERE["produzione"]}})
    b.v("stessa entita' due volte: errore", r["errors"] == {"base": "entita_ripetuta"})

    b.sezione("4. Opzioni")
    voce_conf = Entry({"entita": {"produzione": VERE["produzione"], "scambio_rete": VERE["scambio_rete"]}, "segno_rete": "prelievo_positivo", "segno_batteria": "carica_positiva"})
    opzioni = NexusFotovoltaicoOptionsFlow()
    opzioni.config_entry = voce_conf
    r = await opzioni.async_step_init()
    c = campi(r["schema"])
    b.v("entita' attuali precompilate", suggerito(r, "potenze", "scambio_rete") == VERE["scambio_rete"])
    b.v("niente proposte a sorpresa per le voci non collegate", suggerito(r, "potenze", "consumo") is None)
    b.v("la convenzione salvata e' quella proposta", voce(r, "convenzioni", "segno_rete").default == "prelievo_positivo")
    b.v("animazione chiusa, fondo scala 3000 W", c["animazione"][1].options["collapsed"] and next(iter(c["animazione"][1].schema)).default == 3000.0)
    r = await opzioni.async_step_init({
        "potenze": {"produzione": VERE["produzione"], "scambio_rete": VERE["scambio_rete"]},
        "accumulo": {"batteria": VERE["batteria"], "soc": VERE["soc"]},
        "convenzioni": {"segno_rete": "immissione_positiva", "segno_batteria": "scarica_positiva"},
        "animazione": {"riferimento": 4000},
    })
    b.v("opzioni salvate con batteria, convenzioni e fondo scala", r["type"] == "create_entry" and r["data"] == {
        "entita": {"produzione": VERE["produzione"], "scambio_rete": VERE["scambio_rete"], "batteria": VERE["batteria"], "soc": VERE["soc"]},
        "segno_rete": "immissione_positiva",
        "segno_batteria": "scarica_positiva",
        "riferimento": 4000.0,
    })
    r = await opzioni.async_step_init({"potenze": {}, "animazione": {"riferimento": 4000}})
    b.v("anche nelle opzioni la produzione e' obbligatoria", r["type"] == "form" and r["errors"] == {"base": "manca_produzione"})


asyncio.run(main())
b.fine()
