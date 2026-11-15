# 温度日志管线验证证据

本目录为批次测试证据，不进入源码。全部通过。

- `test_tempcalc.py`：读数保持/裁剪/超温段合并/缺测单列/总量守恒等 9 组纯函数用例。`python3 -I test_tempcalc.py`（无需第三方依赖）。
- `smoke_api.py`：sqlite + 假 Redis 的 56 项 API 与服务集成检查：修订忽略/幂等/分歧拒收/内部冲突拒收、待重算阻断研究、整批发布、并发更正拒绝过期计算、失败保留旧版、修复后发布、手填样本兼容、观察员权限。需 venv 安装 fastapi/sqlalchemy/PyJWT/redis/httpx。
- `smoke_worker.py`：worker 进程恢复、双队列、重算发布与研究计算端到端（另需 scipy）。
- `smoke_seed.py`：演示种子幂等与演示日志计算结果（T01 超温 40 分钟 2 段、缺测 20 分钟；T02 超温 40 分钟 1 段）。
- `render_pages.mjs`：五个前端页面无浏览器渲染冒烟。`node render_pages.mjs`。
