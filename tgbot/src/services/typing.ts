import type TelegramBot from 'node-telegram-bot-api';

export function withTyping(
  bot: TelegramBot,
  chatId: number,
  action: TelegramBot.ChatAction = 'typing'
) {
  let alive = true;
  const tick = () => {
    if (!alive) return;
    bot.sendChatAction(chatId, action).catch(() => {});
  };
  tick();
  const timer = setInterval(tick, 4500);
  return () => {
    alive = false;
    clearInterval(timer);
  };
}
