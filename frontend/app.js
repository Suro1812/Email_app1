const healthDot = document.querySelector("#healthDot");
const healthText = document.querySelector("#healthText");
const activityText = document.querySelector("#activityText");
const emailInput = document.querySelector("#emailInput");
const messageList = document.querySelector("#messageList");
const messageCount = document.querySelector("#messageCount");
const calendarList = document.querySelector("#calendarList");
const calendarCount = document.querySelector("#calendarCount");
const toastContainer = document.querySelector("#toastContainer");
const selectedSubject = document.querySelector("#selectedSubject");
const selectedFrom = document.querySelector("#selectedFrom");
const selectedStatus = document.querySelector("#selectedStatus");
const selectedAvatar = document.querySelector("#selectedAvatar");
const selectedTime = document.querySelector("#selectedTime");
const selectedRecipientToggle = document.querySelector("#selectedRecipientToggle");
const selectedRecipientDetails = document.querySelector("#selectedRecipientDetails");
const selectedDetailFrom = document.querySelector("#selectedDetailFrom");
const selectedDetailTo = document.querySelector("#selectedDetailTo");
const selectedDetailDate = document.querySelector("#selectedDetailDate");
const selectedDetailCcRow = document.querySelector("#selectedDetailCcRow");
const selectedDetailCc = document.querySelector("#selectedDetailCc");
const selectedDetailBccRow = document.querySelector("#selectedDetailBccRow");
const selectedDetailBcc = document.querySelector("#selectedDetailBcc");
const selectedSummary = document.querySelector("#selectedSummary");
const selectedMessageFrame = document.querySelector("#selectedMessageFrame");
const selectedMessagePlain = document.querySelector("#selectedMessagePlain");
const selectedMessageId = document.querySelector("#selectedMessageId");
const selectedCalendarInviteActions = document.querySelector("#selectedCalendarInviteActions");
const messageModal = document.querySelector("#messageModal");
const summaryButton = document.querySelector("#summaryButton");
const summaryResult = document.querySelector("#summaryResult");
const generatedSummary = document.querySelector("#generatedSummary");
const replyModeButton = document.querySelector("#replyModeButton");
const replyIconButton = document.querySelector("#replyIconButton");
const forwardIconButton = document.querySelector("#forwardIconButton");
const replyComposer = document.querySelector("#replyComposer");
const replyTo = document.querySelector("#replyTo");
const replyCc = document.querySelector("#replyCc");
const replyBcc = document.querySelector("#replyBcc");
const replyCcRow = document.querySelector("#replyCcRow");
const replyBccRow = document.querySelector("#replyBccRow");
const replyIntent = document.querySelector("#replyIntent");
const replyIntentEditor = document.querySelector("#replyIntentEditor");
const generatedReply = document.querySelector("#generatedReply");
const generatedReplyEditor = document.querySelector("#generatedReplyEditor");
const replyAttachments = document.querySelector("#replyAttachments");
const replyAttachmentList = document.querySelector("#replyAttachmentList");
const composeButton = document.querySelector("#composeButton");
const composeModal = document.querySelector("#composeModal");
const composeTo = document.querySelector("#composeTo");
const composeCc = document.querySelector("#composeCc");
const composeBcc = document.querySelector("#composeBcc");
const composeCcRow = document.querySelector("#composeCcRow");
const composeBccRow = document.querySelector("#composeBccRow");
const composeSubject = document.querySelector("#composeSubject");
const composeReplyIntentSection = document.querySelector("#composeReplyIntentSection");
const composeReplyIntent = document.querySelector("#composeReplyIntent");
const composeOriginalPreview = document.querySelector("#composeOriginalPreview");
const composeOriginalTitle = document.querySelector("#composeOriginalTitle");
const composeOriginalFrame = document.querySelector("#composeOriginalFrame");
const writerFormatButton = document.querySelector("#writerFormatButton");
const writerFormatMenu = document.querySelector("#writerFormatMenu");
const writerInstruction = document.querySelector("#writerInstruction");
const writerInstructionEditor = document.querySelector("#writerInstructionEditor");
const generatedWriterDraft = document.querySelector("#generatedWriterDraft");
const sendWriterButton = document.querySelector("#sendWriterButton");
const writerButton = document.querySelector("#writerButton");
const writerAttachments = document.querySelector("#writerAttachments");
const writerAttachmentList = document.querySelector("#writerAttachmentList");
const loginButton = document.querySelector("#loginButton");
const loginScreen = document.querySelector("#loginScreen");
const loginScreenButton = document.querySelector("#loginScreenButton");
const loginStatus = document.querySelector("#loginStatus");
const appShell = document.querySelector("#appShell");
const mailboxTitle = document.querySelector("#mailboxTitle");
const mailboxEyebrow = document.querySelector("#mailboxEyebrow");
const messagePanelTitle = document.querySelector("#messagePanelTitle");
const mailboxPagination = document.querySelector("#mailboxPagination");
const previousPageButton = document.querySelector("#previousPage");
const nextPageButton = document.querySelector("#nextPage");
const pageNumbers = document.querySelector("#pageNumbers");
const mailboxToolbar = document.querySelector("#mailboxToolbar");
const mailViewFilter = document.querySelector("#mailViewFilter");
const mailSearchInput = document.querySelector("#mailSearchInput");
const mailSearchButton = document.querySelector("#mailSearchButton");
const clearMailSearchButton = document.querySelector("#clearMailSearch");
const mailboxView = document.querySelector("#mailboxView");
const inboxTabs = document.querySelector("#inboxTabs");
const calendarView = document.querySelector("#calendarView");
const calendarViewTitle = document.querySelector("#calendarViewTitle");
const calendarBoard = document.querySelector("#calendarBoard");
const openCalendarViewButton = document.querySelector("#openCalendarView");
const upcomingEventsPanel = document.querySelector("#upcomingEventsPanel");
const openUpcomingEventsButton = document.querySelector("#openUpcomingEvents");
const closeUpcomingEventsButton = document.querySelector("#closeUpcomingEvents");
const upcomingRailCount = document.querySelector("#upcomingRailCount");
const emojiMenu = document.querySelector("#emojiMenu");
const signatureMenu = document.querySelector("#signatureMenu");
const signatureModal = document.querySelector("#signatureModal");
const closeSignatureModalButton = document.querySelector("#closeSignatureModal");
const signatureEditor = document.querySelector("#signatureEditor");
const signatureValue = document.querySelector("#signatureValue");
const saveSignatureButton = document.querySelector("#saveSignatureButton");
const insertManagedSignatureButton = document.querySelector("#insertManagedSignatureButton");

const SIGNATURE_STORAGE_KEY = "emailReminders.signatureHtml";
const DEFAULT_SIGNATURE_HTML = "<p>Best regards,<br>Surojit Dutta</p>";

const state = {
  email: localStorage.getItem("emailReminders.email") || "",
  messages: [],
  selected: null,
  isLoadingMessages: false,
  isPreloadingMailboxes: false,
  isMailboxLoading: false,
  isLoadingPage: false,
  isInitialMailboxSync: false,
  loadRequestId: 0,
  messageError: "",
  activeMailbox: localStorage.getItem("emailReminders.mailbox") || "inbox",
  activeMailboxTitle: "Inbox",
  activeInboxCategory: localStorage.getItem("emailReminders.inboxCategory") || "primary",
  activeView: localStorage.getItem("emailReminders.view") || "mailbox",
  calendarMode: localStorage.getItem("emailReminders.calendarMode") || "week",
  unreadOnly: localStorage.getItem("emailReminders.mailView") === "unread",
  mailboxPagination: {},
  fullMessages: {},
  fullMessageRequests: new Map(),
  mailboxPagePrefetchRequests: new Set(),
  metadataBackfillRequests: new Set(),
  metadataBackfillTimers: new Map(),
  emailFrameRenderId: 0,
  restoreEmailFrameOnFocus: false,
  calendarEvents: [],
  pendingResponses: [],
  shownEventNotifications: new Set(),
  analysisEnqueued: new Set(),
  isConnected: false,
  authError: "",
  activeEditorId: "",
  composeMode: "compose",
  composeReplyMessageId: "",
  composeOriginalHtml: "",
  composeOriginalPlainText: "",
  isSearchActive: false,
  searchQuery: "",
  preSearchMailbox: "",
  preSearchMailboxTitle: "",
};

const quillEditors = new Map();

window.openEmailReminderMessage = async (messageId) => {
  const message = state.messages.find((entry) => String(entry.message_id) === String(messageId));
  if (message) {
    selectMessage(message);
    return;
  }
  const cached = cachedFullMessage(messageId);
  if (cached) {
    selectMessage(cached);
    return;
  }
  try {
    const fullMessage = await fetchFullMessage(messageId, { timeoutMs: 30000 });
    if (fullMessage) selectMessage(fullMessage);
  } catch (error) {
    setActivity(error.message);
  }
};

const MESSAGE_REFRESH_INTERVAL_MS = 10000;
const MAILBOX_PAGE_SIZE = 25;
const MAILBOX_PRELOAD_INTERVAL_MS = 60000;
const EVENT_NOTIFICATION_INTERVAL_MS = 30000;
const REQUEST_TIMEOUT_MS = 15000;
const FULL_MESSAGE_PREFETCH_LIMIT = 8;
const FULL_MESSAGE_PREFETCH_CONCURRENCY = 2;
const MAILBOX_PAGE_BODY_SYNC_LIMIT = MAILBOX_PAGE_SIZE;
const BACKGROUND_GMAIL_DELAY_MS = 2500;
const METADATA_PREFETCH_DELAY_MS = 600;
const BODY_SYNC_DELAY_MS = 0;
const METADATA_BACKFILL_DELAY_MS = 1200;
const METADATA_BACKFILL_PAGE_DELAY_MS = 350;
const METADATA_BACKFILL_MAX_PAGES = 800;
const METADATA_BACKFILL_REFRESH_PAGES = 3;
const METADATA_BACKFILL_MAX_MESSAGES = 20000;
const INBOX_CATEGORIES = new Set(["primary", "promotions", "social", "updates"]);
const INBOX_CATEGORY_TITLES = {
  primary: "Primary",
  promotions: "Promotions",
  social: "Social",
  updates: "Updates",
};

function mailCache() {
  return window.MailCacheRepository || null;
}

window.emailRemindersCacheStats = async () => {
  const cache = mailCache();
  const stats = cache ? await cache.getStats(state.email) : null;
  console.table(stats ? [stats] : [{ mailboxPages: 0, metadataMessages: 0, bodies: 0, bodyBytes: 0 }]);
  return stats;
};

function normalizedInboxCategory(category = state.activeInboxCategory) {
  const value = String(category || "primary").toLowerCase();
  return INBOX_CATEGORIES.has(value) ? value : "primary";
}

function messageScopeKey(mailbox = state.activeMailbox, category = state.activeInboxCategory) {
  const mailboxKey = String(mailbox || "inbox").toLowerCase();
  return mailboxKey === "inbox" ? `${mailboxKey}.${normalizedInboxCategory(category)}` : mailboxKey;
}

function mailboxDisplayTitle(mailbox = state.activeMailbox, title = state.activeMailboxTitle, category = state.activeInboxCategory) {
  if (String(mailbox || "").toLowerCase() !== "inbox") return title || titleForMailbox(mailbox);
  return `${INBOX_CATEGORY_TITLES[normalizedInboxCategory(category)] || "Primary"} inbox`;
}

function cacheKey(
  email,
  mailbox = state.activeMailbox,
  unreadOnly = state.unreadOnly,
  category = state.activeInboxCategory,
) {
  return `emailReminders.messages.${email}.${messageScopeKey(mailbox, category)}.${unreadOnly ? "unread" : "all"}`;
}

function calendarCacheKey(email) {
  return `emailReminders.calendarEvents.${email}`;
}

function readCachedMessages(email, mailbox = state.activeMailbox, unreadOnly = state.unreadOnly, category = state.activeInboxCategory) {
  if (!email) return [];
  try {
    const cached = sessionStorage.getItem(cacheKey(email, mailbox, unreadOnly, category));
    return cached ? JSON.parse(cached) : [];
  } catch {
    return [];
  }
}

function writeCachedMessages(
  email,
  messages,
  mailbox = state.activeMailbox,
  unreadOnly = state.unreadOnly,
  category = state.activeInboxCategory,
) {
  if (!email) return;
  try {
    sessionStorage.setItem(cacheKey(email, mailbox, unreadOnly, category), JSON.stringify(messages || []));
  } catch {
    setActivity("Messages loaded, but browser session cache is full.");
  }
}

function mailboxCacheScope(
  email = state.email,
  mailbox = state.activeMailbox,
  unreadOnly = state.unreadOnly,
  category = state.activeInboxCategory,
  page = paginationState(mailbox, category).currentPage || 1,
) {
  return {
    userEmail: email,
    mailbox,
    category: String(mailbox || "").toLowerCase() === "inbox" ? normalizedInboxCategory(category) : "",
    unreadOnly: Boolean(unreadOnly),
    page: Math.max(1, Number(page || 1)),
  };
}

async function readLocalMailboxPage(email, mailbox, unreadOnly, category, page = 1) {
  const cache = mailCache();
  if (!cache || !email) return [];
  const cachedPage = await cache.getMailboxPage(mailboxCacheScope(email, mailbox, unreadOnly, category, page));
  return Array.isArray(cachedPage?.messages) ? cachedPage.messages : [];
}

async function writeLocalMailboxPage(email, messages, mailbox, unreadOnly, category, page = 1, meta = {}) {
  const cache = mailCache();
  if (!cache || !email) return;
  await cache.saveMailboxPage(mailboxCacheScope(email, mailbox, unreadOnly, category, page), messages || [], meta);
}

function metadataScopeKey(email, mailbox, unreadOnly, category) {
  const scope = mailboxCacheScope(email, mailbox, unreadOnly, category, 1);
  return [
    scope.userEmail,
    scope.mailbox,
    scope.category,
    scope.unreadOnly ? "unread" : "all",
  ].join("|");
}

function metadataBackfillScope(email = state.email, mailbox = state.activeMailbox, unreadOnly = state.unreadOnly, category = state.activeInboxCategory) {
  return mailboxCacheScope(email, mailbox, unreadOnly, category, 1);
}

function waitForBackgroundSlot(delayMs = METADATA_BACKFILL_PAGE_DELAY_MS) {
  return new Promise((resolve) => {
    window.setTimeout(resolve, delayMs);
  });
}

function metadataTimestampMs(message) {
  const raw = message?.internal_date || message?.date || message?.message_date || "";
  if (!raw) return 0;
  const numeric = Number(raw);
  if (Number.isFinite(numeric) && numeric > 0) {
    return String(raw).length <= 10 ? numeric * 1000 : numeric;
  }
  const parsed = Date.parse(String(raw));
  return Number.isFinite(parsed) ? parsed : 0;
}

