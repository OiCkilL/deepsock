# 使用 Python 3.12 官方镜像作为基础镜像
FROM python:3.12-slim

# 设置工作目录
WORKDIR /app

# 复制依赖文件到工作目录
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 将当前目录的代码和 .env 文件复制到工作目录
# 注意：您需要将 .env 文件放在与 Dockerfile 相同的目录下
COPY . .

# 暴露可能需要的端口（如果您的应用有Web界面或需要监听端口）
# EXPOSE 8000

# 设置默认运行的命令
# 您可以在运行容器时覆盖此命令，例如：docker run your_image python deepsock_ai.py
CMD ["python", "deepsock_ai.py"]
