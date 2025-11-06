import { Agent, Runner, hostedMcpTool, withTrace } from '@openai/agents';

import type { InputPartWithFileId } from '../types';

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

    const financeAgentResult = { output_text: String(result.finalOutput) };
    console.log(
      '🤖 Agent result (length=%d):\n%s',
      financeAgentResult.output_text.length,
      financeAgentResult.output_text,
    );

    return financeAgentResult;
  });
}
