# Telegram Echo Bot

This directory contains a minimal Telegram bot built with [`node-telegram-bot-api`](https://github.com/yagop/node-telegram-bot-api). The bot echoes whatever text a user sends to it.

## Configuration

Set the `TELEGRAM_TOKEN` environment variable to your bot's token provided by [BotFather](https://core.telegram.org/bots#botfather).

## Running locally

```
npm install
TELEGRAM_TOKEN=your_token npm start
```

## Docker

Build and run the container with Docker:

```
docker build -t telegram-echo-bot .
docker run -e TELEGRAM_TOKEN=your_token telegram-echo-bot
```