function formatMetadataCutoffDate(timestampMs) {
  if (!timestampMs) return "";
  return new Date(timestampMs).toLocaleString([], {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function readCachedCalendarEvents(email) {
  if (!email) return [];
  try {
    const cached = localStorage.getItem(calendarCacheKey(email));
    return cached ? JSON.parse(cached) : [];
  } catch {
    return [];
  }
}

function writeCachedCalendarEvents(email, events) {
  if (!email) return;
  try {
    localStorage.setItem(calendarCacheKey(email), JSON.stringify(events || []));
  } catch {
    setActivity("Calendar events loaded, but browser cache is full.");
  }
}

function isModalOpen() {
  return messageModal.classList.contains("is-open");
}

function messageKey(message) {
  return String(message?.message_id || message?.id || "");
}

function rememberFullMessage(fullMessage) {
  if (!fullMessage) return null;
  const key = messageKey(fullMessage);
  if (!key) return null;

  const cached = {
    ...fullMessage,
    message_id: fullMessage.message_id || fullMessage.id || key,
  };
  state.fullMessages[key] = cached;

  const index = state.messages.findIndex((message) => messageKey(message) === key);
  if (index >= 0) {
    state.messages[index] = {
      ...state.messages[index],
      ...cached,
      message_id: state.messages[index].message_id || key,
    };
    writeCachedMessages(state.email, state.messages, state.activeMailbox);
  }

  return cached;
}

function rememberFullMessages(messages) {
  for (const message of messages || []) {
    if (message?.display_html || message?.display_text || message?.body) {
      rememberFullMessage(message);
    }
  }
}

function mergeWithFullMessage(message) {
  const key = messageKey(message);
  if (!key) return message;
  const fullMessage = state.fullMessages[key];
  if (!fullMessage) return message;
  return {
    ...message,
    ...fullMessage,
    message_id: message.message_id || fullMessage.message_id || fullMessage.id || key,
  };
}

function mergeMessageList(messages) {
  return (messages || []).map((message) => mergeWithFullMessage(message));
}

function url(path) {
  return path;
}

function messagesPath(
  mailbox = state.activeMailbox,
  limit = MAILBOX_PAGE_SIZE,
  pageToken = "",
  unreadOnly = state.unreadOnly,
  category = state.activeInboxCategory,
) {
  const params = new URLSearchParams({
    email: state.email,
    mailbox,
    limit: String(limit),
    _: String(Date.now()),
  });
  if (String(mailbox || "").toLowerCase() === "inbox") {
    params.set("category", normalizedInboxCategory(category));
  }
  if (pageToken) params.set("page_token", pageToken);
  if (unreadOnly) params.set("unread_only", "true");
  return `/gmail/messages?${params.toString()}`;
}

function searchMessagesPath(query, limit = MAILBOX_PAGE_SIZE) {
  const params = new URLSearchParams({
    email: state.email,
    mailbox: "search",
    q: query,
    limit: String(limit),
    _: String(Date.now()),
  });
  return `/gmail/messages?${params.toString()}`;
}

function fullMessagePath(messageId, markRead = false, threadId = "") {
  const params = new URLSearchParams({
    email: state.email,
    message_id: messageId,
  });
  if (markRead) params.set("mark_read", "true");
  if (threadId) params.set("thread_id", threadId);
  return `/gmail/message?${params.toString()}`;
}

function calendarEventsPath(limit = 100) {
  const params = new URLSearchParams({
    email: state.email,
    limit: String(limit),
    _: String(Date.now()),
  });
  return `/calendar/events?${params.toString()}`;
}

function dueNotificationsPath(lookaheadMinutes = 0) {
  const params = new URLSearchParams({
    email: state.email,
    lookahead_minutes: String(lookaheadMinutes),
    _: String(Date.now()),
  });
  return `/notifications/events/due?${params.toString()}`;
}

function setActivity(message) {
  activityText.textContent = message;
  if (loginStatus) loginStatus.textContent = message;
}

function renderAuthState() {
  if (!loginScreen || !appShell) return;
  loginScreen.hidden = state.isConnected;
  appShell.hidden = !state.isConnected;
}

function setConnectionState(connected) {
  state.isConnected = Boolean(connected);
  loginButton.textContent = connected ? "Sign out" : "Connect";
  loginButton.dataset.action = connected ? "logout" : "login";
  loginButton.classList.toggle("connected", connected);
  renderAuthState();
}

function setActiveMailbox(mailbox, title, switchView = true) {
  if (switchView) setActiveView("mailbox");
  state.activeMailbox = mailbox;
  state.activeMailboxTitle = title || titleForMailbox(mailbox);
  localStorage.setItem("emailReminders.mailbox", state.activeMailbox);
  clearInactiveMailboxCounts(state.activeMailbox);
  if (state.activeView !== "calendar") {
    mailboxTitle.textContent = state.activeMailboxTitle;
    mailboxEyebrow.textContent = "AI Mail";
  }
  renderInboxTabs();
  const categoryTitle = state.activeMailbox === "inbox" ? mailboxDisplayTitle() : "";
  messagePanelTitle.textContent = categoryTitle
    ? `${categoryTitle} messages`
    : `${state.activeMailboxTitle} messages`;

  document.querySelectorAll(".mailbox-link").forEach((item) => {
    item.classList.toggle("active", item.dataset.mailbox === state.activeMailbox && state.activeView === "mailbox");
  });
}

function renderInboxTabs() {
  if (!inboxTabs) return;
  const isInbox = state.activeMailbox === "inbox" && state.activeView !== "calendar";
  inboxTabs.hidden = !isInbox;
  if (!isInbox) return;
  const activeCategory = normalizedInboxCategory();
  inboxTabs.querySelectorAll("[data-inbox-category]").forEach((button) => {
    const isActive = button.dataset.inboxCategory === activeCategory;
    button.classList.toggle("active", isActive);
    button.setAttribute("aria-selected", isActive ? "true" : "false");
  });
}

function setMailViewFilter(view) {
  const unreadOnly = String(view || "all").toLowerCase() === "unread";
  state.unreadOnly = unreadOnly;
  localStorage.setItem("emailReminders.mailView", unreadOnly ? "unread" : "all");
  if (mailViewFilter) mailViewFilter.value = unreadOnly ? "unread" : "all";
}

function titleForMailbox(mailbox) {
  const link = document.querySelector(`.mailbox-link[data-mailbox="${CSS.escape(mailbox)}"] span:nth-child(2)`);
  return link?.textContent?.trim() || "Inbox";
}

function setMailboxCount(mailbox, count) {
  const countElement = document.querySelector(`[data-count-for="${CSS.escape(mailbox)}"]`);
  if (!countElement) return;
  if (mailbox !== "calendar") return;
  countElement.textContent = Number.isFinite(Number(count)) ? Number(count).toLocaleString() : "";
}

function setMailboxUnreadIndicator(mailbox, hasUnread) {
  if (mailbox === "calendar") return;
  const countElement = document.querySelector(`[data-count-for="${CSS.escape(mailbox)}"]`);
  if (!countElement) return;
  countElement.textContent = hasUnread ? "•" : "";
  countElement.classList.toggle("unread-marker", Boolean(hasUnread));
  countElement.title = hasUnread ? "Unread messages" : "";
}

function clearInactiveMailboxCounts(activeMailbox = state.activeMailbox) {
  for (const mailbox of mailboxKeys()) {
    if (mailbox === activeMailbox) continue;
    const countElement = document.querySelector(`[data-count-for="${CSS.escape(mailbox)}"]`);
    if (countElement && !countElement.classList.contains("unread-marker")) {
      countElement.textContent = "";
    }
  }
}

function paginationState(mailbox = state.activeMailbox, category = state.activeInboxCategory) {
  const key = `${messageScopeKey(mailbox, category)}.${state.unreadOnly ? "unread" : "all"}`;
  if (!state.mailboxPagination[key]) {
    state.mailboxPagination[key] = {
      currentPage: 1,
      pageTokens: [""],
      hasMore: false,
      totalEstimate: 0,
    };
  }
  return state.mailboxPagination[key];
}

function resetPagination(mailbox = state.activeMailbox, category = state.activeInboxCategory) {
  const key = `${messageScopeKey(mailbox, category)}.${state.unreadOnly ? "unread" : "all"}`;
  state.mailboxPagination[key] = {
    currentPage: 1,
    pageTokens: [""],
    hasMore: false,
    totalEstimate: 0,
  };
  return state.mailboxPagination[key];
}

function pageStartToken(mailbox = state.activeMailbox, page = 1, category = state.activeInboxCategory) {
  const pagination = paginationState(mailbox, category);
  return pagination.pageTokens[Math.max(0, Number(page || 1) - 1)] || "";
}

function setPageResult(mailbox, page, nextToken, totalEstimate, category = state.activeInboxCategory) {
  const pagination = paginationState(mailbox, category);
  const pageNumber = Math.max(1, Number(page || 1));
  const cleanToken = String(nextToken || "").trim();
  pagination.currentPage = pageNumber;
  pagination.hasMore = Boolean(cleanToken);
  pagination.totalEstimate = Number.isFinite(Number(totalEstimate)) ? Number(totalEstimate) : pagination.totalEstimate;
  if (cleanToken) {
    pagination.pageTokens[pageNumber] = cleanToken;
  } else {
    pagination.pageTokens = pagination.pageTokens.slice(0, pageNumber);
  }
}

function canLoadMailboxPage(mailbox = state.activeMailbox, page = 1, category = state.activeInboxCategory) {
  const pageNumber = Math.max(1, Number(page || 1));
  if (pageNumber === 1) return true;
  return Boolean(pageStartToken(mailbox, pageNumber, category));
}

function knownPageNumbers(mailbox = state.activeMailbox, category = state.activeInboxCategory) {
  const pagination = paginationState(mailbox, category);
  const knownCount = pagination.pageTokens.length;
  const pages = new Set([1, pagination.currentPage]);
  for (let page = 1; page <= knownCount; page += 1) pages.add(page);
  if (pagination.hasMore) pages.add(pagination.currentPage + 1);
  return Array.from(pages)
    .filter((page) => page >= 1 && canLoadMailboxPage(mailbox, page, category))
    .sort((left, right) => left - right);
}

function updatePaginationControls() {
  if (!mailboxPagination || !previousPageButton || !nextPageButton || !pageNumbers) return;
  const pagination = paginationState();
  const hasMessages = Boolean(state.messages.length);
  const hidden = state.isMailboxLoading || Boolean(state.messageError) || (!hasMessages && !pagination.hasMore);
  mailboxPagination.hidden = hidden;
  if (hidden) return;

  const currentPage = pagination.currentPage;
  previousPageButton.disabled = state.isLoadingPage || currentPage <= 1;
  nextPageButton.disabled = state.isLoadingPage || !pagination.hasMore;
  nextPageButton.textContent = state.isLoadingPage ? "Loading..." : "Next";

  pageNumbers.innerHTML = "";
  for (const page of knownPageNumbers()) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "page-number";
    button.textContent = String(page);
    button.dataset.page = String(page);
    button.disabled = state.isLoadingPage || page === currentPage;
    button.classList.toggle("active", page === currentPage);
    pageNumbers.appendChild(button);
  }
}

function mailboxButtons() {
  return Array.from(document.querySelectorAll(".mailbox-link[data-mailbox]"));
}

function mailboxKeys() {
  return mailboxButtons().map((item) => item.dataset.mailbox).filter(Boolean);
}

function setActiveView(view) {
  state.activeView = view === "calendar" ? "calendar" : "mailbox";
  localStorage.setItem("emailReminders.view", state.activeView);
  const isCalendar = state.activeView === "calendar";
  if (mailboxToolbar) mailboxToolbar.hidden = isCalendar;
  if (mailboxView) mailboxView.hidden = isCalendar;
  if (calendarView) calendarView.hidden = !isCalendar;
  document.querySelectorAll(".mailbox-link").forEach((item) => {
    item.classList.toggle(
      "active",
      isCalendar ? item.dataset.view === "calendar" : item.dataset.mailbox === state.activeMailbox,
    );
  });
  if (isCalendar) {
    mailboxEyebrow.textContent = "Calendar";
    mailboxTitle.textContent = "Calendar";
    renderCalendarBoard();
  } else {
    mailboxEyebrow.textContent = "AI Mail";
    mailboxTitle.textContent = state.activeMailboxTitle;
  }
  renderInboxTabs();
}

function resetSelectedMessage() {
  state.selected = null;
  selectedSubject.textContent = "Choose a message";
  selectedFrom.textContent = "-";
  selectedStatus.textContent = "-";
  if (selectedAvatar) selectedAvatar.textContent = "?";
  if (selectedTime) selectedTime.textContent = "-";
  if (selectedRecipientDetails) selectedRecipientDetails.hidden = true;
  updateSelectedRecipientDetails(null);
  selectedSummary.value = "";
  renderSelectedMessageBody(null, "Select a Gmail message to view its body.");
  selectedMessageId.value = "";
  renderMarkdownSummary("");
  setRichEditorValue(generatedReplyEditor, generatedReply, "");
  setRichEditorValue(replyIntentEditor, replyIntent, "");
  if (replyTo) replyTo.value = "";
  if (replyCc) replyCc.value = "";
  if (replyBcc) replyBcc.value = "";
  if (replyCcRow) replyCcRow.hidden = true;
  if (replyBccRow) replyBccRow.hidden = true;
  clearAttachments(replyAttachments, replyAttachmentList);
  summaryResult.hidden = true;
  replyComposer.hidden = true;
  closeMessageModal();
}

function setBusy(button, busy, label = "Working...") {
  if (!button) return;
  button.disabled = busy;
  button.dataset.originalText ||= button.textContent;
  button.textContent = busy ? label : button.dataset.originalText;
}

async function requestJson(path, options = {}) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), options.timeoutMs || REQUEST_TIMEOUT_MS);
  const response = await fetch(url(path), {
    cache: "no-store",
    signal: controller.signal,
    headers: {
      "Content-Type": "application/json",
      "Cache-Control": "no-cache",
      ...(options.headers || {}),
    },
    ...options,
  }).catch((error) => {
    if (error.name === "AbortError") {
      throw new Error(options.timeoutMessage || "Gmail request timed out. Try this mailbox again.");
    }
    throw error;
  }).finally(() => clearTimeout(timeoutId));

  const text = await response.text();
  let body = {};
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = { raw: text };
    }
  }

  if (!response.ok) {
    const detail = body.detail || body.raw || `Request failed with ${response.status}`;
    throw new Error(detail);
  }

  return body;
}

function cachedFullMessage(messageId) {
  const key = String(messageId || "");
  return key ? state.fullMessages[key] : null;
}

function hasUsefulFullMessage(messageId) {
  const fullMessage = cachedFullMessage(messageId);
  return Boolean(fullMessage?.display_html || fullMessage?.display_text || fullMessage?.body);
}

async function fetchFullMessage(messageId, options = {}) {
  const key = String(messageId || "");
  if (!key || !state.email) return null;

  const cached = cachedFullMessage(key);
  if (cached && hasUsefulFullMessage(key) && !options.markRead) return cached;

  const bodyCache = mailCache();
  const localBody = bodyCache ? await bodyCache.getBody(state.email, key) : null;
  if (localBody && (localBody.display_html || localBody.display_text || localBody.body)) {
    return rememberFullMessage(localBody);
  }

  if (state.fullMessageRequests.has(key)) {
    return state.fullMessageRequests.get(key);
  }

  const threadId = options.threadId || cached?.thread_id || state.messages.find((message) => messageKey(message) === key)?.thread_id || "";
  const request = requestJson(fullMessagePath(key, Boolean(options.markRead), threadId), {
    method: "GET",
    headers: {},
    timeoutMs: options.timeoutMs || 30000,
  })
    .then(async (data) => {
      const fullMessage = rememberFullMessage(data.message);
      if (fullMessage) {
        const fullBodyCache = mailCache();
        if (fullBodyCache) await fullBodyCache.saveBody(state.email, fullMessage);
      }
      return fullMessage;
    })
    .finally(() => {
      state.fullMessageRequests.delete(key);
    });

  state.fullMessageRequests.set(key, request);
  return request;
}

async function preloadFullMessages(messages = state.messages, limit = FULL_MESSAGE_PREFETCH_LIMIT) {
  if (!state.email || !state.isConnected || document.hidden || state.isLoadingMessages || state.isLoadingPage || state.isMailboxLoading) return;

  const candidates = [];
  const seen = new Set();
  for (const message of messages || []) {
    const key = messageKey(message);
    if (!key || seen.has(key) || hasUsefulFullMessage(key)) continue;
    seen.add(key);
    candidates.push(key);
    if (candidates.length >= limit) break;
  }
  if (!candidates.length) return;

  for (let index = 0; index < candidates.length; index += FULL_MESSAGE_PREFETCH_CONCURRENCY) {
    const batch = candidates.slice(index, index + FULL_MESSAGE_PREFETCH_CONCURRENCY);
    await Promise.allSettled(
      batch.map((messageId) => fetchFullMessage(messageId, { timeoutMs: 30000 })),
    );
  }
}

function syncVisiblePageBodies(messages = state.messages, limit = MAILBOX_PAGE_BODY_SYNC_LIMIT, onComplete = null) {
  deferMailboxBackgroundWork(() => {
    preloadFullMessages(messages, limit)
      .catch(() => {
        // Body cache sync is best-effort; opening the message can still fetch on demand.
      })
      .finally(() => {
        if (typeof onComplete === "function") onComplete();
      });
  }, BODY_SYNC_DELAY_MS);
}

function deferMailboxBackgroundWork(callback, delayMs = BACKGROUND_GMAIL_DELAY_MS) {
  window.setTimeout(() => {
    if (document.hidden || state.isLoadingMessages || state.isLoadingPage || state.isMailboxLoading) return;
    callback();
  }, delayMs);
}

function prefetchNextMailboxMetadata(mailbox, category, page) {
  deferMailboxBackgroundWork(async () => {
    if (!state.email || !state.isConnected || document.hidden) return;

    const nextPage = Math.max(1, Number(page || 1)) + 1;
    const cleanCategory = normalizedInboxCategory(category);
    if (!canLoadMailboxPage(mailbox, nextPage, cleanCategory)) return;

    const cached = await readLocalMailboxPage(state.email, mailbox, state.unreadOnly, cleanCategory, nextPage);
    if (cached.length) return;

    const requestKey = [
      state.email,
      mailbox,
      cleanCategory,
      state.unreadOnly ? "unread" : "all",
      nextPage,
    ].join("|");
    if (state.mailboxPagePrefetchRequests.has(requestKey)) return;
    state.mailboxPagePrefetchRequests.add(requestKey);

    try {
      const pageToken = pageStartToken(mailbox, nextPage, cleanCategory);
      const data = await requestJson(messagesPath(mailbox, MAILBOX_PAGE_SIZE, pageToken, state.unreadOnly, cleanCategory), {
        timeoutMs: 30000,
      });
      await writeLocalMailboxPage(
        state.email,
        data.messages || [],
        mailbox,
        state.unreadOnly,
        cleanCategory,
        nextPage,
        {
          result_size_estimate: data.result_size_estimate,
          next_page_token: data.next_page_token,
        },
      );
      if (mailbox === state.activeMailbox && cleanCategory === normalizedInboxCategory()) {
        const currentPage = paginationState(mailbox, cleanCategory).currentPage;
        setPageResult(mailbox, nextPage, data.next_page_token, data.result_size_estimate, cleanCategory);
        paginationState(mailbox, cleanCategory).currentPage = currentPage;
        updatePaginationControls();
      }
    } catch {
      // Metadata prefetch is best-effort; explicit page load can retry.
    } finally {
      state.mailboxPagePrefetchRequests.delete(requestKey);
    }
  }, METADATA_PREFETCH_DELAY_MS);
}

function scheduleMailboxMetadataBackfill(
  mailbox = state.activeMailbox,
  category = state.activeInboxCategory,
  unreadOnly = state.unreadOnly,
  delayMs = METADATA_BACKFILL_DELAY_MS,
) {
  if (!state.email || !state.isConnected) return;
  const cleanCategory = normalizedInboxCategory(category);
  const requestKey = metadataScopeKey(state.email, mailbox, unreadOnly, cleanCategory);
  if (state.metadataBackfillRequests.has(requestKey)) return;
  const existingTimer = state.metadataBackfillTimers.get(requestKey);
  if (existingTimer) window.clearTimeout(existingTimer);
  const timerId = window.setTimeout(() => {
    state.metadataBackfillTimers.delete(requestKey);
    backfillMailboxMetadata(mailbox, cleanCategory, unreadOnly).catch(() => {
      // Local metadata backfill is best-effort; explicit page loads still work.
    });
  }, delayMs);
  state.metadataBackfillTimers.set(requestKey, timerId);
}

