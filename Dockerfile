FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY finance_tracker ./

ENV DB_HOST=mysql \
    DB_PORT=3306 \
    DB_USER=finance \
    DB_PASSWORD=financepass \
    DB_NAME=finance_tracker

CMD ["python", "-m", "finance_tracker"]
