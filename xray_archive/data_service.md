# Accessing ROSAT and eROSITA archive services and HiLIGT tool

Run the Bash commands below from `xray_archive` with Python 3.10 or newer. Both clients use the standard library. Query coordinates are ICRS decimal degrees. CLI search radii are in degrees; the existing MCP tool `query_survey` takes arcseconds. Product downloads stream to a temporary file and publish the completed file at the requested path. Use a new filename in an existing output directory.

## ROSAT


The following commands expose the HEASARC catalogue cone service, image discovery, DataLink resolution and synchronous TAP. The image service returns product links; resolving one of its DataLink URLs gives the related files and their semantics. Use `download` with a file URL from that result. The `sources` and `limit` commands access VizieR and HiLIGT respectively. [HEASARC protocol guide](https://heasarc.gsfc.nasa.gov/docs/archive/vo/instructions.html)

```bash
python rosat.py cone 83.63 22.01 --radius 1 > crab-cone.xml
python rosat.py images 83.63 22.01 --size 1 > crab-images.xml
python rosat.py datalink 'https://heasarc.gsfc.nasa.gov/xamin/vo/datalink?datalink_key&id=ivo://nasa.heasarc/rosmaster?RH500047N00/rosat.obs_hri.im.im1_fits' > crab-files.xml
python rosat.py tap 'SELECT TOP 1 * FROM rassmaster' > survey-example.xml
python rosat.py sources 83.63 22.01 --radius-arcsec 90
python rosat.py limit 83.63 22.01 --mission RosatPointedHRI --sigma 3
```

Search observation **centres** by TAP/ADQL. Use `rosmaster` for pointed observations and `rassmaster` for survey fields. The output is a VOTable that retains field descriptions and units. If the TAP connection fails for a pointed search, the client searches the NASA PSPC and HRI processed-data indexes and reports the switch on stderr. The fallback VOTable contains target, coordinates, sequence, exposure and dates. The survey table still requires TAP. Choose a search radius large enough to include off-axis pointings and confirm exposure at the candidate. For source detections, the existing `archive.query_survey("rosat", ra, dec)` uses VizieR 2RXS. [HEASARC TAP guide](https://heasarc.gsfc.nasa.gov/docs/archive/vo/instructions.html)

```bash
python rosat.py observations 83.63 22.01 --table rosmaster --radius 1 > crab-pointings.xml
python rosat.py observations 83.63 22.01 --table rassmaster --radius 4 > crab-survey-fields.xml
```

List an observation’s actual files before choosing a download. The example retrieves a PSPC image and retains its Unix-compress suffix. `--prefix` also browses other ROSAT collections and subdirectories in the public NASA bucket. Returned file sizes are bytes. [Archive sequences](https://heasarc.gsfc.nasa.gov/docs/rosat/archive_access.html) · [HEASARC cloud access](https://heasarc.gsfc.nasa.gov/docs/archive/cloud.html)

```bash
python rosat.py products --sequence rp500065n00
python rosat.py download 'https://nasa-heasarc.s3.amazonaws.com/rosat/data/pspc/processed_data/500000/rp500065n00/rp500065n00_im1.fits.Z' crab-im1.fits.Z
python rosat.py products --prefix rosat/data/
```

For cross-mission limits the existing `archive.query_hiligt` accepts `RosatSurvey`, `RosatPointedPSPC` and `RosatPointedHRI`. Choose the significance and spectral model before comparing a limit with EP. HEASARC also provides interactive Browse/Xamin, VO image discovery, SkyView image cutouts and Astroquery methods for locating and downloading associated products. [HiLIGT](https://xmmuls.esac.esa.int/upperlimitserver/) · [HEASARC service directory](https://heasarc.gsfc.nasa.gov/docs/archive/apis.html)

## eROSITA

The four operations in the official eRODat API reference are exposed as `cone`, `limit`, `limits`, and `tiles`. Use `cone --verb 1` for the smallest catalogue column set, `--verb 2` for intermediate output, or the default `--verb 3` for all columns. [eRODat APIs](https://erosita.mpe.mpg.de/erodat/apis/)

Use the official Simple Cone Search for catalogue rows and the tile service for product discovery. The cone limit is 5°. Supported catalogues are `DR2_Main`, `DR2_Hard`, `DR1_Main`, `DR1_Hard`, `DR1_Supp` and `DR1_Clusters`. The tile response includes the tile number (`srvmap`), footprint and centre. Format numeric tile IDs as six digits, retaining leading zeroes. [eRODat API specification](https://erosita.mpe.mpg.de/erodat/apis/)

```bash
python erosita.py cone 194 -5.7 --catalog DR2_Main --radius 0.025 > sources.xml
python erosita.py tiles 194 -5.7
```

For an individual archived product, choose the release and product family. The example lists the DR1 detection products for tile 275135 and downloads its one-band area curve. The same listing command works with product directories such as `EXP_010` and `UPP_010` where available. The browser download area shows available groups for each tile. eRODat also provides a download basket and a separate mirroring script for larger collections. The DR2 catalogue page provides whole-catalogue downloads. [Download area](https://erosita.mpe.mpg.de/erodat/data/download/) · [Mirroring instructions](https://erosita.mpe.mpg.de/dr1/AllSkySurveyData_dr1/mirroring.html) · [DR2 catalogue access](https://erosita.mpe.mpg.de/dr2/AllSkySurveyData_dr2/)

```bash
python erosita.py products 275135 DET_010
python erosita.py download 'https://erosita.mpe.mpg.de/erodat/data/download/135/275/DET_010/em01_275135_020_AreaTab1Blik5_c010.fits.gz' tile275135-area.fits.gz
```

For an uncatalogued position, request a single limit by GET or send a JSON array by POST. The batch API accepts up to 10,000 position-band lookups and preserves input order. Band codes are strings. DR1 supports `021` (0.2–0.6 keV), `022` (0.6–2.3), `023` (2.3–5), `024` (0.2–2.3) and `02e` (0.2–5). DR2 supports `023` and `024`. Check `de_sky`, exposure and positional flags before reporting a limit. Outside the footprint a valid response may omit the flux fields. Flux limits are in erg cm⁻² s⁻¹. [API parameters](https://erosita.mpe.mpg.de/erodat/apis/) · [Photometry and limits](https://erosita.mpe.mpg.de/dr1/AllSkySurveyData_dr1/UpperLimitServer_dr1/)

```bash
python erosita.py limit 194 -5.7 --survey DR2_eRASSc3 --band 024
cat > positions.json <<'JSON'
[{"ra":194,"dec":-5.7,"band":"024","dr_survey":"DR1_eRASS1"},{"ra":194,"dec":-5.7,"band":"024","dr_survey":"DR2_eRASSc3"}]
JSON
python erosita.py limits positions.json
```

## ESA HiLIGT

Use HiLIGT when you have a candidate position and want earlier measured fluxes or a quantitative upper limit, including for positions without a catalogue counterpart. Each request searches one mission archive and returns its available energy bands. Use the exact mission identifiers printed by the client. [ESA HiLIGT interface and mission coverage](https://xmmuls.esac.esa.int/upperlimitserver/)

```bash
python hiligt.py missions
python hiligt.py query 15.234 5.678 --mission RosatSurvey > rosat-history.json
python hiligt.py query 15.234 5.678 --mission XMMpnt --sigma 3 --blackbody-ev 100 --nh-cm2 3e20
python hiligt.py query 187.2779 2.0524 --mission SwiftXRT --power-law-slope 2
```

The default is XMM-Newton pointed observations, a three-sigma limit, a power-law slope of 1.7, and an absorption column of 3 × 10²⁰ cm⁻². Blackbody temperatures are entered in eV. Catalogue use is enabled by default; pass `--no-catalogue` to request the alternative offered by ESA. The JSON `query` records the actual parameters sent.

Each observation-band row carries its observation ID, instrument, dates, exposure in seconds and energy bounds in keV. Read measured brightness from `flux` and a bound from `flux_upper_limit` (erg cm⁻² s⁻¹). Count rates and their limits are in counts/s. Missing measurements appear as null. An empty observations list means the selected archive returned no observation rows at this position. A service error exits unsuccessfully. When comparing with EP, retain the band, spectral model, absorption and significance alongside each limit.
