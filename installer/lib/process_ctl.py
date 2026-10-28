"""Stop QQBot processes under the install root and optionally wait for ports."""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import qqbot_lib as lib  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", required=True)
    parser.add_argument("--which", choices=("all", "napcat", "astrbot"), default="all")
    parser.add_argument("--wait-ports", default="")
    parser.add_argument("--timeout", type=int, default=15)
    args = parser.parse_args()
    try:
        target = lib.target_from_args(args.target)
        count = lib.stop_processes(target, args.which)
        print(f"  已停止 {count} 个进程（范围：{args.which}）。", flush=True)
        ports = [int(p) for p in args.wait_ports.split(",") if p.strip()]
        if ports:
            deadline = time.time() + args.timeout
            while time.time() < deadline:
                listeners = lib.get_listeners(ports)
                if not listeners:
                    print(f"  端口已释放：{ports}", flush=True)
                    return 0
                time.sleep(1)
            busy = sorted({int(x["port"]) for x in lib.get_listeners(ports)})
            raise lib.InstallError(
                f"端口仍被占用：{busy}。可能是旧机器人或其他软件还在运行。"
                "请关闭旧机器人（或重启电脑）后重新运行安装器。"
            )
        return 0
    except lib.InstallError as exc:
        print(f"[错误] {exc}", flush=True)
        return 2
    except Exception as exc:  # noqa: BLE001
        print(f"[错误] 停止进程时出现未预期问题：{exc.__class__.__name__}: {exc}", flush=True)
        return 2


if __name__ == "__main__":
    sys.exit(main())
