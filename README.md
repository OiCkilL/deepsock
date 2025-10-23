# DeepSock - DeepSeek 多币种合约交易机器人

一个利用 DeepSeek (或其他 OpenAI 兼容 API) 分析市场并自动执行交易的 Python 加密货币期货合约机器人。

## 功能亮点

*   **AI 驱动决策**: 核心交易逻辑由强大的 LLM 驱动，生成精准的交易信号、止损止盈位和信心度评估。
*   **实时新闻整合**(增强版): 独家集成 BlockBeats 等权威 RSS 新闻源，将最新市场动态实时注入 AI 分析流程，实现更智能的决策。
*   **动态仓位管理**(增强版): AI 不仅决定买卖方向，还能根据市场分析和账户风险状况，智能计算并建议每次交易的最优仓位大小。
*   **多币种支持**: 可同时监控和交易多个加密货币合约 (如 BTC/USDT, ETH/USDT 等)。
*   **灵活配置**: 通过简单的 `.env` 文件即可配置所有参数，包括交易对、杠杆、模型选择等。
*   **版本选择**:
    *   `deepsock.py`: 标准版，基于 K 线和技术指标进行 AI 分析。
    *   `deepsock_ai.py`: **增强版**，在标准版基础上**整合实时新闻流**，为 AI 决策提供更全面的市场信息，实现更高级的自动化。

## 依赖

*   `Docker` (推荐) 或 `Python 3.8+`
*   相关 Python 包见 `requirements.txt`

## 快速开始

### 1. 准备工作

* **克隆项目**:

  ```bash
  git clone <your-repo-url>
  cd deepsock
  ```

* **配置 `.env` 文件**:

  *   复制 `.env.example` 为 `.env`: `cp .env.example .env`
  *   编辑 `.env` 文件，填入您的交易所 API 密钥和 LLM (如 DeepSeek) API 密钥及其他参数。

### 2.A. 使用 Docker (推荐)

* **构建镜像**:

  ```bash
  docker build -t deepsock .
  ```

* **运行**:

  * 标准版:

    ```bash
    docker run --env-file .env deepsock python deepsock.py
    ```

  * **增强版**(推荐 - 包含新闻)

    ```bash
    docker run --env-file .env deepsock python deepsock_ai.py
    ```

* **查看日志**:

  * 如果您在后台运行容器（使用 `-d` 标志），或者想查看正在运行的容器的日志，可以使用 `docker logs` 命令。

  * **获取容器 ID 或名称**: 运行 `docker ps` 查看当前运行的容器列表。

  * **查看日志**:

    ```bash
    docker logs <CONTAINER_ID_OR_NAME>
    ```

  * **实时跟踪日志**: 添加 `-f` 标志可以像 `tail -f` 一样实时查看日志输出。

    ```bash
    docker logs -f <CONTAINER_ID_OR_NAME>
    ```

### 2.B. 使用 Docker Compose

* **构建并启动**:

  * **增强版**(推荐):

    ```bash
    docker-compose up --build
    ```

    *(请确保 `docker-compose.yml` 中的 `command` 指向 `python deepsock_ai.py`)*

  * 标准版: 编辑 `docker-compose.yml`，将 `command` 改为 `python deepsock.py`，然后运行：

    ```bash
    docker-compose up --build
    ```

* **后台运行**: 添加 `-d` 参数，例如 `docker-compose up -d --build`。

* **查看日志**:

  * **查看所有服务日志**:

    ```bash
    docker-compose logs
    ```

  * **实时跟踪所有服务日志**:

    ```bash
    docker-compose logs -f
    ```

  * **查看特定服务日志** (例如，如果您在 `docker-compose.yml` 中定义的服务名为 `deepsock`):

    ```bash
    docker-compose logs deepsock
    ```

  * **实时跟踪特定服务日志**:

    ```bash
    docker-compose logs -f deepsock
    ```

* **停止**: 在项目目录下运行 `docker-compose down`。

### 2.C. 本地运行 (不使用 Docker)

* **安装依赖**:

  ```bash
  pip install -r requirements.txt
  ```

* **配置 `.env` 文件**。

* **运行**:

  *   标准版: `python deepsock.py`
  *   **增强版**(推荐): `python deepsock_ai.py`

**⚠️ 警告: 加密货币交易风险极高，可能导致巨额亏损。本项目代码仅供学习和研究使用。任何基于此代码进行的实盘交易，您需自行承担全部责任。投资有风险，入市须谨慎。**
