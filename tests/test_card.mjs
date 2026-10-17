/**
 * Prove a tavolino dei calcoli della card: quelli che sbaglierebbero in
 * silenzio, senza che il disegno lo dia a vedere.
 *
 *     node tests/test_card.mjs
 *
 * La card e' fatta per il browser: qui si mettono al loro posto le poche cose
 * che cerca al caricamento, poi si importa il file vero (non una copia).
 * Il disegno si collauda in tests/card/prova_card.html.
 */

globalThis.HTMLElement = class {
  attachShadow() {
    return { innerHTML: "", querySelector: () => null, querySelectorAll: () => [] };
  }
};
const definite = {};
globalThis.customElements = { get: (n) => definite[n], define: (n, c) => { definite[n] = c; } };
globalThis.window = globalThis;
globalThis.document = { createElement: () => ({}) };
const registro = [];
console.info = (...righe) => registro.push(righe.join(" "));

const carta = await import("../custom_components/nexus_fotovoltaico/www/nexus-fotovoltaico-card.js");
const { numero, valido, acceso, frazione, durataFlusso, PERIODO_TRATTEGGIO, trovaMappa, RUOLO_MAPPA, VERSIONE_CARD } = carta;

let passate = 0;
const fallite = [];
function v(descrizione, condizione) {
  if (condizione) {
    passate += 1;
    console.log(`  ok   ${descrizione}`);
  } else {
    fallite.push(descrizione);
    console.log(`  NO   ${descrizione}`);
  }
}
const st = (state, attributes = {}) => ({ state: String(state), attributes });

console.log("\n1. Leggere gli stati");
v("un numero e' un numero", numero(st(48.5)) === 48.5);
v("la virgola non rovina il numero", numero("12,5") === 12.5);
v("«unavailable» non e' zero", numero(st("unavailable")) === null);
v("il testo non e' un numero", numero(st("acceso")) === null);
v("lo zero resta zero", numero(st(0)) === 0);
v("valido su un numero, non su «unknown»", valido(st(3)) && !valido(st("unknown")));
v("acceso solo su «on»", acceso(st("on")) && !acceso(st("off")));

console.log("\n2. Velocita' dei flussi");
v("a zero il flusso e' fermo, non lentissimo", durataFlusso(0, 100) === null);
v("senza lettura il flusso e' fermo", durataFlusso(st("unavailable"), 100) === null);
v("a fondo scala il ciclo e' il piu' breve", Math.abs(durataFlusso(100, 100) - PERIODO_TRATTEGGIO / 150) < 0.001);
v("oltre il fondo scala non accelera", durataFlusso(900, 100) === durataFlusso(100, 100));
v("piu' valore, ciclo piu' breve", durataFlusso(80, 100) < durataFlusso(10, 100));
v("il segno non cambia la velocita'", durataFlusso(-40, 100) === durataFlusso(40, 100));
v("la frazione si ferma a 1", frazione(300, 100) === 1);

console.log("\n3. Mappa e registrazione");
const hass = {
  states: {
    "sensor.altro": st(1, { ruolo: "mappa_di_altro" }),
    "sensor.mia_mappa": st(5, { ruolo: RUOLO_MAPPA }),
  },
};
v("trova la mappa di questa integrazione e non quella di un'altra", trovaMappa(hass) === "sensor.mia_mappa");
v("senza mappe: stringa vuota", trovaMappa({ states: {} }) === "");
v("ruolo della mappa", RUOLO_MAPPA === "mappa_fotovoltaico");
v("la card si registra col suo nome", Boolean(definite["nexus-fotovoltaico-card"]) && Boolean(definite["nexus-fotovoltaico-card-editor"]));
v("e si annuncia nel selettore delle card", window.customCards.some((c) => c.type === "nexus-fotovoltaico-card" && c.preview === true));
v("versione della card allineata al manifest", VERSIONE_CARD === "1.1.0");

console.log("\nVoci ritirate dal gateway");
{
  // Il clic su una voce apre la finestra informazioni di Home Assistant. Se
  // l'entita' e' stata ritirata quella finestra viene su vuota, e sembra un
  // guasto della card: meglio non aprirla.
  const Card = definite["nexus-fotovoltaico-card"];
  const scheda = Object.create(Card.prototype);
  scheda._hass = { states: { "sensor.viva": { entity_id: "sensor.viva", state: "1283", attributes: {} } } };
  scheda._entita = () => ({ produzione: "sensor.viva", giornaliera: "sensor.ritirata" });
  const aperte = [];
  scheda.dispatchEvent = (evento) => aperte.push(evento.detail.entityId);

  scheda._apri("produzione");
  v("voce viva: la finestra informazioni si apre", aperte.length === 1 && aperte[0] === "sensor.viva");
  scheda._apri("giornaliera");
  v("voce ritirata: non si apre niente", aperte.length === 1);
  scheda._apri("batteria");
  v("voce non configurata: non si apre niente", aperte.length === 1);
}
v("proposta di configurazione dal selettore", definite["nexus-fotovoltaico-card"].getStubConfig(hass).entity === "sensor.mia_mappa");

console.log("\n4. Fotovoltaico");
v("la card non ricalcola versi e autoconsumo: niente funzioni proprie",
  carta.versoScambio === undefined && carta.versoBatteria === undefined && carta.autoconsumo === undefined);

const totale = passate + fallite.length;
console.log(fallite.length ? `\nCARD: ${passate}/${totale} superate` : `\nCARD: TUTTI I CONTROLLI SUPERATI (${totale})`);
process.exit(fallite.length ? 1 : 0);
