import TelegramBot, { type Message } from 'node-telegram-bot-api';
import { Agent, Runner, hostedMcpTool, withTrace } from "@openai/agents";

const token = process.env.TELEGRAM_TOKEN;
export type WorkflowInput = { input_as_text: string };

const mcp = hostedMcpTool({
  serverLabel: "finance_mcp",
  serverUrl: "http://finance_mcp_server:8888",
  allowedTools: [
    "get_categories",
    "record_bill",
  ],
  requireApproval: "never",
});

const agent = new Agent({
  name: "finance_agent",
  instructions: "调用get_categories获取目前账单有什么类型。分析用户输入，如果是账单（图片/文字）,图片需要解析其中的文字作为账单输入，然后调用record_bill记录账单。中间不用询问用户",
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

async function runWorkflow(workflow: WorkflowInput) {
  if (!process.env.OPENAI_API_KEY) {
    throw new Error("Missing OPENAI_API_KEY");
  }
  const runner = createRunner();
  return await withTrace(`finance_agent run`, async () => {
    const preview = workflow.input_as_text.trim();
    console.log(
      "📝 Received workflow input (preview):",
      preview.length > 200 ? `${preview.slice(0, 200)}…` : preview
    );

    console.log("🚦 Starting agent run with maxTurns=16...");
    const result = await runner.run(agent, workflow.input_as_text, {
      maxTurns: 16,
    });

    console.log("📬 Agent run completed. Result keys:", Object.keys(result));

    if (!result.finalOutput) {
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

  if (typeof msg.text === 'string') {
    console.log("🔍 Running workflow...");
    bot.sendMessage(chatId, "正在处理...");
    const result = await runWorkflow({ input_as_text: msg.text });
    bot.sendMessage(chatId, result.output_text as string);
  } else {
    bot.sendMessage(chatId, 'I can only echo text messages right now.');
  }
});

bot.on('polling_error', (error: Error) => {
  console.error('Polling error:', error.message);
});

console.log('Telegram echo bot is up and running.');
