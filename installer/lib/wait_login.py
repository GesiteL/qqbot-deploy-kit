"""Wait for NapCat to write onebot11_<uin>.json after a successful QR login."""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import qqbot_lib as lib  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", required=True)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--remind", type=int, default=120)
    args = parser.parse_args()
    target = lib.target_from_args(args.target)
    config_dir = lib.onebot_config_dir(target)
    qr = target / "runtime" / "napcat" / "napcat" / "cache" / "qrcode.png"
    uin_file = target / "runtime" / ".install" / "uin.txt"
    start = time.time()
    next_remind = start
    last_qr_note = False
    try:
        print("", flush=True)
        print("  请用手机 QQ 扫 NapCat 黑色窗口里的二维码（用小号，不要用快速登录大号）。", flush=True)
        print(f"  二维码图片：{qr}", flush=True)
        print("  扫码完成后本窗口会自动继续；最多等待 10 分钟。", flush=True)
        while True:
            now = time.time()
            if now - start > args.timeout:
                raise lib.InstallError(
                    "等了 10 分钟还没检测到扫码登录。请确认：手机 QQ 扫的是 NapCat 窗口/图片里的码；"
                    "扫码后手机上点了确认；网络正常。关闭本窗口后重新运行安装器即可重试（已装组件不会重下）。"
                )
            if not last_qr_note and qr.exists():
                print(f"  二维码已生成：{qr}", flush=True)
                last_qr_note = True
            if now >= next_remind:
                print("  [提醒] 请扫黑色 NapCat 窗口里的二维码；如果窗口最小化了，点任务栏的 NapCat 窗口，"
                      f"或打开图片：{qr}", flush=True)
                next_remind = now + args.remind
            candidates = []
            if config_dir.exists():
                for path in config_dir.glob("onebot11_*.json"):
                    m = re.fullmatch(r"onebot11_(\d{5,11})\.json", path.name)
                    if m:
                        candidates.append((path.stat().st_mtime, path, m.group(1)))
            if candidates:
                candidates.sort(reverse=True)
                mtime, path, uin = candidates[0]
                if mtime + 2 < start:
                    time.sleep(2)
                    continue
                try:
                    data = json.loads(path.read_text(encoding="utf-8-sig"))
                except Exception:
                    time.sleep(2)
                    continue
                if not isinstance(data, dict):
                    time.sleep(2)
                    continue
                uin_file.parent.mkdir(parents=True, exist_ok=True)
                uin_file.write_text(uin, encoding="utf-8")
                print("  检测到登录配置，扫码登录完成。", flush=True)
                return 0
            time.sleep(2)
    except lib.InstallError as exc:
        print(f"[错误] {exc}", flush=True)
        return 2
    except KeyboardInterrupt:
        print("[错误] 已取消等待扫码。", flush=True)
        return 2
    except Exception as exc:  # noqa: BLE001
        print(f"[错误] 等待扫码时出现未预期问题：{exc.__class__.__name__}: {exc}", flush=True)
        return 2


if __name__ == "__main__":
    sys.exit(main())
