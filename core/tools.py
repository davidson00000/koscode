# core/tools.py
import subprocess, time, re
from pathlib import Path

def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)

def save_text(path: Path, text: str):
    ensure_dir(path.parent)
    path.write_text(text, encoding="utf-8")

def _strip_code_fence(patch_text: str) -> str:
    m = re.search(r"```(?:diff)?\s*(.*?)```", patch_text, flags=re.DOTALL | re.IGNORECASE)
    return m.group(1).strip() if m else patch_text.strip()

def _strip_git_headers(patch_text: str) -> str:
    lines = []
    for line in patch_text.splitlines():
        if line.startswith("diff --git ") or line.startswith("index "):
            continue
        lines.append(line)
    return "\n".join(lines)

def apply_unified_diff(patch_text: str, root: str = "workspace"):
    """
    - コードフェンスを剥がす
    - パスを正規化（./workspace/ や a/ b/ を削除）
    - 変更対象のホワイトリスト検査（app.py のみ許可）
    - OKなら patch -p0 -d <root> で適用
    """
    stamp = int(time.time())
    patch_raw = Path("artifacts") / f"patch_{stamp}.diff"

    def _normalize_paths(s: str) -> str:
        lines = []
        for ln in s.splitlines():
            if ln.startswith("--- "):
                path = ln[4:].split()[0]
                path = path.replace("./workspace/", "")
                path = path.replace("a/", "")
                ln = f"--- {path}"
            elif ln.startswith("+++ "):
                path = ln[4:].split()[0]
                path = path.replace("./workspace/", "")
                path = path.replace("b/", "")
                ln = f"+++ {path}"
            lines.append(ln)
        return "\n".join(lines)

    cleaned = _strip_code_fence(patch_text)
    cleaned = _normalize_paths(cleaned)

    # ホワイトリスト: app.py のみ
    allowed = {"app.py"}
    targets = []
    for ln in cleaned.splitlines():
        if ln.startswith(("--- ", "+++ ")):
            p = ln[4:].split()[0]
            if p != "/dev/null":
                targets.append(p)
    # 許可外が混ざっていたら適用しない
    if any(t not in allowed for t in targets):
        save_text(Path("artifacts") / f"patch_{stamp}.reject.log",
                  "disallowed paths: " + ", ".join(sorted(set(t for t in targets if t not in allowed))))
        save_text(patch_raw, cleaned)
        return False, "patch contains disallowed paths"

    save_text(patch_raw, cleaned)
    abs_patch = patch_raw.resolve()
    res = subprocess.run(
        ["patch", "-p0", "-d", root, "-i", str(abs_patch)],
        capture_output=True, text=True
    )
    log = res.stdout + "\n" + res.stderr
    save_text(Path("artifacts") / f"patch_{stamp}.log", log)
    return res.returncode == 0, log



def run_in_venv(cmd: str, cwd: str = "workspace", timeout: int = 120):
    """プロジェクト直下にある .venv を有効化して実行"""
    shell = ["bash", "-lc", f"source ../.venv/bin/activate && {cmd}"]
    try:
        res = subprocess.run(shell, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        code, so, se = res.returncode, res.stdout, res.stderr
    except subprocess.TimeoutExpired as e:
        code = 124
        so = e.stdout or ""
        se = (e.stderr or "") + f"\n[timeout] command exceeded {timeout}s: {cmd}\n"
    stamp = int(time.time())
    save_text(Path("artifacts") / f"run_{stamp}.out", so)
    save_text(Path("artifacts") / f"run_{stamp}.err", se)
    return code, so, se
