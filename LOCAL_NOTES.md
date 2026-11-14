# DeepTutor 本地部署笔记（非上游文件）

> 本文件由本地维护添加，记录与上游不同的运行方式、本地定制与踩坑，供未来的自己快速接手。
> 上游代码以 git 历史为准；最后更新：2026-11-14。

## 一、版本与环境

- 上游：HKUDS/DeepTutor **v1.7.1**（2026-10-31）。
- 本目录：`X:\AI\DeepTutor-main`，git 合并历史：
  `6d384e6 local modifications` → `a7cd8dd upstream v1.7.1` → `f3cd1e2 merge upstream v1.7.1 with local customizations` → `af9669b Point Deep_tutor.bat launcher at project venv`。
- Python：项目内 `.venv`（3.11.15）。**不要再依赖 conda `deeptutor_env`**。
- 前端：`web/`（Next 16.2.3 + React 19，Node 22）。
- 数据：`data/user/`（会话、设置、workspace、知识库索引）。
- 远端：`origin` = `git@github.com:LittleNBB/deeptutor_ai_rebuild.git`（SSH）；分支 `main`。
  改完代码/文档后提交并 `git push origin main`，方便回滚与异地继续。

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

## 十一、输出预算（2026-11-12）

- 原则：`max_tokens` 是**上限**，不是目标。抬高它只保证“需要长文本时不被截断”，短回答仍会自然结束。
- 运行时预算在 `data/user/settings/agents.yaml`（该目录不入 git）：
  - `chat.exploring=32768`、`chat.responding=65536`
  - `research.block=32768`、`research.report_section=65536`，其余研究阶段 16384
  - `question.answering=32768`，规划/修复/收尾 16384、工具摘要 4096
  - `solve=32768`、`co_writer=32768`
- 代码级默认（新装也生效）：`deeptutor/services/config/loader.py` 的 `DEFAULT_CHAT/RESEARCH/QUESTION_PARAMS`；`deeptutor/services/config/capabilities_settings.py` 的 `_SIMPLE_LLM_DEFAULTS`。
- 学习流程里的单次调用：`deeptutor/learning/lesson_evidence.py` 的 `_ask`（选源）16384、`deeptutor/learning/semantic_assessment.py` 16384。
- 关键坑：推理模型把 `reasoning_tokens` 计入同一个 `max_tokens`；预算过小会出现“思考吃满、content 为空”（旧 1800 就是这么炸的）。现先用 max effort，结构化调用失败时用 `structured_retry` 以 low effort 重试。
- DeepSeek API 实测接受 `max_tokens=65536`（18k prompt 也正常）；改完代码需重启后端，改 agents.yaml 即时生效。

## 十二、图表可读性：mermaid 宽图与知识库页图（2026-11-14 修复）

- 症状（用户口径：列表 / 表格 / mermaid / 图片都算“图表”）：
  1. 精通之路里横向排布的 mermaid 信号流程图被压成一条细线，字号约 5px，几乎不可读。
  2. 知识库检索返回的教材 PDF 页图固定在 384px 高的矮框里（实际只画 276×384），点击只打开右侧抽屉，无法放大。
- 根因（均在前端渲染层，与模型生成写法无关）：
  1. `web/components/Mermaid.tsx` 的 `mermaid.initialize({ flowchart: { useMaxWidth: true } })` 让
     mermaid 输出 `width="100%"` + `max-width`。会话栏宽 885px 时，viewBox `0 0 2738.97 131` 被压成
     885×42，16px 标签实际 ≈4.7px；图越宽字越小。
  2. `web/components/chat/home/MasterySourcePresentation.tsx:30` 的 `<div className="h-96 w-full">`
     把页图钉死为 384px 高，图片 `max-h-full max-w-full object-contain` 只能画到 276×384。
