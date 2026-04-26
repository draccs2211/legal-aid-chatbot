// ── NyayMitra App.js ── Clean Light UI
const API_BASE = "http://127.0.0.1:8000";

// ── State ──
let currentLang         = "en";
let currentDomain       = null;
let sessionId           = "session_" + Date.now();
let conversationHistory = [];
let isTyping            = false;
let welcomeVisible      = true;

// ── Speech State ──
let mediaRecorder  = null;
let audioChunks    = [];
let isRecording    = false;
let audioQueue     = [];
let isPlaying      = false;
let ttsEnabled     = true;
let ttsAbortCtrl   = null;
let currentAudio   = null;  // FIX: track current playing audio for smooth fade

// ── DOM refs ──
const chatArea      = document.getElementById("chatArea");
const messages      = document.getElementById("messages");
const userInput     = document.getElementById("userInput");
const sendBtn       = document.getElementById("sendBtn");
const welcomeScreen = document.getElementById("welcomeScreen");
const quickActions  = document.getElementById("quickActions");

// ── Language strings ──
const STRINGS = {
  en: {
    placeholder:  "Type your legal question... (Hindi or English)",
    welcomeTitle: "Namaste, I am NyayMitra",
    errorMsg:     "Sorry, server is not responding. Please check if backend is running.",
    thinking:     "NyayMitra is thinking...",
  },
  hi: {
    placeholder:  "Apna sawal likhein... (Hindi ya English mein)",
    welcomeTitle: "नमस्ते, मैं न्यायमित्र हूं",
    errorMsg:     "माफ़ करें, सर्वर से कनेक्शन नहीं हो पा रहा।",
    thinking:     "न्यायमित्र सोच रहा है...",
  }
};

const DOMAIN_QUERIES = {
  rti:          { en: "How do I file an RTI application in UP?",               hi: "UP mein RTI kaise file karein?" },
  fir:          { en: "Police is not registering my FIR, what should I do?",   hi: "Police FIR likhne se mana kar rahi hai kya karoon?" },
  property:     { en: "How to check land records in UP Bhulekh?",              hi: "UP Bhulekh mein apni zameen ki jaankari kaise dekhen?" },
  traffic:      { en: "How do I pay or dispute a traffic challan in UP?",      hi: "UP mein traffic challan kaise bharein ya dispute karein?" },
  women_safety: { en: "What are my rights under the Domestic Violence Act?",   hi: "Domestic Violence Act mein mujhe kya adhikar hain?" },
  tenant:       { en: "My landlord is not returning my security deposit.",      hi: "Mera landlord security deposit wapas nahi de raha kya karoon?" },
  sc_st:        { en: "What are my rights under the SC/ST Act?",               hi: "SC ST Act mein dalit naagrik ke kya adhikar hain?" },
  consumer:     { en: "I want to file a consumer complaint against a company.", hi: "Consumer complaint kaise darj karein?" },
  cyber:        { en: "I got cheated in a UPI fraud, what should I do?",       hi: "UPI fraud hua hai mujhse kya karoon?" },
  labour:       { en: "My employer is not paying my salary, what can I do?",   hi: "Employer salary nahi de raha hai kya karoon?" },
  family:       { en: "I need free legal aid for a family dispute.",            hi: "Family dispute ke liye free legal aid kahan milegi?" },
};

// ── INIT ──
document.addEventListener("DOMContentLoaded", () => {
  setLang("en");
  userInput.focus();
  checkHealth();
});

// ───────────────────────────────────────────────
// SIDEBAR
// ───────────────────────────────────────────────
function toggleSidebar() {
  document.getElementById("sidebar").classList.toggle("open");
  document.getElementById("sidebarOverlay").classList.toggle("open");
}

