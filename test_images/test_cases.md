# Fish Scale Metrics Extraction: Test Cases and Calibration Images

## Overview

This document catalogs images from the reference papers that have **known metric values** and can be used to calibrate and validate the automated extraction program.

**Status:** Images have been extracted using Option 2 (PyMuPDF) and are available as TIFF files in this directory.

---

## Extracted Test Images

The following 13 test case images have been extracted and are ready for validation:

| Filename | Species | Expected Diameter (µm) | Expected Space (µm) |
|----------|---------|------------------------|---------------------|
| `P1_Fig1_Lepidotes_elvensis_4.78um.tif` | *Lepidotes elvensis* | 4.78 | 4.57 |
| `P1_Fig2_Polypterus_bichir_2.63um.tif` | *Polypterus bichir* | 2.63 | 6.19 |
| `P1_Fig3_Lepisosteus_osseus_3.79um.tif` | *Lepisosteus osseus* | 3.79 | 3.14 |
| `P1_Fig4_Atractosteus_simplex_7.07um.tif` | *Atractosteus simplex* | 7.07 | 2.61 |
| `P1_Fig5_Lepisosteidae_indet_Portugal_3.82um.tif` | Lepisosteidae indet. | ~3.82 | ~3.82 |
| `P1_Fig6_Lepisosteidae_indet_Bolivia_4.50um.tif` | Lepisosteidae indet. | ~4.50 | ~4.40 |
| `P2_Fig1c_Paralepidosteus_sp_Acre_5.73um.tif` | ?*Paralepidosteus* sp. (Acre) | 5.73-5.94 | 6.00-6.25 |
| `P2_Fig1d_Lepisosteus_platyrhinchus_3.95um.tif` | *Lepisosteus platyrhinchus* | 3.95 | 3.18 |
| `P2_Fig1e_Polypterus_delhezi_2.19um.tif` | *Polypterus delhezi* | 2.19 | 5.76 |
| `P2_Pl1_Fig1a_Lepisosteus_platostomus_5.38um.tif` | *Lepisosteus platostomus* | 5.38 | 3.59 |
| `P2_Pl1_Fig1b_Polypterus_ornatipinnis_2.81um.tif` | *Polypterus ornatipinnis* | 2.81 | 5.97 |
| `P3_Fig4_Obaichthys_laevis_5.0um.tif` | *Obaichthys? laevis* | 4.73-5.27 | 4.55-4.79 |
| `P3_Fig5_Obaichthys_decoratus_5.0um.tif` | *Obaichthys decoratus* | 4.73-5.27 | 4.55-4.79 |

**Extraction method:** PyMuPDF (fitz) with manual crop coordinates refined via pixel brightness analysis.

**Note:** Images were extracted from scanned PDF pages and cropped to isolate individual SEM figures. Scale bar calibration will need to be performed during analysis (all Paper 1 and 2 images are at 700× magnification).

---

## Source Papers

| Paper ID | Reference | Key Content |
|----------|-----------|-------------|
| **Paper 1** | Gayet & Meunier (1986) C.R. Acad. Sci. Paris 303:1259-1262 | Original methodology, 6 SEM images at 700x |
| **Paper 2** | Gayet & Meunier (1993) Doc. Lab. Géol. Lyon 125:169-185 | Comprehensive measurements tables, 6 plate figures |
| **Paper 3** | Brito et al. (2000) C.R. Acad. Sci. Paris 331:823-829 | Obaichthys scales, 10 figures including SEM |

---

## Test Case Images from Paper 1 (Gayet & Meunier 1986)

All images are SEM micrographs at **G × 700** or **M × 700** magnification.

### Test Case 1.1: Lepidotes elvensis (Semionotidae)
- **Figure:** Fig. 1
- **Source:** Paper 1 (1986), page 1260
- **Species:** *Lepidotes elvensis* (Blainville)
- **Age/Locality:** Upper Lias of France
- **Magnification:** G × 700
- **Expected Results:**
  - Tubercle Diameter: **4.78 µm** (from Table 1, Paper 2)
  - Intertubercular Space: **4.57 µm** (from Table 1, Paper 2)
  - Tubercle Arrangement: **IRREGULAR** (diagnostic for Semionotidae)
- **Test Notes:** Good test for irregular pattern detection

