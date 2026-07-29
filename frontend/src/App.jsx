import React, { useEffect, useRef, useState } from "react";

const api = async (path, options = {}, token) => {
  const headers = { ...(options.headers || {}) };
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`/api${path}`, { ...options, headers });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`);
  return data;
};

function Login({ onLogin }) {
  const [username, setUsername] = useState("analyst");
  const [password, setPassword] = useState("demo");
  const [error, setError] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    try {
      const session = await api("/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      onLogin(session);
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div className="login-wrap">
      <form className="login-card" onSubmit={submit}>
        <h1>AriesView</h1>
        <p className="subtitle">AI-powered document intelligence for CRE</p>
        <label>
          Username
          <input value={username} onChange={(e) => setUsername(e.target.value)} />
        </label>
        <label>
          Password
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
        </label>
        {error && <div className="error">{error}</div>}
        <button type="submit">Sign in</button>
        <p className="hint">Demo accounts: analyst / demo · admin / demo</p>
      </form>
    </div>
  );
}

export default function App() {
  const [session, setSession] = useState(null);
  const [docs, setDocs] = useState([]);
  const [messages, setMessages] = useState([]);
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState(false);
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef();
  const bottomRef = useRef();

  const refreshDocs = async (token) => {
    try {
      const data = await api("/documents", {}, token);
      setDocs(data.documents);
    } catch {
      /* ingestion service may still be starting */
    }
  };

  useEffect(() => {
    if (session) refreshDocs(session.token);
  }, [session]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  if (!session) return <Login onLogin={setSession} />;

  const upload = async (file) => {
    setUploading(true);
    try {
      const form = new FormData();
      form.append("file", file);
      const result = await api("/upload", { method: "POST", body: form }, session.token);
      setMessages((m) => [
        ...m,
        {
          role: "system",
          text: `Ingested ${result.source_file} (${result.document_type} PDF) — ${result.chunks_indexed} chunks indexed.`,
        },
      ]);
      refreshDocs(session.token);
    } catch (err) {
      setMessages((m) => [...m, { role: "system", text: `Upload failed: ${err.message}` }]);
    } finally {
      setUploading(false);
      fileRef.current.value = "";
    }
  };

  const ask = async (e) => {
    e.preventDefault();
    const q = query.trim();
    if (!q || busy) return;
    setQuery("");
    setMessages((m) => [...m, { role: "user", text: q }]);
    setBusy(true);
    try {
      const result = await api(
        "/query",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ query: q }),
        },
        session.token
      );
      setMessages((m) => [
        ...m,
        { role: "assistant", text: result.answer, sources: result.sources, latency: result.latency_ms },
      ]);
    } catch (err) {
      setMessages((m) => [...m, { role: "system", text: `Query failed: ${err.message}` }]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="layout">
      <aside className="sidebar">
        <h2>AriesView</h2>
        <div className="user">
          {session.name}
          <span className="roles">{session.roles.join(", ")}</span>
        </div>
        <button
          className="upload-btn"
          disabled={uploading}
          onClick={() => fileRef.current.click()}
        >
          {uploading ? "Ingesting…" : "Upload PDF"}
        </button>
        <input
          ref={fileRef}
          type="file"
          accept="application/pdf"
          hidden
          onChange={(e) => e.target.files[0] && upload(e.target.files[0])}
        />
        <h3>Documents</h3>
        <ul className="docs">
          {docs.map((d) => (
            <li key={d.document_id}>
              <span className="doc-name">{d.source_file}</span>
              <span className="doc-meta">
                {d.document_type} · {d.portfolio}
              </span>
            </li>
          ))}
          {docs.length === 0 && <li className="empty">No documents yet</li>}
        </ul>
        <button className="logout" onClick={() => setSession(null)}>
          Sign out
        </button>
      </aside>

      <main className="chat">
        <div className="messages">
          {messages.length === 0 && (
            <div className="placeholder">
              Upload a lease or offering memorandum, then ask a question — e.g.{" "}
              <em>"Can the tenant terminate the lease early?"</em>
            </div>
          )}
          {messages.map((m, i) => (
            <div key={i} className={`msg ${m.role}`}>
              <div className="bubble">
                {m.text}
                {m.sources && m.sources.length > 0 && (
                  <div className="sources">
                    {m.sources.map((s) => (
                      <span key={s.ref} className="source">
                        [{s.ref}] {s.source_file} · {s.section_label}
                      </span>
                    ))}
                    {m.latency && <span className="latency">{(m.latency / 1000).toFixed(1)}s</span>}
                  </div>
                )}
              </div>
            </div>
          ))}
          <div ref={bottomRef} />
        </div>
        <form className="composer" onSubmit={ask}>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={busy ? "Generating…" : "Ask about your documents"}
            disabled={busy}
          />
          <button type="submit" disabled={busy || !query.trim()}>
            Send
          </button>
        </form>
      </main>
    </div>
  );
}
