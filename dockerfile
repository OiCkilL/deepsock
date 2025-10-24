# 使用 Python 3.12 官方镜像作为基础镜像
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

CMD ["python", "deepsock.py"]