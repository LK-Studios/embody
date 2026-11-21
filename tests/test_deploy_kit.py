"""The single-world deploy kit a new host starts from: deploy/start.sh picks the world (EMBODY_WORLD by name or by path,
deploy/world from the stage, else the only folder under worlds/) and stops with a clear line when there is none, and
tools/stage_deploy.py ships a world that lives only on disk under worlds/ (git ignores it) or a sample by its path."""

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())
SH = shutil.which("sh")

BUILD = 'WORLD = {{"id": "{id}", "name": "{id}", "seed": 0, "requires": []}}\n'


def _write(p: Path, text: str) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8", newline="\n")
    return p


# ---- deploy/start.sh ---------------------------------------------------------------


def _start(tmp: Path, env: dict[str, str] | None = None, known: str = "[]") -> tuple[int, str, list[str]]:
    """Run a copy of start.sh in tmp with `embody` stubbed: it logs its arguments and answers `--json worlds` with
    `known`. Returns the exit code, stderr and the embody calls."""
    shutil.copy(REPO / "deploy" / "start.sh", _write(tmp / "deploy" / "start.sh", ""))
    bin_ = tmp / "bin"
    log = tmp / "calls.log"
    _write(bin_ / "embody", '#!/bin/sh\necho "$*" >> "$STUB_LOG"\n'
                            'if [ "$1" = "--json" ]; then echo "$STUB_KNOWN"; fi\n'
                            'case "$*" in *serve*) echo "env world=$EMBODY_WORLD site=${EMBODY_SITE:-}" >> "$STUB_LOG";; esac\n')
    _write(bin_ / "python", f'#!/bin/sh\nexec "{Path(sys.executable).as_posix()}" "$@"\n')
    for f in ("embody", "python"):
        (bin_ / f).chmod(0o755)
    e = {k: v for k, v in os.environ.items() if not k.startswith("EMBODY_")}
    e.update({"PATH": str(bin_) + os.pathsep + e.get("PATH", ""), "STUB_LOG": str(log), "STUB_KNOWN": known,
              "EMBODY_DB": "/data/embody.db", "PORT": "8123"}, **(env or {}))
    r = subprocess.run([SH, "deploy/start.sh"], cwd=tmp, env=e, capture_output=True, text=True, timeout=60)
    calls = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
    return r.returncode, r.stderr, calls


needs_sh = pytest.mark.skipif(SH is None, reason="no POSIX sh on PATH")


@needs_sh
def test_no_world_stops_with_a_clear_line(tmp_path):
    _write(tmp_path / "worlds" / "put_worlds_here.txt", "")
    code, err, calls = _start(tmp_path)
    assert code == 64
    assert "no world to host" in err and "EMBODY_WORLD=examples/ferry-at-dusk" in err
    assert calls == []


@needs_sh
def test_the_only_world_under_worlds_is_built_then_served(tmp_path):
    _write(tmp_path / "worlds" / "mine" / "build.py", BUILD.format(id="mine"))
    code, err, calls = _start(tmp_path)
    assert code == 0, err
    assert calls[1] == "--author load mine --hosted"
    assert calls[-2].startswith("--author serve --http --host 0.0.0.0 --port 8123")
    assert calls[-1] == "env world=mine site="


@needs_sh
def test_several_worlds_ask_which(tmp_path):
    for w in ("one", "two"):
        _write(tmp_path / "worlds" / w / "build.py", BUILD.format(id=w))
    code, err, _ = _start(tmp_path)
    assert code == 64 and "which world" in err and "one two" in err


@needs_sh
def test_a_sample_path_loads_by_path_and_renews_by_its_manifest_id(tmp_path):
    _write(tmp_path / "examples" / "sample" / "build.py", BUILD.format(id="the-sample"))
    _write(tmp_path / "examples" / "sample" / "site" / "index.html", "<p>the sample</p>")
    code, err, calls = _start(tmp_path, {"EMBODY_WORLD": "examples/sample"})
    assert code == 0, err
    assert calls[1] == "--author load examples/sample --hosted"
    assert calls[-1] == "env world=the-sample site=examples/sample/site"  # serve gets the id, not the path
    code, err, calls = _start(tmp_path, {"EMBODY_WORLD": "examples/sample"}, known='[{"id": "the-sample"}]')
    assert code == 0, err
    assert "--author --world the-sample load examples/sample --upgrade --hosted" in calls


