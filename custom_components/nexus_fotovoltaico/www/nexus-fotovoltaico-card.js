/**
 * Nexus Fotovoltaico — card del sinottico animato.
 *
 * Pannelli, inverter, casa, rete e (se c'e') accumulo: il flusso in continua
 * va con la produzione, quello in alternata col consumo, la rete cambia verso
 * e colore fra prelievo e immissione.
 *
 * La card non si configura con le entita': legge il sensore «Mappa impianto»
 * dell'integrazione, dove stanno le entita' collegate, le opzioni e i valori
 * calcolati (verso della rete e della batteria, autoconsumo). Il disegno sta dentro la card:
 * scala con la plancia, segue il tema chiaro o scuro, e le animazioni vanno
 * alla velocita' che dicono i sensori.
 *
 * Le funzioni di calcolo sono esportate e si provano a tavolino: tests/test_card.mjs
 */

const VERSIONE_CARD = "1.1.0";
const DOMINIO = "nexus_fotovoltaico";
const RUOLO_MAPPA = "mappa_fotovoltaico";
const NOME_INTEGRAZIONE = "Nexus Fotovoltaico";
const DESCRIZIONE_CARD = "Fotovoltaico animato: produzione, consumo, rete e accumulo si muovono con i valori veri.";

// -----------------------------------------------------------------------------
// Logica: tutto cio' che si puo' sbagliare in silenzio, e che si prova da solo
// -----------------------------------------------------------------------------
const NON_VALIDI = new Set(["unknown", "unavailable", "none", ""]);

/** Il numero di uno stato di Home Assistant, o null se non e' un numero. */
export function numero(stato) {
  if (stato === null || stato === undefined) return null;
  const grezzo = typeof stato === "object" ? stato.state : stato;
  if (grezzo === null || grezzo === undefined) return null;
  const testo = String(grezzo).trim();
  if (NON_VALIDI.has(testo.toLowerCase())) return null;
  const valore = Number(testo.replace(",", "."));
  return Number.isFinite(valore) ? valore : null;
}

/** Vero se lo stato c'e' ed e' utilizzabile (non sconosciuto, non non-disponibile). */
export function valido(stato) {
  if (!stato || stato.state === undefined) return false;
  return !NON_VALIDI.has(String(stato.state).trim().toLowerCase());
}

/** Vero se un binario e' acceso. */
export function acceso(stato) {
  return Boolean(stato) && String(stato.state).toLowerCase() === "on";
}

// Un ciclo di tratteggio nel disegno: trattino 18 + spazio 26 unita'.
export const PERIODO_TRATTEGGIO = 44;
const VELOCITA_MINIMA = 20; // unita' del disegno al secondo, a impianto appena acceso
const VELOCITA_MASSIMA = 150; // a fondo scala

/**
 * Quanto conta il valore rispetto al fondo scala: 0 (fermo) .. 1 (pieno).
 * Oltre il fondo scala resta 1: il disegno non puo' andare piu' veloce del vero.
 */
export function frazione(valore, riferimento, soglia = 0) {
  const v = Math.abs(numero(valore) ?? NaN);
  if (!Number.isFinite(v) || v <= soglia) return 0;
  const rif = Math.abs(Number(riferimento)) || 1;
  return Math.min(v / rif, 1);
}

/**
 * La durata di un ciclo di tratteggio, in secondi, o null se il flusso e' fermo.
 * Piu' il valore e' alto, piu' il ciclo e' breve: i trattini corrono.
 */
export function durataFlusso(valore, riferimento, soglia = 0) {
  const f = frazione(valore, riferimento, soglia);
  if (f === 0) return null;
  const velocita = VELOCITA_MINIMA + (VELOCITA_MASSIMA - VELOCITA_MINIMA) * f;
  return Math.round((PERIODO_TRATTEGGIO / velocita) * 1000) / 1000;
}


