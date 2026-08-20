# Excel Header Audit → 23-Field Mapping

**Source:** `Excel sheets/` — 100 files, 107 MB
**Readable:** 99 files / 305 sheets · **1 unreadable** (encrypted)
**Distinct raw header strings:** 323 · **Distinct header signatures (layouts):** 109

Companion file: **`column_mapping.json`** — 194 aliases + composite-field parsers + exclude list.

> **Three corrections to the first version of this audit**, all found by drilling into the flagged files:
> 1. The headerless `Sheet1` in `014 TOWER` etc. is the **owner** layout, not the property layout.
> 2. `Premise 1/2/3` in the largest family are **not** three hierarchy columns — `Premise 1` is pipe-packed and 2/3 are always empty.
> 3. The `Login`/`Password` columns are in `2. _ Shorelines _`, not `Al Kifaf` / `Address Harbour Point`.

---

## 1. Format problems

| File | Reality | Action |
|---|---|---|
| `Address Harbour_New Data Ryan_Nour.xlsx` (79 KB) | OLE2 with `EncryptedPackage` + `StrongEncryptionDataSpace` — standard Excel password protection | **Needs the password. No workaround.** Only genuinely blocked file. |
| `1062_20251028_...xls` (46 MB) | Not Excel — an HTML `<table>` CRM export | `pandas.read_html`. See §6, it's the single largest dataset here. |
| `25. _ Tiara (The Palm) _.xls` (138 KB) | Genuine BIFF, sheet named `TR-PALM.csv`, 463 rows | `xlrd`. Compound phone/email fields — see §8. |

Detect by magic bytes, not extension: `PK\x03\x04` → xlsx · `\xD0\xCF\x11\xE0` → xls/OLE · `<html` → HTML.

---

## 2. The 9 headerless sheets — all resolved

**Five are the same 25-column owner register**, verified column-by-column against the labelled copies in `Al Satwa.xlsx` and `118 (c).xlsx`. Positional mapping recovers them exactly:

| Pos | Field | Pos | Field | Pos | Field |
|---|---|---|---|---|---|
| 1 | P-NUMBER | 10 | PHONE | 18 | PASSPORT |
| 2 | AREA | 11 | EMAIL | 19 | ISSUE DATE |
| 3 | USAGE | 12 | FAX | 20 | EXPIRY DATE |
| 4 | TOTAL AREA | 13 | PO BOX | 21 | PLACE OF ISSUE |
| 5 | PLOT NUMBER *(see note)* | 14 | GENDER | 22 | EMIRATES ID NUMBER |
| 6 | EMIRATE | 15 | DOB | 23 | EMIRATES ID EXPIRY |
| 7 | NAME | 16 | MOBILE | 24 | RESIDENCE COUNTRY |
| 8 | AREA OWNED | 17 | SECONDARY MOBILE | 25 | NATIONALITY |
| 9 | ADDRESS | | | | |

| File | Owner rows | Distinct props | Multi-owner props | Actual scope (from col 2) | Name / Mobile / Email fill |
|---|---:|---:|---:|---|---|
| `014 TOWER.xlsx` | 31,561 | 26,930 | 3,958 (max 12) | **all Business Bay** | 31,561 / 18,752 / 19,675 |
| `29 BOULEVARD.xlsx` | 26,714 | 20,553 | 4,279 (max 12) | **all Burj Khalifa** | 26,713 / 18,512 / 10,457 |
| `ACT ONE , ACT TWO.xlsx` | 732 | 658 | 72 (max 3) | Burj Khalifa | 732 / 409 / 441 |
| `AG TOWER.xlsx` | 485 | 445 | 40 (max 2) | Business Bay | 485 / 226 / 322 |
| `AL Andalus Phase 2.xlsx` | 145 | 120 | 25 (max 2) | Me'Aisem First | 145 / 104 / 53 |

**The other four are unrelated shapes:**

