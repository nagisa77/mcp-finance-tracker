const TelegramBot = require('node-telegram-bot-api');

const token = process.env.TELEGRAM_TOKEN;

if (!token) {
  throw new Error('TELEGRAM_TOKEN environment variable is not set.');
}

const bot = new TelegramBot(token, { polling: true });

bot.on('message', (msg) => {
  const chatId = msg.chat.id;

  if (typeof msg.text === 'string') {
    bot.sendMessage(chatId, msg.text);
  } else {
    bot.sendMessage(chatId, 'I can only echo text messages right now.');
  }
});

bot.on('polling_error', (error) => {
  console.error('Polling error:', error.message);
});

console.log('Telegram echo bot is up and running.');