- 处理（3 处修改 + 1 个新组件）：
  - `web/components/Mermaid.tsx`：`flowchart.useMaxWidth: false`；新增 `restoreIntrinsicSize(svg)`，
    用 DOMParser 从 viewBox 读宽高、写回 `width`/`height` 像素属性并去掉 `max-width`，容器
    `overflow-x-auto` 横向滚动。**不提供点击全屏**：试过 ZoomableLightbox（最小 75%），2738px 的图
    在 75% 下仍比窗口宽，反而“点开也看不全”，已移除——与 genui 图表一致，只滚动、不缩放。
  - `web/components/chat/preview/previewers/ImagePreview.tsx`：图片外包 button，点击打开全屏浮层
    （blob:URL 的页图也能用），浮层内 `max-w-none` 原图 + 缩放。
  - `web/components/common/ZoomableLightbox.tsx`（新增）：全屏浮层，打开时轮询测量并
    `fit = min(1, (vw-32)/w, (vh-32)/h)` 自动适配，提供缩小/百分比/放大/关闭，Esc 关闭并锁 body 滚动。
  - `web/components/chat/home/MasterySourcePresentation.tsx:30`：`h-96` → `h-[min(72vh,760px)]`。
  - 未新增 i18n key，复用已存在的 Zoom in / Zoom out / Close / Fullscreen（中文渲染为 放大/缩小/关闭/全屏）。
- 验证：
  - 真实会话：mermaid svg 2739×131、字号 16px，容器 885px 宽出现横向滚动条；修复前为 885×42。
  - 知识库页图：卡内 518×720；点击后浮层内 664×923（自动适配），标题带 “PDF page 13”。
  - `cd web && npx tsc --noEmit -p tsconfig.json` 退出码 0；`/chat/<sessionId>` 返回 200。
  - 复现检查：打开任意含宽 mermaid 的会话，应看到横向滚动条且字不再缩小；点知识库页图应弹全屏浮层。
- 注意：
  - 生产模式（前端 3782、`scripts/start_web.py`）读的是 `web/.next-deeptutor` 构建产物，
    改完源码必须重新构建（或改用 dev 模式）才生效；dev 模式（`npm run dev`）是热更新的。
  - 若希望长图彻底不用滚动，应在生成端让 mermaid 改竖排（`flowchart TB`）或分成两行，而不是再压渲染。
- 回滚：`git revert <本提交>` 即可；本次改动不含配置、数据或后端逻辑。

## 十三、默认人格、侧栏新对话与精通记账容错（2026-11-14）

- 需求（用户原话）：「1,和dsh新增对话一样就行，即你说的”左侧栏顶部（标题行右侧）常驻一个 ⊕“ 2,对话内容有部分重复，你自己看； 3,修改原teacher人格就行；」
- 侧栏常驻新对话：`web/components/sidebar/SidebarShell.tsx` 打开态 `.dt-sidebar-header` 内、WorkspaceMenu 之后、搜索按钮之前新增一个 `Link href="/chat" className="dt-nav-icon"`（SquarePen 图标，Tooltip 复用 `navigation.newChat`，onClick 复用 `handleHomeClick`）；折叠态 60px 轨道原本就有新对话图标，未重复添加。
- 默认人格：`deeptutor/services/session/turns/executor.py` 在解析 `payload["persona"]` 后增加回退——请求未指定人格时加载 `teacher`（文件缺失则不注入），显式选择始终优先。重启后端生效。
  - 注意：人格仍是“每轮一个 prompt 块”，不是硬编码指令；用户切到别的人格或清空后仍按上述规则回退。
- teacher 人格重写（`deeptutor/services/persona/presets/teacher/PERSONA.md` 与 `data/user/workspace/personas/teacher/PERSONA.md` 内容一致）：讲解优先（先动机/来由再公式，不拿追问代替讲解）、结构一律画图（Mermaid 优先竖排、教材优先呈现原页/原图并指出看哪一处）、按考点题型带练（计算题给步骤判据、答错指出哪一步并补同类题）、每轮只给一个下一步且不重复收尾。
- 精通记账（`mastery_note_explained`）两处修复：
  1. `deeptutor/capabilities/mastery/tools.py`：新增 `_quote_match_key` 与 `_locate_published_quote`——先精确 `rfind`，再按 NFKC/小写/去空白与 markdown 符号折叠匹配并映射回原文索引，最后用 `difflib.SequenceMatcher` 取 >=0.9 的近似窗口；未真正交付的文本仍返回原拒绝文案。
  2. `deeptutor/capabilities/mastery/prompts/{zh,en}/mastery_loop.yaml`：要求「同一轮同一知识点只记一次，先把讲解写完再调用，调用后不重讲、不重复总结；引文逐字复制（含标点）」。
  - 成因记录：旧实现只做 `published.rfind(quote)`，模型把计划措辞当引文（未交付）或只差一字（“这一个点的” vs “这个点的”）都会失败；模型还会先调用再讲解，造成正文重复收尾。
