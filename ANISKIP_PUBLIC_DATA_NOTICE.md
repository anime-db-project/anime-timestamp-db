# AniSkip public dataset notice

The default Anime Timestamp DB build includes `skip_times_public.csv` from the official `aniskip/sanitize-db-dump` repository.

Upstream describes and uses this file as a public/sanitized dataset export and the AniSkip API project uses the sanitized snapshot for database seeding without user information. The dump repository, however, does not currently expose a separate explicit data license.

Anime Timestamp DB therefore records this source transparently rather than assigning it an invented license:

- source: `https://github.com/aniskip/sanitize-db-dump`;
- imported file: `skip_times_public.csv`;
- build manifest records the exact downloaded SHA-256 and retrieval metadata;
- `user_id` is deliberately excluded from the compiled runtime database, evidence metadata, and per-record payload hashes;
- only timestamp/title/episode fields needed for the database are retained.

If you redistribute a compiled database, verify the current upstream AniSkip terms and repository status yourself. This notice documents the provenance and the absence of an explicit separate data-license grant found at integration time; it is not a substitute for legal advice or an upstream license.