| Sheet | Shape | Content |
|---|---|---|
| `Abu Dhabi Data mayl 25.xlsx :: "Sustainable  con"` | 25 cols declared, **only 3 used** | unit ref (`SC-YN7-CON-CR48-101`) / name / mobile — 355 rows of 1,000 |
| `24 Luxury leads.xlsx :: Sheet1` | 4 cols | name / phone / email — 23 populated |
| `24 Luxury leads (1).xlsx :: Sheet1` | 4 cols | same but **24 populated — not a duplicate** |
| `Address Downtown ... sms campaign :: SMS CAMPAIGN` | 4 cols | mobile / `12` / `97` / `UAE` — a dialling-code split, 300 rows. The stray literal `MOBILE1` sits in row 1 col 1. The real data is in that file's `CLEAN CONSOLIDATED` sheet. |

**Note on position 5.** Labelled `PLOT NUMBER` but in tower files it holds a *unit* ref (`G1-0`, `802-0`, `1401-`); only in land files (`Al Satwa`) is it a real plot (`2-24`). Strip the trailing `-N` to join it to the property sheet's `FLAT NUMBER` (`G1-0` ↔ `G1`).

### Filenames do not describe scope
`014 TOWER.xlsx` Sheet2 holds 44 records for 014 Tower — but Sheet1 is the owner register for **all of Business Bay**, 26,930 properties, of which **43** are 014 Tower. Same for `29 BOULEVARD` and `ACT ONE ACT TWO` (both all of Burj Khalifa). **Derive Community/Building from the row's own columns, never from the filename.**

### Building-level parent rows are not units
Property sheets carry a parent record per building: blank `FLAT NUMBER`, populated `LEVELS`/`SHOPS`/`FLATS`/`OFFICES`, and `ACTUAL AREA` = whole-building area. `014 TOWER` P-NUMBER 265607 = `LEVELS 22, SHOPS 2, OFFICES 39, AREA 10000`. These have no owner row and must be filtered or they enter as phantom units. Counts found: `014 TOWER` 1, `29 BOULEVARD` 3, `AG TOWER` 1, `AL Andalus` 1, `Al Furjan 2023` 33, `Al Hebiah Fourth` 55, `AL kifaf` 4.

---

## 3. The 6 schema families

### Family A — Contact export (55 sheets, ~24,000 rows, the largest by sheet count)
`Full name | Email | Phone Mobile | Phone Home | Person Type | Premise 1 | Premise 2 | Premise 3 | Person Mail Address`

⚠️ **`Premise 1` is a pipe-packed composite. `Premise 2` and `Premise 3` are empty in every single row.** All 24,033 values parsed have **exactly 4 parts**:

```
JBR | DXB | NA             | RIMAL 3 1101
BB  | DXB | NA             | BBET TOWER M 1208
PJT | DXB | Apartment 302  | Al Shahla Apartments
 ^     ^     ^                ^
 |     |     |                part4 -> Building/Cluster (carries the unit when part3 is NA)
 |     |     part3 -> Unit Number; literal "NA" in 13,667 of 24,033 rows
 |     part2 -> emirate, always "DXB" -> drop
 part1 -> Community code
```

Community codes (only 5 exist): `JBR` 9,822 · `JLT` 6,911 · `BB` 3,799 · `PJT` 3,497 · `JBR-BCH` 4 → Jumeirah Beach Residence, Jumeirah Lake Towers, Business Bay, Palm Jumeirah, JBR Beach.

`Person Mail Address` is also packed: `{State=DXB, Country=UAE, P.O. Box=...}`.

### Family B — Abu Dhabi "Serial No." (~60 sheets, 12 column variants)
`Serial No. | Owner`s Name | Property`s Type | No. of Unit | Project Name | Developer | No. BHK | Area sqft | Price | Contact No. | Update | Purchase Value | Documents Available | Service Charges/sqft | Status | Agent`

Variants differ only in which optional columns appear. Almost entirely inside `Abu Dhabi Data mayl 25.xlsx` (97 sheets) — see §5, it is a master that already contains 9 of the standalone files.

### Family C — DLD / Municipality property register (13 sheets)
`P-NUMBER | AREA | PLOT NUMBER | BUILDING NAME | REGISTRATION NUMBER | FLAT NUMBER | BALCONY AREA | PARKING NUMBER | COMMON AREA | FLOOR | ROOMS DESCRIPTION | LEVELS | SHOPS | FLATS | OFFICES | AGE | ACTUAL AREA | MUNICIPALITY NUMBER | MASTER PROJECT | PROJECT | PROPERTY TYPE`

