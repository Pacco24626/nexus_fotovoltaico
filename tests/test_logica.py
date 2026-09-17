"""Prove a tavolino della logica: proposte, versi, autoconsumo, convenzione proposta.

    python tests/test_logica.py
"""

from __future__ import annotations

import finto_ha  # noqa: F401  (prepara i moduli e il percorso)
from finto_ha import Banco

from nexus_fotovoltaico.logica import (
    OBBLIGATORI,
    autoconsumo,
    convenzione_proposta,
    entita_da_modulo,
    errori_entita,
    numero,
    proposte,
    rinomina,
    verso_batteria,
    verso_rete,
)

b = Banco("LOGICA")

FV = "sensor.nexus_t_energy_monitor_"
IMPIANTO = [
    f"{FV}consumo_abitazione",
    f"{FV}energia_immessa_rete",
    f"{FV}energia_prelevata_rete",
    f"{FV}potenza_accumulo_batteria",
    f"{FV}potenza_scambio_rete",
    f"{FV}produzione_fotovoltaico",
    f"{FV}produzione_giornaliera",
    f"{FV}produzione_totale",
    f"{FV}stato_carica_batteria_soc",
    "sensor.consumi_casa_ampere_fotovoltaico_412",
    "sensor.a_vecchio_contatore_energia_prelevata",
    "light.salotto",
]

b.sezione("1. Proposte dal nome")
p = proposte(IMPIANTO)
b.v("produzione", p.get("produzione") == f"{FV}produzione_fotovoltaico")
b.v("consumo", p.get("consumo") == f"{FV}consumo_abitazione")
b.v("scambio con la rete", p.get("scambio_rete") == f"{FV}potenza_scambio_rete")
b.v("produzione di oggi, non quella totale", p.get("giornaliera") == f"{FV}produzione_giornaliera")
b.v("l'energia prelevata segue il prefisso della produzione, non l'ordine alfabetico",
    p.get("prelevata") == f"{FV}energia_prelevata_rete")
b.v("batteria e stato di carica proposti", p.get("batteria") == f"{FV}potenza_accumulo_batteria" and p.get("soc") == f"{FV}stato_carica_batteria_soc")
b.v("gli ampere del contatore non sono la produzione", "ampere" not in p.get("produzione", ""))
b.v("proposta stabile rispetto all'ordine", proposte(IMPIANTO) == proposte(list(reversed(IMPIANTO))))
b.v("un'entita' esclusa non viene proposta", "produzione" not in proposte([f"{FV}produzione_fotovoltaico"], escludi=[f"{FV}produzione_fotovoltaico"]))

b.sezione("2. Modulo e rinomina")
e = entita_da_modulo({"potenze": {"produzione": "sensor.p", "consumo": ""}, "accumulo": {"soc": "sensor.s"}, "convenzioni": {"segno_rete": "x"}})
b.v("sezioni in piano, senza vuoti e senza convenzioni", e == {"produzione": "sensor.p", "soc": "sensor.s"})
b.v("la produzione e' l'unica obbligatoria", OBBLIGATORI == ("produzione",))
b.v("senza produzione: errore", errori_entita({"consumo": "sensor.c"}) == {"base": "manca_produzione"})
b.v("stessa entita' due volte: errore", errori_entita({"produzione": "sensor.p", "consumo": "sensor.p"}) == {"base": "entita_ripetuta"})
b.v("rinomina di una nostra entita'", rinomina({"produzione": "sensor.p"}, "sensor.p", "sensor.pv") == {"produzione": "sensor.pv"})
b.v("rinomina di un'estranea: niente", rinomina({"produzione": "sensor.p"}, "sensor.x", "sensor.y") is None)

b.sezione("3. Verso della rete")
b.v("Nexus-T di notte: -406 W e' prelievo", verso_rete("-406", "immissione_positiva") == "prelievo")
b.v("positivo con immissione positiva: immissione", verso_rete("2430", "immissione_positiva") == "immissione")
b.v("con la convenzione opposta si ribalta", verso_rete("-406", "prelievo_positivo") == "immissione")
b.v("e anche il positivo", verso_rete("2430", "prelievo_positivo") == "prelievo")
b.v("vicino a zero: fermo", verso_rete("3", "immissione_positiva") == "fermo")
b.v("non disponibile: non si sa (non «fermo»)", verso_rete("unavailable", "immissione_positiva") is None)

b.sezione("4. Verso della batteria")
b.v("positivo = carica", verso_batteria("1500", "carica_positiva") == "carica")
b.v("negativo = scarica", verso_batteria("-800", "carica_positiva") == "scarica")
b.v("convenzione opposta", verso_batteria("1500", "scarica_positiva") == "scarica")
b.v("batteria a riposo", verso_batteria("0", "carica_positiva") == "fermo")
b.v("non disponibile: non si sa", verso_batteria("unknown", "carica_positiva") is None)

b.sezione("5. Autoconsumo")
I = "immissione_positiva"
b.v("caso vero con il sole: 3240 prodotti, 2430 immessi = 25%",
    autoconsumo({"produzione": "3240", "scambio_rete": "2430"}, I) == 25.0)
b.v("si preleva: tutto autoconsumato", autoconsumo({"produzione": "46", "scambio_rete": "-406"}, I) == 100.0)
b.v("con la convenzione opposta l'immissione e' il negativo",
    autoconsumo({"produzione": "3240", "scambio_rete": "-2430"}, "prelievo_positivo") == 25.0)
b.v("di notte non si calcola", autoconsumo({"produzione": "0", "scambio_rete": "-452"}, I) is None)
b.v("senza scambio si usa il consumo", autoconsumo({"produzione": "3240", "consumo": "810"}, I) == 25.0)
b.v("consumo maggiore della produzione: 100%", autoconsumo({"produzione": "900", "consumo": "1400"}, I) == 100.0)
b.v("lo scambio vince sul consumo quando ci sono tutti e due",
    autoconsumo({"produzione": "2150", "consumo": "480", "scambio_rete": "170"}, I) == 92.1)
b.v("scambio collegato ma non leggibile: non si ripiega sul consumo",
    autoconsumo({"produzione": "2150", "consumo": "480", "scambio_rete": "unavailable"}, I) is None)
b.v("ne' scambio ne' consumo: non si calcola", autoconsumo({"produzione": "2150"}, I) is None)
b.v("immissione maggiore della produzione (misure sfasate): non va sotto zero",
    autoconsumo({"produzione": "500", "scambio_rete": "800"}, I) == 0.0)

b.sezione("6. Convenzione proposta dai valori di adesso")
b.v("Nexus-T di notte: 46 - 452 = -406 e lo scambio e' -406: positivo = immissione",
    convenzione_proposta("46", "452", "-406") == "immissione_positiva")
b.v("stessi valori con il segno opposto: positivo = prelievo", convenzione_proposta("46", "452", "406") == "prelievo_positivo")
b.v("di giorno, immissione vera", convenzione_proposta("3240", "810", "2430") == "immissione_positiva")
b.v("bilancio troppo piccolo: nessuna proposta", convenzione_proposta("400", "450", "-50") is None)
b.v("scambio troppo piccolo: nessuna proposta", convenzione_proposta("1000", "400", "20") is None)
b.v("un valore mancante: nessuna proposta", convenzione_proposta("1000", "unavailable", "600") is None)
b.v("lettura con la virgola", numero("-406,5") == -406.5)

b.fine()
