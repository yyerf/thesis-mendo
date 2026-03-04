(() => {
  const form = document.getElementById('nlpForm');
  const textEl = document.getElementById('nlpText');
  const analyzeBtn = document.getElementById('analyzeBtn');
  const clearBtn = document.getElementById('clearBtn');
  const ageHidden = document.getElementById('ageHidden');
  const coughHidden = document.getElementById('coughHidden');

  const ageModal = document.getElementById('ageModal');
  const ageInput = document.getElementById('ageInput');
  const ageCancel = document.getElementById('ageCancel');
  const ageConfirm = document.getElementById('ageConfirm');

  const loadingModal = document.getElementById('loadingModal');

  const micBtn = document.getElementById('micBtn');
  const micStatus = document.getElementById('micStatus');

  if (!form || !analyzeBtn || !textEl) return;

  const setHidden = (el, hidden) => {
    if (!el) return;
    el.classList.toggle('hidden', !!hidden);
  };

  const openAgeModal = () => {
    setHidden(ageModal, false);
    setTimeout(() => ageInput?.focus(), 0);
  };

  const closeAgeModal = () => {
    setHidden(ageModal, true);
  };

  const showLoading = () => {
    setHidden(loadingModal, false);
    if (analyzeBtn) analyzeBtn.disabled = true;
  };

  const validAge = (v) => {
    const raw = String(v ?? '').trim();
    if (!raw) return false;
    const n = Number(raw);
    return Number.isFinite(n) && n >= 0 && n <= 120;
  };

  // POS flow: user input first, then age modal on Analyze.
  form.addEventListener('submit', (ev) => {
    const text = (textEl.value || '').trim();
    if (!text) {
      ev.preventDefault();
      textEl.focus();
      return;
    }

    const age = ageHidden?.value;
    if (!validAge(age)) {
      ev.preventDefault();
      openAgeModal();
      return;
    }

    // Valid submission: show loading overlay while server assesses.
    showLoading();
  });

  ageCancel?.addEventListener('click', () => {
    closeAgeModal();
  });

  ageConfirm?.addEventListener('click', () => {
    const age = ageInput?.value;
    if (!validAge(age)) {
      ageInput?.focus();
      return;
    }
    if (ageHidden) ageHidden.value = String(Math.trunc(Number(age)));
    closeAgeModal();
    showLoading();
    // Submit after age is confirmed.
    form.requestSubmit?.() || form.submit();
  });

  clearBtn?.addEventListener('click', () => {
    textEl.value = '';
    if (ageHidden) ageHidden.value = '';
    if (coughHidden) coughHidden.value = '';
    if (ageInput) ageInput.value = '';
    textEl.focus();
  });

  // Browser Speech-to-Text (Web Speech API). This is client-side.
  const setMicStatus = (t) => {
    if (!micStatus) return;
    micStatus.textContent = t || '';
  };

  // OFFLINE STT: record audio, encode WAV, send to server `/api/stt`.
  const sttEndpoint = document.querySelector('meta[name="mendo-stt-endpoint"]')?.getAttribute('content') || '/api/stt';

  const supportsMic = () => !!navigator.mediaDevices?.getUserMedia;
  const isSecureForMic = () => window.isSecureContext || location.hostname === 'localhost' || location.hostname === '127.0.0.1';

  let recording = false;
  let audioContext = null;
  let mediaStream = null;
  let processor = null;
  let sourceNode = null;
  let buffers = [];
  let sampleRate = 44100;

  const mergeBuffers = (chunks) => {
    const total = chunks.reduce((sum, a) => sum + a.length, 0);
    const out = new Float32Array(total);
    let offset = 0;
    for (const c of chunks) {
      out.set(c, offset);
      offset += c.length;
    }
    return out;
  };

  const encodeWav16 = (samples, sr) => {
    // 16-bit PCM mono WAV
    const clamp = (v) => Math.max(-1, Math.min(1, v));
    const pcm = new Int16Array(samples.length);
    for (let i = 0; i < samples.length; i++) {
      pcm[i] = Math.round(clamp(samples[i]) * 0x7fff);
    }

    const headerSize = 44;
    const dataSize = pcm.length * 2;
    const buffer = new ArrayBuffer(headerSize + dataSize);
    const view = new DataView(buffer);
    let p = 0;
    const writeU32 = (v) => { view.setUint32(p, v, true); p += 4; };
    const writeU16 = (v) => { view.setUint16(p, v, true); p += 2; };
    const writeStr = (s) => { for (let i = 0; i < s.length; i++) view.setUint8(p++, s.charCodeAt(i)); };

    writeStr('RIFF');
    writeU32(36 + dataSize);
    writeStr('WAVE');
    writeStr('fmt ');
    writeU32(16);
    writeU16(1);      // PCM
    writeU16(1);      // mono
    writeU32(sr);
    writeU32(sr * 2); // byte rate
    writeU16(2);      // block align
    writeU16(16);     // bits
    writeStr('data');
    writeU32(dataSize);

    // PCM data
    let o = headerSize;
    for (let i = 0; i < pcm.length; i++, o += 2) {
      view.setInt16(o, pcm[i], true);
    }
    return new Blob([buffer], { type: 'audio/wav' });
  };

  const startRecording = async () => {
    if (!supportsMic()) {
      setMicStatus('Mic not supported in this browser.');
      return;
    }
    if (!isSecureForMic()) {
      setMicStatus('Mic blocked: use http://localhost:5000 (or HTTPS).');
      return;
    }
    try {
      setMicStatus('Requesting microphone…');
      mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (e) {
      const msg = (e && (e.name || e.message)) ? String(e.name || e.message) : 'permission denied';
      setMicStatus(`Mic permission failed: ${msg}`);
      return;
    }

    buffers = [];
    audioContext = new (window.AudioContext || window.webkitAudioContext)();
    sampleRate = audioContext.sampleRate || 44100;
    sourceNode = audioContext.createMediaStreamSource(mediaStream);
    // ScriptProcessor is deprecated but widely supported and simplest for offline WAV.
    processor = audioContext.createScriptProcessor(4096, 1, 1);
    processor.onaudioprocess = (ev) => {
      const input = ev.inputBuffer.getChannelData(0);
      buffers.push(new Float32Array(input));
    };
    sourceNode.connect(processor);
    processor.connect(audioContext.destination);

    recording = true;
    if (micBtn) micBtn.textContent = 'Stop Recording';
    setMicStatus('Recording…');
  };

  const stopRecording = async () => {
    recording = false;
    if (micBtn) micBtn.textContent = '🎙 Talk (Offline)';

    try { processor && processor.disconnect(); } catch {}
    try { sourceNode && sourceNode.disconnect(); } catch {}
    try { processor && (processor.onaudioprocess = null); } catch {}
    try { mediaStream && mediaStream.getTracks().forEach((t) => t.stop()); } catch {}
    try { audioContext && audioContext.close && (await audioContext.close()); } catch {}

    const samples = mergeBuffers(buffers);
    if (!samples.length) {
      setMicStatus('No audio captured.');
      return;
    }

    const wavBlob = encodeWav16(samples, sampleRate);
    const form = new FormData();
    form.append('audio', wavBlob, 'speech.wav');

    setMicStatus('Transcribing offline…');
    try {
      const res = await fetch(sttEndpoint, { method: 'POST', body: form });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
      const t = String(data.text || '').trim();
      if (!t) {
        setMicStatus('No speech recognized.');
        return;
      }
      const existing = (textEl.value || '').trim();
      textEl.value = [existing, t].filter(Boolean).join(existing ? ' ' : '');
      setMicStatus('');
      textEl.focus();
    } catch (e) {
      setMicStatus(`STT failed: ${e?.message || e}`);
    }
  };

  if (micBtn) {
    if (!supportsMic()) {
      micBtn.disabled = true;
      micBtn.title = 'Microphone recording not supported in this browser.';
      setMicStatus('Mic recording not supported here. Use Chrome/Edge.');
    }
    micBtn.addEventListener('click', () => {
      if (!supportsMic()) return;
      if (recording) stopRecording();
      else startRecording();
    });
  }
})();
