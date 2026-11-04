"""Conservative independent AniBridge proof for Anime Skip episode identities.

AniList title identity alone never establishes a MAL playback unit. Require
an explicit one-to-one AniDB regular episode -> AniList episode -> MAL episode
route, and verify all native provider title IDs against one AMDB anchor.
"""

from __future__ import annotations

from dataclasses import dataclass

from anime_timestamp_db.anibridge import AniBridgeIndex
from anime_timestamp_db.mapping_identity import MappingAnchorIndex


@dataclass(frozen=True, slots=True)
class ApiEpisodeProof:
    mal_id: str
    mal_episode: int
    anidb_id: str
    anidb_episode: int

    @property
    def episode_key(self) -> str:
        return f"ep:{self.mal_episode}"


class AnimeSkipEpisodeBridge:
    """Never guess title/episode equivalence from numeric equality alone."""

    def __init__(self, bridge: AniBridgeIndex, identities: MappingAnchorIndex) -> None:
        self.bridge = bridge
        self.identities = identities
        self._cache: dict[tuple[str, int, int], ApiEpisodeProof | None] = {}

    def resolve(
        self, anilist_id: str, anchor_id: int, episode: int
    ) -> ApiEpisodeProof | None:
        key = (str(anilist_id), int(anchor_id), int(episode))
        if key not in self._cache:
            self._cache[key] = self._resolve_uncached(*key)
        return self._cache[key]

    def _resolve_uncached(
        self, anilist_id: str, anchor_id: int, episode: int
    ) -> ApiEpisodeProof | None:
        if (
            episode <= 0
            or self.identities.anchor_for("anilist", anilist_id) != anchor_id
        ):
            return None
        aliases = self.identities.ids_for_anchor(anchor_id)
        proofs: set[ApiEpisodeProof] = set()
        for anidb_id in aliases.get("anidb", []):
            matched = self.bridge.resolve_anidb_regular_for_anilist(
                anidb_id, anilist_id, episode
            )
            if matched is None:
                continue
            anidb_episode, result = matched
            if result.skipped_complex_targets:
                continue
            anilist_targets = [
                target
                for target in result.targets
                if target.descriptor.provider == "anilist"
            ]
            # One native AniDB playback unit cannot simultaneously prove
            # two different AniList episodes or anime-title identities.
            if len(anilist_targets) != 1:
                continue
            native = anilist_targets[0]
            if (
                native.descriptor.external_id != anilist_id
                or native.descriptor.scope is not None
                or native.episode_number != episode
            ):
                continue
            mal_targets = [
                target
                for target in result.targets
                if target.descriptor.provider == "mal"
            ]
            # An absent, conflicting, or special-scope MAL identity cannot
            # justify creating a new canonical MAL playback unit.
            if len(mal_targets) != 1:
                continue
            mal = mal_targets[0]
            if (
                anidb_episode < 1
                or mal.episode_number < 1
                or mal.descriptor.scope is not None
                or self.identities.anchor_for("mal", mal.descriptor.external_id)
                != anchor_id
            ):
                continue
            proofs.add(
                ApiEpisodeProof(
                    mal_id=mal.descriptor.external_id,
                    mal_episode=mal.episode_number,
                    anidb_id=anidb_id,
                    anidb_episode=anidb_episode,
                )
            )
        # Multiple independent routes must not silently win by iteration order.
        return next(iter(proofs)) if len(proofs) == 1 else None
