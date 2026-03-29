# Tractatus Formae

**Ei substrat-uavhengig formteori i traktatform**

Iver Raknes Finne, Institutt for design, Arkitektur- og designhøgskolen i Oslo

---

## Om traktaten

*Tractatus Formae* svarar på spørsmålet: kvifor har ting den forma dei har?

Rammeverket har fire hovudkomponentar:

1. **Formrom** (morphospace) -- rommet av alle moglege former innanfor ein klasse
2. **Seleksjonstrykk** -- kreftene som favoriserer visse former framfor andre
3. **Tilpassingslandskap** -- den samla effekten av alle trykka
4. **Navigatorar** -- det som responderer på trykka og realiserer former

Hovudpåstanden er at dette rammeverket gjeld uavhengig av substrat: same struktur beskriv korleis ein handverkar, ein algoritme, ein biologisk vekstprosess og ein marknad produserer form. Teksten er strukturert som eit filosofisk traktat etter Wittgensteins konvensjon, med 8 nummererte hovudproposisjonar og underproposisjonar.

Søstertekst: FORMLÆRE: MATHEMATICA (formell notasjon med eksplisitte bevis).

## Repostruktur

```
formgjevars traktat/
  references.bib                  # Bibliografi (74 oppføringar)
  redaksjon/
    utkast_03.md                  # Noverande arbeidsutkast (547 liner)
    redaksjonsprotokoll.md        # Redaksjonelt oppsett, stemmer, arbeidsflyt
    build_forsteutgave.py         # Byggjeskript: printklar pocketbok
    build_utkast_03.py            # Byggjeskript: arbeidsutkast (.docx + .pdf)
    forsteutgave.pdf              # Printklar pocketbok (130 x 200 mm)
    forsteutgave_a4.pdf           # A4-versjon for skjermlesing
    redaksjonelt-svar-*.md        # Arkiv av redaksjonelle kommentarar
    strukturkritikk.md            # Proposisjon-for-proposisjon-analyse
    stilkritikk.md                # Setningsnivå-kritikk

digibok_2009032304095/            # Sideskann av Wittgensteins Tractatus
                                  # (Gyldendal Fakkel 1999, omsett av Ødegaard)

transcriptions/                   # OCR-transkripsjonar av Tractatus
  batch_01.txt ... batch_09.txt

nbno.py                           # NBNO: Nedlastar for NB.no (IIIF)
assemble_docx.py                  # Montering av Tractatus-transkripsjonar til .docx
akademisk-nn-systeminstruks.md    # Stilretningsliner for akademisk nynorsk
```

## Redaksjonen

Traktaten vert utvikla gjennom ein flerstemd redaksjonsprosess med fem analytiske linser:

| Stemme | Rolle | Perspektiv |
|--------|-------|------------|
| **W** | Forfattar (Wittgenstein) | Logisk strengheit, proposisjonell arkitektur |
| **L** | Redaktør (Levin) | Basal kognisjon, TAME, substrat-uavhengigheit |
| **M** | Kritikar (Michl) | Designhistorisk skepsis, anti-funksjonalisme |
| **T** | Matematikk (Thompson/Turing) | Morfogenese, formell presisjon |
| **D** | Designar | Typografi, layout, ferdigstilling |

Kvar proposisjon er merka med logisk status: **[Definisjon]**, **[Aksiom]**, **[Teorem]**, **[Observasjon]** eller **[Illustrasjon]**, med eksplisitte falsifiseringsvilkår der det er relevant.

Detaljert protokoll: `formgjevars traktat/redaksjon/redaksjonsprotokoll.md`

## Bygg printklar førsteutgåve

Byggjeskriptet produserer ei pocketbok (130 x 200 mm) med typografi modellert etter Gyldendal Fakkel-utgåva av Wittgensteins *Tractatus Logico-Philosophicus*:

```bash
python3 "formgjevars traktat/redaksjon/build_forsteutgave.py"
```

Produserer:
- `forsteutgave.pdf` -- pocketbok, 67 sider, EB Garamond
- `forsteutgave_a4.pdf` -- A4-versjon for skjermlesing

### Typografiske val

| Element | Val | Kjelde |
|---------|-----|--------|
| Font | EB Garamond 12 | Nærast Sabon i Fakkel-utgåva |
| Sideformat | 130 x 200 mm | Samsvarar med Fakkel-serien |
| Proposisjonslayout | Tokolonne: nummer venstre, tekst høgre | Direkte frå sideskanna |
| Overskrifter | Kapiteler (small caps), sentrerte | Analysert frå digibok |
| Sidenummer | Sentrert nedst, 9pt | Identisk med originalen |
| Tittelsida | Sentrert tittel, Kürnberger-motto nedst | Kopi av Tractatus-konvensjonen |

### Krav

```bash
pip install weasyprint python-docx markdown Pillow
sudo apt install fonts-ebgaramond  # EB Garamond font
```

### Korleis byggjeskriptet fungerer

`build_forsteutgave.py` gjer følgjande i rekkjefølgje:

1. **Les bibliografi** -- Parsar `references.bib` (BibTeX) til ein oppslagstabell med forfattar, år og tittel
2. **Les utkast** -- Les `utkast_03.md` (Markdown med proposisjonar, siteringar og matematisk notasjon)
3. **Løys siteringar** -- Erstattar `[bibtex_nøkkel]` med `(Forfattar, År)` basert på bibliografien
4. **Konverter matematikk** -- Gjer `M_C` til M&#x1D04;, `R^n` til R&#x207F;, `nabla` til &#x2207;, osv. via Unicode
5. **Markdown til HTML** -- Konverterer til HTML via Python-markdown
6. **Tractatus-layout** -- Regex-transformasjon av proposisjonar til tokolonne flex-layout med CSS-klassar for djupne
7. **CSS-typografi** -- Injiserer komplett CSS som speglar Gyldendal Fakkel-utgåva (sideformat, margar, fontval, proposisjonsstil)
8. **Tittelsider** -- Genererer halvtittel, kolofon, tittelsida med motto, og forfattarside
9. **WeasyPrint** -- Rendrar HTML+CSS til PDF i to format (pocketbok og A4)

## NBNO.py -- NB.no-nedlastar

Repoet inneheld òg `nbno.py`, eit Python-verktøy for å laste ned digitalt materiale frå Nasjonalbiblioteket (nb.no) via IIIF-protokollen. Det var dette verktøyet som henta sideskanna av Tractatus som ligg i `digibok_2009032304095/`.

### Installering

```bash
pip install nbno        # frå PyPI
# eller
git clone https://github.com/Lanjelin/NBNO.py.git && cd NBNO.py && pip install .
```

### Bruk

```bash
nbno --id <medie-ID>                   # Last ned sider som JPG
nbno --id <medie-ID> --pdf             # Lag PDF av bileta
nbno --id <medie-ID> --start 10 --stop 50  # Sideområde
```

Medie-IDen finn ein ved å klikke Referere/Sitere på nb.no og kopiere teksten etter `no-nb_`.

Støtta medietypar: bøker, aviser, tidsskrift, foto, kart, manuskript, programrapportar.

### Docker (webgrensesnitt)

```bash
docker run --name nbno -p 5000:5000 \
  -v ./nbno/data:/data \
  -d ghcr.io/lanjelin/nbno:latest
```

Opne [localhost:5000](http://127.0.0.1:5000) i nettlesaren.

## Lisens

Apache 2.0
