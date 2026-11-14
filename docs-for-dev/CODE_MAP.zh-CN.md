# DeepTutor 代码地图（本机接手版）

> 给新接手的 AI 或人：先读这一页，知道项目怎么跑、代码在哪、通常改哪里。
>
> - 版本以 [`deeptutor/__version__.py`](../deeptutor/__version__.py) 为准，本机是 **1.7.1**。`docs-for-dev/` 里的多数页面写的是 1.7.0，目录结构基本一致，冲突时以 checkout 为准。
> - 本机不是上游纯净版：默认人格、侧栏、精通之路、图表渲染都有本地改动。运行方式、坑和每项改动的来龙去脉见 [`LOCAL_NOTES.md`](../LOCAL_NOTES.md)。
> - 上游架构契约见 [`AGENTS.md`](../AGENTS.md)；本页只做“代码地图”，不重复契约细节。

## 1. 最短接手路径

1. 读 [`AGENTS.md`](../AGENTS.md) 的 Overview / Architecture / Key Files，建立“入口 → 应用服务 → 能力”的整体印象。
2. 读 [`docs-for-dev/README.md`](README.md) 的 “Choose a reading path”，按任务找对应的 canonical 文档。
3. 用本页第 3 节定位要改的文件；只改一个页面时，不必通读整个后端。
4. 动代码前先 `git status`。本机是个人 fork，`data/` 是运行数据，不要提交。
5. 改完按第 6 节构建、重启，再按 [`TESTING.md`](TESTING.md) 做对应检查。

## 2. 一句话架构

DeepTutor 是本地优先的 AI 学习应用：**Python/FastAPI 后端 + Next.js 16 App Router 前端**。浏览器、CLI、Python SDK 三个入口最终都进入同一条 durable turn 管线；“精通之路”只是其中一个 capability，不是独立应用。

```text
浏览器 / CLI / SDK
        ↓
deeptutor/app/           TurnApplicationService：持久化、受理、重放
        ↓
deeptutor/runtime/       TurnEngine → ChatOrchestrator → 选择 capability
        ↓
deeptutor/agents/        公共 agent loop，或某个 capability 的多阶段管线
deeptutor/capabilities/  接管整轮的能力（mastery、reading、solve…）
        ↓
工具调用（ToolRegistry）→ 模型 → StreamBus 事件
        ↓
turn 持久化 → 前端 `web/features/chat` 重放 / 渲染
```

两条插件契约：

- **Tool**：模型单次调用的函数。名字、类路径和顺序由 `deeptutor/modules/manifests/*.json` 与 `deeptutor/tools/builtin_specs.py` 共同决定。
- **Capability**：接管一整轮的多阶段管线。`deeptutor/runtime/bootstrap/builtin_capabilities.py` 只是读取 manifest 的兼容视图，**真正权威是 `deeptutor/modules/manifests/*.json` 里的 `class_path`**。

## 3. 目录速查

### 3.1 后端 `deeptutor/`

| 路径 | 职责 | 什么时候来这里 |
| --- | --- | --- |
| `deeptutor/api/` | FastAPI app、HTTP routers、WebSocket `/ws` | 加/改接口、排查请求路由 |
| `deeptutor/app/` | `TurnApplicationService`、SDK facade、turn 受理/持久化/重放 | 改“一轮对话怎么被接收和恢复” |
| `deeptutor/runtime/` | TurnEngine、ChatOrchestrator、registry、StreamBus、coordination、bootstrap | 改能力选择、注册、流事件、并发/租约 |
| `deeptutor/core/` | `UnifiedContext`、StreamEvent、Tool/Capability 协议、turn request | 改跨层数据契约 |
| `deeptutor/agents/` | 模型侧实现：`loop/` 公共循环，`chat/`、`research/`、`visualize/`、`math_animator/`、`video_lesson/` 等 | 改提示词循环、工具调用、回答生成 |
| `deeptutor/capabilities/` | 接管整轮的能力包：`mastery/`、`reading/`、`solve/`、`ask_questions/`、`creator/` 等 | 改某个学习模式的行为 |
| `deeptutor/tools/` | 工具包装与实现；`builtin/__init__.py` 是内置工具类，`builtin_specs.py` 是名字/懒加载表；具体逻辑散在 `tools/*.py` | 加工具、改工具参数/返回 |
| `deeptutor/learning/` | 精通之路领域层：证据校验、评分、调度、存储、题目 | 改掌握度规则、间隔复习、精通数据 |
| `deeptutor/services/` | 跨功能服务：`session/`、`llm/`、`rag/`、`memory/`、`persona/`、`workspace/`、`parsing/`、`config/` | 改会话、模型、RAG、记忆、人格、路径 |
| `deeptutor/knowledge/` | 知识库导入、索引、manifest、进度 | 改知识库/检索链路 |
| `deeptutor/modules/` | 模块 manifest 与生命周期；capability/tool 的 class_path 在这里 | 新增/下线能力、排查注册 |
| `deeptutor/i18n/`、`events/`、`notes/`、`reading/`、`book/`、`co_writer/` | 各自领域包 | 改对应功能 |

