#!/usr/bin/env python3
"""Cross-platform smoke test for roblox-gamedev. Runs on macOS and Windows, locally and in CI."""
import ast
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "roblox-gamedev" / "skills"
PY = sys.executable
WINDOWS = sys.platform == "win32"
failures = []


def run(label, cmd, cwd=None, ok_codes=(0,), expect=None):
    r = subprocess.run([str(c) for c in cmd], cwd=cwd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=300)
    out = r.stdout + r.stderr
    bad = r.returncode not in ok_codes or "Traceback" in out or (expect and expect not in out)
    print(f"{'FAIL' if bad else 'ok  '}  {label}", flush=True)
    if bad:
        failures.append(label)
        print(f"      exit {r.returncode}\n" + "\n".join("      " + l for l in out.splitlines()[-25:]))
    return r


def parse_all():
    bad = []
    for f in ROOT.rglob("*.py"):
        try:
            ast.parse(f.read_text(encoding="utf-8"))
        except SyntaxError as e:
            bad.append(f"{f}: {e}")
    print(f"{'FAIL' if bad else 'ok  '}  parse every script", flush=True)
    failures.extend(bad)


def main():
    parse_all()
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        g = ROOT / "create-roblox-game" / "scripts"
        run("check_setup", [PY, ROOT / "roblox-skills-setup/scripts/check_setup.py"], cwd=tmp)
        run("preflight", [PY, g / "preflight.py"], cwd=tmp, ok_codes=(0, 1))
        run("place_state", [PY, g / "place_state.py", "--json"], cwd=tmp)
        run("recover_mcp", [PY, g / "recover_mcp.py"], cwd=tmp, ok_codes=(0, 1), expect="robloxstudio-mcp servers")

        m = ROOT / "roblox-map"
        run("map prove", [PY, "scripts/prove.py", "minimal"], cwd=m, ok_codes=(0, 1), expect="RESULT:")
        run("map plan", [PY, "scripts/plan.py", "minimal", "--prove", "-o", tmp / "plan.png"], cwd=m, ok_codes=(0, 1))
        u = ROOT / "roblox-ui"
        run("ui build", [PY, "scripts/ui_build.py", "examples/coin_hud.json", "--out", tmp / "ui"], cwd=u)
        run("ui verify", [PY, "scripts/verify_ui.py", "examples/coin_hud.json"], cwd=u)

        game = tmp / "Smoke Game"
        run("new_game", [PY, g / "new_game.py", "Smoke Game", "--dir", game], cwd=tmp, expect="wally install")
        if all(shutil.which(x) for x in ("wally", "rojo", "lune", "selene", "stylua")):
            run("wally install", ["wally", "install"], cwd=game)
            run("code gates", [PY, ROOT / "roblox-code/scripts/check.py"], cwd=game, expect="all gates green")
        else:
            print("skip  code gates: toolchain not on PATH", flush=True)

        t_scripts = ROOT / "roblox-trailer" / "scripts"
        run("trailer windows", [PY, t_scripts / "record.py", "windows"], cwd=tmp, expect="screen")
        run("trailer fonts", [PY, t_scripts / "edit.py", "fonts"], cwd=tmp)
        if shutil.which("ffmpeg"):
            frames = tmp / "frames"
            frames.mkdir()
            from PIL import Image
            for i in range(4):
                Image.new("RGB", (64, 64), (i * 60, 0, 0)).save(frames / f"{i}.png")
            run("trailer stitch", [PY, t_scripts / "record.py", "stitch", "s1", "--out", tmp / "tr", "--frames", frames], cwd=tmp)
            if WINDOWS:
                clip = tmp / "clip.mov"
                code = ("import sys; sys.path.insert(0, sys.argv[1]); import record, subprocess; "
                        "sys.exit(subprocess.run(record.record_command(1.0, [0, 0, 320, 240], sys.argv[2])).returncode)")
                run("trailer gdigrab", [PY, "-c", code, t_scripts, clip], cwd=tmp)
                if not clip.exists():
                    failures.append("gdigrab wrote no file")

    print(f"\n{len(failures)} failure(s)" if failures else "\nall smoke checks passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
