# FeedSystem Video

一个基于 FastAPI 的短视频流系统，包含账号、视频上传发布、推荐/关注视频流、点赞、评论、关注关系、Redis 缓存与 RabbitMQ 异步事件处理。项目已内置一个静态前端页面，可直接通过后端根路径访问。

## 功能核查

已完成的视频流系统基本功能：

| 模块 | 状态 | 说明 |
| --- | --- | --- |
| 账号 | 已完成 | 注册、登录、登出、改名、改密、按 ID/用户名查询 |
| 鉴权 | 已完成 | JWT Bearer Token，支持 Redis token 缓存与撤销校验 |
| 视频 | 已完成 | MP4 上传、封面上传、发布视频、作者视频列表、视频详情 |
| 视频流 | 已完成 | 最新流、关注流、点赞数排序、热度排序 |
| 互动 | 已完成 | 点赞、取消点赞、查询是否点赞、我的点赞视频 |
| 评论 | 已完成 | 发布评论、删除自己的评论、视频评论列表 |
| 社交 | 已完成 | 关注、取消关注、粉丝列表、关注作者列表 |
| 异步与缓存 | 已完成 | RabbitMQ 事件、worker 消费、Redis 全局时间线和热度缓存；服务不可用时部分路径可降级到数据库写入/查询 |
| 前端 | 已完成 | 登录注册、浏览视频流、上传发布、点赞、关注、评论、查看详情 |

需要注意：当前项目没有自动化测试；生产部署前建议补充接口测试、上传文件安全校验、配置脱敏和更细的权限/错误码策略。

## 技术栈

- Python 3.12
- FastAPI + Uvicorn
- SQLAlchemy 2.x + MySQL
- Redis
- RabbitMQ
- 原生 HTML/CSS/JavaScript 前端

## 快速启动

推荐使用 Docker Compose 一次启动 MySQL、Redis、RabbitMQ、API 和 worker：

```bash
docker compose up --build
```

启动后访问：

- 前端页面：http://localhost:8080/
- API 文档：http://localhost:8080/docs
- RabbitMQ 管理台：http://localhost:15672/ ，默认账号 `admin`，密码 `password123`

停止服务：

```bash
docker compose down
```

如需清空本地数据卷：

```bash
docker compose down -v
```

## 本地 Python 启动

先准备 MySQL、Redis、RabbitMQ，并确认 `configs/config.yaml` 中连接信息正确。

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m app.main
```

另开一个终端启动异步 worker：

```bash
python -m app.worker
```

也可以通过环境变量覆盖配置，例如：

```bash
$env:DB_HOST="localhost"
$env:DB_PORT="3307"
$env:DB_USER="root"
$env:DB_PASSWORD="123456"
$env:DB_NAME="feedsystem"
python -m app.main
```

## 前端使用

打开 http://localhost:8080/ 后：

1. 使用顶部账号区注册并登录。
2. 在“发布视频”区域选择 `.mp4` 视频和 `.jpg/.jpeg/.png/.webp` 封面。
3. 发布后可在“最新”视频流看到新视频。
4. 切换“热门”“点赞榜”“关注”“我赞过”查看不同视频流。
5. 点击视频卡片的“详情”查看和发布评论。

上传文件会保存到 `.run/uploads`，并通过 `/static/...` 对外访问。

## 主要 API

所有接口均为 `POST`。需要登录的接口使用：

```http
Authorization: Bearer <token>
```

账号：

- `/account/register`
- `/account/login`
- `/account/logout`
- `/account/rename`
- `/account/changePassword`
- `/account/findByID`
- `/account/findByUsername`

视频：

- `/video/uploadVideo`
- `/video/uploadCover`
- `/video/publish`
- `/video/listByAuthorID`
- `/video/getDetail`

视频流：

- `/feed/listLatest`
- `/feed/listLikesCount`
- `/feed/listByFollowing`
- `/feed/listByPopularity`

点赞：

- `/like/like`
- `/like/unlike`
- `/like/isLiked`
- `/like/listMyLikedVideos`

评论：

- `/comment/publish`
- `/comment/delete`
- `/comment/listAll`

社交：

- `/social/follow`
- `/social/unfollow`
- `/social/getAllFollowers`
- `/social/getAllVloggers`

## 配置说明

默认配置文件：

- `configs/config.yaml`：本地运行配置
- `configs/config.docker.yaml`：Docker Compose 内部网络配置

可通过 `FEEDSYSTEM_CONFIG` 指定配置文件路径，也可通过环境变量覆盖数据库、Redis、RabbitMQ 和服务端口配置。

## 项目结构

```text
app/
  api/              # FastAPI 路由
  web/              # 内置前端页面
  main.py           # API 入口和静态资源挂载
  worker.py         # RabbitMQ 消费者
  models.py         # SQLAlchemy 数据模型
  schemas.py        # 请求模型
  serializers.py    # 响应序列化
configs/            # 配置文件
docker-compose.yml  # 本地依赖与服务编排
Dockerfile          # API/worker 镜像
```

## 验证建议

基础冒烟流程：

1. 启动 `docker compose up --build`。
2. 访问 `/docs` 确认 API 可用。
3. 在前端注册、登录。
4. 上传视频和封面并发布。
5. 刷新“最新”视频流，确认可播放。
6. 对视频进行点赞、评论、关注作者。
7. 切换“关注”“我赞过”“点赞榜”“热门”验证数据变化。
