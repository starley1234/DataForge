let currentPage = 1;
const pageSize = 20;
let totalRecords = 0;
let pollTimer = null;

document.addEventListener("DOMContentLoaded", () => {
    loadStats();
    loadContacts();

    // Слушатель поиска по Enter
    document.getElementById("searchInput").addEventListener("keyup", (e) => {
        if (e.key === "Enter") {
            applyFilter();
        }
    });

    // Опрос статуса сбора каждые 3 секунды
    pollTimer = setInterval(pollCollectorStatus, 3000);
});

async function loadStats() {
    try {
        const resp = await fetch("/api/stats");
        const data = await resp.json();

        document.getElementById("metric-total").textContent = data.total_contacts.toLocaleString();
        document.getElementById("metric-domains").textContent = data.unique_domains.toLocaleString();

        // Обновляем статус сборщика
        updateCollectorStatusUI(data.collection_state);

        // Топ организаций
        const orgsContainer = document.getElementById("topOrgsList");
        if (data.top_orgs && data.top_orgs.length > 0) {
            orgsContainer.innerHTML = data.top_orgs.map(o => `
                <div class="d-flex justify-content-between align-items-center small p-2 rounded bg-light">
                    <span class="text-truncate fw-medium" style="max-width: 180px;" title="${o.name}">${o.name}</span>
                    <span class="badge bg-primary-subtle text-primary fw-bold">${o.count}</span>
                </div>
            `).join("");
        } else {
            orgsContainer.innerHTML = `<div class="text-muted small">Нет данных</div>`;
        }

        // Топ доменов
        const domainsContainer = document.getElementById("topDomainsList");
        if (data.top_domains && data.top_domains.length > 0) {
            domainsContainer.innerHTML = data.top_domains.map(d => `
                <div class="d-flex justify-content-between align-items-center small p-2 rounded bg-light">
                    <span class="text-truncate text-secondary" style="max-width: 180px;" title="${d.domain}">@${d.domain}</span>
                    <span class="badge bg-secondary-subtle text-secondary fw-bold">${d.count}</span>
                </div>
            `).join("");
        } else {
            domainsContainer.innerHTML = `<div class="text-muted small">Нет данных</div>`;
        }

    } catch (e) {
        console.error("Ошибка загрузки статистики:", e);
    }
}

async function loadContacts() {
    const search = document.getElementById("searchInput").value;
    const category = document.getElementById("categoryFilter").value;
    const offset = (currentPage - 1) * pageSize;

    const url = `/api/contacts?q=${encodeURIComponent(search)}&category=${encodeURIComponent(category)}&limit=${pageSize}&offset=${offset}`;

    try {
        const resp = await fetch(url);
        const data = await resp.json();

        totalRecords = data.total;
        document.getElementById("resultsCount").textContent = `${totalRecords} контактов`;

        const tbody = document.getElementById("contactsTableBody");
        if (!data.contacts || data.contacts.length === 0) {
            tbody.innerHTML = `<tr><td colspan="4" class="text-center py-4 text-muted">Контакты не найдены. Нажмите «Запустить сбор», чтобы наполнить базу.</td></tr>`;
            updatePagination();
            return;
        }

        tbody.innerHTML = data.contacts.map(c => `
            <tr>
                <td>
                    <div class="d-flex align-items-center gap-2">
                        <span class="fw-bold text-dark text-break">${escapeHtml(c.email)}</span>
                        <button class="btn btn-sm btn-light p-1 copy-btn" title="Копировать email" onclick="copyToClipboard('${escapeHtml(c.email)}')">
                            <i class="bi bi-clipboard"></i>
                        </button>
                    </div>
                    <div class="small text-muted text-truncate mt-1" style="max-width: 280px;" title="${escapeHtml(c.author_name || '')}">
                        <i class="bi bi-person"></i> ${escapeHtml(c.author_name || 'Автор')}
                    </div>
                </td>
                <td>
                    <div class="fw-medium text-dark">${escapeHtml(c.organization || 'Университет / Лаборатория')}</div>
                    <div class="small text-muted">@${escapeHtml(c.domain)}</div>
                </td>
                <td>
                    <div class="d-flex align-items-center gap-2 mb-1">
                        <span class="badge bg-info-subtle text-info-emphasis border border-info-subtle badge-cat">${escapeHtml(c.category)}</span>
                        <span class="small text-muted">${escapeHtml(c.published_date || '')}</span>
                    </div>
                    <div class="small fw-semibold text-dark text-truncate" style="max-width: 480px;" title="${escapeHtml(c.paper_title || '')}">
                        ${escapeHtml(c.paper_title || '')}
                    </div>
                </td>
                <td class="text-end">
                    <div class="d-flex justify-content-end gap-1">
                        <a href="${escapeHtml(c.pdf_url)}" target="_blank" class="btn btn-sm btn-outline-danger" title="Открыть PDF публикации">
                            <i class="bi bi-file-pdf"></i>
                        </a>
                        <a href="mailto:${escapeHtml(c.email)}" class="btn btn-sm btn-outline-primary" title="Написать письмо">
                            <i class="bi bi-envelope"></i>
                        </a>
                    </div>
                </td>
            </tr>
        `).join("");

        updatePagination();

    } catch (e) {
        console.error("Ошибка загрузки контактов:", e);
    }
}

