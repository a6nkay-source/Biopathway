# Data sources

| Source | Base URL | Used for | Rate limit applied | Terms |
|---|---|---|---|---|
| NCBI Gene / PubMed / ClinVar (E-utilities) | https://eutils.ncbi.nlm.nih.gov/entrez/eutils/ | gene resolution, literature search, abstracts (efetch XML), clinical variant assertions | 3 req/s; 10 req/s if `NCBI_API_KEY` is set | public; NCBI asks heavy users to register a key and identify themselves |
| UniProtKB REST | https://rest.uniprot.org/uniprotkb/ | protein entry, function, GO, features, sequence | 5 req/s | CC BY 4.0 |
| Reactome Content Service | https://reactome.org/ContentService/ | pathway search, hierarchy, events, gene-to-pathway mapping | 5 req/s | CC0 (data), CC BY 4.0 (some content) |
| STRING API | https://string-db.org/api/ | functional association networks with channel scores | 1 req/s, `caller_identity=biopathway-mapper` | CC BY 4.0; STRING asks for one call per second |
| KEGG REST | https://rest.kegg.jp/ | pathway lists, flat files, KGML, modules, compounds | 3 req/s | **free for academic use by academic users only**; others need a licence (https://www.kegg.jp/kegg/legal.html). `--no-kegg` / `BPM_DISABLE_KEGG=1` switches it off |

## Environment variables

| Variable | Effect |
|---|---|
| `NCBI_API_KEY` | sent to NCBI only on the wire; never written to cache or the provenance log |
| `NCBI_EMAIL` | sent to NCBI as `email=` if you want NCBI to be able to contact you; not sent otherwise |
| `BPM_CACHE_DIR` | cache location (default `~/.cache/biopathway-mapper`) |
| `BPM_DISABLE_KEGG=1` | same as `--no-kegg` |

## Caching

- One JSON file per request URL (SHA-256 of the URL), storing the body and retrieval time.
- TTL 7 days (`--cache-ttl-days`). `--no-cache` disables reads and writes.
- If a live request fails after retries, an expired cache entry is used and flagged `stale` in the report's request count. A 404 never falls back.
- `--offline` serves from cache regardless of age and never touches the network.

## Retries and errors

- Retries with exponential backoff (1, 2, 4 s; honours `Retry-After`, capped at 60 s) on HTTP 429/500/502/503/504 and network errors. Other 4xx are not retried.
- Reactome, KEGG and STRING use 404/400 for "no such record"; the clients treat those as empty results, not failures.
- Any remaining failure becomes `failed: <reason>` in the report's source table plus a warning. Analyses continue with the remaining sources.

## Identifier systems

| Entity | Primary id | Cross-references kept |
|---|---|---|
| Gene | NCBI Gene id + official symbol | aliases, cytogenetic location |
| Protein | UniProtKB accession (reviewed preferred) | Reactome, KEGG, STRING, GeneID xrefs from UniProt |
| KEGG gene | `hsa:<NCBI Gene id>` | KEGG uses NCBI Gene ids for human, so no lookup table is needed |
| Pathway | KEGG `hsaNNNNN`, Reactome `R-HSA-N` stable ids | URLs in every citation |
| Compound | KEGG `CNNNNN` | primary name |
| Variant | protein HGVS (`p.Arg175His`) | ClinVar VCV accession, UniProt VAR_ ids |

## Provenance

`analysis.json` contains `requests`: every URL fetched (secrets excluded), whether it came from cache, and the retrieval timestamp. The report prints the request count and timestamp range.
