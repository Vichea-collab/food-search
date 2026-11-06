/** The light Markdown the answers use: paragraphs, "- " / "* " / "1. " lists, **bold**, [links](https://…) and
 *  "| a | b |" tables (comparisons). Built as React elements (never as HTML), so nothing in an answer can run as
 *  code on the page. */
import { Fragment, type ReactNode } from "react";
import { ExternalLink } from "./ExternalLink";
import "./markdown.css";

const BULLET = /^\s*([-*•]|\d+\.)\s+/;
const TABLE_ROW = /^\s*\|.*\|\s*$/;
const TABLE_RULE = /^:?-{2,}:?$/;
const INLINE = /(\*\*.+?\*\*|\[[^\]]+\]\(https?:\/\/[^)\s]+\))/g;

function inline(text: string): ReactNode[] {
  return text.split(INLINE).map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**") && part.length > 4) {
      return <strong key={i}>{part.slice(2, -2)}</strong>;
    }
    const link = part.match(/^\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)$/);
    if (link) {
      return <ExternalLink key={i} href={link[2]}>{link[1]}</ExternalLink>;
    }
    return <Fragment key={i}>{part.replace(/\*/g, "")}</Fragment>;
  });
}

const cells = (row: string) => row.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim());

function Table({ rows }: { rows: string[] }) {
  const [head, ...body] = rows.map(cells).filter((r) => !r.every((c) => TABLE_RULE.test(c)));
  const numbered = head[0] === "#";          // one row per place; else side by side: one row per detail
  return (
    <div className="md-table" tabIndex={0}>
      <table className={numbered ? "by-place" : "by-detail"}>
        <thead>
          <tr>{head.map((h, i) => <th key={i} scope={h ? "col" : undefined}>{inline(h)}</th>)}</tr>
        </thead>
        <tbody>
          {body.map((r, i) => (
            <tr key={i}>
              {r.map((c, j) =>
                !numbered && j === 0 ? (
                  <th key={j} scope="row">{inline(c)}</th>
                ) : (
                  <td key={j} className={numbered && j === 0 ? "md-num" : c === "—" ? "md-none" : undefined}>
                    {inline(c)}
                  </td>
                ),
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

type Block = { kind: "p" | "ul" | "table"; lines: string[] };

/** Groups the lines: a run of table rows, a run of bullets, or a paragraph (a blank line ends any of them). */
function blocks(text: string): Block[] {
  const out: Block[] = [];
  for (const line of text.trim().split("\n")) {
    if (!line.trim()) {
      out.push({ kind: "p", lines: [] });
      continue;
    }
    const kind = TABLE_ROW.test(line) ? "table" : BULLET.test(line) ? "ul" : "p";
    const last = out[out.length - 1];
    if (last && last.kind === kind && last.lines.length) last.lines.push(line);
    else out.push({ kind, lines: [line] });
  }
  // one line that starts "1. Costa …" is a sentence naming a place by its number, not a list
  return out
    .filter((b) => b.lines.length)
    .map((b) => (b.kind === "ul" && b.lines.length === 1 && /^\s*\d+\./.test(b.lines[0]) ? { ...b, kind: "p" } : b));
}

export function Markdown({ text }: { text: string }) {
  return (
    <>
      {blocks(text).map((b, i) => {
        if (b.kind === "table") return <Table key={i} rows={b.lines} />;
        if (b.kind === "ul") {
          return (
            <ul key={i}>
              {b.lines.map((l, j) => <li key={j}>{inline(l.replace(BULLET, ""))}</li>)}
            </ul>
          );
        }
        const note = b.lines.length === 1 && b.lines[0].startsWith("— = ");      // the table's "— = not in our data"
        return (
          <p key={i} className={note ? "md-note" : undefined}>
            {b.lines.map((l, j) => (
              <Fragment key={j}>
                {j > 0 && <br />}
                {inline(l)}
              </Fragment>
            ))}
          </p>
        );
      })}
    </>
  );
}