### 3.2 前端 `web/`

| 路径 | 职责 | 什么时候来这里 |
| --- | --- | --- |
| `web/app/` | Next.js App Router。`(workspace)` 是主工作区，`(utility)` 是内存/知识库/设置等，另有 `(settings)`、`(auth)`、`(admin)` | 加页面、改路由布局 |
| `web/features/chat/` | **当前聊天主实现**：`ChatWorkspace`、`ChatMessageList`、transport、trace | 改聊天界面、消息折叠、WebSocket 重放 |
| `web/components/chat/home/` | 输入框、模式菜单、精通卡片、`AskUserOptions`、附件等 | 改 composer 和聊天周边卡片 |
| `web/components/common/` | Markdown 渲染、`AssistantResponse`、`InlineFileCard`、`ZoomableLightbox` | 改消息里的富文本/图片/文件 |
| `web/components/Mermaid.tsx` | mermaid 渲染与主题、尺寸处理 | 改流程图显示 |
| `web/components/sidebar/` | `SidebarShell`、`WorkspaceSidebar`、`LearningNavigation`、命令面板 | 改左侧栏、学习记录树 |
| `web/features/ui-layout/modern/` | 现代皮肤的布局 token 与 `modern.css` | 改间距、侧栏样式、控件外观 |
| `web/lib/` | API client 和领域 helper；`learning-*`、`mastery-*`、`session-*` 都在这里 | 加接口调用、路由/数据转换 |
| `web/shared/` | 无业务依赖的 UI / API / storage 原语 | 写可复用组件 |
| `web/contracts/` | 生成的 API / turn 契约 | 生成物，不手改 |
| `web/proxy.ts` | 前端到后端的 API/WS 代理 | 排查跨端口/代理问题 |

前端依赖规则（见 `ARCHITECTURE.md`）：不要制造循环依赖；`shared` 不能反向依赖 feature；业务状态优先复用现有 transport/store，不要在组件里再写一套 WebSocket 或持久化。

## 4. 一次对话怎么走

1. 浏览器里的 `web/features/chat/transport/UnifiedTurnClient.ts` 发起 turn；WebSocket 端点是 `deeptutor/api/routers/unified_ws.py`（本机 `ws://127.0.0.1:8001/ws`）。
2. `deeptutor/app/service.py` 受理并持久化，交给 `deeptutor/runtime/turn_engine.py`；`runtime/orchestrator.py` 根据 `UnifiedContext` 选择 capability。
3. Capability 跑 `deeptutor/agents/loop/` 的公共循环，或自己的 pipeline；工具经 `runtime/registry/tool_registry.py` 授权；人格和提示块在 `agents/loop/prompt_blocks.py`、`services/persona/` 注入。
4. 事件由 `core/stream.py` 定义、`runtime/stream_bus.py` 分发，turn runtime 持久化；前端按事件重放成消息、过程记录、工具卡、页图。
5. 所有 capability 最后都走 `deeptutor/agents/_shared/capability_result.py` 的统一结果信封（含 usage/cost）。

**排查顺序**：先确认是浏览器事件、API 返回、turn 持久化，还是模型/工具行为；不要一上来改 prompt。会话和 turn 的原始数据在 `data/user/chat_history.db`。

## 5. 常见改动落点

