import { Agent, Runner, hostedMcpTool, withTrace } from '@openai/agents';

import type { InputPartWithFileId, WorkflowImage, WorkflowResult } from '../types';

const TELEGRAM_USER_ID_HEADER = 'x-telegram-user-id';

const MCP_BASE_CONFIG = {
  serverLabel: 'finance_mcp',
  serverUrl: 'https://www.open-isle.com/mcp-wallet',
  allowedTools: [
    'get_categories',
    'record_bill',
    'record_multiple_bills',
    'get_expense_summary',
    'get_category_expense_detail',
  ],
  requireApproval: 'never' as const,
};

const AGENT_INSTRUCTIONS = `
注意: 严禁使用任何markdown格式和符号

首先，务必调用 get_categories 工具，以获取当前可用的账单分类与类型信息。
仔细分析用户输入内容——如包含账单相关信息（无论是图片或文字），需将图片中的文字内容解析出来并用作账单明细。
若用户输入的是单次消费，只需调用 record_bill 工具进行记录；
如为多笔消费，请一次性批量调用 record_multiple_bills 工具。
整个过程中，无需向用户进行中间询问，直接解析并记录。

调用记账类工具（无论单条还是多条）时，所有金额必须为正数，并且类型字段 type（income 或 expense）都需显式传递。
请将每笔账单的详细内容及其对应类型在输出中完整展示。

如果输出包含url，不用贴出具体url，提醒用户上文已包含图片
你是聊天机器人，最终的回复务必使用自然、清晰的文本. 采用自然语言，严禁使用任何markdown格式和符号。
`;

function createAgent(userId: string): Agent {
  const mcpTool = hostedMcpTool({
    ...MCP_BASE_CONFIG,
    headers: {
      [TELEGRAM_USER_ID_HEADER]: userId,
    },
  });

  return new Agent({
    name: 'finance_agent',
    instructions: AGENT_INSTRUCTIONS,
    tools: [mcpTool],
    model: 'gpt-4o',
    modelSettings: {
      temperature: 0.3,
      topP: 1,
      maxTokens: 2048,
      toolChoice: 'auto',
      store: true,
    },
  });
}

function createRunner(): Runner {
  return new Runner({
    workflowName: 'finance_agent',
    traceMetadata: {
      __trace_source__: 'agent-builder',
      workflow_id: 'wf_69003cbd47e08190928745d3c806c0b50d1a01cfae052be8',
    },
  });
}

export async function runWorkflowFromParts(
  contentParts: InputPartWithFileId[],
  telegramUserId: number | string
) {
  if (!process.env.OPENAI_API_KEY) {
    throw new Error('Missing OPENAI_API_KEY');
  }

  if (!Array.isArray(contentParts) || contentParts.length === 0) {
    throw new Error('contentParts is empty.');
  }

  const runner = createRunner();
  const agent = createAgent(String(telegramUserId));

  return await withTrace('finance_agent run', async () => {
    const preview = JSON.stringify(
      contentParts.map((part) =>
        part.type === 'input_text' ? part : { ...part, image: part.image }
      )
    );
    console.log('🖼️ content parts (preview):', preview.slice(0, 500));

    const messages = [
      {
        type: 'message' as const,
        role: 'user' as const,
        content: contentParts,
      },
    ];

    const result = await runner.run(agent as any, messages as any, {
      maxTurns: 16,
    });

    console.log('📬 Agent run completed. Result keys:', Object.keys(result ?? {}));

    if (!result || !result.finalOutput) {
      throw new Error('Agent result is undefined (no final output).');
    }

    const images = extractExpenseSummaryCharts((result as any)?.newItems ?? []);

    const financeAgentResult: WorkflowResult = {
      output_text: String(result.finalOutput),
      images,
    };
    console.log(
      '🤖 Agent result (length=%d):\n%s',
      financeAgentResult.output_text.length,
      financeAgentResult.output_text,
    );

    if (financeAgentResult.images.length > 0) {
      console.log(
        '🖼️ Extracted %d chart image(s) from get_expense_summary.',
        financeAgentResult.images.length,
      );
    }

    return financeAgentResult;
  });
}

