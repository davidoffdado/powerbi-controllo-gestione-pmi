# Dati simulati di un calzaturificio marchigiano (azienda inventata) per la dashboard dimostrativa.
# Gennaio 2024 - settembre 2026. Nei numeri ci sono tre storie da far emergere nella dashboard:
#   1. i ricavi crescono, ma il margine scende perché aumentano gli sconti all'ingrosso e il costo della pelle
#   2. pochi clienti pagano sistematicamente in ritardo e pesano sullo scaduto
#   3. in magazzino resta merce delle stagioni passate che non si muove più
import numpy as np
import pandas as pd
from pathlib import Path

OUT = Path(__file__).parent / "dati"
OUT.mkdir(exist_ok=True)
rng = np.random.default_rng(2026)
INIZIO, FINE = pd.Timestamp("2024-01-01"), pd.Timestamp("2026-09-30")

# ---------------------------------------------------------------- prodotti
categorie = {  # categoria: (linee, prezzo di listino medio, quota di costo)
    "Sneaker": (["Uomo", "Donna", "Bambino"], 95, 0.52),
    "Mocassino": (["Uomo", "Donna"], 130, 0.55),
    "Stivaletto": (["Uomo", "Donna"], 165, 0.57),
    "Sandalo": (["Donna", "Bambino"], 80, 0.50),
    "Décolleté": (["Donna"], 140, 0.54),
}
stagioni = ["PE 2024", "AI 2024", "PE 2025", "AI 2025", "PE 2026", "AI 2026"]
stagionali = {"Sandalo": ["PE"], "Stivaletto": ["AI"]}
prodotti = []
for cat, (linee, prezzo, quota) in categorie.items():
    for linea in linee:
        for s in stagioni + ["Continuativo"]:
            if s != "Continuativo" and cat in stagionali and s[:2] not in stagionali[cat]:
                continue
            if s == "Continuativo" and cat in stagionali:
                continue
            n = 1 if s == "Continuativo" else rng.integers(1, 3)
            for _ in range(n):
                listino = round(prezzo * rng.uniform(0.8, 1.25) * (0.6 if linea == "Bambino" else 1), 0)
                prodotti.append(dict(categoria=cat, linea=linea, stagione=s, prezzo_listino=listino,
                                     costo_base=round(listino * quota * rng.uniform(0.95, 1.05), 2)))
dim_prodotto = pd.DataFrame(prodotti)
dim_prodotto["prodotto_id"] = range(1, len(dim_prodotto) + 1)
sigle = {"Sneaker": "SNK", "Mocassino": "MOC", "Stivaletto": "STV", "Sandalo": "SND", "Décolleté": "DEC"}
dim_prodotto["articolo"] = [f"{l[:2].upper()}-{sigle[c]}-{i:03d}" for l, c, i in
                            zip(dim_prodotto.linea, dim_prodotto.categoria, dim_prodotto.prodotto_id)]

# periodo di vendita di ogni stagione: PE da gennaio ad aprile, AI da luglio a ottobre (più una coda)
def finestra(stagione):
    if stagione == "Continuativo":
        return INIZIO, FINE
    tipo, anno = stagione.split()
    anno = int(anno)
    return (pd.Timestamp(anno, 1, 1), pd.Timestamp(anno, 6, 30)) if tipo == "PE" else \
           (pd.Timestamp(anno, 7, 1), pd.Timestamp(anno, 12, 31))

# ---------------------------------------------------------------- clienti
citta = ["Milano", "Roma", "Torino", "Bologna", "Firenze", "Napoli", "Bari", "Verona", "Padova", "Ancona",
         "Pescara", "Genova", "Palermo", "Brescia", "Perugia", "Rimini", "Bergamo", "Trento", "Lecce", "Cagliari"]
clienti = []
for i in range(36):
    clienti.append(dict(canale="Negozi Italia", cliente=f"Negozio {citta[i % 20]} {i // 20 + 1:02d}",
                        paese="Italia", dilazione=60))
for i, c in enumerate(["Napoli", "Milano", "Bari", "Roma", "Verona", "Palermo", "Bologna", "Torino"]):
    clienti.append(dict(canale="Ingrosso", cliente=f"Grossista {c}", paese="Italia", dilazione=90))
