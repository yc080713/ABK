# patches/

本目录存放 ABK 构建流程在内核编译前应用的内核源码补丁。

## 0001-gunyah-fix-scm-vmid-gki-compat.patch

**用途**：修复骁龙 8 Gen 3 (SM8650) 上 Gunyah 的 SCM VMID 映射问题，使 DroidVM / crosvm
等虚拟化应用能正常创建虚拟机（症状：`No such device (os error 19)`、
`Out of memory (os error 12)`）。

**位置**：`drivers/virt/gunyah/gunyah_qcom.c`

**原理**：

- GKI 的 `gunyah_qcom.c` 在内存 share/reclaim 时把 `QCOM_SCM_VMID_HLOS` 硬编码为源 VMID；
- SM8650 上 Resource Manager 运行在独立 VM，VMID 大于 `QCOM_SCM_MAX_MANAGED_VMID (0x3F)`，
  硬编码 HLOS 会让 SCM assign 被拒绝；
- 补丁新增 `qcom_scm_map_vmid()` 映射助手，并改用 `gh_rm_get_vmid()` 取当前 VM 的真实
  self VMID，同时保留 reclaim 时恢复 HLOS 所有权。

补丁来自 [Yizhou147/Xiaomi14-8Gen3-Gunyah-Fix](https://github.com/Yizhou147/Xiaomi14-8Gen3-Gunyah-Fix)，
上游实现参考 [Andy312432/android_kernel_samsung_sm8650_gunyah](https://github.com/Andy312432/android_kernel_samsung_sm8650_gunyah)，
许可证 GPL-2.0（与本仓库一致）。

**适用版本**：`android14` / `6.1`，例如 `sub_level=138`、`os_patch_level=2025-06`
（对应 `kernel/common` 的 `refs/heads/deprecated/android14-6.1-2025-06`，commit `5929004f86ff`）。
已验证该补丁在上述 ref 上 `git apply --check` 通过（带少量行偏移）。

**如何启用**：

用专用入口 **Actions → 「内核构建 - SM8650 (8 Gen 3) Gunyah 修复」**
（`.github/workflows/kernel-sm8650-gunyah.yml`），它已经把 `android14` + `6.1` + `use_gunyah=true`
固定好，只需要选：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `sub_level` | `138` | 6.1 子版本号，如 `138` / `118`；与补丁基线一致时最稳 |
| `os_patch_level` | `2025-06` | 需与子版本对应（例如 `118` ↔ `2025-01`） |
| `gunyah_builtin_qcom_platform` | `true` | 写入 `CONFIG_GUNYAH_QCOM_PLATFORM=y`，必须开启补丁才会编译进 `Image` |
| `kernelsu_variant` / `kernelsu_branch` / `cancel_susfs` | `BakaSU` / `Stable(标准)` / `true` | 按需选择 |

> 为什么不放进 `kernel-custom`：该工作流的 `workflow_dispatch` 已经用满 GitHub 的
> 25 个 inputs 上限，再加输入会让整个文件校验失败
> （`you may only define up to 25 inputs for a workflow_dispatch event`）。
> `build.yml` 仍然保留 `use_gunyah` / `gunyah_builtin_qcom_platform` 两个 `workflow_call`
> 输入（`workflow_call` 没有 25 上限），其他工作流也可以直接按需传参。

### 为什么需要 `gunyah_builtin_qcom_platform`

GKI 的 `arch/arm64/configs/gki_defconfig` 默认是：

```
CONFIG_GUNYAH=y
# CONFIG_GUNYAH_QCOM_PLATFORM is not set
```

`gunyah_qcom.c` 只在 `CONFIG_GUNYAH_QCOM_PLATFORM` 启用时才会被编译，而本仓库的构建产物
只有内核 `Image`（boot / AnyKernel3 zip，不打包 `.ko`），所以：

- 只用 `use_gunyah=true`：补丁会写进源码，但 `gunyah_qcom.o` 不参与编译，**对镜像没有影响**；
- 再加上 `gunyah_builtin_qcom_platform=true`：写入 `CONFIG_GUNYAH_QCOM_PLATFORM=y`，
  补丁才会真正编进 `Image`。

> 上游仓库的说明提到：把 Gunyah Qualcomm 平台驱动强制内建（`=y`）后，曾在启动早期出现
> panic（第一屏无限重启），因此上游默认只打补丁、不动配置。本仓库把它做成显式开关，
> 默认关闭；开启前请先确认可回退（保留可用的 `boot.img` / fastboot 环境）。
