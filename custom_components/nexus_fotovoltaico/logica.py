"""Logica del fotovoltaico senza Home Assistant: si prova a tavolino.

Qui stanno le regole che si possono sbagliare in silenzio: quali entita'
proporre, da che parte va la potenza con la rete e con la batteria (secondo la
convenzione del contatore), come si calcola l'autoconsumo e quale convenzione
proporre guardando i valori di adesso.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from .const import IMMISSIONE_POSITIVA, PRELIEVO_POSITIVO, SCARICA_POSITIVA


@dataclass(frozen=True)
class Slot:
    """Una voce del sinottico: che entita' ci va e dove sta nel modulo."""

    chiave: str
    domini: tuple[str, ...]
    cerca: str  # espressione sull'object_id, per la proposta automatica
    obbligatorio: bool
    sezione: str


SEZIONI = ("potenze", "energie", "accumulo")

SLOT: tuple[Slot, ...] = (
    Slot("produzione", ("sensor",), r"produzione_fotovoltaic", True, "potenze"),
    Slot("consumo", ("sensor",), r"consumo_(abitazione|casa)$", False, "potenze"),
    Slot("scambio_rete", ("sensor",), r"scambio_rete$", False, "potenze"),
    Slot("giornaliera", ("sensor",), r"produzione_giornaliera$", False, "energie"),
    Slot("prelevata", ("sensor",), r"energia_prelevata", False, "energie"),
    Slot("immessa", ("sensor",), r"energia_immessa", False, "energie"),
    Slot("batteria", ("sensor",), r"potenza_accumulo_batteria$|potenza_batteria$", False, "accumulo"),
    Slot("soc", ("sensor",), r"carica_batteria_soc$|batteria_soc$", False, "accumulo"),
)
CHIAVI = tuple(slot.chiave for slot in SLOT)
OBBLIGATORI = tuple(slot.chiave for slot in SLOT if slot.obbligatorio)

# Sotto qualche watt la potenza e' rumore di misura: nessun verso.
SOGLIA_W = 5
# Per proporre la convenzione servono valori chiari: una differenza di almeno
# 100 W fra produzione e consumo, e uno scambio di almeno 50 W.
SOGLIA_PROPOSTA_BILANCIO = 100
SOGLIA_PROPOSTA_SCAMBIO = 50

_NON_VALIDI = {"unknown", "unavailable", "none", ""}


# -----------------------------------------------------------------------------
# Configurazione
# -----------------------------------------------------------------------------
def _dividi(entity_id: str) -> tuple[str, str]:
    dominio, _, oggetto = entity_id.partition(".")
    return dominio, oggetto


def proposte(entity_ids: Iterable[str], escludi: Iterable[str] = ()) -> dict[str, str]:
    """Le entita' che sembrano quelle giuste per ogni voce, riconosciute dal nome.

    Fra piu' candidati vince quello con lo stesso prefisso della produzione
    (quasi certamente lo stesso misuratore), poi l'ordine alfabetico.
    """
    esclusi = set(escludi)
    tutte = sorted(e for e in entity_ids if "." in e and e not in esclusi)
    scelte: dict[str, str] = {}
    prefisso = ""
    for slot in SLOT:
        candidati = [
            e
            for e in tutte
            if _dividi(e)[0] in slot.domini and re.search(slot.cerca, _dividi(e)[1])
        ]
        if not candidati:
            continue
        if prefisso:
            candidati.sort(key=lambda e: (not _dividi(e)[1].startswith(prefisso), e))
        scelta = candidati[0]
        scelte[slot.chiave] = scelta
        if slot.chiave == "produzione":
            oggetto = _dividi(scelta)[1]
            trovato = re.search(slot.cerca, oggetto)
            prefisso = oggetto[: trovato.start()] if trovato else ""
    return scelte


def entita_da_modulo(dati: Mapping[str, Any]) -> dict[str, str]:
    """Le entita' scelte nel modulo, tolte dalle sezioni e senza i campi vuoti."""
    entita: dict[str, str] = {}
    for sezione in SEZIONI:
        for chiave, valore in (dati.get(sezione) or {}).items():
            if chiave in CHIAVI and isinstance(valore, str) and valore.strip():
                entita[chiave] = valore.strip()
    return entita