async function backfillMailboxMetadata(mailbox = state.activeMailbox, category = state.activeInboxCategory, unreadOnly = state.unreadOnly) {
  const cache = mailCache();
  if (!cache || !state.email || !state.isConnected || document.hidden) return;

  const cleanCategory = normalizedInboxCategory(category);
  const scope = metadataBackfillScope(state.email, mailbox, unreadOnly, cleanCategory);
  const requestKey = metadataScopeKey(state.email, mailbox, unreadOnly, cleanCategory);
  if (state.metadataBackfillRequests.has(requestKey)) return;

  state.metadataBackfillRequests.add(requestKey);
  try {
    const previousState = await cache.getMetadataSyncState?.(scope);
    const wasComplete = Boolean(previousState?.complete && previousState?.stopReason !== "paused");
    const initialSummary = await cache.getMetadataScopeSummary?.(scope);
    const maxPages = wasComplete ? METADATA_BACKFILL_REFRESH_PAGES : METADATA_BACKFILL_MAX_PAGES;
    let page = 1;
    let pageToken = "";
    let syncedMessages = 0;
    let nextToken = "";
    let oldestSyncedMs = 0;
    let stopReason = "";
    const startedAt = new Date().toISOString();

    await cache.saveMetadataSyncState?.(scope, {
      complete: false,
      status: wasComplete ? "refreshing_latest" : "backfilling",
      startedAt,
      syncedPages: Number(previousState?.syncedPages || 0),
      syncedMessages: Number(previousState?.syncedMessages || 0),
    });

    while (
      page <= maxPages &&
      syncedMessages < METADATA_BACKFILL_MAX_MESSAGES &&
      state.email === scope.userEmail &&
      state.isConnected &&
      !document.hidden
    ) {
      while ((state.isLoadingMessages || state.isLoadingPage || state.isMailboxLoading) && !document.hidden) {
        await waitForBackgroundSlot(700);
      }
      if (document.hidden || !state.isConnected || state.email !== scope.userEmail) break;

      let data = null;
      try {
        data = await requestJson(messagesPath(mailbox, MAILBOX_PAGE_SIZE, pageToken, unreadOnly, cleanCategory), {
          timeoutMs: 30000,
        });
      } catch {
        stopReason = "paused";
        break;
      }
      const messages = data.messages || [];
      nextToken = data.next_page_token || "";
      const pageDates = messages.map(metadataTimestampMs).filter(Boolean);
      if (pageDates.length) {
        const pageOldest = Math.min(...pageDates);
        oldestSyncedMs = oldestSyncedMs ? Math.min(oldestSyncedMs, pageOldest) : pageOldest;
      }
      await writeLocalMailboxPage(
        scope.userEmail,
        messages,
        mailbox,
        unreadOnly,
        cleanCategory,
        page,
        {
          result_size_estimate: data.result_size_estimate,
          next_page_token: nextToken,
          synced_by: "metadata_backfill",
        },
      );

      syncedMessages += messages.length;
      if (
        state.email === scope.userEmail &&
        mailbox === state.activeMailbox &&
        cleanCategory === normalizedInboxCategory() &&
        Boolean(unreadOnly) === Boolean(state.unreadOnly)
      ) {
        const pagination = paginationState(mailbox, cleanCategory);
        const currentPage = pagination.currentPage;
        setPageResult(mailbox, page, nextToken, data.result_size_estimate, cleanCategory);
        paginationState(mailbox, cleanCategory).currentPage = currentPage;
        updatePaginationControls();
      }

      await cache.saveMetadataSyncState?.(scope, {
        complete: false,
        status: wasComplete ? "refreshing_latest" : "backfilling",
        syncedPages: wasComplete
          ? Math.max(Number(previousState?.syncedPages || 0), page)
          : page,
        syncedMessages: wasComplete
          ? Math.max(Number(previousState?.syncedMessages || 0), syncedMessages)
          : syncedMessages,
        oldestSyncedDate: formatMetadataCutoffDate(oldestSyncedMs) || previousState?.oldestSyncedDate || "",
        nextPageToken: nextToken,
      });
      await cache.evictMetadata?.(scope, undefined, METADATA_BACKFILL_MAX_PAGES);

      const frontStillAligned = page === 1 &&
        !wasComplete &&
        initialSummary?.firstMessageId &&
        messageKey(messages[0]) === initialSummary.firstMessageId &&
        initialSummary.maxPage > 1 &&
        initialSummary.lastPageNextToken &&
        Number(initialSummary.metadataBytes || 0) < Number(initialSummary.metadataLimitBytes || 0);
      if (frontStillAligned) {
        page = Number(initialSummary.maxPage || 1) + 1;
        pageToken = initialSummary.lastPageNextToken;
        syncedMessages = Number(initialSummary.cachedMessages || syncedMessages);
        oldestSyncedMs = initialSummary.oldestDate ? Date.parse(initialSummary.oldestDate) : oldestSyncedMs;
        await cache.saveMetadataSyncState?.(scope, {
          complete: false,
          status: "backfilling_from_oldest_cached_page",
          syncedPages: Number(initialSummary.maxPage || 1),
          syncedMessages,
          oldestSyncedDate: formatMetadataCutoffDate(oldestSyncedMs) || previousState?.oldestSyncedDate || "",
          nextPageToken: pageToken,
        });
        await waitForBackgroundSlot();
        continue;
      }

      if (!nextToken || !messages.length) {
        stopReason = "gmail_end";
        break;
      }
      page += 1;
      pageToken = nextToken;
      await waitForBackgroundSlot();
    }

    if (!stopReason) {
      if (syncedMessages >= METADATA_BACKFILL_MAX_MESSAGES || page > maxPages) {
        stopReason = "local_limit";
      } else if (document.hidden || !state.isConnected || state.email !== scope.userEmail) {
        stopReason = "paused";
      }
    }
    const complete = stopReason !== "paused" &&
      Boolean(wasComplete || !nextToken || page > maxPages || syncedMessages >= METADATA_BACKFILL_MAX_MESSAGES);
    const stats = await cache.getStats?.(scope.userEmail);
    const statsOldestDate = stats?.metadataOldestDate ? formatMetadataCutoffDate(Date.parse(stats.metadataOldestDate)) : "";
    const oldestSyncedDate = formatMetadataCutoffDate(oldestSyncedMs) ||
      previousState?.oldestSyncedDate ||
      statsOldestDate ||
      "";
    await cache.saveMetadataSyncState?.(scope, {
      complete,
      status: complete ? (wasComplete ? "latest_refreshed" : "metadata_ready") : "paused",
      syncedPages: wasComplete
        ? Math.max(Number(previousState?.syncedPages || 0), Math.min(page, maxPages))
        : Math.min(page, maxPages),
      syncedMessages: wasComplete
        ? Math.max(Number(previousState?.syncedMessages || 0), syncedMessages)
        : syncedMessages,
      oldestSyncedDate,
      stopReason,
      nextPageToken: nextToken,
      completedAt: complete ? new Date().toISOString() : previousState?.completedAt || "",
    });
    const isCurrentScope = state.email === scope.userEmail &&
      mailbox === state.activeMailbox &&
      cleanCategory === normalizedInboxCategory() &&
      Boolean(unreadOnly) === Boolean(state.unreadOnly);
    if (isCurrentScope && complete) {
      const title = mailboxDisplayTitle(mailbox, state.activeMailboxTitle, cleanCategory).toLowerCase();
      const suffix = oldestSyncedDate ? ` till ${oldestSyncedDate}` : "";
      const reason = stopReason === "local_limit" ? "Metadata cache limit reached" : "Finished caching mailbox metadata";
      setActivity(`${reason} for ${title}${suffix}.`);
    } else if (isCurrentScope && stopReason === "paused") {
      const title = mailboxDisplayTitle(mailbox, state.activeMailboxTitle, cleanCategory).toLowerCase();
      const suffix = oldestSyncedDate ? ` at ${oldestSyncedDate}` : "";
      setActivity(`Metadata sync paused for ${title}${suffix}. It will continue automatically.`);
    }
  } finally {
    state.metadataBackfillRequests.delete(requestKey);
  }
}

function messageThreadCount(message) {
  const explicitCount = Number(message?.thread_message_count);
  if (Number.isFinite(explicitCount) && explicitCount > 0) return explicitCount;
  const threadMessages = Array.isArray(message?.thread_messages) ? message.thread_messages : [];
  return threadMessages.length ? threadMessages.length + 1 : 1;
}

function selectedStatusText(message) {
  const base = message?.reply_needed ? "Reply needed" : "Gmail message";
  const count = messageThreadCount(message);
  return count > 1 ? `${base} - ${count} messages` : base;
}

function selectedRecipientLabel(message) {
  const to = String(message?.to || "").toLowerCase();
  const ownEmail = String(state.email || "").toLowerCase();
  if (ownEmail && to.includes(ownEmail)) return "to me";
  return "to recipient";
}

function replyRecipient(message) {
  return senderAddress(message?.from || "");
}

function quotedOriginalMessage(message) {
  const body = selectedMessagePlainText(message, "");
  const quoted = body
    .split("\n")
    .map((line) => `> ${line}`)
    .join("\n");
  return [
    "",
    "",
    `On ${formatDate(message)}, ${displayText(message?.from || "the sender")} wrote:`,
    quoted,
  ].join("\n");
}

function replyDraftWithQuote(message, draft = "") {
  const currentDraft = String(draft || "").trim();
  const quote = quotedOriginalMessage(message).trim();
  if (!quote) return currentDraft;
  if (currentDraft.includes(" wrote:\n>")) return currentDraft;
  return [currentDraft, quote].filter(Boolean).join("\n\n");
}

function setText(element, value = "-") {
  if (element) element.textContent = value || "-";
}

function updateSelectedRecipientDetails(message) {
  setText(selectedDetailFrom, displayText(message?.from || "-"));
  setText(selectedDetailTo, displayText(message?.to || "-"));
  setText(selectedDetailDate, message ? formatDate(message) : "-");
  const cc = displayText(message?.cc || "");
  const bcc = displayText(message?.bcc || "");
  if (selectedDetailCcRow) selectedDetailCcRow.hidden = !cc;
  if (selectedDetailBccRow) selectedDetailBccRow.hidden = !bcc;
  setText(selectedDetailCc, cc || "-");
  setText(selectedDetailBcc, bcc || "-");
  if (selectedRecipientToggle) {
    selectedRecipientToggle.firstChild.textContent = message ? selectedRecipientLabel(message) : "to me";
    selectedRecipientToggle.setAttribute("aria-expanded", selectedRecipientDetails?.hidden ? "false" : "true");
  }
}

function isInboxMailbox(mailbox = state.activeMailbox) {
  return String(mailbox || "").toLowerCase() === "inbox";
}

function isPrimaryInboxScope(mailbox = state.activeMailbox, category = state.activeInboxCategory) {
  return isInboxMailbox(mailbox) && normalizedInboxCategory(category) === "primary";
}

function needsAnalysis(message) {
  const status = String(message?.processing_status || "").toLowerCase();
  const doneStatuses = new Set(["analyzed", "summarized", "reply_generated", "skipped"]);
  if (status === "skipped") return false;
  if (doneStatuses.has(status)) return false;
  if (status === "not_analyzed") {
    return message?.skip_reason !== "no_date_time_expression_detected";
  }
  if (status === "analyzing") {
    const updatedAt = message?.analysis_updated_at || message?.updated_at;
    if (!updatedAt) return true;
    const updatedTime = new Date(updatedAt).getTime();
    if (Number.isNaN(updatedTime)) return true;
    return Date.now() - updatedTime > 2 * 60 * 1000;
  }
  return ["", "pending", "failed"].includes(status) || status.includes("failed");
}

