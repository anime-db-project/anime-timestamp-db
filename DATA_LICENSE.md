# Data licensing

The software in this repository is licensed separately from the timestamp data that may be compiled by it.

## Project code

Project code is licensed under the Apache License 2.0; see `LICENSE`.

## Compiled timestamp databases

There is currently **no published compiled timestamp dataset** in this repository.

Future `timestamps.db`, `timestamps-evidence.db`, JSON/JSONL exports, manifests, and other generated data artifacts may combine records from multiple upstream datasets. Their redistribution terms must therefore be evaluated source by source before the first public data release.

The build system must preserve at least:

- upstream source name;
- original evidence lineage when it differs from the import source;
- upstream URL;
- upstream version/revision when available;
- retrieval timestamp;
- SHA-256 of the imported artifact when possible;
- upstream license/terms note;
- record-level provenance sufficient to audit derived consensus segments.

A source must not be added to a public compiled release merely because its data is technically accessible. Its license or redistribution terms must first be documented in `THIRD_PARTY_NOTICES.md` and in release metadata.

## Aggregators and mirrors

An aggregator is not automatically an independent evidence source. If an imported dataset republishes AniSkip, Anime Skip, or another provider's timings, the original lineage must be retained so derived consensus logic does not double-count the same evidence.

## Future policy

Before the first data-bearing release, this document will be expanded into a per-source compatibility matrix. If the combined database is subject to a share-alike database license, the release will carry the required license and attribution files explicitly.