| 想改什么 | 先看这些文件 | 备注 |
| --- | --- | --- |
| 聊天页布局/输入框 | `web/features/chat/components/ChatWorkspace.tsx`、`web/components/chat/home/ChatComposer.tsx` | `ChatWorkspace` 是 live 入口；`web/components/chat/` 里还有旧/周边组件，先确认 import 链 |
| 消息正文、折叠、过程记录 | `web/features/chat/messages/ChatMessageList.tsx`、`web/components/common/AssistantResponse.tsx` | 正文/思维链/工具卡的分段和折叠都在这里；改动前先看 `buildMessageBlocks` |
| Markdown、公式、代码块 | `web/components/common/RichMarkdownRenderer.tsx`、`MarkdownRenderer.tsx`、`RichCodeBlock.tsx` | 图片分支和 `attachment:` 链接也在这里 |
| 左侧栏、学习记录 | `web/components/sidebar/SidebarShell.tsx`、`LearningNavigation.tsx`、`WorkspaceSidebar.tsx`、`web/features/ui-layout/modern/modern.css` | 精通记录行的“新建会话”加号在 `LearningNavigation` + `dt-record-new-session` |
| 精通之路行为 | `deeptutor/capabilities/mastery/{capability,loop,tools}.py`、`deeptutor/capabilities/mastery/prompts/{zh,en}/mastery_loop.yaml` | 提示词是软约束；硬门在 `deeptutor/learning/lesson_evidence.py` |
| 精通数据/评分/复习 | `deeptutor/learning/{service,lesson_evidence,scheduler,grading,storage,models}.py`、`data/user/workspace/learning/mastery/mastery.sqlite3` | 先分清“教学内容”和“掌握度证据”，不要用页面状态替代证据 |
| 精通页卡/页码定位 | `web/components/chat/home/MasterySourcePresentation.tsx`、`AskUserOptions.tsx` | 页卡默认折叠、按正文页码就近插入；页码提及解析在 `AskUserOptions` |
| 人格 / 默认老师 | `deeptutor/services/persona/service.py`、`presets/teacher/PERSONA.md`、`data/user/workspace/personas/teacher/PERSONA.md`、`deeptutor/services/session/turns/executor.py` | 不选人格时默认回退 `teacher`；改 presets 是改新装默认，改 data 是改本机当前 |
| 加/改工具 | `deeptutor/tools/builtin_specs.py`、`deeptutor/tools/builtin/__init__.py`、`deeptutor/modules/manifests/*.json` 的 `tools` | 工具名、class_path、顺序、能力可用列表要同步 |
| 加/改 capability | `deeptutor/modules/manifests/*.json` 的 `capabilities`、`deeptutor/capabilities/*/capability.py`、`.../loop.py` | manifest 的 `class_path` 和 `tools_used` 是注册权威 |
| 加 HTTP 接口 | `deeptutor/api/routers/*.py`、`deeptutor/app/service.py`（需要 durable 行为时） | 前端对应 `web/lib/*-api.ts` |
| 改流式事件/重放 | `deeptutor/core/stream.py`、`runtime/stream_bus.py`、`web/features/chat/transport/` | 先读 `EVENTS_AND_PROGRESS.md`，不要只改一端 |
| 改知识库/检索 | `deeptutor/knowledge/`、`deeptutor/services/rag/`、`deeptutor/tools/rag_tool.py`、`web/features/knowledge/` | 索引和查询是两条链，改前先确认数据是否需重建 |
| mermaid / 图片放大 | `web/components/Mermaid.tsx`、`web/components/common/ZoomableLightbox.tsx`、`web/components/chat/preview/previewers/ImagePreview.tsx`、`web/components/common/InlineFileCard.tsx` | 宽图要保留固有像素宽 + 横向滚动；详情见 `LOCAL_NOTES.md` 第十二节 |

## 6. 数据放在哪里

| 路径 | 内容 |
| --- | --- |
| `data/user/chat_history.db` | 会话、消息、turn、题库/练习等 SQLite 主库 |
| `data/user/workspace/learning/mastery/mastery.sqlite3` | 精通之路的目标、知识点、进度、证据 |
| `data/user/workspace/reading/_catalog.sqlite3` | 阅读工作区目录 |
| `data/user/settings/*.json`、`*.yaml` | 模型、系统、解析、集成等运行设置；`.env` 不是应用配置源 |
| `data/user/workspace/personas/*/PERSONA.md` | 当前用户的人格文件 |
| `data/knowledge_bases/` | 知识库索引与源数据 |
| `data/parse_cache/` | 文档解析缓存 |
| `data/user/logs/` | 日志 |

`DEEPTUTOR_HOME` 指向的是 `data/` 的父目录，不是 `data/` 本身。外部 Content Workspace 的私有学习数据在 `<workspace>/.deeptutor/data/`。备份见 [`DATA_STORAGE.md`](DATA_STORAGE.md)；改 schema/迁移前先备份。

## 7. 本机运行与验证

| 场景 | 命令/入口 |
| --- | --- |
| 生产一键启动 | `.venv\Scripts\python.exe scripts\start_web.py`；后端 8001、前端 3782，首次/指纹变化会构建到 `web/.next-deeptutor` |
| 开发模式 | 后端 `python -m deeptutor.api.run_server`；前端 `cd web && npm run dev -- -p 3782` |
| 只重建生产前端 | 先停 3782，再在 `web/` 执行 `DEEPTUTOR_NEXT_DIST_DIR=.next-deeptutor npm run build` |
| 重启后端 | `X:/AI/_restart_backend.ps1`（本机辅助脚本，仓库外） |
| 启动生产前端 | `X:/AI/_start_web.ps1`（本机辅助脚本，仓库外） |
| 前端类型检查 | `cd web && npx tsc --noEmit -p tsconfig.json` |
| 前端测试 | `cd web && npm run test:node`；全量检查见 `package.json` 的 `check` |