// -----------------------------------------------------------------------------
// Stile: colori del tema, animazioni, e il rispetto di chi non vuole movimento
// -----------------------------------------------------------------------------
const STILE = `
:host { display: block; }
ha-card { overflow: hidden; }
.testata {
  padding: 14px 18px 2px;
  font-size: var(--ha-card-header-font-size, 22px);
  font-weight: 500;
  line-height: 1.2;
  color: var(--ha-card-header-color, var(--primary-text-color));
}
.corpo { padding: 8px 8px 10px; }
svg { display: block; width: 100%; height: auto; }

.tessere { display: flex; flex-wrap: wrap; gap: 8px; padding: 2px 10px 6px; }
.tessere:empty { display: none; }
.tessera {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 5px 12px; border-radius: 999px;
  font-size: 13px; font-weight: 600; line-height: 1.3;
  background: var(--ns-tessera-fondo, rgba(86,97,111,0.10));
  color: var(--ns-tessera-testo, #56616F);
  border: 1px solid var(--ns-tessera-bordo, rgba(86,97,111,0.22));
}
.tessera.avviso { --ns-tessera-fondo: rgba(222,74,81,0.12); --ns-tessera-testo: #C93C43; --ns-tessera-bordo: rgba(222,74,81,0.35); }
.tessera.freddo { --ns-tessera-fondo: rgba(60,132,198,0.12); --ns-tessera-testo: #2F6FA8; --ns-tessera-bordo: rgba(60,132,198,0.35); }
.tessera.caldo  { --ns-tessera-fondo: rgba(227,155,50,0.14); --ns-tessera-testo: #B7761C; --ns-tessera-bordo: rgba(227,155,50,0.38); }
.tessera.buono  { --ns-tessera-fondo: rgba(46,158,107,0.12); --ns-tessera-testo: #2E9E6B; --ns-tessera-bordo: rgba(46,158,107,0.35); }
.tessera.allarme { animation: ns-pulsa 1.8s ease-in-out infinite; }

.scena {
  --ns-fondo: #F4F8FC;
  --ns-riquadro: #FFFFFF;
  --ns-bordo: #E1E6EC;
  --ns-testo: #1F2933;
  --ns-etichetta: #56616F;
  --ns-metallo-chiaro: #FFFFFF;
  --ns-metallo: #E9EDF2;
  --ns-metallo-scuro: #DCE2E9;
  --ns-interno: #EEF2F6;
  --ns-bordo-metallo: #C5CED8;
  --ns-linea: #8C98A5;
  --ns-muro: #F1F4F8;
  --ns-vetro: #E3EDF7;
}
.scena.scuro {
  --ns-fondo: #151B22;
  --ns-riquadro: #1E262F;
  --ns-bordo: #2E3945;
  --ns-testo: #E8ECF1;
  --ns-etichetta: #9AA5B1;
  --ns-metallo-chiaro: #2B343E;
  --ns-metallo: #232B34;
  --ns-metallo-scuro: #1B222A;
  --ns-interno: #273039;
  --ns-bordo-metallo: #3A4653;
  --ns-linea: #6B7A89;
  --ns-muro: #222A33;
  --ns-vetro: #26313D;
}

.avviso-mappa { padding: 18px 20px; color: var(--secondary-text-color, #56616F); line-height: 1.5; }
.riquadro { cursor: pointer; }
.riquadro .sfondo { transition: stroke 0.15s ease; }
.riquadro:hover .sfondo { stroke: var(--ns-linea); }
.riquadro[hidden] { display: none; }

.flusso { stroke-dasharray: 18 26; stroke-linecap: round; opacity: 0; }
.flusso.in-moto { opacity: 1; animation: ns-scorri 1.2s linear infinite; }
.flusso.contro.in-moto { animation-direction: reverse; }
@keyframes ns-scorri { to { stroke-dashoffset: -${PERIODO_TRATTEGGIO}; } }

.ventola { transform-box: fill-box; transform-origin: center; }
.ventola.in-moto { animation: ns-gira 1.2s linear infinite; }
@keyframes ns-gira { to { transform: rotate(360deg); } }

.raggi { transform-box: fill-box; transform-origin: center; }
.raggi.in-moto { animation: ns-gira 40s linear infinite; }

.respira.in-moto { animation: ns-respira 2.6s ease-in-out infinite; }
@keyframes ns-respira { 0%, 100% { opacity: 0.45; } 50% { opacity: 1; } }
@keyframes ns-pulsa { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }

.spia.acceso { animation: ns-pulsa 2.2s ease-in-out infinite; }

@media (prefers-reduced-motion: reduce) {
  .flusso.in-moto, .ventola.in-moto, .raggi.in-moto, .respira.in-moto,
  .spia.acceso, .tessera.allarme { animation: none; }
  .respira.in-moto { opacity: 1; }
}
.senza-moto .flusso.in-moto, .senza-moto .ventola.in-moto, .senza-moto .raggi.in-moto,
.senza-moto .respira.in-moto, .senza-moto .spia.acceso { animation: none; }
.senza-moto .respira.in-moto { opacity: 1; }
`;

// -----------------------------------------------------------------------------
// Pezzi di disegno comuni
// -----------------------------------------------------------------------------
const DEFS_COMUNI = `
  <linearGradient id="ns-lamiera" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" style="stop-color:var(--ns-metallo-chiaro)"/>
    <stop offset="1" style="stop-color:var(--ns-metallo)"/>
  </linearGradient>
  <filter id="ns-ombra" x="-20%" y="-20%" width="140%" height="160%">
    <feDropShadow dx="0" dy="3" stdDeviation="5" flood-color="#1F2933" flood-opacity="0.09"/>
  </filter>
  <g id="ns-freccia">
    <path d="M-6 -8 L4 0 L-6 8" fill="none" stroke="#FFFFFF" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"/>
  </g>`;

/** Un riquadro di valore: etichetta in alto, numero sotto, tutto cliccabile. */
function riquadro({ slot, x, y, larghezza, altezza, etichetta, colore, coloreEtichetta, piccolo }) {
  const dimEtichetta = piccolo ? 19 : 24;
  const dimValore = piccolo ? 27 : 34;
  const baseEtichetta = y + (piccolo ? 30 : 36);
  const baseValore = y + (piccolo ? 66 : 78);
  return `
  <g class="riquadro" data-slot="${slot}">
    <rect class="sfondo" x="${x}" y="${y}" width="${larghezza}" height="${altezza}" rx="16"
          fill="var(--ns-riquadro)" stroke="var(--ns-bordo)" stroke-width="2" filter="url(#ns-ombra)"/>
    <rect x="${x}" y="${y + 16}" width="6" height="${altezza - 32}" rx="3" fill="${colore}"/>
    <text x="${x + 22}" y="${baseEtichetta}" font-size="${dimEtichetta}" font-weight="700"
          letter-spacing="1.2" fill="${coloreEtichetta || colore}">${etichetta}</text>
    <text class="valore" data-valore="${slot}" x="${x + 22}" y="${baseValore}" font-size="${dimValore}"
          font-weight="700" fill="var(--ns-testo)" data-dim="${dimValore}" data-min="${piccolo ? 13 : 15}"
          data-spazio="${larghezza - 40}">&#8212;</text>
  </g>`;
}

