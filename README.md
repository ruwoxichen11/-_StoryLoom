# 故事织机 · StoryLoom

> 基于 **LangChain 多智能体 + ReAct 推理** 的中文小说创作工作台。
> 把"写一部小说"拆成 6 道工序，每道工序由一位专长智能体负责；核心的「圆桌戏台」让多个角色演绎体像演员一样实时同台飙戏，边演边写。

---

## ✨ 它和普通"AI 写小说"有什么不同

1. **ReAct 角色演绎**：每个角色在发言前会显式经历 `Thought（链式思考 CoT）→ Action（工具路由）→ Observation`，能主动检索设定库核对人名/世界观，避免前后矛盾。前端可展开查看完整推理链。
2. **导演制调度**：「戏剧统筹（Showrunner）」每轮只下一条 JSON 指令（点名发言 / 对手戏 / 旁白 / 收束），把多智能体协作变成一个可控、可暂停的循环。
3. **RAG 设定记忆**：作品的世界观/角色/前情向量化进 **Milvus Lite**，长篇也能保持一致。
4. **零数据库**：作品以 JSON 文件落盘；**一键启动**即可跑通。

## 🧱 技术栈

| 层 | 选型 |
|---|---|
| 智能体 / 推理 | LangChain（ReAct AgentExecutor + LCEL Chain），体现 CoT 与 Tool Routing |
| 向量检索 | Milvus Lite + Embedding（未配 embedding API 时自动回落本地哈希向量） |
| LLM | DeepSeek V3 / R1（OpenAI 兼容协议） |
| 后端 | FastAPI + Uvicorn |
| 实时通信 | WebSocket（圆桌戏台流式输出） |
| 前端 | 原生 HTML + CSS + JavaScript（零构建） |
| 存储 | JSON 文件 |

## 📁 目录结构

```
storyloom/
├─ backend/
│  ├─ app/
│  │  ├─ api/routes/     # works / config / generate / roundtable(WebSocket)
│  │  ├─ core/           # bootstrap：注入 sys.path
│  │  ├─ schemas/        # 请求/响应契约
│  │  ├─ services/       # lore_service：设定汇总 + RAG 入库
│  │  ├─ db.py           # JSON 文件存储
│  │  ├─ models.py       # 领域模型（Work/Character/Outline/Chapter...）
│  │  └─ main.py         # FastAPI 入口
│  └─ requirements.txt
├─ frontend/             # index.html / theme.css / app.js
├─ rag/                  # Milvus Lite 向量库 + embedding
├─ agent/                # 7 位智能体 + ReAct 工具箱 + 人格层叠
├─ model/                # LangChain ChatOpenAI -> DeepSeek 工厂
├─ utils/                # 路径 / 配置 / 文本工具
├─ config/settings.json  # 配置（API Key、模型路由、端口…）
├─ data/                 # 作品 JSON 与向量库落盘
└─ run.py                # 一键启动
```

## 🚀 快速开始

```bash
cd storyloom
python run.py
```

首次启动会自动安装依赖。随后打开 `http://localhost:8200`，在右上「设置」里填入 **DeepSeek API Key**（或设环境变量 `DEEPSEEK_API_KEY`）即可开始创作。

> 要求 Python 3.9+。

## 🧭 六道工序

1. **灵感入织** — 缪斯把一句话灵感提炼为故事基因
2. **选角孵化** — 选角师生成互相咬合的角色阵容
3. **经纬编织** — 织线师规划主线节点 + 支线伏笔
4. **章回部署** — 锁定大纲后自动拆章，逐章写微纲
5. **圆桌戏台** — 戏剧统筹调度角色（ReAct）实时演绎 → 誊抄成稿
6. **总览付梓** — 审稿人一致性复核，导出 Markdown / TXT

## 🤖 智能体阵容

| 名称 | 职责 | 推理方式 |
|---|---|---|
| 灵感缪斯 Muse | 灵感 → 故事基因 | CoT Chain（R1） |
| 选角师 Castmaker | 角色阵容 | CoT Chain |
| 织线师 LoomPlanner | 大纲 + 支线 | CoT Chain（R1） |
| 戏剧统筹 Showrunner | 圆桌调度（JSON 指令） | CoT Chain |
| 角色演绎体 Actor | 扮演角色发言 | **ReAct + 工具检索** |
| 誊抄师 Scribe | 研讨记录 → 正文 | Chain |
| 审稿人 Auditor | 一致性复核 | CoT Chain（R1） |