Property-only, no owner. Pairs with the 25-col owner register (§2) or its narrow form `P-NUMBER | NAME | EMAIL | MOBILE | SECONDARY MOBILE`, joined on `P-NUMBER`. **See §4 — the join is not clean.**

### Family D — DLD transaction export (4 sheets)
`Regis | ProcedureValue | AreaNameEn | Master Project | Project | BuildingNameEn | Size | UnitNumber | DmNo | DmSubNo | PropertyTypeEn | LandNumber | ProcedurePartyTypeNameEn | NameEn | Mobile | ProcedureNameEn | CountryNameEn | IdNumber | UaeIdNumber | PassportExpiryDate | BirthDate | UnifiedNumber`

The **only** source of `Procedure Value`, and one of the few with `Date`. Files: `Al Barari dec 24.xlsx`, `2023 Emaar Beach Front.._done partial.xlsx`.

### Family E — Already normalized (use as test fixtures)
`Al Kifaf_Park Gate 1 and 2_02 03 series_hashim.xlsx` — **20 of your 23 columns**, 999 rows:
`File | Name | Community | Sub Community | Building Name | Unit Number | Size | Plot Reg No | Plot Number | Dmno | DMSubno | Bedroom | Type | Mobile1 | Mobile2 | Mobile3 | Email | PI number | Nationality | Property type`

Near-identical: `Address Harbour Point_01 series.xlsx` (`Flat`+`Series` instead of `Unit Number`), `2023 Emaar Beach Front..` sheet `Palace Beach Residence T.2_DONe`, `Al Furjan Jan 2026.xlsx` (snake_case).

### Family F — CRM HTML export — see §6

---

## 4. The P-NUMBER join is dirty in every paired file

10 files have a property sheet + owner sheet that must be joined on `P-NUMBER` before mapping. None of them join cleanly:

| File | Properties | Owner rows | Matched | No owner | Orphan owners | Rows after join | Max owners/prop |
|---|---:|---:|---:|---:|---:|---:|---:|
| `Al Hebiah Fourth - Sports City` | 25,330 | 31,917 | 25,097 | 233 | 911 | 31,002 (+5,672) | 10 |
| `Al Furjan 2023` | 12,596 | 57,601 | 11,067 | **1,529** | **37,901** | 14,970 (+2,374) | 14 |
| `Al Satwa` | 3,507 | 4,684 | 2,359 | **1,148** | 0 | 4,148 (+641) | **42** |
| `Al Barari 2022` (`Prop`⋈`New`) | 1,256 | 11,392 | 996 | 260 | **7,586** | 1,183 | 11 |
| `AL kifaf park gate residences` | 1,071 | 922 | 796 | **275** | 0 | 922 | 7 |
| `AL HABTOOR CITY_done` | 915 | 11,074 | 915 | 0 | **9,661** | 947 (+32) | 7 |
| `ADDRESS JBR 2022` (+`(July)`) | 930 | 1,514 | 921 | 9 | 0 | 978 (+48) | 4 |
| `Address JBR 2022 (c) July` | 930 | 978 | 921 | 9 | 0 | 978 (+48) | 4 |
| `22 Carat 2022` | 34 | 21 | **16** | **18** | 4 | 16 | 1 |

Three separate problems:

1. **Row inflation from joint ownership.** `Al Satwa` has one property with **42 owners**; `Al Furjan 2023` has 6,516 multi-owner properties. A naive join multiplies rows. Worse, `AREA OWNED` is that owner's *share*, not the unit size — unit 1401 in `014 TOWER` is 135.13 m² split 12 ways at 11.26 each. Mapping `AREA OWNED` → `Size` silently produces wrong sizes.
2. **Orphan owner rows.** `Al Furjan 2023` has 37,901 owner P-NUMBERs with no matching property, `AL HABTOOR CITY` 9,661, `Al Barari 2022` 7,586. The owner sheets are area-wide dumps while the property sheets are project-scoped — same pattern as §2. These rows have a person but no location.
3. **Properties with no owner.** `Al Satwa` 1,148, `Al Furjan 2023` 1,529, `AL kifaf` 275, `22 Carat 2022` 18 of 34.

