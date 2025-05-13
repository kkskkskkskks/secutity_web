FROM python:3.10-slim

WORKDIR /app
# 시스템 종속성 (필요 시 추가)
RUN apt update && apt install -y build-essential

# 소스 복사 & 의존성 설치
COPY Backends/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY Backends/ .

# .env는 docker-compose.yml 또는 run 시 mount 권장
ENV FLASK_ENV=production

# 컨테이너 포트
EXPOSE 8000

# Gunicorn으로 실행
CMD ["gunicorn", "--workers", "3", "--bind", "0.0.0.0:8000", "app:create_app()"]