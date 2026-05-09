// dropbox_oauth.js — ComfyUI extension for the DropSend Setup Node.
//
// Architecture summary
// --------------------
// The Setup Node deliberately has NO secret-bearing inputs in its
// Python INPUT_TYPES. app_key, app_secret, and auth_code are entered
// only via a browser-only modal launched from the "Set credentials…"
// button this extension installs on the node. The modal POSTs the
// values directly to /dropsend/setup/stash (a same-origin route
// registered by dropsend_setup_node.py) and closes. setup() consumes
// the stash entry on the next Queue.
//
// What this guarantees
//   • Secrets never enter any LiteGraph widget value, so they cannot
//     be serialized to workflow JSON, ComfyUI's localStorage auto-save,
//     PNG metadata, copy-pasted nodes, or PromptServer.history /
//     /history.
//   • Browser-native masking (input type=password) covers shoulder-
//     surfing during typing.
//   • Modal closes after Save; no in-process JS cache. User pastes
//     fresh values each time the modal opens — they don't persist
//     across modal sessions.
//
// Auto-trigger UX
// ---------------
// After Run 1 prints the OAuth URL banner, dropsend_setup_node.py
// sends a "dropsend_credentials_needed" WebSocket event to the
// originating client_id only. Receiving that event auto-opens the
// entry modal so the user can paste the auth_code (plus re-paste
// app_key/app_secret) without clicking the button between runs.

import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

// ---------------------------------------------------------------------------
// Constants and small helpers
// ---------------------------------------------------------------------------

// Node-type registered in NODE_CLASS_MAPPINGS in dropsend_setup_node.py.
const SETUP_NODE_TYPE = "DropSendSetup";

// Track OAuth popup window so a second click reuses/replaces the first.
let oauthPopup = null;

// Find every Setup Node currently in the graph (typically just one).
function findSetupNodes() {
    try {
        return app.graph.nodes.filter(n => n.type === SETUP_NODE_TYPE);
    } catch (e) {
        console.warn("[DropSendNode] Could not enumerate graph nodes:", e);
        return [];
    }
}

// ---------------------------------------------------------------------------
// "Set credentials…" button widget on the Setup Node
// ---------------------------------------------------------------------------

// Add the button widget to a Setup Node instance. Idempotent — safe
// to call repeatedly from any code path (prototype.onNodeCreated,
// loadedGraphNode, setup-time sweep) without producing duplicate
// buttons.
//
// Critical detail: after addWidget the node's bounding box must be
// recomputed via setSize(computeSize()), otherwise the new widget is
// drawn outside the existing draw area and looks "missing." This is
// the failure mode that hit when nodeCreated installed the button
// after ComfyUI had already laid out the node for its three other
// widgets.
function ensureCredentialButton(node) {
    if (!node || node.type !== SETUP_NODE_TYPE) return;
    if (node.__dropsendButtonAdded) return;
    if (typeof node.addWidget !== "function") {
        console.warn("[DropSendNode] node.addWidget unavailable; cannot install Set credentials button");
        return;
    }
    node.addWidget("button", "Set credentials…", null, () => {
        openCredentialEntryModal({ reason: "user-clicked" });
    });
    node.__dropsendButtonAdded = true;
    try {
        if (typeof node.computeSize === "function" && typeof node.setSize === "function") {
            node.setSize(node.computeSize());
        }
    } catch (e) {
        console.warn("[DropSendNode] could not recompute node size after adding button:", e);
    }
    try { app.graph.setDirtyCanvas(true, true); } catch (_) {}
    console.log(`[DropSendNode] Installed Set-credentials button on ${SETUP_NODE_TYPE}`);
}

// ---------------------------------------------------------------------------
// Credential ENTRY modal (the new input surface)
// ---------------------------------------------------------------------------
//
// This is the modal the user types secrets INTO. Distinct from
// showCredentialModal below, which is the OUTPUT modal that displays
// the four delivered credentials at the end of a successful Setup run.