def errori_entita(entita: Mapping[str, str]) -> dict[str, str]:
    """Gli errori del modulo, nel formato di Home Assistant (vuoto se va bene)."""
    if any(chiave not in entita for chiave in OBBLIGATORI):
        return {"base": "manca_produzione"}
    valori = list(entita.values())
    if len(valori) != len(set(valori)):
        return {"base": "entita_ripetuta"}
    return {}


def rinomina(entita: Mapping[str, str], vecchio: str, nuovo: str) -> dict[str, str] | None:
    """Le entita' con un id rinominato, o None se il rinominato non e' fra le nostre."""
    if not vecchio or not nuovo or vecchio == nuovo or vecchio not in entita.values():
        return None
    return {chiave: (nuovo if valore == vecchio else valore) for chiave, valore in entita.items()}


# -----------------------------------------------------------------------------
# Valori
# -----------------------------------------------------------------------------
def numero(stato: str | None) -> float | None:
    """Il numero di uno stato grezzo, o None se non c'e' o non e' un numero."""
    if stato is None:
        return None
    testo = str(stato).strip()
    if testo.lower() in _NON_VALIDI:
        return None
    try:
        valore = float(testo.replace(",", "."))
    except ValueError:
        return None
    return valore if valore == valore and abs(valore) != float("inf") else None


def verso_rete(scambio: str | None, convenzione: str) -> str | None:
    """Immissione, prelievo o fermo; None se lo scambio non si legge."""
    valore = numero(scambio)
    if valore is None:
        return None
    if abs(valore) <= SOGLIA_W:
        return "fermo"
    immette = valore > 0
    if convenzione == PRELIEVO_POSITIVO:
        immette = not immette
    return "immissione" if immette else "prelievo"


def verso_batteria(potenza: str | None, convenzione: str) -> str | None:
    """Carica, scarica o fermo; None se la potenza non si legge."""
    valore = numero(potenza)
    if valore is None:
        return None
    if abs(valore) <= SOGLIA_W:
        return "fermo"
    carica = valore > 0
    if convenzione == SCARICA_POSITIVA:
        carica = not carica
    return "carica" if carica else "scarica"


def autoconsumo(letture: Mapping[str, str | None], convenzione: str) -> float | None:
    """La quota di produzione che non finisce in rete, in percento (al decimo).

    Se lo scambio con la rete e' collegato si calcola da quello: e' la
    definizione giusta anche con la batteria, perche' l'energia che la carica
    non esce di casa. Senza scambio si ripiega sul consumo (min fra produzione
    e consumo), che con una batteria sottostima. Una fonte collegata ma non
    leggibile non passa la parola all'altra: il valore resta sconosciuto.
    Di notte (produzione zero) l'autoconsumo non ha senso: None.
    """
    produzione = numero(letture.get("produzione"))
    if produzione is None or produzione <= 0:
        return None

    if "scambio_rete" in letture:
        scambio = numero(letture["scambio_rete"])
        if scambio is None:
            return None
        immissione = -scambio if convenzione == PRELIEVO_POSITIVO else scambio
        quota = (produzione - max(0.0, immissione)) / produzione
    elif "consumo" in letture:
        consumo = numero(letture["consumo"])
        if consumo is None:
            return None
        quota = min(produzione, max(0.0, consumo)) / produzione
    else:
        return None
    return round(max(0.0, min(1.0, quota)) * 100, 1)


def convenzione_proposta(
    produzione: str | None, consumo: str | None, scambio: str | None
) -> str | None:
    """La convenzione del contatore, dedotta dai valori di adesso, se sono chiari.

    Senza batteria lo scambio con la rete e' produzione meno consumo. Se ha lo
    stesso segno, il positivo e' l'immissione; se ha il segno opposto, e' il
    prelievo. Con valori troppo piccoli (o mancanti) non si propone nulla.
    """
    p, c, s = numero(produzione), numero(consumo), numero(scambio)
    if p is None or c is None or s is None:
        return None
    bilancio = p - c
    if abs(bilancio) < SOGLIA_PROPOSTA_BILANCIO or abs(s) < SOGLIA_PROPOSTA_SCAMBIO:
        return None
    return IMMISSIONE_POSITIVA if (bilancio > 0) == (s > 0) else PRELIEVO_POSITIVO
