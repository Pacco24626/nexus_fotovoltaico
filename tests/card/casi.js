/**
 * I casi di prova della card: un finto Home Assistant con i valori veri
 * dell'impianto e il sensore «Mappa impianto» come lo scrive l'integrazione.
 * I valori calcolati (versi, autoconsumo) sono quelli che danno le prove Python
 * sugli stessi numeri.
 */

export const MAPPA = "sensor.fotovoltaico_mappa_impianto";

const FV = "sensor.nexus_t_energy_monitor_";
export const ENTITA = {
  produzione: `${FV}produzione_fotovoltaico`,
  consumo: `${FV}consumo_abitazione`,
  scambio_rete: `${FV}potenza_scambio_rete`,
  giornaliera: `${FV}produzione_giornaliera`,
  prelevata: `${FV}energia_prelevata_rete`,
  immessa: `${FV}energia_immessa_rete`,
};
export const ENTITA_BATTERIA = {
  ...ENTITA,
  batteria: `${FV}potenza_accumulo_batteria`,
  soc: `${FV}stato_carica_batteria_soc`,
};

const UNITA = {
  produzione: "W", consumo: "W", scambio_rete: "W", batteria: "W",
  giornaliera: "kWh", prelevata: "kWh", immessa: "kWh", soc: "%",
};

function stato(entity_id, state, attributes = {}) {
  return { entity_id, state: String(state), attributes };
}

export function stati(valori, derivate, { entita = ENTITA, nome = "Fotovoltaico", opzioni = {} } = {}) {
  const tutti = {};
  Object.entries(entita).forEach(([slot, id]) => {
    if (valori[slot] === undefined) return;
    tutti[id] = stato(id, valori[slot], { unit_of_measurement: UNITA[slot] });
  });
  tutti[MAPPA] = stato(MAPPA, Object.keys(entita).length, {
    ruolo: "mappa_fotovoltaico",
    nome,
    entita: { ...entita },
    opzioni: { riferimento: 3000, segno_rete: "immissione_positiva", segno_batteria: "carica_positiva", ...opzioni },
    derivate: { verso_rete: null, verso_batteria: null, autoconsumo: null, ...derivate },
  });
  return tutti;
}

export const CASI = {
  notte: {
    titolo: "Di notte si preleva (valori veri del 16/09)",
    stati: stati(
      { produzione: 46, consumo: 452, scambio_rete: -406, giornaliera: 0, prelevata: 4606.5, immessa: 1894.7 },
      { verso_rete: "prelievo", autoconsumo: 100.0 }
    ),
  },
  sole: {
    titolo: "Sole pieno, si immette",
    stati: stati(
      { produzione: 3240, consumo: 810, scambio_rete: 2430, giornaliera: 18.4, prelevata: 4606.5, immessa: 1912.1 },
      { verso_rete: "immissione", autoconsumo: 25.0 }
    ),
  },
  batteria: {
    titolo: "Con accumulo in carica",
    stati: stati(
      { produzione: 2150, consumo: 480, scambio_rete: 170, giornaliera: 11.2, prelevata: 4606.5, immessa: 1908.4, batteria: 1500, soc: 62 },
      { verso_rete: "immissione", verso_batteria: "carica", autoconsumo: 92.1 },
      { entita: ENTITA_BATTERIA }
    ),
  },
  scarno: {
    titolo: "Solo produzione e consumo",
    stati: stati(
      { produzione: 900, consumo: 1400 },
      { autoconsumo: 100.0 },
      { entita: { produzione: ENTITA.produzione, consumo: ENTITA.consumo }, nome: "Tetto" }
    ),
  },
};

export function fintoHass(tutti, scuro = false) {
  return {
    states: tutti,
    locale: { language: "it" },
    themes: { darkMode: scuro },
    formatEntityState: (st) => {
      const unita = st.attributes.unit_of_measurement;
      if (st.state === "unavailable") return "Non disponibile";
      const numero = Number(st.state);
      const testo = Number.isFinite(numero) ? numero.toLocaleString("it-IT") : st.state;
      return unita ? `${testo} ${unita}` : testo;
    },
  };
}