function openCredentialEntryModal({ reason }) {
    // If an entry modal is already open (e.g. user clicked the button
    // twice, or auto-trigger fired while one was already open), just
    // bring it to focus instead of stacking.
    const existing = document.getElementById("dropsend-credentials-entry-modal");
    if (existing) {
        const firstInput = existing.querySelector("input");
        if (firstInput) firstInput.focus();
        return;
    }

    const overlay = document.createElement("div");
    overlay.id = "dropsend-credentials-entry-modal";
    overlay.style.cssText = [
        "position:fixed", "inset:0",
        "background:rgba(0,0,0,0.7)",
        "z-index:10001",
        "display:flex", "align-items:center", "justify-content:center",
        'font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif'
    ].join(";");

    const dialog = document.createElement("div");
    dialog.style.cssText = [
        "background:#1e1e1e", "color:#eaeaea",
        "border-radius:12px", "padding:24px",
        "max-width:520px", "width:90%",
        "box-shadow:0 20px 60px rgba(0,0,0,0.5)",
        "box-sizing:border-box"
    ].join(";");

    const header = document.createElement("div");
    header.style.cssText = "display:flex;justify-content:space-between;align-items:center;margin-bottom:8px";
    const title = document.createElement("h2");
    title.textContent = "Set DropSend Credentials";
    title.style.cssText = "margin:0;font-size:1.2rem;color:#fff";
    const closeX = document.createElement("button");
    closeX.textContent = "×";
    closeX.setAttribute("aria-label", "Close");
    closeX.style.cssText = "background:none;border:none;color:#999;font-size:1.5rem;cursor:pointer;padding:0 8px;line-height:1";
    closeX.onclick = () => overlay.remove();
    header.appendChild(title);
    header.appendChild(closeX);
    dialog.appendChild(header);

    const intro = document.createElement("p");
    intro.style.cssText = "color:#bbb;font-size:0.85rem;line-height:1.5;margin:0 0 16px 0";
    intro.textContent =
        reason === "auto-after-oauth-url"
            ? "Authorization URL printed in the ComfyUI terminal. Authorize at Dropbox, copy the auth code, then paste app_key + app_secret + auth_code below and click Save."
            : "Paste your Dropbox app_key and app_secret. Leave auth_code empty for now; you'll paste it later after authorizing at Dropbox. Values are sent to the server (browser only, never written to disk in display_only mode) and are NOT saved by ComfyUI in any workflow JSON, PNG metadata, or browser cache.";
    dialog.appendChild(intro);

    // Three password inputs.
    const fields = [
        { name: "app_key",    label: "App Key" },
        { name: "app_secret", label: "App Secret" },
        { name: "auth_code",  label: "Auth Code (paste after authorizing at Dropbox)" },
    ];
    const inputs = {};
    fields.forEach(({ name, label }) => {
        const row = document.createElement("div");
        row.style.cssText = "margin-bottom:12px";

        const lbl = document.createElement("label");
        lbl.textContent = label;
        lbl.style.cssText = "display:block;font-size:0.8rem;color:#aaa;margin-bottom:4px;letter-spacing:0.02em";
        row.appendChild(lbl);

        const input = document.createElement("input");
        input.type = "password";
        input.autocomplete = "off";
        input.spellcheck = false;
        input.value = "";
        input.style.cssText = "width:100%;box-sizing:border-box;padding:8px;font-family:Menlo,Monaco,monospace;font-size:0.9rem;background:#2a2a2a;color:#eaeaea;border:1px solid #444;border-radius:4px";
        row.appendChild(input);

        dialog.appendChild(row);
        inputs[name] = input;
    });

    // Status line for inline error messages from the Save handler.
    const status = document.createElement("p");
    status.style.cssText = "color:#f87171;font-size:0.8rem;margin:6px 0 0 0;min-height:1em";
    status.textContent = "";
    dialog.appendChild(status);

    const footer = document.createElement("div");
    footer.style.cssText = "display:flex;gap:10px;margin-top:16px;padding-top:12px;border-top:1px solid #333";

    const cancelBtn = document.createElement("button");
    cancelBtn.textContent = "Cancel";
    cancelBtn.style.cssText = "flex:1;padding:9px;background:#444;color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:0.9rem";
    cancelBtn.onclick = () => overlay.remove();

    const saveBtn = document.createElement("button");
    saveBtn.textContent = "Save";
    saveBtn.style.cssText = "flex:1;padding:9px;background:#3b82f6;color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:0.9rem";
    saveBtn.onclick = async () => {
        const payload = {
            app_key: inputs.app_key.value || "",
            app_secret: inputs.app_secret.value || "",
            auth_code: inputs.auth_code.value || "",
        };
        if (!payload.app_key && !payload.app_secret && !payload.auth_code) {
            status.textContent = "Nothing to save. Paste at least app_key + app_secret.";
            return;
        }
        const clientId = api && api.clientId ? api.clientId : null;
        if (!clientId) {
            status.textContent = "Browser not yet connected to ComfyUI. Wait a moment and try again.";
            return;
        }
        saveBtn.disabled = true;
        cancelBtn.disabled = true;
        try {
            const resp = await fetch("/dropsend/setup/stash", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ client_id: clientId, ...payload }),
            });
            if (!resp.ok) throw new Error("server returned " + resp.status);
        } catch (e) {
            console.error("[DropSendNode] Stash POST failed:", e);
            status.textContent = "Could not save: " + e.message;
            saveBtn.disabled = false;
            cancelBtn.disabled = false;
            return;
        }
        // Wipe the input values from DOM the moment Save succeeds —
        // even though the modal is about to be removed, we don't want
        // the values to sit in input.value while the GC catches up.
        Object.values(inputs).forEach(i => { i.value = ""; });
        overlay.remove();
        console.log("[DropSendNode] Stashed credentials via entry modal; click Queue to run setup");
    };

    footer.appendChild(cancelBtn);
    footer.appendChild(saveBtn);
    dialog.appendChild(footer);

    // Submit on Enter from any input.
    Object.values(inputs).forEach(input => {
        input.addEventListener("keydown", (ev) => {
            if (ev.key === "Enter") { ev.preventDefault(); saveBtn.click(); }
            if (ev.key === "Escape") { ev.preventDefault(); cancelBtn.click(); }
        });
    });

    overlay.appendChild(dialog);
    document.body.appendChild(overlay);

    // Auto-focus the first empty input — usually app_key on initial
    // open, auth_code if app_key is already filled (no longer applies
    // here since we don't pre-fill, but the same logic is harmless).
    setTimeout(() => {
        const firstEmpty = fields.map(f => inputs[f.name]).find(i => !i.value);
        if (firstEmpty) firstEmpty.focus();
    }, 0);
}

