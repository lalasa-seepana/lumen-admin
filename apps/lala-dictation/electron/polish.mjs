/**
 * Local "edit model" for dictation cleanup.
 *
 * Pipeline (public product behavior, reconstructed as rules):
 * 1. Protect URLs / emails / filenames
 * 2. Apply spoken punctuation + line/paragraph commands
 * 3. Backtrack ("actually", "scratch that", "never mind", restatements)
 * 4. Remove fillers (Light+)
 * 5. List formatting from "one / two" or "first / second"
 * 6. Capitalization + sentence boundaries
 * 7. Medium: light clarity rewrites (deterministic, no cloud)
 */

const FILLERS = [
  /\b(?:um+|uh+|erm+|hmm+|ah+|eh+)\b/gi,
  /\byou know\b/gi,
  /\bi mean\b/gi,
  /\bkind of\b/gi,
  /\bsort of\b/gi,
  /\blike\b(?=\s+\w)/gi,
  /\bbasically\b/gi,
  /\bliterally\b/gi,
  /\bright\b(?=\s*[,.])/gi,
];

const SPOKEN_PUNCT = [
  [/\bperiod\b/gi, "."],
  [/\bfull stop\b/gi, "."],
  [/\bcomma\b/gi, ","],
  [/\bquestion mark\b/gi, "?"],
  [/\bexclamation (?:point|mark)\b/gi, "!"],
  [/\bcolon\b/gi, ":"],
  [/\bsemicolon\b/gi, ";"],
  [/\bem[\s-]?dash\b/gi, "—"],
  [/\bnew (?:line|paragraph)\b/gi, "\n"],
  [/\bnext line\b/gi, "\n"],
  [/\bline break\b/gi, "\n"],
  [/\bskip a line\b/gi, "\n\n"],
  [/\bstart a new paragraph\b/gi, "\n\n"],
];

const PROTECT_RE =
  /(?:https?:\/\/\S+|www\.\S+|\b[\w.+-]+@[\w.-]+\.\w+\b|\b[\w.-]+\.(?:com|org|net|io|ai|dev|app|co|health)(?:\/\S*)?|\b[\w.-]+\.[a-z0-9]{1,10}\b)/gi;

function protectTokens(text) {
  const tokens = [];
  const out = text.replace(PROTECT_RE, (m) => {
    const id = `__PROT_${tokens.length}__`;
    tokens.push(m.replace(/\s+/g, ""));
    return id;
  });
  return { out, tokens };
}

function restoreTokens(text, tokens) {
  return text.replace(/__PROT_(\d+)__/g, (_, i) => tokens[Number(i)] ?? "");
}

function applySpokenPunctuation(text) {
  let t = text;
  for (const [re, rep] of SPOKEN_PUNCT) t = t.replace(re, rep);
  return t;
}

function applyBacktrack(text) {
  // Drop the abandoned attempt; merge "make that X" into prior clause.
  const re =
    /^(.*?)\b(?:actually|scratch that|never mind|nevermind|wait no|no wait|correction|i meant)\b[,:]?\s*(.*)$/i;
  const m = text.match(re);
  if (!m) return text.trim();

  const before = m[1].trim();
  const after = m[2].trim();
  if (!after) return before;
  if (!before) return after;

  const makeThat = after.match(
    /^(?:make that|make it|change that to|change it to)\s+(.+)$/i
  );
  if (makeThat) {
    const replacement = makeThat[1].trim();
    return before.replace(/\b[\w'-]+\b(?!.*\b[\w'-]+\b)/, replacement);
  }

  if (/^(?:let me start over|start over)\b/i.test(after)) {
    return after.replace(/^(?:let me start over|start over)[,:]?\s*/i, "");
  }

  // Short correction after a longer draft → replace trailing "for/on/at/to X"
  if (after.split(/\s+/).length <= 4 && before.split(/\s+/).length > 2) {
    const trimmed = before.replace(/\b(?:for|on|at|to)\s+[\w'-]+$/i, "").trim();
    if (trimmed && trimmed !== before) return `${trimmed} ${after}`.trim();
  }

  return after;
}

function removeFillers(text) {
  let t = text;
  for (const re of FILLERS) t = t.replace(re, " ");
  return t.replace(/\s{2,}/g, " ").trim();
}

function formatLists(text) {
  const marker =
    /\b(?:first|second|third|fourth|fifth|one|two|three|four|five)\b/gi;
  const hits = text.match(marker);
  if (!hits || hits.length < 2) return text;

  const itemRe =
    /\b(?:first|second|third|fourth|fifth|one|two|three|four|five)\s+(.+?)(?=\s+\b(?:first|second|third|fourth|fifth|one|two|three|four|five)\b|$)/gi;
  const items = [];
  let m;
  while ((m = itemRe.exec(text)) !== null) {
    const item = m[1].replace(/^[,:\s]+|[,.\s]+$/g, "").trim();
    if (item) items.push(item);
  }
  if (items.length < 2) return text;
  return items.map((it, i) => `${i + 1}. ${capitalize(it)}`).join("\n");
}

function capitalize(s) {
  if (!s) return s;
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function smartSentences(text) {
  let t = text
    .replace(/\s+([,.!?;:])/g, "$1")
    .replace(/([.!?])\s*([a-z])/g, (_, p, c) => `${p} ${c.toUpperCase()}`)
    .replace(/\bi\b/g, "I")
    .replace(/\s+\n/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();

  if (t && !/[.!?]$/.test(t) && !t.includes("\n") && t.split(/\s+/).length > 3) {
    t += ".";
  }
  return capitalize(t);
}

function mediumClarity(text) {
  // Deterministic light rewrites for Medium cleanup.
  return text
    .replace(/\b(?:I want to|I'd like to)\b/gi, "I want to")
    .replace(/\b(?:could you please|can you please)\b/gi, "please")
    .replace(/\b(?:in order to)\b/gi, "to")
    .replace(/\b(?:a lot of)\b/gi, "many")
    .replace(/\b(?:due to the fact that)\b/gi, "because")
    .replace(/\s{2,}/g, " ")
    .trim();
}

/**
 * @param {string} raw
 * @param {"none"|"light"|"medium"} level
 */
export function polish(raw, level = "light") {
  if (!raw || !raw.trim()) return { raw: "", polished: "", level };

  const original = raw.trim();
  if (level === "none") {
    return { raw: original, polished: original, level };
  }

  const { out, tokens } = protectTokens(original);
  let t = out;
  t = applySpokenPunctuation(t);
  t = applyBacktrack(t);
  t = removeFillers(t);
  t = formatLists(t);
  t = smartSentences(t);
  if (level === "medium") t = mediumClarity(t);
  t = restoreTokens(t, tokens);
  t = t.replace(/\s{2,}/g, " ").trim();

  return { raw: original, polished: t, level };
}

export const CLEANUP_LEVELS = ["none", "light", "medium"];
