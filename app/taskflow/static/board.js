// All writes go through the public JSON API — the page holds no rules of
// its own. After a successful write the page simply reloads; the server
// re-renders the board from the same source the API reads.

async function callApi(url, method, payload) {
  const response = await fetch(url, {
    method: method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const message =
      body && body.error ? body.error.message : "HTTP " + response.status;
    alert("Request failed: " + message);
    return false;
  }
  return true;
}

document.addEventListener("click", async (event) => {
  const button = event.target.closest("button.move");
  if (!button) return;
  button.disabled = true;
  const ok = await callApi("/api/v1/tasks/" + button.dataset.taskId, "PATCH", {
    status: button.dataset.status,
  });
  if (ok) {
    location.reload();
  } else {
    button.disabled = false;
  }
});

const form = document.getElementById("create-task");
if (form) {
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const fields = new FormData(form);
    const payload = {
      board_id: Number(fields.get("board_id")),
      title: fields.get("title"),
      priority: fields.get("priority"),
    };
    const assignee = fields.get("assignee").trim();
    if (assignee) payload.assignee = assignee;
    if (await callApi("/api/v1/tasks", "POST", payload)) location.reload();
  });
}