// -----------------------------------------------------------------------------
// Scena: fotovoltaico (inverter, casa, rete, batteria)
// -----------------------------------------------------------------------------
const PANNELLO_D = "M18 0 H102 L84 62 H0 Z";
const POSTI_PANNELLI = [
  [62, 90],
  [154, 90],
  [246, 90],
  [44, 158],
  [136, 158],
  [228, 158],
];
const DC_D = "M334 200 H430";
const AC_D = "M570 200 H716";
const RETE_D = "M635 200 V560";
const BATTERIA_D = "M500 266 V340";

function raggiSole() {
  let disegno = "";
  for (let i = 0; i < 8; i += 1) {
    const angolo = (i * Math.PI) / 4;
    const x1 = Math.round(Math.cos(angolo) * 26 * 10) / 10;
    const y1 = Math.round(Math.sin(angolo) * 26 * 10) / 10;
    const x2 = Math.round(Math.cos(angolo) * 34 * 10) / 10;
    const y2 = Math.round(Math.sin(angolo) * 34 * 10) / 10;
    disegno += `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}"/>`;
  }
  return disegno;
}

function scenaFotovoltaico(conBatteria) {
  const pannelli = POSTI_PANNELLI.map(([x, y]) => `<use href="#ns-pannello" transform="translate(${x} ${y})"/>`).join("\n  ");
  const lucidi = POSTI_PANNELLI.map(
    ([x, y]) => `<path class="lucido" transform="translate(${x} ${y})" d="${PANNELLO_D}" fill="#FFFFFF" opacity="0"/>`
  ).join("\n  ");

  const batteria = conBatteria
    ? `
  <!-- Accumulo: c'e' solo se e' stato configurato -->
  <g data-blocco="batteria">
    <path d="${BATTERIA_D}" fill="none" stroke="var(--ns-linea)" stroke-width="14" stroke-linecap="round"/>
    <path d="${BATTERIA_D}" fill="none" stroke="var(--ns-bordo-metallo)" stroke-width="4" opacity="0.6" stroke-linecap="round"/>
    <path class="flusso" data-flusso="batteria" d="${BATTERIA_D}" fill="none" stroke="#FFFFFF" stroke-width="8"/>
    <rect x="480" y="328" width="40" height="14" rx="5" fill="var(--ns-bordo-metallo)"/>
    <rect x="425" y="340" width="150" height="212" rx="16" fill="url(#ns-lamiera)" stroke="var(--ns-bordo-metallo)" stroke-width="3"/>
    <rect data-livello="soc" x="437" y="540" width="126" height="0" rx="8" fill="#2E9E6B" opacity="0.85"/>
    <text data-valore="soc" x="500" y="458" text-anchor="middle" font-size="40" font-weight="700"
          fill="var(--ns-testo)" paint-order="stroke" stroke="var(--ns-metallo-chiaro)" stroke-width="7"
          stroke-linejoin="round" data-dim="40" data-min="18" data-spazio="130">&#8212;</text>
    <text x="500" y="590" text-anchor="middle" font-size="22" font-weight="700" letter-spacing="1.5" fill="var(--ns-etichetta)">ACCUMULO</text>
    ${riquadro({ slot: "batteria", x: 400, y: 610, larghezza: 176, altezza: 84, etichetta: "BATTERIA", colore: "#2E9E6B", piccolo: true })}
  </g>`
    : "";

  return `
<svg viewBox="0 0 1000 800" preserveAspectRatio="xMidYMid meet" xmlns="http://www.w3.org/2000/svg"
     font-family="var(--ha-font-family-body, Roboto, system-ui, sans-serif)">
  <defs>
    ${DEFS_COMUNI}
    <linearGradient id="ns-cella" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#2F6DB0"/>
      <stop offset="1" stop-color="#1B3F6B"/>
    </linearGradient>
    <g id="ns-pannello">
      <path d="${PANNELLO_D}" fill="url(#ns-cella)" stroke="var(--ns-bordo-metallo)" stroke-width="3" stroke-linejoin="round"/>
      <path d="M46 0 L28 62 M74 0 L56 62 M9 31 H93" stroke="#FFFFFF" stroke-width="2" opacity="0.35"/>
    </g>
  </defs>

  <rect width="1000" height="800" rx="12" fill="var(--ns-fondo)"/>

  <!-- Linee: continua dal fotovoltaico (ambra), alternata verso casa, rete in verticale -->
  <g fill="none" stroke-linecap="round" stroke-linejoin="round">
    <path d="${DC_D}" stroke="#E39B32" stroke-width="16"/>
    <path d="${DC_D}" stroke="#FFD08A" stroke-width="4" opacity="0.6"/>
    <path class="flusso" data-flusso="dc" d="${DC_D}" stroke="#FFF1DC" stroke-width="9"/>
    <path d="${AC_D}" stroke="#6B7A89" stroke-width="16"/>
    <path d="${AC_D}" stroke="#AEBBC8" stroke-width="4" opacity="0.6"/>
    <path class="flusso" data-flusso="ac" d="${AC_D}" stroke="#FFFFFF" stroke-width="9"/>
    <path d="${RETE_D}" stroke="#9AA5B1" stroke-width="16"/>
    <path data-linea="rete" d="${RETE_D}" stroke="#D3DAE2" stroke-width="4" opacity="0.6"/>
    <path class="flusso" data-flusso="rete" d="${RETE_D}" stroke="#FFFFFF" stroke-width="9"/>
  </g>
  <use href="#ns-freccia" transform="translate(384 200)"/>
  <use href="#ns-freccia" transform="translate(600 200)"/>
  <use href="#ns-freccia" transform="translate(682 200)"/>
  <circle cx="635" cy="200" r="11" fill="#6B7A89"/>
  <g data-verso="immissione" opacity="0">
    <circle cx="635" cy="430" r="21" fill="#2E9E6B"/>
    <path d="M635 419 V441 M626 432 L635 441 L644 432" fill="none" stroke="#FFFFFF" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>
  </g>
  <g data-verso="prelievo" opacity="0">
    <circle cx="635" cy="430" r="21" fill="#DE4A51"/>
    <path d="M635 441 V419 M626 428 L635 419 L644 428" fill="none" stroke="#FFFFFF" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>
  </g>

  <!-- Sole e fotovoltaico -->
  <g transform="translate(48 46)">
    <g class="raggi" data-raggi="sole" stroke="#F6C453" stroke-width="5" stroke-linecap="round" opacity="0.35">
      <circle r="36" fill="none" stroke="none"/>
      ${raggiSole()}
    </g>
    <circle data-sole="disco" r="19" fill="#F6C453" opacity="0.35"/>
  </g>
  <text x="215" y="62" text-anchor="middle" font-size="25" font-weight="700" letter-spacing="1.5" fill="var(--ns-etichetta)">FOTOVOLTAICO</text>
  <ellipse cx="186" cy="262" rx="150" ry="11" fill="#1F2933" opacity="0.07"/>
  <g stroke="var(--ns-bordo-metallo)" stroke-width="6" stroke-linecap="round">
    <line x1="88" y1="222" x2="88" y2="256"/>
    <line x1="284" y1="222" x2="284" y2="256"/>
  </g>
  ${pannelli}
  ${lucidi}

  <!-- Inverter -->
  <text x="500" y="90" text-anchor="middle" font-size="25" font-weight="700" letter-spacing="1.5" fill="var(--ns-etichetta)">INVERTER</text>
  <ellipse cx="500" cy="276" rx="80" ry="9" fill="#1F2933" opacity="0.07"/>
  <rect x="430" y="110" width="140" height="156" rx="16" fill="url(#ns-lamiera)" stroke="var(--ns-bordo-metallo)" stroke-width="3"/>
  <rect x="452" y="132" width="96" height="46" rx="7" fill="#26313D"/>
  <path d="M462 162 l10 -12 l8 8 l12 -14 l10 10 l10 -6 l14 10" fill="none" stroke="#7FD1A8" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
  <circle class="spia" data-spia="inverter" cx="462" cy="198" r="5" fill="var(--ns-bordo-metallo)"/>
  <g stroke="var(--ns-bordo-metallo)" stroke-width="5" stroke-linecap="round">
    <line x1="452" y1="220" x2="548" y2="220"/>
    <line x1="452" y1="236" x2="548" y2="236"/>
    <line x1="452" y1="252" x2="548" y2="252"/>
  </g>

  <!-- Casa -->
  <text x="815" y="62" text-anchor="middle" font-size="25" font-weight="700" letter-spacing="1.5" fill="var(--ns-etichetta)">CASA</text>
  <path d="M700 180 L815 92 L930 180 Z" fill="var(--ns-muro)" stroke="var(--ns-linea)" stroke-width="4" stroke-linejoin="round"/>
  <rect x="716" y="172" width="198" height="118" rx="6" fill="var(--ns-metallo-chiaro)" stroke="var(--ns-bordo-metallo)" stroke-width="3"/>
  <rect data-respira="finestra1" x="742" y="198" width="44" height="40" rx="4" fill="var(--ns-vetro)" stroke="var(--ns-bordo-metallo)" stroke-width="2"/>
  <rect data-respira="finestra2" x="844" y="198" width="44" height="40" rx="4" fill="var(--ns-vetro)" stroke="var(--ns-bordo-metallo)" stroke-width="2"/>
  <rect x="797" y="224" width="36" height="66" rx="4" fill="var(--ns-metallo)" stroke="var(--ns-bordo-metallo)" stroke-width="2"/>

  <!-- Contatore e rete -->
  <rect x="598" y="330" width="74" height="52" rx="9" fill="var(--ns-riquadro)" stroke="var(--ns-bordo-metallo)" stroke-width="3"/>
  <text x="635" y="363" text-anchor="middle" font-size="18" font-weight="700" fill="var(--ns-etichetta)">kWh</text>
  <g stroke="var(--ns-linea)" stroke-width="5" stroke-linecap="round" stroke-linejoin="round" fill="none">
    <path d="M603 760 L627 564 M667 760 L643 564"/>
    <path d="M581 592 H689 M593 632 H677"/>
    <path d="M622 608 L656 652 L612 696 L660 736 M648 608 L614 652 L658 696 L610 736"/>
    <path d="M627 564 H643"/>
  </g>
  <circle cx="581" cy="592" r="5" fill="var(--ns-linea)"/>
  <circle cx="689" cy="592" r="5" fill="var(--ns-linea)"/>
  <text x="635" y="792" text-anchor="middle" font-size="22" font-weight="700" letter-spacing="1.5" fill="var(--ns-etichetta)">RETE</text>
${batteria}

  ${riquadro({ slot: "produzione", x: 40, y: 300, larghezza: 260, altezza: 96, etichetta: "PRODUZIONE", colore: "#E39B32", coloreEtichetta: "#C9801F" })}
  ${riquadro({ slot: "giornaliera", x: 40, y: 412, larghezza: 260, altezza: 96, etichetta: "OGGI", colore: "#E39B32", coloreEtichetta: "#C9801F" })}
  ${riquadro({ slot: "scambio_rete", x: 40, y: 560, larghezza: 290, altezza: 96, etichetta: "SCAMBIO RETE", colore: "#9AA5B1", coloreEtichetta: "var(--ns-etichetta)" })}
  ${riquadro({ slot: "consumo", x: 700, y: 330, larghezza: 260, altezza: 96, etichetta: "CONSUMO", colore: "#6B7A89", coloreEtichetta: "var(--ns-etichetta)" })}
  ${riquadro({ slot: "prelevata", x: 700, y: 560, larghezza: 260, altezza: 96, etichetta: "PRELEVATA", colore: "#DE4A51", coloreEtichetta: "#C93C43" })}
  ${riquadro({ slot: "immessa", x: 700, y: 672, larghezza: 260, altezza: 96, etichetta: "IMMESSA", colore: "#2E9E6B" })}
  <text x="185" y="700" text-anchor="middle" font-size="20" fill="var(--ns-etichetta)"><tspan fill="#C93C43" font-weight="700">&#8722;</tspan> prelievo  &#183;  <tspan fill="#2E9E6B" font-weight="700">+</tspan> immissione</text>
</svg>`;
}

