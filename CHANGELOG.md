# CHANGELOG


## v0.6.2 (2026-06-03)

### Bug Fixes

- Ignore PDF footnote lines (e.g. 4Fraisetcotisations) in label collection
  ([`1a6b728`](https://github.com/aminekhettat/commonledger/commit/1a6b7285dd0b045fa5dd7baa34b748f36c0a0f48))

La Banque Postale PDFs use digit superscripts as footnote markers (e.g. '4')

to flag fees/cotisations. pdfplumber reads these as '4FRAIS...' or

'4Fraisetcotisationsper├ºusourembours├®s.' in the text stream.

Previous behaviour: footnote legend lines were appended to the preceding

transaction label (e.g. VIREMENT INSTANTANE ... 4Fraisetcotisations...).

Fix: _est_ligne_ignoree() now detects lines where digit(s) are immediately

followed by a letter with no space (footnote pattern). Lines like

'6121209 Billetterie...' (digit + space + letter = legitimate reference)

are correctly NOT filtered.

Also corrected the misleading comment in csv_parser.comparer_avec_pdf:

both CSV and PDF contain complete labels; they differ because the bank

represents the transaction ID slightly differently per export format.

333 tests, 100 coverage.


## v0.6.1 (2026-06-03)

### Bug Fixes

- Set chart PNG export resolution to 300 DPI (print quality)
  ([`8876f14`](https://github.com/aminekhettat/commonledger/commit/8876f143c24321f2f39a2006c12023e7511ea441))

### Chores

- **release**: V0.6.1 [skip ci]
  ([`1d185e2`](https://github.com/aminekhettat/commonledger/commit/1d185e2672a64a2a99295a4170b10cac14691d9a))


## v0.6.0 (2026-06-02)

### Chores

- **release**: V0.6.0 [skip ci]
  ([`7ff1190`](https://github.com/aminekhettat/commonledger/commit/7ff11900bdf3b7d2ba870ff0f7c1c6cff0a5859e))

### Features

- Save chart as PNG/SVG with exercise identification header/footer
  ([`24e8189`](https://github.com/aminekhettat/commonledger/commit/24e8189e3fd05348cc95c5763ff6c533e86682fc))

A 'Save chart' button is added below the matplotlib canvas.

The saved image embeds identifying metadata as clean header/footer bands:

header: association name, exercise label, period, chart type

footer: generation date, CommonLedger version

separator lines between header/chart/footer

The figure is restored to its original state after saving (non-destructive).

Default filename: Graphique_{libelle}_{type}_{YYYYMMDD}.png at 200 DPI.

User can override destination via file dialog; offered to open after save.

333 tests, 100 coverage.


## v0.5.0 (2026-06-02)

### Chores

- **release**: V0.5.0 [skip ci]
  ([`d6fb880`](https://github.com/aminekhettat/commonledger/commit/d6fb880018bda19ded016ac8e0b5c6b17136f7ce))

### Features

- Persistent report output directory (dossier_rapports)
  ([`d34c133`](https://github.com/aminekhettat/commonledger/commit/d34c13383c3e48f69dcd54989c6302bd28a2da52))

The user can now choose and remember a default output directory for

generated reports (Word/PDF), configurable from both the Report tab

and the Settings tab.

- ReportWidget: 'Dossier de sortie des rapports' group with text field

+ Browse button; persists to config/association.json on change;

auto-names reports as Rapport_{libelle}_{type}_{YYYYMMDD}.docx;

warns if directory is invalid before generating

- SettingsWidget: same field in the association parameters tab

- Both widgets stay in sync via set_config() signal

- 333 tests, 100 coverage


## v0.4.0 (2026-06-02)

### Chores

- **release**: V0.4.0 [skip ci]
  ([`6b04a71`](https://github.com/aminekhettat/commonledger/commit/6b04a71d18f099da04add324cd556b39a4dd0f6e))

### Features

- Support cross-year fiscal periods (e.g. Sept 2025 to Aug 2026)
  ([`272e0c7`](https://github.com/aminekhettat/commonledger/commit/272e0c78aabbe1fce683aa5793cb82ddb696f490))

Exercice.date_fin can now extend into the year following annee,

enabling non-calendar fiscal years used by many associations.

Rules:

- date_debut must belong to self.annee (identifies the exercise)

- date_fin can be in annee or annee+1 (max 31/12/annee+1)

- libelle property: '2025' for same-year, '2025-2026' for cross-year

- Validation in ImportWidget updated accordingly

- 333 tests, 100 coverage


## v0.3.0 (2026-06-02)

### Chores

- **release**: V0.3.0 [skip ci]
  ([`f87ff28`](https://github.com/aminekhettat/commonledger/commit/f87ff28239229f1e1fdd6191f50c226426985c02))

### Features

- Mandatory period (date_debut/date_fin) on exercise import
  ([`f01caf5`](https://github.com/aminekhettat/commonledger/commit/f01caf5fe5535afb642107e24e48c05a52a8b99c))

The user must now enter an explicit start and end date before importing.

This replaces the year-only validation with a proper date-range filter.

Changes:

- Exercice: date_debut/date_fin are now settable properties (validated),

persisted in JSON, and used for transaction filtering in importer_releve

(replaces t.date.year == annee with date_debut <= t.date <= date_fin)

- Exercice: partial exercises supported (e.g. 01/06 to 30/06)

- ImportWidget: two QDateEdit fields (auto-filled from year, adjustable)

with validation before launch; warning shown if transactions filtered

- 329 tests, 100 coverage


## v0.2.2 (2026-06-02)

### Bug Fixes

- Filter out-of-year transactions on import, warn user in journal
  ([`f02a8df`](https://github.com/aminekhettat/commonledger/commit/f02a8df4f0993708809ee82fd9e46c3eddb5b7c4))

Exercice.importer_releve now silently discards transactions whose year

does not match the exercice year (e.g. a CSV covering Aug 2024-Feb 2025

imported into Exercice(2025) kept the 2024 transactions). A warning is

logged and displayed in the import journal when transactions are filtered.

322 tests, 100 coverage.

### Chores

- **release**: V0.2.2 [skip ci]
  ([`3547895`](https://github.com/aminekhettat/commonledger/commit/35478953a63796acdb1b13a66a6a23a4be93c339))


## v0.2.1 (2026-06-02)

### Bug Fixes

- Strip PDF page-number artifacts glued to transaction labels
  ([`a2e267c`](https://github.com/aminekhettat/commonledger/commit/a2e267c4ed140349de80410e9eac98009caeeb52))

pdfplumber can merge a page number (e.g. '4') directly with the first word

of a transaction label on a new page, producing '4COTISATION' instead of

'COTISATION'. Fixed by: (1) detecting lone-digit lines in _est_ligne_ignoree,

(2) stripping leading digits immediately followed by an uppercase letter in

the final libelle (regex ^\d+[A-Z...] - safe: spaces prevent false positives).

Also corrected misleading comment in csv_parser.comparer_avec_pdf:

CSV contains the FULL label; PDF truncates it. Comparison by (date, montant)

is correct and intentional given this structural difference.

### Chores

- **release**: V0.2.1 [skip ci]
  ([`1f8214e`](https://github.com/aminekhettat/commonledger/commit/1f8214e99266a4cdac12c01bb5f29a10725812ec))


## v0.2.0 (2026-06-02)

### Chores

- **release**: V0.2.0 [skip ci]
  ([`56c8393`](https://github.com/aminekhettat/commonledger/commit/56c8393aa9d1536aec6f6308f8c2c323730a433d))

### Features

- Add CSV parser for La Banque Postale exports and accessibility live regions
  ([`27aa040`](https://github.com/aminekhettat/commonledger/commit/27aa04051fdaebb34fc2de3b472fa2b5dd641c53))

- CSVParserLaBanquePostale: parse La Banque Postale portal CSV exports (UTF-8-BOM, semicolon, French
  numbers)

- Aggregate transactions across overlapping CSV files with deduplication

- Gap detection (>45 days between transactions, missing year start/end coverage)

- Compare CSV vs PDF results by (date, montant) matching ÔÇö 98.4 LiveRegion, JournalLive,
  StatusBarLive classes for real-time NVDA/JAWS announcements

- 320 tests, 100 coverage


## v0.1.8 (2026-06-02)

### Chores

- **release**: V0.1.8 [skip ci]
  ([`413b8f5`](https://github.com/aminekhettat/commonledger/commit/413b8f50c8ed2379932adf78c966ef786a165706))

### Testing

- Accessibility tests 10/11 pass - all widgets have accessibleName set
  ([`21fe2b9`](https://github.com/aminekhettat/commonledger/commit/21fe2b96229c7d85390502be9d180388892ad8f4))


## v0.1.7 (2026-06-02)

### Chores

- **release**: V0.1.7 [skip ci]
  ([`7933833`](https://github.com/aminekhettat/commonledger/commit/7933833c7b6da7f5c335da71b1302b0c6ea8fb15))

### Testing

- Integration bilans annuels 2013-2025 - 13 bilans generes avec verification
  ([`564da76`](https://github.com/aminekhettat/commonledger/commit/564da76a521c584b4079bef30e988e29d7beff55))


## v0.1.6 (2026-06-01)

### Chores

- **release**: V0.1.6 [skip ci]
  ([`90ea291`](https://github.com/aminekhettat/commonledger/commit/90ea2910b5ad7bd9a09dfb59c556f194d6fd6b6a))

### Testing

- 249 tests, 100% coverage (pragma:no cover on unreachable defensive branches)
  ([`d84e47e`](https://github.com/aminekhettat/commonledger/commit/d84e47eca1be0ec2fd347433bededf1699b06201))


## v0.1.5 (2026-06-01)

### Chores

- **release**: V0.1.5 [skip ci]
  ([`9b3cbe7`](https://github.com/aminekhettat/commonledger/commit/9b3cbe7e17f64fa8e275f48299b118c0f5d006b5))

### Documentation

- Sphinx+autodoc+napoleon setup with pre-push enforcement
  ([`dc0ed8b`](https://github.com/aminekhettat/commonledger/commit/dc0ed8b4611d1b0f8923e839199bb916765c194d))


## v0.1.4 (2026-06-01)

### Chores

- **release**: V0.1.4 [skip ci]
  ([`8b34975`](https://github.com/aminekhettat/commonledger/commit/8b34975fa8f5fe35efb4eb1b31fc9c642cf4739a))

### Documentation

- Add pdoc API documentation generator and GitHub Pages deployment
  ([`9ca401f`](https://github.com/aminekhettat/commonledger/commit/9ca401f7f0518fd69432b96702446782ae889de8))


## v0.1.3 (2026-06-01)

### Bug Fixes

- Mypy 0 errors, parser coverage 45%->86%, total 89% (209 tests)
  ([`e1f9826`](https://github.com/aminekhettat/commonledger/commit/e1f98262022f3e23c25f74cea1397898a8275a44))

### Chores

- **release**: V0.1.3 [skip ci]
  ([`e2c34e3`](https://github.com/aminekhettat/commonledger/commit/e2c34e38d913aafd13ad6fb419b987232b031abd))


## v0.1.2 (2026-06-01)

### Chores

- Apply ruff auto-fixes to all source files
  ([`b6b8168`](https://github.com/aminekhettat/commonledger/commit/b6b8168064f823b714839cf23ec57d8ba620c466))

- Ruff config - ignore non-blocking style warnings for alpha phase
  ([`db0a31a`](https://github.com/aminekhettat/commonledger/commit/db0a31a7ce86363a3ccaf019588efcd53705f7c3))

- **release**: V0.1.2 [skip ci]
  ([`e1ff320`](https://github.com/aminekhettat/commonledger/commit/e1ff3202299465339432894f93b5b7e8283ba74f))


## v0.1.1 (2026-06-01)

### Chores

- **release**: V0.1.1 [skip ci]
  ([`443bc46`](https://github.com/aminekhettat/commonledger/commit/443bc463970e1121971403fcde8b30bf358cfc79))

### Testing

- 185 tests, 77 coverage - complete test suite
  ([`6bae253`](https://github.com/aminekhettat/commonledger/commit/6bae2531650bdbeb8d2ae9ef3fabd89d7d21fa3d))


## v0.1.0 (2026-06-01)

### Bug Fixes

- Deterministic id_unique with hashlib.md5, add pret_recu category, fix graphiques Decimal/float
  ([`e5bf928`](https://github.com/aminekhettat/commonledger/commit/e5bf9281e1b87034d2d888ef221f9d0622ff16bf))

- Parser robustness for all years 2013-2025
  ([`8b7a55f`](https://github.com/aminekhettat/commonledger/commit/8b7a55f53dd29dcc3dfb28ebce1f2de76bb96170))

- Periode detection for new filename format YYYY-MM-DD and YYYYMMDD mois
  ([`70599b0`](https://github.com/aminekhettat/commonledger/commit/70599b055c41e48656d84fe025e7a451f8804ad1))

### Chores

- Add .gitattributes for consistent line endings
  ([`92cd85d`](https://github.com/aminekhettat/commonledger/commit/92cd85d658c40f4403fcb4ad66c260e05c41baaf))

- Update .gitignore - exclude debug scripts and audit files
  ([`59d4c65`](https://github.com/aminekhettat/commonledger/commit/59d4c6599b0ba81fe4393cc7d603b60926ef8f45))

- **release**: V0.1.0 [skip ci]
  ([`5c30bf7`](https://github.com/aminekhettat/commonledger/commit/5c30bf73861a4792d740cc7200b295b91d6bd138))

### Continuous Integration

- Complete test suite, CI/CD pipeline, auto-versioning, repo docs
  ([`a3711f3`](https://github.com/aminekhettat/commonledger/commit/a3711f3f2a5037a23a0326c122ce999048d4b1a9))

### Documentation

- Update README - rename TresoLib to CommonLedger, add CSV export, versioning section
  ([`07f7995`](https://github.com/aminekhettat/commonledger/commit/07f7995492741ef1973cadcaa41a00b47bb0d17d))

### Features

- About dialog (BLIND SYSTEMS) + HTML user manual + Help menu
  ([`f0ad731`](https://github.com/aminekhettat/commonledger/commit/f0ad73115714354ec895f357ea597c54c0faae41))

- Application icon - Civic Ledger design
  ([`80af7c8`](https://github.com/aminekhettat/commonledger/commit/80af7c841a4ac994e948510efcdc88d2e37cb662))

- Application icon - Civic Ledger design
  ([`b5051db`](https://github.com/aminekhettat/commonledger/commit/b5051db87ea09c1392cafb671b41b97561f8f951))

- Bilan simplifie, immobilisations, type structure, report a nouveau
  ([`1c98235`](https://github.com/aminekhettat/commonledger/commit/1c982354c2bf04b09536bc4520aed42e27b57d82))

- Extract period from PDF body only, never from filename
  ([`8664505`](https://github.com/aminekhettat/commonledger/commit/8664505e52cf22fd82054c0f5e547a2449dcefaa))

- Initial release TresoLib v0.1.0
  ([`4f8c1db`](https://github.com/aminekhettat/commonledger/commit/4f8c1dbe8cea91f0f83b9abc4c6e64c545d06e6b))

- Professional report layout v1.1
  ([`b255780`](https://github.com/aminekhettat/commonledger/commit/b255780e78c71f526656a3ed32da0805a22965c4))

- Professional report layout v1.1
  ([`1c3175b`](https://github.com/aminekhettat/commonledger/commit/1c3175bbdbe483ebb4a9fa008f4f96670dab49a9))

- Rename to CommonLedger, add CSV export, fix Decimal/float graphiques, versioning
  ([`d4fef5c`](https://github.com/aminekhettat/commonledger/commit/d4fef5c8bbe7855dc5311c0d500831a64e4dd6f2))

- Responsive UI + French reports + layout fixes
  ([`b7b534b`](https://github.com/aminekhettat/commonledger/commit/b7b534bd9f569526b8221f008b10f5311df513b9))

- Responsive UI + French reports + layout fixes
  ([`1466040`](https://github.com/aminekhettat/commonledger/commit/1466040cefff1545f666bcb11e3db94ccb3ba630))
