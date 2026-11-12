# DeepTutor 本地部署笔记（非上游文件）

> 本文件由本地维护添加，记录与上游不同的运行方式、本地定制与踩坑，供未来的自己快速接手。
> 上游代码以 git 历史为准；最后更新：2026-11-05。

## 一、版本与环境

- 上游：HKUDS/DeepTutor **v1.7.1**（2026-10-31）。
- 本目录：`X:\AI\DeepTutor-main`，git 合并历史：
  `6d384e6 local modifications` → `a7cd8dd upstream v1.7.1` → `f3cd1e2 merge upstream v1.7.1 with local customizations` → `af9669b Point Deep_tutor.bat launcher at project venv`。
- Python：项目内 `.venv`（3.11.15）。**不要再依赖 conda `deeptutor_env`**。
- 前端：`web/`（Next 16.2.3 + React 19，Node 22）。
- 数据：`data/user/`（会话、设置、workspace、知识库索引）。

## 二、启动 / 停止 / 自启

- 一键启动（生产模式，自动打开浏览器）：
  `.venv\Scripts\python.exe scripts\start_web.py`
  - 后端 8001 / 前端 3782（`data/user/settings/system.json`；`BACKEND_PORT` / `FRONTEND_PORT` 可覆盖）。
  - 首次或源码/端口变化时先构建前端到 `web/.next-deeptutor`（约 1 分钟）；指纹（`.deeptutor-build.json`）不变则秒级。
- dev 模式（改代码即时生效）：
  后端 `python -m deeptutor.api.run_server`；前端 `cd web && npm run dev -- -p 3782`。
- 开机自启（登录时）：
  `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\DeepTutor.lnk`
  → `start\后台运行.vbs` → `start\Deep_tutor.bat`。
- 停止：任务管理器结束 `python` / `node`；或 `netstat -ano | findstr :8001` 查 PID。
- 取消自启：删除 Startup 里的 `DeepTutor.lnk`。

## 三、HTTP / WS 接口（v1.7.1 变更）

- API 前缀 **`/api`**（旧 `/api/v1/...` 已 404）。
- WS：**`ws://127.0.0.1:8001/ws`**（不是 `/api/ws`）。
- 每条客户端命令必须带 `protocol_version: "2.0"`；校验类型在
  `deeptutor/api/contracts/turn_protocol.py`（`ClientCommand` / `StartTurnCommand`）。
  `TurnRequest` 定义在 `deeptutor/core/turn_request.py`。
- 不传 `session_id` 新建会话；传不存在的 id 会报 `start_turn_rejected`。
- 事件流：`stage_start` / `content` / `thinking` / `observation` / `result` / `done`，
  metadata 含 `call_id` / `call_kind` / `trace_role`。

## 四、配置与思考强度

- 设置页 `/settings`（v1.7.1 新页）；模型工作台 `/settings/models`。
- `reasoning_effort` 存储在 `data/user/settings/model_catalog.json` 的
  `services.llm.models[].reasoning_effort`（**不是 profile**）。当前 `deepseek-v4-flash = max`。
- 解析：`deeptutor/services/config/provider_runtime.py`（模型字段 + 会话级 selection 覆盖）。
- 请求参数：`deeptutor/services/llm/reasoning_params.py`（deepseek 发 `reasoning_effort` + `extra_body.thinking`）。
- `.env` 在 v1.7.1 基本被 settings 取代，LLM 配置以 catalog 为准。

## 五、本地定制（相对上游 v1.7.1）

- 中文内部推理：`deeptutor/services/prompt/language.py` 新增
  `reasoning_language_directive` / `append_reasoning_language_directive`；
  `deeptutor/agents/loop/prompt_blocks.py` 的 `render()` 注入；
  `deeptutor/agents/chat/prompts/zh/agentic_chat.yaml` 的 `runtime_policy` 增加硬约束。
- 缓存计费（DeepSeek cache hit 双定价 + CNY）：`deeptutor/agents/research/utils/token_tracker.py`；
  usage 透传在 `deeptutor/agents/base_agent.py` 的 `_track_tokens(..., usage=...)`。
- 启动器：`start\Deep_tutor.bat`（ASCII + CRLF）、`start\后台运行.vbs`。
- 数据修补：`data/user/.runtime/workspaces.sqlite3` 与
  `data/user/archive/legacy-chat/migration-ledger.json` 中的旧绝对路径已改到当前项目根。
- 已随上游淘汰：`complete_with_response`、旧 `env_store.py`、TracePanels 去标签、旧设置页。

## 六、常见故障

1. **前端闪烁 / 白屏循环**：旧 `.next` 缓存（含旧绝对路径）导致 Turbopack panic。
   → 停前端，`rm -rf web/.next node_modules/.cache`，重启。
2. **WS 报 “The selected workspace folder does not exist.”**：
   `workspaces.sqlite3` / `migration-ledger.json` 里路径过期。→ 改成当前绝对路径。
3. **双击 vbs 没反应**：`Deep_tutor.bat` 必须是 ASCII + CRLF（UTF-8 + LF 会解析错乱），
   或端口被残留进程占用。
4. **设置页看不到 max**：`web/lib/reasoning-effort.ts` 的 supported 表未列 `deepseek-v4-flash`；
   已存值仍会显示；需要时把 flash 加入表。
5. **聊天出现字面 thinking/response**：上游 `factory.py` 已用 `<think>` 标签；只可能来自本地改动，检查是否又被改坏。