### Test Case 1.2: Polypterus bichir (Polypteridae)
- **Figure:** Fig. 2
- **Source:** Paper 1 (1986), page 1260
- **Species:** *Polypterus bichir* Geoffroy-Saint-Hilaire
- **Age/Locality:** Extant, Africa
- **Magnification:** M × 700
- **Expected Results:**
  - Tubercle Diameter: **2.63 µm** (from Table 3, Paper 2)
  - Intertubercular Space: **6.19 µm** (from Table 3, Paper 2)
  - Tubercle Arrangement: **REGULAR**
- **Test Notes:** Smallest tubercles, largest spacing - boundary case

### Test Case 1.3: Lepisosteus osseus (Lepisosteidae)
- **Figure:** Fig. 3
- **Source:** Paper 1 (1986), page 1260
- **Species:** *Lepisosteus osseus* (Linnaeus)
- **Age/Locality:** Extant, U.S.A.
- **Magnification:** G × 700
- **Expected Results:**
  - Tubercle Diameter: **3.79 µm** (from Table 2, Paper 2)
  - Intertubercular Space: **3.14 µm** (from Table 2, Paper 2)
  - Tubercle Arrangement: **REGULAR**
- **Test Notes:** Reference standard for *Lepisosteus* genus

### Test Case 1.4: Atractosteus simplex (Lepisosteidae)
- **Figure:** Fig. 4
- **Source:** Paper 1 (1986), page 1260
- **Species:** *Atractosteus simplex* (Leidy)
- **Age/Locality:** Lower Eocene of U.S.A.
- **Magnification:** G × 700
- **Expected Results:**
  - Tubercle Diameter: **7.07 µm** (from Table 2, Paper 2)
  - Intertubercular Space: **2.61 µm** (from Table 2, Paper 2)
  - Tubercle Arrangement: **REGULAR**, tightly packed
- **Test Notes:** Large tubercles, small spacing - diagnostic for *Atractosteus*

### Test Case 1.5: Undetermined Lepisosteidae (Portugal)
- **Figure:** Fig. 5
- **Source:** Paper 1 (1986), page 1260
- **Species:** Lepisosteidae indet.
- **Age/Locality:** Upper Cretaceous of Portugal
- **Magnification:** G × 700
- **Expected Results:**
  - Should fall within *Lepisosteus* range based on Paper 2 identification as "Clastes pustulosus"
  - Tubercle Diameter: ~**3.82 µm** (from Table 2, Paper 2)
  - Intertubercular Space: ~**3.82 µm** (from Table 2, Paper 2)
- **Test Notes:** Blind test - species originally undetermined

### Test Case 1.6: Undetermined Lepisosteidae (Bolivia)
- **Figure:** Fig. 6
- **Source:** Paper 1 (1986), page 1260
- **Species:** Lepisosteidae indet.
- **Age/Locality:** Upper Cretaceous of Bolivia
- **Magnification:** G × 700
- **Expected Results:**
  - Should fall within *Lepisosteus* range
  - Tubercle Diameter: ~**4.48-4.55 µm** (estimated from Table 2, Paper 2 - Vila Vila/Hotel Cordillera specimens)
  - Intertubercular Space: ~**4.07-4.77 µm** (estimated)
- **Test Notes:** Blind test for validation

---

## Test Case Images from Paper 2 (Gayet & Meunier 1993)

### Test Case 2.1: ?Paralepidosteus sp. (Fig. 1c)
- **Figure:** Fig. 1c
- **Source:** Paper 2 (1993), page 172 (from "Gayet Scales Paralepidotus Markiert.pdf")
- **Species:** ?*Paralepidosteus* sp.
- **Age/Locality:** Cretaceous, Acre, Brazil
- **Magnification:** × 700
- **Expected Results:**
  - Tubercle Diameter: **5.73-5.94 µm** (from Table 2, Paper 2 - Paralepidosteus range)
  - Intertubercular Space: **6.00-6.25 µm** (from Table 2, Paper 2)
  - Tubercle Arrangement: **REGULAR**
- **Test Notes:** Paralepidosteus has distinctive large spacing; this is the reference image for `extraction_methodology.png`

### Test Case 2.2: Lepisosteus platyrhinchus (Fig. 1d)
- **Figure:** Fig. 1d
- **Source:** Paper 2 (1993), page 172 (from "Gayet Scales Paralepidotus Markiert.pdf")
- **Species:** *Lepisosteus platyrhinchus*
- **Age/Locality:** Extant (Recent)
- **Magnification:** × 700
- **Expected Results:**
  - Tubercle Diameter: **3.95 µm** (from Table 2, Paper 2)
  - Intertubercular Space: **3.18 µm** (from Table 2, Paper 2)
  - Tubercle Arrangement: **REGULAR**