for p in ["Germania", "Francia", "Svizzera", "Austria", "Belgio", "Paesi Bassi", "Regno Unito", "Stati Uniti",
          "Giappone", "Corea del Sud", "Spagna", "Danimarca"]:
    clienti.append(dict(canale="Estero", cliente=f"Distributore {p}", paese=p, dilazione=30))
clienti.append(dict(canale="E-commerce", cliente="Sito e-commerce aziendale", paese="Italia", dilazione=0))
dim_cliente = pd.DataFrame(clienti)
dim_cliente["cliente_id"] = range(1, len(dim_cliente) + 1)
# dimensione dei clienti: pochi grandi, molti piccoli
dim_cliente["peso"] = rng.lognormal(0, 0.8, len(dim_cliente))
dim_cliente.loc[dim_cliente.canale == "Ingrosso", "peso"] *= 3.2
dim_cliente.loc[dim_cliente.canale == "Estero", "peso"] *= 2.0
dim_cliente.loc[dim_cliente.canale == "E-commerce", "peso"] = 9.0
# comportamento di pagamento: la maggior parte puntuale, alcuni in ritardo, due cronici
ritardo = rng.choice([0, 8, 25], len(dim_cliente), p=[0.6, 0.3, 0.1]).astype(float)
cronici = dim_cliente.index[dim_cliente.canale.isin(["Negozi Italia", "Ingrosso"])][[5, 38]]
ritardo[cronici] = [75, 110]
dim_cliente["ritardo_tipico"] = ritardo
dim_cliente.loc[dim_cliente.canale == "E-commerce", "ritardo_tipico"] = 0

# ---------------------------------------------------------------- vendite
giorni = pd.date_range(INIZIO, FINE, freq="D")
mese = giorni.month.values
stagionalita = {  # peso mensile delle spedizioni per canale
    "B2B": np.array([1.6, 2.2, 1.8, 0.9, 0.4, 0.3, 1.5, 2.3, 2.0, 1.0, 0.4, 0.3]),
    "E-commerce": np.array([0.8, 0.7, 1.0, 1.1, 1.1, 1.0, 0.9, 0.8, 1.0, 1.1, 1.6, 1.9]),
}
crescita = lambda d: 1.0 + 0.10 * ((d - INIZIO).days / 365)
sconto_canale = {"Negozi Italia": (0.05, 0.03), "Ingrosso": (0.15, 0.04), "Estero": (0.02, 0.0), "E-commerce": (0.0, 0.0)}
ricarico_canale = {"Negozi Italia": 1.0, "Ingrosso": 1.0, "Estero": 1.15, "E-commerce": 1.9}

righe = []
for c in dim_cliente.itertuples():
    profilo = stagionalita["E-commerce" if c.canale == "E-commerce" else "B2B"][mese - 1]
    giorni_lavoro = giorni[giorni.dayofweek < 5] if c.canale != "E-commerce" else giorni
    w = profilo[np.isin(giorni, giorni_lavoro)] * np.array([crescita(d) for d in giorni_lavoro])
    n_ordini = int(c.peso * (60 if c.canale != "E-commerce" else 900))
    date_ordini = rng.choice(giorni_lavoro, n_ordini, p=w / w.sum())
    for d in date_ordini:
        d = pd.Timestamp(d)
        disponibili = dim_prodotto[[finestra(s)[0] <= d <= finestra(s)[1] for s in dim_prodotto.stagione]]
        n_art = 1 if c.canale == "E-commerce" else rng.integers(2, 7)
        scelti = disponibili.sample(min(n_art, len(disponibili)), random_state=int(rng.integers(1e9)))
        anni = (d - INIZIO).days / 365
        base, deriva = sconto_canale[c.canale]
        for p in scelti.itertuples():
            qta = 1 if c.canale == "E-commerce" else int(rng.integers(4, 25))
            prezzo = p.prezzo_listino * ricarico_canale[c.canale] * (1 + 0.025 * anni)
            sconto = min(0.35, max(0, base + deriva * anni + rng.normal(0, 0.015)))
            costo = p.costo_base * (1 + 0.045 * anni)  # la pelle costa sempre di più
            righe.append(dict(data=d.date(), cliente_id=c.cliente_id, prodotto_id=p.prodotto_id, quantita=qta,
                              ricavo_lordo=round(qta * prezzo, 2), sconto=round(qta * prezzo * sconto, 2),
                              costo=round(qta * costo, 2)))
