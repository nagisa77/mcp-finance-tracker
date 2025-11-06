import type { PhotoSize } from 'node-telegram-bot-api';

export type StoredPhoto = {
  fileId: string;
  fileName: string;
  mimeType: string;
  base64Data: string;
};

export type InputPartWithFileId =
  | { type: 'input_text'; text: string }
  | { type: 'input_image'; image: { id: string }; detail: 'low' | 'high' | 'auto' };

export type TelegramPhoto = PhotoSize;

export type WorkflowImage = {
  fileName: string;
  mimeType: string;
  caption?: string;
  base64Data?: string;
  imageUrl?: string;
};

export type WorkflowResult = {
  output_text: string;
  images: WorkflowImage[];
};
