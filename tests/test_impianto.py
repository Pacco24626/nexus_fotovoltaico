"""Prove a tavolino dell'impianto e dei sensori, su un Home Assistant finto.

    python tests/test_impianto.py
"""

from __future__ import annotations

import asyncio

import finto_ha
from finto_ha import Banco, Entry, Hass

from nexus_fotovoltaico.const import VERSI_BATTERIA, VERSI_RETE
from nexus_fotovoltaico.impianto import Impianto
from nexus_fotovoltaico.sensor import (
    AutoconsumoSensor,
    MappaSensor,
    VersoBatteriaSensor,
    VersoReteSensor,
    async_setup_entry,
    sensori_per,
)

b = Banco("IMPIANTO")

FV = "sensor.nexus_t_energy_monitor_"
ENTITA = {
    "produzione": f"{FV}produzione_fotovoltaico",
    "consumo": f"{FV}consumo_abitazione",
    "scambio_rete": f"{FV}potenza_scambio_rete",
    "giornaliera": f"{FV}produzione_giornaliera",
}


def prepara(entita=None, opzioni=None, data_extra=None):
    hass = Hass()
    hass.stati.imposta(f"{FV}produzione_fotovoltaico", "46")
    hass.stati.imposta(f"{FV}consumo_abitazione", "452")
    hass.stati.imposta(f"{FV}potenza_scambio_rete", "-406")
    hass.stati.imposta(f"{FV}produzione_giornaliera", "0")
    hass.stati.imposta(f"{FV}potenza_accumulo_batteria", "0")
    hass.stati.imposta("light.salotto", "off")
    # In Home Assistant un'entita' MQTT ha anche una voce nel registro: e' da li'
    # che si capisce se e' stata ritirata davvero o se semplicemente non ha
    # ancora uno stato.
    for entity_id in hass.stati.async_entity_ids():
        hass.registro.aggiungi(entity_id, "mqtt")
    data = {"entita": dict(entita or ENTITA), **(data_extra or {})}
    return hass, Entry(data, options=opzioni, title="Fotovoltaico", entry_id="fv1")


def tipi(sensori):
    return [type(s).__name__ for s in sensori]


