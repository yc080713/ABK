#!/usr/bin/env python3
"""从 SukiSU_patch 的 patch_linux 里提取内嵌的 x86_64 kptools。

背景
----
ShirkNeko/SukiSU_patch 提供三个预编译工具：

* ``kpm/patch_linux``   —— x86_64 wrapper，Linux 构建机上可直接运行（ABK 用它对 Image 打补丁）
* ``kpm/patch_android`` —— aarch64 wrapper，手机上用
* ``kpm/kptools``       —— **aarch64 + /system/bin/linker64（Android 动态链接）**，
  在 x86_64 的 GitHub runner 上会直接 ``cannot execute binary file: Exec format error``

而 ``patch_linux`` 这个 wrapper 的 ``main.cpp`` 把 kptools 参数写死成
``{"-p","-s","123","-i","Image","-k",<kpimg>,"-o","oImage"}`` 并且不解析自己的 argv，
所以 ``./patch -s "<密码>"`` 传进去的超级密码会被丢弃，内核里始终是默认的 ``123``。

CMakeLists 用 ``xxd -i`` 把 ``res/kptools-linux``（x86_64 ELF）**原样**内嵌进
``patch_linux``（只有 kpimg 做了 XOR 0xAA）。因此本脚本按 ELF 头把这份 x86_64 kptools
抠出来，用 ``kptools -r -s <密码> -i oImage -o oImage.rekey`` 重置超级密码 ——
和 wrapper 用的是同一个版本，不需要额外下载或编译工具链。

用法
----
    python3 extract-kptools.py <patch_linux> <输出文件>

失败时返回非 0，并把原因写到 stderr。
"""

import struct
import sys
from pathlib import Path

EM_X86_64 = 0x3E


def elf_image_size(data: bytes, off: int) -> int:
    """返回从 off 开始的 ELF 完整长度（程序头/节头覆盖范围的最大值）。"""
    e_phoff, = struct.unpack_from("<Q", data, off + 32)
    e_shoff, = struct.unpack_from("<Q", data, off + 40)
    e_phentsize, e_phnum = struct.unpack_from("<HH", data, off + 54)
    e_shentsize, e_shnum = struct.unpack_from("<HH", data, off + 58)

    size = 0
    for n in range(e_phnum):
        ph = off + e_phoff + n * e_phentsize
        if ph + e_phentsize > len(data):
            return 0
        p_offset, = struct.unpack_from("<Q", data, ph + 8)
        p_filesz, = struct.unpack_from("<Q", data, ph + 32)
        size = max(size, p_offset + p_filesz)
    if e_shoff and e_shnum:
        size = max(size, e_shoff + e_shentsize * e_shnum)
    return size


def find_embedded_kptools(data: bytes):
    """找出内嵌的 x86_64 kptools，返回 (offset, size)；找不到返回 None。"""
    best = None
    for off in range(len(data) - 64):
        if data[off:off + 4] != b"\x7fELF":
            continue
        if data[off + 4] != 2 or data[off + 5] != 1:  # 64 位、小端
            continue
        if off == 0:  # 外层 wrapper 自己
            continue
        machine, = struct.unpack_from("<H", data, off + 18)
        if machine != EM_X86_64:
            continue
        e_type, = struct.unpack_from("<H", data, off + 16)
        if e_type not in (2, 3):  # EXEC / DYN
            continue
        size = elf_image_size(data, off)
        if size <= 0 or off + size > len(data):
            continue
        if b"--reset-skey" not in data[off:off + size]:
            continue  # 不是 kptools
        if best is None or size > best[1]:
            best = (off, size)
    return best


def main(argv) -> int:
    if len(argv) != 3:
        print(__doc__.strip().splitlines()[-1], file=sys.stderr)
        print("usage: extract-kptools.py <patch_linux> <output>", file=sys.stderr)
        return 2

    src, dst = Path(argv[1]), Path(argv[2])
    if not src.is_file():
        print(f"错误：找不到 {src}", file=sys.stderr)
        return 1

    data = src.read_bytes()
    found = find_embedded_kptools(data)
    if not found:
        print(
            "错误：在 patch_linux 中找不到内嵌的 x86_64 kptools"
            "（上游可能改了打包方式，可改用 tools/ 源码编译 kptools）",
            file=sys.stderr,
        )
        return 1

    off, size = found
    dst.write_bytes(data[off:off + size])
    dst.chmod(0o755)
    print(f"extracted embedded x86_64 kptools: offset={off:#x} size={size} -> {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
