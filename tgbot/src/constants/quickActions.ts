export interface QuickAction {
  /** 命令描述，将展示在 Telegram 命令列表中 */
  title: string;
  /** 交给代理执行的提示词 */
  prompt: string;
  /** 允许用户直接输入的同义词或快捷短语 */
  aliases?: string[];
}

export const QUICK_ACTIONS = {
  report_recent: {
    title: "生成最近开销报表",
    prompt: "请生成最近开销报表。",
    aliases: ["生成最近开销报表", "/report", "report"],
  },
  compare_weekly: {
    title: "对比本周和上周支出",
    prompt: "请对比本周和上周的支出情况，并给出主要差异和建议。",
    aliases: ["对比本周和上周支出", "/compare", "compare"],
  },
  compare_monthly: {
    title: "对比本月和上月支出",
    prompt:
      "请对比本月与上月的支出结构，指出显著变化并提供优化建议。",
    aliases: ["对比本月和上月支出", "/compare_monthly"],
  },
  detail: {
    title: "查看分类支出详情",
    prompt: "请提供最近一段时间各分类的支出详情。",
    aliases: ["查看分类支出详情", "/detail"],
  },
  budget_health_check: {
    title: "预算执行健康检查",
    prompt:
      "请评估当前预算执行情况，指出超支或结余的类别，并给出调优建议。",
    aliases: ["预算执行健康检查", "预算健康检查"],
  },
  savings_insights: {
    title: "储蓄与现金流洞察",
    prompt:
      "请分析近期储蓄及现金流趋势，指出潜在风险并提供改善建议。",
    aliases: ["储蓄洞察", "现金流洞察"],
  },
} as const satisfies Record<string, QuickAction>;

export type QuickActionKey = keyof typeof QUICK_ACTIONS;

export function resolveQuickAction(
  text: string
): { key: QuickActionKey; action: QuickAction } | undefined {
  const normalized = text.trim();
  if (!normalized) {
    return undefined;
  }

  const withoutSlash = normalized.startsWith("/")
    ? (normalized.slice(1) as QuickActionKey)
    : (normalized as QuickActionKey);

  if (withoutSlash in QUICK_ACTIONS) {
    const action = QUICK_ACTIONS[withoutSlash];
    return { key: withoutSlash, action };
  }

  for (const [key, action] of Object.entries(QUICK_ACTIONS) as Array<[
    QuickActionKey,
    QuickAction
  ]>) {
    if (
      action.aliases?.includes(normalized) === true ||
      action.title === normalized
    ) {
      return { key, action };
    }
  }

  return undefined;
}
