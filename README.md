# FeedSystem Video

FeedSystem Video 是一个基于 FastAPI 的短视频流系统示例项目。它提供账号登录、视频上传发布、视频流浏览、点赞评论、关注关系，以及 Redis 缓存和 RabbitMQ 异步事件处理。

项目内置了一个轻量前端页面，启动后访问 `http://localhost:8080/` 即可使用。

## 当前能力

项目当前已经覆盖短视频流系统的主要业务路径，适合作为课程设计、原型验证或后续工程化扩展的基础版本。

| 模块 | 能力 |
| --- | --- |
| 账号 | 注册、登录、登出、改名、改密、按 ID 或用户名查询 |
| 鉴权 | JWT Bearer Token，支持 Redis 缓存 token 与撤销校验 |
| 视频 | 上传 MP4、上传封面、发布视频、查询详情、查询作者作品 |
| 视频流 | 最新视频流、关注视频流、点赞榜、热度榜 |
| 点赞 | 点赞、取消点赞、查询点赞状态、查看我赞过的视频 |
| 评论 | 发布评论、删除自己的评论、查看视频评论 |
| 社交 | 关注、取消关注、查看粉丝、查看关注作者 |
| 异步处理 | RabbitMQ 投递点赞、评论、关注、热度和时间线事件，worker 异步消费 |
| 缓存 | Redis 缓存登录状态、全局时间线、视频详情和热度窗口 |
| 前端 | 登录注册、视频流切换、上传发布、播放视频、点赞、关注、评论和详情面板 |

## 架构概览

```text
Browser
  |
  | HTTP / JSON / multipart upload
  v
FastAPI API
  |
  +-- MySQL: 账号、视频、点赞、评论、关注、outbox
  +-- Redis: token、限流、视频详情、全局时间线、热度榜
  +-- RabbitMQ: 点赞、评论、关注、热度、时间线事件
          |
          v
       worker
```

核心入口：

- `app/main.py`：FastAPI 应用入口，挂载 API、上传文件和前端静态页面
- `app/api/`：业务接口
- `app/worker.py`：RabbitMQ 消费者
- `app/web/`：内置前端
- `configs/`：本地和 Docker 配置

## 技术栈

- Python 3.12
- FastAPI + Uvicorn
- SQLAlchemy 2.x
- MySQL 8
- Redis 7
- RabbitMQ 3
- 原生 HTML / CSS / JavaScript
- Docker Compose

## 快速启动

推荐用 Docker Compose 启动完整环境：

```bash
docker compose up --build
```

启动完成后访问：

- 前端页面：`http://localhost:8080/`
- API 文档：`http://localhost:8080/docs`
- RabbitMQ 管理台：`http://localhost:15672/`

RabbitMQ 默认账号：

```text
username: admin
password: password123
```

停止服务：

```bash
docker compose down
```

清空 Docker 数据卷：

```bash
docker compose down -v
```

## 本地运行

本地运行前需要先准备 MySQL、Redis 和 RabbitMQ，并确认 `configs/config.yaml` 里的连接信息可用。

安装依赖：

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

启动 API：

```bash
python -m app.main
```

启动 worker：

```bash
python -m app.worker
```

也可以通过环境变量覆盖配置：

```powershell
$env:DB_HOST="localhost"
$env:DB_PORT="3307"
$env:DB_USER="root"
$env:DB_PASSWORD="123456"
$env:DB_NAME="feedsystem"
$env:REDIS_HOST="localhost"
$env:RABBITMQ_HOST="localhost"
python -m app.main
```

## 前端使用

访问 `http://localhost:8080/` 后，可以完成下面的流程：

1. 注册账号并登录。
2. 上传 `.mp4` 视频文件和 `.jpg`、`.jpeg`、`.png` 或 `.webp` 封面。
3. 发布视频，刷新“最新”视频流。
4. 切换“热门”“点赞榜”“关注”“我赞过”等视频流。
5. 播放视频，点赞或取消点赞。
6. 查看视频详情，发布或删除自己的评论。
7. 关注或取消关注视频作者。

上传文件默认保存到 `.run/uploads`，并通过 `/static/...` 地址访问。