// -----------------------------------------------------------------------------
// Aiuti sul disegno
// -----------------------------------------------------------------------------
function muovi(nodo, durata) {
  if (!nodo) return;
  if (durata) {
    nodo.style.animationDuration = `${durata}s`;
    nodo.classList.add("in-moto");
  } else {
    nodo.classList.remove("in-moto");
    nodo.style.removeProperty("animation-duration");
  }
}

function perDato(radice, dato) {
  const mappa = {};
  radice.querySelectorAll(`[data-${dato}]`).forEach((n) => {
    mappa[n.dataset[dato]] = n;
  });
  return mappa;
}

function riferimenti(radice) {
  return {
    valori: perDato(radice, "valore"),
    riquadri: perDato(radice, "slot"),
    flussi: perDato(radice, "flusso"),
    ventole: perDato(radice, "ventola"),
    respiri: perDato(radice, "respira"),
    spie: perDato(radice, "spia"),
    acque: perDato(radice, "acqua"),
    versi: perDato(radice, "verso"),
    livelli: perDato(radice, "livello"),
    sole: perDato(radice, "sole"),
    raggi: perDato(radice, "raggi"),
    blocchi: perDato(radice, "blocco"),
    lucidi: Array.from(radice.querySelectorAll(".lucido")),
    finestre: Array.from(radice.querySelectorAll('[data-respira^="finestra"]')),
  };
}

