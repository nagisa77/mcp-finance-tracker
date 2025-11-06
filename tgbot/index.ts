import TelegramBot, { type Message, type PhotoSize } from 'node-telegram-bot-api';
import { Agent, Runner, hostedMcpTool, withTrace } from "@openai/agents";
import https from 'https';
import OpenAI from "openai";
import { toFile } from "openai/uploads";

async function uploadPhotosAndGetFileIds(photos: StoredPhoto[]) {
  const ids: string[] = [];
  for (const p of photos) {
    const file = await openai.files.create({
      file: await toFile(Buffer.from(p.base64Data, "base64"), p.fileName, { type: p.mimeType }),
      purpose: "assistants",
    });
    ids.push(file.id);
  }
  return ids;
}

type InputPartWithFileId =
  | { type: "input_text"; text: string }
  | { type: "input_image"; image: { id: string }; detail: "low" | "high" | "auto" };

async function buildContentPartsWithFileIds(text: string, photos: StoredPhoto[]): Promise<InputPartWithFileId[]> {
  const fileIds = await uploadPhotosAndGetFileIds(photos);
  const parts: InputPartWithFileId[] = [];

  for (const id of fileIds) {
    parts.push({ type: "input_image", image: { id: id }, detail: "high" });
  }

  parts.push({ type: "input_text", text });

  return parts;
}

const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
});

const token = process.env.TELEGRAM_TOKEN;

type StoredPhoto = {
  fileId: string;
  fileName: string;
  mimeType: string;
  base64Data: string;
};

const pendingPhotos = new Map<number, StoredPhoto[]>();