**Decision needed:** one record per owner (keep all rows, `Size` = unit size not share) or one per property (collapse owners into `Name` + `Mobile 1/2/3`). Your 23 fields have three mobile slots, which points at one-record-per-property — but 6,516 properties in `Al Furjan 2023` alone have more than 3 owners.

---

## 5. Duplicates — 23 groups, 68,943 redundant rows

Content-hashed every sheet (normalized: trailing blanks and empty rows ignored) across all 97 openable files. **28 of 275 sheets are redundant copies.**

Largest:

| Rows | Copies | Where |
|---:|---:|---|
| 49,634 | ×2 | `Address Downtown 2022 (c).xlsx` / `..._1.xlsx` :: `Sheet2` |
| 5,750 | ×2 | `Address Harbour Point_01 series.xlsx` / `..._1.xlsx` :: `ALL` |
| 2,100 | ×2 | `A Ranches 3- [OctAug2025].xlsx` / `A Ranches 3-.xlsx` :: `Sheet1` |
| 1,630 | ×2 | `Al furjan villas Quortaj villas  (2022)(1630).xlsx` / `... (1630).xlsx` |
| 979 + 931 | ×2 | `ADDRESS JBR 2022 (July).xlsx` / `ADDRESS JBR 2022.xlsx` :: `Owner`, `Prop` |
| 890 | ×3 | `Abu Dhabi Data mayl 25 :: Al Raha Gardens` = `Al Raha Gardens.xlsx` = `Al Raha Gardens (1).xlsx` |

**`Abu Dhabi Data mayl 25.xlsx` is a consolidated master.** Its sheets are byte-identical to nine standalone files: `AL REEMAN2`, `AL REEMAN PLOTS`, `Al Maha`, `Al Raha`, `Al Raha Gardens`, `AL GURM`, `AL BAZRA`, `AL JURF`, `AL MANARA` (and their `(1)` copies). Ingest the master and skip those, or vice versa — not both.

**Two genuine data bugs, not file duplicates:**
- `3. _ JLT _ (18 towers) (1).xlsx` — sheets `Lake Terrace Tower` and `Lake View Tower` hold **byte-identical 537-row content**. One of the two towers has the wrong data pasted in. Needs a human to say which.
- `24 Luxury leads.xlsx` (23 rows) vs `24 Luxury leads (1).xlsx` (24 rows) — near-identical, the `(1)` has one extra record. Keep `(1)`.
- `Act One Act Two ... (1).xlsx` vs `... .xlsx` — same 3,116 cells, differ only by 2 trailing blank rows. Effectively identical.

---

## 6. The 46 MB HTML file is the single largest dataset

`1062_20251028_...xls` → **91,674 data rows × 19 columns**, more than any other file. A CRM (Bitrix24-style) owner-leads export.

`ID | Name | Stage | Created by | Unit Number | Created on | Import - Main Phone | Import - Owner name | Responsible person | Import - Second Phone | Sub-Community | Building Name | Community | Size | Bedroom | Amount/Currency | Purpose | Price | Plot Number`

| Column | Fill | Note |
|---|---|---|
| `Import - Owner name` | 91,661 | **the real person** — `Name` is a record label (`"Owners Data #193265"`), do not map it to Name |
| `Import - Main Phone` | 91,662 | → Mobile 1 |
| `Import - Second Phone` | 8,325 | → Mobile 2 |
| `Unit Number` | 90,586 | |
| `Sub-Community` | 91,095 | **all 91,095 carry an `[ID]` prefix** — 222 distinct |
| `Building Name` | 89,181 | **all prefixed** — 621 distinct |
| `Community` | 88,205 | **all prefixed** — 40 distinct |
| `Size` | 84,457 | |
| `Bedroom` | 931 | ~1% — effectively absent |
| `Price` / `Plot Number` | 9 / 8 | **effectively empty, ignore** |
| `Amount/Currency` | 91,674 | but the value is `AED0` throughout — treat 0 as NULL |