// ───────────────────────────────────────────────
// SEND MESSAGE
// ───────────────────────────────────────────────
async function sendMessage() {
  const text = userInput.value.trim();
  if (!text || isTyping) return;

  // Stop any TTS playing when user sends message
  stopSpeakingImmediate();

  if (welcomeVisible) {
    welcomeScreen.style.display = "none";
    welcomeVisible = false;
  }

  quickActions.innerHTML = "";
  appendBubble("user", text);
  userInput.value = "";
  autoResize(userInput);

  const typingId = showTyping();
  isTyping = true;
  sendBtn.disabled = true;

  try {
    const res = await fetch(`${API_BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: text,
        session_id: sessionId,
        conversation_history: conversationHistory.slice(-6),
      }),
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    removeTyping(typingId);
    appendBubble("bot", data.reply, {
      domain: data.domain,
      isEmergency: data.is_emergency,
      language: data.language,
    });

    conversationHistory.push({ role: "user",      content: text });
    conversationHistory.push({ role: "assistant", content: data.reply });
    if (conversationHistory.length > 10) conversationHistory = conversationHistory.slice(-10);

    if (data.quick_actions?.length) showQuickActions(data.quick_actions);
    if (data.domain && data.domain !== "general") setActivePill(data.domain);

  } catch (err) {
    removeTyping(typingId);
    appendBubble("bot", STRINGS[currentLang].errorMsg, { isError: true });
    console.error("Chat error:", err);
  }

  isTyping = false;
  sendBtn.disabled = false;
  userInput.focus();
}

// ───────────────────────────────────────────────
// RENDER BUBBLE
// ───────────────────────────────────────────────
function appendBubble(role, text, meta = {}) {
  const msgDiv = document.createElement("div");
  msgDiv.className = `message ${role}${meta.isEmergency ? " emergency" : ""}`;

  const avatar = document.createElement("div");
  avatar.className = "avatar";
  avatar.textContent = role === "user" ? "आप" : "⚖";

  const bubble = document.createElement("div");
  bubble.className = "bubble";

  if (role === "bot" && meta.domain && meta.domain !== "general") {
    const tag = document.createElement("div");
    tag.className = "domain-tag";
    tag.textContent = meta.domain.replace(/_/g, " ").toUpperCase();
    bubble.appendChild(tag);
  }

  if (meta.isEmergency) {
    const banner = document.createElement("div");
    banner.className = "emergency-banner";
    banner.textContent = "🚨 EMERGENCY — Call 112 immediately";
    bubble.appendChild(banner);
  }

  const textDiv = document.createElement("div");
  textDiv.className = "bubble-text";
  textDiv.innerHTML = formatText(text);
  bubble.appendChild(textDiv);

  const time = document.createElement("div");
  time.className = "msg-time";
  time.textContent = getTime();
  bubble.appendChild(time);

  msgDiv.appendChild(avatar);
  msgDiv.appendChild(bubble);
  messages.appendChild(msgDiv);
  scrollToBottom();

  // Auto TTS for bot replies
  if (role === "bot" && ttsEnabled && !meta.isError) {
    speakText(text, "auto");
  }
}

// ───────────────────────────────────────────────
// FORMAT TEXT — URL fix + legal section protection
// ───────────────────────────────────────────────
function formatText(text) {
  if (!text) return "";

  let safe = text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  // 1. Protect legal section numbers from being linkified
  const legalSections = [];
  safe = safe.replace(
    /(?:धारा|Section|IPC|BNS|CrPC|Act|section)\s+(\d+[A-Za-z]?(?:\s*[,\/]\s*\d+[A-Za-z]?)*)/gi,
    (match) => { const i = legalSections.length; legalSections.push(match); return `__L${i}__`; }
  );

  // 2. URLs — no trailing ) . , ; : captured
  safe = safe.replace(
    /(https?:\/\/[^\s<>&\)"\']+(?<![.,;:])|(?:www\.)?[a-zA-Z0-9][-a-zA-Z0-9]*\.(?:gov\.in|nic\.in|org\.in)(?:\/[a-zA-Z0-9\-._/?=&%#]*)?)/gi,
    (m) => {
      const href = m.startsWith("http") ? m : "https://" + m;
      const disp = m.replace(/^https?:\/\/(www\.)?/, "");
      return `<a href="${href}" target="_blank" class="msg-link msg-link-url" onclick="event.stopPropagation()">${disp}</a>`;
    }
  );

  // 3. Phone numbers → callable
  safe = safe.replace(
    /\b(\d{10}|\d{4}-\d{7}|\d{4}-\d{6}|1[0-9]{3,4}|[1-9][0-9]{2})\b/g,
    (m) => `<a href="tel:${m.replace(/-/g,"")}" class="msg-link msg-link-phone">${m}</a>`
  );

  // 4. Restore legal sections
  legalSections.forEach((orig, i) => { safe = safe.replace(`__L${i}__`, orig); });

  // 5. Numbered steps
  safe = safe.replace(
    /^(\d+)\.\s+(.+)$/gm,
    '<div class="step-item"><span class="step-num">$1</span><span>$2</span></div>'
  );

  safe = safe.replace(/\n\n/g, "<br><br>").replace(/\n/g, "<br>");
  return safe;
}

// ── TYPING ──
function showTyping() {
  const id = "t_" + Date.now();
  const d = document.createElement("div");
  d.className = "message bot"; d.id = id;
  const av = document.createElement("div");
  av.className = "avatar"; av.textContent = "⚖";
  const b = document.createElement("div");
  b.className = "typing-bubble";
  b.innerHTML = `<div class="dot"></div><div class="dot"></div><div class="dot"></div><span class="typing-text">${STRINGS[currentLang].thinking}</span>`;
  d.appendChild(av); d.appendChild(b);
  messages.appendChild(d);
  scrollToBottom();
  return id;
}
function removeTyping(id) { const el = document.getElementById(id); if (el) el.remove(); }

// ── QUICK ACTIONS ──
function showQuickActions(actions) {
  quickActions.innerHTML = "";
  actions.slice(0, 4).forEach(a => {
    const btn = document.createElement("button");
    btn.className = "qa-btn"; btn.textContent = a;
    btn.onclick = () => { userInput.value = a; sendMessage(); };
    quickActions.appendChild(btn);
  });
}

// ── DOMAIN PILLS ──
function askDomain(domain) {
  currentDomain = domain;
  setActivePill(domain);
  userInput.value = DOMAIN_QUERIES[domain]?.[currentLang] || `Tell me about ${domain} laws in UP`;
  sendMessage();
}
function setActivePill(domain) {
  document.querySelectorAll(".dpill").forEach(p => {
    p.classList.toggle("active", p.getAttribute("onclick")?.includes(`'${domain}'`));
  });
  document.querySelectorAll(".nav-item").forEach(p => {
    p.classList.toggle("active", p.getAttribute("onclick")?.includes(`'${domain}'`));
  });
}
function sendStarter(query) { userInput.value = query; sendMessage(); }

// ── LANGUAGE ──
function setLang(lang) {
  currentLang = lang;
  document.getElementById("btn-en").classList.toggle("active", lang === "en");
  document.getElementById("btn-hi").classList.toggle("active",  lang === "hi");
  userInput.placeholder = STRINGS[lang].placeholder;
  const t = document.getElementById("welcomeTitle");
  if (t) t.textContent = STRINGS[lang].welcomeTitle;
}

// ── EMERGENCY MODAL ──
function showEmergency()  { document.getElementById("emergencyModal").classList.add("open"); }
function closeEmergency() { document.getElementById("emergencyModal").classList.remove("open"); }
document.addEventListener("keydown", e => { if (e.key === "Escape") closeEmergency(); });

// ── INPUT HELPERS ──
function autoResize(el) {
  el.style.height = "auto";
  el.style.height = Math.min(el.scrollHeight, 120) + "px";
}
function handleKey(e) { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); } }
function scrollToBottom() { setTimeout(() => { chatArea.scrollTop = chatArea.scrollHeight; }, 50); }
function getTime() { return new Date().toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" }); }

// ── HEALTH CHECK ──
async function checkHealth() {
  const dot = document.getElementById("statusDot");
  try {
    const res = await fetch(`${API_BASE}/health`, { signal: AbortSignal.timeout(5000) });
    if (res.ok) {
      if (dot) { dot.classList.add("online"); dot.title = "Connected"; }
    } else throw new Error();
  } catch {
    if (dot) { dot.classList.add("offline"); dot.title = "Not connected"; }
    const cap = document.getElementById("inputCaption");
    if (cap) { cap.textContent = "⚠️ Server not connected — start backend first."; cap.style.color = "#C62828"; }
  }
}

// ───────────────────────────────────────────────
// TTS — Text to Speech (Chunked + Parallel + Smooth cancel)
// ───────────────────────────────────────────────
async function speakText(text, language = "auto") {
  if (!ttsEnabled || !text) return;

  // Smooth stop before starting new speech
  await stopSpeakingSmooth();

  ttsAbortCtrl = new AbortController();
  try {
    const res = await fetch(`${API_BASE}/tts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      signal: ttsAbortCtrl.signal,
      body: JSON.stringify({ text, language }),
    });
    if (!res.ok) return;
    const data = await res.json();
    if (!data.audio_chunks?.length) return;
    audioQueue = data.audio_chunks.map(b64ToAudio);
    playNextChunk();
  } catch (e) { if (e.name !== "AbortError") console.warn("TTS:", e); }
}