- 验证：
  - `py_compile` 通过；`cd web && npx tsc --noEmit` 退出码 0；YAML 可正常解析。
  - 匹配器实测：精确/加粗 **T**/错别字「输人」都定位到同一片段；未来计划式引文与未交付内容返回 None。
  - 生产前端 3782（重建 `.next-deeptutor`）：侧栏标题行出现「新对话」按钮，从 /space 点击后跳转 /chat。
  - 默认人格实测：新会话未选人格时，回复按中文讲解风格输出，模型思维链里明确提到「persona 要求画图」。
  - 精通实测：同一会话续讲后，两次 `mastery_note_explained` 均被接受（partially_explained），正文只有一个「一句话收束」，未再出现三段重复收尾。
- 关键坑：直接 `cd web && npm run build` 写的是 `web/.next`，生产读的是 `web/.next-deeptutor`；必须 `DEEPTUTOR_NEXT_DIST_DIR=.next-deeptutor npm run build`（或走 `scripts/start_web.py`），否则构建产物时间戳不变、页面毫无变化。
- 回滚：`git revert <本提交>`；若只想关掉默认人格，删掉 executor.py 里 `if not requested_persona:` 分支并重启后端。

## 十四、精通记录行内的“新建会话”加号（2026-11-14）

- 需求（用户原话，m00666）：“我希望是像dsh里一样，点加号在对应区域下新建对话，是在这个精通之路下新增会话，而不是新增chat……点击新建对话后出现一个新的会话和那两个会话同级。” 顶部全局 ⊕ 保留（m00710：“不用删。”）。
- 界面：`web/components/sidebar/LearningNavigation.tsx` 的记录行（`.dt-record-node-row`）末尾、标题链接之后新增 `.dt-record-new-session` 按钮（Plus 图标，`navigation.newChat` 作 aria-label/title），仅 `record.kind === 'mastery'` 且带 `pathId` 时出现；样式在 `web/features/ui-layout/modern/modern.css`（常驻 55% 不透明度，悬停/激活/聚焦时 100%）。
- 数据：`web/lib/learning-dashboard.ts` 的 `LearningActivity` 新增可选 `pathId`、`contentWorkspaceId`，mastery 分支填 `topic.path_id` 与 `topic.content_workspace_id`，避免跨工作区建错位置。
- 点击即建（关键）：后端原本没有创建会话的 HTTP 接口（普通“新对话”也要等首条消息才建行），仅导航到 `/learning/mastery/<path>/sessions` 时侧栏不会出现同级新行。新增：
  - `deeptutor/api/routers/mastery_path.py`：`POST /api/mastery-paths/topics/{path_id}/sessions`（201）。校验 topic 存在（404），`get_session_store().create_session()` 建行，`update_session_preferences` 写 `workspace_mode=mastery_path`、`mastery_path_id`、`mastery_session_mode=study`，再 `LearningStore().bind_session(path_id, session_id)`；任一步失败则尽力 `delete_session` 并原样抛出，避免留下无主空行。
  - 响应 `{path_id, session_id, title, created_at, updated_at}`；`GET /topics/{path_id}/sessions` 本来就会列出无消息会话，所以新行立即出现在记录下。
