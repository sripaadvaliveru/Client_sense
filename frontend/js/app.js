/* ClientSense frontend.
 *
 * All values that originate from the LLM (brief fields, red flags, nudge copy)
 * are inserted with textContent, never innerHTML - the memory bank content is
 * untrusted input as far as the DOM is concerned.
 */
(function () {
    "use strict";

    var API_BASE =
        new URLSearchParams(window.location.search).get("api") ||
        "http://localhost:8000";

    var state = {
        clients: [],
        client: "",
    };

    // -- tiny DOM helper -------------------------------------------------
    function el(tag, className, text) {
        var node = document.createElement(tag);
        if (className) node.className = className;
        if (text !== undefined && text !== null) node.textContent = String(text);
        return node;
    }

    function $(id) {
        return document.getElementById(id);
    }

    function clear(node) {
        while (node.firstChild) node.removeChild(node.firstChild);
    }

    function show(node, visible) {
        node.classList.toggle("hidden", !visible);
    }

    // -- networking ------------------------------------------------------
    async function api(path, options) {
        var response = await fetch(API_BASE + path, Object.assign({
            headers: { "Content-Type": "application/json" },
        }, options || {}));

        var payload = null;
        try {
            payload = await response.json();
        } catch (err) {
            payload = null;
        }

        if (!response.ok) {
            var detail =
                (payload && (payload.detail || payload.message)) ||
                "HTTP " + response.status;
            throw new Error(detail);
        }
        return payload;
    }

    function setStatus(id, message, kind) {
        var node = $(id);
        node.textContent = message || "";
        node.className = "status" + (kind ? " status-" + kind : "");
    }

    // -- client selection ------------------------------------------------
    function selectedClient() {
        var typed = $("client-name").value.trim();
        return typed || state.client;
    }

    function syncClientFromInputs() {
        var typed = $("client-name").value.trim();
        var chosen = $("client-select").value;
        state.client = typed || chosen;
        $("picker-hint").textContent = state.client
            ? "Acting on: " + state.client
            : "Choose or type a client to begin.";
    }

    async function loadClients() {
        var select = $("client-select");
        try {
            state.clients = await api("/clients") || [];
        } catch (err) {
            clear(select);
            select.appendChild(el("option", null, "Could not load clients"));
            $("picker-hint").textContent =
                "Start the backend on " + API_BASE + " (" + err.message + ")";
            return;
        }

        clear(select);
        if (!state.clients.length) {
            select.appendChild(el("option", null, "No clients yet - seed the bank"));
            return;
        }

        state.clients.forEach(function (client) {
            var slug = client.slug.replace(/^client-/, "").replace(/-/g, " ");
            var label = client.slug.charAt(0).toUpperCase() + slug.slice(1);
            var option = el("option", null, label + "  (" + client.memories + ")");
            option.value = client.tag.replace("client:", "");
            select.appendChild(option);
        });

        // Pre-select the revision-heavy client: the most useful default.
        var preferred = state.clients.find(function (c) {
            return c.slug.indexOf("bloom") !== -1;
        }) || state.clients[0];
        select.value = preferred.slug;
        $("client-select").dataset.display = preferred.slug;
        state.client = titleCase(preferred.slug);
        $("client-name").placeholder = state.client + " (or type a new name)";
    }

    function titleCase(slug) {
        return slug
            .split("-")
            .map(function (word) {
                return word.charAt(0).toUpperCase() + word.slice(1);
            })
            .join(" ");
    }

    // Briefs are keyed by the display name; the bank stores tags, so the
    // display name is what the user typed and is what we retain against.
    function resolveClientName() {
        var typed = $("client-name").value.trim();
        if (typed) return typed;
        var slug = $("client-select").value;
        if (!slug) return "";
        return titleCase(slug);
    }

    // -- view 1: brief ----------------------------------------------------
    async function loadBrief() {
        var name = resolveClientName();
        if (!name) {
            setStatus("brief-status", "Choose a client first", "error");
            return;
        }

        setStatus("brief-status", "Reading memory and reasoning...");
        $("get-brief-btn").disabled = true;
        show($("brief-result"), true);

        try {
            var data = await api("/client-brief", {
                method: "POST",
                body: JSON.stringify({ client_name: name }),
            });
            renderBrief(data);
            setStatus("brief-status", "Brief generated", "ok");
        } catch (err) {
            setStatus("brief-status", err.message, "error");
        } finally {
            $("get-brief-btn").disabled = false;
        }
    }

    function renderBrief(data) {
        $("brief-client-name").textContent = data.client_name;

        var summary = data.evidence_summary || {};
        $("brief-meta").textContent =
            (summary.total_interactions || 0) + " memories on file · " +
            (summary.cited_memories || 0) + " cited · confidence: " +
            (data.confidence || "unknown");

        $("brief-payment").textContent = data.payment_behavior || "No data.";
        $("brief-revision").textContent = data.revision_scope_behavior || "No data.";
        $("brief-communication").textContent = data.communication_style || "No data.";
        $("brief-recommendation").textContent = data.recommendation || "No recommendation.";

        var flags = $("brief-red-flags");
        clear(flags);
        if (!data.red_flags || !data.red_flags.length) {
            flags.appendChild(el("p", "muted", "No red flags backed by enough history."));
        } else {
            data.red_flags.forEach(function (flag) {
                var box = el("div", "flag flag-" + (flag.severity || "medium"));
                var head = el("div", "flag-head");
                head.appendChild(el("span", "flag-title", flag.flag));
                head.appendChild(
                    el("span", "flag-count", (flag.evidence_count || 0) + " instances")
                );
                box.appendChild(head);
                (flag.evidence || []).forEach(function (line) {
                    box.appendChild(el("p", "flag-evidence", line));
                });
                flags.appendChild(box);
            });
        }

        var cited = (data.evidence_summary || {}).cited_memories || 0;
        $("brief-evidence").textContent = cited
            ? "This brief drew on " + cited + " retrieved memories."
            : "No memories were cited.";

        show($("brief-citations-wrap"), false);

        // Markdown fallback: shown only when structured parsing failed.
        if (data.raw_analysis) {
            $("brief-raw").textContent = data.raw_analysis;
            show($("brief-raw-wrap"), true);
        } else {
            show($("brief-raw-wrap"), false);
        }
    }

    // -- view 2: log interaction ----------------------------------------
    async function logInteraction(event) {
        event.preventDefault();

        var name = resolveClientName();
        var text = $("log-text").value.trim();
        if (!name || !text) {
            setStatus("log-status", "Client and description are required", "error");
            return;
        }

        var amount = parseFloat($("log-amount").value);
        $("log-submit").disabled = true;
        setStatus("log-status", "Retaining interaction...");

        try {
            var result = await api("/log-interaction", {
                method: "POST",
                body: JSON.stringify({
                    client_name: name,
                    interaction_text: text,
                    event_type: $("log-type").value,
                    project: $("log-project").value.trim() || null,
                    amount: isNaN(amount) ? null : amount,
                }),
            });

            $("log-text").value = "";
            setStatus("log-status", result.message, "ok");
            renderNudge(result.proactive_nudge);
            loadClients();
        } catch (err) {
            setStatus("log-status", err.message, "error");
        } finally {
            $("log-submit").disabled = false;
        }
    }

    function renderNudge(nudge) {
        var host = $("nudge-result");
        clear(host);
        if (!nudge) return;

        if (!nudge.should_nudge) {
            var quiet = el("div", "nudge nudge-quiet");
            quiet.appendChild(el("h3", null, "No pattern flagged"));
            quiet.appendChild(
                el("p", "muted",
                    nudge.structured_output_error
                        ? "Nudge unavailable: " + nudge.structured_output_error
                        : "This interaction did not match anything in the client's history.")
            );
            host.appendChild(quiet);
            return;
        }

        var box = el("div", "nudge nudge-alert");
        var head = el("div", "nudge-head");
        head.appendChild(el("h3", null, "Pattern flagged"));
        var kind = nudge.pattern_type === "new_escalation"
            ? "Beyond their usual pattern"
            : "Known pattern repeating";
        head.appendChild(el("span", "nudge-kind", kind));
        box.appendChild(head);

        if (nudge.pattern_matched) {
            box.appendChild(el("p", "nudge-pattern", nudge.pattern_matched));
        }
        box.appendChild(el("p", "nudge-message", nudge.nudge_message || ""));

        if (nudge.recommended_action) {
            var action = el("p", "nudge-action");
            action.appendChild(el("strong", null, "Do now: "));
            action.appendChild(document.createTextNode(nudge.recommended_action));
            box.appendChild(action);
        }

        if ((nudge.evidence || []).length) {
            var list = el("ul", "nudge-evidence");
            nudge.evidence.forEach(function (line) {
                list.appendChild(el("li", null, line));
            });
            box.appendChild(list);
        }

        box.appendChild(
            el("p", "nudge-foot",
                "Backed by " + (nudge.evidence_count || 0) + " earlier interactions.")
        );
        host.appendChild(box);
    }

    // -- view 3: timeline -------------------------------------------------
    async function loadTimeline() {
        var name = resolveClientName();
        if (!name) {
            setStatus("timeline-status", "Choose a client first", "error");
            return;
        }

        setStatus("timeline-status", "Loading history...");
        var host = $("timeline-result");
        clear(host);

        try {
            var data = await api(
                "/timeline/" + encodeURIComponent(name) + "?limit=50"
            );
            clear(host);

            if (!data.total) {
                host.appendChild(el("p", "muted", "No retained history for " + name + " yet."));
                setStatus("timeline-status", "Empty", "ok");
                return;
            }

            setStatus("timeline-status", data.total + " memories", "ok");
            var list = el("ol", "timeline");
            data.items.forEach(function (item) {
                var entry = el("li", "timeline-item");
                var when = (item.occurred_start || item.mentioned_at || "").slice(0, 10);
                var head = el("div", "timeline-head");
                head.appendChild(el("span", "timeline-date", when || "undated"));
                var context = item.context || "interaction";
                head.appendChild(el("span", "timeline-type", context));
                entry.appendChild(head);
                entry.appendChild(el("p", "timeline-text", item.text));
                list.appendChild(entry);
            });
            host.appendChild(list);
        } catch (err) {
            clear(host);
            host.appendChild(el("p", "error", err.message));
            setStatus("timeline-status", "Failed", "error");
        }
    }

    // -- tabs -------------------------------------------------------------
    function initTabs() {
        var tabs = document.querySelectorAll(".tab");
        Array.prototype.forEach.call(tabs, function (tab) {
            tab.addEventListener("click", function () {
                Array.prototype.forEach.call(tabs, function (other) {
                    other.classList.toggle("active", other === tab);
                    other.setAttribute("aria-selected", String(other === tab));
                });
                ["brief", "log", "timeline"].forEach(function (name) {
                    show($("view-" + name), name === tab.dataset.view);
                });
            });
        });
    }

    // -- init -------------------------------------------------------------
    document.addEventListener("DOMContentLoaded", function () {
        initTabs();

        $("get-brief-btn").addEventListener("click", loadBrief);
        $("get-timeline-btn").addEventListener("click", loadTimeline);
        $("log-form").addEventListener("submit", logInteraction);
        $("client-select").addEventListener("change", syncClientFromInputs);
        $("client-name").addEventListener("input", syncClientFromInputs);

        $("client-name").addEventListener("keypress", function (event) {
            if (event.key === "Enter") {
                event.preventDefault();
                loadBrief();
            }
        });

        loadClients().then(syncClientFromInputs);
    });
})();