function b64ToAudio(b64) {
  const raw = atob(b64);
  const bytes = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
  const url = URL.createObjectURL(new Blob([bytes], { type: "audio/wav" }));
  const a = new Audio(url); a._url = url; return a;
}

function playNextChunk() {
  if (!audioQueue.length || !ttsEnabled) {
    isPlaying = false;
    currentAudio = null;
    showSpeakerIcon(false);
    // FIX: ready for next message after TTS completes
    userInput.focus();
    return;
  }
  isPlaying = true;
  showSpeakerIcon(true);
  const audio = audioQueue.shift();
  currentAudio = audio;
  audio.onended = () => { URL.revokeObjectURL(audio._url); currentAudio = null; playNextChunk(); };
  audio.onerror = () => { URL.revokeObjectURL(audio._url); currentAudio = null; playNextChunk(); };
  audio.play().catch(() => { currentAudio = null; playNextChunk(); });
}

// FIX: Smooth fade stop — 150ms fade out
async function stopSpeakingSmooth() {
  if (ttsAbortCtrl) { ttsAbortCtrl.abort(); ttsAbortCtrl = null; }

  if (currentAudio && isPlaying) {
    const audio = currentAudio;
    await new Promise((resolve) => {
      const fade = setInterval(() => {
        if (audio.volume > 0.08) {
          audio.volume = Math.max(0, audio.volume - 0.18);
        } else {
          clearInterval(fade);
          audio.volume = 0;
          audio.pause();
          resolve();
        }
      }, 20);
      setTimeout(() => { clearInterval(fade); try { audio.pause(); } catch {} resolve(); }, 200);
    });
  }

  audioQueue.forEach(a => { try { URL.revokeObjectURL(a._url); } catch {} });
  audioQueue = []; isPlaying = false; currentAudio = null;
  showSpeakerIcon(false);
}