- **Test Notes:** Typical *Lepisosteus* pattern with intermediate-sized tubercles

### Test Case 2.3: Polypterus delhezi (Fig. 1e)
- **Figure:** Fig. 1e
- **Source:** Paper 2 (1993), page 172 (from "Gayet Scales Paralepidotus Markiert.pdf")
- **Species:** *Polypterus delhezi*
- **Age/Locality:** Extant (Recent), Africa
- **Magnification:** × 700
- **Expected Results:**
  - Tubercle Diameter: **2.19 µm** (from Table 3, Paper 2)
  - Intertubercular Space: **5.76 µm** (from Table 3, Paper 2)
  - Tubercle Arrangement: **REGULAR**
- **Test Notes:** Smallest tubercle diameter in the test set; wide spacing typical of Polypteridae

### Test Case 2.4: Lepisosteus platostomus (Plate 1, Fig. 1a)
- **Figure:** Pl. 1, Fig. 1a
- **Source:** Paper 2 (1993), Plate 1
- **Species:** *Lepisosteus platostomus*
- **Age/Locality:** Extant, Eastern North America
- **Magnification:** × 700
- **Expected Results:**
  - Tubercle Diameter: **5.38 µm** (from Table 2, Paper 2)
  - Intertubercular Space: **3.59 µm** (from Table 2, Paper 2)
  - Tubercle Arrangement: **REGULAR**
- **Test Notes:** Upper size range for *Lepisosteus*

### Test Case 2.5: Polypterus ornatipinnis (Plate 1, Fig. 1b)
- **Figure:** Pl. 1, Fig. 1b
- **Source:** Paper 2 (1993), Plate 1
- **Species:** *Polypterus ornatipinnis*
- **Age/Locality:** Extant, Africa
- **Magnification:** × 700
- **Expected Results:**
  - Tubercle Diameter: **2.81 µm** (from Table 3, Paper 2)
  - Intertubercular Space: **5.97 µm** (from Table 3, Paper 2)
  - Tubercle Arrangement: **REGULAR**
- **Test Notes:** Typical *Polypterus* pattern

---

## Test Case Images from Paper 3 (Brito et al. 2000)

### Test Case 3.1: Obaichthys? laevis - Tubercle Surface (Fig. 4)
- **Figure:** Fig. 4
- **Source:** Paper 3 (2000), page 826
- **Species:** †*Obaichthys? laevis*
- **Age/Locality:** Albian, Santana Formation, Northeast Brazil
- **Magnification:** Bar = 10 µm
- **Expected Results:**
  - Tubercle Diameter: **4.73-5.27 µm**
  - Intertubercular Space: **4.55-4.79 µm**
  - Tubercle Arrangement: **REGULAR**
- **Test Notes:** Oldest known lepisosteid; intermediate values

### Test Case 3.2: Obaichthys decoratus - Tubercle Surface (Fig. 5)
- **Figure:** Fig. 5
- **Source:** Paper 3 (2000), page 826
- **Species:** †*Obaichthys decoratus*
- **Age/Locality:** Albian, Santana Formation, Northeast Brazil
- **Magnification:** Bar = 10 µm
- **Expected Results:**
  - Tubercle Diameter: **4.73-5.27 µm**
  - Intertubercular Space: **4.55-4.79 µm**
  - Tubercle Arrangement: **REGULAR**
- **Test Notes:** Same range as *O.? laevis* - confirms they form a clade

---

## Complete Reference Table for Validation

### Lepisosteidae

