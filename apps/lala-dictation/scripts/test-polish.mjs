import { polish } from "../electron/polish.mjs";

const samples = [
  {
    name: "fillers + grammar",
    raw: "um so I think we should like basically ship the demo tomorrow uh you know",
  },
  {
    name: "backtrack",
    raw: "book the room for Tuesday actually make that Wednesday",
  },
  {
    name: "spoken punctuation",
    raw: "hello comma how are you question mark",
  },
  {
    name: "url preserved",
    raw: "check example.com/docs for the docs um please",
  },
  {
    name: "list",
    raw: "first buy milk second call the clinic third send the report",
  },
];

for (const sample of samples) {
  console.log(`\n=== ${sample.name} ===`);
  console.log("raw:   ", sample.raw);
  for (const level of ["none", "light", "medium"]) {
    const { polished } = polish(sample.raw, level);
    console.log(`${level.padEnd(7)}`, polished);
  }
}