// FIX: Immediate stop (no fade) — used when user sends new message
function stopSpeakingImmediate() {
  if (ttsAbortCtrl) { ttsAbortCtrl.abort(); ttsAbortCtrl = null; }
  if (currentAudio) { try { currentAudio.pause(); } catch {} currentAudio = null; }
  audioQueue.forEach(a => { try { URL.revokeObjectURL(a._url); } catch {} });
  audioQueue = []; isPlaying = false;
  showSpeakerIcon(false);
}

function toggleTTS() {
  ttsEnabled = !ttsEnabled;
  const btn = document.getElementById("ttsToggle");
  if (btn) {
    btn.textContent = ttsEnabled ? "🔊 Voice" : "🔇 Voice";
    btn.classList.toggle("active", ttsEnabled);
  }
  // FIX: smooth fade when toggling off
  if (!ttsEnabled) stopSpeakingSmooth();
}

// ───────────────────────────────────────────────
// ASR — Speech to Text
// FIX: stops TTS, waits if bot is responding, auto-sends, ready for next
// ───────────────────────────────────────────────
async function toggleRecording() {
  isRecording ? stopRecording() : await startRecording();
}

async function startRecording() {
  // FIX: stop TTS smoothly when mic pressed
  await stopSpeakingSmooth();

  // FIX: don't allow recording while bot is responding
  if (isTyping) {
    setCaption("⏳ Please wait for response...", false);
    return;
  }

  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    audioChunks = [];
    mediaRecorder = new MediaRecorder(stream, { mimeType: "audio/webm" });
    mediaRecorder.ondataavailable = e => { if (e.data.size > 0) audioChunks.push(e.data); };
    mediaRecorder.onstop = async () => {
      stream.getTracks().forEach(t => t.stop());
      await transcribeAudio(new Blob(audioChunks, { type: "audio/webm" }));
    };
    mediaRecorder.start();
    isRecording = true;
    setMicUI("recording");
  } catch (err) {
    setCaption(
      err.name === "NotAllowedError"
        ? "⚠️ Mic permission denied — allow in browser settings."
        : "⚠️ Mic not available.",
      true
    );
  }
}

