import https from 'https';
import type TelegramBot from 'node-telegram-bot-api';
import OpenAI from 'openai';
import { toFile } from 'openai/uploads';

import type { InputPartWithFileId, StoredPhoto, TelegramPhoto } from '../types';

async function uploadPhotosAndGetFileIds(openai: OpenAI, photos: StoredPhoto[]) {
  const ids: string[] = [];
  for (const photo of photos) {
    const file = await openai.files.create({
      file: await toFile(Buffer.from(photo.base64Data, 'base64'), photo.fileName, {
        type: photo.mimeType,
      }),
      purpose: 'assistants',
    });
    ids.push(file.id);
  }
  return ids;
}

export async function buildContentPartsWithFileIds(
  openai: OpenAI,
  text: string,
  photos: StoredPhoto[],
): Promise<InputPartWithFileId[]> {
  const fileIds = await uploadPhotosAndGetFileIds(openai, photos);
  const parts: InputPartWithFileId[] = [];

  for (const id of fileIds) {
    parts.push({ type: 'input_image', image: { id }, detail: 'high' });
  }

  parts.push({ type: 'input_text', text });

  return parts;
}

export function selectLargestPhoto(photos: TelegramPhoto[]): TelegramPhoto | undefined {
  return photos.reduce<TelegramPhoto | undefined>((selected, current) => {
    if (!selected) {
      return current;
    }
    const selectedPixels = (selected.width ?? 0) * (selected.height ?? 0);
    const currentPixels = (current.width ?? 0) * (current.height ?? 0);
    return currentPixels > selectedPixels ? current : selected;
  }, undefined);
}

export async function downloadPhotoAsBase64(
  bot: TelegramBot,
  token: string,
  fileId: string,
): Promise<StoredPhoto> {
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