## API 概览

所有业务接口均使用 `POST`。需要登录的接口使用 Bearer Token：

```http
Authorization: Bearer <token>
```

账号接口：

| 接口 | 说明 |
| --- | --- |
| `/account/register` | 注册 |
| `/account/login` | 登录并返回 token |
| `/account/logout` | 登出并撤销 token |
| `/account/rename` | 修改用户名 |
| `/account/changePassword` | 修改密码 |
| `/account/findByID` | 按 ID 查询账号 |
| `/account/findByUsername` | 按用户名查询账号 |

视频接口：

| 接口 | 说明 |
| --- | --- |
| `/video/uploadVideo` | 上传 MP4 视频 |
| `/video/uploadCover` | 上传封面 |
| `/video/publish` | 发布视频 |
| `/video/listByAuthorID` | 查询作者视频 |
| `/video/getDetail` | 查询视频详情 |

视频流接口：

| 接口 | 说明 |
| --- | --- |
| `/feed/listLatest` | 最新视频流 |
| `/feed/listLikesCount` | 按点赞数排序 |
| `/feed/listByFollowing` | 关注作者视频流 |
| `/feed/listByPopularity` | 热度视频流 |

互动接口：

| 接口 | 说明 |
| --- | --- |
| `/like/like` | 点赞 |
| `/like/unlike` | 取消点赞 |
| `/like/isLiked` | 查询是否点赞 |
| `/like/listMyLikedVideos` | 我赞过的视频 |
| `/comment/publish` | 发布评论 |
| `/comment/delete` | 删除评论 |
| `/comment/listAll` | 查看视频评论 |
| `/social/follow` | 关注作者 |
| `/social/unfollow` | 取消关注 |
| `/social/getAllFollowers` | 查看粉丝 |
| `/social/getAllVloggers` | 查看关注作者 |

## 配置

配置文件：

- `configs/config.yaml`：本地运行配置
- `configs/config.docker.yaml`：Docker Compose 环境配置

支持通过 `FEEDSYSTEM_CONFIG` 指定配置文件：

```powershell
$env:FEEDSYSTEM_CONFIG="configs/config.yaml"
python -m app.main
```

也支持通过环境变量覆盖常用配置：

| 环境变量 | 说明 |
| --- | --- |
| `PORT` | API 端口 |
| `DB_HOST` / `DB_PORT` / `DB_USER` / `DB_PASSWORD` / `DB_NAME` | MySQL 配置 |
| `REDIS_HOST` / `REDIS_PORT` / `REDIS_PASSWORD` / `REDIS_DB` | Redis 配置 |
| `RABBITMQ_HOST` / `RABBITMQ_PORT` / `RABBITMQ_USERNAME` / `RABBITMQ_PASSWORD` | RabbitMQ 配置 |

## 项目结构

```text
app/
  api/              FastAPI 路由
  web/              内置前端页面
  auth.py           密码哈希和 JWT
  cache.py          Redis 封装
  config.py         配置加载
  database.py       SQLAlchemy 初始化
  main.py           API 入口
  models.py         数据模型
  mq.py             RabbitMQ 封装
  schemas.py        请求模型
  serializers.py    响应序列化
  timeline.py       时间线与热度缓存
  worker.py         异步消费者
configs/
  config.yaml
  config.docker.yaml
docker-compose.yml
Dockerfile
requirements.txt
```

## 冒烟验证

启动后建议按下面流程验证：

1. 打开 `http://localhost:8080/docs`，确认 API 文档可访问。
2. 打开 `http://localhost:8080/`，注册并登录。
3. 上传视频和封面，发布视频。
4. 在“最新”中确认视频可播放。
5. 点赞、评论、关注作者。
6. 切换“点赞榜”“热门”“关注”“我赞过”，确认数据变化。

## 已知限制

- 目前没有自动化测试。
- 上传文件只做了扩展名和大小限制，生产环境应补充 MIME、内容扫描和对象存储。
- `configs/config.yaml` 不应提交真实生产连接信息，部署时建议改用环境变量或密钥管理。
- 部分接口错误码沿用了现有实现，后续可以统一为更清晰的业务错误码。
