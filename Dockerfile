FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x /app/start.sh

ENV APP_NAME="Multi Market Quant Suite"
ENV SECRET_KEY="change-me-in-production"
ENV ACCESS_TOKEN_EXPIRE_MINUTES=720
ENV DATABASE_URL="sqlite:///./quant_suite.db"
ENV CREDENTIALS_KEY="replace-with-32-url-safe-base64-key"
ENV HOST="0.0.0.0"
ENV PORT="8000"

EXPOSE 8000
CMD ["./start.sh"]
