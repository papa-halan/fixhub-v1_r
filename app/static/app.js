async function sendJson(url, method, payload) {
  const headers = { "Content-Type": "application/json" };
  const currentUserEmail = document.body?.dataset?.userEmail;

  if (currentUserEmail) {
    headers["X-User-Email"] = currentUserEmail;
  }

  const response = await fetch(url, {
    method,
    headers,
    credentials: "same-origin",
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const detail = await response.json().catch(() => ({ detail: "Request failed" }));
    throw new Error(detail.detail || "Request failed");
  }

  return response.json();
}

function wireJsonForm(form, handler) {
  const feedback = form.querySelector("[data-feedback]");
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (feedback) {
      feedback.textContent = "";
    }

    try {
      await handler(new FormData(form), form);
    } catch (error) {
      if (feedback) {
        feedback.textContent = error.message;
      } else {
        window.alert(error.message);
      }
    }
  });
}

window.FixHub = { sendJson, wireJsonForm };
