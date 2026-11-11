# 易（yi）· 术数五件套（4 个引擎 + 1 个路由）

> 项目名「易」，仓库名 `yi`。

一套可直接给 AI Agent 用的传统术数技能包。**算法由脚本确定性计算，解读由 LLM 完成**——排盘不靠模型"背"，结论不靠模型"编"。

| 技能 | 解决什么 | 引擎 | 依赖 |
|---|---|---|---|
| `meihua-yishu` 梅花易数 | 一件当下的事：成不成、阻力在哪、该不该动 | `scripts/meihua.py` 时间起卦（本卦/互卦/变卦＋体用五行） | `lunar-python` |
| `ziwei-doushu` 紫微斗数 | 一个人的格局与各阶段：性格、事业、感情、大限流年 | `scripts/paipan.py` 安星/四化/格局/运限 | `x-iztro` |
| `zhougong-jiemeng` 周公解梦 | 一个梦：象是什么、什么意思、为什么反复 | `scripts/jiemeng.py` 475 条梦象库（古断/推演分层） | 无（纯 stdlib） |
| `fengshui` 风水·阳宅 | 一个空间：形（采光/通风/噪音/动线）＋八宅游位＋流年 | `scripts/fengshui.py` 二十四山/游年/命卦/流年九星 + 75 条煞库 | 无（纯 stdlib） |
| `fortune-hub` 路由 | 用户不知道该问哪个体系时，分诊到对的技能 | 无（纯提示词） | 无 |

设计原则只有三条：

1. **能算的不许 LLM 手算**——每一盘都由脚本算出，脚本有 `--self-test`；
2. **不给结论性预言**——只给"宜/不宜/阻力"与可做的事，不给日期、不给死生祸福；
3. **诚实分层**——古本有的标"古断"，按取象推的标"推演"，不冒充古书。

## 下载与解压

```bash
unzip yi-1.0.1.zip -d yi    # 注意：zip 内没有顶层目录，用 -d 指定解压到 yi/
cd yi
```

PowerShell：`Expand-Archive yi-1.0.1.zip -DestinationPath yi; cd yi`

## 安装

**Windows（PowerShell 5.1 / 7）**

```powershell
.\install.ps1                # 挂到 $env:DSH_HOME\skills（或 ~\.dsh\skills）
.\install.ps1 -Copy          # 复制而非软链，便于装到其他 agent
.\install.ps1 -Only fengshui # 只装某一个
.\install.ps1 -Check         # 只检查依赖
```

**macOS / Linux**

```bash
chmod +x install.sh && ./install.sh          # 软链到 ${DSH_HOME:-~/.dsh}/skills
./install.sh --copy --only fengshui
```

**其他 agent（Claude Code / Codex / 自建）**：把 `skills/` 下需要的目录复制进它自己的技能根即可（每个目录就是标准 `SKILL.md` + 可选 `scripts/ references/ data/`）。

安装后**重启会话或发一条消息**，技能目录才会刷新。

## 验证

```bash
python verify.py
```

检查四件事：`SKILL.md` frontmatter 与目录名一致、所有脚本可编译、零依赖引擎跑 `--self-test`、有库时做一次端到端冒烟（没装库的标 SKIP，不算失败）。

## 快速用法

```text
"帮我起一卦，问这次合作"            -> meihua-yishu
"1990 年 6 月 15 日申时生，男"      -> ziwei-doushu
"梦见在电梯里一直往下坠"            -> zhougong-jiemeng
"坐北朝南三室，床头朝哪好"          -> fengshui
"这些该问哪个"                      -> fortune-hub
```

各引擎也可单独调用：

```bash
python skills/meihua-yishu/scripts/meihua.py --solar 2024-2-5 --time-index 6
python skills/ziwei-doushu/scripts/paipan.py --solar 1990-6-15 --time-index 6 --gender male
python skills/zhougong-jiemeng/scripts/jiemeng.py --text "我梦见在电梯里往下坠"
python skills/fengshui/scripts/fengshui.py --bazhai 210
```

## 分诊表（fortune-hub）

| 你想问 | 用 |
|---|---|
| 这件事成不成、该不该动、对方什么态度 | 梅花易数 |
| 哪天办、往哪个方向、哪个时辰 | 奇门（见下节：本包不含，可选） |
| 这个人一生格局、各阶段运势 | 紫微斗数 |
| 这个梦什么意思、为什么反复 | 周公解梦 |
| 这房子/户型/床位/书桌/装修 | 风水 |

## 关于奇门遁甲

本包**未包含** `qimen-dunjia`。原因有两条，都写在这里免得误解：

1. 它是第三方产物（来源为 Marvis 技能商店，未声明开源许可），**没有授权就没法随包再分发**；
2. 它没有本地脚本引擎，排盘要靠模型自行推算——与"能算的不许手算"这条原则冲突，质量无法保证。

需要奇门择时，请自行获取有明确许可、且带排盘引擎的实现。`fortune-hub` 会在路由时说明这一点，不会假装能算。

## 依赖

| 包 | 用途 | 许可 |
|---|---|---|
| `lunar-python` | 农历/节气换算（梅花起卦用） | MIT |
| `x-iztro` | 紫微安星引擎（Python 绑定） | MIT |

```bash
pip install lunar-python x-iztro
```

两者**不随包分发**，未安装时对应技能会明确报错而不是瞎算：解梦与风水是纯标准库实现，不受影响。

## 边界与免责

这套东西是**解释框架，不是预言机**：

- 不预测确切日期、数字、死生祸福、疾病官非；
- 不提供开光、法器、符咒、法事、付费改运；
- 不替代医疗、法律、财务判断，不替代结构/机电/消防等专业勘测；
- 涉及持续困扰（反复噩梦、长期焦虑、居家安全隐患）时，明确建议寻求专业帮助。

所有解读都由 LLM 生成，可能与脚本给出的盘象不一致——**以脚本输出为准**，不一致就是模型的错，不是盘的错。

## 目录结构

```
yi/
├── install.ps1 / install.sh   # 安装（软链 or 复制；--only / --check）
├── verify.py                  # 自检（结构/编译/引擎/校验和）
├── release.py                 # 一键发布：归一 LF → 重算校验和 → 打包 → 解包自检
├── SHA256SUMS                 # 完整性校验（31 条）
├── README.md  LICENSE  NOTICE  CHANGELOG.md
└── skills/
    ├── fortune-hub/           # 路由（无脚本）
    ├── meihua-yishu/          # SKILL.md + references(2) + scripts/meihua.py
    ├── ziwei-doushu/          # SKILL.md + references(1) + scripts/paipan.py
    ├── zhougong-jiemeng/      # SKILL.md + references(3) + data(475 条) + scripts/jiemeng.py
    └── fengshui/              # SKILL.md + references(3) + data(75 条) + scripts/fengshui.py
```

不含 `MEMORY.md`（各技能的本地偏好文件）——那是使用者自己的数据，不随包发布。

## 版本与许可

v1.0.2 · MIT（代码与文档）· 传统文本部分见 `NOTICE`。

致谢：`lunar-python`、`x-iztro` 两个上游库；《周易》《梅花易数》《八宅明镜》一系传统文本为公有领域。