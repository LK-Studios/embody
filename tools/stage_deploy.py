"""Stage a deploy: the engine's committed tree (git archive HEAD, so nothing uncommitted ships), each world from its own
repository's committed tree when it has one (worlds/<id> linked to a private repo), each world's site folder (which
stays out of git: its films are large and are the site's own), and the list of worlds the container hosts. Prints the
one command that deploys the stage.

    uv run python tools/stage_deploy.py --world glass-reach=D:/path/to/site
    uv run python tools/stage_deploy.py --world glass-reach=D:/sites/reach --world gossip-goblin \\
        --domain theglassreach.quest=glass-reach
    railway up <stage> --path-as-root --no-gitignore --ci

One world ships as before (deploy/start.sh serves it alone); two or more ship with deploy/worlds, and start.sh runs
`embody hub`: one server per world, each on its own database file. A world's `private/` folder (git-ignored: codes
and lock words its build reads) ships beside it. The site's own working files stay behind: dot-files, and the names
in SKIP (notes, sources, local tools). `--world W --site S` (the older form) still works for one world.
"""

import argparse
import io
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP = {"BRIEF.md", "README.md", "dev", "media-src", "node_modules"}


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True).stdout.strip()


def _untar(tar: bytes, dest: Path) -> None:
    with tarfile.open(fileobj=io.BytesIO(tar)) as t:
        t.extractall(dest, filter="data")


def stage_world(out: Path, wid: str, site: Path | None) -> str:
    """worlds/<wid> into the stage: from its own repository when it has one, else already there from the engine's tree.
    Returns a line on what it shipped."""
    src = ROOT / "worlds" / wid
    dest = out / "worlds" / wid
    top = _git(src, "rev-parse", "--show-toplevel") if src.is_dir() else ""
    own = bool(top) and Path(top).resolve() != ROOT.resolve()
    if own:
        if not _git(src, "rev-parse", "--verify", "-q", "HEAD"):
            raise SystemExit(f"{wid}: its repository ({top}) has no commits yet; commit the world, then stage")
        dirty = _git(src, "status", "--porcelain", "--untracked-files=no")
        if dirty:
            print(f"note: {wid}: uncommitted changes stay behind; the stage is its HEAD:\n{dirty}", file=sys.stderr)
        sub = Path(src.resolve()).relative_to(Path(top).resolve()).as_posix()
        tree = f"HEAD:{sub}" if sub != "." else "HEAD"
        shutil.rmtree(dest, ignore_errors=True)
        dest.mkdir(parents=True)
        _untar(subprocess.run(["git", "archive", "--format=tar", tree], cwd=top, capture_output=True, check=True).stdout,
               dest)
        what = f"{wid}: {_git(Path(top), 'rev-parse', '--short', 'HEAD')} from its own repository"
    elif (dest / "build.py").is_file():
        what = f"{wid}: from the engine's tree"
    else:
        raise SystemExit(f"no world {wid}: worlds/{wid} is neither in the engine's tree nor its own repository")
    private = src / "private"
    if private.is_dir():
        shutil.copytree(private, dest / "private", dirs_exist_ok=True)
        what += ", with its private/ folder"
    if site is not None:
        if not (site / "index.html").is_file():
            raise SystemExit(f"no index.html in {site}")
        shutil.copytree(site, dest / "site", dirs_exist_ok=True,
                        ignore=lambda d, names: [n for n in names if n.startswith(".") or n in SKIP])
        files = [p for p in (dest / "site").rglob("*") if p.is_file()]
        what += f", {len(files)} site files ({sum(p.stat().st_size for p in files) / 2**20:.1f} MiB)"
    return what


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--world", action="append", required=True,
                    help="a world to host, as ID or ID=SITE_FOLDER; repeat for more (the first is the default)")
    ap.add_argument("--site", help="the site folder, for a single --world given without one")
    ap.add_argument("--domain", action="append", default=[], help="HOST=WORLD for the hub's domain map; repeat")
    ap.add_argument("--out", help="where to stage (default: a fresh temporary folder)")
    a = ap.parse_args()
    worlds: list[tuple[str, Path | None]] = []
    for w in a.world:
        wid, _, site = w.partition("=")
        worlds.append((wid.strip(), Path(site).resolve() if site else None))
    if a.site:
        if len(worlds) != 1 or worlds[0][1] is not None:
            print("--site goes with one --world given without a site (or write --world ID=SITE)", file=sys.stderr)
            return 2
        worlds[0] = (worlds[0][0], Path(a.site).resolve())
    dirty = _git(ROOT, "status", "--porcelain", "--untracked-files=no")
    if dirty:
        print("note: uncommitted changes stay behind; the stage is HEAD:\n" + dirty, file=sys.stderr)
    out = Path(a.out) if a.out else Path(tempfile.mkdtemp(prefix="embody-stage-"))
    if out.exists() and any(out.iterdir()):
        print(f"{out} is not empty", file=sys.stderr)
        return 2
    out.mkdir(parents=True, exist_ok=True)
    _untar(subprocess.run(["git", "archive", "--format=tar", "HEAD"], cwd=ROOT, capture_output=True, check=True).stdout, out)
    lines = [stage_world(out, wid, site) for wid, site in worlds]
    if len(worlds) > 1 or a.domain:
        (out / "deploy" / "worlds").write_text(",".join(w for w, _ in worlds) + "\n", encoding="utf-8")
        (out / "deploy" / "domains").write_text(",".join(a.domain) + "\n", encoding="utf-8")
    print(f"staged {out}: the engine's HEAD ({_git(ROOT, 'rev-parse', '--short', 'HEAD')})")
    for line in lines:
        print("  " + line)
    if len(worlds) > 1 or a.domain:
        print(f"  hub: {', '.join(w for w, _ in worlds)}; domains {', '.join(a.domain) or '(none)'}")
    print(f"deploy: railway up \"{out}\" --path-as-root --no-gitignore --ci")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