// ---------------------------------------------------------------------------
// OAuth popup window (delegate to Dropbox)
// ---------------------------------------------------------------------------

window.openDropboxOAuth = function (url) {
    console.log("[DropSendNode] Opening OAuth popup:", url);
    if (oauthPopup && !oauthPopup.closed) oauthPopup.close();
    const popup = window.open(
        url,
        "dropbox_oauth",
        "width=500,height=700,scrollbars=yes,resizable=yes,status=no,location=no,toolbar=no,menubar=no"
    );
    if (popup) {
        oauthPopup = popup;
        popup.focus();
        const checkClosed = setInterval(() => {
            if (popup.closed) {
                console.log("[DropSendNode] OAuth popup closed");
                clearInterval(checkClosed);
                oauthPopup = null;
            }
        }, 500);
        return popup;
    }
    console.error("[DropSendNode] OAuth popup blocked by browser?");
    return null;
};

// ---------------------------------------------------------------------------
// Credential OUTPUT modal (the existing display_only delivery surface)
// ---------------------------------------------------------------------------
//
// Renders the four credentials delivered by the server after a
// successful exchange. Browser-only — never persisted, discarded
// when closed.

function showCredentialModal(creds) {
    const existing = document.getElementById("dropsend-credentials-modal");
    if (existing) existing.remove();

    const overlay = document.createElement("div");
    overlay.id = "dropsend-credentials-modal";
    overlay.style.cssText = [
        "position:fixed", "inset:0",
        "background:rgba(0,0,0,0.7)",
        "z-index:10000",
        "display:flex", "align-items:center", "justify-content:center",
        'font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif'
    ].join(";");

    const dialog = document.createElement("div");
    dialog.style.cssText = [
        "background:#1e1e1e", "color:#eaeaea",
        "border-radius:12px", "padding:24px",
        "max-width:600px", "width:90%", "max-height:85vh",
        "overflow-y:auto",
        "box-shadow:0 20px 60px rgba(0,0,0,0.5)",
        "box-sizing:border-box"
    ].join(";");

    const header = document.createElement("div");
    header.style.cssText = "display:flex;justify-content:space-between;align-items:center;margin-bottom:12px";
    const title = document.createElement("h2");
    title.textContent = "DropSend Credentials";
    title.style.cssText = "margin:0;font-size:1.25rem;color:#fff";
    const closeX = document.createElement("button");
    closeX.textContent = "×";
    closeX.setAttribute("aria-label", "Close");
    closeX.style.cssText = "background:none;border:none;color:#999;font-size:1.5rem;cursor:pointer;padding:0 8px;line-height:1";
    closeX.onclick = () => overlay.remove();
    header.appendChild(title);
    header.appendChild(closeX);
    dialog.appendChild(header);

    const intro = document.createElement("p");
    intro.style.cssText = "color:#bbb;font-size:0.9rem;line-height:1.5;margin:0 0 18px 0";
    intro.textContent =
        "These values are shown only in this browser and will be discarded when you close " +
        "this dialog. They are NOT written to disk in this mode. Save each value somewhere " +
        "safe now (password manager, secure note). Then configure them as your platform's " +
        "secrets (RunPod Secrets, Docker env, systemd EnvironmentFile). Most cloud platforms " +
        "require a pod or container restart for new secrets to take effect. Running the " +
        "AutoUploader will fail until that restart completes.";
    dialog.appendChild(intro);

    const flashCopied = (btn) => {
        const original = btn.textContent;
        btn.textContent = "✓";
        setTimeout(() => { btn.textContent = original; }, 1200);
    };

    Object.entries(creds).forEach(([name, value]) => {
        const row = document.createElement("div");
        row.style.cssText = "margin-bottom:14px";

        const labelRow = document.createElement("div");
        labelRow.style.cssText = "display:flex;justify-content:space-between;align-items:center;margin-bottom:4px";
        const label = document.createElement("label");
        label.textContent = name;
        label.style.cssText = "font-weight:600;font-size:0.85rem;color:#aaa;letter-spacing:0.02em";

        const copyBtn = document.createElement("button");
        copyBtn.textContent = "Copy";
        copyBtn.style.cssText = "padding:4px 12px;font-size:0.8rem;background:#3b82f6;color:#fff;border:none;border-radius:4px;cursor:pointer";
        copyBtn.onclick = async () => {
            try {
                await navigator.clipboard.writeText(value);
                flashCopied(copyBtn);
            } catch (e) {
                input.select();
                document.execCommand("copy");
                flashCopied(copyBtn);
            }
        };
        labelRow.appendChild(label);
        labelRow.appendChild(copyBtn);

        const input = document.createElement("input");
        input.type = "text";
        input.value = value;
        input.readOnly = true;
        input.style.cssText = "width:100%;box-sizing:border-box;padding:8px;font-family:Menlo,Monaco,monospace;font-size:0.85rem;background:#2a2a2a;color:#eaeaea;border:1px solid #444;border-radius:4px";
        input.onclick = () => input.select();
        input.onfocus = () => input.select();

        row.appendChild(labelRow);
        row.appendChild(input);
        dialog.appendChild(row);
    });

    const footer = document.createElement("div");
    footer.style.cssText = "display:flex;gap:10px;margin-top:18px;padding-top:14px;border-top:1px solid #333";

    const copyAllBtn = document.createElement("button");
    copyAllBtn.textContent = "Copy all as NAME=value";
    copyAllBtn.style.cssText = "flex:1;padding:10px;background:#3b82f6;color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:0.9rem";
    copyAllBtn.onclick = async () => {
        const text = Object.entries(creds).map(([k, v]) => `${k}=${v}`).join("\n");
        try {
            await navigator.clipboard.writeText(text);
            flashCopied(copyAllBtn);
        } catch (e) {
            console.error("[DropSendNode] Clipboard write failed:", e);
            alert("Clipboard write failed; select and copy values manually.");
        }
    };

    const doneBtn = document.createElement("button");
    doneBtn.textContent = "I have copied them";
    doneBtn.style.cssText = "flex:1;padding:10px;background:#444;color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:0.9rem";
    doneBtn.onclick = () => overlay.remove();

    footer.appendChild(copyAllBtn);
    footer.appendChild(doneBtn);
    dialog.appendChild(footer);

    overlay.appendChild(dialog);
    document.body.appendChild(overlay);
}

