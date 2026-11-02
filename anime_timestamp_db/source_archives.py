from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import subprocess
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path

import zstandard as zstd

_SAFE_TAG = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")
_ARCHIVE_KINDS = ("7z", "tar.zst", "zip")


@dataclass(frozen=True, slots=True)
class SourceArchiveSet:
    project: str
    tag: str
    root_name: str
    seven_zip: Path
    tar_zstd: Path
    zip: Path

    @property
    def paths(self) -> tuple[Path, Path, Path]:
        return (self.seven_zip, self.tar_zstd, self.zip)


def validate_release_token(value: str, *, field: str) -> str:
    normalized = str(value).strip()
    if not _SAFE_TAG.fullmatch(normalized):
        raise ValueError(
            f"{field} must contain only letters, digits, '.', '_' and '-' "
            "and must start with a letter or digit"
        )
    return normalized


def archive_set(project: str, tag: str, output_dir: Path) -> SourceArchiveSet:
    project = validate_release_token(project, field="project")
    tag = validate_release_token(tag, field="tag")
    output_dir = Path(output_dir)
    root_name = f"{project}-{tag}"
    prefix = f"zz-{root_name}-source"
    return SourceArchiveSet(
        project=project,
        tag=tag,
        root_name=root_name,
        seven_zip=output_dir / f"{prefix}.7z",
        tar_zstd=output_dir / f"{prefix}.tar.zst",
        zip=output_dir / f"{prefix}.zip",
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def append_checksum_rows(checksum_path: Path, paths: tuple[Path, ...]) -> None:
    checksum_path = Path(checksum_path)
    names = {path.name for path in paths}
    preserved: list[str] = []
    if checksum_path.is_file():
        for line in checksum_path.read_text(encoding="utf-8").splitlines():
            fields = line.split(maxsplit=1)
            if len(fields) == 2 and fields[1].lstrip("* ") in names:
                continue
            if line.strip():
                preserved.append(line)
    rows = [f"{sha256_file(path)}  {path.name}" for path in paths]
    checksum_path.parent.mkdir(parents=True, exist_ok=True)
    checksum_path.write_text("\n".join([*preserved, *rows]) + "\n", encoding="utf-8")


def _git_archive(
    repo_root: Path,
    *,
    commit: str,
    archive_format: str,
    root_name: str,
    destination: Path,
) -> None:
    with destination.open("wb") as output:
        subprocess.run(
            [
                "git",
                "archive",
                f"--format={archive_format}",
                f"--prefix={root_name}/",
                commit,
            ],
            cwd=repo_root,
            stdout=output,
            check=True,
        )


def _seven_zip_executable() -> str:
    for candidate in ("7z", "7zz", "7za"):
        found = shutil.which(candidate)
        if found:
            return found
    raise RuntimeError("7z executable not found; install p7zip-full (or 7-Zip)")


def package_source_archives(
    *,
    repo_root: Path,
    output_dir: Path,
    project: str,
    tag: str,
    commit: str,
    checksum_path: Path | None = None,
) -> SourceArchiveSet:
    repo_root = Path(repo_root).resolve()
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    archives = archive_set(project, tag, output_dir)

    commit = str(commit).strip()
    if not commit:
        raise ValueError("commit must not be empty")
    subprocess.run(
        ["git", "rev-parse", "--verify", f"{commit}^{{commit}}"],
        cwd=repo_root,
        stdout=subprocess.DEVNULL,
        check=True,
    )

    for path in archives.paths:
        path.unlink(missing_ok=True)

    with tempfile.TemporaryDirectory(prefix="source-archive-") as temp_dir:
        temp = Path(temp_dir)
        tar_path = temp / "source.tar"
        stage = temp / "stage"
        stage.mkdir()

        _git_archive(
            repo_root,
            commit=commit,
            archive_format="zip",
            root_name=archives.root_name,
            destination=archives.zip,
        )
        _git_archive(
            repo_root,
            commit=commit,
            archive_format="tar",
            root_name=archives.root_name,
            destination=tar_path,
        )

        with tar_path.open("rb") as source, archives.tar_zstd.open("wb") as output:
            zstd.ZstdCompressor(level=19, threads=-1).copy_stream(source, output)

        with tarfile.open(tar_path, mode="r:") as source_tar:
            source_tar.extractall(stage, filter="data")

        subprocess.run(
            [
                _seven_zip_executable(),
                "a",
                "-t7z",
                "-mx=9",
                str(archives.seven_zip),
                archives.root_name,
            ],
            cwd=stage,
            stdout=subprocess.DEVNULL,
            check=True,
        )

    if checksum_path is not None:
        append_checksum_rows(Path(checksum_path), archives.paths)
    return archives


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Package the exact tracked Git tree as ZIP, TAR.ZST and 7Z release assets."
    )
    parser.add_argument("--project", required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--checksums", type=Path)
    return parser


def main() -> None:
    args = _parser().parse_args()
    archives = package_source_archives(
        repo_root=args.repo_root,
        output_dir=args.output_dir,
        project=args.project,
        tag=args.tag,
        commit=args.commit,
        checksum_path=args.checksums,
    )
    for kind, path in zip(_ARCHIVE_KINDS, archives.paths, strict=True):
        print(f"{kind}: {path.name} {path.stat().st_size} B {sha256_file(path)}")


if __name__ == "__main__":
    main()