| Taxon | Diameter (µm) | Space (µm) | Age | Paper Source |
|-------|---------------|------------|-----|--------------|
| *Lepisosteus osseus* | 3.79 | 3.14 | Recent | P1, P2 |
| *Lepisosteus* sp. (Niger) | 3.80 | 3.11 | K | P2 |
| *L. cominatoi* | 3.80 | 4.48 | K | P2 |
| *Clastes pustulosus* | 3.82 | 3.82 | K | P2 |
| *L. platyrhinchus* | 3.95 | 3.18 | Recent | P2 |
| *L. occulatus* | 4.00 | 3.14 | Recent | P2 |
| *Lepisosteus* sp. (Tarija) | 4.27 | 3.91 | K | P2 |
| *Lepisosteus* sp. (Pakistan) | 4.32 | 3.07 | K/T | P2 |
| *L. indicus* | 4.34 | 4.04 | K | P2 |
| *Lepisosteus* sp. (Vila Vila) | 4.48 | 4.77 | K | P2 |
| *Lepisosteus* sp. (Hotel Cordillera) | 4.55 | 4.07 | K | P2 |
| †*Obaichthys* spp. | 4.73-5.27 | 4.55-4.79 | K | P3 |
| *L. platostomus* | 5.38 | 3.59 | Recent | P2 |
| *L. cuneatus* | 5.57 | 4.75 | T | P2 |
| *L. fimbriatus* | 5.61 | 4.00 | T | P2 |
| *Atractosteus tropicus* | 5.68 | 1.96 | Recent | P2 |
| †*Paralepidosteus* sp. (Deccan) | 5.73 | 6.00 | K/T | P2 |
| †*P. praecurser* | 5.94 | 6.25 | K | P2 |
| *A. trichoechus* | 6.11 | 1.89 | Recent | P2 |
| *A. spatula* | 6.25 | 2.82 | Recent | P2 |
| *A. occidentalis* | 6.95 | 2.36 | K | P2 |
| *A. simplex* | 7.07 | 2.61 | T | P1, P2 |
| "L." suessionensis | 8.26 | 1.57 | T | P2 |
| *A. strausi* | 9.07 | 2.38 | T | P2 |

### Polypteridae

| Taxon | Diameter (µm) | Space (µm) | Age | Paper Source |
|-------|---------------|------------|-----|--------------|
| *Polypterus delhesi* | 2.19 | 5.76 | Recent | P2 |
| *P. bichir lapradii* | 2.53 | 6.60 | Recent | P2 |
| *P. endlicheri* | 2.54 | 5.87 | Recent | P2 |
| *P. bichir bichir* | 2.63 | 6.19 | Recent | P1, P2 |
| *P. weeksii* | 2.63 | 7.23 | Recent | P2 |
| *P. senegalus* | 2.63 | 8.17 | Recent | P2 |
| *Polypterus* sp. (In Becetem) | 2.70 | 8.20 | K | P2 |
| *P. ornatipinnis* | 2.81 | 5.97 | Recent | P2 |
| *P. retropinnis* | 2.81 | 8.54 | Recent | P2 |
| *Erpetoichthys calabaricus* | 2.98 | 5.57 | Recent | P2 |
| *P. palmas* | 3.03 | 6.71 | Recent | P2 |
| †*Dagetella sudamericana* | 3.20 | 5.80 | K-T | P2 |

### Semionotidae

| Taxon | Diameter (µm) | Space (µm) | Age | Paper Source |
|-------|---------------|------------|-----|--------------|
| *Lepidotes laevis* | 3.93 | 4.82 | Mesozoic | P2 |
| Semionotidae indet. (Bolivia) | 4.41 | 4.51 | K | P2 |
| *Lepidotes mantelli* | 4.66 | 5.02 | K | P2 |
| *Lepidotes elvensis* | 4.78 | 4.57 | Jurassic | P1, P2 |

### Palaeonisciformes (Outgroup)

| Taxon | Diameter (µm) | Space (µm) | Paper Source |
|-------|---------------|------------|--------------|
| †*Aeduella* sp. | 2.03 | 4.79 | P3 |
| †Paramblypteridae indet. | 2.66 | 6.88 | P3 |

---

## Diagnostic Clustering Plot: Expected Test Results