Strip `^\[[A-Za-z0-9]+\]` from the three location columns: `[T40a]Town Square` → `Town Square`. Top communities: Dubai Creek Harbour 10,515 · Business Bay 8,643 · Town Square 8,561 · Downtown 7,709 · Arabian Ranches 3 6,653.

`ID` is unique across all 91,674 rows — a reliable dedup key for this source. `Stage` (New Owner 61,303 / Contacted 21,568 / Follow Up 2,627 / Wrong Number 1,016 …) has no slot in the 23 — worth keeping in extras, since `Wrong Number` and `Not Active Landlord` mark records you probably don't want to call.

---

## 7. Sensitive columns — exclude at ingestion

| File | Sheet | Columns |
|---|---|---|
| `2. _ Shorelines _ (The Palm) (2175 contacts) (1).xlsx` | `Al Shahla (119)` | **`Login(or use email)` (119/119 populated), `Password` (13 populated)** |
| `118 (c).xlsx` | `Sheet2` | `PASSPORT`, `EMIRATES ID NUMBER`, `EMIRATES ID EXPIRY DATE` |
| `Al Satwa.xlsx` | `Sheet1` | same three |
| `Al Hebiah Fourth - Sports City.xlsx` | `owner` | same three |
| `2023 Emaar Beach Front.._done partial.xlsx` | 4 sheets | `IdNumber`, `UaeIdNumber`, `PassportExpiryDate`, `UnifiedNumber` |

13 real passwords sit in that Shorelines sheet. None of these map to any of the 23 fields, so excluding them costs nothing — but they will be pulled in by a naive "read every column" loader. The exclude list is in `column_mapping.json` under `exclude_columns`.

Note `PI number` is aliased to `P-NUMBER` (a property ref) in most files but to national ID numbers in Family D. Decide whether `PI number` means property ID or person ID before mapping `UnifiedNumber`/`IdNumber` into it.

---

## 8. The mapping table

Match rule: trim → collapse whitespace → uppercase → backtick`` ` ``→ apostrophe.

| # | Target | Source headers found |
|---|---|---|
| 1 | **Name** | `NAME`, `Full name`, `Owner\`s Name`, `Owner Name`, `Owners name`, `Owners_Name`, `NameEn`, `owner_name`, `Customer Name`, `Import - Owner name`, `Contact/occupier persons name`, `Joint Acct Name` |
| 2 | **Community** | `COMMUNITY`, `AREA`, `AreaNameEn`, `MASTER PROJECT`, `Master Location`, `Location`, `BU Name`, *+ Premise 1 part 1* |
| 3 | **Sub-Community** | `Sub-Community`, `Sub Community`, `sub_community`, `PROJECT`, `Project Name`, `PROJECT_NAME_EN` |
| 4 | **Building/Cluster** | `BUILDING`, `BUILDING NAME`, `BUILDING/CLUSTER`, `BuildingName`, `BuildingNameEn`, `Building No`, `TOWER`, `property_tower`, `Property Name`, *+ Premise 1 part 4* |
| 5 | **Unit Number** | `UNIT NUMBER`, `Unit`, `UnitNumber`, `unit_number`, `No. of Unit`, `FLAT`, `FLAT NUMBER`, `Flat No.`, `VILLA NUMBER`, `TOWNHOUSE NUMBER`, `Number`, `DAR Unit_No`, `property_number`, *+ Premise 1 part 3* |
| 6 | **Size** | `SIZE`, `Area sqft`, `ACTUAL AREA`, `TOTAL AREA`, `Actual Size`, `BUA`, `Built Up`, `Internal Area`, `Plot Area`, `Plot Size` — **not `AREA OWNED`, that's an ownership share** |
| 7 | **Plot Reg. No** | `PLOT REG NO`, `REGISTRATION NUMBER`, `REG NO`, `REG`, `Regis`, `PRE_REGISTRATION_NUMBER` |
| 8 | **Plot Number** | `PLOT NUMBER`, `PLOT NO`, `PLOT`, `plot_number`, `LAND NUMBER`, `LandNumber` |
| 9 | **DMNO** | `DMNO`, `DM NO`, `DmNo`, `MUNICIPALITY NUMBER`, `Municipality No`, `MUNCPLTY NO`, `Old No` |
| 10 | **DMsubno** | `DMSUBNO`, `DM SUB NO`, `DmSubNo`, `Municipality Sub No`, `New No` |
| 11 | **Bedroom** | `BEDROOM`, `BEDROOMS`, `bedrooms`, `NO. BHK`, `ROOMS`, `ROOMS DESCRIPTION`, `beds` |
| 12 | **Type (Buyer/Seller)** | `TYPE`, `ProcedurePartyTypeNameEn` only — **see warning below** |
| 13 | **Mobile 1** | `MOBILE`, `MOBILE 1`, `MOBILE1`, `mobile_1`, `Contact No.`, `CONTACT`, `PHONE`, `Phone Mobile`, `Phone 1`, `Import - Main Phone`, `TELEPHONE`, `Owners_Phone` |
| 14 | **Mobile 2** | `MOBILE 2`, `MOBILE2`, `mobile_2`, `SECONDARY MOBILE`, `Phone Home`, `Phone 2`, `Import - Second Phone`, `Telephone Residence` |
| 15 | **Mobile 3** | `MOBILE 3`, `MOBILE3`, `mobile_3`, `Telephone Office` |
| 16 | **Email Address** | `EMAIL`, `EMAIL ADDRESS`, `email`, `Person Mail Address`, `Owners_Email` |
| 17 | **PI number** | `PI NUMBER`, `P-NUMBER`, `UnifiedNumber`, `IdNumber`, `UaeIdNumber`, `AccountID`, `SystemID`, `ID` |
| 18 | **Nationality** | `NATIONALITY`, `CountryNameEn`, `RESIDENCE COUNTRY` |
| 19 | **Property Type** | `PROPERTY TYPE`, `Property\`s Type`, `PropertyTypeEn`, `PropertySubTypeNameEn`, `USAGE`, `Sub Type`, `Plan Type` |
| 20 | **Date** | `date`, `Transaction Date`, `Booking Date`, `Created on`, `Update` |
| 21 | **Procedure Value** | `ProcedureValue`, `Price`, `Purchase Value`, `Transaction Amount`, `Amount/Currency` |
| 22 | **Developer** | `DEVELOPER`, `Agent`, `Created by`, `Responsible person` |
| 23 | **Project** | `PROJECT`, `Project Name`, `PROJECT_NAME_EN`, `Project Lnd` |