function extractExpenseSummaryCharts(newItems: any[]): WorkflowImage[][] {
  if (!Array.isArray(newItems) || newItems.length === 0) {
    console.log('[extractExpenseSummaryCharts] No newItems or not an array:', newItems);
    return [];
  }

  const collected: WorkflowImage[][] = [];

  for (const [itemIdx, item] of newItems.entries()) {
    const itemCharts: WorkflowImage[] = [];
    if (!item || item.type !== 'tool_call_item') {
      console.log(`[extractExpenseSummaryCharts][${itemIdx}] Skipping item: not a tool_call_item, got:`, item?.type);
      continue;
    }

    const rawItem = item.rawItem ?? {};

    const structured = extractStructuredData(rawItem.output);
    if (!structured || typeof structured !== 'object') {
      console.log(`[extractExpenseSummaryCharts][${itemIdx}] No structured data found.`);
      continue;
    }

    const charts = structured.charts;
    if (!Array.isArray(charts) || charts.length === 0) {
      console.log(
        `[extractExpenseSummaryCharts][${itemIdx}] Charts field missing or not an array. structured:`,
        structured
      );
      continue;
    }

    charts.forEach((chart: any, chartIdx: number) => {
      if (!chart || typeof chart !== 'object') {
        console.log(
          `[extractExpenseSummaryCharts][${itemIdx}] Chart index ${chartIdx} missing or not an object:`,
          chart
        );
        return;
      }

      console.log(`[extractExpenseSummaryCharts][${itemIdx}] Chart[${chartIdx}]:`, chart);

      const base64Value =
        chart.base64_data ?? chart.base64Data ?? chart.image_base64 ?? chart.imageBase64;
      const imageUrlValue = chart.image_url ?? chart.imageUrl ?? chart.url ?? chart.href;

      const mimeType: string = chart.mime_type ?? chart.mimeType ?? 'image/png';
      const caption =
        typeof chart.title === 'string' && chart.title.trim().length > 0 ? chart.title : undefined;

      const normalizedBase64 =
        typeof base64Value === 'string' && base64Value.trim().length > 0
          ? normalizeBase64(base64Value)
          : undefined;

      const normalizedUrl =
        typeof imageUrlValue === 'string' && imageUrlValue.trim().length > 0
          ? imageUrlValue.trim()
          : undefined;

      if (!normalizedBase64 && !normalizedUrl) {
        console.log(
          `[extractExpenseSummaryCharts][${itemIdx}] Skipping chart index ${chartIdx}: no base64 or url.`
        );
        return;
      }

      const imageObj = {
        fileName: chart.file_name ?? chart.fileName ?? `expense-summary-${chartIdx + 1}.png`,
        mimeType,
        base64Data: normalizedBase64,
        imageUrl: normalizedUrl,
        caption,
      };

      console.log(
        `[extractExpenseSummaryCharts][${itemIdx}] Extracted chart:`,
        JSON.stringify({
          index: chartIdx,
          fileName: imageObj.fileName,
          base64Len: normalizedBase64?.length,
          imageUrl: normalizedUrl,
          mimeType,
          caption,
        })
      );

      itemCharts.push(imageObj);
    });
    collected.push(itemCharts);
  }

  console.log(`[extractExpenseSummaryCharts] Collected total: ${collected.length}`);
  return collected;
}

function normalizeBase64(value: string): string {
  const trimmed = value.trim();
  if (!trimmed.startsWith('data:')) {
    return trimmed;
  }

  const commaIndex = trimmed.indexOf(',');
  return commaIndex === -1 ? trimmed : trimmed.slice(commaIndex + 1);
}

function extractStructuredData(output: any): any | null {
  console.log('[extractStructuredData] Input:', JSON.stringify(output));

  if (!output) {
    console.log('[extractStructuredData] Output is null/undefined.');
    return null;
  }

  if (Array.isArray(output)) {
    console.log('[extractStructuredData] Output is array, recursively checking items...');
    for (const item of output) {
      const structured = extractStructuredData(item);
      if (structured) {
        console.log('[extractStructuredData] Found structured data in array item:', JSON.stringify(structured));
        return structured;
      }
    }
    console.log('[extractStructuredData] No structured data found in array.');
    return null;
  }

  if (typeof output === 'string') {
    console.log('[extractStructuredData] Output is string, attempting to parse as JSON...');
    try {
      const parsed = JSON.parse(output);
      console.log('[extractStructuredData] Successfully parsed string to object:', JSON.stringify(parsed));
      return parsed;
    } catch (error) {
      console.log('[extractStructuredData] Failed to parse string as JSON:', error);
      return null;
    }
  }

  if (typeof output !== 'object') {
    console.log('[extractStructuredData] Output is not object, returning null.');
    return null;
  }

  if (output.json && typeof output.json === 'object') {
    console.log('[extractStructuredData] Found "json" property:', JSON.stringify(output.json));
    return output.json;
  }

  if (output.structuredContent && typeof output.structuredContent === 'object') {
    console.log('[extractStructuredData] Found "structuredContent" property:', JSON.stringify(output.structuredContent));
    return output.structuredContent;
  }

  if (typeof output.data === 'string') {
    console.log('[extractStructuredData] Found string "data" property, attempting to parse as JSON...');
    try {
      const parsed = JSON.parse(output.data);
      console.log('[extractStructuredData] Successfully parsed "data" property:', JSON.stringify(parsed));
      return parsed;
    } catch (error) {
      console.log('[extractStructuredData] Failed to parse "data" property:', error);
      // ignore parse error
    }
  }

  if (typeof output.text === 'string') {
    console.log('[extractStructuredData] Found string "text" property, attempting to parse as JSON...');
    try {
      const parsed = JSON.parse(output.text);
      console.log('[extractStructuredData] Successfully parsed "text" property:', JSON.stringify(parsed));
      return parsed;
    } catch (error) {
      console.log('[extractStructuredData] Failed to parse "text" property:', error);
      // ignore parse error
    }
  }

  if (output.charts && typeof output.charts === 'object') {
    console.log('[extractStructuredData] Found "charts" property with object value, returning output as structured data.');
    return output;
  }

  console.log('[extractStructuredData] No structured data found, returning null.');
  return null;
}
