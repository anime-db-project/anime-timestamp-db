from __future__ import annotations

import sqlite3
from collections import defaultdict
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

from anime_timestamp_db.anibridge import AniBridgeIndex, EpisodeTarget

_ANIME_PROVIDERS = ("mal", "anilist", "anidb")
_SHOW_ROUTES = (("tvdb", "tvdb_show"), ("tmdb_tv", "tmdb_show"))
_MOVIE_ROUTES = (("tvdb_movie", "tvdb_movie"), ("tmdb_movie", "tmdb_movie"))


@dataclass(frozen=True, slots=True)
class TitleCandidates:
    mal: tuple[str, ...] = ()
    anilist: tuple[str, ...] = ()
    anidb: tuple[str, ...] = ()

    @property
    def is_anime(self) -> bool:
        return bool(self.mal or self.anilist or self.anidb)

    def as_dict(self) -> dict[str, list[str]]:
        return {
            "mal": list(self.mal),
            "anilist": list(self.anilist),
            "anidb": list(self.anidb),
        }


@dataclass(frozen=True, slots=True)
class EpisodeResolution:
    ids: dict[str, str]
    episode_number: int
    episode_key: str
    is_special: bool
    provider_episodes: tuple[EpisodeTarget, ...]
    method: str
    confidence: float
    routes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EpisodePlanStats:
    anime_titles: int
    exact_episodes: int
    inferred_episodes: int
    exact_dual_route: int
    exact_single_route: int

    def as_dict(self) -> dict[str, int]:
        return {
            "anime_titles": self.anime_titles,
            "exact_episodes": self.exact_episodes,
            "inferred_episodes": self.inferred_episodes,
            "exact_dual_route": self.exact_dual_route,
            "exact_single_route": self.exact_single_route,
        }


def _normalize_targets(targets: Iterable[EpisodeTarget]) -> EpisodeResolution | None:
    unique = {
        (
            item.descriptor.provider,
            item.descriptor.external_id,
            item.descriptor.scope,
            item.episode_number,
        ): item
        for item in targets
    }
    ordered = tuple(unique[key] for key in sorted(unique))
    if not ordered:
        return None

    by_provider: dict[str, set[tuple[str, str | None, int]]] = defaultdict(set)
    for target in ordered:
        by_provider[target.descriptor.provider].add(
            (
                target.descriptor.external_id,
                target.descriptor.scope,
                target.episode_number,
            )
        )
    if any(len(values) != 1 for values in by_provider.values()):
        return None

    flat = {provider: next(iter(values)) for provider, values in by_provider.items()}
    regular_numbers = {
        episode_number
        for provider, (_external_id, _scope, episode_number) in flat.items()
        if provider in {"mal", "anilist"}
    }
    if len(regular_numbers) > 1:
        return None

    ids = {
        provider: external_id
        for provider, (external_id, _scope, _episode_number) in flat.items()
    }
    if regular_numbers:
        episode_number = next(iter(regular_numbers))
        return EpisodeResolution(
            ids=ids,
            episode_number=episode_number,
            episode_key=f"ep:{episode_number}",
            is_special=False,
            provider_episodes=ordered,
            method="exact",
            confidence=1.0,
            routes=(),
        )

    anidb = flat.get("anidb")
    if anidb is None:
        return None
    _external_id, scope, episode_number = anidb
    normalized_scope = (scope or "R").upper()
    episode_key = (
        f"ep:{episode_number}"
        if normalized_scope == "R"
        else f"anidb:{normalized_scope}:{episode_number}"
    )
    return EpisodeResolution(
        ids=ids,
        episode_number=episode_number,
        episode_key=episode_key,
        is_special=normalized_scope != "R",
        provider_episodes=ordered,
        method="exact",
        confidence=1.0,
        routes=(),
    )


