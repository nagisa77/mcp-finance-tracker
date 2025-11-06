import TelegramBot, { type Message } from "node-telegram-bot-api";
import http from "node:http";
import https from "node:https";
import { URL } from "node:url";

import { QUICK_ACTIONS } from "./constants/quickActions";
import { requireEnvVar } from "./config/env";
import { openai } from "./openaiClient";
import { runWorkflowFromParts } from "./services/agent";
import {
  downloadPhotoAsBase64,
  buildContentPartsWithFileIds,
  selectLargestPhoto,
} from "./services/photo";
import { withTyping } from "./services/typing";
import type {
  InputPartWithFileId,
  StoredPhoto,
  WorkflowImage,
  WorkflowResult,
} from "./types";

const token = requireEnvVar("TELEGRAM_TOKEN");
const bot = new TelegramBot(token, { polling: true });
const pendingPhotos = new Map<number, StoredPhoto[]>();

bot.setMyCommands([
  { command: "start", description: "开始使用记账机器人" },
  { command: "report", description: "生成最近开销报表" },
  { command: "compare", description: "对比本周和上周支出" },
  { command: "detail", description: "查看分类支出详情" },
]);

bot.on("message", async (msg: Message) => {
  const chatId = msg.chat.id;
  try {
    if (msg.text === "/start") {
      await bot.sendMessage(chatId, "请选择需要的功能或直接发送账单信息。", {
        reply_markup: {
          keyboard: Object.keys(QUICK_ACTIONS).map((text) => [{ text }]),
          resize_keyboard: true,
        },
      });
      return;
    }
    if (msg.text === "/report") {
      await runWithTyping(chatId, async () => {
        await sendWorkflowResult(chatId, [
          { type: "input_text", text: QUICK_ACTIONS["生成最近开销报表"] },
        ]);
      });
      return;
    }
    if (msg.text === "/compare") {
      await runWithTyping(chatId, async () => {
        await sendWorkflowResult(chatId, [
          { type: "input_text", text: QUICK_ACTIONS["对比本周和上周支出"] },
        ]);
      });
      return;
    }
    if (msg.text === "/detail") {
      await runWithTyping(chatId, async () => {
        await sendWorkflowResult(chatId, [
          { type: "input_text", text: QUICK_ACTIONS["查看分类支出详情"] },
        ]);
      });
      return;
    }

    if (Array.isArray(msg.photo) && msg.photo.length > 0) {
      const largestPhoto = selectLargestPhoto(msg.photo);
      if (!largestPhoto) {
        await bot.sendMessage(chatId, "未能识别图片，请重试。");
        return;
      }

      const storedPhoto = await downloadPhotoAsBase64(
        bot,
        token,
        largestPhoto.file_id
      );
      const existingPhotos = pendingPhotos.get(chatId) ?? [];
      existingPhotos.push(storedPhoto);
      pendingPhotos.set(chatId, existingPhotos);

      const captionText =
        typeof msg.caption === "string" ? msg.caption.trim() : "";
      if (captionText.length > 0) {
        await runWithTyping(chatId, async () => {
          const parts = await buildContentPartsWithFileIds(
            openai,
            captionText,
            existingPhotos
          );
          pendingPhotos.delete(chatId);
          await sendWorkflowResult(chatId, parts);
        });
      } else {
        const photoCount = existingPhotos.length;
        await bot.sendMessage(
          chatId,
          `已收到图片，目前共${photoCount}张，请继续发送文字描述，我们会一起处理。`
        );
      }
      return;
    }

    if (typeof msg.text === "string" && msg.text.trim().length > 0) {
      const storedPhotos = pendingPhotos.get(chatId) ?? [];
      const trimmedText = msg.text.trim();
      const preparedText = QUICK_ACTIONS[trimmedText] ?? trimmedText;

      await runWithTyping(chatId, async () => {
        const parts = await buildContentPartsWithFileIds(
          openai,
          preparedText,
          storedPhotos
        );
        pendingPhotos.delete(chatId);
        await sendWorkflowResult(chatId, parts);
      });
      return;
    }

    await bot.sendMessage(chatId, "目前仅支持接收图片和文本消息。");
  } catch (error) {
    console.error("处理消息时出错:", error);
    await bot.sendMessage(chatId, "处理消息时发生错误，请稍后再试。");
  }
});

bot.on("polling_error", (error: Error) => {
  console.error("Polling error:", error.message);
});

console.log("Telegram echo bot is up and running.");

async function runWithTyping(chatId: number, action: () => Promise<void>) {
  const stopTyping = withTyping(bot, chatId);
  try {
    await action();
  } finally {
    stopTyping();
  }
}

async function sendWorkflowResult(
  chatId: number,
  parts: InputPartWithFileId[]
) {
  const result: WorkflowResult = await runWorkflowFromParts(parts);
  await bot.sendMessage(chatId, result.output_text);

  for (const images of result.images ?? []) {
    try {
      for (const image of images) {
        const payload = await resolveImagePayload(image);
        const contentType =
          image.mimeType ?? payload.contentType ?? "image/png";

        await bot.sendPhoto(
          chatId,
          payload.buffer,
          undefined,
          {
            filename: image.fileName,
            contentType,
          }
        );
      }
      for (const image of images) {
        await bot.sendMessage(chatId, image.caption ?? "");
      }
      
    } catch (error) {
      console.error("发送图表图片失败:", error);
      await bot.sendMessage(chatId, "图表图片发送失败，但报表已生成。");
    }
  }
}

async function resolveImagePayload(image: WorkflowImage): Promise<{
  buffer: Buffer;
  contentType?: string;
}> {
  if (image.base64Data && image.base64Data.trim().length > 0) {
    return {
      buffer: Buffer.from(image.base64Data, "base64"),
      contentType: image.mimeType,
    };
  }

  if (image.imageUrl) {
    return downloadImageFromUrl(image.imageUrl);
  }

  throw new Error("未提供可用的图像数据。");
}

function downloadImageFromUrl(
  imageUrl: string,
  redirectCount = 0
): Promise<{ buffer: Buffer; contentType?: string }> {
  const MAX_REDIRECTS = 3;

  return new Promise((resolve, reject) => {
    let urlToFetch: URL;
    try {
      urlToFetch = new URL(imageUrl);
    } catch (error) {
      reject(error);
      return;
    }

    const httpModule = urlToFetch.protocol === "https:" ? https : http;

    const request = httpModule.get(urlToFetch, (response) => {
      const statusCode = response.statusCode ?? 0;

      if (statusCode >= 300 && statusCode < 400 && response.headers.location) {
        response.resume();
        if (redirectCount >= MAX_REDIRECTS) {
          reject(new Error("重定向次数过多，无法下载图像。"));
          return;
        }
        const nextUrl = new URL(response.headers.location, urlToFetch);
        downloadImageFromUrl(nextUrl.toString(), redirectCount + 1)
          .then(resolve)
          .catch(reject);
        return;
      }

      if (statusCode >= 400) {
        response.resume();
        reject(new Error(`下载图像失败，状态码: ${statusCode}`));
        return;
      }

      const chunks: Buffer[] = [];
      response.on("data", (chunk) => {
        chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
      });
      response.on("end", () => {
        const buffer = Buffer.concat(chunks);
        const headerContentType = response.headers["content-type"];
        const contentType = Array.isArray(headerContentType)
          ? headerContentType[0]
          : headerContentType;
        resolve({ buffer, contentType });
      });
    });

    request.on("error", (error) => {
      reject(error);
    });
  });
}
