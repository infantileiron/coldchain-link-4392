# 鲜达冷链 · 温控与损耗关联簿

给鲜达冷链 12 条线路的运营分析组，用运输背景解释温控与货损之间的关联。上游班次和温控记录进入工作簿，分析员检查缺失、执行真实统计，负责人把改善建议签核给线路主管。

原流程是调度员整理工作簿，分析员复制公式，主管在聊天记录里拍板。痛点是手填暴露分钟无法复核、缺失样本被静默删除、统计口径容易改错、建议与研究证据分离。此项目提供班次清单、样本质检、温度日志、关联分析、改善建议五个业务页面，贯穿四类实体；并含登录、审计、CSV 之外的 JSON 研究导出。登记探头与运输起止的班次，其样本暴露分钟与超温段数改由探头温度日志自动计算，逐段明细可复核；手填样本不受影响，仍可正常录入与进入研究。

## 启动

```sh
cp .env.example .env
docker compose up -d --build
docker compose exec -T backend python -m scripts.seed_demo
```

访问 http://localhost:18201 ，后端 http://localhost:19201/docs ，MySQL 映射 17701。恰好五个健康检查服务 frontend/backend/worker/db/redis。backend 与 worker 共享 `/artifacts`；Redis appendonly；数据库命名卷。停止与清空演示数据：`docker compose down -v --remove-orphans`。

## 演示账号和权限

| 邮箱 | 密码 | 权限 |
|---|---|---|
| admin@demo.local | Demo123! | 全部读写、负责人签核与审计 |
| analyst@demo.local | Demo123! | 创建和修改班次/样本、提交研究、起草建议；不能签核 |
| viewer@demo.local | Demo123! | 所有业务数据只读与下载；禁止任何写入和计算任务提交 |

JWT 有效期 8 小时，后端查数据库角色，不信任前端传入角色。密码 PBKDF2；演示使用固定盐和可公开的 JWT key，部署时通过环境变量替换 key，并为正式账号改成每用户随机盐。首次启动 SEED_DEMO=true 自动导入；失败记日志。自然键唯一约束、只插入缺失数据，重复执行不覆盖用户修改。

## 一天的业务剧本

1. 08:50 viewer 核对昨日 XD-1115-001 班次。
2. 09:00 analyst 查看 60 班次、60 条样本和缺失数据。
3. 09:10 创建 XD-1115-061，鲜达线路 01 / 冷藏。
4. 09:20 采集暴露 32 分钟、超温 3 次、货损 4.2% 的样本。
5. 09:25 在温度日志页导入探头 P-01 修订 2 的更正日志，相关班次样本标为待重算。
6. 09:27 worker 重算全部待发布样本并一起发布新版本；页面核对逐段超温时长、缺测时段与班次总量。
7. 09:30 创建冷藏温区暴露时长研究（待重算期间新建会被拒绝，旧研究不变）。
8. 09:40 Redis 队列交给 worker 计算；刷新查看真实结果。
9. 10:00 阅读散点、p 值、配对数及混杂因素警示。
10. 10:10 起草“复核线路 01 装卸等待时长”等建议，admin 签核。
11. 10:20 viewer 下载 coldchain-link-<研究id>.json 供线路主管复核。

## 温度日志与自动样本

班次登记探头编号与运输起止后，其样本的暴露分钟与超温段数不再手填，改由温度日志计算。导入批次为 `{probe, revision, points:[{ts,temp}]}`（POST /logs，页面支持 JSON 文件或文本框）。计算口径：读数保持到下一时刻，但单条读数最多覆盖“缺测间隔”（默认 10 分钟，可按班次覆盖）；裁剪到运输区间后累计超温分钟（温度严格大于阈值，阈值按班次或温区默认：冷藏 4°C、冷冻 -18°C、常温对照 25°C）与连续超温段数；相邻读数间隔超过设定间隔的时段列为缺测，不计入正常也不计入超温。逐段时长、峰值、缺测时段与班次总量（运输总时长＝实测＋缺测）在温度日志页逐样本核对。

