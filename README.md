# DeepSock - DeepSeek 多币种合约交易机器人

一个基于 DeepSeek (或其他 OpenAI 兼容 API) 分析市场并使用 Binance Future API 执行交易的 Python 自动交易机器人。

## 功能

*   **多币种支持**: 可同时监控和交易多个合约 (BTC/USDT, ETH/USDT 等)。
*   **AI 驱动决策**: 利用 LLM 生成交易信号、止损止盈和信心度。
*   **实时持仓**: 准确获取并显示交易所实时持仓信息。
*   **灵活配置**: 通过 `.env` 文件配置 API 密钥、交易对、杠杆、模型等所有参数。
*   **版本选择**:
    *   `deepsock.py`: 标准版，基于 K 线和技术指标进行 AI 分析。
    *   `deepsock_ai.py`: 增强版，在标准版基础上整合了 BlockBeats 等 RSS 实时新闻，为 AI 决策提供更多市场信息。

## 依赖

*   `Docker` (推荐) 或 `Python 3.8+`
*   相关 Python 包见 `requirements.txt`

## 快速开始

### 1. 准备工作

*   **克隆项目**:
    ```bash
    git clone <your-repo-url>
    cd deepsock
    ```
*   **配置 `.env` 文件**:
    *   复制 `.env.example` 为 `.env`: `cp .env.example .env`
    *   编辑 `.env` 文件，填入您的 `Binance` 和 `LLM` (如 DeepSeek) API 密钥及其他参数。

### 2.A. 使用 Docker (推荐)

*   **构建镜像**:
    ```bash
    docker build -t deepsock .
    ```
*   **运行**:
    *   标准版:
        ```bash
        docker run --env-file .env deepsock python deepsock.py
        ```
    *   增强版:
        ```bash
        docker run --env-file .env deepsock python deepsock_ai.py
        ```
*   **查看日志**:
    *   如果您在后台运行容器（使用 `-d` 标志），或者想查看正在运行的容器的日志，可以使用 `docker logs` 命令。
    *   **获取容器 ID 或名称**: 运行 `docker ps` 查看当前运行的容器列表。
    *   **查看日志**:
        ```bash
        docker logs <CONTAINER_ID_OR_NAME>
        ```
    *   **实时跟踪日志**: 添加 `-f` 标志可以像 `tail -f` 一样实时查看日志输出。
        ```bash
        docker logs -f <CONTAINER_ID_OR_NAME>
        ```

### 2.B. 使用 Docker Compose

*   **构建并启动**:
    *   标准版: 编辑 `docker-compose.yml`，确保 `command` 是 `python deepsock.py`，然后运行：
        ```bash
        docker-compose up --build
        ```
    *   增强版: 编辑 `docker-compose.yml`，取消注释 `command: python deepsock_ai.py` 行，并注释掉默认的 `command` 行，然后运行：
        ```bash
        docker-compose up --build
        ```
*   **后台运行**: 添加 `-d` 参数，例如 `docker-compose up -d --build`。
*   **查看日志**:
    *   **查看所有服务日志**:
        ```bash
        docker-compose logs
        ```
    *   **实时跟踪所有服务日志**:
        ```bash
        docker-compose logs -f
        ```
    *   **查看特定服务日志** (例如，如果您在 `docker-compose.yml` 中定义的服务名为 `deepsock`):
        ```bash
        docker-compose logs deepsock
        ```
    *   **实时跟踪特定服务日志**:
        ```bash
        docker-compose logs -f deepsock
        ```
*   **停止**: 在项目目录下运行 `docker-compose down`。

### 2.C. 本地运行 (不使用 Docker)

*   **安装依赖**:
    ```bash
    pip install -r requirements.txt
    ```
*   **配置 `.env` 文件**。
*   **运行**:
    *   标准版: `python deepsock.py`
    *   增强版: `python deepsock_ai.py`

**⚠️ 警告: 加密货币交易风险极高，可能导致巨额亏损。本项目代码仅供学习和研究使用。任何基于此代码进行的实盘交易，您需自行承担全部责任。投资有风险，入市须谨慎。**