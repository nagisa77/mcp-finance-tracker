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
  instructions: "首先务必调用get_categories获取目前记账基本类型信息。分析用户输入，如果是账单（图片/文字），图片需要解析其中的文字作为账单输入。如果用户输入的是单次消费，调用record_bill记录账单；如果是多次消费，调用record_multiple_bills。不需要中间询问用户。调用记账类工具时，所有金额都必须为正数，并且无论是单条还是多条记录都要显式提供type字段（income 或 expense）。另外最后输出的时候，需要包含记账每笔账单+类型信息",
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

bot.on('message', async (msg: Message) => {
  const chatId = msg.chat.id;

  try {
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

      await bot.sendMessage(chatId, '已收到图片，请继续发送文字描述，我们会一起处理。');
      return;
    }

    if (typeof msg.text === 'string' && msg.text.trim().length > 0) {
      const storedPhotos = pendingPhotos.get(chatId) ?? [];
      await bot.sendMessage(chatId, "正在处理...");
      const parts = await buildContentPartsWithFileIds(msg.text.trim(), storedPhotos);
      pendingPhotos.delete(chatId);
    
      const result = await runWorkflowFromParts(parts as any);
      await bot.sendMessage(chatId, result.output_text);
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
