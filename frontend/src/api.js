const API_BASE = import.meta.env.VITE_API_BASE || "/api/v1";

async function check(res) {
  if (res.ok) return res;
  let detail = `${res.status} ${res.statusText}`;
  try {
    const body = await res.json();
    if (body.detail) detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
  } catch {
    /* not JSON */
  }
  throw new Error(detail);
}

export async function apiGet(path) {
  const res = await check(await fetch(`${API_BASE}${path}`));
  return res.json();
}

export async function apiPostForm(path, formData) {
  const res = await check(await fetch(`${API_BASE}${path}`, { method: "POST", body: formData }));
  return res.json();
}

export async function apiDelete(path) {
  await check(await fetch(`${API_BASE}${path}`, { method: "DELETE" }));
}

export async function apiPostBlob(path, body) {
  const res = await check(
    await fetch(`${API_BASE}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  );
  return res.blob();
}

// POST + server-sent events. Calls onEvent(name, data) for each event until the stream ends.
export async function apiStream(path, body, { onEvent, signal }) {
  const res = await check(
    await fetch(`${API_BASE}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify(body),
      signal,
    }),
  );
  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += value;
    let sep;
    while ((sep = buffer.indexOf("\n\n")) !== -1) {
      const block = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      let event = "message";
      let data = "";
      for (const line of block.split("\n")) {
        if (line.startsWith("event: ")) event = line.slice(7);
        else if (line.startsWith("data: ")) data += line.slice(6);
      }
      if (data) onEvent(event, JSON.parse(data));
    }
  }
}
