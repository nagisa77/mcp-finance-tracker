import { Agent, Runner, hostedMcpTool, withTrace } from '@openai/agents';

import type { InputPartWithFileId, WorkflowImage, WorkflowResult } from '../types';

const mcp = hostedMcpTool({
  serverLabel: 'finance_mcp',
  serverUrl: 'https://www.open-isle.com/mcp-wallet',
  allowedTools: [
    'get_categories',
    'record_bill',
    'record_multiple_bills',
    'get_expense_summary',
    'get_category_expense_detail',
  ],
  requireApproval: 'never',
});

const agent = new Agent({
  name: 'finance_agent',
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
  model: 'gpt-4o',
  modelSettings: {
    temperature: 0.7,
    topP: 1,
    maxTokens: 2048,
    toolChoice: 'auto',
    store: true,
  },
});

function createRunner(): Runner {
  return new Runner({
    workflowName: 'finance_agent',
    traceMetadata: {
      __trace_source__: 'agent-builder',
      workflow_id: 'wf_69003cbd47e08190928745d3c806c0b50d1a01cfae052be8',
    },
  });
}

export async function runWorkflowFromParts(contentParts: InputPartWithFileId[]) {
  if (!process.env.OPENAI_API_KEY) {
    throw new Error('Missing OPENAI_API_KEY');
  }

  if (!Array.isArray(contentParts) || contentParts.length === 0) {
    throw new Error('contentParts is empty.');
  }

  const runner = createRunner();

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

function extractExpenseSummaryCharts(newItems: any[]): WorkflowImage[] {
  if (!Array.isArray(newItems) || newItems.length === 0) {
    return [];
  }

  const collected: WorkflowImage[] = [];

  for (const item of newItems) {
    if (!item || item.type !== 'tool_call_output_item') {
      continue;
    }

    const rawItem = item.rawItem ?? {};
    const toolName = rawItem.name ?? rawItem.tool_name ?? rawItem.toolName;
    if (toolName !== 'get_expense_summary') {
      continue;
    }

    const structured = extractStructuredData(item.output);
    if (!structured || typeof structured !== 'object') {
      continue;
    }

    const charts = structured.charts;
    if (!charts || typeof charts !== 'object') {
      continue;
    }

    const chartEntries: Array<[string, any, string]> = [
      ['bar_chart', charts.bar_chart ?? charts.barChart, 'bar'],
      ['pie_chart', charts.pie_chart ?? charts.pieChart, 'pie'],
    ];

    for (const [_key, chart, suffix] of chartEntries) {
      if (!chart || typeof chart !== 'object') {
        continue;
      }

      const base64Value =
        chart.base64_data ?? chart.base64Data ?? chart.image_base64 ?? chart.imageBase64;
      if (typeof base64Value !== 'string' || base64Value.trim().length === 0) {
        continue;
      }

      const mimeType: string = chart.mime_type ?? chart.mimeType ?? 'image/png';
      const caption =
        typeof chart.title === 'string' && chart.title.trim().length > 0 ? chart.title : undefined;

      collected.push({
        fileName: `expense-summary-${suffix}.png`,
        mimeType,
        base64Data: normalizeBase64(base64Value),
        caption,
      });
    }
  }

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
  if (!output) {
    return null;
  }

  if (Array.isArray(output)) {
    for (const item of output) {
      const structured = extractStructuredData(item);
      if (structured) {
        return structured;
      }
    }
    return null;
  }

  if (typeof output === 'string') {
    try {
      return JSON.parse(output);
    } catch (error) {
      return null;
    }
  }

  if (typeof output !== 'object') {
    return null;
  }

  if (output.json && typeof output.json === 'object') {
    return output.json;
  }

  if (output.structuredContent && typeof output.structuredContent === 'object') {
    return output.structuredContent;
  }

  if (typeof output.data === 'string') {
    try {
      return JSON.parse(output.data);
    } catch (error) {
      // ignore parse error
    }
  }

  if (typeof output.text === 'string') {
    try {
      return JSON.parse(output.text);
    } catch (error) {
      // ignore parse error
    }
  }

  if (output.charts && typeof output.charts === 'object') {
    return output;
  }

  return null;
}
