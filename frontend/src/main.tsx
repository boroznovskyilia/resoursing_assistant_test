import { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import type { Answer, Block, History, Thread } from "./types";
import "./style.css";

async function api<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(
    path,
    body === undefined
      ? undefined
      : {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
  );
  const data = await response.json();
  if (!response.ok)
    throw new Error(
      data.error?.message || `Request failed (${response.status})`,
    );
  return data as T;
}
type Decision = (id: string, decision: "confirm" | "reject") => void;
function Blocks({
  answer,
  disabled,
  onDecision,
}: {
  answer: Answer;
  disabled: boolean;
  onDecision: Decision;
}) {
  return (
    <>
      {answer.blocks.map((block, index) => (
        <BlockView
          key={index}
          block={block}
          disabled={disabled}
          onDecision={onDecision}
        />
      ))}
      {answer.assumptions?.length > 0 && (
        <p className="note">Assumptions: {answer.assumptions.join(" · ")}</p>
      )}
      {answer.issues?.map((issue, index) => (
        <p role="status" className="warning" key={index}>
          {issue.message}
        </p>
      ))}
    </>
  );
}
function BlockView({
  block,
  disabled,
  onDecision,
}: {
  block: Block;
  disabled: boolean;
  onDecision: Decision;
}) {
  if (block.type === "text") return <p className="answer-text">{block.text}</p>;
  if (block.type === "sql")
    return (
      <details className="sql">
        <summary>Executed SQL · {block.purpose}</summary>
        <pre>
          {block.sql}
          {"\n\n"}Parameters: {JSON.stringify(block.parameters, null, 2)}
        </pre>
      </details>
    );
  if (block.type === "table") {
    const info = block.completeness || {};
    return (
      <section className="result">
        <h3>{block.title}</h3>
        {info.mode === "shortlist" && (
          <p className="note">
            Shortlist · assessed {String(info.processed)} of{" "}
            {String(info.eligible)} eligible candidates
          </p>
        )}
        {info.mode === "exhaustive" && (
          <p className="note">
            Exhaustive coverage: {String(info.processed)} /{" "}
            {String(info.eligible)} · uncertain: {String(info.uncertain)}
          </p>
        )}
        {Boolean(info.truncated) && (
          <p className="warning">
            This displayed list is truncated. It is not the full result set.
          </p>
        )}
        <div
          className="table-scroll"
          tabIndex={0}
          aria-label={`${block.title} table`}
        >
          <table>
            <thead>
              <tr>
                {block.columns.map((c) => (
                  <th scope="col" key={c.key}>
                    {c.label}
                    {c.unit ? ` (${c.unit})` : ""}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {block.rows.map((r, i) => (
                <tr key={i}>
                  {block.columns.map((c) => (
                    <td key={c.key}>
                      {r[c.key] === null || r[c.key] === undefined
                        ? "—"
                        : String(r[c.key])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!block.rows.length && (
          <p className="note">No matching records under these conditions.</p>
        )}
      </section>
    );
  }
  if (block.type === "confirmation") {
    const f = block.fields;
    return (
      <section
        className={`booking ${block.status}`}
        aria-label="Soft booking proposal"
      >
        <div className="card-heading">
          <span className="eyebrow">SOFT BOOKING</span>
          <span className="badge">{block.status}</span>
        </div>
        <h3>{f.person}</h3>
        <dl>
          <div>
            <dt>Project</dt>
            <dd>{f.engagement}</dd>
          </div>
          <div>
            <dt>Period (inclusive)</dt>
            <dd>
              {f.start} — {f.end_inclusive}
            </dd>
          </div>
          <div>
            <dt>Hours</dt>
            <dd>{f.hours}</dd>
          </div>
        </dl>
        {f.warnings?.map((w, i) => (
          <p className="warning" key={i}>
            {w}
          </p>
        ))}
        {block.status === "pending" ? (
          <>
            <p className="note">
              No booking has been created. Confirm these exact terms to save it.
            </p>
            <div className="actions">
              <button
                disabled={disabled}
                onClick={() => onDecision(block.action_id, "confirm")}
              >
                Confirm soft booking
              </button>
              <button
                className="secondary"
                disabled={disabled}
                onClick={() => onDecision(block.action_id, "reject")}
              >
                Reject
              </button>
            </div>
          </>
        ) : (
          <p className="note">
            {block.booking_id
              ? `Saved booking #${block.booking_id}`
              : block.status === "rejected"
                ? "Rejected — no booking was created."
                : "This proposal has been superseded."}
          </p>
        )}
      </section>
    );
  }
  return <p role="alert">Unsupported response block.</p>;
}

function App() {
  const [threads, setThreads] = useState<Thread[]>([]),
    [thread, setThread] = useState(""),
    [history, setHistory] = useState<History | null>(null),
    [input, setInput] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState<Set<string>>(new Set()),
    [health, setHealth] = useState({ chat: "unknown", embeddings: "unknown" });
  const [ready, setReady] = useState(false),
    [navigating, setNavigating] = useState(false);
  const [retry, setRetry] = useState<{
    thread: string;
    request_id: string;
    text: string;
    mode: "same" | "new";
  } | null>(null);
  const current = useRef(""),
    inputRef = useRef<HTMLTextAreaElement>(null),
    endRef = useRef<HTMLDivElement>(null);
  const setWorking = (id: string, value: boolean) =>
    setBusy((previous) => {
      const next = new Set(previous);
      value ? next.add(id) : next.delete(id);
      return next;
    });
  const refreshList = async () => setThreads(await api<Thread[]>("/threads"));
  const load = async (id: string) => {
    const data = await api<History>(`/threads/${id}`);
    if (current.current === id) setHistory(data);
    return data;
  };
  const choose = async (id: string) => {
    setNavigating(true);
    current.current = id;
    setThread(id);
    setHistory(null);
    setError("");
    localStorage.setItem("resourcing-thread", id);
    window.history.replaceState(null, "", `?thread=${id}`);
    try {
      await load(id);
    } catch (e) {
      setError(String(e));
    } finally {
      setNavigating(false);
    }
  };
  const create = async () => {
    setNavigating(true);
    try {
      const t = await api<{ thread_id: string }>("/threads", {});
      await refreshList();
      await choose(t.thread_id);
      inputRef.current?.focus();
    } catch (e) {
      setError(String(e));
    } finally {
      setNavigating(false);
    }
  };
  useEffect(() => {
    void (async () => {
      try {
        setHealth(await api("/health"));
        const list = await api<Thread[]>("/threads");
        setThreads(list);
        const selected =
          new URLSearchParams(location.search).get("thread") ||
          localStorage.getItem("resourcing-thread") ||
          list[0]?.thread_id;
        if (selected) await choose(selected);
        else await create();
      } catch (e) {
        setError(String(e));
      } finally {
        setReady(true);
      }
    })();
  }, []);
  const interrupted = history?.requests.find((r) => r.status === "interrupted");
  const processing = history?.requests.some((r) => r.status === "processing");
  const disabled =
    !ready ||
    navigating ||
    busy.has(thread) ||
    Boolean(interrupted) ||
    Boolean(processing);
  useEffect(() => {
    if (!processing || !thread) return;
    const timer = setInterval(() => {
      void load(thread).catch((e) => setError(String(e)));
    }, 1500);
    return () => clearInterval(timer);
  }, [processing, thread]);
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [history, busy]);
  useEffect(() => {
    if (
      ready &&
      !navigating &&
      !busy.has(thread) &&
      !interrupted &&
      !processing
    )
      inputRef.current?.focus();
  }, [thread, ready, navigating, busy]);
  const send = async (saved?: {
    thread: string;
    request_id: string;
    text: string;
  }) => {
    const text = saved?.text ?? input.trim(),
      id = saved?.thread ?? thread;
    if (!text || !id) return;
    const request = {
      thread: id,
      request_id: saved?.request_id ?? crypto.randomUUID(),
      text,
    };
    setWorking(id, true);
    setInput("");
    setError("");
    setRetry(null);
    try {
      await api<Answer>(`/threads/${id}/messages`, {
        request_id: request.request_id,
        text,
      });
      await load(id);
      await refreshList();
      setHealth(await api("/health"));
    } catch (e) {
      setError(String(e));
      let mode: "same" | "new" = "same";
      try {
        const saved = await load(id);
        if (
          saved.requests.some(
            (r) => r.request_id === request.request_id && r.status === "failed",
          )
        )
          mode = "new";
      } catch {
        /* Unknown network outcome keeps the original identity. */
      }
      setRetry({ ...request, mode });
    } finally {
      setWorking(id, false);
      inputRef.current?.focus();
    }
  };
  const decide = async (action: string, decision: "confirm" | "reject") => {
    const id = thread;
    setWorking(id, true);
    setError("");
    try {
      await api(`/threads/${id}/confirm`, { action_id: action, decision });
      await load(id);
    } catch (e) {
      setError(
        `${String(e)}. Refresh history to verify the saved outcome before retrying.`,
      );
      try {
        await load(id);
      } catch {
        /* Outcome remains unknown. */
      }
    } finally {
      setWorking(id, false);
    }
  };
  const resume = async () => {
    if (!interrupted) return;
    const id = thread;
    setWorking(id, true);
    setError("");
    try {
      await api(`/threads/${id}/requests/${interrupted.request_id}/resume`, {});
      await load(id);
    } catch (e) {
      setError(String(e));
      await load(id).catch(() => {});
    } finally {
      setWorking(id, false);
    }
  };
  const pendingShown = history?.messages.some(
    (m) =>
      typeof m.content !== "string" &&
      m.content.blocks.some(
        (b) =>
          b.type === "confirmation" &&
          b.action_id === history.pending_action?.action_id,
      ),
  );
  return (
    <div className="shell">
      <aside>
        <a className="brand" href="/" aria-label="Resourcing Assistant home">
          <span className="brand-icon">r</span>
          <span>
            Resourcing<span className="brand-sub">ASSISTANT</span>
          </span>
        </a>
        <button
          className="new-chat"
          disabled={!ready || navigating}
          onClick={() => void create()}
        >
          ＋ New conversation
        </button>
        <div className="eyebrow sidebar-title">SAVED CONVERSATIONS</div>
        <nav aria-label="Saved conversations">
          {threads.map((t) => (
            <button
              key={t.thread_id}
              aria-label={`Open conversation: ${t.label || "New conversation"}`}
              disabled={navigating}
              className={`thread ${thread === t.thread_id ? "selected" : ""}`}
              onClick={() => void choose(t.thread_id)}
            >
              {t.label || "New conversation"}
            </button>
          ))}
        </nav>
        <div className="sidebar-footer">
          <span className="dot" />
          Local workspace<span>Source-grounded · Human-approved writes</span>
        </div>
      </aside>
      <main>
        <header>
          <div>
            <span className="eyebrow">YOUR RESOURCE WORKSPACE</span>
            <h1>Resourcing Assistant</h1>
          </div>
          <span className="reference">
            Reference date
            <br />
            <strong>
              {history?.effective_reference_date.slice(0, 10) || "Loading…"} UTC
            </strong>
          </span>
        </header>
        <div className="conversation" aria-live="polite">
          {health.chat === "not_configured" && (
            <div className="notice">
              Azure access is not configured. Saved conversations remain
              available. Add endpoint/key to the local .env and restart the API
              to ask questions.
            </div>
          )}
          {health.embeddings === "degraded" && (
            <div className="notice">
              Embedding search is degraded. Cached vectors or original-text
              assessment may be used; some requests can take longer.
            </div>
          )}
          {history !== null && history.messages.length === 0 && (
            <section className="welcome">
              <span className="welcome-icon">↗</span>
              <h2>
                Find the right people.
                <br />
                See the evidence.
              </h2>
              <p>
                Explore skills, project work and staffing risks. Review exact
                terms before creating a soft booking.
              </p>
              <div className="examples">
                <button
                  disabled={disabled}
                  onClick={() =>
                    setInput(
                      "Who in EMEA has Python at proficiency 4 or higher?",
                    )
                  }
                >
                  Find people by skills <span>↗</span>
                </button>
                <button
                  disabled={disabled}
                  onClick={() =>
                    setInput("Which active projects have staffing risks?")
                  }
                >
                  Explore project risks <span>↗</span>
                </button>
              </div>
            </section>
          )}
          {history?.messages.map((m) => (
            <article key={m.message_id} className={`message ${m.role}`}>
              <div className="message-label">
                {m.role === "user" ? "YOU" : "RESOURCING ASSISTANT"}
              </div>
              {typeof m.content === "string" ? (
                <p className="answer-text">{m.content}</p>
              ) : (
                <Blocks
                  answer={m.content}
                  disabled={disabled}
                  onDecision={(id, d) => void decide(id, d)}
                />
              )}
            </article>
          ))}
          {history?.pending_action && !pendingShown && (
            <BlockView
              block={{ type: "confirmation", ...history.pending_action }}
              disabled={disabled}
              onDecision={(id, d) => void decide(id, d)}
            />
          )}
          {history?.requests
            .filter((r) => r.status === "failed")
            .map((r) => (
              <p className="warning" key={r.request_id}>
                A previous request failed.{" "}
                {r.error
                  ? (() => {
                      try {
                        return JSON.parse(r.error).message;
                      } catch {
                        return "See local diagnostics.";
                      }
                    })()
                  : ""}
              </p>
            ))}
          {interrupted && (
            <div className="notice">
              <strong>This request was interrupted.</strong>
              <p>
                Continue from the saved graph checkpoint before asking another
                question here, or open a new conversation.
              </p>
              <button disabled={busy.has(thread)} onClick={() => void resume()}>
                Continue request
              </button>
            </div>
          )}
          {(busy.has(thread) || processing) && (
            <p role="status" className="working">
              <span className="dot" />
              Working with your source data…
            </p>
          )}
          {error && (
            <div role="alert" className="error">
              {error}
              <div className="actions">
                <button
                  className="secondary"
                  onClick={() =>
                    void load(thread).catch((e) => setError(String(e)))
                  }
                >
                  Refresh history
                </button>
                {retry?.thread === thread && (
                  <button
                    disabled={disabled}
                    onClick={() =>
                      void send(
                        retry.mode === "new"
                          ? { ...retry, request_id: crypto.randomUUID() }
                          : retry,
                      )
                    }
                  >
                    {retry.mode === "new"
                      ? "Try as a new request"
                      : "Retry same request"}
                  </button>
                )}
              </div>
            </div>
          )}
          <div ref={endRef} />
        </div>
        <form
          className="composer"
          onSubmit={(e) => {
            e.preventDefault();
            void send();
          }}
        >
          <label className="sr-only" htmlFor="message">
            Message
          </label>
          <textarea
            id="message"
            ref={inputRef}
            value={input}
            disabled={disabled || !thread}
            placeholder="Ask about people, projects, skills or a soft booking…"
            rows={2}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                if (!disabled) void send();
              }
            }}
          />
          <button
            aria-label="Send message"
            disabled={disabled || !input.trim() || !thread}
            type="submit"
          >
            Send ↑
          </button>
          <p>
            Answers use the supplied database. Bookings require your explicit
            confirmation.
          </p>
        </form>
      </main>
    </div>
  );
}
createRoot(document.getElementById("root")!).render(<App />);
