import OpenAI from 'openai';
import { requireEnvVar } from './config/env';

export const openai = new OpenAI({
  apiKey: requireEnvVar('OPENAI_API_KEY'),
});
