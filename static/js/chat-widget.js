/**
 * AI Agent Gateway - Universal Drop-in Chat Widget (Shadow DOM Architecture)
 * 
 * Features:
 * - Zero-dependencies, 100% Shadow DOM CSS & DOM encapsulation.
 * - Server-Sent Events (SSE) token streaming via POST /api/v1/chat/stream with /api/v1/chat fallback.
 * - Persistent multi-turn session in sessionStorage.
 * - Lightweight Markdown parser (bold, italics, lists, links, code blocks).
 * - Full programmatic window.AiChatWidget API.
 * - Fully responsive for mobile (<= 600px) and desktop.
 */
(function () {
  'use strict';

  if (window.AiChatWidgetLoaded) {
    return;
  }
  window.AiChatWidgetLoaded = true;

  // 1. Resolve Script Attributes and Defaults
  function resolveConfig() {
    var script =
      document.currentScript ||
      document.querySelector('script[data-api-url]') ||
      document.querySelector('script[src*="chat-widget.js"]');

    var apiUrl = 'https://ai-agent-gateway-sued.onrender.com';
    var agent = 'ecommerce';
    var title = 'Asistente de Compras';
    var primaryColor = '#2563eb';
    var userToken = null;

    if (script) {
      if (script.getAttribute('data-api-url')) apiUrl = script.getAttribute('data-api-url');
      else if (script.dataset && script.dataset.apiUrl) apiUrl = script.dataset.apiUrl;

      if (script.getAttribute('data-agent')) agent = script.getAttribute('data-agent');
      else if (script.dataset && script.dataset.agent) agent = script.dataset.agent;

      if (script.getAttribute('data-title')) title = script.getAttribute('data-title');
      else if (script.dataset && script.dataset.title) title = script.dataset.title;

      if (script.getAttribute('data-primary-color')) primaryColor = script.getAttribute('data-primary-color');
      else if (script.dataset && script.dataset.primaryColor) primaryColor = script.dataset.primaryColor;

      if (script.getAttribute('data-user-token')) userToken = script.getAttribute('data-user-token');
      else if (script.dataset && script.dataset.userToken) userToken = script.dataset.userToken;
    }

    return {
      apiUrl: apiUrl.replace(/\/+$/, ''),
      agent: agent,
      title: title,
      primaryColor: primaryColor,
      userToken: userToken || null
    };
  }

  var config = resolveConfig();

  // 2. Session ID Management
  var STORAGE_SESSION_KEY = 'ai_chat_session_id';
  var STORAGE_HISTORY_PREFIX = 'ai_chat_history_';

  function generateSessionId() {
    return 'sess_' + Date.now() + '_' + Math.random().toString(36).substring(2, 11);
  }

  function getSessionId() {
    var sessId = sessionStorage.getItem(STORAGE_SESSION_KEY);
    if (!sessId) {
      sessId = generateSessionId();
      sessionStorage.setItem(STORAGE_SESSION_KEY, sessId);
    }
    return sessId;
  }

  var currentSessionId = getSessionId();

  function getHistoryKey(sessId) {
    return STORAGE_HISTORY_PREFIX + sessId;
  }

  function loadHistory(sessId) {
    try {
      var saved = sessionStorage.getItem(getHistoryKey(sessId));
      return saved ? JSON.parse(saved) : null;
    } catch (e) {
      return null;
    }
  }

  function saveHistory(sessId, messages) {
    try {
      sessionStorage.setItem(getHistoryKey(sessId), JSON.stringify(messages));
    } catch (e) {
      console.warn('[AiChatWidget] Failed to save history', e);
    }
  }

  // 3. Widget State
  var state = {
    apiUrl: config.apiUrl,
    agent: config.agent,
    title: config.title,
    primaryColor: config.primaryColor,
    userToken: config.userToken,
    sessionId: currentSessionId,
    isOpen: false,
    isStreaming: false,
    messages: []
  };

  var DEFAULT_WELCOME_MSG =
    '¡Hola! 👋 Soy tu **Asistente de Compras** inteligente.\n\n¿En qué te puedo ayudar hoy? Puedes consultarme sobre productos, especificaciones, disponibilidad y recomendaciones personalizadas.';

  // 4. Lightweight Markdown Parser
  function escapeHtml(str) {
    if (!str) return '';
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function renderMarkdown(raw) {
    if (!raw) return '';

    // Step 1: Extract code blocks
    var codeBlocks = [];
    var text = raw.replace(/```([a-zA-Z0-9_-]*)\n?([\s\S]*?)```/g, function (_, lang, code) {
      var idx = codeBlocks.length;
      codeBlocks.push({ lang: lang.trim() || 'code', code: code.replace(/\n$/, '') });
      return '%%%CODEBLOCKPART' + idx + 'END%%%';
    });

    // Step 2: Extract inline code
    var inlineCodes = [];
    text = text.replace(/`([^`\n]+)`/g, function (_, code) {
      var idx = inlineCodes.length;
      inlineCodes.push(code);
      return '%%%INLINECODEPART' + idx + 'END%%%';
    });

    // Step 3: Markdown Tables Parsing
    var tableBlocks = [];
    text = text.replace(/((?:^[ \t]*\|.+?\|[ \t]*(?:\r?\n|$)){2,})/gm, function (tableBlock) {
      var lines = tableBlock.trim().split(/\r?\n/).map(function (l) { return l.trim(); }).filter(Boolean);
      if (lines.length < 2) return tableBlock;

      var sepIdx = -1;
      for (var i = 0; i < lines.length; i++) {
        if (/^\|[ :\-|\t]+\|$/.test(lines[i]) && lines[i].includes('-')) {
          sepIdx = i;
          break;
        }
      }
      if (sepIdx < 1) return tableBlock;

      var headerLines = lines.slice(0, sepIdx);
      var sepLine = lines[sepIdx];
      var dataLines = lines.slice(sepIdx + 1);

      var sepCells = sepLine.split('|').slice(1, -1);
      var alignments = sepCells.map(function (c) {
        var cell = c.trim();
        var left = cell.startsWith(':');
        var right = cell.endsWith(':');
        if (left && right) return 'text-center';
        if (right) return 'text-end';
        return 'text-start';
      });

      var headerHtml = '<thead>';
      headerLines.forEach(function (hLine) {
        var cells = hLine.split('|').slice(1, -1).map(function (c) { return c.trim(); });
        headerHtml += '<tr>';
        cells.forEach(function (h, idx) {
          var alignClass = alignments[idx] || 'text-start';
          var formattedHeader = escapeHtml(h);
          formattedHeader = formattedHeader.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
          headerHtml += '<th class="' + alignClass + '">' + formattedHeader + '</th>';
        });
        headerHtml += '</tr>';
      });
      headerHtml += '</thead>';

      var bodyHtml = '<tbody>';
      dataLines.forEach(function (rowLine) {
        if (!rowLine.includes('|')) return;
        var cells = rowLine.split('|').slice(1, -1).map(function (c) { return c.trim(); });
        bodyHtml += '<tr>';
        cells.forEach(function (cellContent, idx) {
          var alignClass = alignments[idx] || 'text-start';
          var formattedCell = escapeHtml(cellContent);
          formattedCell = formattedCell.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
          formattedCell = formattedCell.replace(/__([^_]+)__/g, '<strong>$1</strong>');
          formattedCell = formattedCell.replace(/(^|[^\*])\*([^*]+)\*([^\*]|$)/g, '$1<em>$2</em>$3');
          formattedCell = formattedCell.replace(/(^|[^_])_([^_]+)_([^_]|$)/g, '$1<em>$2</em>$3');
          formattedCell = formattedCell.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>');
          formattedCell = formattedCell.replace(/\[([^\]]+)\]\((https?:\/\/[^\s\)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer" class="chat-link">$1 ↗</a>');
          bodyHtml += '<td class="' + alignClass + '">' + formattedCell + '</td>';
        });
        bodyHtml += '</tr>';
      });
      bodyHtml += '</tbody>';

      var tableHtml = '<div class="table-responsive"><table class="chat-table">' + headerHtml + bodyHtml + '</table></div>';
      var idx = tableBlocks.length;
      tableBlocks.push(tableHtml);
      return '%%%HTMLTABLEPART' + idx + 'END%%%';
    });

    // Step 4: Escape plain text
    text = escapeHtml(text);

    // Step 5: Markdown Links [text](url)
    text = text.replace(/\[([^\]]+)\]\((https?:\/\/[^\s\)]+)\)/g, function (_, label, url) {
      var safeUrl = encodeURI(url.trim());
      return '<a href="' + safeUrl + '" target="_blank" rel="noopener noreferrer" class="chat-link">' + label + ' ↗</a>';
    });

    // Step 6: Bold and Italics
    text = text.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    text = text.replace(/__([^_]+)__/g, '<strong>$1</strong>');
    text = text.replace(/(^|[^\*])\*([^*]+)\*([^\*]|$)/g, '$1<em>$2</em>$3');
    text = text.replace(/(^|[^_])_([^_]+)_([^_]|$)/g, '$1<em>$2</em>$3');

    // Step 7: Bullet and Numbered Lists
    text = text.replace(/((?:^(?:-|\*)\s+.+(?:\n|$))+)/gm, function (match) {
      var items = match
        .trim()
        .split('\n')
        .map(function (line) {
          return line.replace(/^(?:-|\*)\s+/, '').trim();
        })
        .filter(Boolean)
        .map(function (item) {
          return '<li>' + item + '</li>';
        })
        .join('');
      return '<ul class="chat-list">' + items + '</ul>';
    });

    text = text.replace(/((?:^\d+\.\s+.+(?:\n|$))+)/gm, function (match) {
      var items = match
        .trim()
        .split('\n')
        .map(function (line) {
          return line.replace(/^\d+\.\s+/, '').trim();
        })
        .filter(Boolean)
        .map(function (item) {
          return '<li>' + item + '</li>';
        })
        .join('');
      return '<ol class="chat-list">' + items + '</ol>';
    });

    // Step 8: Paragraphs & Newlines
    text = text.replace(/\n\n+/g, '</p><p>');
    text = text.replace(/\n/g, '<br>');
    if (!text.startsWith('<div') && !text.startsWith('<ul') && !text.startsWith('<ol') && !text.startsWith('<p')) {
      text = '<p>' + text + '</p>';
    }

    // Step 9: Reinsert HTML table blocks
    text = text.replace(/%%%HTMLTABLEPART(\d+)END%%%/g, function (_, id) {
      return tableBlocks[Number(id)] || '';
    });

    // Step 10: Reinsert code blocks
    text = text.replace(/%%%CODEBLOCKPART(\d+)END%%%/g, function (_, id) {
      var block = codeBlocks[Number(id)];
      if (!block) return '';
      var safeCode = escapeHtml(block.code);
      return (
        '<div class="code-container">' +
        '<div class="code-header"><span>' + escapeHtml(block.lang) + '</span><button type="button" class="copy-btn" data-code="' + encodeURIComponent(block.code) + '">Copiar</button></div>' +
        '<pre><code>' + safeCode + '</code></pre>' +
        '</div>'
      );
    });

    // Step 11: Reinsert inline codes
    text = text.replace(/%%%INLINECODEPART(\d+)END%%%/g, function (_, id) {
      return '<code class="inline-code">' + escapeHtml(inlineCodes[Number(id)] || '') + '</code>';
    });

    return text;
  }

  // 5. Shadow DOM Setup & Styles
  var hostElement = document.createElement('div');
  hostElement.id = 'ai-chat-widget-root';
  document.body.appendChild(hostElement);

  var shadow = hostElement.attachShadow({ mode: 'open' });

  var styleSheet = document.createElement('style');
  styleSheet.textContent = `
    :host {
      all: initial;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      font-size: 14px;
      line-height: 1.5;
      color: #1e293b;
      --primary-color: ${state.primaryColor};
      --bg-surface: #ffffff;
      --bg-body: #f8fafc;
      --border-color: #e2e8f0;
      --text-main: #0f172a;
      --text-muted: #64748b;
    }

    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }

    /* Floating Launcher Button */
    .widget-launcher {
      position: fixed;
      bottom: 24px;
      right: 24px;
      width: 60px;
      height: 60px;
      border-radius: 50%;
      background-color: var(--primary-color);
      color: #ffffff;
      border: none;
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 999999;
      transition: transform 0.25s cubic-bezier(0.34, 1.56, 0.64, 1), box-shadow 0.25s ease;
      outline: none;
    }

    .widget-launcher:hover {
      transform: scale(1.08);
      box-shadow: 0 6px 24px rgba(0, 0, 0, 0.25);
    }

    .widget-launcher:active {
      transform: scale(0.96);
    }

    .widget-launcher svg {
      width: 28px;
      height: 28px;
      fill: currentColor;
      transition: transform 0.25s ease, opacity 0.25s ease;
    }

    .launcher-icon-chat {
      position: absolute;
      opacity: 1;
      transform: scale(1) rotate(0deg);
    }

    .launcher-icon-close {
      position: absolute;
      opacity: 0;
      transform: scale(0.5) rotate(-90deg);
    }

    .widget-launcher.is-active .launcher-icon-chat {
      opacity: 0;
      transform: scale(0.5) rotate(90deg);
    }

    .widget-launcher.is-active .launcher-icon-close {
      opacity: 1;
      transform: scale(1) rotate(0deg);
    }

    /* Chat Window Container */
    .chat-window {
      position: fixed;
      bottom: 96px;
      right: 24px;
      width: 380px;
      height: 580px;
      max-width: calc(100vw - 32px);
      max-height: calc(100vh - 120px);
      background: var(--bg-surface);
      border-radius: 16px;
      box-shadow: 0 12px 48px rgba(0, 0, 0, 0.18), 0 0 0 1px rgba(0, 0, 0, 0.05);
      display: flex;
      flex-direction: column;
      overflow: hidden;
      z-index: 999999;
      opacity: 0;
      visibility: hidden;
      transform: translateY(20px) scale(0.94);
      transform-origin: bottom right;
      transition: opacity 0.25s cubic-bezier(0.16, 1, 0.3, 1), transform 0.25s cubic-bezier(0.16, 1, 0.3, 1), visibility 0.25s;
    }

    .chat-window.is-open {
      opacity: 1;
      visibility: visible;
      transform: translateY(0) scale(1);
    }

    /* Header */
    .chat-header {
      background-color: var(--primary-color);
      color: #ffffff;
      padding: 14px 16px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      user-select: none;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
      position: relative;
      z-index: 2;
    }

    .header-info {
      display: flex;
      align-items: center;
      gap: 10px;
      min-width: 0;
    }

    .header-avatar {
      position: relative;
      width: 38px;
      height: 38px;
      border-radius: 50%;
      background: rgba(255, 255, 255, 0.2);
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
    }

    .header-avatar svg {
      width: 22px;
      height: 22px;
      fill: #ffffff;
    }

    .header-status-dot {
      position: absolute;
      bottom: 0;
      right: 0;
      width: 10px;
      height: 10px;
      background-color: #22c55e;
      border: 2px solid var(--primary-color);
      border-radius: 50%;
    }

    .header-details {
      display: flex;
      flex-direction: column;
      min-width: 0;
    }

    .header-title-row {
      display: flex;
      align-items: center;
      gap: 6px;
    }

    .header-title {
      font-weight: 600;
      font-size: 15px;
      line-height: 1.2;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .header-badge {
      font-size: 10px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      background: rgba(255, 255, 255, 0.25);
      color: #ffffff;
      padding: 2px 7px;
      border-radius: 10px;
      display: inline-block;
      flex-shrink: 0;
    }

    .header-actions {
      display: flex;
      align-items: center;
      gap: 4px;
      flex-shrink: 0;
    }

    .header-btn {
      background: transparent;
      border: none;
      color: #ffffff;
      opacity: 0.85;
      width: 32px;
      height: 32px;
      border-radius: 8px;
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      transition: opacity 0.2s, background-color 0.2s;
      outline: none;
    }

    .header-btn:hover {
      opacity: 1;
      background: rgba(255, 255, 255, 0.2);
    }

    .header-btn svg {
      width: 18px;
      height: 18px;
      stroke: currentColor;
      fill: none;
      stroke-width: 2;
      stroke-linecap: round;
      stroke-linejoin: round;
    }

    /* Message Body */
    .chat-body {
      flex: 1;
      padding: 16px;
      overflow-y: auto;
      background-color: var(--bg-body);
      display: flex;
      flex-direction: column;
      gap: 12px;
      scroll-behavior: smooth;
    }

    .chat-body::-webkit-scrollbar {
      width: 5px;
    }

    .chat-body::-webkit-scrollbar-thumb {
      background: #cbd5e1;
      border-radius: 4px;
    }

    .msg-row {
      display: flex;
      flex-direction: column;
      max-width: 85%;
      animation: fadeIn 0.2s ease-out;
    }

    @keyframes fadeIn {
      from {
        opacity: 0;
        transform: translateY(6px);
      }
      to {
        opacity: 1;
        transform: translateY(0);
      }
    }

    .msg-row.user {
      align-self: flex-end;
      align-items: flex-end;
    }

    .msg-row.bot {
      align-self: flex-start;
      align-items: flex-start;
    }

    .msg-bubble {
      padding: 10px 14px;
      font-size: 13.5px;
      line-height: 1.5;
      word-break: break-word;
      position: relative;
    }

    .msg-row.user .msg-bubble {
      background-color: var(--primary-color);
      color: #ffffff;
      border-radius: 16px 16px 4px 16px;
      box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
    }

    .msg-row.bot .msg-bubble {
      background-color: #ffffff;
      color: #1e293b;
      border: 1px solid var(--border-color);
      border-radius: 16px 16px 16px 4px;
      box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
    }

    .msg-row.error .msg-bubble {
      background-color: #fef2f2;
      color: #991b1b;
      border: 1px solid #fecaca;
    }

    .msg-bubble p {
      margin-bottom: 8px;
    }

    .msg-bubble p:last-child {
      margin-bottom: 0;
    }

    .msg-bubble strong {
      font-weight: 600;
    }

    .msg-bubble em {
      font-style: italic;
    }

    .chat-link {
      color: var(--primary-color);
      text-decoration: underline;
      font-weight: 500;
    }

    .chat-list {
      margin: 6px 0 6px 18px;
      padding-left: 0;
    }

    .chat-list li {
      margin-bottom: 4px;
    }

    .table-responsive {
      width: 100%;
      overflow-x: auto;
      margin: 8px 0;
      border-radius: 6px;
      border: 1px solid var(--border-color);
      -webkit-overflow-scrolling: touch;
    }

    .table-responsive::-webkit-scrollbar {
      height: 5px;
    }

    .table-responsive::-webkit-scrollbar-thumb {
      background: #cbd5e1;
      border-radius: 3px;
    }

    .chat-table {
      width: 100%;
      border-collapse: collapse;
      font-size: 12px;
      text-align: left;
    }

    .chat-table th {
      background: #f8fafc;
      color: #334155;
      font-weight: 600;
      padding: 7px 10px;
      border-bottom: 1px solid var(--border-color);
      white-space: nowrap;
    }

    .chat-table td {
      padding: 7px 10px;
      border-bottom: 1px solid #f1f5f9;
      color: #1e293b;
    }

    .chat-table tr:last-child td {
      border-bottom: none;
    }

    .chat-table tr:hover {
      background: #f8fafc;
    }

    .text-start { text-align: left; }
    .text-center { text-align: center; }
    .text-end { text-align: right; }

    .inline-code {
      background: #f1f5f9;
      color: #0f172a;
      padding: 2px 5px;
      border-radius: 4px;
      font-family: ui-monospace, Menlo, Monaco, Consolas, monospace;
      font-size: 12px;
    }

    .msg-row.user .inline-code {
      background: rgba(255, 255, 255, 0.25);
      color: #ffffff;
    }

    .code-container {
      margin: 8px 0;
      background: #0f172a;
      border-radius: 6px;
      overflow: hidden;
      width: 100%;
    }

    .code-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 4px 10px;
      background: #1e293b;
      color: #94a3b8;
      font-size: 11px;
      font-family: monospace;
      text-transform: uppercase;
    }

    .copy-btn {
      background: transparent;
      border: 1px solid #475569;
      color: #cbd5e1;
      font-size: 10px;
      padding: 2px 6px;
      border-radius: 4px;
      cursor: pointer;
    }

    .code-container pre {
      padding: 10px;
      margin: 0;
      overflow-x: auto;
      font-family: ui-monospace, Menlo, Monaco, Consolas, monospace;
      font-size: 12px;
      color: #f8fafc;
      line-height: 1.4;
    }

    /* Typing & Streaming Indicator */
    .typing-indicator {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      padding: 10px 14px;
      background-color: #ffffff;
      border: 1px solid var(--border-color);
      border-radius: 16px 16px 16px 4px;
      box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
      align-self: flex-start;
    }

    .typing-dot {
      width: 6px;
      height: 6px;
      background-color: var(--text-muted);
      border-radius: 50%;
      animation: typingBounce 1.4s infinite ease-in-out both;
    }

    .typing-dot:nth-child(1) { animation-delay: -0.32s; }
    .typing-dot:nth-child(2) { animation-delay: -0.16s; }
    .typing-dot:nth-child(3) { animation-delay: 0; }

    @keyframes typingBounce {
      0%, 80%, 100% { transform: scale(0); opacity: 0.4; }
      40% { transform: scale(1); opacity: 1; }
    }

    .streaming-cursor {
      display: inline-block;
      width: 4px;
      height: 14px;
      background-color: var(--primary-color);
      vertical-align: -2px;
      margin-left: 2px;
      animation: blink 0.9s infinite;
    }

    @keyframes blink {
      0%, 100% { opacity: 1; }
      50% { opacity: 0; }
    }

    /* Footer */
    .chat-footer {
      border-top: 1px solid var(--border-color);
      padding: 12px 14px;
      background: var(--bg-surface);
      display: flex;
      gap: 8px;
      align-items: center;
      position: relative;
      z-index: 2;
    }

    .chat-input {
      flex: 1;
      border: 1px solid #cbd5e1;
      border-radius: 24px;
      padding: 10px 16px;
      font-size: 13.5px;
      outline: none;
      background: #ffffff;
      color: var(--text-main);
      transition: border-color 0.2s, box-shadow 0.2s;
      font-family: inherit;
    }

    .chat-input:focus {
      border-color: var(--primary-color);
      box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.15);
    }

    .chat-input:disabled {
      background-color: #f1f5f9;
      cursor: not-allowed;
    }

    .send-btn {
      width: 38px;
      height: 38px;
      min-width: 38px;
      border-radius: 50%;
      background: var(--primary-color);
      color: #ffffff;
      border: none;
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      transition: filter 0.2s, transform 0.15s;
      outline: none;
    }

    .send-btn:hover:not(:disabled) {
      filter: brightness(1.08);
      transform: scale(1.05);
    }

    .send-btn:disabled {
      background: #cbd5e1;
      cursor: not-allowed;
      opacity: 0.7;
    }

    .send-btn svg {
      width: 18px;
      height: 18px;
      fill: currentColor;
    }

    /* Mobile Responsive */
    @media (max-width: 600px) {
      .chat-window {
        bottom: 0 !important;
        right: 0 !important;
        left: 0 !important;
        top: 0 !important;
        width: 100vw !important;
        height: 100vh !important;
        max-width: 100vw !important;
        max-height: 100vh !important;
        border-radius: 0 !important;
      }

      .widget-launcher {
        bottom: 16px;
        right: 16px;
        width: 52px;
        height: 52px;
      }
    }
  `;

  // HTML Structure
  var rootContainer = document.createElement('div');
  rootContainer.className = 'ai-chat-root';

  rootContainer.innerHTML = `
    <!-- Floating Launcher Button -->
    <button type="button" class="widget-launcher" id="aiLauncher" aria-label="Abrir asistente de compras">
      <svg class="launcher-icon-chat" viewBox="0 0 24 24">
        <path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H5.2L4 17.2V4h16v12z"/>
        <circle cx="8" cy="10" r="1.5"/>
        <circle cx="12" cy="10" r="1.5"/>
        <circle cx="16" cy="10" r="1.5"/>
      </svg>
      <svg class="launcher-icon-close" viewBox="0 0 24 24">
        <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
      </svg>
    </button>

    <!-- Chat Modal Window -->
    <div class="chat-window" id="aiChatWindow" role="dialog" aria-modal="true" aria-label="Asistente de compras virtual">
      <!-- Header -->
      <div class="chat-header">
        <div class="header-info">
          <div class="header-avatar">
            <svg viewBox="0 0 24 24">
              <path d="M12 2a2 2 0 0 1 2 2c0 .74-.4 1.39-1 1.73V7h1a7 7 0 0 1 7 7h1a1 1 0 0 1 1 1v3a1 1 0 0 1-1 1h-1v1a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-1H2a1 1 0 0 1-1-1v-3a1 1 0 0 1 1-1h1a7 7 0 0 1 7-7h1V5.73c-.6-.34-1-.99-1-1.73a2 2 0 0 1 2-2M7.5 13A2.5 2.5 0 0 0 5 15.5 2.5 2.5 0 0 0 7.5 18 2.5 2.5 0 0 0 10 15.5 2.5 2.5 0 0 0 7.5 13m9 0a2.5 2.5 0 0 0-2.5 2.5 2.5 2.5 0 0 0 2.5 2.5 2.5 2.5 0 0 0 2.5-2.5 2.5 2.5 0 0 0-2.5-2.5"/>
            </svg>
            <span class="header-status-dot"></span>
          </div>
          <div class="header-details">
            <div class="header-title-row">
              <span class="header-title" id="aiHeaderTitle">${escapeHtml(state.title)}</span>
              <span class="header-badge" id="aiHeaderBadge">${escapeHtml(state.agent)}</span>
            </div>
          </div>
        </div>
        <div class="header-actions">
          <button type="button" class="header-btn" id="aiClearBtn" title="Limpiar conversación" aria-label="Limpiar conversación">
            <svg viewBox="0 0 24 24">
              <polyline points="3 6 5 6 21 6"></polyline>
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
            </svg>
          </button>
          <button type="button" class="header-btn" id="aiCloseBtn" title="Cerrar chat" aria-label="Cerrar chat">
            <svg viewBox="0 0 24 24">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>
      </div>

      <!-- Message History Body -->
      <div class="chat-body" id="aiChatBody"></div>

      <!-- Footer Input -->
      <div class="chat-footer">
        <input
          type="text"
          class="chat-input"
          id="aiChatInput"
          placeholder="Escribe tu consulta aquí..."
          autocomplete="off"
        />
        <button type="button" class="send-btn" id="aiSendBtn" aria-label="Enviar mensaje" disabled>
          <svg viewBox="0 0 24 24">
            <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
          </svg>
        </button>
      </div>
    </div>
  `;

  shadow.appendChild(styleSheet);
  shadow.appendChild(rootContainer);

  // Element References
  var launcherBtn = shadow.getElementById('aiLauncher');
  var chatWindow = shadow.getElementById('aiChatWindow');
  var chatBody = shadow.getElementById('aiChatBody');
  var chatInput = shadow.getElementById('aiChatInput');
  var sendBtn = shadow.getElementById('aiSendBtn');
  var clearBtn = shadow.getElementById('aiClearBtn');
  var closeBtn = shadow.getElementById('aiCloseBtn');
  var headerTitleEl = shadow.getElementById('aiHeaderTitle');
  var headerBadgeEl = shadow.getElementById('aiHeaderBadge');

  // UI Helpers
  function scrollToBottom(smooth) {
    chatBody.scrollTo({
      top: chatBody.scrollHeight,
      behavior: smooth !== false ? 'smooth' : 'auto'
    });
  }

  function appendMessageNode(role, rawContent, isError) {
    var row = document.createElement('div');
    row.className = 'msg-row ' + role + (isError ? ' error' : '');

    var bubble = document.createElement('div');
    bubble.className = 'msg-bubble';

    if (role === 'user') {
      bubble.textContent = rawContent;
    } else {
      bubble.innerHTML = renderMarkdown(rawContent);
    }

    row.appendChild(bubble);
    chatBody.appendChild(row);
    scrollToBottom(true);
    return row;
  }

  function showTypingIndicator() {
    removeTypingIndicator();
    var indicator = document.createElement('div');
    indicator.className = 'typing-indicator';
    indicator.id = 'aiTypingIndicator';
    indicator.innerHTML = '<span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-dot"></span>';
    chatBody.appendChild(indicator);
    scrollToBottom(true);
  }

  function removeTypingIndicator() {
    var el = shadow.getElementById('aiTypingIndicator');
    if (el) el.remove();
  }

  function updateHeaderInfo() {
    headerTitleEl.textContent = state.title;
    headerBadgeEl.textContent = state.agent;
  }

  function initializeHistory() {
    chatBody.innerHTML = '';
    var saved = loadHistory(state.sessionId);

    if (saved && Array.isArray(saved) && saved.length > 0) {
      state.messages = saved;
      for (var i = 0; i < state.messages.length; i++) {
        var msg = state.messages[i];
        appendMessageNode(msg.role, msg.text, msg.isError);
      }
    } else {
      state.messages = [
        {
          role: 'bot',
          text: DEFAULT_WELCOME_MSG,
          timestamp: Date.now()
        }
      ];
      saveHistory(state.sessionId, state.messages);
      appendMessageNode('bot', DEFAULT_WELCOME_MSG);
    }
  }

  // 6. Streaming and Backend Fetching Layer
  async function performSendMessage(text) {
    var trimmed = (text || '').trim();
    if (!trimmed || state.isStreaming) return;

    // 1. Add user message
    state.messages.push({
      role: 'user',
      text: trimmed,
      timestamp: Date.now()
    });
    saveHistory(state.sessionId, state.messages);
    appendMessageNode('user', trimmed);

    // 2. Lock UI
    state.isStreaming = true;
    chatInput.value = '';
    chatInput.disabled = true;
    sendBtn.disabled = true;
    showTypingIndicator();

    var payload = {
      agent_id: state.agent,
      session_id: state.sessionId,
      message: trimmed,
      stream: true,
      user_token: state.userToken || null,
      context: {
        source: 'ecommerce_web_widget',
        page: window.location.pathname
      }
    };

    var headers = {
      'Content-Type': 'application/json'
    };
    if (state.userToken) {
      headers['Authorization'] = 'Bearer ' + state.userToken;
    }

    var streamSucceeded = false;
    var accumulatedText = '';
    var botRow = null;
    var botBubble = null;

    // Attempt A: POST /api/v1/chat/stream
    try {
      var response = await fetch(state.apiUrl + '/api/v1/chat/stream', {
        method: 'POST',
        headers: headers,
        body: JSON.stringify(payload)
      });

      if (response.ok && response.body) {
        removeTypingIndicator();

        botRow = document.createElement('div');
        botRow.className = 'msg-row bot';
        botBubble = document.createElement('div');
        botBubble.className = 'msg-bubble';
        botBubble.innerHTML = '<span class="streaming-cursor"></span>';
        botRow.appendChild(botBubble);
        chatBody.appendChild(botRow);
        scrollToBottom(true);

        var reader = response.body.getReader();
        var decoder = new TextDecoder('utf-8');
        var buffer = '';

        while (true) {
          var chunkRes = await reader.read();
          if (chunkRes.done) break;

          buffer += decoder.decode(chunkRes.value, { stream: true });
          var lines = buffer.split('\n');
          buffer = lines.pop(); // keep remainder

          for (var j = 0; j < lines.length; j++) {
            var line = lines[j].trim();
            if (!line || line.startsWith(':')) continue;

            if (line.startsWith('data:')) {
              var dataStr = line.substring(5).trim();
              if (dataStr === '[DONE]') {
                continue;
              }
              try {
                var parsed = JSON.parse(dataStr);
                var token =
                  parsed.text !== undefined
                    ? parsed.text
                    : parsed.delta !== undefined
                    ? parsed.delta
                    : parsed.content !== undefined
                    ? parsed.content
                    : parsed.message !== undefined
                    ? parsed.message
                    : parsed.token !== undefined
                    ? parsed.token
                    : typeof parsed === 'string'
                    ? parsed
                    : '';
                if (token) {
                  accumulatedText += token;
                  botBubble.innerHTML = renderMarkdown(accumulatedText) + '<span class="streaming-cursor"></span>';
                  scrollToBottom(true);
                }
              } catch (e) {
                accumulatedText += dataStr;
                botBubble.innerHTML = renderMarkdown(accumulatedText) + '<span class="streaming-cursor"></span>';
                scrollToBottom(true);
              }
            } else if (!line.startsWith('event:')) {
              accumulatedText += line + ' ';
              botBubble.innerHTML = renderMarkdown(accumulatedText) + '<span class="streaming-cursor"></span>';
              scrollToBottom(true);
            }
          }
        }

        if (buffer.trim()) {
          var lastLine = buffer.trim();
          if (lastLine.startsWith('data:')) {
            var lastData = lastLine.substring(5).trim();
            if (lastData !== '[DONE]') {
              try {
                var parsedLast = JSON.parse(lastData);
                var lastToken = parsedLast.text || parsedLast.delta || parsedLast.content || parsedLast.message || '';
                if (lastToken) accumulatedText += lastToken;
              } catch (e) {
                accumulatedText += lastData;
              }
            }
          } else if (!lastLine.startsWith('event:')) {
            accumulatedText += lastLine;
          }
        }

        if (accumulatedText.trim()) {
          streamSucceeded = true;
        }
      }
    } catch (streamErr) {
      console.warn('[AiChatWidget] Stream failed, falling back to /api/v1/chat', streamErr);
    }

    // Attempt B: Fallback to POST /api/v1/chat
    if (!streamSucceeded || !accumulatedText.trim()) {
      try {
        if (!botRow) {
          removeTypingIndicator();
          showTypingIndicator();
        }

        var fallbackPayload = Object.assign({}, payload, { stream: false });
        var fallbackRes = await fetch(state.apiUrl + '/api/v1/chat', {
          method: 'POST',
          headers: headers,
          body: JSON.stringify(fallbackPayload)
        });

        removeTypingIndicator();

        if (!fallbackRes.ok) {
          throw new Error('HTTP ' + fallbackRes.status);
        }

        var data = await fallbackRes.json();
        accumulatedText =
          data.reply ||
          data.response ||
          data.message ||
          data.text ||
          data.content ||
          (typeof data === 'string' ? data : 'Respuesta recibida.');

        if (!botRow) {
          botRow = document.createElement('div');
          botRow.className = 'msg-row bot';
          botBubble = document.createElement('div');
          botBubble.className = 'msg-bubble';
          botRow.appendChild(botBubble);
          chatBody.appendChild(botRow);
        }
      } catch (fallbackErr) {
        removeTypingIndicator();
        console.error('[AiChatWidget] Fallback request failed', fallbackErr);
        accumulatedText =
          '⚠️ Hubo un inconveniente al conectar con el servidor de IA. Por favor, verifica tu conexión o intenta nuevamente en unos momentos.';

        if (!botRow) {
          botRow = document.createElement('div');
          botRow.className = 'msg-row bot error';
          botBubble = document.createElement('div');
          botBubble.className = 'msg-bubble';
          botRow.appendChild(botBubble);
          chatBody.appendChild(botRow);
        } else {
          botRow.classList.add('error');
        }
      }
    }

    // Finalize bubble
    if (botBubble) {
      botBubble.innerHTML = renderMarkdown(accumulatedText);
    }

    state.messages.push({
      role: 'bot',
      text: accumulatedText,
      timestamp: Date.now(),
      isError: botRow && botRow.classList.contains('error')
    });
    saveHistory(state.sessionId, state.messages);

    // Unlock UI
    state.isStreaming = false;
    chatInput.disabled = false;
    sendBtn.disabled = !chatInput.value.trim();
    chatInput.focus();
    scrollToBottom(true);
  }

  // 7. Navigation & Window Controls
  function openWidget() {
    if (state.isOpen) return;
    state.isOpen = true;
    chatWindow.classList.add('is-open');
    launcherBtn.classList.add('is-active');
    setTimeout(function () {
      chatInput.focus();
      scrollToBottom(false);
    }, 150);
  }

  function closeWidget() {
    if (!state.isOpen) return;
    state.isOpen = false;
    chatWindow.classList.remove('is-open');
    launcherBtn.classList.remove('is-active');
  }

  function toggleWidget() {
    if (state.isOpen) {
      closeWidget();
    } else {
      openWidget();
    }
  }

  function clearSession() {
    sessionStorage.removeItem(getHistoryKey(state.sessionId));
    state.sessionId = generateSessionId();
    sessionStorage.setItem(STORAGE_SESSION_KEY, state.sessionId);
    initializeHistory();
  }

  // Event Listeners
  launcherBtn.addEventListener('click', toggleWidget);
  closeBtn.addEventListener('click', closeWidget);
  clearBtn.addEventListener('click', function () {
    if (confirm('¿Deseas reiniciar la conversación con el asistente?')) {
      clearSession();
    }
  });

  chatInput.addEventListener('input', function () {
    sendBtn.disabled = !chatInput.value.trim() || state.isStreaming;
  });

  chatInput.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      var val = chatInput.value.trim();
      if (val && !state.isStreaming) {
        performSendMessage(val);
      }
    }
  });

  sendBtn.addEventListener('click', function () {
    var val = chatInput.value.trim();
    if (val && !state.isStreaming) {
      performSendMessage(val);
    }
  });

  // Code Copy Delegation
  chatBody.addEventListener('click', function (e) {
    var target = e.target;
    var copyBtn = target.closest ? target.closest('.copy-btn') : null;
    if (copyBtn) {
      var code = decodeURIComponent(copyBtn.getAttribute('data-code') || '');
      if (navigator.clipboard) {
        navigator.clipboard.writeText(code).then(function () {
          var original = copyBtn.textContent;
          copyBtn.textContent = '¡Copiado!';
          copyBtn.style.color = '#4ade80';
          setTimeout(function () {
            copyBtn.textContent = original;
            copyBtn.style.color = '';
          }, 2000);
        });
      }
    }
  });

  // 8. Global API
  window.AiChatWidget = {
    open: openWidget,
    close: closeWidget,
    toggle: toggleWidget,
    setAgent: function (agentId) {
      if (!agentId) return;
      state.agent = agentId;
      updateHeaderInfo();
    },
    sendMessage: function (messageText) {
      openWidget();
      if (messageText && typeof messageText === 'string') {
        performSendMessage(messageText);
      }
    },
    setUserToken: function (token) {
      state.userToken = token || null;
    },
    clearSession: clearSession,
    getAgent: function () {
      return state.agent;
    },
    getSessionId: function () {
      return state.sessionId;
    }
  };

  // Initialize
  initializeHistory();
  updateHeaderInfo();
})();