- 前端调用：`web/lib/learning-api.ts` 新增 `createMasteryTopicSession(pathId, workspaceId)`，用 `scopedUrl(..., workspaceId)` 显式带 `dt_workspace`；创建成功后 `window.location.assign(masterySessionRoute(...))`，整页加载让侧栏重新拉到这条会话；请求期间按钮 disabled，失败 `notify(t('Action failed'))`。
- 验证（生产 3782 + 后端 8001，Edge/Playwright）：
  - `POST` 返回 `unified_...`，`GET /topics/<id>/sessions` 从 2 条变 3 条，新增行 title=New conversation、message_count=0；`sessions.preferences_json` 中三项偏好正确。
  - 在 `/learning/mastery/<path>` 点击行内 ⊕：跳转 `/learning/mastery/<path>/sessions/unified_...`，落地页直接进入该知识点的学习界面；刷新后侧栏记录展开，新会话排在最前，与两条旧会话同级。
  - 清理探针数据后 `mastery_path_sessions` 恢复为原 2 条，旧会话标题/时间未变。
- 构建/部署（承接第十三节）：`DEEPTUTOR_NEXT_DIST_DIR=.next-deeptutor npm run build` 之前必须先停 3782（Windows 上 `libvips-42.dll` 被占用会 EPERM）；启动脚本 `X:/AI/_start_web.ps1`（PORT=3782、API 8001、DEEPTUTOR_HOME），后端 `X:/AI/_restart_backend.ps1`。
- 回滚：`git revert <本提交>`；若只想撤掉行内加号，删掉 `LearningNavigation.tsx` 的 mastery 按钮与 `modern.css` 的 `.dt-record-new-session` 规则，后端接口可保留（无调用方）。

## 十五、精通回复：正文折叠、页图位置与思维链收敛（2026-11-14）

- 需求（用户原话，m00993/m00994）：1 思维链过度、内容基本相同反复思考；2 正文和图片位置混乱，正文竟在“过程记录”里，点一下就折叠；3 引用图片应在正文对应位置，不是开头/结尾；4 图片引用默认折叠，像思维链点击展开。确认：图片按页码自动就近插入；思维链不是限制轮次，是内容重复，要减少。
- 根因：
  1. web/features/chat/messages/ChatMessageList.tsx 的 buildMessageBlocks 只保留末尾连续 text 作为答案；该轮 messageSegments 依次为 trace、source_view(page10)、trace、text(3726)、source_view(page11)，末尾是页卡，answerStart 落到数组长度，正文被并进 process 折叠块。
  2. 页图事件来自最后一轮工具调用，天然排在全部正文之前；该轮 16 个 rag tool_result 的 metadata.assistant_content_offset 全为 None，前端无法按 offset 定位，只能放在开头/结尾。
  3. MasterySourcePresentation.tsx 的 SourcePage 默认展开整页原图，两张就把正文顶出屏幕。
  4. 思维链每轮开头复述“学习者要求 / 资料 ready / 页码约定 / 下一步计划”，第 9 轮仍在复述同一套上下文。
- 改动：
  - ChatMessageList.tsx：foldable = trace || (isMastery && source_view)；preserveTeachingBefore 回退时跳过这两类，正文不再因页卡被折进“过程记录”。
  - web/components/chat/home/AskUserOptions.tsx：新增 placeSourceViewsAtMentions——按正文里的“第 N 页 / page N / C2.2.N”找到页码提及，把对应 source_view 移到该段之后，并把正文切成多段；无提及则保留原位。extractMessageSegments 在消息 settled 后调用。
  - MasterySourcePresentation.tsx：SourcePage 改为 details 默认 closed，summary 只显示“文件名 · PDF page N”；图片组件仅在展开后挂载，展开后仍可点击全屏。
  - deeptutor/capabilities/mastery/prompts/zh|en/mastery_loop.yaml：增加“推理只前进，不复述”“检索要收敛”“先写下引用它的句子，再展示页”。
  - deeptutor/services/persona/presets/teacher/PERSONA.md（运行目录 data/user/workspace/personas/teacher/PERSONA.md 同步）：增加“## 思考方式”，要求推理只用于决定下一步，发现重复就停止推演。