修订规则：较低修订即使后到也整批忽略；同号修订与已接收温度有分歧（或批次内部同一时刻两个温度）则整批拒收并留痕；同号同内容幂等无变化，同号新时刻合并；更高修订整批替换并保留旧修订读数备查。任何被接收的变更都会把相关班次样本标为待重算，worker 全部算完才一起发布为新版本；任一样本失败则整批不发布、保留旧版。更正与发布并发时，发布前复核日志世代，世代已变则拒绝本次过期计算并重新排队。研究只取同一已发布版本的样本快照；存在待重算或失败样本时拒绝新建研究，已创建研究的结果不变。手填样本（未登记探头的班次）行为与此前完全一致。

## 算法与边界

Python SciPy 计算 Pearson r = sum((x-xmean)(y-ymean))/sqrt(sum((x-xmean)^2)sum((y-ymean)^2))；Spearman 使用平均秩处理并列值，再对秩求 Pearson。返回双侧 p 值、有效配对数、排除数、散点和原始快照。输入为同温区样本，x 为暴露分钟或超温次数，y 固定为货损率%。只有 x/y 均非空的配对进入计算；不做插补。少于3对、任一变量为常量，任务明确 failed。相关性不等于因果，不自动决定线路处罚。60条 seed 使用 Random(3102)；冷藏和冷冻各有一条缺失暴露，10条常温对照的暴露均20分钟，用于失败诊断。研究创建时冻结输入，后续修改样本不改变已有结果。任务失败可修复原始记录再新建研究。worker 启动恢复 queued/running 任务；单 worker 模式，不承诺多副本 exactly-once。

## 技术和目录

Python3.11 / FastAPI / SQLAlchemy / SciPy / PyMySQL / PyJWT；MySQL8.0；Redis7；Nginx1.27；原生 HTML、CSS、JS ES modules。前端无构建步骤。

- backend/src/models、schemas、services、controllers、routes 分层承载实体与业务；services/tempcalc.py 为纯函数的温度窗口计算，services/logs.py 负责修订接收规则，services/recalc.py 负责整批重算与原子发布。
- backend/src/middlewares 为 JWT 角色鉴权、请求 ID、安全响应头；异常返回可恢复错误。
- backend/scripts/seed_demo.py 导入数据（含 P-01/P-02 演示日志与两个探头班次）；migrations/001_initial.sql 说明建表策略，当前由 SQLAlchemy create_all 建表，尚未采用版本迁移工具；启动时 ensure_columns 自动为既有 MySQL 库补齐新增列，原手填数据保留。
- frontend/src/api、stores、types、components/common、hooks、pages、router、utils、constants 为请求、状态、契约、共享表格/标签/字段、表单、五页面与路由。
- 共享枚举 ROLES、STATES、ZONES：backend/src/constants/enums.py 与 frontend/src/constants/enums.js；校验在 backend/src/schemas/business.py，任务状态在 worker.py，UI 标签在 components/common/status.js。

本地开发：安装 backend/requirements.lock（真实运行环境完整依赖锁定；requirements.txt 为直接依赖）；启动本地 MySQL/Redis，设置 DATABASE_URL/REDIS_URL/JWT_SECRET 后 `uvicorn src.main:app --reload`。前端可由 Nginx 提供，代理 `/api/` 去除前缀转发给后端。

环境变量：COMPOSE_PROJECT_NAME（容器前缀）、FRONTEND_PORT/BACKEND_PORT/DB_PORT（映射）、DB_PASSWORD（演示数据库密码）、JWT_SECRET、SEED_DEMO。仅内部服务接触 Redis，不映射宿主端口。编辑班次与样本 API 支持 PUT；UI 当前以新增和浏览为主，无批量 CSV 导入、删除、分页或邮件通知。Google Fonts 需联网，无法联网则浏览器回退 serif/sans-serif。证据和测试在批次根 test-artifacts/gb-3102，不写入源码。

License: MIT。

NETWORK_SUBNET 默认 10.253.102.0/24，适配本机默认地址池耗尽的情况；迁移到其他环境可修改为空闲子网。