function withTyping(
  bot: TelegramBot,
  chatId: number,
  action: TelegramBot.ChatAction = "typing"
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

const QUICK_ACTIONS: Record<string, string> = {
  生成最近开销报表: "请生成最近开销报表。",
  对比本周和上周支出: "请对比本周和上周的支出情况，并给出主要差异和建议。",
  查看分类支出详情: "请提供最近一段时间各分类的支出详情。",
};

const mcp = hostedMcpTool({
  serverLabel: "finance_mcp",
  serverUrl: "https://www.open-isle.com/mcp-wallet",
  allowedTools: [
    "get_categories",
    "record_bill",
    "record_multiple_bills",
    "get_expense_summary",
    "get_category_expense_detail",
  ],
  requireApproval: "never",
});

const agent = new Agent({
  name: "finance_agent",
  instructions: `
首先，务必调用 get_categories 工具，以获取当前可用的账单分类与类型信息。
仔细分析用户输入内容——如包含账单相关信息（无论是图片或文字），需将图片中的文字内容解析出来并用作账单明细。
若用户输入的是单次消费，只需调用 record_bill 工具进行记录；
如为多笔消费，请一次性批量调用 record_multiple_bills 工具。
整个过程中，无需向用户进行中间询问，直接解析并记录。

调用记账类工具（无论单条还是多条）时，所有金额必须为正数，并且类型字段 type（income 或 expense）都需显式传递。
请将每笔账单的详细内容及其对应类型在输出中完整展示。

你是聊天机器人，最终的回复务必使用自然、清晰的文本（不要使用 markdown 格式和符号）。
`,
  tools: [mcp],
  model: "gpt-4o",
  modelSettings: {
    temperature: 0.7,
    topP: 1,
    maxTokens: 2048,
    toolChoice: "auto",
    store: true,
  },
});

function createRunner(): Runner {
  return new Runner({
    workflowName: "finance_agent",
    traceMetadata: {
      __trace_source__: "agent-builder",
      workflow_id: "wf_69003cbd47e08190928745d3c806c0b50d1a01cfae052be8",
    },
  });
}

async function runWorkflowFromParts(contentParts: InputPartWithFileId[]) {
  if (!process.env.OPENAI_API_KEY) {
    throw new Error("Missing OPENAI_API_KEY");
  }

  // 可选：做一点点防御
  if (!Array.isArray(contentParts) || contentParts.length === 0) {
    throw new Error("contentParts is empty.");
  }

  const runner = createRunner();

  return await withTrace(`finance_agent run`, async () => {
    // 打点预览（避免把完整 file_id 打爆日志）
    // 改成保护嵌套的 file_id
    const preview = JSON.stringify(
      contentParts.map(p =>
        p.type === "input_text" ? p : { ...p, image: p.image }
      )
    );
    console.log("🖼️ content parts (preview):", preview.slice(0, 500));

    // 关键：把输入封装成“消息数组”，而不是纯字符串
    const messages = [
      {
        type: "message",
        role: "user" as const,
        content: contentParts, 
      },
    ];

    // 有些类型定义较严格，必要时可加 `as any`
    const result = await runner.run(agent as any, messages as any, {
      maxTurns: 16,
    });

    console.log("📬 Agent run completed. Result keys:", Object.keys(result ?? {}));

    if (!result || !result.finalOutput) {
      throw new Error("Agent result is undefined (no final output).");
    }

    const financeAgentResult = { output_text: String(result.finalOutput) };
    console.log(
      "🤖 Agent result (length=%d):\n%s",
      financeAgentResult.output_text.length,
      financeAgentResult.output_text
    );

    return financeAgentResult;
  });
}

if (!token) {
  throw new Error('TELEGRAM_TOKEN environment variable is not set.');
}

const bot = new TelegramBot(token, { polling: true });

bot.setMyCommands([
  { command: "start", description: "开始使用记账机器人" },
  { command: "report", description: "生成最近开销报表" },
  { command: "compare", description: "对比本周和上周支出" },
  { command: "detail", description: "查看分类支出详情" },
]);

bot.onText(/\/report/, async (msg) => {
  const chatId = msg.chat.id;
  const stopTyping = withTyping(bot, chatId);
  try {
    const result = await runWorkflowFromParts([
      { type: "input_text", text: QUICK_ACTIONS["生成最近开销报表"] },
    ]);
    bot.sendMessage(chatId, result.output_text);
  } finally {
    stopTyping();
  }
});

bot.onText(/\/compare/, async (msg) => {
  const chatId = msg.chat.id;
  const stopTyping = withTyping(bot, chatId);
  try {
    const result = await runWorkflowFromParts([
      { type: "input_text", text: QUICK_ACTIONS["对比本周和上周支出"] },
    ]);
    await bot.sendMessage(chatId, result.output_text);
  } finally {
    stopTyping();
  }
}); 

bot.on('message', async (msg: Message) => {
  const chatId = msg.chat.id;

  try {
    if (msg.text === '/start') {
      await bot.sendMessage(chatId, '请选择需要的功能或直接发送账单信息。', {
        reply_markup: {
          keyboard: Object.keys(QUICK_ACTIONS).map((text) => [{ text }]),
          resize_keyboard: true,
        },
      });
      return;
    }

    if (Array.isArray(msg.photo) && msg.photo.length > 0) {
      const largestPhoto = selectLargestPhoto(msg.photo);
      if (!largestPhoto) {
        await bot.sendMessage(chatId, '未能识别图片，请重试。');
        return;
      }

      const storedPhoto = await downloadPhotoAsBase64(largestPhoto.file_id);

      const existingPhotos = pendingPhotos.get(chatId) ?? [];
      existingPhotos.push(storedPhoto);
      pendingPhotos.set(chatId, existingPhotos);

      const captionText = typeof msg.caption === 'string' ? msg.caption.trim() : '';
      if (captionText.length > 0) {
        const stopTyping = withTyping(bot, chatId);
        try {
          const parts = await buildContentPartsWithFileIds(captionText, existingPhotos);
          pendingPhotos.delete(chatId);
          const result = await runWorkflowFromParts(parts as any);
          await bot.sendMessage(chatId, result.output_text);
        } finally {
          stopTyping();
        }
      } else {
        const photoCount = existingPhotos.length;
        await bot.sendMessage(
          chatId,
          `已收到图片，目前共${photoCount}张，请继续发送文字描述，我们会一起处理。`
        );
      }
      return;
    }

    if (typeof msg.text === 'string' && msg.text.trim().length > 0) {
      const storedPhotos = pendingPhotos.get(chatId) ?? [];
      const trimmedText = msg.text.trim();
      const preparedText = QUICK_ACTIONS[trimmedText] ?? trimmedText;
      const stopTyping = withTyping(bot, chatId);
      try {
        const parts = await buildContentPartsWithFileIds(preparedText, storedPhotos);
        pendingPhotos.delete(chatId);

        const result = await runWorkflowFromParts(parts as any);
        await bot.sendMessage(chatId, result.output_text);
      } finally {
        stopTyping();
      }
      return;
    }


    await bot.sendMessage(chatId, '目前仅支持接收图片和文本消息。');
  } catch (error) {
    console.error('处理消息时出错:', error);
    await bot.sendMessage(chatId, '处理消息时发生错误，请稍后再试。');
  }
});

bot.on('polling_error', (error: Error) => {
  console.error('Polling error:', error.message);
});

console.log('Telegram echo bot is up and running.');

function selectLargestPhoto(photos: PhotoSize[]): PhotoSize | undefined {
  return photos.reduce<PhotoSize | undefined>((selected, current) => {
    if (!selected) {
      return current;
    }
    const selectedPixels = (selected.width ?? 0) * (selected.height ?? 0);
    const currentPixels = (current.width ?? 0) * (current.height ?? 0);
    return currentPixels > selectedPixels ? current : selected;
  }, undefined);
}

async function downloadPhotoAsBase64(fileId: string): Promise<StoredPhoto> {
  const file = await bot.getFile(fileId);
  if (!file.file_path) {
    throw new Error('无法获取图片路径');
  }

  const fileUrl = `https://api.telegram.org/file/bot${token}/${file.file_path}`;
  const fileBuffer = await fetchFileBuffer(fileUrl);
  const fileName = file.file_path.split('/').pop() ?? `${fileId}.jpg`;
  const mimeType = guessMimeType(file.file_path);

  return {
    fileId,
    fileName,
    mimeType,
    base64Data: fileBuffer.toString('base64'),
  };
}

function fetchFileBuffer(url: string): Promise<Buffer> {
  return new Promise((resolve, reject) => {
    https
      .get(url, (res) => {
        if (res.statusCode && res.statusCode >= 400) {
          reject(new Error(`下载失败，状态码: ${res.statusCode}`));
          res.resume();
          return;
        }

        const data: Buffer[] = [];
        res.on('data', (chunk) => data.push(chunk as Buffer));
        res.on('end', () => resolve(Buffer.concat(data)));
      })
      .on('error', reject);
  });
}

function guessMimeType(filePath: string): string {
  const extension = filePath.split('.').pop()?.toLowerCase();
  switch (extension) {
    case 'jpg':
    case 'jpeg':
      return 'image/jpeg';
    case 'png':
      return 'image/png';
    case 'webp':
      return 'image/webp';
    case 'gif':
      return 'image/gif';
    default:
      return 'application/octet-stream';
  }
}