### ⚠️ Field 12 does not mean what the header names suggest

I checked the actual values in every column I'd mapped to `Type (Buyer/Seller)`. Only two of the four carry buyer/seller:

| Source column | Distinct values | Verdict |
|---|---|---|
| `ProcedurePartyTypeNameEn` | `Seller` 5,068 · `Buyer` 4,989 | ✅ true buyer/seller |
| `TYPE` | `Buyer` 2,705 · `Seller` 1,146 · **`A`/`B`/`C`/`D` 141** | ⚠️ mostly, but 141 rows are block codes — validate values |
| `Person Type` | `Unit Owner` 19,509 · `Unit Tenant` 4,472 · `Building Owner Enduser` 4,258 · `Building Owner` 322 | ❌ **occupancy role**, not buyer/seller |
| `Customer Type` | `PERSON` 2,222 · `ORGANIZATION` 777 | ❌ **entity type**, not buyer/seller |

**Corrected coverage: 10 files (10%), not the 29% stated in §9.** `Person Type` and `Customer Type` are now on the do-not-map list and belong in extras — they're useful data, just not this field.

Also note `'Person Type'` appears 15 times *as a value* and `'Type'` once, meaning some sheets have **header rows repeated mid-data** (stacked/concatenated exports). Skip rows where a key field equals its own header name.

### Ambiguities that need your decision