@needs_sh
def test_the_staged_choice_wins_over_the_folder_scan(tmp_path):
    for w in ("one", "two"):
        _write(tmp_path / "worlds" / w / "build.py", BUILD.format(id=w))
    _write(tmp_path / "deploy" / "world", "two\n")
    code, err, calls = _start(tmp_path)
    assert code == 0, err
    assert calls[1] == "--author load two --hosted"


@needs_sh
def test_a_missing_world_names_where_it_looked(tmp_path):
    code, err, calls = _start(tmp_path, {"EMBODY_WORLD": "glass-reach"})
    assert code == 64 and "no world at worlds/glass-reach" in err
    assert calls == []


# ---- tools/stage_deploy.py ---------------------------------------------------------


@pytest.fixture
def stage(tmp_path, monkeypatch):
    """stage_deploy pointed at a small engine repository in tmp: deploy/, worlds/ with only the placeholder tracked,
    and a sample under examples/."""
    spec = importlib.util.spec_from_file_location("stage_deploy", REPO / "tools" / "stage_deploy.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    root = tmp_path / "engine"
    _write(root / "deploy" / "start.sh", "#!/bin/sh\n")
    _write(root / "worlds" / "put_worlds_here.txt", "")
    _write(root / ".gitignore", "worlds/*\n!worlds/put_worlds_here.txt\n*.db\n")
    _write(root / "examples" / "sample" / "build.py", BUILD.format(id="sample"))
    git = ["git", "-c", "user.email=test@example.com", "-c", "user.name=test", "-c", "commit.gpgsign=false"]
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run([*git, "commit", "-q", "-m", "engine"], cwd=root, check=True)
    monkeypatch.setattr(mod, "ROOT", root)
    return mod, root, tmp_path / "stage"


def test_a_world_only_on_disk_ships_without_its_working_files(stage):
    mod, root, out = stage
    w = root / "worlds" / "mine"
    _write(w / "build.py", BUILD.format(id="mine"))
    _write(w / "scripts" / "door.py", "# a script\n")
    _write(w / "private" / "codes.txt", "lock words\n")
    _write(w / "mirror" / "state.json", "{}")
    _write(w / "embody.db", "")
    _write(w / ".embody.json", "{}")
    assert mod.main(["--world", "mine", "--out", str(out)]) == 0
    got = out / "worlds" / "mine"
    assert (got / "build.py").is_file() and (got / "scripts" / "door.py").is_file()
    assert (got / "private" / "codes.txt").is_file()
    assert not (got / "mirror").exists() and not (got / "embody.db").exists() and not (got / ".embody.json").exists()
    assert (out / "deploy" / "world").read_text(encoding="utf-8") == "mine\n"
    assert not (out / "deploy" / "worlds").exists()


def test_a_sample_ships_by_its_path(stage):
    mod, root, out = stage
    assert mod.main(["--world", "examples\\sample", "--out", str(out)]) == 0
    assert (out / "examples" / "sample" / "build.py").is_file()
    assert (out / "deploy" / "world").read_text(encoding="utf-8") == "examples/sample\n"


def test_a_world_that_is_nowhere_is_refused(stage):
    mod, root, out = stage
    with pytest.raises(SystemExit, match="no world nope"):
        mod.main(["--world", "nope", "--out", str(out)])
    with pytest.raises(SystemExit, match="no world at examples/nope"):
        mod.main(["--world", "examples/nope", "--out", str(tmp := out.with_name("stage2"))])
    assert mod.main(["--world", "examples/sample", "--world", "mine", "--out", str(tmp.with_name("s3"))]) == 2


def test_two_worlds_still_make_a_hub(stage):
    mod, root, out = stage
    for w in ("one", "two"):
        _write(root / "worlds" / w / "build.py", BUILD.format(id=w))
    assert mod.main(["--world", "one", "--world", "two", "--out", str(out)]) == 0
    assert (out / "deploy" / "worlds").read_text(encoding="utf-8") == "one,two\n"
    assert not (out / "deploy" / "world").exists()