async def main():
    b.sezione("1. Di notte, come il 16/09")
    hass, entry = prepara(data_extra={"segno_rete": "immissione_positiva"})
    impianto = Impianto(hass, entry)
    await impianto.async_start()
    b.v("verso della rete: prelievo", impianto.derivate["verso_rete"] == "prelievo")
    b.v("autoconsumo: 100% (i 46 W restano in casa)", impianto.derivate["autoconsumo"] == 100.0)
    b.v("senza batteria collegata il verso batteria non c'e'", impianto.derivate["verso_batteria"] is None)

    b.sezione("2. Quali sensori nascono")
    b.v("impianto completo senza batteria: mappa, autoconsumo, verso rete",
        tipi(sensori_per(impianto)) == ["MappaSensor", "AutoconsumoSensor", "VersoReteSensor"])
    hass2, entry2 = prepara(entita={"produzione": f"{FV}produzione_fotovoltaico"})
    b.v("sola produzione: solo la mappa", tipi(sensori_per(Impianto(hass2, entry2))) == ["MappaSensor"])
    hass3, entry3 = prepara(entita={"produzione": f"{FV}produzione_fotovoltaico", "consumo": f"{FV}consumo_abitazione", "batteria": f"{FV}potenza_accumulo_batteria"})
    b.v("con consumo e batteria ma senza scambio: autoconsumo e verso batteria, niente verso rete",
        tipi(sensori_per(Impianto(hass3, entry3))) == ["MappaSensor", "AutoconsumoSensor", "VersoBatteriaSensor"])

    b.sezione("3. Sensori")
    mappa, auto, rete = MappaSensor(impianto), AutoconsumoSensor(impianto), VersoReteSensor(impianto)
    for s in (mappa, auto, rete):
        await s.async_added_to_hass()
    a = mappa.extra_state_attributes
    b.v("ruolo della mappa", a["ruolo"] == "mappa_fotovoltaico")
    b.v("opzioni con i predefiniti", a["opzioni"] == {"riferimento": 3000.0, "segno_rete": "immissione_positiva", "segno_batteria": "carica_positiva"})
    b.v("valori calcolati nella mappa", a["derivate"] == {"verso_rete": "prelievo", "verso_batteria": None, "autoconsumo": 100.0})
    b.v("oggetti nuovi a ogni lettura", mappa.extra_state_attributes["opzioni"] is not a["opzioni"])
    b.v("verso rete e' un elenco chiuso", rete.device_class == "enum" and rete._attr_options == VERSI_RETE)
    b.v("icona del prelievo", rete.icon == "mdi:transmission-tower-import")
    b.v("unique_id legati alla voce", auto.unique_id == "fv1_autoconsumo" and rete.unique_id == "fv1_verso_rete")

    b.sezione("4. Arriva il sole")
    scritture = getattr(rete, "scritture", 0)
    hass.stati.imposta(f"{FV}produzione_fotovoltaico", "3240")
    hass.stati.imposta(f"{FV}consumo_abitazione", "810")
    b.v("con lo scambio ancora a -406 resta prelievo", rete.native_value == "prelievo")
    hass.stati.imposta(f"{FV}potenza_scambio_rete", "2430")
    b.v("scambio positivo: immissione", rete.native_value == "immissione")
    b.v("autoconsumo 25%", auto.native_value == 25.0)
    b.v("icona dell'immissione", rete.icon == "mdi:transmission-tower-export")
    b.v("i sensori sono stati riscritti", getattr(rete, "scritture", 0) > scritture)
    fisse = getattr(mappa, "scritture", 0)
    hass.stati.imposta(f"{FV}produzione_giornaliera", "4.2")
    b.v("l'energia di oggi non muove i calcolati: nessuna riscrittura", getattr(mappa, "scritture", 0) == fisse)
    hass.stati.imposta(f"{FV}potenza_scambio_rete", "unavailable")
    b.v("scambio perso: verso sconosciuto, non «fermo»", rete.native_value is None)
    b.v("e autoconsumo sconosciuto", auto.native_value is None)

    b.sezione("5. Convenzione opposta nelle opzioni")
    hass4, entry4 = prepara(opzioni={"segno_rete": "prelievo_positivo"})
    impianto4 = Impianto(hass4, entry4)
    await impianto4.async_start()
    b.v("con «positivo = prelievo» il -406 diventa immissione", impianto4.derivate["verso_rete"] == "immissione")
    b.v("e l'autoconsumo si calcola di conseguenza", impianto4.derivate["autoconsumo"] == 0.0)
    entry4.options = {"segno_rete": "inventata", "riferimento": -5}
    b.v("convenzione e fondo scala illeggibili tornano ai predefiniti",
        impianto4.opzioni == {"riferimento": 3000.0, "segno_rete": "immissione_positiva", "segno_batteria": "carica_positiva"})

    b.sezione("6. Batteria")
    hass5, entry5 = prepara(entita={**ENTITA, "batteria": f"{FV}potenza_accumulo_batteria"})
    impianto5 = Impianto(hass5, entry5)
    await impianto5.async_start()
    bat = VersoBatteriaSensor(impianto5)
    await bat.async_added_to_hass()
    b.v("batteria a zero: ferma", bat.native_value == "fermo")
    hass5.stati.imposta(f"{FV}potenza_accumulo_batteria", "1500")
    b.v("in carica", bat.native_value == "carica" and bat.icon == "mdi:battery-arrow-up")
    b.v("verso batteria e' un elenco chiuso", bat._attr_options == VERSI_BATTERIA)

    b.sezione("7. Sensori tolti da «Configura» spariscono dal registro")
    hass6, entry6 = prepara(entita={"produzione": f"{FV}produzione_fotovoltaico"})
    hass6.registro.aggiungi("sensor.fotovoltaico_verso_rete", "nexus_fotovoltaico", "fv1_verso_rete")
    hass6.registro.aggiungi("sensor.fotovoltaico_autoconsumo", "nexus_fotovoltaico", "fv1_autoconsumo")
    hass6.registro.aggiungi("sensor.fotovoltaico_mappa_impianto", "nexus_fotovoltaico", "fv1_mappa")
    hass6.registro.aggiungi("sensor.altro_autoconsumo", "altra_integrazione", "fv1_autoconsumo")
    hass6.data["nexus_fotovoltaico"] = {"fv1": Impianto(hass6, entry6)}
    aggiunti = []
    await async_setup_entry(hass6, entry6, lambda sensori: aggiunti.extend(sensori))
    b.v("verso rete e autoconsumo rimossi", sorted(hass6.registro.rimosse) == ["sensor.fotovoltaico_autoconsumo", "sensor.fotovoltaico_verso_rete"])
    b.v("la mappa resta", "sensor.fotovoltaico_mappa_impianto" in hass6.registro.entities)
    b.v("un'entita' di un'altra integrazione con lo stesso unique_id non si tocca", "sensor.altro_autoconsumo" in hass6.registro.entities)
    b.v("aggiunta la sola mappa", tipi(aggiunti) == ["MappaSensor"])

    b.sezione("8. Rinomina e arresto")
    hass.bus.spara(finto_ha.EVENT_ENTITY_REGISTRY_UPDATED, {"action": "update", "entity_id": "sensor.pv_potenza", "old_entity_id": ENTITA["produzione"], "changes": {}})
    b.v("la produzione rinominata finisce nelle opzioni", entry.options["entita"]["produzione"] == "sensor.pv_potenza")
    await impianto.async_stop()
    for s in (mappa, auto, rete):
        s.rimuovi()
    b.v("nessun ascoltatore resta attaccato", not hass.stati.ascoltatori and not hass.bus.ascoltatori and not impianto._ascoltatori)

    b.sezione("Entita' ritirate dal gateway")
    # Dalla V0.8.63 il gateway ritira le entita' dell'energia quando il modulo
    # viene spento: prima restavano in Home Assistant per sempre, ferme
    # sull'ultimo valore. Qui spariscono tutte e nove insieme, non una parte:
    # l'elenco pero' sta nella NOSTRA voce di configurazione, e continuerebbe a
    # puntare al vuoto senza dire niente a nessuno.
    hass, entry = prepara()
    impianto = Impianto(hass, entry)
    await impianto.async_start()
    b.v("impianto intero: nessun avviso", not hass.avvisi.aperti)

    hass.registro.async_remove(ENTITA["giornaliera"])
    hass.bus.spara(finto_ha.EVENT_ENTITY_REGISTRY_UPDATED,
                   {"action": "remove", "entity_id": ENTITA["giornaliera"]})
    aperti = list(hass.avvisi.aperti.items())
    b.v("entita' ritirata: si apre un avviso di riparazione", len(aperti) == 1)
    dati = aperti[0][1] if aperti else {}
    b.v("l'avviso dice quale voce, di quale impianto, ed e' un avvertimento",
        dati.get("translation_key") == "entita_sparite"
        and dati.get("translation_placeholders", {}).get("voci") == "giornaliera"
        and dati.get("translation_placeholders", {}).get("nome") == "Fotovoltaico"
        and dati.get("severity") == "warning"
        and dati.get("is_fixable") is False)
    b.v("ma la configurazione non si sgancia da sola: decide chi ha installato",
        impianto.entita.get("giornaliera") == ENTITA["giornaliera"])

    hass.registro.aggiungi(ENTITA["giornaliera"], "mqtt")
    hass.bus.spara(finto_ha.EVENT_ENTITY_REGISTRY_UPDATED,
                   {"action": "create", "entity_id": ENTITA["giornaliera"]})
    b.v("entita' tornata: l'avviso si chiude da solo", not hass.avvisi.aperti)

    # Il modulo energia spento le porta via tutte insieme, obbligatoria compresa.
    # Formula unica: un avviso solo che le elenca, senza casi speciali.
    hass, entry = prepara()
    tutte = Impianto(hass, entry)
    await tutte.async_start()
    for entity_id in list(ENTITA.values()):
        hass.registro.async_remove(entity_id)
    hass.bus.spara(finto_ha.EVENT_ENTITY_REGISTRY_UPDATED,
                   {"action": "remove", "entity_id": ENTITA["produzione"]})
    dati = list(hass.avvisi.aperti.values())[0] if hass.avvisi.aperti else {}
    b.v("modulo energia spento: un avviso solo, con dentro tutte le voci",
        len(hass.avvisi.aperti) == 1
        and dati.get("translation_placeholders", {}).get("voci")
        == ", ".join(sorted(ENTITA)))

    # Controllo che discrimina: senza STATO ma nel registro non e' una
    # sparizione. All'avvio capita di continuo, MQTT che non e' ancora pronto.
    hass, entry = prepara()
    hass.stati._stati.pop(ENTITA["consumo"], None)
    senza_stato = Impianto(hass, entry)
    await senza_stato.async_start()
    b.v("senza stato ma nel registro: nessun avviso", not hass.avvisi.aperti)

    # Il ritiro puo' essere successo mentre Home Assistant era spento.
    hass, entry = prepara()
    hass.registro.async_remove(ENTITA["consumo"])
    spenta = Impianto(hass, entry)
    await spenta.async_start()
    b.v("sparita a Home Assistant spento: l'avviso c'e' lo stesso",
        len(hass.avvisi.aperti) == 1)

    # Controllo di sanita': un rinomino non e' una sparizione.
    hass, entry = prepara()
    rinominata = Impianto(hass, entry)
    await rinominata.async_start()
    hass.registro.entities.pop(ENTITA["consumo"], None)
    hass.registro.aggiungi("sensor.consumo_nuovo", "mqtt")
    hass.bus.spara(finto_ha.EVENT_ENTITY_REGISTRY_UPDATED,
                   {"action": "update", "entity_id": "sensor.consumo_nuovo",
                    "old_entity_id": ENTITA["consumo"], "changes": {}})
    b.v("rinomino: nessun avviso, e il collegamento segue il nome nuovo",
        not hass.avvisi.aperti
        and entry.options.get("entita", {}).get("consumo") == "sensor.consumo_nuovo")


asyncio.run(main())
b.fine()