/**
 * Scrive il valore nel riquadro. Restituisce false se non si e' potuto misurare.
 *
 * Il disegno scala con la card, quindi su un telefono un numero da 34 unita'
 * arriverebbe a una decina di pixel. `unitaPerPixel` (quante unita' del disegno
 * stanno in un pixel) fa crescere il carattere quel tanto che basta a non
 * scendere sotto la soglia leggibile; poi, se non ci sta nel riquadro, si
 * rimpicciolisce comunque.
 */
function scriviValore(nodo, testo, unitaPerPixel = 0) {
  if (!nodo) return;
  nodo.textContent = testo;
  const minimo = Number(nodo.dataset.min) || 0;
  const base = Math.max(Number(nodo.dataset.dim) || 34, unitaPerPixel > 0 ? minimo * unitaPerPixel : 0);
  const spazio = Number(nodo.dataset.spazio) || 200;
  nodo.setAttribute("font-size", String(Math.round(base * 10) / 10));
  let larghezza = 0;
  try {
    larghezza = nodo.getComputedTextLength();
  } catch (errore) {
    larghezza = 0;
  }
  // Finche' la card non e' a video il testo non si puo' misurare: si dice a chi
  // chiama che questa misura non vale, e si riprova al primo disegno utile.
  if (larghezza <= 0) return testo === "" ;
  if (larghezza > spazio) {
    nodo.setAttribute("font-size", String(Math.max(13, Math.floor((base * spazio) / larghezza))));
  }
  return true;
}


// -----------------------------------------------------------------------------
// Come i valori muovono il disegno
// -----------------------------------------------------------------------------
const RIFERIMENTO_PREDEFINITO = 3000; // W di fondo scala per la velocita' del flusso

function conBatteria(mappa) {
  const entita = (mappa && mappa.entita) || {};
  return Boolean(entita.batteria || entita.soc);
}

function firmaScena(mappa) {
  return `fotovoltaico|${conBatteria(mappa)}`;
}

