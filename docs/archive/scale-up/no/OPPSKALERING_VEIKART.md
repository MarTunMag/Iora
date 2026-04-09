# Aris Oppskaleringsveikart: Fra Privat Trader til Imperium

**Formål:** Kartlegge hele reisen fra privat algo-trader som komponderer personlig kapital, gjennom til institusjonell drift, kapitaldiversifisering og samfunnsnyttig foretaksbygging.

**Nåværende Status:** 14 V2-botter live på ICMarkets, 3-lags risikoallokering, 59 features, 86,1% WR backtest.

---

## Innholdsfortegnelse

1. [Fase 0: Komponderingsgrunnlag (Nåværende til $500K)](#fase-0-komponderingsgrunnlag)
2. [Fase 1: Lot-tak Metning og Flerkonti ($500K til $2M)](#fase-1-lot-tak-metning)
3. [Fase 2: Flermegler Diversifisering ($2M til $10M)](#fase-2-flermegler-diversifisering)
4. [Fase 3: Prime-of-Prime og Selskapsetablering ($10M til $50M)](#fase-3-prime-of-prime)
5. [Fase 4: Institusjonell Prime Brokerage ($50M til $500M)](#fase-4-institusjonell-prime-brokerage)
6. [Fase 5: Bygg Egen Infrastruktur ($500M+)](#fase-5-bygg-egen-infrastruktur)
7. [Kapitaldiversifiseringsstrategi](#kapitaldiversifiseringsstrategi)
8. [Imperiumvisjonen](#imperiumvisjonen)
9. [Nåværende ICMarkets Lot-tak (Referanse)](#lot-tak-referanse)

---

## Fase 0: Komponderingsgrunnlag

**Kapitalområde:** Nåværende til $500K

### Hva Skjer Her
- 14 botter komponderer kapital med 1,0/0,75/0,5% risiko per handel
- Posisjonsstørrelser vokser naturlig med kontoegenkapitalen
- Ingen strukturelle endringer nødvendig — systemet fungerer som det er
- Fokus: overvåk live vs. backtest-paritet, samle data, bevis at edgen er ekte

### Viktige Milepæler
- **$50K:** Første meningsfulle egenkapitalbase. Posisjoner er store nok for anstendig R-avkastning i kroneverdi.
- **$100K:** Begynner å treffe min-lot begrensninger sjeldnere på indekser. Alle 14 symboler bidrar aktivt.
- **$250K:** Noen symboler (BTCUSD med 10 lots maks, DE40/UK100 med 50 lots) begynner å nærme seg lot-tak på større handler.
- **$500K:** Flere symboler treffer regelmessig lot-tak. Effektiv risiko faller under mål fordi posisjonsstørrelse er begrenset. **Dette er triggeren for å begynne Fase 1.**

### Flaskehalsopdaging
Når `calculate_position_size()` returnerer `max_lot` istedenfor beregnet størrelse, legger du igjen edge på bordet. Systemet logger dette — overvåk for:
```
Beregnet: 15.2 lots -> Begrenset til: 10.0 lots (BTCUSD)
```
Når dette skjer på >20% av handler for et symbol, er det symbolet "mettet".

### Tiltak
- [ ] Bygg lot-tak metningsmonitor (varsel når >20% av handler treffer max_lot)
- [ ] Spor effektiv risiko vs. målrisiko per symbol
- [ ] Start skatteplanlegging — konsulter regnskapsfører om handelsselskapsstruktur

---

## Fase 1: Lot-tak Metning

**Kapitalområde:** $500K til $2M
**Trigger:** Flere symboler treffer regelmessig maks lots

### Problemet
ICMarkets har per-posisjon maks lots:

| Symbol | Maks Lots | Ca. Kapital ved Metning (1% risiko) |
|--------|----------|--------------------------------------|
| BTCUSD | 10 | ~$200K-500K (avhenger av ATR) |
| DE40 | 50 | ~$1M-2M |
| UK100 | 50 | ~$1M-2M |
| NZDUSD | 50 | ~$1M-2M |
| XAGUSD | 50 | ~$800K-1,5M |
| EURJPY | 100 | ~$2M-4M |
| GBPJPY | 100 | ~$2M-4M |
| XAUUSD | 100 | ~$2M-4M |
| US500 | 100 | ~$3M-5M |
| EURUSD | 200 | ~$5M-10M |
| GBPUSD | 200 | ~$5M-10M |
| USDJPY | 200 | ~$5M-10M |

### Strategi A: Flere ICMarkets-kontoer
**Enkleste første trekk. Null infrastrukturendring.**

- Åpne 2-3 ICMarkets-kontoer under samme navn/selskap
- Kjør identiske bot-instanser på hver konto
- Hver konto får sin egen MT5-instans + bot-floate
- Multipliserer effektivt lot-tak med antall kontoer
- ICMarkets tillater flere kontoer — dette er standard praksis

**Implementering:**
```
Konto 1: 14 botter (original)
Konto 2: 14 botter (klon — samme modeller, samme konfig)
Konto 3: 14 botter (klon)
= 3x lot-kapasitet per symbol
```

**Fordeler:** Null kodeendring, samme megler, samme betingelser
**Ulemper:** Manuell kapitalforvaltning på tvers av kontoer, 3x provisjon, 3x overvåking

### Strategi B: Del Flåten På Tvers av Kontoer
Istedenfor å klone alle 14 botter, del etter metningsnivå:

```
Konto 1: Hoymetningssymboler (BTCUSD, DE40, UK100, XAGUSD, NZDUSD)
Konto 2: Middels metning (XAUUSD, EURJPY, GBPJPY, US500, USTEC, US30)
Konto 3: Lav metning (EURUSD, GBPUSD, USDJPY) — disse når 200-lot tak sist
```

Alloker mer kapital til kontoer med symboler som mettes først.

### Strategi C: Ok Symboldekning
Legg til flere symboler for å spre kapital over flere instrumenter:
- Ekstra forex: AUDUSD, USDCHF, USDCAD, AUDNZD, EURGBP
- Ekstra indekser: JP225 (Nikkei), HK50 (Hang Seng), AU200 (ASX)
- Ekstra metaller: XPTUSD (Platina)
- Råvarer: USOIL, UKOIL, NATGAS

Hvert nytt symbol = ekstra lot-kapasitet. Tren V2-modeller for nye symboler med samme pipeline.

### Strategi D: Flertidsramme-modeller
For tiden kun M5. Legg til:
- M15 inngangsmodell (annet inngangstiminig, annen lot-allokering)
- H1 swing-modell (større TP/SL, færre handler, større størrelse per handel)

Forskjellige tidsrammer = ukorrelerte innganger = mer kapasitet uten lot-konflikter.

### Tiltak for Fase 1
- [ ] Åpne 2. ICMarkets-konto
- [ ] Bygg flåteorkestrator (styrer botter på tvers av flere MT5-instanser)
- [ ] Legg til 5-10 nye symboler i V2-treningspipeline
- [ ] Utforsk M15/H1 modellvarianter
- [ ] Etabler handelsselskap (skatteeffektivitet, ansvarsbeskyttelse)

---

## Fase 2: Flermegler Diversifisering

**Kapitalområde:** $2M til $10M
**Trigger:** 3+ ICMarkets-kontoer nærmer seg metning ELLER ønske om motpartsrisikoreduksjon

### Hvorfor Flere Meglere
1. **Motpartsrisiko** — ha aldri all kapital hos en megler
2. **Aggregerte lot-grenser** — hver megler har uavhengige grenser
3. **Eksekveringsmangfold** — forskjellige likviditetspooler, forskjellige fyllinger
4. **Regulatorisk beskyttelse** — spre på tvers av jurisdiksjoner

### Kriterier for Meglervalg
| Krav | Hvorfor |
|------|---------|
| Raw spread / ECN-konto | Matcher ICMarkets eksekveringsmodell |
| MT5-støtte | V2-botter kjører på MT5 |
| FIX API tilgjengelig | Fremtidig institusjonell tilkobling |
| Samme symboler tilgjengelig | Paritet med eksisterende flåte |
| Lav latens til meglerserver | Eksekverings kvalitet |
| Segregerte klientmidler | Sikkerhet |

### Kandidatmeglere (Tier 1 Detaljhandel/Semi-Institusjonell)
| Megler | Styrker | Lot-grenser | Merknader |
|--------|---------|-------------|-----------|
| **Pepperstone** | Raw spread, MT5, FIX API | 100-200 lots | Australsk + britisk regulert |
| **FP Markets** | ECN, MT5, bra for algo | 100+ lots | Australsk regulert |
| **Global Prime** | DMA, FIX API | Lignende ICMarkets | Algo-vennlig |
| **Interactive Brokers** | Institusjonelt API, multiaktiva | Svart høye grenser | Annen plattform (ikke MT5) — krever adapter |
| **Darwinex** | Algo-fokusert, kan bli "Darwin"-fond | Varierer | Kapitalallokeringsprogram for beviste strategier |

### Kapitalallokering På Tvers av Meglere
```
ICMarkets:   40% ($800K-4M)  — Primær, bevist eksekvering
Pepperstone: 30% ($600K-3M)  — Sekundær, uavhengig likviditet
IBKR:        20% ($400K-2M)  — Institusjonell bro, multiaktiva eksponering
Reserve:     10% ($200K-1M)  — Kontantbuffer / ny megler onboarding
```

### Interactive Brokers — Broen til Institusjonelt

IBKR fortjener spesiell oppmerksomhet fordi det er den naturlige broen mellom detaljhandel og institusjonelt:
- **Ingen per-posisjon lot-grenser** for de fleste instrumenter (bruker marginbaserte grenser istedet)
- **FIX API** for institusjonell tilkobling
- **Prime Broker-tjenester** for fond fra ~$500K+
- **Multiaktiva:** Aksjer, opsjoner, futures, forex, obligasjoner — alt på en konto
- **Lavere marginkostnader** enn detaljhandelsmeglere etter hvert som kontostørrelsen vokser

**Avveining:** Ikke MT5 — må bygge et bot-adapterlag (Python API er utmerket, og vår V2 signalgenerering er allerede Python-native).

### Tiltak for Fase 2
- [ ] Åpne Pepperstone + IBKR-kontoer
- [ ] Bygg megleragonostisk eksekveringslag (abstraher bort MT5-avhengighet)
- [ ] Bygg tverrmegler risikoaggregator (total eksponeringsovervåking)
- [ ] Tilpass V2SignalProvider til å gi signaler for IBKR API
- [ ] Juridisk: formaliser handelsselskap, regnskap, skattestrategi

---

## Fase 3: Prime-of-Prime og Selskapsetablering

**Kapitalområde:** $10M til $50M
**Trigger:** Detaljhandelsmeglere kan ikke effektivt håndtere ditt volum; soker institusjonell likviditet

### Beslutning om Selskapsstruktur

På dette kapitalnivået betyr selskapsstruktur enormt mye:

#### Alternativ A: Family Office (Anbefalt Forst)
- **Hva:** Juridisk enhet som forvalter din egen/familiens kapital
- **Regulering:** Generelt unntatt fra registreringskrav
- **Fleksibilitet:** Maksimal — ingen investorrapportering, ingen ekstern rapportering
- **Skatt:** Kan optimalisere struktur (holdingselskap -> handelsselskap -> eiendomsselskap)
- **Best for:** Privat kapitalkompondering uten eksterne investorer

```
Aris Holdings (Morselskap)
+-- Aris Trading AS (algo-trading drift)
+-- Aris Eiendom AS (eiendomsinvesteringer)
+-- Aris Ventures AS (aksje-/oppstartsinvesteringer)
+-- Aris Stiftelsen (filantropisk arm — skattefradrag)
```

#### Alternativ B: Hedgefond (Når Du Tar Inn Ekstern Kapital)
- **Hva:** Samlet investeringskjoretoy med eksterne investorer
- **Regulering:** Krever tillatelse over visse AUM-terskler; varierer etter jurisdiksjon
- **Struktur:** Typisk LP/GP med 2/20 gebyrmodell (2% forvaltning + 20% avkastning)
- **Min praktisk AUM:** $10M-50M for å rettferdiggjøre driftskostnader ($100K-300K/år overhead)
- **Best for:** Når du vil forvalte andres penger sammen med dine egne

#### Alternativ C: Begge (Krafttrekket)
- Family office forvalter personlig kapital (ingen regulering)
- Hedgefond som separat enhet tar ekstern kapital
- Delt infrastruktur (samme botter, samme modeller, samme team)
- Family office allokerer til fondet som investor

### Prime-of-Prime (PoP) Tilgang

Ved $10M+ kvalifiserer du for PoP-leverandorer:

| PoP-leverandor | Min Kapital | Hva Du Får |
|----------------|-------------|-------------|
| **IS Prime** | ~$1M-5M | FCA-regulert, Tier-1 banklikviditet, lav-latens FIX |
| **Advanced Markets** | ~$1M | DMA, institusjonelle spreader |
| **CFH Clearing** | ~$2M | Multiaktiva likviditet, prime-of-prime clearing |
| **Invast Global** | ~$5M | Direkte markedstilgang, Tier-1 aggregering |

**Hva PoP gir deg:**
- Direkte tilgang til Tier-1 banklikviditet (Goldman, JPM, Citi, Barclays)
- Mye høyere lot-grenser (eller ingen per-handel grenser — kun marginbasert)
- Bedre spreader enn detaljhandel (0,0-0,1 pip på major-par)
- FIX API-tilkobling (bransjestandard for institusjonell handel)
- Ingen "detaljhandelsmegler" i kjeden

### Infrastrukturutvikling
```
FOR (Detaljhandel):
  Bot -> MT5 -> ICMarkets -> Likviditetsleverandor

ETTER (PoP):
  Bot -> FIX Engine -> PoP -> Tier-1 Banker (flere)
                           -> Ikke-bank markedsaktorer
                           -> ECN-pooler
```

### Tiltak for Fase 3
- [ ] Engasjer forretningsadvokat — etabler holdingselskap + handelsselskap
- [ ] Engasjer skatterådgiver — optimaliser kapitalstrommer mellom selskaper
- [ ] Sok 2-3 PoP-leverandorer om tilbud
- [ ] Bygg FIX API eksekveringsmotor (erstatt MT5-avhengighet)
- [ ] Ansett: DevOps-ingenior (infrastruktur), compliance-konsulent
- [ ] Beslutt: kun family office vs. hedgefondstruktur

---

## Fase 4: Institusjonell Prime Brokerage

**Kapitalområde:** $50M til $500M
**Trigger:** Volum og AUM rettferdiggjør direkte prime broker-forhold

### Tier-1 Prime Broker-krav
| Krav | Typisk Terskel |
|------|---------------|
| AUM | $50M-500M minimum (varierer per PB) |
| Månedlig volum | $10B+ nominell foretrukket |
| Selskapstype | Regulert fond eller family office |
| Track record | 2-3+ års revidert avkastning |
| Infrastruktur | FIX-tilkobling, risikosystemer, compliance |

### Prime Broker-fordeler
- **Direkte bankforhold** — handel med Goldman, JPM, Citi direkte
- **Kryssmarginering** — portefoljenivå margin istedenfor per-posisjon
- **Verdipapirlan** — hvis du utvider til aksjer
- **Kapitalintroduksjon** — PB introduserer deg for allokatorer/investorer
- **Finansiering** — gearing på portefoljenivå til institusjonelle renter
- **Depot** — institusjonell aktivadeponering
- **Ingen lot-grenser** — kun marginbaserte eksponeringsgrenser

### Fler-prime Strategi
Bruk aldri bare en prime broker (Lehman-lærdommen):
```
Primær PB:    Goldman Sachs (40% av flyten)
Sekundær PB:  Morgan Stanley (30% av flyten)
Tertiær PB:   Interactive Brokers Prime (20% av flyten)
Reserve:       Separat depot (10% kontanter/obligasjoner)
```

### Teknologi på Denne Skalaen
| Komponent | Formål |
|-----------|---------|
| **OMS** (Ordrestyringssystem) | Sentral ordreruting, allokering, compliance |
| **EMS** (Eksekveringsstyringssystem) | Smart ordreruting, algo-eksekvering, multimarked |
| **Risikomotor** | Sanntids portefoljerisiko, korrelasjonsovervåking, VaR |
| **FIX Gateway** | Multi-PB tilkobling |
| **Datainfrastruktur** | Ko-lokaliserte servere, tick-data, alternativ data |
| **Compliance-system** | Revisjonsspor, regulatorisk rapportering, posisjonsgrenser |

### Tiltak for Fase 4
- [ ] Etabler prime broker-relasjoner (start samtaler ved $25M+)
- [ ] Bygg OMS/EMS (eller lisensier: FlexTrade, TradingScreen, osv.)
- [ ] Ansett: Tradingsjef, risikomanager, compliance-offiser
- [ ] Få fondet revidert (påkrevd for institusjonell troverdighet)
- [ ] Etabler multi-prime oppsett
- [ ] Vurder: ko-lokasjon på NY4/LD4 for eksekverings kvalitet

---

## Fase 5: Bygg Egen Infrastruktur

**Kapitalområde:** $500M+
**Trigger:** Volum rettferdiggjør å eie infrastrukturstakken

### Alternativ A: Eget Meglerhus / Market Maker
Ved $500M+ AUM med bevist eksekveringsbehov blir det levedyktig å bygge egen prime-of-prime eller market making-enhet:

- **Egen likviditetsaggregator** — koble direkte til 20+ Tier-1 banker og ECN-er
- **Intern kryssing** — match ordrer på tvers av egne fond/kontoer for de går til markedet (reduserer markedspåvirkning)
- **Market making** — gi likviditet til detaljhandels-/institusjonelle kunder, tjen spread
- **Hvitmerking** — lisensier teknologistakken til andre fond

```
Aris Capital (Morselskap)
+-- Aris Execution Services (egen prime-of-prime / market maker)
|   +-- FIX-tilkoblinger til 20+ banker
|   +-- Smart Ordreruter
|   +-- Intern kryssingsmotor
+-- Aris Alpha Fund (dine algo-strategier)
+-- Aris Systematic Fund (ekstern kapital)
+-- Aris Technology (lisensier teknologi til andre)
```

### Alternativ B: Flerstrategiutvidelse
Din V2-edge er HA Fibonacci + LightGBM. På denne skalaen, diversifiser alfagenereringen:

| Strategiklasse | Beskrivelse | Kapitalallokering |
|----------------|-------------|-------------------|
| **V2 Kjerne** (nåværende) | M5 HA-fib innganger, 14 symboler | 30% |
| **V2 Utvidet** | Nye symboler, nye tidsrammer (M15/H1/H4) | 20% |
| **Statistisk Arbitrasje** | Tverrpar gjennomsnittsbetydning, kointegrasjon | 15% |
| **Makro Systematisk** | Trendfolgning på renter, råvarer, aksjer | 15% |
| **Alternativ Data** | Sentiment, flow, posisjonsbaserte signaler | 10% |
| **Kontanter / Obligasjoner** | Avkastning på reserver, risk-off allokering | 10% |

### Alternativ C: Teknologilisensiering
Din V2-pipeline (featuregenerering -> trening -> distribusjon -> live eksekvering) er et produkt:
- Lisensier plattformen til andre tradere/fond
- SaaS-modell: datapipeline + modelltrening + eksekvering
- Inntektsdiversifisering utover handels-PnL

---

## Kapitaldiversifiseringsstrategi

**Prinsipp:** Trading genererer kapitalen. Diversifisering bevarer og multipliserer den.

### Kapitalfossen

```
Handelsoverskudd
    |
    +-- 50% -> Reinvester i Trading (komponder edgen)
    |          +-- Mer kapital = flere lots = mer absolutt avkastning
    |
    +-- 20% -> Eiendom
    |          +-- Næringseiendom (kontantstrøm)
    |          +-- Boligutvikling
    |          +-- Tomtebanking
    |
    +-- 15% -> Aksjer og Private Markeder
    |          +-- Indeksfond (passiv)
    |          +-- Teknologi/vekstaksjer (aktiv)
    |          +-- Oppstartsinvesteringer (angel/VC)
    |          +-- Private equity-saminvesteringer
    |
    +-- 10% -> Kontanter og Obligasjoner (likviditetsbuffer)
    |          +-- Statsobligasjoner
    |          +-- Selskapsobligasjoner
    |          +-- Pengemarked
    |
    +-- 5% -> Stiftelse / Giving
               +-- Se "Imperiumvisjonen" nedenfor
```

### Diversifisering etter Kapitalnivå

| Kapital | Trading % | Eiendom | Aksjer | Kontanter/Obligasjoner | Stiftelse |
|---------|-----------|---------|--------|----------------------|-----------|
| $0-1M | 90% | 0% | 5% | 5% | 0% |
| $1M-10M | 70% | 10% | 10% | 8% | 2% |
| $10M-50M | 50% | 20% | 15% | 10% | 5% |
| $50M-500M | 40% | 25% | 18% | 10% | 7% |
| $500M+ | 30% | 25% | 20% | 10% | 15% |

Etter hvert som kapitalen vokser, reduser handelskonsentrasjon (selv om det er den høyest-avkastende aktivaklassen) fordi:
1. Lot-tak skaper avtagende avkastning ved skala
2. Enkeltstrategirisiko oker med konsentrasjon
3. Diversifiserte aktiva gir ukorrelert avkastning
4. Eiendom og aksjer komponderer uavhengig av tradingledgen

### Eiendomsstrategi
| Fase | Kapital Deployert | Strategi |
|------|-------------------|----------|
| Tidlig ($1M-5M) | $100K-500K | Bolig utleie, 1-3 eiendommer |
| Vekst ($5M-20M) | $1M-4M | Små næringslokaler, boligportefoljer |
| Skala ($20M-100M) | $5M-25M | Utviklingsprosjekter, næringsportefoljer |
| Institusjonell ($100M+) | $25M+ | Eiendomsfond, utviklingspartnerskap, tomt |

### Aksje- og Venturestrategi
| Fase | Strategi |
|------|----------|
| Tidlig | Indeksfond (S&P 500, globalt), noen individuelle teknologiaksjer |
| Vekst | Legg til angelinvesteringer (5-10 oppstarter å $25K-100K hver) |
| Skala | VC-fond saminvesteringer, private equity, pre-IPO allokeringer |
| Institusjonell | Start egen venturearm, direkteinvesteringer, styreposisjoner |

---

## Imperiumvisjonen

### Kjernefilosofi
> Penger er verktoyet. Frihet er målet. Pavirkning er hensikten.

Trading-bottene skaper motoren. Alt annet kommer fra denne motorens produksjon.

### Foretaksstruktur (Full Visjon)

```
IMPERIUM HOLDINGS
|
+-- ARIS CAPITAL (Trading og Investering)
|   +-- Algoritmisk Trading (V2-botter + fremtidige strategier)
|   +-- Hedgefond (ekstern kapital)
|   +-- Eksekverings tjenester (egen prime/market maker)
|   +-- Teknologilisensiering (SaaS)
|
+-- ARIS EIENDOM
|   +-- Boligportefoljer
|   +-- Næringsportefoljer
|   +-- Utviklingsprosjekter
|
+-- ARIS VENTURES
|   +-- Oppstartsinvesteringer
|   +-- Teknologisatsninger
|   +-- Aksjeportefoljeforvaltning
|
+-- ARIS OPERATIONS
|   +-- Handelsinfrastruktur
|   +-- Datasentre
|   +-- Fellestjenester (juridisk, regnskap, HR)
|
+-- ARIS STIFTELSEN (Ideell)
    +-- Gratis Opplæringsprogrammer (se nedenfor)
    +-- Offentlig Infrastruktur
    +-- Utdanning
    +-- Helse og Velvare
```

### Arbeidsplassvisjonen

Når kapitalen opprettholder det, bygg organisasjoner der:

| Element | Standard | Aris-Standard |
|---------|----------|-----------------|
| Arbeidsdag | 8 timer slit | 8 timer totalt: 5t arbeid + 2t selvutvikling + 1t trening |
| Opplæring | "Se denne videoen" | Profesjonelle kurs, sertifiseringer, mentorer — fullt finansiert |
| Trening | "Rabatt på treningssenter" | Eget treningssenter, personlige trenere, gruppetimer — alt betalt |
| Lønn | "Konkurransedyktig" | Genuint over markedet. Folk skal ikke stresse over penger |
| Vekst | "Karrierestige" | Ekte ferdighetsutvikling — koding, trading, ledelse, kreativitet |
| Formål | "Aksjonærverdi" | Bygge ting som gjør verden målbart bedre |

### Samfunnspåvirkning

Hva "å gjøre godt" ser ut som i stor skala:

| Kapitalnivå | Påvirkningskapasitet |
|-------------|----------------------|
| $10M+ | Finansier stipend, sponse lokale programmer |
| $50M+ | Bygg gratis opplæringssentre, finansier lokal infrastruktur |
| $100M+ | Etabler stiftelse med permanent kapitalbase |
| $500M+ | Storskala offentlige prosjekter — bolig, utdanning, helsevesen |
| $1B+ | Systemisk endring — finansier policyresearch, bygg institusjoner |

Nøkkelinnsikten: **du trenger ikke vente på milliarder.** Start stiftelsen tidlig (selv med 2% av overskuddet), la den kompondere sammen med handelskapitalen, og skaler påvirkningen etter hvert som kapitalen vokser.

---

## Lot-tak Referanse

Fra `src/iki/utils/market_mechanics.py` (SSOT):

| Symbol | Maks Lots | Aktivaklasse | Risikonivå |
|--------|----------|-------------|-------------|
| BTCUSD | 10 | Krypto | T1 (1,0%) |
| NZDUSD | 50 | Forex | T3 (0,5%) |
| XAGUSD | 50 | Metall | T2 (0,75%) |
| DE40 | 50 | Indeks | T1 (1,0%) |
| UK100 | 50 | Indeks | T1 (1,0%) |
| EURJPY | 100 | Forex JPY | T2 (0,75%) |
| GBPJPY | 100 | Forex JPY | T3 (0,5%) |
| XAUUSD | 100 | Metall | T2 (0,75%) |
| US500 | 100 | Indeks | T1 (1,0%) |
| USTEC | 100 | Indeks | T1 (1,0%) |
| US30 | 100 | Indeks | T2 (0,75%) |
| EURUSD | 200 | Forex Major | T3 (0,5%) |
| GBPUSD | 200 | Forex Major | T3 (0,5%) |
| USDJPY | 200 | Forex JPY | T3 (0,5%) |

**Første symbol som mettes:** BTCUSD (10 lots) — overvåk dette først.

---

## Beslutningsrammeverk

Ved hver kapitalmilepæl, spor:

1. **Er noen symboler lot-begrenset på >20% av handler?** -> Skaler horisontalt (flere kontoer/meglere)
2. **Er motpartsrisiko konsentrert?** -> Diversifiser meglere
3. **Er selskapsstrukturen skatteoptimal?** -> Restrukturer om nødvendig
4. **Legger vi igjen edge på bordet?** -> Legg til symboler, tidsrammer, strategier
5. **Er kapitalkonsentrasjon for hoy i trading?** -> Diversifiser til eiendom/aksjer
6. **Kan vi begynne å gi tilbake ennå?** -> Finansier stiftelsen

---

## Viktige Risikohensyn

| Risiko | Tiltak |
|--------|--------|
| Edge-forfall | Kontinuerlig overvåking, retren modeller, Fase 5 diversifisering |
| Meglerinsolvens | Flermegler, segregerte midler, maks 40% hos en enkelt enhet |
| Regulatorisk endring | Flerjurisdiksjon selskaper, juridisk rådgiver |
| Nokkelperson-risiko (deg) | Dokumenter alt, bygg team, automatiser drift |
| Markedsregimeendring | Flerstrategi diversifisering, kontantreserver |
| Teknologisvikt | Redundant infrastruktur, multi-DC deployment |
| Overbelanning ved skala | Streng risikoallokering, uavhengig risikofunksjon |

---

## Umiddelbare Neste Steg (Prioritert Rekkefolge)

1. **Overvak lot-tak metning** — bygg varselet (kodeendring)
2. **Skatte-/juridisk konsultasjon** — forstå optimal selskapsstruktur for Norge
3. **2. ICMarkets-konto** — enkleste skaleringstrekk når metning inntreffer
4. **Ny symboltrening** — utvid flåten fra 14 til 20+ symboler
5. **IBKR-konto** — begynn å utforske institusjonell eksekvering
6. **Start stiftelsen** — selv med 1-2%, begynn vanen med å gi

---

*Opprettet: 2026-03-01*
*Dette er et levende dokument. Oppdater etter hvert som kapitalmilepæler nås.*
