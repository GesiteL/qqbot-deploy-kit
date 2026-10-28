"""Port, connection, and model connectivity checks for the QQBot installer."""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import qqbot_lib as lib  # noqa: E402


def wait_ports(args) -> int:
    ports = [int(p) for p in args.ports.split(",") if p.strip()]
    print(f"  等待 127.0.0.1:{','.join(str(p) for p in ports)} ...", flush=True)
    if lib.wait_connect(ports, args.timeout):
        print("  端口已就绪。", flush=True)
        return 0
    raise lib.InstallError(f"等待 {args.timeout} 秒后端口仍未就绪：{ports}")


def assert_connection(args) -> int:
    deadline = time.time() + args.timeout
    while time.time() < deadline:
        if lib.get_established(3001):
            print("  3001 已出现 ESTABLISHED（NapCat 已连上 AstrBot）。", flush=True)
            return 0
        time.sleep(1)
    raise lib.InstallError(
        "NapCat 没有连上 AstrBot（3001 没有 ESTABLISHED）。"
        "常见原因：OneBot token 不一致、NapCat 未登录、或端口被别的程序占用。"
    )


def ports(args) -> int:
    listeners = lib.get_listeners(lib.PORTS_ALL)
    by_port: dict[int, list[dict]] = {p: [] for p in lib.PORTS_ALL}
    for item in listeners:
        try:
            by_port.setdefault(int(item["port"]), []).append(item)
        except Exception:
            continue
    bad = []
    for item in listeners:
        if not lib.is_loopback(str(item.get("address", ""))):
            bad.append(item)
    missing = [p for p in lib.PORTS_REQUIRED if not by_port.get(p)]
    print("  端口状态：", flush=True)
    for p in lib.PORTS_ALL:
        entries = by_port.get(p) or []
        if entries:
            addrs = ", ".join(sorted({str(x.get("address")) for x in entries}))
            print(f"    {p}: 监听 {addrs}", flush=True)
        else:
            print(f"    {p}: 未监听", flush=True)
    established = lib.get_established(3001)
    print(f"    3001 ESTABLISHED: {len(established)} 条", flush=True)
    if bad:
        raise lib.InstallError("有服务监听在非本机地址（不是 127.0.0.1），已停止。请把 install.log 发给交付方。")
    if missing:
        raise lib.InstallError(f"必需端口没有监听：{missing}")
    if not established:
        raise lib.InstallError("3001 没有 ESTABLISHED，NapCat 与 AstrBot 没有连上。")
    print("  四端口检查通过：仅本机监听，3001 已连接。", flush=True)
    return 0


def llm(args) -> int:
    print("  正在做一次最小模型调用（不显示 Key）...", flush=True)
    status, reason = lib.llm_probe(Path(args.target), timeout=args.timeout)
    if status == 200:
        print("  模型连通性：HTTP 200。", flush=True)
        return 0
    if status in (401, 403):
        raise lib.InstallError("模型 Key 无效或没有权限（HTTP {}）。请检查 Key/额度后重试。".format(status))
    if status == 404:
        raise lib.InstallError(
            "模型地址返回 404。中转站地址通常要以 /v1 结尾（例如 https://example.com/v1）；"
            "请核对后重新运行安装器。"
        )
    if status == 429:
        raise lib.InstallError("模型服务返回 429（限流/额度不足）。请稍后重试或检查中转站额度。")
    if status == 0:
        raise lib.InstallError(f"连接模型服务失败：{reason}。请检查网络、代理或中转站地址。")
    raise lib.InstallError(f"模型调用失败：HTTP {status}（{reason}）。请检查中转站地址与 Key。")


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("wait")
    p.add_argument("--ports", required=True)
    p.add_argument("--timeout", type=int, default=90)
    p = sub.add_parser("assert-connection")
    p.add_argument("--timeout", type=int, default=60)
    p = sub.add_parser("ports")
    p = sub.add_parser("llm")
    p.add_argument("--target", required=True)
    p.add_argument("--timeout", type=int, default=60)
    args = parser.parse_args()
    try:
        if args.command == "wait":
            return wait_ports(args)
        if args.command == "assert-connection":
            return assert_connection(args)
        if args.command == "ports":
            return ports(args)
        if args.command == "llm":
            return llm(args)
        raise lib.InstallError("未知命令")
    except lib.InstallError as exc:
        print(f"[错误] {exc}", flush=True)
        return 2
    except Exception as exc:  # noqa: BLE001
        print(f"[错误] 验证阶段出现未预期问题：{exc.__class__.__name__}: {exc}", flush=True)
        return 2


if __name__ == "__main__":
    sys.exit(main())