function applyFilter() {
    currentPage = 1;
    loadContacts();
}

function prevPage() {
    if (currentPage > 1) {
        currentPage--;
        loadContacts();
    }
}

function nextPage() {
    if (currentPage * pageSize < totalRecords) {
        currentPage++;
        loadContacts();
    }
}

function updatePagination() {
    const totalPages = Math.ceil(totalRecords / pageSize) || 1;
    document.getElementById("pageIndicator").textContent = `Страница ${currentPage} из ${totalPages}`;
    document.getElementById("btnPrev").disabled = (currentPage <= 1);
    document.getElementById("btnNext").disabled = (currentPage >= totalPages);
}

async function startHarvest() {
    const query = document.getElementById("harvestQuery").value;
    const limit = document.getElementById("harvestLimit").value;

    const modalEl = document.getElementById("harvestModal");
    const modal = bootstrap.Modal.getInstance(modalEl);
    if (modal) modal.hide();

    try {
        const resp = await fetch("/api/harvest", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ query: query, limit: parseInt(limit) })
        });
        const data = await resp.json();
        if (data.success) {
            pollCollectorStatus();
        } else {
            alert(data.message);
        }
    } catch (e) {
        alert("Ошибка при запуске сбора: " + e);
    }
}

async function pollCollectorStatus() {
    try {
        const resp = await fetch("/api/stats");
        const data = await resp.json();
        updateCollectorStatusUI(data.collection_state);

        // Если сбор был завершен, обновляем таблицу и метрики
        if (!data.collection_state.is_running) {
            document.getElementById("metric-total").textContent = data.total_contacts.toLocaleString();
            document.getElementById("metric-domains").textContent = data.unique_domains.toLocaleString();
        }
    } catch (e) {
        // Ошибка опроса
    }
}

function updateCollectorStatusUI(state) {
    if (!state) return;
    const statusText = document.getElementById("collector-status");
    const spinner = document.getElementById("status-spinner");

    statusText.textContent = state.last_status;

    if (state.is_running) {
        spinner.classList.remove("d-none");
        statusText.classList.add("text-primary");
    } else {
        spinner.classList.add("d-none");
        statusText.classList.remove("text-primary");
    }
}

function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        alert("Email скопирован в буфер: " + text);
    }).catch(() => {
        prompt("Скопируйте адрес вручную:", text);
    });
}

function escapeHtml(string) {
    const entityMap = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
    };
    return String(string).replace(/[&<>"']/g, s => entityMap[s]);
}