**三个本机坑**：

1. `npm run build` 默认写 `web/.next`，不是 3782 读取的 `web/.next-deeptutor`。不设置 `DEEPTUTOR_NEXT_DIST_DIR` 就等于没更新生产前端。
2. 3782 在跑时构建 `.next-deeptutor` 可能因 Windows 锁定 `sharp` 的 DLL 报 `EPERM`；先停 3782。
3. 本机 X: 盘上源文件的 mtime 有时不更新，webpack 可能复用旧缓存，出现“代码改了、界面没变”。停服后删除 `web/.next-deeptutor`，干净重建，再用浏览器确认新构建的 `BUILD_ID`。

Python 侧：本机 `.venv` 目前**没有安装 pytest**，不能假装跑过 `pytest`。小改动至少做 `py_compile`，再用真实请求/真实页面复现；涉及 schema、迁移、并发或安全边界时再补测试环境。

## 8. 本地定制索引（相对上游）

这些是本机已经改过、以后容易被误回退的部分，细节都在 [`LOCAL_NOTES.md`](../LOCAL_NOTES.md)：

| 主题 | 主要文件 | LOCAL_NOTES |
| --- | --- | --- |
| mermaid 宽图保持可读、知识库页图可放大 | `web/components/Mermaid.tsx`、`ZoomableLightbox.tsx`、`ImagePreview.tsx`、`MasterySourcePresentation.tsx` | 第十二节 |
| 默认 teacher 人格、侧栏顶部“新对话”、精通记账容错 | `services/session/turns/executor.py`、`SidebarShell.tsx`、`capabilities/mastery/tools.py`、`prompts/{zh,en}/mastery_loop.yaml` | 第十三节 |
| 精通记录行右侧“+ 新建会话” | `api/routers/mastery_path.py`、`web/lib/learning-api.ts`、`LearningNavigation.tsx`、`modern.css` | 第十四节 |
| 精通正文不被折进过程记录、页图按页码插入、默认折叠 | `web/features/chat/messages/ChatMessageList.tsx`、`MasterySourcePresentation.tsx`、`AskUserOptions.tsx` | 第十五节 |

## 9. 文档导航：哪些该读，哪些可以忽略

| 文档 | 用途 |
| --- | --- |
| [`AGENTS.md`](../AGENTS.md) | 架构总览、三层入口、capability 列表、关键文件；接手先读 |
| [`docs-for-dev/README.md`](README.md) | 任务 → 文档的索引，找 canonical 页面 |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | 请求链路和每层 owner |
| [`TOOLS_AND_CAPABILITIES.md`](TOOLS_AND_CAPABILITIES.md) | Tool/Capability 契约、挂载规则、加改流程 |
| [`DATA_STORAGE.md`](DATA_STORAGE.md) | 运行数据、workspace、备份 |
| [`RUNTIME_DESIGN.md`](RUNTIME_DESIGN.md) | 懒加载、隔离解析 worker、私有模型历史、缓存证据 |
| [`TESTING.md`](TESTING.md) | 改动后该跑什么 |
| [`LOCAL_NOTES.md`](../LOCAL_NOTES.md) | 本机端口、启动、故障、定制与回滚；改本机行为前必读 |

可以忽略、不要当代码入口的：

- `README.md`：上游项目介绍/发布说明为主，不是开发指南。
- `assets/README/README_*.md`：多语言 README。
- `assets/releases/past_releases/*.md`：历史版本发布说明。
- `docs-for-dev/CLAUDE_MODEL_SYNC.md`、`CONTAINERIZATION.md`、`remote-hermes-backend.md` 等：只在做对应集成时读。

> 这些历史/翻译文档目前保留，是为了不破坏上游 README 的链接；它们不是本项目的代码路径。以后要精简可以删，但删除时同步检查链接。

## 10. 接手检查清单

- [ ] `git status` 干净；最近提交能看懂（`git log --oneline -5`）。
- [ ] 8001 / 3782 是否在跑；打开页面确认是**当前构建**，不是旧 chunk。
- [ ] 改前端后已重建 `.next-deeptutor`，而不是只跑了 `npm run build`。
- [ ] 改后端后已重启 8001；改人格后确认请求确实带了 persona，或被默认回退逻辑覆盖。
- [ ] 改精通/证据前，先备份 `data/user/chat_history.db` 与 `data/user/workspace/learning/mastery/mastery.sqlite3`。
- [ ] 不把 `data/`、`.next*`、日志、临时探针脚本提交进 Git。

---

维护建议：这份地图只写“入口、owner、常见落点”。具体契约、状态机和测试证据仍以 `docs-for-dev/` 的 canonical 页面为准；本机专属内容继续追加到 `LOCAL_NOTES.md`。
