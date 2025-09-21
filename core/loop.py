# core/loop.py
# -*- coding: utf-8 -*-

from pathlib import Path
import yaml

from core.llm import ollama_chat
from core.roles import SYSTEM_PLANNER, SYSTEM_CODER, SYSTEM_CRITIC
from core.tools import save_text, apply_unified_diff, run_in_venv, ensure_dir

# 設定の読込
CFG = yaml.safe_load(Path("config.yaml").read_text(encoding="utf-8"))


def _get(section: str, key: str, default):
    """config の存在しないキーにデフォルトを入れるヘルパ"""
    sec = CFG.get(section) or {}
    return sec.get(key, default)


# --- Plan --------------------------------------------------------------------
def cmd_plan(task_path: str):
    t = yaml.safe_load(Path(task_path).read_text(encoding="utf-8"))
    prompt_parts = [
        "# GOAL",
        str(t.get("goal", "")),
        "",
        "# CONSTRAINTS",
        str(t.get("constraints", "")),
        "",
        "# ACCEPTANCE",
        str(t.get("acceptance", "")),
        "必ず YAML のみ出力。",
    ]
    prompt = "\n".join(prompt_parts)

    messages = [
        {"role": "system", "content": SYSTEM_PLANNER},
        {"role": "user", "content": prompt},
    ]
    plan_text = ollama_chat(
        _get("planner", "model", "llama3.2:3b-instruct-q4_K_M"),
        messages,
        _get("planner", "temperature", 0.2),
        _get("planner", "num_ctx", 1024),
        _get("planner", "num_predict", 128),
        _get("planner", "timeout", 120),
    )
    save_text(Path(CFG["artifacts"]) / "plan.yaml", plan_text)
    print("[bold green]Plan saved -> artifacts/plan.yaml[/bold green]")


# --- Code --------------------------------------------------------------------
def cmd_code(instruction: str):
    # 現状スナップショット
    ap = (
        Path("workspace/app.py").read_text(encoding="utf-8")
        if Path("workspace/app.py").exists()
        else "(missing)"
    )
    tp = (
        Path("workspace/tests/test_basic.py").read_text(encoding="utf-8")
        if Path("workspace/tests/test_basic.py").exists()
        else "(missing)"
    )

    # プロンプトは list -> join（f文字列は使わない）
    lines = [
        "作業ディレクトリは ./workspace です。",
        "以下の制約で unified diff のみを出力（説明文は一切禁止）：",
        "- 変更可能ファイルは app.py のみ（tests/* の変更や追加は厳禁）。",
        "- 既存の main() の戻り値・挙動は変更禁止。必要な関数を新規追加してテストを通すこと。",
        "- a/ b/ を付けない相対パスを用いること。新規ファイルは --- /dev/null を使用。",
        "- diff --git や index 行は出力しないこと。",
        "- patch -p0 -d workspace で適用可能な形式にすること。",
        "",
        "現状の app.py:",
        "```python",
        ap,
        "```",
        "現状の tests/test_basic.py:",
        "```python",
        tp,
        "```",
        "",
        instruction,
    ]
    user_content = "\n".join(lines)

    messages = [
        {"role": "system", "content": SYSTEM_CODER},
        {"role": "user", "content": user_content},
    ]

    patch = ollama_chat(
        _get("coder", "model", "qwen2.5-coder:7b-instruct-q4_K_M"),
        messages,
        _get("coder", "temperature", 0.2),
        _get("coder", "num_ctx", 1024),
        _get("coder", "num_predict", 120),
        _get("coder", "timeout", 120),
    )
    save_text(Path("artifacts") / "last_patch.diff", patch)
    ok, _log = apply_unified_diff(patch, root=CFG["workspace"])
    print(
        "[bold green]Patch applied[/bold green]"
        if ok
        else "[bold red]Patch failed (see artifacts/*patch*.log)[/bold red]"
    )


# --- Run ---------------------------------------------------------------------
def cmd_run(cmd: str):
    code, so, se = run_in_venv(cmd, cwd=CFG["workspace"])
    print(f"[bold]exit={code}[/bold]\nSTDOUT:\n{so}\nSTDERR:\n{se}")
    return code


# --- Loop --------------------------------------------------------------------
def cmd_loop(task_path: str, max_iters: int = 10):
    ensure_dir(Path(CFG["workspace"]))
    ensure_dir(Path(CFG["artifacts"]))

    cmd_plan(task_path)

    for i in range(max_iters):
        print(f"[cyan]=== Iteration {i+1}/{max_iters} ===[/cyan]")

        # 事前に pytest。通っていたら即終了（無駄なパッチ防止）
        print("[yellow]Running tests (pre-check): PYTHONPATH=. pytest -q[/yellow]")
        code, _, _ = run_in_venv("PYTHONPATH=. pytest -q", cwd=CFG["workspace"])
        if code == 0:
            print("[bold green]All tests passed![/bold green]")
            break

        if i == 0:
            instruction = "テストを通すために app.py に必要最小限の変更（新規関数追加のみ）を加えなさい。"
        else:
            # 直近の失敗ログ末尾（長すぎる時は末尾2,000文字）
            err_files = sorted(Path("artifacts").glob("run_*.err"))
            last_err = err_files[-1].read_text(encoding="utf-8") if err_files else ""
            critic_user = "\n".join(
                [
                    "直近の失敗ログ:",
                    "```",
                    last_err[-2000:],
                    "```",
                    "テストを通すための最小の一手のみを日本語で。",
                ]
            )
            critic_messages = [
                {"role": "system", "content": SYSTEM_CRITIC},
                {"role": "user", "content": critic_user},
            ]
            instruction = ollama_chat(
                _get("planner", "model", "llama3.2:3b-instruct-q4_K_M"),
                critic_messages,
                _get("planner", "temperature", 0.2),
                _get("planner", "num_ctx", 1024),
                _get("planner", "num_predict", 64),
                _get("planner", "timeout", 120),
            )

        print("Calling Coder...")
        cmd_code(instruction)

        print("[yellow]Running tests (post-patch): PYTHONPATH=. pytest -q[/yellow]")
        code, _, _ = run_in_venv("PYTHONPATH=. pytest -q", cwd=CFG["workspace"])
        print(f"[magenta]pytest exit={code}[/magenta]")
        if code == 0:
            print("[bold green]All tests passed![/bold green]")
            break
    else:
        print("[bold red]Reached max iterations without passing tests.[/bold red]")