function stopRecording() {
  if (mediaRecorder && isRecording) {
    mediaRecorder.stop();
    isRecording = false;
    setMicUI("loading");
  }
}

async function transcribeAudio(blob) {
  try {
    const fd = new FormData();
    fd.append("audio", blob, "recording.webm");
    fd.append("language", "unknown");
    const res = await fetch(`${API_BASE}/stt`, { method: "POST", body: fd });
    if (!res.ok) throw new Error();
    const data = await res.json();
    if (data.transcript?.trim()) {
      userInput.value = data.transcript;
      autoResize(userInput);
      userInput.focus(); // Show user what was transcribed
      // FIX: small delay so user sees transcript before auto-send
      setTimeout(() => sendMessage(), 500);
    } else {
      setCaption("🎤 Could not understand. Please try again or type.", true);
      userInput.focus(); // Ready for manual typing fallback
    }
  } catch {
    setCaption("⚠️ Speech recognition failed. Please type.", true);
    userInput.focus();
  } finally {
    setMicUI("idle");
  }
}

// ── SPEECH UI HELPERS ──
function setMicUI(state) {
  const btn = document.getElementById("micBtn");
  if (!btn) return;
  btn.className = "action-btn mic-btn";
  btn.disabled = false;
  if (state === "recording") {
    btn.classList.add("recording");
    btn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="6" width="12" height="12" rx="2"/></svg>`;
    btn.title = "Recording... tap to stop";
  } else if (state === "loading") {
    btn.innerHTML = `<span class="mic-loading">...</span>`;
    btn.disabled = true;
    btn.title = "Processing...";
  } else {
    btn.innerHTML = `<svg width="17" height="17" viewBox="0 0 24 24" fill="none"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" stroke="currentColor" stroke-width="2"/><path d="M19 10v2a7 7 0 0 1-14 0v-2M12 19v4M8 23h8" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>`;
    btn.title = "Click to speak";
  }
}

function showSpeakerIcon(show) {
  const bubbles = document.querySelectorAll(".message.bot .bubble");
  if (!bubbles.length) return;
  const last = bubbles[bubbles.length - 1];
  let icon = last.querySelector(".speaker-icon");
  if (show && !icon) {
    icon = document.createElement("span");
    icon.className = "speaker-icon";
    icon.textContent = " 🔊";
    last.appendChild(icon);
  } else if (!show && icon) {
    icon.remove();
  }
}

function setCaption(msg, isError = false) {
  const cap = document.getElementById("inputCaption");
  if (!cap) return;
  const orig = cap.textContent;
  const oc = cap.style.color;
  cap.textContent = msg;
  cap.style.color = isError ? "#C62828" : "";
  setTimeout(() => { cap.textContent = orig; cap.style.color = oc; }, 3000);
}