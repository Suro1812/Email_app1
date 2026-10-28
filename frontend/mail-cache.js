(function () {
  const DB_NAME = "emailRemindersMailCache";
  const DB_VERSION = 2;
  const METADATA_CACHE_MAX_BYTES = 400 * 1024 * 1024;
  const BODY_CACHE_MAX_BYTES = 400 * 1024 * 1024;

  function requestToPromise(request) {
    return new Promise((resolve, reject) => {
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error || new Error("IndexedDB request failed."));
    });
  }

  function openDatabase() {
    if (!("indexedDB" in window)) return Promise.resolve(null);

    return new Promise((resolve, reject) => {
      const request = indexedDB.open(DB_NAME, DB_VERSION);
      request.onupgradeneeded = () => {
        const db = request.result;

        if (!db.objectStoreNames.contains("mailboxPages")) {
          db.createObjectStore("mailboxPages", { keyPath: "key" });
        }

        let messages = null;
        if (!db.objectStoreNames.contains("messages")) {
          messages = db.createObjectStore("messages", { keyPath: "cacheKey" });
        } else {
          messages = request.transaction.objectStore("messages");
        }
        if (messages) {
          if (!messages.indexNames.contains("by_scope")) {
            messages.createIndex("by_scope", ["userEmail", "mailbox", "category", "unreadOnly", "page"]);
          }
          if (!messages.indexNames.contains("by_message")) {
            messages.createIndex("by_message", ["userEmail", "messageId"]);
          }
        }

        if (!db.objectStoreNames.contains("syncState")) {
          db.createObjectStore("syncState", { keyPath: "key" });
        }

        if (!db.objectStoreNames.contains("bodies")) {
          const bodies = db.createObjectStore("bodies", { keyPath: "cacheKey" });
          bodies.createIndex("by_user_message", ["userEmail", "messageId"], { unique: true });
          bodies.createIndex("by_last_accessed", "lastAccessedAt");
        }
      };
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error || new Error("Could not open mail cache."));
    });
  }

  let dbPromise = null;

  async function db() {
    if (!dbPromise) {
      dbPromise = openDatabase().catch(() => null);
    }
    return dbPromise;
  }

  function pageKey({ userEmail, mailbox, category, unreadOnly, page }) {
    return [
      String(userEmail || ""),
      String(mailbox || "inbox"),
      String(category || ""),
      unreadOnly ? "unread" : "all",
      String(page || 1),
    ].join("|");
  }

  function scopeKey({ userEmail, mailbox, category, unreadOnly }) {
    return [
      String(userEmail || ""),
      String(mailbox || "inbox"),
      String(category || ""),
      unreadOnly ? "unread" : "all",
    ].join("|");
  }

  function bodyKey(userEmail, messageId) {
    return `${String(userEmail || "")}|${String(messageId || "")}`;
  }

  function messageKey(message) {
    return String(message?.message_id || message?.id || "");
  }

  function estimateSize(value) {
    try {
      return new Blob([JSON.stringify(value || {})]).size;
    } catch {
      return JSON.stringify(value || {}).length;
    }
  }

  function timestampMs(value) {
    if (value === null || value === undefined || value === "") return 0;
    const raw = String(value);
    const numeric = Number(raw);
    if (Number.isFinite(numeric) && numeric > 0) {
      return raw.length <= 10 ? numeric * 1000 : numeric;
    }
    const parsed = Date.parse(raw);
    return Number.isFinite(parsed) ? parsed : 0;
  }

  function timestampIso(value) {
    const ms = timestampMs(value);
    return ms ? new Date(ms).toISOString() : "";
  }

  function stripAttachmentContent(value) {
    if (Array.isArray(value)) return value.map(stripAttachmentContent);
    if (!value || typeof value !== "object") return value;

    const stripped = {};
    for (const [key, item] of Object.entries(value)) {
      const lowerKey = key.toLowerCase();
      if (
        lowerKey === "data" ||
        lowerKey === "content" ||
        lowerKey === "payload" ||
        lowerKey === "base64" ||
        lowerKey === "bytes"
      ) {
        continue;
      }
      stripped[key] = stripAttachmentContent(item);
    }
    return stripped;
  }

  function cacheableBodyPayload(message) {
    const payload = { ...(message || {}) };
    if (Array.isArray(payload.attachments)) {
      payload.attachments = payload.attachments.map((attachment) => stripAttachmentContent(attachment));
    }
    if (Array.isArray(payload.thread_messages)) {
      payload.thread_messages = payload.thread_messages.map((entry) => {
        const threadEntry = { ...(entry || {}) };
        if (Array.isArray(threadEntry.attachments)) {
          threadEntry.attachments = threadEntry.attachments.map((attachment) => stripAttachmentContent(attachment));
        }
        return threadEntry;
      });
    }
    return payload;
  }

  async function transaction(storeNames, mode, callback) {
    const database = await db();
    if (!database) return null;

    return new Promise((resolve, reject) => {
      const tx = database.transaction(storeNames, mode);
      const stores = Array.isArray(storeNames)
        ? Object.fromEntries(storeNames.map((name) => [name, tx.objectStore(name)]))
        : tx.objectStore(storeNames);
      let callbackResult;
      tx.oncomplete = () => resolve(callbackResult);
      tx.onerror = () => reject(tx.error || new Error("Mail cache transaction failed."));
      tx.onabort = () => reject(tx.error || new Error("Mail cache transaction aborted."));
      callbackResult = callback(stores);
    });
  }

  async function getMailboxPage(scope) {
    const key = pageKey(scope);
    try {
      const database = await db();
      if (!database) return null;
      const tx = database.transaction("mailboxPages", "readonly");
      const row = await requestToPromise(tx.objectStore("mailboxPages").get(key));
      return row?.messages ? row : null;
    } catch {
      return null;
    }
  }

  async function saveMailboxPage(scope, messages, meta = {}) {
    const key = pageKey(scope);
    const now = new Date().toISOString();
    const cleanMessages = Array.isArray(messages) ? messages : [];
    const pagePayload = { messages: cleanMessages, meta };
    const pageSizeBytes = estimateSize(pagePayload);
    try {
      await transaction(["mailboxPages", "messages"], "readwrite", (stores) => {
        stores.mailboxPages.put({
          key,
          ...scope,
          messages: cleanMessages,
          meta,
          sizeBytes: pageSizeBytes,
          cachedAt: now,
          lastSyncedAt: now,
        });

        for (const message of cleanMessages) {
          const id = messageKey(message);
          if (!id) continue;
          const labels = Array.isArray(message.label_ids) ? message.label_ids : [];
          const messagePayloadSize = estimateSize(message);
          stores.messages.put({
            cacheKey: bodyKey(scope.userEmail, id),
            userEmail: scope.userEmail,
            messageId: id,
            threadId: message.thread_id || "",
            mailbox: scope.mailbox || "",
            category: scope.category || "",
            unreadOnly: Boolean(scope.unreadOnly),
            page: Number(scope.page || 1),
            sender: message.from || "",
            recipients: message.to || "",
            subject: message.subject || "",
            snippet: message.snippet || message.summary || "",
            timestamp: message.internal_date || message.date || "",
            labels,
            isRead: !labels.includes("UNREAD"),
            isStarred: labels.includes("STARRED"),
            hasAttachment: Boolean(message.has_attachment),
            attachmentMetadata: Array.isArray(message.attachments)
              ? message.attachments.map((attachment) => stripAttachmentContent(attachment))
              : [],
            bodyCached: Boolean(message.display_html || message.display_text || message.body),
            sizeBytes: messagePayloadSize,
            cachedAt: now,
            updatedAt: now,
            payload: message,
          });
        }
      });
    } catch {
      // Cache writes are best-effort.
    }
  }

  async function getMetadataSyncState(scope) {
    const key = scopeKey(scope);
    try {
      const database = await db();
      if (!database) return null;
      const tx = database.transaction("syncState", "readonly");
      return await requestToPromise(tx.objectStore("syncState").get(key));
    } catch {
      return null;
    }
  }

  async function saveMetadataSyncState(scope, state = {}) {
    const key = scopeKey(scope);
    const now = new Date().toISOString();
    try {
      await transaction("syncState", "readwrite", (store) => {
        store.put({
          key,
          ...scope,
          ...state,
          updatedAt: now,
        });
      });
    } catch {
      // Sync state is best-effort; the next run can restart from the latest page.
    }
  }

  async function getMetadataScopeSummary(scope) {
    try {
      const database = await db();
      if (!database) return null;

      const tx = database.transaction(["mailboxPages", "messages"], "readonly");
      const [pages, messages] = await Promise.all([
        requestToPromise(tx.objectStore("mailboxPages").getAll()),
        requestToPromise(tx.objectStore("messages").getAll()),
      ]);
      const inScope = (row) => (
        row.userEmail === scope.userEmail &&
        row.mailbox === scope.mailbox &&
        String(row.category || "") === String(scope.category || "") &&
        Boolean(row.unreadOnly) === Boolean(scope.unreadOnly)
      );
      const scopedPages = pages.filter(inScope).sort((a, b) => Number(a.page || 1) - Number(b.page || 1));
      const scopedMessages = messages.filter(inScope);
      const firstPage = scopedPages.find((row) => Number(row.page || 1) === 1) || null;
      const lastPage = scopedPages[scopedPages.length - 1] || null;
      const messageDates = scopedMessages
        .map((row) => timestampMs(row.timestamp || row.payload?.internal_date || row.payload?.date))
        .filter(Boolean);
      const metadataBytes = scopedPages.reduce((sum, row) => sum + Number(row.sizeBytes || 0), 0) +
        scopedMessages.reduce((sum, row) => sum + Number(row.sizeBytes || 0), 0);

      return {
        cachedPages: scopedPages.length,
        cachedMessages: scopedMessages.length,
        maxPage: scopedPages.reduce((max, row) => Math.max(max, Number(row.page || 0)), 0),
        firstMessageId: messageKey(firstPage?.messages?.[0]),
        lastPageNextToken: lastPage?.meta?.next_page_token || "",
        oldestDate: messageDates.length ? timestampIso(Math.min(...messageDates)) : "",
        newestDate: messageDates.length ? timestampIso(Math.max(...messageDates)) : "",
        metadataBytes,
        metadataLimitBytes: METADATA_CACHE_MAX_BYTES,
      };
    } catch {
      return null;
    }
  }

  async function evictMetadata(scope, maxBytes = METADATA_CACHE_MAX_BYTES, maxPages = 800) {
    try {
      const database = await db();
      if (!database) return { metadataBytes: 0, deletedPages: 0 };

      const tx = database.transaction(["mailboxPages", "messages"], "readwrite");
      const pagesStore = tx.objectStore("mailboxPages");
      const messagesStore = tx.objectStore("messages");
      const [pages, messages] = await Promise.all([
        requestToPromise(pagesStore.getAll()),
        requestToPromise(messagesStore.getAll()),
      ]);
      const inScope = (row) => (
        row.userEmail === scope.userEmail &&
        row.mailbox === scope.mailbox &&
        String(row.category || "") === String(scope.category || "") &&
        Boolean(row.unreadOnly) === Boolean(scope.unreadOnly)
      );
      const scopedPages = pages.filter(inScope).sort((a, b) => Number(a.page || 1) - Number(b.page || 1));
      const scopedMessages = messages.filter(inScope);
      let totalBytes = scopedPages.reduce((sum, row) => sum + Number(row.sizeBytes || 0), 0) +
        scopedMessages.reduce((sum, row) => sum + Number(row.sizeBytes || 0), 0);
      let deletedPages = 0;

      for (const page of scopedPages.slice().sort((a, b) => Number(b.page || 1) - Number(a.page || 1))) {
        if (totalBytes <= maxBytes && Number(page.page || 1) <= maxPages) break;
        pagesStore.delete(page.key);
        for (const message of scopedMessages.filter((row) => Number(row.page || 1) === Number(page.page || 1))) {
          messagesStore.delete(message.cacheKey);
          totalBytes -= Number(message.sizeBytes || 0);
        }
        totalBytes -= Number(page.sizeBytes || 0);
        deletedPages += 1;
      }

      return { metadataBytes: Math.max(0, totalBytes), deletedPages };
    } catch {
      return { metadataBytes: 0, deletedPages: 0 };
    }
  }

  async function getBody(userEmail, messageId) {
    const key = bodyKey(userEmail, messageId);
    try {
      const database = await db();
      if (!database) return null;
      const tx = database.transaction("bodies", "readwrite");
      const store = tx.objectStore("bodies");
      const row = await requestToPromise(store.get(key));
      if (!row?.payload) return null;
      row.lastAccessedAt = Date.now();
      store.put(row);
      return row.payload;
    } catch {
      return null;
    }
  }

  async function saveBody(userEmail, message) {
    const id = messageKey(message);
    if (!userEmail || !id) return;
    const key = bodyKey(userEmail, id);
    const now = Date.now();
    const payload = cacheableBodyPayload(message);
    const sizeBytes = estimateSize(payload);

    try {
      await transaction(["bodies", "messages"], "readwrite", (stores) => {
        stores.bodies.put({
          cacheKey: key,
          userEmail,
          messageId: id,
          threadId: message.thread_id || "",
          sanitizedHtml: message.display_html || "",
          plainText: message.display_text || message.body || "",
          sizeBytes,
          cachedAt: now,
          lastAccessedAt: now,
          payload,
        });

        const messageRequest = stores.messages.get(key);
        messageRequest.onsuccess = () => {
          const existing = messageRequest.result;
          if (!existing) return;
          existing.bodyCached = true;
          existing.updatedAt = new Date().toISOString();
          stores.messages.put(existing);
        };
      });
      evictBodies(BODY_CACHE_MAX_BYTES);
    } catch {
      // Cache writes are best-effort.
    }
  }

  async function evictBodies(maxBytes = BODY_CACHE_MAX_BYTES) {
    try {
      const database = await db();
      if (!database) return;
      const tx = database.transaction("bodies", "readwrite");
      const store = tx.objectStore("bodies");
      const rows = await requestToPromise(store.getAll());
      const total = rows.reduce((sum, row) => sum + Number(row.sizeBytes || 0), 0);
      if (total <= maxBytes) return;

      let remaining = total;
      for (const row of rows.sort((a, b) => Number(a.lastAccessedAt || 0) - Number(b.lastAccessedAt || 0))) {
        if (remaining <= maxBytes) break;
        store.delete(row.cacheKey);
        remaining -= Number(row.sizeBytes || 0);
      }
    } catch {
      // Eviction is best-effort.
    }
  }

  async function getStats(userEmail = "") {
    try {
      const database = await db();
      if (!database) {
        return { mailboxPages: 0, metadataMessages: 0, metadataBytes: 0, bodies: 0, bodyBytes: 0 };
      }
      const [pages, messages, bodies, syncStates] = await Promise.all(
        ["mailboxPages", "messages", "bodies", "syncState"].map((storeName) => new Promise((resolve, reject) => {
          const tx = database.transaction(storeName, "readonly");
          const request = tx.objectStore(storeName).getAll();
          request.onsuccess = () => resolve(request.result || []);
          request.onerror = () => reject(request.error);
        })),
      );
      const filterUser = (row) => !userEmail || row.userEmail === userEmail;
      const userPages = pages.filter(filterUser);
      const userMessages = messages.filter(filterUser);
      const userBodies = bodies.filter(filterUser);
      const userSyncStates = syncStates.filter(filterUser);
      const latestSyncState = userSyncStates
        .slice()
        .sort((a, b) => timestampMs(b.updatedAt) - timestampMs(a.updatedAt))[0] || {};
      const messageDates = userMessages
        .map((row) => timestampMs(row.timestamp || row.payload?.internal_date || row.payload?.date))
        .filter(Boolean);
      const metadataNewestMs = messageDates.length ? Math.max(...messageDates) : 0;
      const metadataOldestMs = messageDates.length ? Math.min(...messageDates) : 0;
      const metadataMaxCachedPage = userPages.reduce((max, row) => Math.max(max, Number(row.page || 0)), 0);
      return {
        mailboxPages: userPages.length,
        metadataMessages: userMessages.length,
        metadataMaxCachedPage,
        metadataNewestDate: timestampIso(metadataNewestMs),
        metadataOldestDate: timestampIso(metadataOldestMs),
        metadataBytes: userPages.reduce((sum, row) => sum + Number(row.sizeBytes || 0), 0) +
          userMessages.reduce((sum, row) => sum + Number(row.sizeBytes || 0), 0),
        metadataLimitBytes: METADATA_CACHE_MAX_BYTES,
        metadataSyncScopes: userSyncStates.length,
        metadataSyncCompleteScopes: userSyncStates.filter((row) => row.complete).length,
        metadataLastSyncStatus: latestSyncState.status || "",
        metadataLastSyncStopReason: latestSyncState.stopReason || "",
        metadataLastSyncOldestDate: latestSyncState.oldestSyncedDate || "",
        bodies: userBodies.length,
        bodyBytes: userBodies.reduce((sum, row) => sum + Number(row.sizeBytes || 0), 0),
        bodyLimitBytes: BODY_CACHE_MAX_BYTES,
      };
    } catch {
      return { mailboxPages: 0, metadataMessages: 0, metadataBytes: 0, bodies: 0, bodyBytes: 0 };
    }
  }

  async function clearUser(userEmail) {
    try {
      const database = await db();
      if (!database) return;
      for (const storeName of ["mailboxPages", "messages", "bodies", "syncState"]) {
        const tx = database.transaction(storeName, "readwrite");
        const store = tx.objectStore(storeName);
        const rows = await requestToPromise(store.getAll());
        for (const row of rows) {
          if (row.userEmail === userEmail) store.delete(row.key || row.cacheKey);
        }
      }
    } catch {
      // Clearing cache is best-effort.
    }
  }

  window.MailCacheRepository = {
    getMailboxPage,
    saveMailboxPage,
    getBody,
    saveBody,
    evictBodies,
    getMetadataSyncState,
    saveMetadataSyncState,
    getMetadataScopeSummary,
    evictMetadata,
    getStats,
    clearUser,
  };
})();
