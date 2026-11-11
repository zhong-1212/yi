# CHANGELOG

## v1.0.2 — 2026-11-11

### 变更（仅文档，无功能改动）
- README 目录结构补上 `release.py`，并说明它的作用（归一 LF → 重算校验和 → 打包 → 解包自检）。
- 版本号与 Release 说明对齐到 v1.0.2。

### 本次错误与改进（复盘闭环）
- **发布顺序错误复发一次**：先归一 LF、又用 `write_text` 打补丁（把 CRLF 写回去），再算校验和 → 包内 `verify.py` 哈希对不上。根因是「改写文件」与「算校验和」的先后顺序没有固化。
- 修复方式：把顺序写死进 `release.py`（归一 → 算校验和 → **必须提交** → `git archive` → 解包自检 → 打印 sha256），并在 `verify.py` 里加 **SHA256SUMS 自检**——以后行尾漂移会在本地就 FAIL，不会等用户安装时才炸。
- 另：改名后 GitHub 的 License 识别一度显示为空，几分钟后自动恢复为 MIT（非缺陷，缓存延迟）。

## v1.0.1 — 2026-11-11

### 变更
- 项目改名：`yi`（中文名「易」）。仓库 `zhong-1212/fortune-suite` → `zhong-1212/yi`，发布物 `yi-1.0.1.zip`。
- 修正安装说明：zip 内**没有**顶层目录，原 `unzip ... && cd fortune-suite` 会失败；改为 `unzip ... -d yi && cd yi`（Windows 用 `Expand-Archive -DestinationPath yi`）。
- 说明：npm 的 `yi` 与 PyPI 的 `yi` 已被占用（0.1.0 / 0.0.7），本项目不发布到那两处；GitHub 同账号内 `yi` 可用。

### 本次错误与改进（复盘闭环）
- 发布时发现 8 个文件因 Python 在 Windows 写文本会转 CRLF，而 zip 经 `.gitattributes` 归一为 LF，导致 `SHA256SUMS` 与包内文件不一致、他人的完整性校验必失败 → 全仓统一 LF、重算校验和、重打资产，并用「下载包→解压→verify→install」全链路复验。
- 空仓库首次发布时 Git Data API 返回 409（`Git Repository is empty`）→ 先用 Contents API 落一个文件起仓，再整树提交。
- 教训：**发布物的字节一致性必须验到 sha256，不能只看"推成功"**；行尾是最隐蔽的差异源。

## v1.0.0 — 2026-11-11

首个公开版本：4 个带引擎的技能 + 1 个路由技能。

### 新增
- `fortune-hub` v1.0.0：五体系分诊（梅花/奇门/紫微/解梦/风水），含互斥判据、合参顺序、统一禁用表达清单。纯提示词，无脚本。
- `meihua-yishu`：梅花易数时间起卦（本卦/互卦/变卦、体用五行、64 卦全覆盖），脚本纯 stdlib + lunar-python。
- `ziwei-doushu`：紫微斗数排盘（安星/四化/格局/大限流年），引擎 x-iztro。
- `zhougong-jiemeng` v1.0.0：475 条梦象库（18 类目，古占 83.6%，其余标"推"），检索脚本纯 stdlib，五段式解读（拆象—古断—取象—心理—行动）。
- `fengshui` v1.0.0：二十四山/八宅游年/命卦/三元九运/流年九星/煞象库 75 条；形法优先、玄空飞星明确不排。

### 工程
- `install.ps1` / `install.sh`：软链或复制两种模式，支持 `--only`、`--check`，装前校验 SHA256SUMS。
- `verify.py`：结构 + 编译 + 零依赖引擎 self-test + 有库时冒烟；缺库标 SKIP 不计失败。
- 全部脚本零网络出口；`GBK` 控制台兜底（Windows 中文环境直接可跑）。

### 已知限制
- `qimen-dunjia` 未包含（第三方许可不明 + 无本地引擎），见 NOTICE。
- 八宅命卦以立春为年界，脚本不查节气——立春前后出生需调用方确认年柱。
- 玄空山向飞星、罗盘分金、择日、阴宅勘测：明确不做，需专业师傅/专业软件。