class SkipDBMappingIndex:
    """Bridge SkipDB IMDb identities through mappings.db into AniBridge episodes."""

    def __init__(self, mapping_db: Path, anibridge: AniBridgeIndex) -> None:
        path = Path(mapping_db).resolve()
        if not path.is_file():
            raise FileNotFoundError(path)
        self.path = path
        self.anibridge = anibridge
        self.conn = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
        self.conn.execute("PRAGMA query_only=ON")
        self.conn.execute("PRAGMA temp_store=FILE")
        self._node_cache: dict[str, int | None] = {}
        self._candidate_cache: dict[str, TitleCandidates] = {}
        self._route_cache: dict[tuple[str, str], tuple[str, ...]] = {}

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "SkipDBMappingIndex":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _imdb_node(self, imdb_id: str) -> int | None:
        cached = self._node_cache.get(imdb_id)
        if imdb_id in self._node_cache:
            return cached
        row = self.conn.execute(
            "SELECT id FROM nodes WHERE provider='imdb' AND external_id=?",
            (imdb_id,),
        ).fetchone()
        value = int(row[0]) if row is not None else None
        self._node_cache[imdb_id] = value
        return value

    def _targets(
        self,
        imdb_id: str,
        provider: str,
        *,
        suppress_conflicts: bool,
    ) -> tuple[str, ...]:
        cache_key = (imdb_id, f"{provider}:{int(suppress_conflicts)}")
        cached = self._route_cache.get(cache_key)
        if cached is not None:
            return cached
        node_id = self._imdb_node(imdb_id)
        if node_id is None:
            self._route_cache[cache_key] = ()
            return ()
        if suppress_conflicts:
            conflict = self.conn.execute(
                "SELECT 1 FROM conflicts WHERE source_node=? AND target_provider=?",
                (node_id, provider),
            ).fetchone()
            if conflict is not None:
                self._route_cache[cache_key] = ()
                return ()
        rows = self.conn.execute(
            """
            WITH direct_targets(target_node) AS (
                SELECT b_node
                FROM edges
                WHERE a_node=? AND status='accepted'
                UNION ALL
                SELECT a_node
                FROM edges
                WHERE b_node=? AND status='accepted'
            )
            SELECT target.external_id
            FROM direct_targets AS direct
            JOIN nodes AS target ON target.id=direct.target_node
            WHERE target.provider=?
            ORDER BY target.external_id
            """,
            (node_id, node_id, provider),
        )
        result = tuple(dict.fromkeys(str(row[0]) for row in rows))
        self._route_cache[cache_key] = result
        return result

    def title_candidates(self, imdb_id: str) -> TitleCandidates:
        cached = self._candidate_cache.get(imdb_id)
        if cached is not None:
            return cached
        result = TitleCandidates(
            mal=self._targets(imdb_id, "mal", suppress_conflicts=False),
            anilist=self._targets(imdb_id, "anilist", suppress_conflicts=False),
            anidb=self._targets(imdb_id, "anidb", suppress_conflicts=False),
        )
        self._candidate_cache[imdb_id] = result
        return result

    def _unique_route(self, imdb_id: str, mapping_provider: str) -> str | None:
        values = self._targets(imdb_id, mapping_provider, suppress_conflicts=True)
        return values[0] if len(values) == 1 else None

    def resolve_exact_series_episode(
        self, imdb_id: str, season: int, episode: int
    ) -> EpisodeResolution | None:
        targets: list[EpisodeTarget] = []
        routes: list[str] = []
        for mapping_provider, bridge_provider in _SHOW_ROUTES:
            external_id = self._unique_route(imdb_id, mapping_provider)
            if external_id is None:
                continue
            result = self.anibridge.resolve_show_episode(
                bridge_provider, external_id, season, episode
            )
            if result.targets:
                targets.extend(result.targets)
                routes.append(result.source_descriptor)
        normalized = _normalize_targets(targets)
        if normalized is None:
            return None
        method = "exact-dual-bridge" if len(routes) >= 2 else "exact-single-bridge"
        confidence = 1.0 if len(routes) >= 2 else 0.98
        return EpisodeResolution(
            ids=normalized.ids,
            episode_number=normalized.episode_number,
            episode_key=normalized.episode_key,
            is_special=normalized.is_special,
            provider_episodes=normalized.provider_episodes,
            method=method,
            confidence=confidence,
            routes=tuple(sorted(routes)),
        )

    def resolve_movie(self, imdb_id: str) -> EpisodeResolution | None:
        routes: list[str] = []
        descriptors = list(self.anibridge.resolve_movie(imdb_id))
        if descriptors:
            routes.append(f"imdb_movie:{imdb_id}")
        if not descriptors:
            for mapping_provider, bridge_provider in _MOVIE_ROUTES:
                external_id = self._unique_route(imdb_id, mapping_provider)
                if external_id is None:
                    continue
                found = self.anibridge.resolve_movie_from(bridge_provider, external_id)
                if found:
                    descriptors.extend(found)
                    routes.append(f"{bridge_provider}:{external_id}")
        per_provider: dict[str, set[tuple[str, str | None]]] = defaultdict(set)
        for item in descriptors:
            per_provider[item.provider].add((item.external_id, item.scope))
        if not per_provider or any(
            len(values) != 1 for values in per_provider.values()
        ):
            return None
        ids = {
            provider: next(iter(values))[0] for provider, values in per_provider.items()
        }
        provider_episodes = tuple(
            EpisodeTarget(item, 1)
            for item in sorted(
                {d for d in descriptors},
                key=lambda d: (d.provider, d.external_id, d.scope or ""),
            )
        )
        return EpisodeResolution(
            ids=ids,
            episode_number=1,
            episode_key="ep:1",
            is_special=False,
            provider_episodes=provider_episodes,
            method="exact-movie",
            confidence=1.0,
            routes=tuple(sorted(routes)),
        )

    def prepare_series_episode_map(
        self, rows: Iterable[Mapping[str, object]]
    ) -> tuple[dict[tuple[str, int, int], EpisodeResolution], EpisodePlanStats]:
        episode_keys: set[tuple[str, int, int]] = set()
        anime_titles: set[str] = set()
        for raw in rows:
            if str(raw.get("media_type") or "").casefold() != "series":
                continue
            imdb_id = str(raw.get("imdb_id") or "").strip()
            try:
                season = int(raw.get("season"))
                episode = int(raw.get("episode"))
            except (TypeError, ValueError):
                continue
            if not imdb_id or season < 0 or episode < 0:
                continue
            episode_keys.add((imdb_id, season, episode))
            if self.title_candidates(imdb_id).is_anime:
                anime_titles.add(imdb_id)

        result: dict[tuple[str, int, int], EpisodeResolution] = {}
        exact_dual = 0
        exact_single = 0
        for key in sorted(episode_keys):
            resolved = self.resolve_exact_series_episode(*key)
            if resolved is None:
                continue
            result[key] = resolved
            if resolved.method == "exact-dual-bridge":
                exact_dual += 1
            else:
                exact_single += 1

        by_season: dict[tuple[str, int], list[tuple[int, EpisodeResolution]]] = (
            defaultdict(list)
        )
        all_by_season: dict[tuple[str, int], set[int]] = defaultdict(set)
        for imdb_id, season, episode in episode_keys:
            all_by_season[(imdb_id, season)].add(episode)
            resolved = result.get((imdb_id, season, episode))
            if resolved is not None:
                by_season[(imdb_id, season)].append((episode, resolved))

        inferred = 0
        for season_key, source_episodes in all_by_season.items():
            anchors = by_season.get(season_key, [])
            if len(anchors) < 2:
                continue
            mal_anchors: list[tuple[int, str, int]] = []
            for source_episode, resolved in anchors:
                mal_id = resolved.ids.get("mal")
                if mal_id is None:
                    continue
                target_numbers = {
                    target.episode_number
                    for target in resolved.provider_episodes
                    if target.descriptor.provider == "mal"
                    and target.descriptor.external_id == mal_id
                }
                if len(target_numbers) != 1:
                    continue
                mal_anchors.append((source_episode, mal_id, next(iter(target_numbers))))
            if len(mal_anchors) < 2:
                continue
            mal_ids = {item[1] for item in mal_anchors}
            offsets = {item[2] - item[0] for item in mal_anchors}
            if len(mal_ids) != 1 or len(offsets) != 1:
                continue
            mal_id = next(iter(mal_ids))
            offset = next(iter(offsets))
            for source_episode in sorted(source_episodes):
                key = (season_key[0], season_key[1], source_episode)
                if key in result:
                    continue
                target_episode = source_episode + offset
                if target_episode <= 0:
                    continue
                descriptor = next(
                    (
                        target.descriptor
                        for _source, resolved in anchors
                        for target in resolved.provider_episodes
                        if target.descriptor.provider == "mal"
                        and target.descriptor.external_id == mal_id
                    ),
                    None,
                )
                if descriptor is None:
                    continue
                result[key] = EpisodeResolution(
                    ids={"mal": mal_id},
                    episode_number=target_episode,
                    episode_key=f"ep:{target_episode}",
                    is_special=False,
                    provider_episodes=(EpisodeTarget(descriptor, target_episode),),
                    method="inferred-season-offset",
                    confidence=0.85,
                    routes=("season-offset-from-exact-anchors",),
                )
                inferred += 1

        return result, EpisodePlanStats(
            anime_titles=len(anime_titles),
            exact_episodes=exact_dual + exact_single,
            inferred_episodes=inferred,
            exact_dual_route=exact_dual,
            exact_single_route=exact_single,
        )