- 验证（生产 3782 + 后端 8001，Edge/Playwright）：
  - 目标会话 unified_1794637340178_733de588：最终 details=2、无“过程记录”按钮、正文 H2 不在折叠容器内；page10 卡紧跟提到“上面第 10 页…那张图就是采样过程的原貌”的段落后，page11 卡紧跟“上面第 11 页四张图里…”段落后；两卡默认 closed，展开后 img 826×619.5（natural 1440×1080），可点开全屏；已人工核对正文与两张页卡的实际 DOM 顺序。
  - 一次临时 mastery 会话（已删除）实测：20.4 秒、2 次 rag；thinking 3,257 字符 / 1,855 个 delta，对比旧问题轮 29,418 字符 / 15,805 delta、9 轮 16 次工具调用；仍有一轮页码歧义的自我讨论，但不再每轮复述同一套上下文。结论：提示词是收敛措施，不保证每次都短，需继续观察。
  - npm run test:node：1335 pass / 0 fail；npx tsc --noEmit -p tsconfig.json 退出 0；干净构建成功。
- 关键坑（承接第十三、十四节）：X: 盘上源文件 mtime 不随编辑更新（ChatMessageList.tsx 改后仍显示 2026-11-05 20:33:09），webpack 会复用旧模块，构建“成功”但产物没变。改前端后必须：停 3782 → rm -rf web/.next-deeptutor → DEEPTUTOR_NEXT_DIST_DIR=.next-deeptutor npm run build → 启动。只跑 build 不删目录时，页面会继续显示旧折叠逻辑。
- 回滚：git revert <本提交>；若只想退回旧折叠行为，删掉 ChatMessageList.tsx 的 foldable 分支即可，其余为独立增强。

## 十六、聊天对话目录与一键回到底部（2026-11-14）

- 需求（用户原话，m00002）：DTR 打开对话默认在顶端且没有一键到底的按钮（默认在顶端这点不用改）；边上没有对话历史记录，需要自己翻到对应位置，很麻烦。确认口径（m00080）：打开在顶部的问题不用管，只要侧边目录 + 一键到底。
- 现状：上游 v1.7.1 只有左侧 gutter 的 TurnNavigator 刻度（无标签、hover 才预览、不足 3 问或窄窗口直接隐藏），没有可见按钮；打开会话的位置由 useChatAutoScroll 决定，本次未改动。
- 改动：
  - 新建 `web/components/chat/home/ChatOutlinePanel.tsx`：右侧 288px 对话目录，每条用户提问一行（序号 + 两行标题 + 回复首句）；点击调用 ChatWorkspace 的 jumpToTurn（复用 `scrollToChatTurn`，topOffset 56 + turn-flash 闪烁）；滚动时按距顶部 140px 的判定线高亮当前行，并用 `offsetTop` 让列表跟随；顶部显示条数与关闭按钮。`aside` 上带 `data-outline-panel="true"`。
  - `web/hooks/useChatAutoScroll.ts`：新增 `isAtBottom`（阈值 80px，只在跨阈值时 setState，滚动每帧不重渲染），随 hook 返回。
  - `web/features/chat/components/ChatWorkspace.tsx`：头部 actions 增加 ListOrdered 按钮（t("Conversation outline")，title 用原有 "Jump to one of your questions" 文案）；新增 `outlineOpen` 状态与 `dt:chat:outline-panel` 持久化（存 "1"/"0"；无存量时 ≥1280 展开、<1280 收起）；`jumpToOutlineTurn` 在窄屏跳转后自动收起；消息区 wrapper 改为 `flex-row`；未在底部时渲染悬浮胶囊按钮 `data-back-to-bottom`（右侧偏移随面板开合 304/16px），点击执行 resumeFollowingLatest（重新跟随并置底）。
  - 文案：`web/locales/{en,zh,de,fr,ja,pl,pt,tr,uk,vi}/app.json` 各新增 "Conversation outline" / "Back to bottom" / "No questions yet"（中文：对话目录 / 回到底部 / 还没有提问）。strict 语言（de/vi/tr/ja/pl/pt）必须补齐，否则 `npm run i18n:audit` 退出 1。