function formatDate(message) {
  const rawDate = message.date || [message.message_date, message.message_time].filter(Boolean).join(" ");
  if (!rawDate) return "";

  const parsed = new Date(rawDate);
  if (Number.isNaN(parsed.getTime())) return rawDate;

  return parsed.toLocaleString([], {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function formatEventTime(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function eventDate(value) {
  const date = new Date(value || "");
  return Number.isNaN(date.getTime()) ? null : date;
}

function eventDateKey(value) {
  const date = eventDate(value);
  if (!date) return "";
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

function startOfDay(date = new Date()) {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate());
}

function addDays(date, days) {
  const next = new Date(date);
  next.setDate(next.getDate() + days);
  return next;
}

function startOfWeek(date = new Date()) {
  const day = startOfDay(date);
  const diff = (day.getDay() + 6) % 7;
  return addDays(day, -diff);
}

function formatCalendarDay(date) {
  return date.toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" });
}

function formatCalendarTime(value) {
  const date = eventDate(value);
  if (!date) return "";
  return date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

function isPlannedEventReminder(event) {
  return String(event?.event_kind || "").toLowerCase() === "planned_event_reminder";
}

function isIcsInvite(event) {
  const source = String(event?.source || "").toLowerCase();
  const eventKind = String(event?.event_kind || "").toLowerCase();
  return source === "ics" || eventKind === "ics_invite" || Boolean(event?.uid && (event?.organizer || event?.status));
}

function selectedCalendarEvent(message) {
  const event = message?.calendar_event;
  return event && isIcsInvite(event) ? event : null;
}

function eventKindText(event) {
  return String(event?.event_kind || "")
    .replace(/[_-]+/g, " ")
    .trim();
}

function eventKindLabel(event) {
  if (isIcsInvite(event)) return "ICS invite";
  if (isPlannedEventReminder(event)) return "Planned event reminder";
  const kind = eventKindText(event);
  if (!kind || kind === "calendar event") return "Calendar notification";
  const suffix = ["deadline", "task reminder", "follow up", "payment", "renewal"].includes(kind)
    ? "reminder"
    : "event";
  return `${kind.charAt(0).toUpperCase()}${kind.slice(1)} ${suffix}`;
}

function saveEmail() {
  state.email = emailInput.value.trim();
  if (state.email) {
    localStorage.setItem("emailReminders.email", state.email);
  }
}

function applyAuthRedirectParams() {
  const params = new URLSearchParams(window.location.search);
  const email = params.get("email");
  const connected = params.get("connected") === "1";
  const authError = params.get("auth_error");
  if (!email && !connected && !authError) return false;

  if (email) {
    emailInput.value = email;
    saveEmail();
  }
  if (connected) {
    setConnectionState(true);
    setActivity("Gmail connected. Loading mailbox...");
  }
  if (authError) {
    state.authError = authError;
    setConnectionState(false);
    setActivity(authError);
    if (loginScreenButton) loginScreenButton.hidden = false;
  }

  window.history.replaceState({}, document.title, window.location.pathname);
  return connected;
}

function redirectToGoogleLogin(reason = "Opening Google login...") {
  setActivity(reason);
  window.location.assign("/auth/login");
}

function showLoginPrompt(message = "Continue with Google to open your mailbox.") {
  setConnectionState(false);
  if (loginScreenButton) loginScreenButton.hidden = false;
  setActivity(message);
  if (!loginScreen) {
    window.location.assign("/");
  }
}

async function hydrateFromSessionCache() {
  saveEmail();
  const cachedMessages = await readLocalMailboxPage(
    state.email,
    state.activeMailbox,
    state.unreadOnly,
    state.activeInboxCategory,
    1,
  ) || readCachedMessages(state.email);
  if (!cachedMessages.length) return false;

  state.messages = mergeMessageList(cachedMessages);
  rememberFullMessages(state.messages);
  state.selected = null;
  state.isMailboxLoading = false;
  state.messageError = "";
  renderMessages();
  setActivity(`Showing ${cachedMessages.length} cached message${cachedMessages.length === 1 ? "" : "s"}.`);
  return true;
}

function renderMessages() {
  const pagination = paginationState();
  const start = state.messages.length ? (pagination.currentPage - 1) * MAILBOX_PAGE_SIZE + 1 : 0;
  const end = state.messages.length ? start + state.messages.length - 1 : 0;
  messageCount.textContent = state.messages.length ? `${start}-${end}` : "0";
  updatePaginationControls();

  if (state.isMailboxLoading && !state.messages.length) {
    const loadingText = state.isSearchActive
      ? `Searching for "${escapeHtml(state.searchQuery)}"...`
      : state.isInitialMailboxSync
        ? "Syncing your Gmail data..."
        : `Loading ${escapeHtml(state.activeMailboxTitle.toLowerCase())} messages...`;
    messageList.innerHTML = `<div class="empty-state loading-state">${loadingText}</div>`;
    return;
  }

  if (state.messageError) {
    messageList.innerHTML = `<div class="empty-state error-state">${escapeHtml(state.messageError)}</div>`;
    return;
  }

  if (!state.messages.length) {
    const emptyText = state.isSearchActive
      ? `No messages found for "${escapeHtml(state.searchQuery)}".`
      : "No messages loaded for this mailbox.";
    messageList.innerHTML = `<div class="empty-state">${emptyText}</div>`;
    return;
  }

  messageList.innerHTML = "";
  for (const message of state.messages) {
    const threadCount = messageThreadCount(message);
    const item = document.createElement("button");
    item.type = "button";
    item.className = "message-item";
    item.dataset.messageId = message.message_id;
    item.dataset.action = "open-message";
    item.onclick = () => window.openEmailReminderMessage(message.message_id);
    if (state.selected?.message_id === message.message_id) {
      item.classList.add("active");
    }

    item.innerHTML = `
      <span class="message-sender">${escapeHtml(displayText(message.from || "Unknown sender"))}</span>
      <span class="message-main">
        <strong>
          ${escapeHtml(displayText(message.subject || "(No subject)"))}
          ${threadCount > 1 ? `<span class="thread-count">${threadCount}</span>` : ""}
        </strong>
        <span>${escapeHtml(displayText(message.summary || message.skip_reason || "No summary available."))}</span>
      </span>
      <span class="message-date">${escapeHtml(formatDate(message))}</span>
    `;

    messageList.appendChild(item);
  }
}

function renderCalendarEvents() {
  const todayEvents = eventsForDate(new Date());
  const tomorrowEvents = eventsForDate(addDays(new Date(), 1));
  const upcomingEvents = [...todayEvents, ...tomorrowEvents];
  // Events awaiting an approve/deny are notifications in their own right, even
  // when they fall outside the today/tomorrow window, so they count here too.
  const pendingResponses = state.pendingResponses || [];
  const notificationCount = upcomingEvents.length + pendingResponses.length;
  calendarCount.textContent = String(notificationCount);
  if (upcomingRailCount) upcomingRailCount.textContent = String(notificationCount);
  setMailboxCount("calendar", notificationCount);

  if (!notificationCount) {
    calendarList.innerHTML = '<div class="empty-state">No events today or tomorrow.</div>';
    renderCalendarBoard();
    return;
  }

  const pendingSection = pendingResponses.length
    ? `
      <section class="upcoming-day-group">
        <h4>Needs your response</h4>
        ${pendingResponses.map((event) => calendarEventCard(event, false)).join("")}
      </section>
    `
    : "";

  calendarList.innerHTML = `
    ${pendingSection}
    <section class="upcoming-day-group">
      <h4>Today</h4>
      ${todayEvents.length
        ? todayEvents.map((event) => calendarEventCard(event, false)).join("")
        : '<div class="calendar-empty-slot">No events today</div>'}
    </section>
    <section class="upcoming-day-group">
      <h4>Tomorrow</h4>
      ${tomorrowEvents.length
        ? tomorrowEvents.map((event) => calendarEventCard(event, false)).join("")
        : '<div class="calendar-empty-slot">No events tomorrow</div>'}
    </section>
  `;
  renderCalendarBoard();
}

function setUpcomingEventsPanelOpen(open) {
  if (!upcomingEventsPanel || !openUpcomingEventsButton) return;
  upcomingEventsPanel.classList.toggle("is-open", Boolean(open));
  upcomingEventsPanel.setAttribute("aria-hidden", open ? "false" : "true");
  openUpcomingEventsButton.classList.toggle("active", Boolean(open));
  openUpcomingEventsButton.setAttribute("aria-expanded", open ? "true" : "false");
}

function handleCalendarEventCardClick(event, root) {
  const proposalButton = event.target.closest('[data-action="show-proposal"]');
  if (proposalButton && root.contains(proposalButton)) {
    const card = proposalButton.closest(".calendar-event-card");
    const proposal = card?.querySelector(".calendar-proposal");
    if (proposal) proposal.hidden = !proposal.hidden;
    return true;
  }

  const responseButton = event.target.closest("[data-calendar-response]");
  if (responseButton && root.contains(responseButton)) {
    const card = responseButton.closest(".calendar-event-card");
    sendCalendarEventResponse(card, responseButton.dataset.calendarResponse);
    return true;
  }

  const removeButton = event.target.closest('[data-action="remove-event"]');
  if (removeButton && root.contains(removeButton)) {
    const card = removeButton.closest(".calendar-event-card");
    removeCalendarEvent(card);
    return true;
  }

  const openButton = event.target.closest('[data-action="open-event"]');
  if (openButton && root.contains(openButton)) {
    window.openEmailReminderMessage(openButton.dataset.messageId);
    return true;
  }

  const card = event.target.closest(".calendar-event-card");
  if (card && root.contains(card)) {
    window.openEmailReminderMessage(card.dataset.messageId);
    return true;
  }

  return false;
}

function eventsForDate(date) {
  const key = eventDateKey(date);
  return state.calendarEvents
    .filter((event) => eventDateKey(event.start_at) === key)
    .sort((left, right) => {
      if (isPlannedEventReminder(left) !== isPlannedEventReminder(right)) {
        return isPlannedEventReminder(left) ? -1 : 1;
      }
      return (eventDate(left.start_at)?.getTime() || 0) - (eventDate(right.start_at)?.getTime() || 0);
    });
}

function calendarCardActionsHtml() {
  return `
    <div class="calendar-rsvp-actions" aria-label="Calendar event response">
      <button class="secondary" type="button" data-calendar-response="accepted">Approve</button>
      <button class="secondary" type="button" data-calendar-response="declined">Deny</button>
      <button class="secondary" type="button" data-action="remove-event">Remove</button>
    </div>
  `;
}

const CALENDAR_STATUS_BADGE_LABELS = {
  accepted: "Approved",
  declined: "Denied",
  tentative: "Tentative",
  proposed: "Proposed",
};

function calendarEventStatusKey(event) {
  return String(event?.status || "").trim().toLowerCase();
}

function calendarStatusBadgeHtml(status) {
  const normalized = String(status || "").trim().toLowerCase();
  const label = CALENDAR_STATUS_BADGE_LABELS[normalized];
  if (!label) return "";
  return `<span class="calendar-status-badge status-${normalized}">${escapeHtml(label)}</span>`;
}

function calendarEventCard(event, compact = false) {
  const title = displayText(event.title || event.subject || "Email event");
  const messageId = escapeHtml(event.message_id || "");
  const statusKey = calendarEventStatusKey(event);
  const statusBadge = calendarStatusBadgeHtml(statusKey);
  const declinedClass = statusKey === "declined" ? "status-declined-card" : "";
  if (isIcsInvite(event)) {
    const organizer = displayText(event.organizer || event.from || "Organizer not listed");
    const status = displayText(event.status || "Needs response");
    return `
      <article class="calendar-event-card ics-invite ${compact ? "compact" : ""} ${declinedClass}" data-message-id="${messageId}">
        ${statusBadge}
        <button class="calendar-card-open" type="button" data-action="open-event" data-message-id="${messageId}">
          <strong>${escapeHtml(title)}</strong>
          <span>${escapeHtml(organizer)}</span>
          <small>${escapeHtml(status)}</small>
        </button>
        ${compact ? "" : calendarCardActionsHtml()}
      </article>
    `;
  }
  const meta = isPlannedEventReminder(event)
    ? "Planned event reminder"
    : formatCalendarTime(event.start_at) || eventKindLabel(event);
  return `
    <article class="calendar-event-card ${compact ? "compact" : ""} ${isPlannedEventReminder(event) ? "planned" : ""} ${declinedClass}" data-message-id="${messageId}">
      ${statusBadge}
      <button class="calendar-card-open" type="button" data-action="open-event" data-message-id="${messageId}">
        <strong>${escapeHtml(title)}</strong>
        <span>${escapeHtml(meta)}</span>
        ${compact ? "" : `<small>${escapeHtml(displayText(event.from || event.location || event.subject || ""))}</small>`}
      </button>
      ${compact ? "" : calendarCardActionsHtml()}
    </article>
  `;
}

function renderSelectedCalendarInviteActions(message) {
  if (!selectedCalendarInviteActions) return;
  const event = selectedCalendarEvent(message);
  if (!event || !message?.message_id) {
    selectedCalendarInviteActions.hidden = true;
    selectedCalendarInviteActions.innerHTML = "";
    return;
  }

  const title = displayText(event.title || message.subject || "Calendar invite");
  const organizer = displayText(event.organizer || message.from || "Organizer not listed");
  const status = displayText(event.status || "Needs response");
  selectedCalendarInviteActions.hidden = false;
  selectedCalendarInviteActions.innerHTML = `
    <article class="calendar-event-card ics-invite selected-ics-invite" data-message-id="${escapeHtml(message.message_id)}">
      <div class="selected-ics-summary">
        <strong>${escapeHtml(title)}</strong>
        <span>${escapeHtml(organizer)}</span>
        <small>${escapeHtml(status)}</small>
      </div>
      <div class="calendar-rsvp-actions" aria-label="Calendar invite response">
        <button class="secondary" type="button" data-calendar-response="accepted">Send approve</button>
        <button class="secondary" type="button" data-calendar-response="declined">Deny</button>
        <button class="secondary" type="button" data-calendar-response="tentative">Send tentative</button>
        <button class="secondary" type="button" data-action="show-proposal">New proposal</button>
      </div>
      <div class="calendar-proposal" hidden>
        <input type="date" aria-label="Proposed date" />
        <input type="time" aria-label="Proposed time" />
        <button class="primary" type="button" data-calendar-response="proposed">Send proposal</button>
      </div>
    </article>
  `;
}

function renderCalendarDayView() {
  const today = startOfDay(new Date());
  const events = eventsForDate(today);
  calendarViewTitle.textContent = `Day - ${formatCalendarDay(today)}`;
  if (!events.length) {
    calendarBoard.innerHTML = '<div class="empty-state">No events for today.</div>';
    return;
  }
  const plannedEvents = events.filter(isPlannedEventReminder);
  const timedEvents = events.filter((event) => !isPlannedEventReminder(event));
  calendarBoard.innerHTML = `
    <div class="calendar-day-view">
      ${plannedEvents.length ? `
        <div class="calendar-planned-row">
          ${plannedEvents.map((event) => calendarEventCard(event)).join("")}
        </div>
      ` : ""}
      ${timedEvents.map((event) => `
        <div class="calendar-time-row">
          <time>${escapeHtml(formatCalendarTime(event.start_at))}</time>
          ${calendarEventCard(event)}
        </div>
      `).join("")}
    </div>
  `;
}

function renderCalendarWeekView() {
  const firstDay = startOfWeek(new Date());
  const days = Array.from({ length: 7 }, (_, index) => addDays(firstDay, index));
  calendarViewTitle.textContent = "Week";
  calendarBoard.innerHTML = `
    <div class="calendar-week-view">
      ${days.map((day) => {
        const events = eventsForDate(day);
        return `
          <section class="calendar-day-column">
            <h4>${escapeHtml(formatCalendarDay(day))}</h4>
            <div class="calendar-day-events">
              ${events.length ? events.map((event) => calendarEventCard(event, true)).join("") : '<span class="calendar-empty-slot">No events</span>'}
            </div>
          </section>
        `;
      }).join("")}
    </div>
  `;
}

function renderCalendarMonthView() {
  const today = new Date();
  const first = new Date(today.getFullYear(), today.getMonth(), 1);
  const gridStart = addDays(first, -first.getDay());
  const days = Array.from({ length: 42 }, (_, index) => addDays(gridStart, index));
  calendarViewTitle.textContent = today.toLocaleDateString([], { month: "long", year: "numeric" });
  calendarBoard.innerHTML = `
    <div class="calendar-month-view">
      ${days.map((day) => {
        const events = eventsForDate(day);
        const isOutside = day.getMonth() !== today.getMonth();
        return `
          <section class="calendar-month-cell ${isOutside ? "outside" : ""}">
            <h4>${day.getDate()}</h4>
            ${events.slice(0, 3).map((event) => calendarEventCard(event, true)).join("")}
            ${events.length > 3 ? `<span class="calendar-more">+${events.length - 3} more</span>` : ""}
          </section>
        `;
      }).join("")}
    </div>
  `;
}

function renderCalendarBoard() {
  if (!calendarBoard || calendarView.hidden) return;
  document.querySelectorAll(".calendar-mode").forEach((button) => {
    button.classList.toggle("active", button.dataset.calendarMode === state.calendarMode);
  });
  if (!state.calendarEvents.length) {
    calendarViewTitle.textContent = "Events";
    calendarBoard.innerHTML = '<div class="empty-state">No calendar events detected yet.</div>';
    return;
  }
  if (state.calendarMode === "day") {
    renderCalendarDayView();
  } else if (state.calendarMode === "month") {
    renderCalendarMonthView();
  } else {
    renderCalendarWeekView();
  }
}

function setMessagesFromList(messages, mailbox = state.activeMailbox, writeCache = true, page = paginationState(mailbox).currentPage || 1) {
  state.messages = mergeMessageList(messages || []);
  rememberFullMessages(state.messages);
  if (writeCache) {
    writeCachedMessages(state.email, state.messages, mailbox);
  }
  writeLocalMailboxPage(
    state.email,
    state.messages,
    mailbox,
    state.unreadOnly,
    state.activeInboxCategory,
    page,
  );
}

async function enqueuePendingAnalysis(messages = state.messages) {
  saveEmail();
  if (!state.email || !isPrimaryInboxScope()) return;

  const pendingIds = [];
  for (const message of messages || []) {
    const messageId = messageKey(message);
    if (!messageId || state.analysisEnqueued.has(messageId) || !needsAnalysis(message)) continue;
    pendingIds.push(messageId);
  }

  if (!pendingIds.length) return;
  for (const messageId of pendingIds) {
    state.analysisEnqueued.add(messageId);
    const message = state.messages.find((entry) => messageKey(entry) === messageId);
    if (message) {
      message.processing_status = "analyzing";
    }
  }
  renderMessages();

  try {
    await requestJson("/pipeline/messages", {
      method: "POST",
      body: JSON.stringify({
        email: state.email,
        mailbox: state.activeMailbox,
        category: normalizedInboxCategory(),
        message_ids: pendingIds,
      }),
    });
    setActivity(`Analyzing ${pendingIds.length} message${pendingIds.length === 1 ? "" : "s"} for events and reminders.`);
  } catch (error) {
    for (const messageId of pendingIds) state.analysisEnqueued.delete(messageId);
    setActivity(error.message);
  }
}

function selectMessage(message) {
  const selected = mergeWithFullMessage(message);
  state.selected = selected;
  selectedSubject.textContent = displayText(selected.subject || "(No subject)");
  selectedFrom.textContent = displayText(selected.from || "-");
  selectedStatus.textContent = selectedStatusText(selected);
  if (selectedAvatar) selectedAvatar.textContent = senderInitial(selected.from);
  if (selectedTime) selectedTime.textContent = formatDate(selected);
  if (selectedRecipientDetails) selectedRecipientDetails.hidden = true;
  updateSelectedRecipientDetails(selected);
  renderSelectedCalendarInviteActions(selected);
  renderSelectedMessageBody(selected, "Loading full message...");
  selectedMessageId.value = selected.message_id;
  renderMarkdownSummary("");
  setRichEditorValue(generatedReplyEditor, generatedReply, selected.suggested_reply || "");
  setRichEditorValue(replyIntentEditor, replyIntent, "");
  if (replyTo) replyTo.value = replyRecipient(selected);
  if (replyCc) replyCc.value = "";
  if (replyBcc) replyBcc.value = "";
  if (replyCcRow) replyCcRow.hidden = true;
  if (replyBccRow) replyBccRow.hidden = true;
  summaryResult.hidden = true;
  replyComposer.hidden = true;
  renderMessages();
  openMessageModal();
  loadFullMessage(selected.message_id);
}

function renderSelectedMessage() {
  if (!state.selected) return;
  selectedSubject.textContent = displayText(state.selected.subject || "(No subject)");
  selectedFrom.textContent = displayText(state.selected.from || "-");
  selectedStatus.textContent = selectedStatusText(state.selected);
  if (selectedAvatar) selectedAvatar.textContent = senderInitial(state.selected.from);
  if (selectedTime) selectedTime.textContent = formatDate(state.selected);
  updateSelectedRecipientDetails(state.selected);
  renderSelectedCalendarInviteActions(state.selected);
  renderSelectedMessageBody(state.selected, "No preview available.");
  selectedMessageId.value = state.selected.message_id;
  syncRichEditorToTextarea(generatedReplyEditor, generatedReply);
  if (!generatedReply.value.trim()) {
    setRichEditorValue(generatedReplyEditor, generatedReply, state.selected.suggested_reply || "");
  }
}

function openMessageModal() {
  messageModal.classList.add("is-open");
  messageModal.setAttribute("aria-hidden", "false");
  document.body.classList.add("modal-open");
}

function closeMessageModal() {
  messageModal.classList.remove("is-open");
  messageModal.setAttribute("aria-hidden", "true");
  document.body.classList.remove("modal-open");
  state.selected = null;
  selectedMessageId.value = "";
  renderSelectedCalendarInviteActions(null);
  state.restoreEmailFrameOnFocus = false;
  clearEmailHtmlFrame();
}

function resetComposeModal() {
  state.composeMode = "compose";
  state.composeReplyMessageId = "";
  state.composeOriginalHtml = "";
  state.composeOriginalPlainText = "";
  const composeTitle = document.querySelector("#composeTitle");
  if (composeTitle) composeTitle.textContent = "New message";
  if (sendWriterButton) sendWriterButton.textContent = "Send";
  if (writerButton) {
    writerButton.hidden = false;
    writerButton.textContent = "Use AI writer";
  }
  if (composeReplyIntentSection) composeReplyIntentSection.hidden = true;
  if (composeReplyIntent) composeReplyIntent.value = "";
  if (composeOriginalPreview) composeOriginalPreview.hidden = true;
  if (composeOriginalFrame) composeOriginalFrame.removeAttribute("srcdoc");
  composeTo.value = "";
  if (composeCc) composeCc.value = "";
  if (composeBcc) composeBcc.value = "";
  if (composeCcRow) composeCcRow.hidden = true;
  if (composeBccRow) composeBccRow.hidden = true;
  composeSubject.value = "";
  setWriterFormat("formal");
  setRichEditorValue(writerInstructionEditor, writerInstruction, "");
  generatedWriterDraft.value = "";
  clearAttachments(writerAttachments, writerAttachmentList);
}

function renderComposeOriginalPreview(title, html) {
  if (!composeOriginalPreview || !composeOriginalFrame) return;
  state.composeOriginalHtml = html || "";
  if (composeOriginalTitle) composeOriginalTitle.textContent = title || "Tagged message";
  composeOriginalFrame.srcdoc = buildEmailPreviewDocument(html || '<p class="empty-message">(No body available.)</p>');
  composeOriginalPreview.hidden = false;
}

function composeBodyWithOriginalHtml(bodyHtml) {
  const draftHtml = String(bodyHtml || "").trim();
  const originalHtml = String(state.composeOriginalHtml || "").trim();
  if (!originalHtml) return draftHtml;
  return [draftHtml, originalHtml].filter(Boolean).join("");
}

function composeBodyWithOriginalPlainText(bodyText) {
  const draftText = String(bodyText || "").trim();
  const originalText = String(state.composeOriginalPlainText || "").trim();
  if (!originalText) return draftText;
  return [draftText, originalText].filter(Boolean).join("\n\n");
}

function openComposeModal(mode = "compose") {
  resetComposeModal();
  state.composeMode = mode;
  composeModal.classList.add("is-open");
  composeModal.setAttribute("aria-hidden", "false");
  document.body.classList.add("modal-open");
  composeTo.focus();
}

function openForwardCompose() {
  const selected = state.selected;
  if (!selected) {
    setActivity("Select a message first.");
    return;
  }
  closeMessageModal();
  openComposeModal();
  const composeTitle = document.querySelector("#composeTitle");
  if (composeTitle) composeTitle.textContent = "Forward message";
  composeSubject.value = /^fwd:/i.test(selected.subject || "")
    ? displayText(selected.subject || "")
    : `Fwd: ${displayText(selected.subject || "(No subject)")}`;
  const forwarded = [
    "",
    "",
    "---------- Forwarded message ---------",
    `From: ${displayText(selected.from || "")}`,
    `Date: ${formatDate(selected)}`,
    `Subject: ${displayText(selected.subject || "")}`,
    `To: ${displayText(selected.to || "")}`,
  ].join("\n");
  setRichEditorValue(writerInstructionEditor, writerInstruction, forwarded);
  state.composeOriginalPlainText = selectedMessagePlainText(selected, "");
  renderComposeOriginalPreview("Forwarded message", selectedMessageRenderedHtml(selected));
  generatedWriterDraft.value = writerInstruction.value;
  setActivity("Forward draft opened.");
}

function replySubject(subject = "") {
  const cleanSubject = displayText(subject || "(No subject)");
  return /^re:/i.test(cleanSubject) ? cleanSubject : `Re: ${cleanSubject}`;
}

function selectedMessageRenderedHtml(message) {
  return selectedMessageIframeHtml(message) || bodyTextToHtml(selectedMessagePlainText(message, ""));
}

function replyOriginalHtml(message) {
  const originalHtml = selectedMessageRenderedHtml(message);
  const from = displayText(message?.from || "the sender");
  const date = formatDate(message);
  return `
    <p></p>
    <p></p>
    <div class="reply-original-message">
      <p>On ${escapeHtml(date)}, ${escapeHtml(from)} wrote:</p>
      <blockquote>${originalHtml}</blockquote>
    </div>
  `;
}

function openReplyCompose() {
  const selected = state.selected;
  if (!selected) {
    setActivity("Select a message first.");
    return;
  }
  const messageId = messageKey(selected);
  closeMessageModal();
  openComposeModal("reply");
  state.composeReplyMessageId = messageId;
  const composeTitle = document.querySelector("#composeTitle");
  if (composeTitle) composeTitle.textContent = "Reply";
  if (sendWriterButton) sendWriterButton.textContent = "Send reply";
  if (writerButton) {
    writerButton.hidden = false;
    writerButton.textContent = "Use AI writer";
  }
  if (composeReplyIntentSection) composeReplyIntentSection.hidden = false;
  if (composeReplyIntent) composeReplyIntent.value = "";
  composeTo.value = replyRecipient(selected);
  composeSubject.value = replySubject(selected.subject || "");
  setRichEditorValue(writerInstructionEditor, writerInstruction, selected.suggested_reply || "");
  state.composeOriginalPlainText = quotedOriginalMessage(selected).trim();
  renderComposeOriginalPreview("Tagged original message", replyOriginalHtml(selected));
  generatedWriterDraft.value = writerInstruction.value;
  setActivity("Reply draft opened.");
}

function showComposeRecipientField(field) {
  const row = field === "bcc" ? composeBccRow : composeCcRow;
  const input = field === "bcc" ? composeBcc : composeCc;
  if (!row || !input) return;
  row.hidden = false;
  input.focus();
}

function showReplyRecipientField(field) {
  const row = field === "bcc" ? replyBccRow : replyCcRow;
  const input = field === "bcc" ? replyBcc : replyCc;
  if (!row || !input) return;
  row.hidden = false;
  input.focus();
}

function prepareReplyComposer() {
  if (!state.selected) return;
  if (replyTo && !replyTo.value.trim()) replyTo.value = replyRecipient(state.selected);
  const currentDraft = richEditorPlainText(generatedReplyEditor);
  setRichEditorValue(generatedReplyEditor, generatedReply, replyDraftWithQuote(state.selected, currentDraft));
}

function writerFormatValue() {
  return writerFormatButton?.dataset.format || "formal";
}

function setWriterFormat(format) {
  const nextFormat = format === "informal" ? "informal" : "formal";
  if (!writerFormatButton) return;
  writerFormatButton.dataset.format = nextFormat;
  writerFormatButton.textContent = nextFormat === "informal" ? "Informal" : "Formal";
}

function closeComposeModal() {
  composeModal.classList.remove("is-open");
  composeModal.setAttribute("aria-hidden", "true");
  document.body.classList.remove("modal-open");
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function displayText(value) {
  const textarea = document.createElement("textarea");
  textarea.innerHTML = String(value || "")
    .replace(/<\/?external_source>/g, "")
    .replace(/\r\n/g, "\n")
    .replace(/\r/g, "\n")
    .replace(/[ \t]+\n/g, "\n")
    .replace(/\n[ \t]+/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
  return textarea.value;
}

function plainTextToRichHtml(value) {
  const text = displayText(value || "");
  if (!text) return "";
  return text
    .split(/\n{2,}/)
    .map((paragraph) => {
      const lines = paragraph
        .split(/\n/)
        .map((line) => escapeHtml(line))
        .join("<br>");
      return `<p>${lines}</p>`;
    })
    .join("");
}

function richEditorPlainText(editor) {
  const quill = quillEditors.get(editor?.id);
  if (quill) {
    return quill.getText()
      .replace(/\u00a0/g, " ")
      .replace(/\n{3,}/g, "\n\n")
      .trim();
  }
  return String(editor?.innerText || "")
    .replace(/\u00a0/g, " ")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function richEditorHtml(editor) {
  const quill = quillEditors.get(editor?.id);
  const html = String(
    quill
      ? (typeof quill.getSemanticHTML === "function" ? quill.getSemanticHTML() : quill.root.innerHTML)
      : editor?.innerHTML || "",
  ).trim();
  return richEditorPlainText(editor) ? html : "";
}

function setRichEditorValue(editor, textarea, value) {
  const html = plainTextToRichHtml(value || "");
  const quill = quillEditors.get(editor?.id);
  if (quill) {
    quill.clipboard.dangerouslyPasteHTML(html || "");
  } else if (editor) {
    editor.innerHTML = html;
  }
  if (textarea) textarea.value = displayText(value || "");
}

function setRichEditorHtml(editor, textarea, html) {
  const cleanHtml = String(html || "");
  const quill = quillEditors.get(editor?.id);
  if (quill) {
    quill.clipboard.dangerouslyPasteHTML(cleanHtml);
  } else if (editor) {
    editor.innerHTML = cleanHtml;
  }
  if (textarea) textarea.value = richEditorPlainText(editor);
}

function syncRichEditorToTextarea(editor, textarea) {
  if (!textarea) return;
  textarea.value = richEditorPlainText(editor);
}

function focusRichEditorForToolbar(toolbar) {
  const editorId = toolbar?.closest(".rich-editor")?.dataset.richEditor;
  const editor = editorId ? document.querySelector(`#${CSS.escape(editorId)}`) : null;
  const quill = quillEditors.get(editor?.id);
  if (quill) quill.focus();
  else if (editor) editor.focus();
  return editor;
}

function richEditorById(editorId) {
  return editorId ? document.querySelector(`#${CSS.escape(editorId)}`) : null;
}

function insertTextIntoEditor(editorId, text) {
  const editor = richEditorById(editorId);
  const quill = quillEditors.get(editor?.id);
  if (quill) {
    quill.focus();
    const range = quill.getSelection(true);
    const index = range?.index ?? quill.getLength();
    quill.insertText(index, text, "user");
    quill.setSelection(index + text.length, 0, "silent");
    syncRichEditorToTextarea(editor, editorTextarea(editorId));
    return;
  }
  if (editor) {
    editor.focus();
    document.execCommand("insertText", false, text);
    syncRichEditorToTextarea(editor, editorTextarea(editorId));
  }
}

function insertHtmlIntoEditor(editorId, html) {
  const editor = richEditorById(editorId);
  const quill = quillEditors.get(editor?.id);
  if (quill) {
    quill.focus();
    const range = quill.getSelection(true);
    const index = range?.index ?? quill.getLength();
    quill.clipboard.dangerouslyPasteHTML(index, html, "user");
    syncRichEditorToTextarea(editor, editorTextarea(editorId));
    return;
  }
  if (editor) {
    editor.focus();
    document.execCommand("insertHTML", false, html);
    syncRichEditorToTextarea(editor, editorTextarea(editorId));
  }
}

function editorTextarea(editorId) {
  return {
    generatedReplyEditor: generatedReply,
    replyIntentEditor: replyIntent,
    writerInstructionEditor: writerInstruction,
    signatureEditor: signatureValue,
  }[editorId];
}

function savedSignatureHtml() {
  return localStorage.getItem(SIGNATURE_STORAGE_KEY) || DEFAULT_SIGNATURE_HTML;
}

function hideFloatingMenus() {
  if (emojiMenu) emojiMenu.hidden = true;
  if (signatureMenu) signatureMenu.hidden = true;
  if (writerFormatMenu) writerFormatMenu.hidden = true;
}

function positionFloatingMenu(menu, anchor) {
  if (!menu || !anchor) return;
  const rect = anchor.getBoundingClientRect();
  menu.style.left = `${Math.min(rect.left, window.innerWidth - 220)}px`;
  menu.style.top = `${rect.bottom + 6}px`;
  menu.hidden = false;
}

function openSignatureManager() {
  hideFloatingMenus();
  setRichEditorHtml(signatureEditor, signatureValue, savedSignatureHtml());
  signatureModal.classList.add("is-open");
  signatureModal.setAttribute("aria-hidden", "false");
  document.body.classList.add("modal-open");
}

function closeSignatureManager() {
  signatureModal.classList.remove("is-open");
  signatureModal.setAttribute("aria-hidden", "true");
  if (!messageModal.classList.contains("is-open") && !composeModal.classList.contains("is-open")) {
    document.body.classList.remove("modal-open");
  }
}

function saveSignature() {
  const html = richEditorHtml(signatureEditor) || DEFAULT_SIGNATURE_HTML;
  localStorage.setItem(SIGNATURE_STORAGE_KEY, html);
  setActivity("Signature saved.");
}

function insertSavedSignature() {
  if (!state.activeEditorId) return;
  insertHtmlIntoEditor(state.activeEditorId, savedSignatureHtml());
  hideFloatingMenus();
}

const MAX_ATTACHMENT_TOTAL_BYTES = 20 * 1024 * 1024;

function attachmentFiles(input) {
  return Array.from(input?.files || []);
}

function formatFileSize(bytes) {
  const size = Number(bytes || 0);
  if (size >= 1024 * 1024) return `${(size / (1024 * 1024)).toFixed(1)} MB`;
  if (size >= 1024) return `${Math.ceil(size / 1024)} KB`;
  return `${size} B`;
}

function updateAttachmentList(input, list) {
  if (!list) return;
  const files = attachmentFiles(input);
  if (!files.length) {
    list.innerHTML = "";
    return;
  }
  list.innerHTML = files
    .map((file) => `<span class="attachment-chip">${escapeHtml(file.name)} <small>${escapeHtml(formatFileSize(file.size))}</small></span>`)
    .join("");
}

function fileToAttachment(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error(`Could not read ${file.name}.`));
    reader.onload = () => {
      const result = String(reader.result || "");
      const commaIndex = result.indexOf(",");
      resolve({
        filename: file.name,
        content_type: file.type || "application/octet-stream",
        data: commaIndex >= 0 ? result.slice(commaIndex + 1) : result,
      });
    };
    reader.readAsDataURL(file);
  });
}

async function readAttachments(input) {
  const files = attachmentFiles(input);
  const totalSize = files.reduce((sum, file) => sum + Number(file.size || 0), 0);
  if (totalSize > MAX_ATTACHMENT_TOTAL_BYTES) {
    throw new Error("Attachments exceed the 20 MB limit.");
  }
  return Promise.all(files.map(fileToAttachment));
}

function clearAttachments(input, list) {
  if (input) input.value = "";
  updateAttachmentList(input, list);
}

function renderInlineMarkdown(text) {
  return escapeHtml(text)
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/__([^_]+)__/g, "<strong>$1</strong>");
}

function renderMarkdownSummary(value) {
  const text = displayText(value);
  if (!text) {
    generatedSummary.innerHTML = '<p class="markdown-placeholder">Generated summary will appear here.</p>';
    return;
  }

  const html = [];
  let listOpen = false;
  const closeList = () => {
    if (listOpen) {
      html.push("</ul>");
      listOpen = false;
    }
  };

  for (const rawLine of text.split("\n")) {
    const line = rawLine.trim();
    if (!line) {
      closeList();
      continue;
    }

    const hashHeading = line.match(/^(#{1,4})\s+(.+)$/);
    const boldHeading = line.match(/^\*\*(.+)\*\*$/);
    if (hashHeading || boldHeading) {
      closeList();
      html.push(`<h5>${renderInlineMarkdown(hashHeading?.[2] || boldHeading?.[1] || "")}</h5>`);
      continue;
    }

    const bullet = line.match(/^[-*]\s+(.+)$/);
    const numbered = line.match(/^\d+[.)]\s+(.+)$/);
    if (bullet || numbered) {
      if (!listOpen) {
        html.push("<ul>");
        listOpen = true;
      }
      html.push(`<li>${renderInlineMarkdown(bullet?.[1] || numbered?.[1] || "")}</li>`);
      continue;
    }

    closeList();
    html.push(`<p>${renderInlineMarkdown(line)}</p>`);
  }

  closeList();
  generatedSummary.innerHTML = html.join("");
}

function cleanSummaryPlaceholders(value) {
  let text = displayText(value || "");
  const placeholderSections = [
    /(?:^|\n\n)Previous messages:\s*(?:[-*]\s*)?None\.?(?=\n\n|$)/gi,
    /(?:^|\n\n)User action:\s*(?:[-*]\s*)?No clear user action requested(?:\s*\([^)]*\))?\.?(?=\n\n|$)/gi,
    /(?:^|\n\n)Notes:\s*(?:[-*]\s*)?No major caveats\.?(?=\n\n|$)/gi,
  ];
  for (const pattern of placeholderSections) {
    text = text.replace(pattern, "");
  }
  return text.replace(/\n{3,}/g, "\n\n").trim();
}

function displayMessageBody(value) {
  const text = displayText(value);
  return text
    .replace(/[ \t]+(-{3,}\s*Forwarded message\s*-{3,})/gi, "\n\n$1\n")
    .replace(/[ \t]+(On\s(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun),?\s.+?\swrote:)/gi, "\n\n$1\n")
    .replace(/[ \t]+(On\s\d{1,2}\s\w+\s\d{4}.+?\swrote:)/gi, "\n\n$1\n")
    .replace(/[ \t]+(From:\s)/gi, "\n$1")
    .replace(/[ \t]+(Date:\s)/gi, "\n$1")
    .replace(/[ \t]+(Subject:\s)/gi, "\n$1")
    .replace(/[ \t]+(To:\s)/gi, "\n$1")
    .replace(/(?:^|[ \t])>{1,4}[ \t]+/gm, "\n> ")
    .replace(/\n{4,}/g, "\n\n\n")
    .trim();
}

function readableMessageText(value) {
  const text = displayMessageBody(value);
  if (text.includes("\n")) return text;

  return text
    .replace(/[ \t]+((?:Device|Verification code|Thanks):\s)/gi, "\n$1")
    .replace(/[ \t]+((?:If you|If you'd|A sign in|To complete|Visit|See)\b)/g, "\n\n$1")
    .replace(/[ \t]+(The [A-Z][A-Za-z0-9 .'-]+ Team\b)/g, "\n$1")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function messageBodySource(message, fallbackText = "") {
  return (
    message?.display_text ||
    message?.body ||
    message?.snippet ||
    message?.summary ||
    message?.skip_reason ||
    fallbackText
  );
}

function threadEntryBody(entry) {
  return readableMessageText(messageBodySource(entry));
}

function threadEntryId(entry) {
  return String(entry?.id || entry?.message_id || "");
}

function threadEntryTime(entry, fallbackIndex) {
  const rawDate = entry?.date || [entry?.message_date, entry?.message_time].filter(Boolean).join(" ");
  const parsed = new Date(rawDate);
  return {
    raw: rawDate || "",
    value: Number.isNaN(parsed.getTime()) ? fallbackIndex : parsed.getTime(),
  };
}

function selectedThreadMessages(message) {
  const currentId = threadEntryId(message);
  const entries = [];
  const seen = new Set();

  for (const entry of Array.isArray(message?.thread_messages) ? message.thread_messages : []) {
    const entryId = threadEntryId(entry);
    if (entryId && entryId === currentId) continue;
    if (entryId && seen.has(entryId)) continue;
    entries.push(entry);
    if (entryId) seen.add(entryId);
  }

  entries.push({
    ...message,
    id: message?.id || message?.message_id,
    message_id: message?.message_id || message?.id,
  });

  return entries
    .map((entry, index) => ({ entry, index, time: threadEntryTime(entry, index) }))
    .sort((left, right) => left.time.value - right.time.value || left.index - right.index)
    .map(({ entry }) => entry);
}

function selectedMessageDisplay(message) {
  const entries = selectedThreadMessages(message);
  if (messageThreadCount(message) <= 1 || entries.length <= 1) {
    return readableMessageText(messageBodySource(message, "No preview available."));
  }

  return entries
    .map((entry, index) => {
      const isLatest = index === entries.length - 1;
      const title = isLatest ? "Latest message" : `Thread message ${index + 1}`;
      const meta = [
        title,
        entry?.from ? `From: ${displayText(entry.from)}` : "",
        entry?.to ? `To: ${displayText(entry.to)}` : "",
        entry?.date ? `Date: ${formatDate(entry)}` : "",
        entry?.subject ? `Subject: ${displayText(entry.subject)}` : "",
      ].filter(Boolean);
      return `${meta.join("\n")}\n\n${threadEntryBody(entry) || "(No body available.)"}`;
    })
    .join("\n\n------------------------------------------------\n\n");
}

function senderInitial(sender) {
  const clean = displayText(sender || "").replace(/<[^>]+>/g, "").trim();
  return (clean.match(/[A-Za-z0-9]/)?.[0] || "?").toUpperCase();
}

function senderName(sender) {
  const clean = displayText(sender || "Unknown sender").trim();
  const nameMatch = clean.match(/^"?([^"<]+?)"?\s*</);
  return (nameMatch?.[1] || clean.replace(/<[^>]+>/g, "") || "Unknown sender").trim();
}

function senderAddress(sender) {
  const clean = displayText(sender || "").trim();
  const addressMatch = clean.match(/<([^>]+)>/);
  return (addressMatch?.[1] || clean).trim();
}

function splitQuotedBody(text) {
  const body = displayMessageBody(text || "");
  const quotePatterns = [
    /\n(?=On\s(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun),?\s.+?\swrote:)/i,
    /\n(?=On\s\d{1,2}\s\w+\s\d{4}.+?\swrote:)/i,
    /\n(?=-{3,}\s*Forwarded message\s*-{3,})/i,
  ];
  let splitIndex = -1;
  for (const pattern of quotePatterns) {
    const match = body.match(pattern);
    if (match?.index >= 0 && (splitIndex < 0 || match.index < splitIndex)) {
      splitIndex = match.index;
    }
  }

  if (splitIndex < 0) {
    const lines = body.split("\n");
    const firstQuotedLine = lines.findIndex((line, index) => {
      if (index === 0 || !line.trim().startsWith(">")) return false;
      const nextLines = lines.slice(index, index + 3);
      return nextLines.length >= 2 && nextLines.every((candidate) => candidate.trim().startsWith(">") || !candidate.trim());
    });
    if (firstQuotedLine > 0) {
      return {
        main: lines.slice(0, firstQuotedLine).join("\n").trim(),
        quoted: lines.slice(firstQuotedLine).join("\n").trim(),
      };
    }
    return { main: body.trim(), quoted: "" };
  }

  return {
    main: body.slice(0, splitIndex).trim(),
    quoted: body.slice(splitIndex).trim(),
  };
}

function bodyTextToHtml(text) {
  const clean = readableMessageText(text || "").trim();
  if (!clean) return '<p class="empty-message">(No body available.)</p>';

  const paragraphs = clean
    .replace(/^>\s?/gm, "")
    .split(/\n{2,}/)
    .map((paragraph) => paragraph.trim())
    .filter(Boolean);

  if (!paragraphs.length) return '<p class="empty-message">(No body available.)</p>';
  return paragraphs
    .map((paragraph) => `<p>${paragraph.split(/\n/).map((line) => linkifyEscapedText(escapeHtml(line))).join("<br>")}</p>`)
    .join("");
}

function linkifyEscapedText(text) {
  return String(text || "").replace(
    /(https?:\/\/[^\s<]+)/g,
    (url) => {
      const cleanUrl = url.replace(/[),.;:!?]+$/g, "");
      const trailing = url.slice(cleanUrl.length);
      return `<a href="${cleanUrl}" target="_blank" rel="noopener noreferrer nofollow">${cleanUrl}</a>${trailing}`;
    },
  );
}

function linkifyHtmlUrls(html) {
  let insideAnchor = false;
  return String(html || "")
    .split(/(<[^>]+>)/g)
    .map((part) => {
      if (!part) return "";
      if (part.startsWith("<")) {
        if (/^<a\b/i.test(part)) insideAnchor = true;
        if (/^<\/a\b/i.test(part)) insideAnchor = false;
        return part;
      }
      return insideAnchor ? part : linkifyEscapedText(part);
    })
    .join("");
}

function threadSnippet(entry) {
  const body = splitQuotedBody(threadEntryBody(entry)).main || threadEntryBody(entry);
  return displayText(body).replace(/\s+/g, " ").slice(0, 180);
}

function threadEntryHtml(entry, index, total) {
  const isLatest = index === total - 1;
  const body = splitQuotedBody(threadEntryBody(entry));
  const from = displayText(entry?.from || "Unknown sender");
  const to = displayText(entry?.to || "");
  const subject = displayText(entry?.subject || "");
  const date = entry?.date ? formatDate(entry) : "";
  const details = [
    to ? `to ${escapeHtml(to)}` : "",
    subject ? `subject ${escapeHtml(subject)}` : "",
  ].filter(Boolean);

  const content = `
    <div class="gmail-message-content">
      <header class="gmail-message-header">
        <div class="gmail-sender-line">
          <strong>${escapeHtml(senderName(from))}</strong>
          <span>${escapeHtml(senderAddress(from))}</span>
        </div>
        <time>${escapeHtml(date)}</time>
      </header>
      ${details.length ? `<div class="gmail-message-details">${details.join(" · ")}</div>` : ""}
      <div class="gmail-message-body">${bodyTextToHtml(body.main)}</div>
      ${
        body.quoted
          ? `<details class="gmail-quoted"><summary>Show quoted text</summary><div>${bodyTextToHtml(body.quoted)}</div></details>`
          : ""
      }
    </div>
  `;

  if (!isLatest) {
    return `
      <details class="gmail-thread-message gmail-thread-collapsed">
        <summary>
          <span class="gmail-avatar" aria-hidden="true">${escapeHtml(senderInitial(from))}</span>
          <span class="gmail-collapsed-main">
            <span><strong>${escapeHtml(senderName(from))}</strong> <small>${escapeHtml(threadSnippet(entry))}</small></span>
            <time>${escapeHtml(date)}</time>
          </span>
        </summary>
        ${content}
      </details>
    `;
  }

  return `
    <article class="gmail-thread-message latest">
      <div class="gmail-avatar" aria-hidden="true">${escapeHtml(senderInitial(from))}</div>
      ${content}
    </article>
  `;
}

function selectedMessageThreadHtml(message) {
  const entries = selectedThreadMessages(message);
  if (!entries.length) return "";

  return `
    <div class="gmail-thread-view">
      ${entries.map((entry, index) => threadEntryHtml(entry, index, entries.length)).join("")}
    </div>
  `;
}

function selectedMessageHtml(message) {
  return String(message?.display_html || "").trim();
}

function threadEntryDisplayHtml(entry) {
  return String(entry?.display_html || "").trim();
}

function threadEntryIframeHtml(entry, index, total) {
  const from = displayText(entry?.from || "Unknown sender");
  const to = displayText(entry?.to || "");
  const subject = displayText(entry?.subject || "");
  const date = entry?.date ? formatDate(entry) : "";
  const details = [
    to ? `to ${escapeHtml(to)}` : "",
    subject ? `subject ${escapeHtml(subject)}` : "",
  ].filter(Boolean);
  const html = threadEntryDisplayHtml(entry);
  const body = splitQuotedBody(threadEntryBody(entry));
  const bodyHtml = html || bodyTextToHtml(body.main || threadEntryBody(entry));
  const content = `
    <header class="gmail-message-header">
      <div class="gmail-sender-line">
        <strong>${escapeHtml(senderName(from))}</strong>
        <span>${escapeHtml(senderAddress(from))}</span>
      </div>
      <time>${escapeHtml(date)}</time>
    </header>
    ${details.length ? `<div class="gmail-message-details">${details.join(" · ")}</div>` : ""}
    <div class="gmail-message-body">${bodyHtml}</div>
  `;

  return `
    <article class="gmail-thread-message${index === total - 1 ? " latest" : ""}">
      ${content}
    </article>
  `;
}

function selectedMessageIframeHtml(message) {
  const entries = selectedThreadMessages(message);
  if (entries.length > 1) {
    return `
      <div class="gmail-thread-view iframe-thread-view">
        ${entries.map((entry, index) => threadEntryIframeHtml(entry, index, entries.length)).join("")}
      </div>
    `;
  }
  return selectedMessageHtml(message);
}

function selectedMessagePlainText(message, fallbackText = "No preview available.") {
  return selectedMessageDisplay(message) || readableMessageText(message?.display_text || "") || fallbackText;
}

function buildEmailPreviewDocument(emailHtml) {
  const linkedEmailHtml = linkifyHtmlUrls(emailHtml);
  return `<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta http-equiv="Content-Security-Policy" content="script-src 'none'; object-src 'none'; frame-src 'none'; form-action 'none'; connect-src 'none'">
    <base target="_blank">
    <style>
      html, body {
        margin: 0;
        padding: 0;
        background: #fff;
        color: #202124;
        font-family: Arial, Helvetica, sans-serif;
        line-height: 1.45;
      }
      body {
        overflow-wrap: anywhere;
      }
      img {
        max-width: 100%;
        height: auto;
      }
      table {
        max-width: 100%;
      }
      a {
        color: #0b57d0;
      }
      .gmail-thread-view {
        display: grid;
        gap: 16px;
        padding: 16px;
      }
      .gmail-thread-message {
        border: 1px solid #dadce0;
        border-radius: 12px;
        padding: 16px;
        background: #fff;
      }
      .gmail-thread-message summary {
        cursor: pointer;
        color: #3c4043;
        list-style-position: inside;
        margin-bottom: 12px;
      }
      .gmail-collapsed-main {
        display: inline-flex;
        justify-content: space-between;
        gap: 12px;
        width: calc(100% - 24px);
        vertical-align: top;
      }
      .gmail-collapsed-main small {
        color: #5f6368;
        font-weight: 400;
      }
      .gmail-message-header {
        display: flex;
        justify-content: space-between;
        gap: 12px;
        margin-bottom: 10px;
        color: #5f6368;
        font-size: 14px;
      }
      .gmail-sender-line {
        display: grid;
        gap: 2px;
      }
      .gmail-sender-line strong {
        color: #202124;
      }
      .gmail-message-details {
        margin-bottom: 12px;
        color: #5f6368;
        font-size: 13px;
      }
      .gmail-message-body > *:first-child {
        margin-top: 0;
      }
      .gmail-message-body > *:last-child {
        margin-bottom: 0;
      }
    </style>
  </head>
  <body>${linkedEmailHtml}</body>
</html>`;
}

function setSelectedPlainMessage(text, isLoading = false) {
  selectedMessagePlain.textContent = text;
  selectedMessagePlain.classList.toggle("is-loading", isLoading);
}

function setSelectedThreadHtml(html) {
  selectedMessagePlain.innerHTML = html;
  selectedMessagePlain.classList.remove("is-loading");
}

function renderEmailHtmlFrame(emailHtml, fallbackText = "Rendering email preview...") {
  const renderId = String(++state.emailFrameRenderId);
  selectedMessageFrame.dataset.renderId = renderId;
  selectedMessageFrame.dataset.loadedRenderId = "";

  selectedMessageFrame.onload = () => {
    if (selectedMessageFrame.dataset.renderId !== renderId) return;

    if (selectedMessageFrame.dataset.loadedRenderId === renderId) {
      restoreSelectedEmailFrame("Restoring email preview...");
      return;
    }

    selectedMessageFrame.dataset.loadedRenderId = renderId;
    selectedMessagePlain.hidden = true;
    selectedMessagePlain.classList.remove("is-loading");
    selectedMessageFrame.hidden = false;
  };
  selectedMessageFrame.srcdoc = buildEmailPreviewDocument(emailHtml);
  selectedMessagePlain.hidden = true;
  selectedMessagePlain.classList.remove("is-loading");
  selectedMessageFrame.hidden = false;
}

function clearEmailHtmlFrame() {
  selectedMessageFrame.onload = null;
  selectedMessageFrame.hidden = true;
  selectedMessageFrame.removeAttribute("srcdoc");
  delete selectedMessageFrame.dataset.renderId;
  delete selectedMessageFrame.dataset.loadedRenderId;
}

function restoreSelectedEmailFrame(fallbackText = "Restoring email preview...") {
  if (!state.selected || !isModalOpen()) return;
  const html = selectedMessageIframeHtml(state.selected);
  if (!html) return;
  renderEmailHtmlFrame(html, fallbackText);
}

function renderSelectedMessageBody(message, fallbackText = "No preview available.") {
  const loadingFullMessage = fallbackText === "Loading full message..." && message && !hasUsefulFullMessage(messageKey(message));
  const plainText = loadingFullMessage ? fallbackText : (message ? selectedMessagePlainText(message, fallbackText) : fallbackText);
  selectedSummary.value = plainText;

  const html = message ? selectedMessageIframeHtml(message) : "";
  if (html) {
    renderEmailHtmlFrame(html, "Rendering email preview...");
    return;
  }

  clearEmailHtmlFrame();
  selectedMessagePlain.hidden = false;
  if (loadingFullMessage) {
    setSelectedPlainMessage(fallbackText, true);
    return;
  }
  const threadHtml = message ? selectedMessageThreadHtml(message) : "";
  if (threadHtml) {
    setSelectedThreadHtml(threadHtml);
    return;
  }
  setSelectedPlainMessage(plainText, false);
}

function mergeFullMessage(fullMessage) {
  if (!fullMessage) return null;
  const cached = rememberFullMessage(fullMessage);
  if (!cached || !state.selected) return cached;

  const key = messageKey(cached);
  if (key && messageKey(state.selected) !== key) return cached;

  const merged = {
    ...state.selected,
    ...cached,
    message_id: state.selected.message_id || key,
  };
  state.selected = merged;
  renderSelectedMessage();
  return merged;
}

async function loadFullMessage(messageId) {
  saveEmail();
  if (!state.email || !messageId) return;
  const threadId = state.selected?.thread_id || "";
  if (hasUsefulFullMessage(messageId)) {
    mergeFullMessage(cachedFullMessage(messageId));
    fetchFullMessage(messageId, { timeoutMs: 30000, markRead: true, threadId })
      .then((fullMessage) => {
        if (selectedMessageId.value !== messageId) return;
        mergeFullMessage(fullMessage);
      })
      .catch((error) => {
        setActivity(error.message);
      });
    return;
  }
  renderSelectedMessageBody(state.selected, "Loading full message...");
  try {
    if (selectedMessageId.value !== messageId) return;
    const fullMessage = await fetchFullMessage(messageId, { timeoutMs: 30000, markRead: true, threadId });
    if (selectedMessageId.value !== messageId) return;
    mergeFullMessage(fullMessage);
    setActivity("Full message loaded.");
  } catch (error) {
    renderSelectedMessageBody(state.selected, "Could not load full message.");
    setActivity(error.message);
  }
}

async function checkHealth() {
  healthDot.classList.remove("ok", "bad");
  healthText.textContent = "Checking API";
  try {
    const data = await requestJson("/health", { method: "GET", headers: {} });
    healthDot.classList.add("ok");
    healthText.textContent = data.status === "ok" ? "API healthy" : "API reachable";
  } catch (error) {
    healthDot.classList.add("bad");
    healthText.textContent = "API unavailable";
    setActivity(error.message);
  }
}

async function loadMessages(button, showLoading = true, page = 1, resetPageState = true) {
  saveEmail();
  if (!state.email) {
    setActivity("Enter your Gmail address first.");
    return;
  }
  if (!state.isConnected) {
    state.isMailboxLoading = false;
    state.messageError = "Connect Gmail before refreshing this mailbox.";
    renderMessages();
    setActivity("Connect Gmail before refreshing this mailbox.");
    return;
  }
  const requestId = ++state.loadRequestId;
  const requestedMailbox = state.activeMailbox;
  const requestedTitle = state.activeMailboxTitle;
  const requestedCategory = normalizedInboxCategory();
  const requestedUnreadOnly = state.unreadOnly;
  const requestedDisplayTitle = mailboxDisplayTitle(requestedMailbox, requestedTitle, requestedCategory);
  const requestedPage = Math.max(1, Number(page || 1));
  if (resetPageState) resetPagination(requestedMailbox, requestedCategory);
  if (!canLoadMailboxPage(requestedMailbox, requestedPage, requestedCategory)) {
    setActivity(`Page ${requestedPage} is not available yet.`);
    return;
  }
  const requestedPageToken = pageStartToken(requestedMailbox, requestedPage, requestedCategory);
  state.isLoadingMessages = true;
  state.isMailboxLoading = showLoading;
  state.messageError = "";
  if (button) setBusy(button, true, "Refreshing...");
  if (showLoading) renderMessages();
  const localMessages = await readLocalMailboxPage(
    state.email,
    requestedMailbox,
    requestedUnreadOnly,
    requestedCategory,
    requestedPage,
  );
  state.isInitialMailboxSync = requestedPage === 1 && !localMessages.length && !readCachedMessages(
    state.email,
    requestedMailbox,
    requestedUnreadOnly,
    requestedCategory,
  ).length;
  if (state.isInitialMailboxSync) {
    renderMessages();
    setActivity("Syncing your Gmail data...");
  }
  if (localMessages.length) {
    state.isInitialMailboxSync = false;
    paginationState(requestedMailbox, requestedCategory).currentPage = requestedPage;
    setMessagesFromList(localMessages, requestedMailbox, requestedPage === 1, requestedPage);
    state.isLoadingMessages = false;
    state.isMailboxLoading = false;
    if (button) setBusy(button, false);
    renderMessages();
    updatePaginationControls();
    syncVisiblePageBodies(localMessages, MAILBOX_PAGE_BODY_SYNC_LIMIT, () => {
      scheduleMailboxMetadataBackfill(requestedMailbox, requestedCategory, requestedUnreadOnly);
    });
    setActivity(`Showing cached ${requestedDisplayTitle.toLowerCase()} page ${requestedPage}. Refreshing in background...`);
  }
  const viewLabel = state.unreadOnly ? "unread " : "";
  if (!state.isInitialMailboxSync && !localMessages.length) {
    setActivity(`Loading ${viewLabel}${requestedDisplayTitle.toLowerCase()} page ${requestedPage} from Gmail...`);
  }
  try {
    const data = await requestJson(messagesPath(requestedMailbox, MAILBOX_PAGE_SIZE, requestedPageToken, requestedUnreadOnly, requestedCategory));
    if (
      requestId !== state.loadRequestId ||
      requestedMailbox !== state.activeMailbox ||
      requestedCategory !== normalizedInboxCategory()
    ) return;

    setActiveMailbox(
      data.mailbox || state.activeMailbox,
      data.title || state.activeMailboxTitle,
      state.activeView !== "calendar",
    );
    setPageResult(state.activeMailbox, requestedPage, data.next_page_token, data.result_size_estimate, requestedCategory);
    setMessagesFromList(data.messages || [], state.activeMailbox, requestedPage === 1, requestedPage);
    state.isInitialMailboxSync = false;
    state.isMailboxLoading = false;
    state.messageError = "";
    setMailboxCount(state.activeMailbox, data.result_size_estimate ?? state.messages.length);
    const selectedId = state.selected?.message_id;
    if (selectedId && !isModalOpen()) {
      state.selected = state.messages.find((message) => message.message_id === selectedId) || null;
    }
    if (!state.selected && !isModalOpen()) {
      resetSelectedMessage();
    } else if (!isModalOpen()) {
      renderSelectedMessage();
    }
    renderMessages();
    if (state.messages.length) {
      setConnectionState(true);
    }
    if (requestedPage === 1) {
      loadCalendarEvents();
    }
    syncVisiblePageBodies(state.messages, MAILBOX_PAGE_BODY_SYNC_LIMIT, () => {
      scheduleMailboxMetadataBackfill(requestedMailbox, requestedCategory, requestedUnreadOnly);
    });
    setActivity(`Loaded ${viewLabel}${requestedDisplayTitle.toLowerCase()} page ${requestedPage}.`);
    // Safety net: if the Pub/Sub push never arrived for a message, analyze it
    // from what the live Gmail fetch just returned instead of losing it.
    enqueuePendingAnalysis(state.messages);
  } catch (error) {
    if (
      requestId !== state.loadRequestId ||
      requestedMailbox !== state.activeMailbox ||
      requestedCategory !== normalizedInboxCategory()
    ) return;

    const cachedMessages = (
      await readLocalMailboxPage(state.email, requestedMailbox, requestedUnreadOnly, requestedCategory, requestedPage)
    ) || readCachedMessages(state.email, requestedMailbox, requestedUnreadOnly, requestedCategory);
    if (cachedMessages.length) {
      setMessagesFromList(cachedMessages, state.activeMailbox, true, requestedPage);
      state.isInitialMailboxSync = false;
      state.isMailboxLoading = false;
      state.messageError = "";
      if (!isModalOpen()) resetSelectedMessage();
      renderMessages();
      setActivity(`${error.message} Showing ${cachedMessages.length} cached message${cachedMessages.length === 1 ? "" : "s"}.`);
      return;
    }
    state.messages = [];
    state.isInitialMailboxSync = false;
    state.isMailboxLoading = false;
    state.messageError = error.message;
    if (!isModalOpen()) resetSelectedMessage();
    renderMessages();
    setActivity(error.message);
  } finally {
    if (requestId === state.loadRequestId) {
      state.isLoadingMessages = false;
      state.isInitialMailboxSync = false;
      if (button) setBusy(button, false);
    }
  }
}

function updateMailSearchUi() {
  if (mailSearchInput) mailSearchInput.value = state.searchQuery;
  if (clearMailSearchButton) clearMailSearchButton.hidden = !state.isSearchActive;
}

function exitMailSearch() {
  if (!state.isSearchActive) return;
  state.isSearchActive = false;
  state.searchQuery = "";
  state.preSearchMailbox = "";
  state.preSearchMailboxTitle = "";
  updateMailSearchUi();
}

function clearMailSearch() {
  const restoreMailbox = state.preSearchMailbox || "inbox";
  const restoreTitle = state.preSearchMailboxTitle || titleForMailbox(restoreMailbox);
  exitMailSearch();
  setActiveMailbox(restoreMailbox, restoreTitle);
  resetSelectedMessage();
  state.messages = [];
  state.messageError = "";
  state.isMailboxLoading = true;
  state.isInitialMailboxSync = false;
  renderMessages();
  loadMessages(document.querySelector("#refreshMessages"));
}

async function performMailSearch(rawQuery) {
  saveEmail();
  const query = String(rawQuery || "").trim();
  if (!query) {
    setActivity("Enter a search term first.");
    return;
  }
  if (!state.email) {
    setActivity("Enter your Gmail address first.");
    return;
  }
  if (!state.isConnected) {
    setActivity("Connect Gmail before searching.");
    return;
  }

  const requestId = ++state.loadRequestId;
  setActiveView("mailbox");
  if (!state.isSearchActive) {
    state.preSearchMailbox = state.activeMailbox;
    state.preSearchMailboxTitle = state.activeMailboxTitle;
  }
  state.activeMailbox = "search";
  state.activeMailboxTitle = `Search results for "${query}"`;
  state.isSearchActive = true;
  state.searchQuery = query;
  document.querySelectorAll(".mailbox-link").forEach((item) => item.classList.remove("active"));
  mailboxEyebrow.textContent = "AI Mail";
  mailboxTitle.textContent = state.activeMailboxTitle;
  updateMailSearchUi();
  resetSelectedMessage();
  state.messages = [];
  state.messageError = "";
  state.isMailboxLoading = true;
  state.isInitialMailboxSync = false;
  setBusy(mailSearchButton, true, "Searching...");
  renderMessages();
  setActivity(`Searching Gmail for "${query}"...`);

  try {
    const data = await requestJson(searchMessagesPath(query));
    if (requestId !== state.loadRequestId) return;
    setMessagesFromList(data.messages || [], "search", false, 1);
    state.isMailboxLoading = false;
    state.messageError = "";
    renderMessages();
    const count = state.messages.length;
    setActivity(`Found ${count} message${count === 1 ? "" : "s"} for "${query}".`);
  } catch (error) {
    if (requestId !== state.loadRequestId) return;
    state.messages = [];
    state.isMailboxLoading = false;
    state.messageError = error.message;
    renderMessages();
    setActivity(error.message);
  } finally {
    if (requestId === state.loadRequestId) setBusy(mailSearchButton, false);
  }
}

async function loadMailboxPage(page, button = null) {
  saveEmail();
  if (!state.email || !state.isConnected || state.isLoadingPage || state.isMailboxLoading) return;

  const requestedPage = Math.max(1, Number(page || 1));
  const requestedCategory = normalizedInboxCategory();
  if (!canLoadMailboxPage(state.activeMailbox, requestedPage, requestedCategory)) {
    updatePaginationControls();
    return;
  }

  const requestId = ++state.loadRequestId;
  const requestedMailbox = state.activeMailbox;
  const requestedTitle = state.activeMailboxTitle;
  const requestedUnreadOnly = state.unreadOnly;
  const requestedDisplayTitle = mailboxDisplayTitle(requestedMailbox, requestedTitle, requestedCategory);
  const requestedPageToken = pageStartToken(requestedMailbox, requestedPage, requestedCategory);
  state.isLoadingPage = true;
  state.isMailboxLoading = true;
  if (button) setBusy(button, true, "Loading...");
  updatePaginationControls();
  renderMessages();
  const localMessages = await readLocalMailboxPage(
    state.email,
    requestedMailbox,
    requestedUnreadOnly,
    requestedCategory,
    requestedPage,
  );
  if (localMessages.length) {
    paginationState(requestedMailbox, requestedCategory).currentPage = requestedPage;
    setMessagesFromList(localMessages, requestedMailbox, requestedPage === 1, requestedPage);
    state.isLoadingPage = false;
    state.isMailboxLoading = false;
    if (button) setBusy(button, false);
    renderMessages();
    updatePaginationControls();
    syncVisiblePageBodies(localMessages, MAILBOX_PAGE_BODY_SYNC_LIMIT, () => {
      scheduleMailboxMetadataBackfill(requestedMailbox, requestedCategory, requestedUnreadOnly);
    });
    setActivity(`Showing cached ${requestedDisplayTitle.toLowerCase()} page ${requestedPage}. Refreshing in background...`);
  }
  const viewLabel = requestedUnreadOnly ? "unread " : "";
  if (!localMessages.length) {
    setActivity(`Loading ${viewLabel}${requestedDisplayTitle.toLowerCase()} page ${requestedPage}...`);
  }

  try {
    const data = await requestJson(messagesPath(requestedMailbox, MAILBOX_PAGE_SIZE, requestedPageToken, requestedUnreadOnly, requestedCategory), {
      timeoutMs: 30000,
    });
    if (
      requestId !== state.loadRequestId ||
      requestedMailbox !== state.activeMailbox ||
      requestedCategory !== normalizedInboxCategory()
    ) return;

    setMessagesFromList(data.messages || [], state.activeMailbox, requestedPage === 1, requestedPage);
    setPageResult(state.activeMailbox, requestedPage, data.next_page_token, data.result_size_estimate, requestedCategory);
    setMailboxCount(state.activeMailbox, data.result_size_estimate ?? state.messages.length);
    state.isMailboxLoading = false;
    renderMessages();
    syncVisiblePageBodies(data.messages || [], MAILBOX_PAGE_BODY_SYNC_LIMIT, () => {
      scheduleMailboxMetadataBackfill(requestedMailbox, requestedCategory, requestedUnreadOnly);
    });
    setActivity(`Loaded ${viewLabel}${requestedDisplayTitle.toLowerCase()} page ${requestedPage}.`);
  } catch (error) {
    if (
      requestId !== state.loadRequestId ||
      requestedMailbox !== state.activeMailbox ||
      requestedCategory !== normalizedInboxCategory()
    ) return;

    const cachedMessages = await readLocalMailboxPage(
      state.email,
      requestedMailbox,
      requestedUnreadOnly,
      requestedCategory,
      requestedPage,
    );
    if (cachedMessages.length) {
      setMessagesFromList(cachedMessages, state.activeMailbox, requestedPage === 1, requestedPage);
      state.isMailboxLoading = false;
      renderMessages();
      setActivity(`${error.message} Showing cached page ${requestedPage}.`);
      return;
    }
    state.isMailboxLoading = false;
    renderMessages();
    setActivity(error.message);
  } finally {
    if (requestId === state.loadRequestId) {
      state.isLoadingPage = false;
      setBusy(button, false);
      updatePaginationControls();
    }
  }
}

async function autoRefreshMessages() {
  saveEmail();
  if (!state.email || !state.isConnected || document.hidden || state.isLoadingMessages || state.isMailboxLoading) return;
  if (paginationState().currentPage !== 1) return;
  const requestId = ++state.loadRequestId;
  const requestedMailbox = state.activeMailbox;
  const requestedCategory = normalizedInboxCategory();
  state.isLoadingMessages = true;
  try {
    const data = await requestJson(messagesPath(requestedMailbox, MAILBOX_PAGE_SIZE, "", state.unreadOnly, requestedCategory));
    if (
      requestId !== state.loadRequestId ||
      requestedMailbox !== state.activeMailbox ||
      requestedCategory !== normalizedInboxCategory()
    ) return;

    const nextMessages = data.messages || [];
    setMailboxCount(requestedMailbox, data.result_size_estimate ?? nextMessages.length);
    setPageResult(requestedMailbox, 1, data.next_page_token, data.result_size_estimate, requestedCategory);
    const mergedMessages = mergeMessageList(nextMessages);
    if (JSON.stringify(mergedMessages) === JSON.stringify(state.messages)) {
      renderMessages();
      return;
    }

    const previousCount = state.messages.length;
    const selectedId = state.selected?.message_id;
    setMessagesFromList(mergedMessages, requestedMailbox, true, 1);
    state.messageError = "";
    if (selectedId && !isModalOpen()) {
      state.selected = state.messages.find((message) => message.message_id === selectedId) || state.selected;
      renderSelectedMessage();
    }
    renderMessages();
    if (state.messages.length) {
      setConnectionState(true);
    }
    syncVisiblePageBodies(state.messages);
    if (state.messages.length > previousCount) {
      setActivity(`Loaded ${state.messages.length - previousCount} new ${state.activeMailboxTitle.toLowerCase()} message${state.messages.length - previousCount === 1 ? "" : "s"}.`);
    }
    enqueuePendingAnalysis(state.messages);
    loadCalendarEvents();
  } catch {
    // Keep the current list visible; manual refresh shows detailed errors.
  } finally {
    if (requestId === state.loadRequestId) {
      state.isLoadingMessages = false;
    }
  }
}

async function loadCalendarEvents() {
  saveEmail();
  if (!state.email || !state.isConnected) return;

  const cachedEvents = readCachedCalendarEvents(state.email);
  if (cachedEvents.length && !state.calendarEvents.length) {
    state.calendarEvents = cachedEvents;
    renderCalendarEvents();
  }

  try {
    const data = await requestJson(calendarEventsPath());
    const nextEvents = data.events || [];
    if (nextEvents.length || !state.calendarEvents.length) {
      state.calendarEvents = nextEvents;
      writeCachedCalendarEvents(state.email, state.calendarEvents);
    }
    renderCalendarEvents();
  } catch {
    if (!state.calendarEvents.length && cachedEvents.length) {
      state.calendarEvents = cachedEvents;
      renderCalendarEvents();
    }
    // Calendar loading should not block inbox browsing.
  }
}

async function acknowledgeEventNotification(messageId) {
  if (!state.email || !messageId) return;
  try {
    await requestJson("/notifications/events/ack", {
      method: "POST",
      body: JSON.stringify({
        email: state.email,
        message_id: messageId,
      }),
    });
  } catch {
    // The next poll can retry if acknowledgement fails.
  }
}

function showEventToast(event) {
  const key = String(event.message_id || event.start_at || event.title || "");
  if (!key || state.shownEventNotifications.has(key)) return;
  state.shownEventNotifications.add(key);

  const toast = document.createElement("section");
  toast.className = "event-toast";
  toast.dataset.messageId = String(event.message_id || "");
  toast.innerHTML = `
    <div>
      <p class="eyebrow">Calendar notification</p>
      <strong>${escapeHtml(displayText(event.title || event.subject || "Email event"))}</strong>
      <span>${escapeHtml(formatEventTime(event.start_at))}</span>
    </div>
    <div class="toast-actions">
      <button class="secondary" type="button" data-calendar-response="accepted">Approve</button>
      <button class="secondary" type="button" data-calendar-response="declined">Deny</button>
      <button class="secondary" type="button" data-action="open">Open</button>
      <button class="icon-button" type="button" data-action="dismiss" aria-label="Dismiss" title="Dismiss">x</button>
    </div>
  `;
  const dismissTimer = setTimeout(() => toast.remove(), 12000);
  const stopAutoDismiss = () => clearTimeout(dismissTimer);
  toast.querySelector('[data-action="open"]').addEventListener("click", () => {
    stopAutoDismiss();
    window.openEmailReminderMessage(event.message_id);
    toast.remove();
  });
  toast.querySelector('[data-action="dismiss"]').addEventListener("click", () => {
    stopAutoDismiss();
    toast.remove();
  });
  toast.querySelector('[data-calendar-response="accepted"]').addEventListener("click", async () => {
    stopAutoDismiss();
    await sendCalendarEventResponse(toast, "accepted");
    toast.remove();
  });
  toast.querySelector('[data-calendar-response="declined"]').addEventListener("click", async () => {
    stopAutoDismiss();
    await sendCalendarEventResponse(toast, "declined");
    toast.remove();
  });
  toastContainer.appendChild(toast);
  acknowledgeEventNotification(event.message_id);
}

async function pollEventNotifications() {
  saveEmail();
  if (!state.email || !state.isConnected || document.hidden) return;

  try {
    const data = await requestJson(dueNotificationsPath());
    for (const event of data.notifications || []) {
      showEventToast(event);
    }
    state.pendingResponses = data.pending_responses || [];
    renderCalendarEvents();
  } catch {
    // Notification polling should not interrupt normal inbox use.
  }
}

async function preloadMailbox(mailbox) {
  if (!state.email || !state.isConnected || !mailbox) return;

  const requestedMailbox = String(mailbox || "");
  if (requestedMailbox === "more") return;
  const unreadData = await requestJson(messagesPath(requestedMailbox, 1, "", true));
  const unreadEstimate = Number(unreadData.result_size_estimate || 0);
  setMailboxUnreadIndicator(requestedMailbox, unreadEstimate > 0 || Boolean((unreadData.messages || []).length));
}

async function preloadAllMailboxes() {
  saveEmail();
  if (
    !state.email ||
    !state.isConnected ||
    document.hidden ||
    state.isPreloadingMailboxes ||
    state.isLoadingMessages ||
    state.isLoadingPage ||
    state.isMailboxLoading
  ) return;

  state.isPreloadingMailboxes = true;
  const mailboxes = mailboxKeys();
  try {
    for (const mailbox of mailboxes) {
      await preloadMailbox(mailbox);
    }
    setActivity("Mailbox tabs auto-refreshed.");
  } catch (error) {
    setActivity(error.message);
  } finally {
    state.isPreloadingMailboxes = false;
  }
}

async function refreshConnectionStatus() {
  try {
    const data = await requestJson("/auth/status", {
      method: "GET",
      headers: {},
    });
    if (data.email) {
      emailInput.value = data.email;
      saveEmail();
    }
    const connected = Boolean(data.connected);
    setConnectionState(connected);
    return connected;
  } catch {
    if (!state.messages.length && !readCachedMessages(state.email).length) {
      setConnectionState(false);
    }
    return false;
  }
}

async function login(button) {
  redirectToGoogleLogin();
}

function clearBrowserSession() {
  const email = state.email;
  localStorage.removeItem("emailReminders.email");
  if (email) localStorage.removeItem(calendarCacheKey(email));
  state.email = "";
  state.messages = [];
  state.calendarEvents = [];
  state.mailboxPagination = {};
  state.isInitialMailboxSync = false;
  state.fullMessages = {};
  state.fullMessageRequests.clear();
  state.analysisEnqueued.clear();

  for (const key of Object.keys(sessionStorage)) {
    if (key.startsWith("emailReminders.messages.")) {
      sessionStorage.removeItem(key);
    }
  }
}

async function logout(button) {
  setBusy(button, true, "Signing out...");
  clearBrowserSession();
  window.location.assign("/auth/logout");
}

function handleAuthButton(button) {
  if (state.isConnected) {
    logout(button);
    return;
  }
  login(button);
}

async function generateReply(button) {
  saveEmail();
  const messageId = selectedMessageId.value.trim();
  if (!state.email || !messageId) {
    setActivity("Select a message first.");
    return;
  }

  setBusy(button, true, "Generating...");
  setActivity("Generating reply draft...");
  try {
    const data = await requestJson("/reply/message", {
      method: "POST",
      timeoutMs: 180000,
      body: JSON.stringify({
        email: state.email,
        message_id: messageId,
        intent: richEditorPlainText(replyIntentEditor),
      }),
    });
    const suggested = data?.result?.reply?.suggested_reply;
    if (typeof suggested !== "string") {
      setActivity("Reply response was missing result.reply.suggested_reply.");
      return;
    }
    if (!suggested.trim()) {
      setActivity("Reply endpoint completed but returned no draft.");
      return;
    }
    setRichEditorValue(generatedReplyEditor, generatedReply, suggested);
    if (state.selected) {
      state.selected.suggested_reply = suggested;
    }
    setActivity("Reply draft generated.");
  } catch (error) {
    setActivity(error.message);
  } finally {
    setBusy(button, false);
  }
}

async function generateWriterDraft(button) {
  saveEmail();
  if (!state.email) {
    setActivity("Enter your Gmail address first.");
    return;
  }
  if (state.composeMode === "reply") {
    await generateComposeReplyDraft(button);
    return;
  }

  setBusy(button, true, "Generating...");
  setActivity("Generating compose draft...");
  try {
    const data = await requestJson("/writer/message", {
      method: "POST",
      timeoutMs: 50000,
      timeoutMessage: "AI writer timed out waiting for the model server.",
      body: JSON.stringify({
        email: state.email,
        to: composeTo.value.trim(),
        cc: composeCc?.value.trim() || "",
        bcc: composeBcc?.value.trim() || "",
        subject: composeSubject.value.trim(),
        instruction: richEditorPlainText(writerInstructionEditor),
        format: writerFormatValue(),
      }),
    });
    const draft = data?.result?.writer?.draft;
    if (typeof draft !== "string" || !draft.trim()) {
      setActivity("Writer endpoint completed but returned no draft.");
      return;
    }
    setRichEditorValue(writerInstructionEditor, writerInstruction, draft);
    generatedWriterDraft.value = writerInstruction.value;
    setActivity("Compose draft generated.");
  } catch (error) {
    setActivity(error.message);
  } finally {
    setBusy(button, false);
  }
}

async function generateComposeReplyDraft(button) {
  const messageId = state.composeReplyMessageId || selectedMessageId.value.trim();
  if (!state.email || !messageId) {
    setActivity("Select a message first.");
    return;
  }

  setBusy(button, true, "Generating...");
  setActivity("Generating reply draft...");
  try {
    const data = await requestJson("/reply/message", {
      method: "POST",
      timeoutMs: 180000,
      body: JSON.stringify({
        email: state.email,
        message_id: messageId,
        intent: String(composeReplyIntent?.value || "").trim(),
      }),
    });
    const suggested = data?.result?.reply?.suggested_reply;
    if (typeof suggested !== "string" || !suggested.trim()) {
      setActivity("Reply endpoint completed but returned no draft.");
      return;
    }
    setRichEditorValue(writerInstructionEditor, writerInstruction, suggested);
    generatedWriterDraft.value = writerInstruction.value;
    if (state.selected) state.selected.suggested_reply = suggested;
    setActivity("Reply draft generated.");
  } catch (error) {
    setActivity(error.message);
  } finally {
    setBusy(button, false);
  }
}

async function sendWriterMessage(button) {
  saveEmail();
  if (state.composeMode === "reply") {
    await sendComposeReply(button);
    return;
  }
  const to = composeTo.value.trim();
  const cc = composeCc?.value.trim() || "";
  const bcc = composeBcc?.value.trim() || "";
  const body = composeBodyWithOriginalPlainText(richEditorPlainText(writerInstructionEditor));
  const bodyHtml = composeBodyWithOriginalHtml(richEditorHtml(writerInstructionEditor));
  if (!state.email) {
    setActivity("Enter your Gmail address first.");
    return;
  }
  if (!to || !body) {
    setActivity("Add a recipient and review the draft first.");
    return;
  }

  setBusy(button, true, "Sending...");
  setActivity("Sending message...");
  try {
    const attachments = await readAttachments(writerAttachments);
    await requestJson("/writer/send", {
      method: "POST",
      body: JSON.stringify({
        email: state.email,
        to,
        cc,
        bcc,
        subject: composeSubject.value.trim(),
        body,
        body_html: bodyHtml,
        attachments,
      }),
    });
    setActivity("Message sent.");
    clearAttachments(writerAttachments, writerAttachmentList);
    closeComposeModal();
  } catch (error) {
    setActivity(error.message);
  } finally {
    setBusy(button, false);
  }
}

async function sendComposeReply(button) {
  saveEmail();
  const messageId = state.composeReplyMessageId || selectedMessageId.value.trim();
  const to = composeTo.value.trim();
  const cc = composeCc?.value.trim() || "";
  const bcc = composeBcc?.value.trim() || "";
  const userReplyText = richEditorPlainText(writerInstructionEditor);
  const userReplyHtml = richEditorHtml(writerInstructionEditor).trim();
  const replyBody = composeBodyWithOriginalPlainText(userReplyText);
  const replyHtml = composeBodyWithOriginalHtml(userReplyHtml);
  if (!state.email || !messageId || !to || !replyBody) {
    setActivity("Select a message, add a recipient, and review the reply draft first.");
    return;
  }

  setBusy(button, true, "Sending...");
  setActivity("Sending reply...");
  try {
    const attachments = await readAttachments(writerAttachments);
    await requestJson("/reply/send", {
      method: "POST",
      body: JSON.stringify({
        email: state.email,
        message_id: messageId,
        to,
        cc,
        bcc,
        reply_body: replyBody,
        reply_html: replyHtml,
        attachments,
      }),
    });
    setActivity("Reply sent.");
    clearAttachments(writerAttachments, writerAttachmentList);
    closeComposeModal();
  } catch (error) {
    setActivity(error.message);
  } finally {
    setBusy(button, false);
  }
}

async function generateSummary(button) {
  saveEmail();
  const messageId = selectedMessageId.value.trim();
  if (!state.email || !messageId) {
    setActivity("Select a message first.");
    return;
  }

  setBusy(button, true, "Summarizing...");
  setActivity("Summarizing selected message...");
  try {
    const data = await requestJson("/summary/message", {
      method: "POST",
      timeoutMs: 180000,
      body: JSON.stringify({
        email: state.email,
        message_id: messageId,
      }),
    });
    mergeFullMessage(data?.result?.message);
    const summary =
      data?.result?.summary?.summary ||
      data?.result?.summary ||
      data?.summary?.summary ||
      "";
    const cleanSummary = cleanSummaryPlaceholders(summary);
    renderMarkdownSummary(cleanSummary);
    summaryResult.hidden = false;
    if (state.selected) {
      state.selected.summary = cleanSummary || state.selected.summary;
      const listMessage = state.messages.find((message) => messageKey(message) === messageId);
      if (listMessage) listMessage.summary = state.selected.summary;
      writeCachedMessages(state.email, state.messages, state.activeMailbox);
      renderMessages();
    }
    setActivity("Summary generated.");
  } catch (error) {
    setActivity(error.message);
  } finally {
    setBusy(button, false);
  }
}

async function sendReply(button) {
  saveEmail();
  const messageId = selectedMessageId.value.trim();
  const to = replyTo?.value.trim() || "";
  const cc = replyCc?.value.trim() || "";
  const bcc = replyBcc?.value.trim() || "";
  const replyBody = richEditorPlainText(generatedReplyEditor);
  const replyHtml = richEditorHtml(generatedReplyEditor);
  if (!state.email || !messageId || !to || !replyBody) {
    setActivity("Select a message, add a recipient, and review the reply draft first.");
    return;
  }

  setBusy(button, true, "Sending...");
  setActivity("Sending reply...");
  try {
    const attachments = await readAttachments(replyAttachments);
    await requestJson("/reply/send", {
      method: "POST",
      body: JSON.stringify({
        email: state.email,
        message_id: messageId,
        to,
        cc,
        bcc,
        reply_body: replyBody,
        reply_html: replyHtml,
        attachments,
      }),
    });
    setActivity("Reply sent.");
    clearAttachments(replyAttachments, replyAttachmentList);
  } catch (error) {
    setActivity(error.message);
  } finally {
    setBusy(button, false);
  }
}

const CALENDAR_RESPONSE_ACTIONS = {
  accepted: "Accept",
  declined: "Decline",
  tentative: "Tentative",
  proposed: "Propose a new time for",
};

function dismissEventToast(messageId) {
  if (!messageId || !toastContainer) return;
  toastContainer.querySelectorAll(".event-toast").forEach((toast) => {
    if (String(toast.dataset.messageId || "") === String(messageId)) toast.remove();
  });
}

function confirmCalendarEventResponse(messageId, selectedEvent, response) {
  const listEvent = state.calendarEvents.find(
    (entry) => String(entry.message_id) === String(messageId),
  );
  const event = selectedEvent || listEvent || null;
  const title = displayText(event?.title || event?.subject || "") || "this invite";
  const organizer = displayText(event?.organizer || "").replace(/^mailto:/i, "");
  const action = CALENDAR_RESPONSE_ACTIONS[response] || response;
  const recipient = organizer ? ` to ${organizer}` : " to the organizer";
  return window.confirm(`${action} "${title}"?\n\nThis sends an email reply${recipient} right now.`);
}

async function sendCalendarEventResponse(card, response) {
  const messageId = card?.dataset.messageId || "";
  if (!messageId || !response) return;
  const selectedEvent = String(state.selected?.message_id || "") === String(messageId)
    ? selectedCalendarEvent(state.selected)
    : null;
  const proposal = card.querySelector(".calendar-proposal");
  const proposedDate = proposal?.querySelector('input[type="date"]')?.value || "";
  const proposedTime = proposal?.querySelector('input[type="time"]')?.value || "";
  if (response === "proposed" && (!proposedDate || !proposedTime)) {
    setActivity("Choose a date and time for the new proposal.");
    return;
  }
  if (!confirmCalendarEventResponse(messageId, selectedEvent, response)) {
    setActivity("Calendar response cancelled.");
    return;
  }

  const button = card.querySelector(`[data-calendar-response="${CSS.escape(response)}"]`);
  setBusy(button, true, "Sending...");
  setActivity("Sending calendar response...");
  try {
    await requestJson("/calendar/events/respond", {
      method: "POST",
      body: JSON.stringify({
        message_id: messageId,
        response,
        proposed_date: proposedDate,
        proposed_time: proposedTime,
      }),
    });
    const event = state.calendarEvents.find((entry) => String(entry.message_id) === String(messageId));
    if (event) event.status = response;
    state.pendingResponses = (state.pendingResponses || []).filter(
      (entry) => String(entry.message_id) !== String(messageId),
    );
    if (selectedEvent) {
      selectedEvent.status = response;
      renderSelectedCalendarInviteActions(state.selected);
    }
    renderCalendarEvents();
    dismissEventToast(messageId);
    setActivity("Calendar response sent.");
  } catch (error) {
    setActivity(error.message);
  } finally {
    setBusy(button, false);
  }
}

async function removeCalendarEvent(card) {
  const messageId = card?.dataset.messageId || "";
  if (!messageId) return;
  if (!window.confirm("Remove this event from your calendar? This won't notify anyone.")) {
    setActivity("Event kept on your calendar.");
    return;
  }

  const button = card.querySelector('[data-action="remove-event"]');
  setBusy(button, true, "Removing...");
  setActivity("Removing calendar event...");
  try {
    await requestJson("/calendar/events/remove", {
      method: "POST",
      body: JSON.stringify({ message_id: messageId }),
    });
    state.calendarEvents = state.calendarEvents.filter(
      (entry) => String(entry.message_id) !== String(messageId),
    );
    state.pendingResponses = (state.pendingResponses || []).filter(
      (entry) => String(entry.message_id) !== String(messageId),
    );
    if (String(state.selected?.message_id) === String(messageId)) {
      state.selected.calendar_event = null;
      renderSelectedCalendarInviteActions(state.selected);
    }
    renderCalendarEvents();
    dismissEventToast(messageId);
    setActivity("Event removed from your calendar.");
  } catch (error) {
    setActivity(error.message);
  } finally {
    setBusy(button, false);
  }
}

function registerQuillFonts() {
  if (!window.Quill) return;
  const Font = window.Quill.import("formats/font");
  Font.whitelist = ["serif", "monospace", "times-new-roman", "arial", "georgia"];
  window.Quill.register(Font, true);
}

function initializeRichEditors() {
  const textareaMap = {
    generatedReplyEditor: generatedReply,
    replyIntentEditor: replyIntent,
    writerInstructionEditor: writerInstruction,
    signatureEditor: signatureValue,
  };
  registerQuillFonts();

  document.querySelectorAll(".rich-editor").forEach((container) => {
    const editorId = container.dataset.richEditor;
    const editor = editorId ? document.querySelector(`#${CSS.escape(editorId)}`) : null;
    const textarea = textareaMap[editorId];
    if (!editor) return;

    const toolbar = container.querySelector(".rich-toolbar");
    if (window.Quill && toolbar) {
      const quill = new window.Quill(editor, {
        modules: { toolbar },
        placeholder: editor.dataset.placeholder || "",
        theme: "snow",
      });
      quillEditors.set(editorId, quill);
      quill.on("text-change", () => syncRichEditorToTextarea(editor, textarea));
      toolbar.querySelectorAll("[data-editor-action]").forEach((button) => {
        button.addEventListener("click", (event) => {
          state.activeEditorId = editorId;
          if (button.dataset.editorAction === "signature") {
            positionFloatingMenu(signatureMenu, event.currentTarget);
            return;
          }
          if (button.dataset.editorAction === "emoji") {
            positionFloatingMenu(emojiMenu, event.currentTarget);
            return;
          }
        });
      });
      return;
    }

    editor.addEventListener("input", () => syncRichEditorToTextarea(editor, textarea));
  });
}

initializeRichEditors();

document.querySelector("#refreshHealth").addEventListener("click", checkHealth);
document.querySelector("#refreshMessages").addEventListener("click", (event) => {
  refreshConnectionStatus();
  loadMessages(event.currentTarget);
});
mailViewFilter.addEventListener("change", (event) => {
  setMailViewFilter(event.currentTarget.value);
  resetPagination(state.activeMailbox);
  state.messages = [];
  state.messageError = "";
  state.isMailboxLoading = true;
  renderMessages();
  loadMessages(document.querySelector("#refreshMessages"));
});
previousPageButton.addEventListener("click", (event) => {
  const previousPage = Math.max(1, paginationState().currentPage - 1);
  loadMailboxPage(previousPage, event.currentTarget);
});
nextPageButton.addEventListener("click", (event) => {
  loadMailboxPage(paginationState().currentPage + 1, event.currentTarget);
});
pageNumbers.addEventListener("click", (event) => {
  const button = event.target.closest(".page-number");
  if (!button || !pageNumbers.contains(button)) return;
  loadMailboxPage(Number(button.dataset.page), button);
});
loginButton.addEventListener("click", (event) => handleAuthButton(event.currentTarget));
if (loginScreenButton) {
  loginScreenButton.addEventListener("click", (event) => login(event.currentTarget));
}
if (replyAttachments) {
  replyAttachments.addEventListener("change", () => updateAttachmentList(replyAttachments, replyAttachmentList));
}
if (writerAttachments) {
  writerAttachments.addEventListener("change", () => updateAttachmentList(writerAttachments, writerAttachmentList));
}
composeButton.addEventListener("click", () => {
  resetComposeModal();
  openComposeModal();
});
document.querySelector("#closeModal").addEventListener("click", closeMessageModal);
messageModal.addEventListener("click", (event) => {
  if (event.target === messageModal) closeMessageModal();
});
document.querySelector("#closeComposeModal").addEventListener("click", closeComposeModal);
composeModal.addEventListener("click", (event) => {
  const recipientToggle = event.target.closest("[data-compose-toggle]");
  if (recipientToggle && composeModal.contains(recipientToggle)) {
    showComposeRecipientField(recipientToggle.dataset.composeToggle);
    return;
  }
  if (event.target === writerFormatButton) {
    positionFloatingMenu(writerFormatMenu, writerFormatButton);
    return;
  }
  if (event.target === composeModal) closeComposeModal();
});
replyComposer?.addEventListener("click", (event) => {
  const recipientToggle = event.target.closest("[data-reply-toggle]");
  if (!recipientToggle || !replyComposer.contains(recipientToggle)) return;
  showReplyRecipientField(recipientToggle.dataset.replyToggle);
});
writerFormatMenu?.addEventListener("click", (event) => {
  const formatButton = event.target.closest("[data-writer-format]");
  if (!formatButton) return;
  setWriterFormat(formatButton.dataset.writerFormat);
  hideFloatingMenus();
});
emojiMenu?.addEventListener("click", (event) => {
  const emojiButton = event.target.closest("[data-emoji]");
  if (!emojiButton) return;
  insertTextIntoEditor(state.activeEditorId, emojiButton.dataset.emoji || "");
  hideFloatingMenus();
});
signatureMenu?.addEventListener("click", (event) => {
  const actionButton = event.target.closest("[data-signature-action]");
  if (!actionButton) return;
  if (actionButton.dataset.signatureAction === "insert") {
    insertSavedSignature();
    return;
  }
  if (actionButton.dataset.signatureAction === "manage") {
    openSignatureManager();
  }
});
saveSignatureButton?.addEventListener("click", saveSignature);
insertManagedSignatureButton?.addEventListener("click", () => {
  saveSignature();
  insertSavedSignature();
  closeSignatureManager();
});
closeSignatureModalButton?.addEventListener("click", closeSignatureManager);
signatureModal?.addEventListener("click", (event) => {
  if (event.target === signatureModal) closeSignatureManager();
});
document.addEventListener("click", (event) => {
  const target = event.target;
  if (
    target.closest(".floating-menu") ||
    target.closest("[data-editor-action]")
  ) {
    return;
  }
  hideFloatingMenus();
});
document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape") return;
  hideFloatingMenus();
  if (signatureModal.classList.contains("is-open")) closeSignatureManager();
  if (messageModal.classList.contains("is-open")) closeMessageModal();
  if (composeModal.classList.contains("is-open")) closeComposeModal();
});
summaryButton.addEventListener("click", (event) => generateSummary(event.currentTarget));
function showReplyComposer() {
  prepareReplyComposer();
  replyComposer.hidden = false;
  replyIntentEditor.focus();
}
replyModeButton?.addEventListener("click", showReplyComposer);
replyIconButton?.addEventListener("click", openReplyCompose);
forwardIconButton?.addEventListener("click", openForwardCompose);
selectedRecipientToggle?.addEventListener("click", () => {
  if (!selectedRecipientDetails) return;
  selectedRecipientDetails.hidden = !selectedRecipientDetails.hidden;
  selectedRecipientToggle.setAttribute("aria-expanded", selectedRecipientDetails.hidden ? "false" : "true");
});
document.querySelector("#replyButton").addEventListener("click", (event) => generateReply(event.currentTarget));
document.querySelector("#sendReplyButton").addEventListener("click", (event) => sendReply(event.currentTarget));
writerButton?.addEventListener("click", (event) => generateWriterDraft(event.currentTarget));
sendWriterButton.addEventListener("click", (event) => sendWriterMessage(event.currentTarget));
document.querySelectorAll(".calendar-mode").forEach((button) => {
  button.addEventListener("click", () => {
    state.calendarMode = button.dataset.calendarMode || "week";
    localStorage.setItem("emailReminders.calendarMode", state.calendarMode);
    renderCalendarBoard();
  });
});
calendarBoard.addEventListener("click", (event) => {
  handleCalendarEventCardClick(event, calendarBoard);
});
calendarList.addEventListener("click", (event) => {
  if (handleCalendarEventCardClick(event, calendarList)) return;
  const item = event.target.closest(".calendar-item");
  if (!item || !calendarList.contains(item)) return;
  window.openEmailReminderMessage(item.dataset.messageId);
});
selectedCalendarInviteActions?.addEventListener("click", (event) => {
  handleCalendarEventCardClick(event, selectedCalendarInviteActions);
});
selectedMessageFrame.addEventListener("focus", () => {
  state.restoreEmailFrameOnFocus = true;
});
messageList.addEventListener("click", (event) => {
  const item = event.target.closest(".message-item");
  if (!item || !messageList.contains(item)) return;
  window.openEmailReminderMessage(item.dataset.messageId);
});
messageList.addEventListener("pointerover", (event) => {
  const item = event.target.closest(".message-item");
  if (!item || !messageList.contains(item)) return;
  fetchFullMessage(item.dataset.messageId, { timeoutMs: 30000 }).catch(() => {
    // Hover prefetch is best-effort only.
  });
});

inboxTabs?.addEventListener("click", async (event) => {
  const tab = event.target.closest("[data-inbox-category]");
  if (!tab || !inboxTabs.contains(tab)) return;
  const nextCategory = normalizedInboxCategory(tab.dataset.inboxCategory);
  if (state.activeMailbox !== "inbox") {
    setActiveMailbox("inbox", "Inbox");
  }
  if (nextCategory === normalizedInboxCategory()) return;
  state.activeInboxCategory = nextCategory;
  localStorage.setItem("emailReminders.inboxCategory", state.activeInboxCategory);
  resetSelectedMessage();
  state.messages = [];
  state.messageError = "";
  state.isMailboxLoading = true;
  state.isInitialMailboxSync = false;
  resetPagination("inbox", state.activeInboxCategory);
  renderInboxTabs();
  renderMessages();
  if (await hydrateFromSessionCache()) {
    if (state.isConnected) {
      loadMessages(document.querySelector("#refreshMessages"), false);
    }
    return;
  }
  loadMessages(document.querySelector("#refreshMessages"));
});

function openCalendarWorkspace() {
  setUpcomingEventsPanelOpen(false);
  setActiveView("calendar");
  state.calendarEvents = state.calendarEvents.length ? state.calendarEvents : readCachedCalendarEvents(state.email);
  renderCalendarEvents();
  loadCalendarEvents();
}

for (const link of mailboxButtons()) {
  link.addEventListener("click", async () => {
    exitMailSearch();
    const nextMailbox = link.dataset.mailbox || "inbox";
    const nextTitle = link.querySelector("span:nth-child(2)")?.textContent?.trim() || titleForMailbox(nextMailbox);
    if (nextMailbox === "inbox") {
      state.activeInboxCategory = "primary";
      localStorage.setItem("emailReminders.inboxCategory", state.activeInboxCategory);
    }
    setActiveMailbox(nextMailbox, nextTitle);
    resetSelectedMessage();
    state.messages = [];
    state.messageError = "";
    state.isMailboxLoading = true;
    state.isInitialMailboxSync = false;
    renderMessages();
    if (await hydrateFromSessionCache()) {
      if (state.isConnected) {
        loadMessages(document.querySelector("#refreshMessages"), false);
      }
      return;
    }
    loadMessages(document.querySelector("#refreshMessages"));
  });
}

document.querySelector('[data-view="calendar"]').addEventListener("click", () => {
  exitMailSearch();
  openCalendarWorkspace();
});
openCalendarViewButton?.addEventListener("click", openCalendarWorkspace);
mailSearchButton?.addEventListener("click", () => performMailSearch(mailSearchInput.value));
mailSearchInput?.addEventListener("keydown", (event) => {
  if (event.key !== "Enter") return;
  event.preventDefault();
  performMailSearch(mailSearchInput.value);
});
clearMailSearchButton?.addEventListener("click", clearMailSearch);
openUpcomingEventsButton?.addEventListener("click", () => {
  renderCalendarEvents();
  setUpcomingEventsPanelOpen(!upcomingEventsPanel?.classList.contains("is-open"));
});
closeUpcomingEventsButton?.addEventListener("click", () => setUpcomingEventsPanelOpen(false));

emailInput.value = state.email;
const didReturnFromGoogleLogin = applyAuthRedirectParams();
setMailViewFilter(state.unreadOnly ? "unread" : "all");
setActiveMailbox(state.activeMailbox, titleForMailbox(state.activeMailbox));
setActiveView(state.activeView);
emailInput.addEventListener("change", () => {
  saveEmail();
  state.calendarEvents = readCachedCalendarEvents(state.email);
  renderCalendarEvents();
  refreshConnectionStatus();
  hydrateFromSessionCache();
});
checkHealth();
closeMessageModal();
renderCalendarEvents();
setConnectionState(true);
setActivity("Loading mailbox...");
const startApp = async () => {
  await hydrateFromSessionCache();
  state.calendarEvents = readCachedCalendarEvents(state.email);
  renderCalendarEvents();
  loadMessages(document.querySelector("#refreshMessages"), !didReturnFromGoogleLogin).finally(() => {
    preloadAllMailboxes();
    scheduleMailboxMetadataBackfill(state.activeMailbox, state.activeInboxCategory, state.unreadOnly);
  });
  loadCalendarEvents();
};
const resolveStartupConnection = state.email ? Promise.resolve(true) : refreshConnectionStatus();
resolveStartupConnection.then((connected) => {
  if (!connected) {
    if (state.authError) {
      showLoginPrompt(state.authError);
      return;
    }
    showLoginPrompt();
    return;
  }
  startApp();
});
setInterval(autoRefreshMessages, MESSAGE_REFRESH_INTERVAL_MS);
setInterval(preloadAllMailboxes, MAILBOX_PRELOAD_INTERVAL_MS);
setInterval(pollEventNotifications, EVENT_NOTIFICATION_INTERVAL_MS);
window.addEventListener("focus", () => {
  autoRefreshMessages();
  if (state.restoreEmailFrameOnFocus) {
    state.restoreEmailFrameOnFocus = false;
    restoreSelectedEmailFrame();
  }
});
document.addEventListener("visibilitychange", () => {
  if (!document.hidden) {
    refreshConnectionStatus();
    autoRefreshMessages();
    loadCalendarEvents();
    pollEventNotifications();
    preloadAllMailboxes();
    if (state.restoreEmailFrameOnFocus) {
      state.restoreEmailFrameOnFocus = false;
      restoreSelectedEmailFrame();
    }
  }
});
