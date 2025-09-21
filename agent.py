# agent.py
import typer
from core.loop import cmd_plan, cmd_code, cmd_run, cmd_loop

app = typer.Typer(help="koscode agent CLI")

@app.command()
def plan(task: str = "tasks/sample.yaml"):
    """プラン生成（artifacts/plan.yaml へ保存）"""
    cmd_plan(task)

@app.command()
def code(instruction: str = typer.Argument(...)):
    """手動で指示してパッチを当てる"""
    cmd_code(instruction)

@app.command()
def run(cmd: str = typer.Argument(...)):
    """workspace で任意コマンドを実行"""
    cmd_run(cmd)

@app.command()
def loop(task: str = "tasks/sample.yaml", max_iters: int = 10):
    """自己修復ループ"""
    cmd_loop(task, max_iters)

if __name__ == "__main__":
    app()