- 验证（2026-11-14 晚，生产 3782）：
  - `node ./node_modules/typescript/bin/tsc --noEmit -p tsconfig.json` 退出 0；eslint 三个改动文件 0 error（ChatWorkspace 里 img/alt 两条 warning 是既有代码）；`i18n_parity` OK；`i18n_audit` 退出 0（strict 语言 used keys 100%）。
  - 干净重建：停 3782 → `rm -rf web/.next-deeptutor` → `DEEPTUTOR_NEXT_DIST_DIR=.next-deeptutor node ./scripts/build.mjs`，BUILD_ID `ji_OHak4E6tT4OexBFqiO`。
  - Edge/Playwright 1440x900 实测会话 unified_1794637340178_733de588：目录 7 行、滚动/跳转后 active 行跟随；FAB 在滚到顶部后出现（文案“回到底部”）、点击回到底部并消失；点第 3 条后 scrollTop 6498、turn-flash=1、active 变第 3 条；头部按钮可关/开；1000x800 下 aside 变 absolute 覆盖层、跳转后自动关闭；console 无 error。截图：X:/AI/AI对话/DSH对话/shot-outline-panel.png、shot-back-to-bottom.png、shot-outline-active.png。
- 运行注意：本次验证用的前端是手工启的 standalone 实例（`cd web/.next-deeptutor/standalone` 后设 PORT=3782、HOSTNAME=0.0.0.0、DEEPTUTOR_API_BASE_URL=http://127.0.0.1:8001、DEEPTUTOR_AUTH_ENABLED=false、NEXT_PUBLIC_AUTH_ENABLED=false 再 `node server.js`）；如果用 `python scripts/start_web.py` 托管，正常重启 launcher 即可，它会复用已占用的 8001/3782。
- 已知边界：目录只收用户提问（复用 `buildChatOutline`），不列工具/系统记录；打开会话仍按原逻辑停在顶部，本次没动（用户明确要求不改）；面板宽度与 `xl` 断点（1280px）绑定。
- 精通之路会话（2026-11-14 深夜补齐，用户反馈“精通之路对话中没有”）：该路由不走 ChatWorkspace，而是 `web/app/(workspace)/learning/mastery/[pathId]/sessions/[sessionId]/page.tsx` → `web/components/space/learning/MasteryStudy.tsx`。复用同一套 ChatOutlinePanel / scrollToChatTurn / useChatAutoScroll，改动：
  - MasteryStudy 头部加 ListOrdered 按钮（aria-pressed，title 复用 "Jump to one of your questions"）；`chatOutlineOpen` 与 `dt:chat:outline-panel` 持久化，与聊天共用同一份面板偏好；打开 Activity 侧栏时自动收起目录，保证右侧只有一条栏。
  - 转写区父容器改 `relative flex`，滚动区 `min-w-0 flex-1`，目录作为兄弟节点：≥1280px 静态并排（不再遮正文，实测正文右缘与面板左缘留 10px），<1280px 仍 absolute 覆盖层；覆盖层下点击目录跳转后自动关闭。
  - `nearBottom` 由滚动距离阈值 80px 维护，并在 messages/session 变化时重算；`hasMessages && !nearBottom` 渲染 `data-back-to-bottom` 胶囊，右侧 304/16px 随目录开合。
- 验证（2026-11-15 00:30，生产 3782，BUILD_ID dqXoFBUzt7gCXG1V3XuMF）：1440x900 精通会话 unified_1794637340178_733de588 面板 position=static、7 行、正文与面板 overlap=-10px；跳转 scrollTop 6760、面板保持；回到底部后 dist=0 且 FAB 消失；1000x800 打开目录→跳转后面板自动关闭、scrollTop 5202；普通聊天 /chat/unified_... 目录默认 1 个/7 行、滚到顶部 FAB 出现；三处 console/pageerror 均为空。tsc 退出 0、eslint 退出 0。截图：shot-mastery-final.png、shot-mastery-narrow-after-jump.png。
- 回滚：`git checkout -- web/features/chat/components/ChatWorkspace.tsx web/components/space/learning/MasteryStudy.tsx web/hooks/useChatAutoScroll.ts web/locales` 并删除 ChatOutlinePanel.tsx；面板本身可随时用头部按钮关闭，不影响消息流。