1. **`PROJECT` / `Project Name` maps to both #3 and #23.** Where `MASTER PROJECT` + `PROJECT` both exist → Community + Sub-Community. Where only `Project Name` exists → write to both. **Confirm.**
2. **`Price` → `Procedure Value`?** `ProcedureValue` is a transaction amount; `Price` is an asking price. Same slot, different meaning.
3. **`AREA` is overloaded** — a locality name (`Me'Aisem First`) in Family C, a number in `Area sqft`. Disambiguate on whether the column is numeric.
4. **`TYPE` is overloaded** — `Person Type` = Buyer/Seller (#12); `Property's Type` = Villa/Apartment (#19). Never map bare `TYPE` without inspecting values.
5. **`PI number`** — property ref or person ID? See §7.

---

## 9. Coverage against the 23 fields

Files (of 99) containing at least one column mapping to each target:

| Target | Files | % | | Target | Files | % |
|---|---:|---:|---|---|---:|---:|
| Name | 91 | 92% | ✅ | PI number | 37 | 37% |
| Unit Number | 89 | 90% | ✅ | DMNO | 36 | 36% |
| Mobile 1 | 85 | 86% | ✅ | Plot Reg. No | 30 | 30% |
| Email Address | 67 | 68% | | **Type (Buyer/Seller)** | **10** | **10%** ⚠️ |
| Sub-Community | 65 | 66% | | Nationality | 14 | 14% | ⚠️ |
| Building/Cluster | 63 | 64% | | Developer | 11 | 11% | ⚠️ |
| Mobile 2 | 58 | 59% | | Mobile 3 | 11 | 11% | ⚠️ |
| Project | 47 | 47% | | DMsubno | 10 | 10% | ⚠️ |
| Bedroom | 42 | 42% | | Date | 9 | 9% | ⚠️ |
| Community / Size | 41 | 41% | | Procedure Value | 6 | 6% | ⚠️ |
| Plot Number / Property Type | 40 | 40% | | | | |

Only `Name`, `Unit Number`, `Mobile 1` are near-universal. Make all 23 nullable except those, and don't let dedup depend on a sparse field.

---

## 10. Value-level normalization

| Issue | Where | Handling |
|---|---|---|
| `Premise 1` pipe-packed, 4 parts | Family A, 24,033 rows | Split on `\|`; part3 `NA` → take unit from part4 |
| Phone label soup: `Fax 1: x, Mobile 1: y, Other 1: z, Home: w` | `25. _ Tiara _.xls` | Parse labelled pairs; `Mobile*` → Mobile 1-3, drop Fax/Other/Work |
| Multi-email: `a@x.com, b@x.com, c@x.com, d@x.com` | Tiara, Family A | First → Email Address, rest → extras |
| `{State=DXB, Country=UAE, P.O. Box=...}` | Family A `Person Mail Address` | key=value dict — parse or keep raw; **not an email** despite the name |
| Phone as `971\|50-6597775`, `92\|4478886161` | DLD exports | Split on `\|`, normalize to E.164 |
| Phone as `O588974731` (letter O for zero) | lead lists | Character repair before validation |
| Phone as float (`5.0655e10`), `7.4995E+21` | many | Read as string; the E+21 values are corrupt, reject |
| `[T40a]Town Square` prefixes | CRM HTML export, 268k values | `re.sub(r'^\[[A-Za-z0-9]+\]', '', v)` |
| `null` as a literal string | Family A `Phone Home` | Treat as NULL |
| Arabic values (`دبي`, addresses) | `Al Satwa`, `Al Hebiah Fourth` | UTF-8 end to end, don't transliterate |
| Excel serial dates *and* `1986-10-07 00:00:00` strings | mixed | Detect per column |
| `AED0` | CRM export, all 91,674 rows | Strip currency, 0 → NULL |

---

## 11. Recommended order of work

1. **Confirm the 5 ambiguities in §8** — they change the schema, not just the code.
2. **Decide the join grain in §4** (one row per owner vs per property). Everything downstream depends on it.
3. Build the mapper off `column_mapping.json`; add positional fallback for the 5 owner-register sheets and the composite parsers for `Premise 1` / `Owners_Phone`.
4. Apply the §5 dedup list before ingesting — it removes 68,943 duplicate rows for free.
5. Filter building-level parent rows (§2) and exclude the §7 columns.
6. Test on `Al Kifaf_Park Gate 1 and 2_02 03 series_hashim.xlsx` (20/23 columns, 999 rows), then `014 TOWER` (headerless + join + 12-way joint ownership), then the 91,674-row HTML export for volume.
7. Ask for the password to `Address Harbour_New Data Ryan_Nour.xlsx` or drop it.