vendite = pd.DataFrame(righe).sort_values(["data", "cliente_id"]).reset_index(drop=True)
vendite["ricavo"] = (vendite.ricavo_lordo - vendite.sconto).round(2)

# ---------------------------------------------------------------- scadenzario
# una fattura per cliente e giorno di spedizione; l'e-commerce si incassa subito
fatture = vendite.groupby(["cliente_id", "data"], as_index=False).ricavo.sum()
fatture = fatture.merge(dim_cliente[["cliente_id", "canale", "dilazione", "ritardo_tipico"]], on="cliente_id")
fatture = fatture[fatture.canale != "E-commerce"].copy()
fatture["importo"] = (fatture.ricavo * 1.22).round(2)  # con IVA (estero semplificato)
fatture["data_fattura"] = pd.to_datetime(fatture.data)
fatture["data_scadenza"] = fatture.data_fattura + pd.to_timedelta(fatture.dilazione, "D")
rit = np.maximum(0, rng.normal(fatture.ritardo_tipico, np.maximum(3, fatture.ritardo_tipico * 0.35)))
rit[rng.random(len(fatture)) < 0.04] += rng.uniform(30, 90)  # qualche ritardo occasionale
fatture["data_incasso"] = fatture.data_scadenza + pd.to_timedelta(rit.round(), "D")
aperta = fatture.data_incasso > FINE
fatture.loc[aperta, "data_incasso"] = pd.NaT
fatture["stato"] = np.where(aperta, "Aperta", "Incassata")
fatture["giorni_ritardo"] = (fatture.data_incasso - fatture.data_scadenza).dt.days.clip(lower=0).astype("Int64")
fatture["giorni_incasso"] = (fatture.data_incasso - fatture.data_fattura).dt.days.astype("Int64")
scaduto = (FINE - fatture.data_scadenza).dt.days
fasce = [("Incassata", 0), ("Non scaduta", 1), ("Scaduta da 1-30 giorni", 2), ("Scaduta da 31-60 giorni", 3),
         ("Scaduta da 61-90 giorni", 4), ("Scaduta da oltre 90 giorni", 5)]
idx = np.select([~aperta, scaduto <= 0, scaduto <= 30, scaduto <= 60, scaduto <= 90], [0, 1, 2, 3, 4], 5)
fatture["fascia"] = [fasce[i][0] for i in idx]
fatture["fascia_ordine"] = idx
fatture = fatture.sort_values("data_fattura").reset_index(drop=True)
fatture["fattura"] = [f"FT {d.year}/{i:05d}" for i, d in enumerate(fatture.data_fattura, 1)]
scadenze = fatture[["fattura", "cliente_id", "data_fattura", "data_scadenza", "data_incasso", "importo", "stato",
                    "fascia", "fascia_ordine", "giorni_ritardo", "giorni_incasso"]]

# ---------------------------------------------------------------- magazzino (fine mese, al costo)
fine_mesi = pd.date_range(INIZIO, FINE, freq="ME")
venduto = vendite.assign(data=pd.to_datetime(vendite.data)).groupby(["prodotto_id", "data"]).quantita.sum()
mag = []
for p in dim_prodotto.itertuples():
    inizio_v, fine_v = finestra(p.stagione)
    s = venduto.get(p.prodotto_id, pd.Series(dtype=float))
    totale = s.sum()
    if p.stagione == "Continuativo":
        # riassortimento continuo: scorta di circa due mesi di vendite
        for m in fine_mesi:
            vm = s[(s.index > m - pd.DateOffset(months=1)) & (s.index <= m)].sum()
            mag.append((m, p.prodotto_id, int(max(0, vm * rng.uniform(1.6, 2.4)))))
        continue
    prodotto_tot = totale * rng.uniform(1.06, 1.32)  # si produce sempre un po' più del venduto
    arrivi = [(inizio_v - pd.DateOffset(months=2), 0.5 * prodotto_tot), (inizio_v, 0.5 * prodotto_tot)]
    for m in fine_mesi:
        arrivato = sum(q for d, q in arrivi if d <= m)
        giac = arrivato - s[s.index <= m].sum()
        if m > fine_v:  # dopo la stagione una parte va in outlet ogni mese, il resto resta fermo
            giac *= 0.93 ** ((m - fine_v).days / 30)
        mag.append((m, p.prodotto_id, int(max(0, round(giac)))))
