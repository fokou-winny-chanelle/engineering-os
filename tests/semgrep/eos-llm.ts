// Fixtures for core/scaffold/llm/semgrep-llm.yml (JavaScript / TypeScript). Not executed.
import OpenAI from "openai";
import Anthropic from "@anthropic-ai/sdk";
import { generateText, streamText } from "ai";
import { execSync } from "node:child_process";

// ruleid: eos-js-llm-client-default-timeout
const client = new OpenAI();
// ruleid: eos-js-llm-client-default-timeout
const claude = new Anthropic({ maxRetries: 1 });
// ok: eos-js-llm-client-default-timeout
const good = new OpenAI({ timeout: 30_000, maxRetries: 0 });

// ruleid: eos-js-llm-client-default-timeout
const browser = new OpenAI({
  apiKey: "placeholder",
  // ruleid: eos-llm-dangerously-allow-browser
  ...{ dangerouslyAllowBrowser: true },
});

// ruleid: eos-llm-key-in-client-env
const k1 = process.env.NEXT_PUBLIC_OPENAI_API_KEY;
// ruleid: eos-llm-key-in-client-env
const k2 = process.env.EXPO_PUBLIC_ANTHROPIC_KEY;
// ruleid: eos-llm-key-in-client-env
const k3 = import.meta.env.VITE_GEMINI_API_KEY;
// ok: eos-llm-key-in-client-env
const k4 = process.env.OPENAI_API_KEY;
// ok: eos-llm-key-in-client-env
const k5 = process.env.NEXT_PUBLIC_API_URL;

export async function handler(question: string, db: any, el: HTMLElement) {
  const r = await good.responses.create({ model: "gpt-6-luna", input: question, max_output_tokens: 300 });
  const out = r.output_text;
  // ruleid: eos-js-llm-output-to-exec
  eval(out);
  // ruleid: eos-js-llm-output-to-exec
  execSync(`git log ${out}`);
  // ruleid: eos-js-llm-output-to-exec
  await db.query(`SELECT * FROM t WHERE ${out}`);
  // ok: eos-js-llm-output-to-exec
  await db.query("SELECT * FROM t WHERE ref = $1", [out]);
  // ruleid: eos-js-llm-output-to-exec
  el.innerHTML = out;
  // ok: eos-js-llm-output-to-exec
  el.textContent = out;
  const { text } = await generateText({ model: "openai/gpt-6-luna", prompt: question, maxOutputTokens: 200 });
  // ruleid: eos-js-llm-output-to-exec
  new Function(text)();
}

export async function limits(question: string) {
  // ruleid: eos-js-llm-missing-max-tokens
  await good.responses.create({ model: "gpt-6-luna", input: question });
  // ok: eos-js-llm-missing-max-tokens
  await good.responses.create({ model: "gpt-6-luna", input: question, max_output_tokens: 500 });
  // ruleid: eos-js-llm-missing-max-tokens
  await good.chat.completions.create({ model: "gpt-6-luna", messages: [] });
  // ruleid: eos-js-llm-missing-max-tokens
  streamText({ model: "openai/gpt-6-luna", prompt: question });
  // ok: eos-js-llm-missing-max-tokens
  await generateText({ model: "openai/gpt-6-luna", prompt: question, maxOutputTokens: 100 });
}