function disegnaScena(mappa) {
  return scenaFotovoltaico(conBatteria(mappa));
}

function aggiornaScena(ctx) {
  const { rif } = ctx;
  const riferimento = ctx.riferimento();
  const produzione = ctx.num("produzione");
  const consumo = ctx.num("consumo");

  muovi(rif.flussi.dc, durataFlusso(produzione, riferimento, 0));
  muovi(rif.flussi.ac, durataFlusso(consumo, riferimento, 0));

  // Sole e pannelli: piu' produzione, piu' luce. Di notte restano spenti.
  const luce = frazione(produzione, riferimento, 0);
  const disco = rif.sole.disco;
  const raggi = rif.raggi.sole;
  if (disco) disco.setAttribute("opacity", (0.3 + 0.7 * Math.min(luce * 2.5, 1)).toFixed(2));
  if (raggi) {
    raggi.setAttribute("opacity", (0.25 + 0.75 * Math.min(luce * 2.5, 1)).toFixed(2));
    muovi(raggi, luce > 0 ? 40 : null);
  }
  rif.lucidi.forEach((l) => l.setAttribute("opacity", (0.3 * Math.min(luce * 1.6, 1)).toFixed(3)));

  // Finestre di casa: si scaldano con il consumo, senza lampeggiare.
  const quotaConsumo = frazione(consumo, riferimento, 0);
  rif.finestre.forEach((f) => {
    f.setAttribute("fill", quotaConsumo > 0 ? "#FFE9B8" : "var(--ns-vetro)");
    f.setAttribute("opacity", quotaConsumo > 0 ? (0.45 + 0.55 * Math.min(quotaConsumo * 2, 1)).toFixed(2) : "1");
  });

  // Verso della rete e della batteria li decide l'integrazione, con la
  // convenzione scelta in configurazione: la card non rifa' il conto.
  const verso = ctx.derivata("verso_rete") || "fermo";
  const scambio = ctx.num("scambio_rete");
  if (rif.versi.immissione) rif.versi.immissione.setAttribute("opacity", verso === "immissione" ? "1" : "0");
  if (rif.versi.prelievo) rif.versi.prelievo.setAttribute("opacity", verso === "prelievo" ? "1" : "0");
  const flussoRete = rif.flussi.rete;
  if (flussoRete) {
    flussoRete.classList.toggle("contro", verso === "prelievo");
    flussoRete.setAttribute("stroke", verso === "prelievo" ? "#FFD9DB" : "#CDF0DF");
  }
  muovi(flussoRete, verso === "fermo" ? null : durataFlusso(scambio, riferimento, 0));

  if (rif.blocchi.batteria) {
    const versoBat = ctx.derivata("verso_batteria") || "fermo";
    const flussoBat = rif.flussi.batteria;
    if (flussoBat) flussoBat.classList.toggle("contro", versoBat === "scarica");
    muovi(flussoBat, versoBat === "fermo" ? null : durataFlusso(ctx.num("batteria"), riferimento, 0));
    const soc = ctx.num("soc");
    const livello = rif.livelli.soc;
    if (livello) {
      const altezza = soc === null ? 0 : Math.round((Math.min(Math.max(soc, 0), 100) / 100) * 188);
      livello.setAttribute("height", String(altezza));
      livello.setAttribute("y", String(540 - altezza));
      livello.setAttribute("fill", versoBat === "scarica" ? "#E39B32" : "#2E9E6B");
    }
    if (versoBat === "carica") ctx.tessera("Batteria in carica", "buono");
    if (versoBat === "scarica") ctx.tessera("Batteria in scarica", "caldo");
  }

  if (verso === "immissione") ctx.tessera("Immissione in rete", "buono");
  if (verso === "prelievo") ctx.tessera("Prelievo dalla rete", "avviso");
  const quota = numero(ctx.derivata("autoconsumo"));
  if (quota !== null) ctx.tessera(`Autoconsumo ${Math.round(quota)}%`, quota >= 70 ? "buono" : "");

  const spia = rif.spie.inverter;
  if (spia) {
    const accesa = produzione !== null && produzione > 0;
    spia.setAttribute("fill", accesa ? "#2E9E6B" : "var(--ns-bordo-metallo)");
    spia.classList.toggle("acceso", accesa);
  }
}

// -----------------------------------------------------------------------------
// La card: tutto quello che serve lo legge dal sensore «Mappa impianto»
// -----------------------------------------------------------------------------
function testoSicuro(testo) {
  return String(testo).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
}

/** Il sensore «Mappa impianto» di questa integrazione, se in Home Assistant ce n'e' uno. */
export function trovaMappa(hass) {
  const stati = (hass && hass.states) || {};
  return Object.keys(stati).find((id) => stati[id].attributes && stati[id].attributes.ruolo === RUOLO_MAPPA) || "";
}

class NexusFotovoltaicoCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._firma = null;
    this._rif = null;
  }

  static getConfigElement() {
    return document.createElement("nexus-fotovoltaico-card-editor");
  }

  static getStubConfig(hass) {
    return { entity: trovaMappa(hass) };
  }

  setConfig(config) {
    if (!config || !config.entity) {
      throw new Error(`Indica il sensore «Mappa impianto» di ${NOME_INTEGRAZIONE}`);
    }
    this._config = { ...config };
    this._firma = null;
    this._firmaTessere = null;
    this._rif = null;
    this.shadowRoot.innerHTML = "";
    if (this._hass) this._aggiorna();
  }

  set hass(hass) {
    this._hass = hass;
    this._aggiorna();
  }

  getCardSize() {
    return 12;
  }

  getGridOptions() {
    return { columns: 12, min_columns: 6, rows: "auto" };
  }

  disconnectedCallback() {
    if (this._osservatore) this._osservatore.disconnect();
  }

  connectedCallback() {
    if (this._osservatore && this._scena) this._osservatore.observe(this._scena);
    // Appena attaccata la card ha una larghezza: i numeri si rimisurano subito,
    // senza aspettare un disegno che in una scheda in secondo piano non arriva.
    this._riscriviValori();
  }

  _mappa() {
    const stato = this._hass && this._config ? this._hass.states[this._config.entity] : null;
    if (!stato || !stato.attributes || stato.attributes.ruolo !== RUOLO_MAPPA) return null;
    return stato.attributes;
  }

  _entita() {
    const mappa = this._mappa();
    return (mappa && mappa.entita) || {};
  }

  _stato(slot) {
    const id = this._entita()[slot];
    if (!id || !this._hass) return null;
    const stato = this._hass.states[id];
    return valido(stato) ? stato : null;
  }

  _testo(slot) {
    const id = this._entita()[slot];
    if (!id) return "\u2014";
    const stato = this._hass ? this._hass.states[id] : null;
    if (!stato) return "assente";
    // Anche «non disponibile» e «sconosciuto» passano da Home Assistant: e' lui
    // che li traduce nella lingua giusta.
    if (typeof this._hass.formatEntityState === "function") {
      try {
        return this._hass.formatEntityState(stato);
      } catch (errore) {
        /* si continua col ripiego */
      }
    }
    if (!valido(stato)) return "\u2014";
    const unita = stato.attributes.unit_of_measurement;
    return unita ? `${stato.state} ${unita}` : String(stato.state);
  }

  _numeroTesto(valore, decimali) {
    const lingua = (this._hass && this._hass.locale && this._hass.locale.language) || "it";
    try {
      return Number(valore).toLocaleString(lingua, { minimumFractionDigits: decimali, maximumFractionDigits: decimali });
    } catch (errore) {
      return String(valore);
    }
  }

  _titolo(mappa) {
    if (this._config.title !== undefined && this._config.title !== null) return String(this._config.title);
    return (mappa && mappa.nome) || "";
  }

  _avviso(testo) {
    const firma = `avviso|${testo}`;
    if (this._firma === firma) return;
    if (this._osservatore) this._osservatore.disconnect();
    this._firma = firma;
    this._firmaTessere = null;
    this._rif = null;
    this._scena = null;
    this.shadowRoot.innerHTML = `<style>${STILE}</style><ha-card><div class="avviso-mappa">${testoSicuro(testo)}</div></ha-card>`;
  }

  _costruisci(mappa) {
    const titolo = this._titolo(mappa);
    const radice = this.shadowRoot;
    radice.innerHTML = `<style>${STILE}</style>
      <ha-card>
        ${titolo ? `<div class="testata">${testoSicuro(titolo)}</div>` : ""}
        <div class="corpo">
          <div class="scena">${disegnaScena(mappa)}</div>
          <div class="tessere"></div>
        </div>
      </ha-card>`;
    this._scena = radice.querySelector(".scena");
    this._tessere = radice.querySelector(".tessere");
    this._firmaTessere = null;
    this._rif = riferimenti(this._scena);
    Object.entries(this._rif.riquadri).forEach(([slot, nodo]) => {
      nodo.addEventListener("click", () => this._apri(slot));
    });
    if (this._osservatore) this._osservatore.disconnect();
    if (typeof ResizeObserver !== "undefined") {
      this._osservatore = new ResizeObserver(() => this._riscriviValori());
      this._osservatore.observe(this._scena);
    }
  }

  /** Quante unita' del disegno stanno in un pixel: 0 se la card non e' ancora a video. */
  _unitaPerPixel() {
    const larghezza = this._scena ? this._scena.clientWidth : 0;
    return larghezza > 0 ? 1000 / larghezza : 0;
  }

  _riscriviValori() {
    if (!this._rif || !this._config) return;
    const entita = this._entita();
    const scala = this._unitaPerPixel();
    let misurati = true;
    Object.entries(this._rif.riquadri).forEach(([slot, nodo]) => {
      const configurato = Boolean(entita[slot]);
      nodo.hidden = !configurato;
      if (configurato && !scriviValore(this._rif.valori[slot], this._testo(slot), scala)) misurati = false;
    });
    if (this._rif.valori.soc) {
      const testo = entita.soc ? this._testo("soc") : "\u2014";
      if (!scriviValore(this._rif.valori.soc, testo, scala)) misurati = false;
    }
    // Card non ancora a video: si riprova al disegno successivo, una volta sola.
    if (!misurati && !this._attesaMisura && typeof requestAnimationFrame === "function") {
      this._attesaMisura = true;
      requestAnimationFrame(() => {
        this._attesaMisura = false;
        this._riscriviValori();
      });
    }
  }

  _apri(slot) {
    const id = this._entita()[slot];
    if (!id) return;
    // Un'entita' ritirata dal gateway non ha piu' una finestra da aprire: il
    // dialogo verrebbe su vuoto e sembrerebbe un guasto della scheda.
    if (!this._hass || !this._hass.states[id]) return;
    this.dispatchEvent(new CustomEvent("hass-more-info", { detail: { entityId: id }, bubbles: true, composed: true }));
  }

  _aggiorna() {
    if (!this._config || !this._hass) return;
    const mappa = this._mappa();
    if (!mappa) {
      const stato = this._hass.states[this._config.entity];
      if (!stato) {
        this._avviso(`${this._config.entity} non esiste: controlla l'integrazione ${NOME_INTEGRAZIONE}.`);
      } else if (stato.attributes && stato.attributes.ruolo) {
        this._avviso(`${this._config.entity} non e' una mappa di ${NOME_INTEGRAZIONE}.`);
      } else {
        this._avviso(`Mappa non disponibile: l'integrazione ${NOME_INTEGRAZIONE} non e' caricata.`);
      }
      return;
    }

    const firma = `${firmaScena(mappa)}|${this._titolo(mappa)}`;
    if (firma !== this._firma) {
      this._firma = firma;
      this._costruisci(mappa);
    }

    this._scena.classList.toggle("scuro", Boolean(this._hass.themes && this._hass.themes.darkMode));
    this._scena.classList.toggle("senza-moto", this._config.animazioni === false);
    this._riscriviValori();

    const tessere = [];
    const opzioni = mappa.opzioni || {};
    const ctx = {
      hass: this._hass,
      mappa,
      rif: this._rif,
      entita: mappa.entita || {},
      stato: (slot) => this._stato(slot),
      num: (slot) => numero(this._stato(slot)),
      acceso: (slot) => acceso(this._stato(slot)),
      derivata: (nome) => {
        const derivate = mappa.derivate || {};
        return derivate[nome] === undefined ? null : derivate[nome];
      },
      riferimento: () => {
        const scelto = Number(opzioni.riferimento);
        return Number.isFinite(scelto) && scelto > 0 ? scelto : RIFERIMENTO_PREDEFINITO;
      },
      numeroTesto: (valore, decimali) => this._numeroTesto(valore, decimali),
      tessera: (testo, classe) => tessere.push({ testo, classe: classe || "" }),
    };

    try {
      aggiornaScena(ctx);
    } catch (errore) {
      console.error(`${NOME_INTEGRAZIONE}: disegno non aggiornato`, errore);
    }
    this._disegnaTessere(tessere);
  }

  _disegnaTessere(tessere) {
    const firma = tessere.map((t) => `${t.testo}|${t.classe}`).join("\u00A7");
    if (firma === this._firmaTessere) return;
    this._firmaTessere = firma;
    this._tessere.innerHTML = tessere
      .map((t) => `<span class="tessera ${t.classe}">${testoSicuro(t.testo)}</span>`)
      .join("");
  }
}