magazzino = pd.DataFrame(mag, columns=["data", "prodotto_id", "giacenza"])
costo_attuale = dim_prodotto.set_index("prodotto_id").costo_base * (1 + 0.045 * (FINE - INIZIO).days / 365)
magazzino["valore"] = (magazzino.giacenza * magazzino.prodotto_id.map(costo_attuale)).round(2)
magazzino["data"] = magazzino.data.dt.date
magazzino = magazzino[magazzino.giacenza > 0]

ultima = pd.to_datetime(vendite.groupby("prodotto_id").data.max())
dim_prodotto["ultima_vendita"] = dim_prodotto.prodotto_id.map(ultima).dt.date
dim_prodotto["giorni_senza_vendite"] = (FINE - pd.to_datetime(dim_prodotto.ultima_vendita)).dt.days
dim_prodotto["fermo"] = dim_prodotto.giorni_senza_vendite > 180
dim_prodotto["stagione_ordine"] = dim_prodotto.stagione.map({s: i for i, s in enumerate(stagioni + ["Continuativo"], 1)})

# ---------------------------------------------------------------- calendario
dim_data = pd.DataFrame({"data": giorni.date})
d = pd.to_datetime(dim_data.data)
nomi = ["gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic"]
dim_data["anno"] = d.dt.year
dim_data["mese_numero"] = d.dt.month
dim_data["mese"] = d.dt.to_period("M").dt.to_timestamp().dt.date
dim_data["mese_nome"] = [f"{nomi[m - 1]} {y}" for m, y in zip(d.dt.month, d.dt.year)]
dim_data["trimestre"] = "T" + d.dt.quarter.astype(str) + " " + d.dt.year.astype(str)

# ---------------------------------------------------------------- scrittura
def scrivi(df, nome):
    df.to_csv(OUT / f"{nome}.csv", index=False, encoding="utf-8", date_format="%Y-%m-%d")

scrivi(dim_data, "dim_data")
scrivi(dim_cliente[["cliente_id", "cliente", "canale", "paese", "dilazione"]].rename(columns={"dilazione": "giorni_dilazione"}), "dim_cliente")
scrivi(dim_prodotto[["prodotto_id", "articolo", "linea", "categoria", "stagione", "prezzo_listino",
                     "stagione_ordine", "ultima_vendita", "giorni_senza_vendite", "fermo"]], "dim_prodotto")
scrivi(vendite[["data", "cliente_id", "prodotto_id", "quantita", "ricavo_lordo", "sconto", "ricavo", "costo"]], "fatti_vendite")
scrivi(scadenze, "fatti_scadenze")
scrivi(magazzino, "fatti_magazzino")

# ---------------------------------------------------------------- controlli: le tre storie si vedono?
v = vendite.assign(anno=pd.to_datetime(vendite.data).dt.year)
per_anno = v.groupby("anno")[["ricavo", "costo", "sconto", "ricavo_lordo"]].sum()
per_anno["margine_%"] = 100 * (1 - per_anno.costo / per_anno.ricavo)
per_anno["sconto_%"] = 100 * per_anno.sconto / per_anno.ricavo_lordo
print(per_anno.round(1))
v9 = v[pd.to_datetime(v.data).dt.month <= 9].groupby("anno").ricavo.sum()
print("ricavi gen-set:", (v9 / 1e6).round(2).to_dict())
aperte = scadenze[scadenze.stato == "Aperta"]
print("crediti aperti:", round(aperte.importo.sum()), "scaduti:", round(aperte[aperte.fascia_ordine >= 2].importo.sum()))
print(aperte[aperte.fascia_ordine >= 2].merge(dim_cliente, on="cliente_id").groupby("cliente").importo.sum()
      .sort_values(ascending=False).head(4).round())
ult = magazzino[magazzino.data == magazzino.data.max()].merge(dim_prodotto, on="prodotto_id")
print("magazzino:", round(ult.valore.sum()), "fermo:", round(ult[ult.fermo].valore.sum()))
print("righe:", len(vendite), "fatture:", len(scadenze), "prodotti:", len(dim_prodotto), "clienti:", len(dim_cliente))