## 七、验证清单（升级/改动后）

- `curl http://127.0.0.1:8001/` → 200；`curl http://localhost:3782/chat` → 200。
- WS 发一条中文消息（`protocol_version: "2.0"`），确认：
  response 为中文、无 `<think>` 残留、thinking 为中文、
  `usage_summary.cache_hit_rate` 有值。
- `/api/settings` 返回 catalog，活动模型 `deepseek-v4-flash`、`reasoning_effort=max`。

## 八、备份 / 回滚

- 完整旧树：`X:\AI\_dt_old_20261105`。
- 压缩备份：`X:\AI\_dt_upgrade\backup\deeptutor_source_20261105.tar.gz`、
  `deeptutor_data_20261105.tar.gz`。
- 回滚：停服务 → 旧树覆盖（或改名切换）→ 恢复 data → 重启。

## 九、更详细记录

DSH 的 Mnemon 文档里有三份更细的记录（搜索 “DeepTutor”）：
- DeepTutor v1.7.1 升级合并与迁移记录
- dtr 启动与开机自启运维手册
- DeepTutor 思维链溢出与推理强度修复记录

## 十、知识库重排序（2026-11-12 修复）

- 现象：设置里填了 `BAAI/bge-reranker-base`，但从未自动下载；检索静默退化为纯向量，日志 warning
  `Reranker model '...' is configured, but sentence-transformers is not installed; using embedding retrieval unchanged.`
  另外 Mastery「Prepare Lesson」偶发 `The model returned an invalid source-selection response. Please retry.`
- 处理：
  - 依赖：`.venv` 与 conda `deeptutor_env` 都装了 `sentence-transformers`（含 CPU 版 torch）。
    启动器走 `.venv`，所以两个环境都要有，避免换启动方式后又退化。
  - 模型：从 ModelScope 下载到 `X:\AI\models\bge-reranker-base`（safetensors + tokenizer，跳过 1.1GB 的 pytorch_model.bin）。
  - 配置：`data/user/settings/llamaindex.json` 的 `reranker_model` 指向本地目录
    `X:/AI/models/bge-reranker-base`（normalize 允许任意 ≤200 字字符串）。
  - 解析加固（`deeptutor/learning/lesson_evidence.py`）：`_json_response` 支持 think 包裹、```json 围栏、
    前后散文、平衡 JSON 提取；`_ask` 解析失败自动重试一次（追加 "Return ONLY the JSON object"），
    并把失败原文前 500 字写入 warning 日志。
- 验证：
  - `CrossEncoder` 直接加载本地目录打分正常；`rerank_nodes(...)` 返回 sigmoid 分数且排序正确。
  - `RAGService().search("什么是梯度下降？", kb_name="计算机控制期末复习")` → provider=llamaindex、8 条来源、
    无 error；日志出现 `activation_fct` 弃用提示（说明确实走了 CrossEncoder）。
  - 后端以 `.venv` 重启（8001），日志 `data/user/logs/backend-8001.err.log` 无 "sentence-transformers is not installed"。
- 注意：
  - `rerank_nodes` 入参是 `NodeWithScore` 列表，不是 `TextNode`。
  - `sentence-transformers 5.7` 用 `activation_fn` 取代 `activation_fct`（旧名仍兼容，暂不改代码以免破坏 >=3.0 下限）。
  - 若重排序模型路径失效，检索会静默退化为向量检索；排查先看日志里是否有 rerank warning。

## 十一、精通之路 Prepare Lesson：空响应与首次 30s 延迟（2026-11-12 二次修复）

- 症状：仍报 `The model returned an invalid source-selection response. Please retry.`；精通之路对话前 ~30s 无输出。
- 根因 1（空响应）：DeepSeek 的 reasoning token 计入同一个 `max_tokens` 预算；`lesson_evidence._ask`
  原设 1800，复杂候选页 + 长指令时思考吃满、`content` 为空字符串。日志证据：
  `data/user/logs/deeptutor.jsonl` 中 `Source-selection parse failed on attempt 1 (0 chars)`。
- 修复 1：改用项目既有 `deeptutor/services/llm/structured_retry.py` 的 `payload_with_reasoning_retry`：
  第一次按配置反思强度（`max_tokens=3000`），若返回空/不可用，自动以 `RETRY_REASONING_EFFORT="low"`
  重试一次；两次都失败才抛原错误。`_json_response` 已支持 think 包裹 / ```json 围栏 / 前后散文 / 平衡 JSON。
- 根因 2（30s 延迟）：`BAAI/bge-reranker-base` 的 CrossEncoder 首次加载（含 torch import）约 30s，
  发生在第一次知识库检索请求里。
- 修复 2：`deeptutor/services/rag/pipelines/llamaindex/rerank.py` 新增 `warm_up_configured_reranker()`，
  `deeptutor/api/main.py` 的 `lifespan` 启动时后台线程预加载；启动日志出现 `Loading weights: 100%` 即预热完成。
- 注意：uvicorn 会以 `_base_executable`（conda 的 python）再 spawn 一个 worker；`.venv` 是父进程、
  实际服务在 conda 子进程，两个环境都必须装 sentence-transformers，改依赖时两边同步。
- 排查：`grep "Source-selection parse failed" data/user/logs/deeptutor.jsonl`；
  `tail data/user/logs/backend-8001.err.log` 看 `Loading weights`。
