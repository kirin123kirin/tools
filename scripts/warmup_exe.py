"""全コマンドのexeを1回ずつ起動し、EDR/DLP等のセキュリティ製品による
初回スキャンを事前に済ませておくためのウォームアップスクリプト。

各exeは引数なしで実行するため、多くはargparseのエラーで即終了するが、
目的は処理の成功ではなく実行ファイル自体へのファイルアクセスを発生させる
ことなので問題ない。

使い方:
    python scripts/warmup_exe.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys

from workpytools.cli import _discover_processors
from workpytools.common.help_gen import standalone_entry_point_name


def main() -> int:
    processors = _discover_processors()
    names = sorted({standalone_entry_point_name(name) for name in processors})

    missing: list[str] = []
    for name in names:
        exe = shutil.which(f"{name}.exe") or shutil.which(name)
        if exe is None:
            missing.append(name)
            continue
        print(f"起動中: {exe}")
        subprocess.run([exe], capture_output=True, timeout=60)

    print(f"\n{len(names) - len(missing)}個のexeを起動しました")
    if missing:
        print(f"見つからなかったexe: {', '.join(missing)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