// ---------------------------------------------------------------------------
// Extension registration
// ---------------------------------------------------------------------------

app.registerExtension({
    name: "DropSendNode.OAuthHandler",

    async setup() {
        console.log("[DropSendNode] OAuth extension loaded");

        // Defensive sweep: if ComfyUI restored a workflow before our
        // hooks were attached, install the button on any Setup Node
        // already in the graph at this point.
        try {
            findSetupNodes().forEach(n => ensureCredentialButton(n));
        } catch (e) {
            console.warn("[DropSendNode] setup-time sweep failed:", e);
        }

        // Reconnect-complete: server cleared credentials and wants the
        // browser to refresh so the auth UI is back in its initial state.
        api.addEventListener("dropbox_reconnect_complete", (event) => {
            console.log("[DropSendNode] dropbox_reconnect_complete:", event.detail);
            const data = event.detail;
            if (data && data.success) {
                this.handleReconnectSuccess();
            }
        });

        // Credentials-needed: server printed the OAuth URL and is
        // signaling the browser to open the entry modal so the user
        // can paste the auth_code (and re-paste app_key/app_secret)
        // as soon as Dropbox shows them the code.
        api.addEventListener("dropsend_credentials_needed", (event) => {
            console.log("[DropSendNode] dropsend_credentials_needed:", event.detail);
            const data = event.detail || {};
            const expectedClientId = data.client_id;
            const ourClientId = api && typeof api.clientId !== "undefined" ? api.clientId : null;
            if (expectedClientId && ourClientId && expectedClientId !== ourClientId) {
                console.warn(
                    "[DropSendNode] Ignoring credentials-needed event: client_id mismatch (got " +
                    String(expectedClientId) + ", expected " + String(ourClientId) + ")"
                );
                return;
            }
            openCredentialEntryModal({ reason: "auto-after-oauth-url" });
        });

        // Credentials-ready: server delivered the four output values
        // for display_only mode. Show the OUTPUT modal.
        api.addEventListener("dropsend_credentials_ready", (event) => {
            console.log("[DropSendNode] dropsend_credentials_ready");
            const data = event.detail;
            if (!data || !data.credentials || typeof data.credentials !== "object") {
                console.error("[DropSendNode] credentials_ready payload missing/malformed", event);
                return;
            }
            const expectedClientId = data.client_id;
            const ourClientId = api && typeof api.clientId !== "undefined" ? api.clientId : null;
            if (ourClientId == null) {
                console.warn(
                    "[DropSendNode] api.clientId not available, cannot defense-in-depth verify; " +
                    "trusting the server's sid-targeted delivery."
                );
            } else if (expectedClientId && expectedClientId !== ourClientId) {
                console.warn(
                    "[DropSendNode] Ignoring credentials event: client_id mismatch (got " +
                    String(expectedClientId) + ", expected " + String(ourClientId) + ")"
                );
                return;
            }
            // If an entry modal is still open from before, close it —
            // we don't need it any more, the values were consumed and
            // the OUTPUT modal is about to render.
            const entry = document.getElementById("dropsend-credentials-entry-modal");
            if (entry) entry.remove();
            showCredentialModal(data.credentials);
        });
    },

    resetReconnectFields() {
        try {
            findSetupNodes().forEach(node => {
                if (!node.widgets) return;
                const reconnectWidget = node.widgets.find(w => w.name === "reconnect");
                if (reconnectWidget && reconnectWidget.value === true) {
                    reconnectWidget.value = false;
                    if (node.onWidgetChanged) node.onWidgetChanged("reconnect", false);
                }
            });
        } catch (e) {
            console.log("[DropSendNode] Could not reset reconnect fields:", e);
        }
    },

    handleReconnectSuccess() {
        console.log("[DropSendNode] Reconnect success - refreshing UI to show auth fields");
        this.resetReconnectFields();
        // Close any open entry modal — the prior session is gone.
        const entry = document.getElementById("dropsend-credentials-entry-modal");
        if (entry) entry.remove();
        setTimeout(() => {
            console.log("[DropSendNode] Reloading after reconnect");
            window.location.reload();
        }, 1000);
    },

    nodeCreated(node) {
        ensureCredentialButton(node);
    },

    // Fires when a node is restored from saved state — auto-save in
    // localStorage on page reload, dragged workflow JSON, dragged PNG
    // with embedded workflow metadata. Without this, the button
    // wouldn't be added to nodes that already existed when the
    // workflow was loaded.
    loadedGraphNode(node, _app) {
        ensureCredentialButton(node);
    },

    // Install the Set-credentials button on every instance of the
    // Setup Node. We override prototype.onNodeCreated here (rather
    // than relying solely on the nodeCreated extension hook) because
    // it runs in-context with the node's construction, so the
    // button is added before ComfyUI computes the node's initial
    // size — guaranteeing the button is inside the drawn bounds.
    //
    // Also detects the OAuth URL printed by the Python setup() and
    // auto-opens it in a popup window.
    async beforeRegisterNodeDef(nodeType, nodeData, _app) {
        if (nodeData.name !== SETUP_NODE_TYPE) return;
        console.log(`[DropSendNode] Registered ${SETUP_NODE_TYPE} enhancement`);

        const origOnNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const r = origOnNodeCreated ? origOnNodeCreated.apply(this, arguments) : undefined;
            try {
                ensureCredentialButton(this);
            } catch (e) {
                console.warn("[DropSendNode] ensureCredentialButton via prototype hook failed:", e);
            }
            return r;
        };

        const originalExecuted = nodeType.prototype.onExecuted;
        nodeType.prototype.onExecuted = function (message) {
            try {
                if (message && message.text && message.text[0]) {
                    const text = message.text[0];
                    if (text.includes("Dropbox OAuth Ready!")) {
                        const m = text.match(/(https:\/\/www\.dropbox\.com\/oauth2\/authorize[^\s]+)/);
                        if (m) {
                            setTimeout(() => window.openDropboxOAuth(m[1]), 500);
                        }
                    }
                }
            } catch (e) {
                console.warn("[DropSendNode] onExecuted hook error:", e);
            }
            if (originalExecuted) return originalExecuted.apply(this, arguments);
        };
    },
});