// -----------------------------------------------------------------------------
// Editor
// -----------------------------------------------------------------------------
const SCHEMA_EDITOR = [
  { name: "entity", required: true, selector: { entity: { integration: DOMINIO, domain: "sensor" } } },
  { name: "title", selector: { text: {} } },
  { name: "animazioni", selector: { boolean: {} } },
];
const ETICHETTE_EDITOR = {
  entity: "Mappa impianto",
  title: "Titolo (vuoto: il nome dato all'integrazione)",
  animazioni: "Animazioni",
};

class NexusFotovoltaicoCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = config;
    this._aggiorna();
  }

  set hass(hass) {
    this._hass = hass;
    this._aggiorna();
  }

  _aggiorna() {
    if (!this._config || !this._hass) return;
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.schema = SCHEMA_EDITOR;
      this._form.computeLabel = (voce) => ETICHETTE_EDITOR[voce.name] || voce.name;
      this._form.addEventListener("value-changed", (evento) => {
        const valore = { ...evento.detail.value };
        if (valore.animazioni !== false) delete valore.animazioni;
        if (!valore.title) delete valore.title;
        this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: valore }, bubbles: true, composed: true }));
      });
      this.appendChild(this._form);
    }
    this._form.hass = this._hass;
    this._form.data = { ...this._config, animazioni: this._config.animazioni !== false };
  }
}

// -----------------------------------------------------------------------------
// Registrazione: idempotente e non fatale
// -----------------------------------------------------------------------------
try {
  if (!customElements.get("nexus-fotovoltaico-card")) {
    customElements.define("nexus-fotovoltaico-card", NexusFotovoltaicoCard);
    customElements.define("nexus-fotovoltaico-card-editor", NexusFotovoltaicoCardEditor);
    window.customCards = window.customCards || [];
    window.customCards.push({
      type: "nexus-fotovoltaico-card",
      name: NOME_INTEGRAZIONE,
      description: DESCRIZIONE_CARD,
      preview: true,
      documentationURL: `https://github.com/Pacco24626/${DOMINIO}`,
    });
    console.info(
      `%c NEXUS-FOTOVOLTAICO-CARD %c ${VERSIONE_CARD} `,
      "color:#fff;background:#E07A2F;font-weight:700;",
      "color:#E07A2F;background:#FDF0E3;font-weight:700;"
    );
  }
} catch (errore) {
  console.error(`${NOME_INTEGRAZIONE}: registrazione della card non riuscita`, errore);
}

export { NexusFotovoltaicoCard, NexusFotovoltaicoCardEditor, VERSIONE_CARD, RUOLO_MAPPA, muovi, scriviValore };