```
     Tubercle Diameter (µm)
           │
       10 ─┼ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
           │
        9 ─┼ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ● A. strausi
           │                                     │
        8 ─┼ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ● L.suess│
           │                                     │ ATRACTOSTEUS
        7 ─┼ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ● A.simpl  │ ZONE
           │                         ● A.occid  │
        6 ─┼ ─ ─ ─ ─ ─ ● P.praec ─ ● A.spat ─ ─ ┘
           │           ● P.sp     ● A.trich        PARALEPIDOSTEUS
           │                      ● A.trop         ZONE
        5 ─┼ ─ ─ ─ ─ ─│─ ─ ─ ─ ─ ─│─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
           │   ● L.fimb           │
           │   ● L.cuneat ● Obaichthys zone
           │   ● L.platos         │         LEPISOSTEUS
        4 ─┼ ─ ● L.sp(VV) ─ ─ ─ ─ │─ ─ ─ ─ ─    ZONE
           │   ● Lepidotes (SEM)  │
           │   ● L.indic          │
           │   ● L.sp(Pak)        │
           │ ● L.occul            │
           │ ● L.platyr           │
        3 ─┼ ● L.comina ─ ─ ─ ─ ─ │─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
           │ ● L.osseus           │   ● Dagetella
           │ ● L.sp(Nig)    ·P.palmas
           │ ● Clastes      ·E.calab   POLYPTERIDAE
           │                ·P.ornati    ZONE
        2 ─┼ ─ ─ ─ ─ ─ ─ ─ ·P.bichir ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
           │  ·Aeduella    ·P.delhesi
           │  ·Paramblyp            ·P.seneg  ·P.retrop
           │                                  ·P.sp(InBec)
        1 ─┼───┼───┼───┼───┼───┼───┼───┼───┼───►
               1   2   3   4   5   6   7   8   9
                      Intertubercular Space (µm)

Legend:
● = Lepisosteidae (expect diameter 3.5-9+ µm, spacing 1.5-5 µm)
· = Polypteridae (expect diameter 2-3.5 µm, spacing 5.5-8.5 µm)
```

---

## Instructions for Extracting Test Images

### Option 1: Manual PDF Screenshot
1. Open PDF in high-quality viewer (Adobe Acrobat, etc.)
2. Zoom to 200-300% on the figure
3. Use screenshot/snipping tool to capture image
4. Save as TIFF or PNG (lossless formats)
5. Note the scale bar value from the figure caption

### Option 2: PDF Image Extraction Tools
```bash
# Using pdfimages (from poppler-utils)
pdfimages -tiff paper.pdf output_prefix

# Using Python with PyMuPDF
import fitz
doc = fitz.open("paper.pdf")
for page_num in range(len(doc)):
    for img_index, img in enumerate(doc[page_num].get_images()):
        # Extract image
```

### Option 3: Request Original Images
Contact authors or institutions for original SEM micrographs at full resolution.

---

## Acceptance Criteria for Automated Program

The automated extraction program should produce results within the following tolerances:

| Metric | Acceptable Error | Notes |
|--------|------------------|-------|
| Tubercle Diameter | ± 0.5 µm | ~10-15% relative error |
| Intertubercular Space | ± 0.7 µm | ~15-20% relative error |
| Genus Classification | Correct assignment | Based on clustering zones |

### Pass/Fail Criteria per Test Case

For each test image, the program **PASSES** if:
1. Mean tubercle diameter falls within ± 0.5 µm of reference value
2. Mean intertubercular space falls within ± 0.7 µm of reference value
3. Genus assignment matches expected classification

---

## Notes on Image Quality Requirements

From the original papers, images were captured at:
- **Magnification:** 700× (standard for this methodology)
- **Scale bars:** Typically 10 µm
- **Imaging:** Scanning Electron Microscopy (SEM)

For accurate measurements, test images should:
1. Have visible scale bars for calibration
2. Be in focus across the field of view
3. Have good contrast between tubercles and background
4. Be free of significant debris or damage
5. Show at least 20-30 tubercles for statistical validity

---

## File Naming Convention

When placing extracted images in `test_images/`, use the following naming convention:

```
<paper_id>_<figure_number>_<species>_<expected_diameter>um.tif

Examples:
P1_Fig3_Lepisosteus_osseus_3.79um.tif
P1_Fig4_Atractosteus_simplex_7.07um.tif
P2_Pl1_Fig1a_Lepisosteus_platostomus_5.38um.tif
P3_Fig4_Obaichthys_laevis_5.0um.tif
```

---

## References

1. Gayet M. & Meunier F.J. (1986) Apport de l'étude de l'ornementation microscopique de la ganoïne dans la détermination de l'appartenance générique et/ou spécifique des écailles isolées. C.R. Acad. Sci. Paris, t. 303, Série II, n° 13, pp. 1259-1262.

2. Gayet M. & Meunier F.J. (1993) Conséquences paléobiogéographiques et biostratigraphiques de l'identification d'écailles ganoïdes du Crétacé supérieur et du Tertiaire inférieur d'Amérique du Sud. Doc. Lab. Géol. Lyon 125: 169-185.

3. Brito P.M., Meunier F.J. & Gayet M. (2000) The morphology and histology of the scales of the Cretaceous gar Obaichthys (Actinopterygii, Lepisosteidae): phylogenetic implications. C.R. Acad. Sci. Paris, Sciences de la Terre et des planètes 331: 823-829.
