import { Send } from "lucide-react";
import { type FormEvent, useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api, qs } from "../api/client";
import type { UserBrief } from "../api/types";
import { Card, EmptyState, PageHeader, Spinner } from "../components/ui";
import { cx } from "../lib/cx";
import { useToast } from "../context/ToastContext";
import { ROLE_LABEL, timeAgo } from "../lib/format";
import { useDebounced, useFetch } from "../lib/hooks";

interface Conv { user: UserBrief; last: string; last_at: string; unread: number }
interface Thread { user: UserBrief; messages: { id: number; body: string; mine: boolean; created_at: string }[] }

export default function Messages() {
  const toast = useToast();
  const [params, setParams] = useSearchParams();
  const other = params.get("u");
  const convs = useFetch<Conv[]>("/api/messages");
  const thread = useFetch<Thread>(other ? `/api/messages/${other}` : null);
  const [search, setSearch] = useState("");
  const ds = useDebounced(search);
  const contacts = useFetch<(UserBrief & { staff_type: string | null })[]>(ds.length >= 2 ? `/api/messages/contacts${qs({ q: ds })}` : null);
  const [text, setText] = useState("");
  const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => endRef.current?.scrollIntoView({ block: "end" }), [thread.data]);

  async function send(e: FormEvent) {
    e.preventDefault();
    if (!text.trim() || !other) return;
    try {
      await api.post("/api/messages", { recipient_id: Number(other), body: text });
      setText("");
      void thread.reload();
      void convs.reload();
    } catch (e2) {
      toast("error", (e2 as Error).message);
    }
  }

  return (
    <>
      <PageHeader title="Messages" subtitle="Message wardens, hostel staff and other students." />
      <div className="grid gap-6 lg:grid-cols-3">
        <Card title="Conversations">
          <input type="search" aria-label="Find a person" placeholder="Find a person (name or reg. no.)" value={search} onChange={(e) => setSearch(e.target.value)} className="mb-3 w-full rounded-lg border border-slate-300 px-3 py-1.5 text-sm" />
          {ds.length >= 2 && contacts.data && (
            <ul className="mb-3 divide-y divide-slate-100 rounded-lg border border-slate-200">
              {contacts.data.length ? contacts.data.map((c) => (
                <li key={c.id}><button className="w-full px-3 py-2 text-left text-sm hover:bg-slate-50" onClick={() => { setParams({ u: String(c.id) }); setSearch(""); }}>{c.full_name} <span className="text-xs text-slate-500">· {ROLE_LABEL[c.role]}{c.reg_no ? ` · ${c.reg_no}` : ""}</span></button></li>
              )) : <li className="px-3 py-2 text-sm text-slate-500">No matches</li>}
            </ul>
          )}
          {convs.loading && !convs.data ? <Spinner /> : !convs.data?.length ? <p className="text-sm text-slate-500">No conversations yet. Search for a person above.</p> : (
            <ul className="space-y-1">
              {convs.data.map((c) => (
                <li key={c.user.id}>
                  <button onClick={() => setParams({ u: String(c.user.id) })} className={cx("w-full rounded-lg px-3 py-2 text-left hover:bg-slate-50", other === String(c.user.id) && "bg-navy-50")}>
                    <div className="flex items-center justify-between"><span className="text-sm font-medium text-slate-800">{c.user.full_name}</span>{c.unread > 0 && <span className="rounded-full bg-navy-700 px-1.5 text-[11px] font-bold text-white">{c.unread}</span>}</div>
                    <p className="truncate text-xs text-slate-500">{c.last} · {timeAgo(c.last_at)}</p>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card title={thread.data ? `${thread.data.user.full_name} · ${ROLE_LABEL[thread.data.user.role]}` : "Conversation"} className="lg:col-span-2">
          {!other ? <EmptyState title="Select a conversation" /> : thread.loading && !thread.data ? <Spinner /> : (
            <>
              <div className="h-[50vh] space-y-2 overflow-y-auto rounded-lg bg-slate-50 p-3" data-testid="message-thread">
                {thread.data?.messages.length ? thread.data.messages.map((m) => (
                  <div key={m.id} className={cx("flex", m.mine ? "justify-end" : "justify-start")}>
                    <div className={cx("max-w-[80%] rounded-2xl px-3.5 py-2 text-sm", m.mine ? "bg-navy-700 text-white" : "bg-white text-slate-800 shadow-sm")}>
                      <p className="whitespace-pre-wrap">{m.body}</p>
                      <p className={cx("mt-0.5 text-[10px]", m.mine ? "text-navy-100" : "text-slate-500")}>{timeAgo(m.created_at)}</p>
                    </div>
                  </div>
                )) : <p className="py-10 text-center text-sm text-slate-500">Say hello 👋</p>}
                <div ref={endRef} />
              </div>
              <form onSubmit={send} className="mt-3 flex gap-2">
                <input aria-label="Message" value={text} onChange={(e) => setText(e.target.value)} maxLength={1000} placeholder="Type a message" className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm" />
                <button type="submit" className="inline-flex items-center gap-1 rounded-lg bg-navy-700 px-4 py-2 text-sm font-medium text-white hover:bg-navy-800 disabled:opacity-50" disabled={!text.trim()}><Send className="h-4 w-4" /> Send</button>
              </form>
            </>
          )}
        </Card>
      </div>
    </>
  );
}
