import React, { useState, useCallback, useRef, useEffect } from 'react';
import './App.css';
import axios from 'axios';
import unswLogo from './assets/UNSW_logo.png';
import data61Logo from './assets/data61-logo.png';
import exampleSite from './assets/hse-safety.jpg';
import hseRefinery  from './assets/hse-refinery.jpg';
import hseClimb     from './assets/hse-climb.jpg';
import hseBoiler    from './assets/hse-boiler.jpg';
import hsePpe       from './assets/hse-ppe.jpg';
import hseSandblast from './assets/hse-sandblast.jpg';
import hseWater     from './assets/hse-water.jpg';
import figArchitecture  from './assets/fig-architecture.png';
import figAiGrowth      from './assets/fig-ai_growth.png';
import figCrossBinding  from './assets/fig-cross_binding.png';
import figStripSurvival from './assets/fig-strip_survival.png';
import figRobustness    from './assets/fig-robustness.png';
import teamWeiSong from './assets/team_weisong.jpg';
import teamYuleiSui from './assets/team_yuleisui.jpg';
import teamZhenchangXing from './assets/team_zhenchangxing.jpg';
import teamJinglingXue from './assets/team_jinglingxue.jpeg';

// Default to same-origin: in production (Flask serves both frontend and API),
// the React app and the API live on the same host, so relative URLs are the
// safest default. The CRA dev server on :3000 proxies unprefixed requests to
// localhost:8000 via the "proxy" field in package.json, so dev mode still works.
const API_URL = process.env.REACT_APP_API_URL ?? '';
const ALLOWED_TYPES = ['image/jpeg', 'image/jpg', 'image/png'];
const MAX_FILE_BYTES = 10 * 1024 * 1024;

function validateFile(file) {
  if (!ALLOWED_TYPES.includes(file.type)) {
    return 'Invalid file type. Please upload a JPG, JPEG, or PNG image.';
  }
  if (file.size > MAX_FILE_BYTES) {
    return 'File size too large (max 10MB).';
  }
  return null;
}

function WarningBanner({ title, detail }) {
  return (
    <div className="feature-warning" role="alert">
      <svg className="warning-icon" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
        <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
        <line x1="12" y1="9" x2="12" y2="13"></line>
        <line x1="12" y1="17" x2="12.01" y2="17"></line>
      </svg>
      <div className="warning-body">
        <strong className="warning-title">{title}</strong>
        {detail && <span className="warning-detail">{detail}</span>}
      </div>
    </div>
  );
}

function FileDropZone({ panelId, file, preview, onFile, onClear, disabled }) {
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef(null);

  const handleDragEnter = (e) => { e.preventDefault(); e.stopPropagation(); setDragging(true); };
  const handleDragLeave = (e) => { e.preventDefault(); e.stopPropagation(); setDragging(false); };
  const handleDragOver = (e) => { e.preventDefault(); e.stopPropagation(); };
  const handleDrop = (e) => {
    e.preventDefault(); e.stopPropagation(); setDragging(false);
    const files = Array.from(e.dataTransfer.files);
    if (files.length > 0) onFile(files[0]);
  };
  const handleSelect = (e) => {
    const files = Array.from(e.target.files);
    if (files.length > 0) onFile(files[0]);
    e.target.value = '';
  };
  const loadExample = async () => {
    const resp = await fetch(exampleSite);
    const blob = await resp.blob();
    onFile(new File([blob], 'example-site.jpg', { type: blob.type || 'image/jpeg' }));
  };

  if (preview) {
    return (
      <div className="panel-preview">
        <img src={preview} alt={`${panelId} preview`} className="panel-preview-img" />
        <div className="panel-preview-meta">
          <span className="panel-preview-name" title={file?.name}>{file?.name}</span>
          <button className="panel-clear-btn" onClick={onClear} disabled={disabled} title="Remove">
            ✕
          </button>
        </div>
      </div>
    );
  }

  return (
    <div
      className={`panel-dropzone ${dragging ? 'dragging' : ''}`}
      onDragEnter={handleDragEnter}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      <svg className="panel-upload-icon" width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
        <polyline points="17 8 12 3 7 8"></polyline>
        <line x1="12" y1="3" x2="12" y2="15"></line>
      </svg>
      <p className="panel-dropzone-text">Drag &amp; drop or choose an image</p>
      <p className="panel-dropzone-hint">JPG / PNG, max 10MB</p>
      <div className="panel-dropzone-actions">
        <input
          ref={inputRef}
          type="file"
          id={`file-input-${panelId}`}
          className="file-input"
          accept="image/jpeg,image/jpg,image/png"
          onChange={handleSelect}
          disabled={disabled}
        />
        <label htmlFor={`file-input-${panelId}`} className="file-input-label">Choose file</label>
        <button className="example-image-button-small" onClick={loadExample} disabled={disabled}>
          Use example
        </button>
      </div>
    </div>
  );
}

function C2paPanel() {
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState(null);
  const [error, setError] = useState(null);
  const [downloadUrl, setDownloadUrl] = useState(null);
  const [downloadName, setDownloadName] = useState(null);
  const [downloadLabel, setDownloadLabel] = useState('Signed file');
  const [manifest, setManifest] = useState(null);
  const [hasC2pa, setHasC2pa] = useState(null);
  const [commonName, setCommonName] = useState('');
  const [issuer, setIssuer] = useState('');

  const reset = () => {
    setFile(null); setPreview(null); setError(null);
    setDownloadUrl(null); setDownloadName(null);
    setManifest(null); setHasC2pa(null);
    setCommonName(''); setIssuer('');
  };

  const onFile = useCallback((f) => {
    const err = validateFile(f);
    if (err) { setError(err); return; }
    setError(null); setDownloadUrl(null); setDownloadName(null);
    setManifest(null); setHasC2pa(null);
    const reader = new FileReader();
    reader.onloadend = () => { setPreview(reader.result); setFile(f); };
    reader.readAsDataURL(f);
  }, []);

  const handleSign = async () => {
    if (!file || busy) return;
    setBusy('sign'); setError(null); setManifest(null); setHasC2pa(null);
    try {
      const formData = new FormData();
      formData.append('file', file);
      if (commonName.trim()) formData.append('common_name', commonName.trim());
      if (issuer.trim())     formData.append('issuer',      issuer.trim());
      const resp = await axios.post(`${API_URL}/upload`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 180000,
      });
      setDownloadUrl(resp.data.download_url);
      setDownloadName(resp.data.filename);
      setDownloadLabel('Signed file');

      try {
        const signedResp = await axios.get(`${API_URL}${resp.data.download_url}`, {
          responseType: 'blob',
          timeout: 30000,
        });
        const signedBlob = signedResp.data;
        const verifyForm = new FormData();
        verifyForm.append('file', new File([signedBlob], resp.data.filename, { type: signedBlob.type || 'image/jpeg' }));
        const verifyResp = await axios.post(`${API_URL}/read-c2pa-upload`, verifyForm, {
          headers: { 'Content-Type': 'multipart/form-data' },
          timeout: 30000,
        });
        if (verifyResp.data.success && verifyResp.data.has_c2pa) {
          setManifest(verifyResp.data.manifest);
          setHasC2pa(true);
        }
      } catch (verifyErr) {
        console.warn('Auto-verify after sign failed:', verifyErr);
      }
    } catch (err) {
      setError(err.response?.data?.error || err.response?.data?.details || err.message);
    } finally {
      setBusy(null);
    }
  };

  const handleVerify = async () => {
    if (!file || busy) return;
    setBusy('verify'); setError(null); setManifest(null); setHasC2pa(null);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const resp = await axios.post(`${API_URL}/read-c2pa-upload`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 60000,
      });
      if (resp.data.success && resp.data.has_c2pa) {
        setManifest(resp.data.manifest);
        setHasC2pa(true);
      } else {
        setHasC2pa(false);
      }
    } catch (err) {
      if (err.response?.data?.has_c2pa === false) {
        setHasC2pa(false);
      } else {
        setError(err.response?.data?.error || err.message);
      }
    } finally {
      setBusy(null);
    }
  };

  const handleStrip = async () => {
    if (!file || busy) return;
    setBusy('strip'); setError(null); setManifest(null); setHasC2pa(null);
    setDownloadUrl(null); setDownloadName(null);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const resp = await axios.post(`${API_URL}/strip-c2pa-upload`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 60000,
      });
      setDownloadUrl(resp.data.download_url);
      setDownloadName(resp.data.filename);
      setDownloadLabel('Unsigned file (signature removed)');
    } catch (err) {
      setError(err.response?.data?.error || err.response?.data?.details || err.message);
    } finally {
      setBusy(null);
    }
  };

  const handleDownload = () => {
    if (!downloadUrl) return;
    window.location.href = `${API_URL}${downloadUrl}`;
  };

  return (
    <section className="feature-panel feature-panel-c2pa">
      <header className="feature-header">
        <h2 className="feature-title">C2PA Signing</h2>
        <p className="feature-subtitle">Sign images with verifiable provenance credentials</p>
      </header>

      <FileDropZone
        panelId="c2pa"
        file={file}
        preview={preview}
        onFile={onFile}
        onClear={reset}
        disabled={!!busy}
      />

      <div className="manifest-input-grid">
        <div className="manifest-input-field">
          <label htmlFor="c2pa-common-name" className="wm-message-label">Common name <span className="manifest-input-hint">(optional)</span></label>
          <input
            id="c2pa-common-name"
            type="text"
            className="wm-message-input"
            value={commonName}
            onChange={(e) => setCommonName(e.target.value)}
            placeholder="e.g. Wei Song"
            maxLength={120}
            disabled={!!busy}
          />
        </div>
        <div className="manifest-input-field">
          <label htmlFor="c2pa-issuer" className="wm-message-label">Issuer <span className="manifest-input-hint">(optional)</span></label>
          <input
            id="c2pa-issuer"
            type="text"
            className="wm-message-input"
            value={issuer}
            onChange={(e) => setIssuer(e.target.value)}
            placeholder="e.g. UNSW Sydney"
            maxLength={120}
            disabled={!!busy}
          />
        </div>
      </div>

      <div className="feature-actions">
        <button
          className="feature-btn primary"
          onClick={handleSign}
          disabled={!file || !!busy}
        >
          {busy === 'sign' ? (<><span className="btn-spinner"></span>Signing…</>) : 'Sign image'}
        </button>
        <button
          className="feature-btn secondary"
          onClick={handleVerify}
          disabled={!file || !!busy}
        >
          {busy === 'verify' ? (<><span className="btn-spinner"></span>Verifying…</>) : 'Verify C2PA'}
        </button>
        <button
          className="feature-btn secondary"
          onClick={handleStrip}
          disabled={!file || !!busy}
        >
          {busy === 'strip' ? (<><span className="btn-spinner"></span>Removing…</>) : 'Remove signature'}
        </button>
      </div>

      {error && <div className="feature-error">⚠ {error}</div>}

      {downloadUrl && (
        <div className="feature-result success">
          <div className="result-row">
            <span>✅ {downloadLabel}: <code>{downloadName}</code></span>
          </div>
          <button className="feature-btn download" onClick={handleDownload}>
            Download
          </button>
        </div>
      )}

      {hasC2pa === false && (
        <WarningBanner title="This file is NOT signed!" detail="No C2PA manifest was found. Use “Sign image” to add one." />
      )}

      {hasC2pa === true && manifest && (
        <div className="feature-result">
          <h3 className="result-title">C2PA manifest</h3>
          <C2paManifestView manifest={manifest} />
        </div>
      )}
    </section>
  );
}

function C2paManifestView({ manifest }) {
  const activeId = manifest.active_manifest;
  const active = activeId && manifest.manifests ? manifest.manifests[activeId] : null;
  const sig = active?.signature_info || {};
  const validationState = manifest.validation_state || 'unknown';

  // Pull failures so we can decide what kind of warning to show.
  const failures = manifest?.validation_results?.activeManifest?.failure || [];

  // "Integrity failures" mean the file has actually been tampered with — these
  // get the loud red banner. "Trust failures" (untrusted root, untrusted TSA)
  // mean the cert chain isn't anchored to a real CA — we surface those
  // separately as informational, because they're expected for a demo signer
  // and don't mean someone tampered with the asset.
  const INTEGRITY_CODES = new Set([
    'claimSignature.mismatch',
    'assertion.hashedURI.mismatch',
    'assertion.dataHash.mismatch',
    'assertion.hashedURI.notFound',
    'claimSignature.missing',
    'claim.missing',
  ]);
  const integrityFailures = failures.filter(f => INTEGRITY_CODES.has(f.code));
  const trustFailures     = failures.filter(f => !INTEGRITY_CODES.has(f.code));
  const isTampered = integrityFailures.length > 0;
  const isUntrusted = trustFailures.length > 0;

  const tamperDetail = integrityFailures
    .map(f => f.explanation || f.code)
    .filter(Boolean)
    .slice(0, 3)
    .join('; ');

  // Common name + Issuer come from the CreativeWork assertion we injected at
  // sign time (the cert subject itself is Adobe's test cert and not shown).
  const creativeWork = (active?.assertions || []).find(
    a => a.label === 'stds.schema-org.CreativeWork'
  )?.data;
  const claimedCommonName = creativeWork?.author?.[0]?.name || null;
  const claimedIssuer     = creativeWork?.publisher?.name  || null;

  // The Validation badge reflects the signature's integrity. Trust failures
  // (untrusted CA — expected for a demo cert) don't downgrade it; only an
  // actual signature/asset-hash mismatch makes it "Invalid".
  let badgeClass = 'badge-ok';
  let badgeText  = 'Valid';
  if (isTampered) { badgeClass = 'badge-bad'; badgeText = 'Invalid'; }

  return (
    <div className="c2pa-manifest-view">
      {isTampered && (
        <WarningBanner
          title="The signature is modified and invalid!"
          detail={tamperDetail || `Validation state: ${validationState}`}
        />
      )}
      <div className="manifest-info">
        <div className="manifest-row"><span>Common name</span><strong>{claimedCommonName || '—'}</strong></div>
        <div className="manifest-row"><span>Issuer</span><strong>{claimedIssuer || '—'}</strong></div>
        <div className="manifest-row"><span>Signed at</span><strong>{sig.time ? new Date(sig.time).toLocaleString() : '—'}</strong></div>
        <div className="manifest-row"><span>Claim generator</span><strong>{active?.claim_generator || '—'}</strong></div>
        <div className="manifest-row">
          <span>Validation</span>
          <strong className={badgeClass}>{badgeText}</strong>
        </div>
        {active?.assertions && active.assertions.length > 0 && (
          <div className="manifest-row">
            <span>Assertions</span>
            <strong>{active.assertions.map(a => a.label).join(', ')}</strong>
          </div>
        )}
      </div>
      <details className="manifest-raw">
        <summary>Raw JSON</summary>
        <pre>{JSON.stringify(manifest, null, 2)}</pre>
      </details>
    </div>
  );
}

function WatermarkPanel() {
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState(null);
  const [error, setError] = useState(null);
  const [message, setMessage] = useState('UNSW CSE');
  const [downloadUrl, setDownloadUrl] = useState(null);
  const [downloadName, setDownloadName] = useState(null);
  const [encodedMessage, setEncodedMessage] = useState(null);
  const [decoded, setDecoded] = useState(null);
  const [hasWatermark, setHasWatermark] = useState(null);

  // C2PA-derived watermark option ----
  const [useC2paHash, setUseC2paHash] = useState(false);
  const [derivedHash, setDerivedHash] = useState(null);
  const [hashStatus, setHashStatus] = useState(null); // null | 'deriving' | 'ok' | 'no-c2pa'

  const reset = () => {
    setFile(null); setPreview(null); setError(null);
    setDownloadUrl(null); setDownloadName(null); setEncodedMessage(null);
    setDecoded(null); setHasWatermark(null);
    setUseC2paHash(false); setDerivedHash(null); setHashStatus(null);
  };

  const onFile = useCallback((f) => {
    const err = validateFile(f);
    if (err) { setError(err); return; }
    setError(null); setDownloadUrl(null); setDownloadName(null);
    setEncodedMessage(null); setDecoded(null); setHasWatermark(null);
    setUseC2paHash(false); setDerivedHash(null); setHashStatus(null);
    const reader = new FileReader();
    reader.onloadend = () => { setPreview(reader.result); setFile(f); };
    reader.readAsDataURL(f);
  }, []);

  // When the toggle is on and a file is loaded, fetch the C2PA manifest and
  // derive a 12-char SHA-256 hex prefix to use as the watermark payload.
  useEffect(() => {
    if (!file || !useC2paHash) {
      setDerivedHash(null);
      setHashStatus(null);
      return;
    }
    let cancelled = false;
    setHashStatus('deriving');
    (async () => {
      try {
        const fd = new FormData();
        fd.append('file', file);
        const resp = await axios.post(`${API_URL}/read-c2pa-upload`, fd, {
          headers: { 'Content-Type': 'multipart/form-data' },
          timeout: 30000,
        });
        if (cancelled) return;
        if (resp.data?.success && resp.data?.has_c2pa) {
          const manifestText = JSON.stringify(resp.data.manifest);
          const buf = new TextEncoder().encode(manifestText);
          const hashBuf = await crypto.subtle.digest('SHA-256', buf);
          if (cancelled) return;
          const hex = Array.from(new Uint8Array(hashBuf))
            .map(b => b.toString(16).padStart(2, '0')).join('');
          setDerivedHash(hex.slice(0, 12));
          setHashStatus('ok');
        } else {
          setHashStatus('no-c2pa');
          setDerivedHash(null);
        }
      } catch (err) {
        if (cancelled) return;
        setHashStatus('no-c2pa');
        setDerivedHash(null);
      }
    })();
    return () => { cancelled = true; };
  }, [file, useC2paHash]);

  // The actual payload sent to embed/decode. When the toggle is on and a hash
  // was successfully derived, we use that; otherwise fall back to the typed
  // message (handles unsigned input gracefully).
  const effectiveMessage = (useC2paHash && derivedHash) ? derivedHash : message;
  const effectiveBytes = new TextEncoder().encode(effectiveMessage).length;
  const messageTooLong = effectiveBytes > 12;

  const handleEmbed = async () => {
    if (!file || busy || messageTooLong) return;
    setBusy('embed'); setError(null); setDecoded(null); setHasWatermark(null);
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('message', effectiveMessage);
      const resp = await axios.post(`${API_URL}/watermark-upload`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 180000,
      });
      setDownloadUrl(resp.data.download_url);
      setDownloadName(resp.data.filename);
      setEncodedMessage(resp.data.encoded_message ?? effectiveMessage);
    } catch (err) {
      setError(err.response?.data?.error || err.response?.data?.message || err.message);
    } finally {
      setBusy(null);
    }
  };

  const handleDecode = async () => {
    if (!file || busy) return;
    setBusy('decode'); setError(null); setDecoded(null); setHasWatermark(null);
    try {
      const formData = new FormData();
      formData.append('file', file);
      if (effectiveMessage) formData.append('expected_message', effectiveMessage);
      const resp = await axios.post(`${API_URL}/decode-watermark-upload`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 60000,
      });
      const d = resp.data || {};
      setDecoded({
        message: d.decoded_message ?? '',
        bits: d.watermark ?? [],
        accuracy: d.accuracy ?? null,
        isText: !!d.is_text,
      });
      setHasWatermark(!!d.has_watermark);
    } catch (err) {
      setError(err.response?.data?.error || err.message);
    } finally {
      setBusy(null);
    }
  };

  const handleDownload = () => {
    if (!downloadUrl) return;
    window.location.href = `${API_URL}${downloadUrl}`;
  };

  return (
    <section className="feature-panel feature-panel-watermark">
      <header className="feature-header">
        <h2 className="feature-title">Invisible Watermarking</h2>
        <p className="feature-subtitle">Embed and recover invisible watermarks</p>
      </header>

      <FileDropZone
        panelId="watermark"
        file={file}
        preview={preview}
        onFile={onFile}
        onClear={reset}
        disabled={!!busy}
      />

      <div className="wm-message-field">
        <label className="wm-c2pa-toggle">
          <input
            type="checkbox"
            checked={useC2paHash}
            onChange={(e) => setUseC2paHash(e.target.checked)}
            disabled={!!busy}
          />
          <span>Derive watermark from C2PA manifest (SHA-256, 12 hex chars)</span>
        </label>

        {/* Three distinct UI states for the message field:
            1) Toggle off → editable text input
            2) Toggle on + no C2PA → no input, explicit warning + two ways out
            3) Toggle on + C2PA → read-only derived hex hash */}

        {!useC2paHash && (
          <>
            <label htmlFor="wm-message-input" className="wm-message-label">
              Watermark message
              <span className={`wm-message-counter ${messageTooLong ? 'over' : ''}`}>
                {effectiveBytes}/12 bytes
              </span>
            </label>
            <input
              id="wm-message-input"
              type="text"
              className="wm-message-input"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="e.g. your name"
              disabled={!!busy}
            />
            {messageTooLong && (
              <p className="wm-message-hint">
                Too long — the watermark stores at most 12 UTF-8 bytes; anything beyond will be truncated.
              </p>
            )}
          </>
        )}

        {useC2paHash && hashStatus === 'deriving' && (
          <p className="wm-message-hint wm-message-hint--info">
            Reading C2PA manifest from the file…
          </p>
        )}

        {useC2paHash && hashStatus === 'no-c2pa' && (
          <WarningBanner
            title="This image isn't C2PA-signed — can't derive a watermark from it."
            detail="Either uncheck the box above to type a watermark message manually, or sign the image first in the “C2PA” tab and come back."
          />
        )}

        {useC2paHash && hashStatus === 'ok' && (
          <>
            <label htmlFor="wm-message-input" className="wm-message-label">
              Derived watermark
              <span className={`wm-message-counter ${messageTooLong ? 'over' : ''}`}>
                {effectiveBytes}/12 bytes
              </span>
            </label>
            <input
              id="wm-message-input"
              type="text"
              className="wm-message-input wm-message-input--derived"
              value={derivedHash}
              readOnly
              disabled={!!busy}
              title="Derived from the uploaded image's C2PA manifest"
            />
            <p className="wm-message-hint wm-message-hint--info">
              SHA-256 prefix of the verified C2PA manifest. Tampering with either the manifest or the pixels will desynchronise the two.
            </p>
          </>
        )}
      </div>

      <div className="feature-actions">
        <button
          className="feature-btn primary"
          onClick={handleEmbed}
          disabled={!file || !!busy || messageTooLong || (useC2paHash && hashStatus !== 'ok')}
        >
          {busy === 'embed' ? (<><span className="btn-spinner"></span>Embedding…</>) : 'Embed watermark'}
        </button>
        <button
          className="feature-btn secondary"
          onClick={handleDecode}
          disabled={!file || !!busy}
        >
          {busy === 'decode' ? (<><span className="btn-spinner"></span>Decoding…</>) : 'Decode watermark'}
        </button>
      </div>

      {error && <div className="feature-error">⚠ {error}</div>}

      {downloadUrl && (
        <div className="feature-result success">
          <div className="result-row">
            <span>✅ Watermark embedded as <strong>“{encodedMessage}”</strong></span>
          </div>
          <div className="result-row">
            <span>File: <code>{downloadName}</code></span>
          </div>
          <button className="feature-btn download" onClick={handleDownload}>
            Download watermarked image
          </button>
        </div>
      )}

      {hasWatermark === false && decoded && (
        <WarningBanner
          title="This image is NOT watermarked!"
          detail={`The decoder returned “${decoded.message || '<unprintable bytes>'}” which doesn't look like real text — usually meaning this image was never watermarked, or the watermark was destroyed.`}
        />
      )}

      {hasWatermark === true && decoded && (
        <div className="feature-result">
          <h3 className="result-title">Decoded watermark</h3>
          <DecodedWatermarkView decoded={decoded} />
        </div>
      )}
    </section>
  );
}

function DecodedWatermarkView({ decoded }) {
  return (
    <div className="watermark-bits-view">
      <div className="manifest-row">
        <span>Decoded message</span>
        <strong className="wm-decoded-message">“{decoded.message || '<empty>'}”</strong>
      </div>
      <div className="manifest-row">
        <span>Total bits</span><strong>{decoded.bits.length}</strong>
      </div>
      <details className="manifest-raw">
        <summary>Raw bit pattern</summary>
        <code className="bit-string">{decoded.bits.join('')}</code>
      </details>
    </div>
  );
}

function CombinedPanel() {
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [downloadUrl, setDownloadUrl] = useState(null);
  const [downloadName, setDownloadName] = useState(null);
  const [commonName, setCommonName] = useState('');
  const [issuer, setIssuer] = useState('');
  const [wmMessage, setWmMessage] = useState('UNSW CSE');
  const [wmAccuracy, setWmAccuracy] = useState(null);
  const [useIdentityHash, setUseIdentityHash] = useState(false);
  const [derivedHash, setDerivedHash] = useState('');

  const reset = () => {
    setFile(null); setPreview(null); setError(null);
    setDownloadUrl(null); setDownloadName(null);
    setCommonName(''); setIssuer(''); setWmMessage('UNSW CSE'); setWmAccuracy(null);
    setUseIdentityHash(false); setDerivedHash('');
  };

  const onFile = useCallback((f) => {
    const err = validateFile(f);
    if (err) { setError(err); return; }
    setError(null); setDownloadUrl(null); setDownloadName(null); setWmAccuracy(null);
    const reader = new FileReader();
    reader.onloadend = () => { setPreview(reader.result); setFile(f); };
    reader.readAsDataURL(f);
  }, []);

  // When the "derive" toggle is on and both CN + Issuer are filled, compute
  // a 12-hex-char SHA-256 prefix of (common_name | issuer). Bound to the same
  // 96-bit payload size as the typed watermark. When either field is empty,
  // we leave derivedHash blank and the UI nudges the user to fill them in.
  useEffect(() => {
    if (!useIdentityHash) { setDerivedHash(''); return; }
    const cn = commonName.trim();
    const iss = issuer.trim();
    if (!cn || !iss) { setDerivedHash(''); return; }
    let cancelled = false;
    (async () => {
      const buf = new TextEncoder().encode(cn + '|' + iss);
      const hashBuf = await crypto.subtle.digest('SHA-256', buf);
      if (cancelled) return;
      const hex = Array.from(new Uint8Array(hashBuf))
        .map(b => b.toString(16).padStart(2, '0')).join('');
      setDerivedHash(hex.slice(0, 12));
    })();
    return () => { cancelled = true; };
  }, [useIdentityHash, commonName, issuer]);

  const effectiveMessage = useIdentityHash ? derivedHash : wmMessage;
  const wmBytes = new TextEncoder().encode(effectiveMessage).length;
  const wmTooLong = wmBytes > 12;
  const identityIncomplete = useIdentityHash && (!commonName.trim() || !issuer.trim());

  const handleRun = async () => {
    if (!file || busy || wmTooLong || identityIncomplete) return;
    setBusy(true); setError(null); setWmAccuracy(null);
    try {
      const formData = new FormData();
      formData.append('file', file);
      if (commonName.trim()) formData.append('common_name', commonName.trim());
      if (issuer.trim())     formData.append('issuer',      issuer.trim());
      if (effectiveMessage)  formData.append('message',     effectiveMessage);
      const resp = await axios.post(`${API_URL}/sign-and-watermark-upload`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 240000,
      });
      setDownloadUrl(resp.data.download_url);
      setDownloadName(resp.data.filename);
      if (typeof resp.data.watermark_accuracy === 'number') {
        setWmAccuracy(resp.data.watermark_accuracy);
      }
    } catch (err) {
      setError(err.response?.data?.error || err.response?.data?.message || err.message);
    } finally {
      setBusy(false);
    }
  };

  const handleDownload = () => {
    if (!downloadUrl) return;
    window.location.href = `${API_URL}${downloadUrl}`;
  };

  return (
    <section className="feature-panel feature-panel-combined">
      <header className="feature-header">
        <h2 className="feature-title">DCP — full protection</h2>
        <p className="feature-subtitle">Apply C2PA signing and invisible watermarking in one pass</p>
      </header>

      <div className="combined-body">
        <FileDropZone
          panelId="combined"
          file={file}
          preview={preview}
          onFile={onFile}
          onClear={reset}
          disabled={busy}
        />

        <div className="manifest-input-grid">
          <div className="manifest-input-field">
            <label htmlFor="dcp-common-name" className="wm-message-label">Common name <span className="manifest-input-hint">(optional)</span></label>
            <input
              id="dcp-common-name"
              type="text"
              className="wm-message-input"
              value={commonName}
              onChange={(e) => setCommonName(e.target.value)}
              placeholder="e.g. Wei Song"
              maxLength={120}
              disabled={busy}
            />
          </div>
          <div className="manifest-input-field">
            <label htmlFor="dcp-issuer" className="wm-message-label">Issuer <span className="manifest-input-hint">(optional)</span></label>
            <input
              id="dcp-issuer"
              type="text"
              className="wm-message-input"
              value={issuer}
              onChange={(e) => setIssuer(e.target.value)}
              placeholder="e.g. UNSW Sydney"
              maxLength={120}
              disabled={busy}
            />
          </div>
        </div>

        <div className="wm-message-field">
          <label className="wm-c2pa-toggle">
            <input
              type="checkbox"
              checked={useIdentityHash}
              onChange={(e) => setUseIdentityHash(e.target.checked)}
              disabled={busy}
            />
            <span>Derive watermark from C2PA identity (SHA-256 of Common name + Issuer)</span>
          </label>

          {!useIdentityHash && (
            <>
              <label htmlFor="dcp-wm-message" className="wm-message-label">
                Watermark message
                <span className={`wm-message-counter ${wmTooLong ? 'over' : ''}`}>
                  {wmBytes}/12 bytes
                </span>
              </label>
              <input
                id="dcp-wm-message"
                type="text"
                className="wm-message-input"
                value={wmMessage}
                onChange={(e) => setWmMessage(e.target.value)}
                placeholder="e.g. UNSW CSE"
                disabled={busy}
              />
              {wmTooLong && (
                <p className="wm-message-hint">
                  Too long — the watermark stores at most 12 UTF-8 bytes; anything beyond will be truncated.
                </p>
              )}
            </>
          )}

          {useIdentityHash && identityIncomplete && (
            <WarningBanner
              title="Common name and Issuer are required for identity-derived watermark."
              detail="Fill in both fields above, or uncheck the box to type a watermark message manually."
            />
          )}

          {useIdentityHash && !identityIncomplete && (
            <>
              <label htmlFor="dcp-wm-message" className="wm-message-label">
                Derived watermark
                <span className="wm-message-counter">{wmBytes}/12 bytes</span>
              </label>
              <input
                id="dcp-wm-message"
                type="text"
                className="wm-message-input wm-message-input--derived"
                value={derivedHash}
                readOnly
                disabled={busy}
                title="SHA-256 prefix of Common name + Issuer"
              />
              <p className="wm-message-hint wm-message-hint--info">
                Binds the watermark to the identity claim. A C2PA viewer can recover this watermark from the pixels and confirm it matches the manifest's Common name + Issuer.
              </p>
            </>
          )}
        </div>

        <div className="feature-actions">
          <button
            className="feature-btn primary"
            onClick={handleRun}
            disabled={!file || busy || wmTooLong || identityIncomplete}
          >
            {busy ? (<><span className="btn-spinner"></span>Processing…</>) : 'Sign & watermark'}
          </button>
        </div>

        {error && <div className="feature-error">⚠ {error}</div>}

        {downloadUrl && (
          <div className="feature-result success">
            <div className="result-row">
              <span>✅ Signed &amp; watermarked file ready: <code>{downloadName}</code></span>
            </div>
            {wmAccuracy != null && (
              <div className="result-row">
                <span>
                  Watermark embedded with {useIdentityHash ? 'identity-derived hash' : 'message'} <strong>“{effectiveMessage}”</strong>.
                </span>
              </div>
            )}
            <button className="feature-btn download" onClick={handleDownload}>
              Download
            </button>
          </div>
        )}
      </div>
    </section>
  );
}

// Extract the human-readable strings we can offer as tamper targets from a
// manifest. Each entry is { label, value } and we only include ones that look
// safe to byte-search-and-replace (i.e. unique-ish strings present verbatim in
// the file). VINE's CBOR encoding embeds these as UTF-8.
function manifestTamperTargets(manifest) {
  const activeId = manifest?.active_manifest;
  const active = activeId && manifest?.manifests ? manifest.manifests[activeId] : null;
  if (!active) return [];

  // Prefer the CreativeWork assertion (where the user's typed Common name /
  // Issuer live) over the cert-derived signature_info (which is the underlying
  // Adobe test cert, "John Smith" / "C2PA Python Demo"). Falling back to the
  // cert means we still offer something useful on files signed without the
  // CreativeWork assertion.
  const sig = active.signature_info || {};
  const creativeWork = (active.assertions || []).find(
    a => a.label === 'stds.schema-org.CreativeWork'
  )?.data;
  const claimedCN  = creativeWork?.author?.[0]?.name;
  const claimedIss = creativeWork?.publisher?.name;

  const candidates = [
    { label: 'Common name', value: claimedCN  || sig.common_name },
    { label: 'Issuer',      value: claimedIss || sig.issuer },
    { label: 'Claim generator', value: active.claim_generator },
  ];
  return candidates.filter(c => typeof c.value === 'string' && c.value.length >= 2);
}

function TamperPanel() {
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState(null); // 'inspect' | 'tamper-image' | 'tamper-manifest'
  const [error, setError] = useState(null);
  const [sourceManifest, setSourceManifest] = useState(null);
  const [hasC2pa, setHasC2pa] = useState(null);
  const [downloadUrl, setDownloadUrl] = useState(null);
  const [downloadName, setDownloadName] = useState(null);
  const [tamperSummary, setTamperSummary] = useState(null);
  const [selectedField, setSelectedField] = useState(0);
  const [newValue, setNewValue] = useState('');

  const reset = () => {
    setFile(null); setPreview(null); setError(null);
    setSourceManifest(null); setHasC2pa(null);
    setDownloadUrl(null); setDownloadName(null); setTamperSummary(null);
    setSelectedField(0); setNewValue('');
  };

  const clearOutputs = () => {
    setDownloadUrl(null); setDownloadName(null); setTamperSummary(null);
    setError(null);
  };

  const inspect = async (f) => {
    setBusy('inspect');
    try {
      const fd = new FormData();
      fd.append('file', f);
      const resp = await axios.post(`${API_URL}/read-c2pa-upload`, fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 60000,
      });
      if (resp.data.success && resp.data.has_c2pa) {
        setSourceManifest(resp.data.manifest);
        setHasC2pa(true);
        const targets = manifestTamperTargets(resp.data.manifest);
        if (targets.length > 0) setNewValue(targets[0].value);
      } else {
        setHasC2pa(false);
      }
    } catch (err) {
      setError(err.response?.data?.error || err.message);
    } finally {
      setBusy(null);
    }
  };

  const onFile = useCallback((f) => {
    const err = validateFile(f);
    if (err) { setError(err); return; }
    reset();
    const reader = new FileReader();
    reader.onloadend = () => {
      setPreview(reader.result);
      setFile(f);
      inspect(f);
    };
    reader.readAsDataURL(f);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleTamperImage = async () => {
    if (!file || busy) return;
    clearOutputs();
    setBusy('tamper-image');
    try {
      const fd = new FormData();
      fd.append('file', file);
      const resp = await axios.post(`${API_URL}/tamper-image-upload`, fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 60000,
      });
      setDownloadUrl(resp.data.download_url);
      setDownloadName(resp.data.filename);
      setTamperSummary(resp.data.message);
    } catch (err) {
      setError(err.response?.data?.error || err.response?.data?.details || err.message);
    } finally {
      setBusy(null);
    }
  };

  const targets = sourceManifest ? manifestTamperTargets(sourceManifest) : [];
  const target = targets[selectedField] || null;
  const oldLen = target ? target.value.length : 0;
  const newLen = new TextEncoder().encode(newValue).length;
  // We compare *string length* not byte length because the backend does the
  // same length check; the warning about UTF-8 is just for the user.
  const lengthOk = target ? newValue.length === target.value.length : false;
  const isMultibyte = newLen !== newValue.length;

  const handleTamperManifest = async () => {
    if (!file || busy || !target || !lengthOk) return;
    clearOutputs();
    setBusy('tamper-manifest');
    try {
      const fd = new FormData();
      fd.append('file', file);
      fd.append('old_value', target.value);
      fd.append('new_value', newValue);
      const resp = await axios.post(`${API_URL}/tamper-manifest-upload`, fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 60000,
      });
      setDownloadUrl(resp.data.download_url);
      setDownloadName(resp.data.filename);
      setTamperSummary(resp.data.message);
    } catch (err) {
      setError(err.response?.data?.error || err.response?.data?.details || err.message);
    } finally {
      setBusy(null);
    }
  };

  const handleDownload = () => {
    if (!downloadUrl) return;
    window.location.href = `${API_URL}${downloadUrl}`;
  };

  return (
    <section className="feature-panel feature-panel-tamper">
      <header className="feature-header">
        <h2 className="feature-title">C2PA Tamper</h2>
        <p className="feature-subtitle">
          Modify a signed image and watch C2PA verification reject it.
        </p>
      </header>

      <FileDropZone
        panelId="tamper"
        file={file}
        preview={preview}
        onFile={onFile}
        onClear={reset}
        disabled={!!busy}
      />

      {busy === 'inspect' && <div className="feature-result info">Inspecting the uploaded file…</div>}

      {file && hasC2pa === false && (
        <WarningBanner
          title="This file is NOT signed!"
          detail="The C2PA Tamper demo needs a C2PA-signed image. Sign one in the “C2PA” tab first."
        />
      )}

      {file && hasC2pa === true && (
        <>
          <div className="feature-result info">
            ✓ This file is signed. Pick a tamper mode below — both should make the signature invalid.
          </div>

          <div className="tamper-mode-block">
            <h3 className="tamper-mode-title">A. Modify image pixels</h3>
            <p className="tamper-mode-desc">
              Flip ~16 bytes in the compressed image data. The C2PA asset-hash assertion will fail.
            </p>
            <div className="feature-actions">
              <button
                className="feature-btn primary"
                onClick={handleTamperImage}
                disabled={!!busy}
              >
                {busy === 'tamper-image'
                  ? (<><span className="btn-spinner"></span>Tampering…</>)
                  : 'Tamper image bytes'}
              </button>
            </div>
          </div>

          <div className="tamper-mode-block">
            <h3 className="tamper-mode-title">B. Modify a manifest field</h3>
            <p className="tamper-mode-desc">
              Replace one text field embedded in the signed manifest with a value of equal length.
              The cryptographic signature over the claim/cert bytes will fail.
            </p>

            {targets.length === 0 ? (
              <div className="feature-result info">No tamperable text fields were detected in this manifest.</div>
            ) : (
              <div className="tamper-field-form">
                <label className="wm-message-label" htmlFor="tamper-field-select">
                  Field to tamper
                </label>
                <select
                  id="tamper-field-select"
                  className="wm-message-input"
                  value={selectedField}
                  onChange={(e) => {
                    const i = parseInt(e.target.value, 10);
                    setSelectedField(i);
                    setNewValue(targets[i]?.value || '');
                  }}
                  disabled={!!busy}
                >
                  {targets.map((t, i) => (
                    <option key={i} value={i}>
                      {t.label}: “{t.value}”
                    </option>
                  ))}
                </select>

                <label className="wm-message-label" htmlFor="tamper-new-value">
                  New value
                  <span className={`wm-message-counter ${lengthOk ? '' : 'over'}`}>
                    {newValue.length}/{oldLen} chars
                  </span>
                </label>
                <input
                  id="tamper-new-value"
                  type="text"
                  className="wm-message-input"
                  value={newValue}
                  onChange={(e) => setNewValue(e.target.value)}
                  disabled={!!busy}
                />
                {!lengthOk && (
                  <p className="wm-message-hint">
                    Must be exactly {oldLen} characters so the file structure stays intact.
                  </p>
                )}
                {isMultibyte && (
                  <p className="wm-message-hint">
                    Heads-up: non-ASCII characters take multiple bytes and may not match in the file.
                  </p>
                )}

                <div className="feature-actions">
                  <button
                    className="feature-btn primary"
                    onClick={handleTamperManifest}
                    disabled={!!busy || !lengthOk}
                  >
                    {busy === 'tamper-manifest'
                      ? (<><span className="btn-spinner"></span>Tampering…</>)
                      : 'Tamper manifest field'}
                  </button>
                </div>
              </div>
            )}
          </div>
        </>
      )}

      {error && <div className="feature-error">⚠ {error}</div>}

      {downloadUrl && (
        <div className="feature-result success">
          <div className="result-row">
            <span>✅ Tampered file ready: <code>{downloadName}</code></span>
          </div>
          {tamperSummary && <div className="result-row"><span>{tamperSummary}</span></div>}
          <button className="feature-btn download" onClick={handleDownload}>
            Download tampered file
          </button>
        </div>
      )}

    </section>
  );
}

function WatermarkTamperPanel() {
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState(null); // 'inspect' | 'tamper-noise' | 'tamper-recompress'
  const [error, setError] = useState(null);
  const [baseline, setBaseline] = useState(null); // { hasWatermark, message, accuracy } of source file
  const [downloadUrl, setDownloadUrl] = useState(null);
  const [downloadName, setDownloadName] = useState(null);
  const [tamperSummary, setTamperSummary] = useState(null);
  const [noiseSigma, setNoiseSigma] = useState(10);

  const reset = () => {
    setFile(null); setPreview(null); setError(null);
    setBaseline(null);
    setDownloadUrl(null); setDownloadName(null); setTamperSummary(null);
  };

  const clearOutputs = () => {
    setDownloadUrl(null); setDownloadName(null); setTamperSummary(null);
    setError(null);
  };

  const inspect = async (f) => {
    setBusy('inspect');
    try {
      const fd = new FormData();
      fd.append('file', f);
      // Don't pass expected_message here — we just want to detect whether a
      // watermark exists; the backend's is_text heuristic decides.
      const resp = await axios.post(`${API_URL}/decode-watermark-upload`, fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 60000,
      });
      const d = resp.data || {};
      setBaseline({
        hasWatermark: !!d.has_watermark,
        message: d.decoded_message ?? '',
        accuracy: d.accuracy ?? null,
      });
    } catch (err) {
      setError(err.response?.data?.error || err.message);
    } finally {
      setBusy(null);
    }
  };

  const onFile = useCallback((f) => {
    const err = validateFile(f);
    if (err) { setError(err); return; }
    reset();
    const reader = new FileReader();
    reader.onloadend = () => {
      setPreview(reader.result);
      setFile(f);
      inspect(f);
    };
    reader.readAsDataURL(f);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const runTamper = async (endpoint, mode, extra = {}) => {
    if (!file || busy) return;
    clearOutputs();
    setBusy(mode);
    try {
      const fd = new FormData();
      fd.append('file', file);
      Object.entries(extra).forEach(([k, v]) => fd.append(k, v));
      const resp = await axios.post(`${API_URL}${endpoint}`, fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 120000,
      });
      setDownloadUrl(resp.data.download_url);
      setDownloadName(resp.data.filename);
      setTamperSummary(resp.data.message);
    } catch (err) {
      setError(err.response?.data?.error || err.response?.data?.details || err.message);
    } finally {
      setBusy(null);
    }
  };

  const handleNoise = () => runTamper('/tamper-watermark-noise-upload', 'tamper-noise', { sigma: noiseSigma });
  const handleRecompress = () => runTamper('/tamper-watermark-recompress-upload', 'tamper-recompress');

  const handleDownload = () => {
    if (!downloadUrl) return;
    window.location.href = `${API_URL}${downloadUrl}`;
  };

  return (
    <section className="feature-panel feature-panel-wm-tamper">
      <header className="feature-header">
        <h2 className="feature-title">Invisible Watermark Tamper</h2>
        <p className="feature-subtitle">
          Modify a watermarked image and break the decoder's ability to recover the hidden message.
        </p>
      </header>

      <FileDropZone
        panelId="wm-tamper"
        file={file}
        preview={preview}
        onFile={onFile}
        onClear={reset}
        disabled={!!busy}
      />

      {busy === 'inspect' && <div className="feature-result info">Decoding the uploaded file to check for a watermark…</div>}

      {baseline && baseline.hasWatermark === false && (
        <WarningBanner
          title="This image is NOT watermarked!"
          detail="The tamper demo needs an image carrying an invisible watermark. Embed one in the “Invisible Watermarking” tab first."
        />
      )}

      {baseline && baseline.hasWatermark === true && (
        <>
          <div className="feature-result info">
            ✓ Watermark detected (decoded: <strong>“{baseline.message}”</strong>
            {baseline.accuracy != null && <>, accuracy {(baseline.accuracy * 100).toFixed(1)}%</>}).
            Pick an attack below — both should make the message unrecoverable.
          </div>

          <div className="tamper-mode-block">
            <h3 className="tamper-mode-title">A. Add Gaussian noise</h3>
            <p className="tamper-mode-desc">
              Add random noise to every pixel. Higher σ = more distortion. VINE is robust, so a mild attack may not destroy the watermark — that's part of the story.
            </p>
            <div className="noise-sigma-row">
              <label htmlFor="noise-sigma" className="noise-sigma-label">Noise level (σ)</label>
              <input
                id="noise-sigma"
                type="number"
                min="1"
                max="100"
                step="1"
                value={noiseSigma}
                onChange={(e) => setNoiseSigma(Math.max(1, Math.min(100, Number(e.target.value))))}
                disabled={!!busy}
                className="noise-sigma-input"
              />
            </div>
            <div className="feature-actions">
              <button
                className="feature-btn primary"
                onClick={handleNoise}
                disabled={!!busy}
              >
                {busy === 'tamper-noise'
                  ? (<><span className="btn-spinner"></span>Adding noise…</>)
                  : 'Add noise'}
              </button>
            </div>
          </div>

          <div className="tamper-mode-block">
            <h3 className="tamper-mode-title">B. JPEG re-compression</h3>
            <p className="tamper-mode-desc">
              Re-encode as JPEG at quality≈30 — the kind of compression a social-media upload pass might apply. Mostly imperceptible. The watermark may or may not survive.
            </p>
            <div className="feature-actions">
              <button
                className="feature-btn primary"
                onClick={handleRecompress}
                disabled={!!busy}
              >
                {busy === 'tamper-recompress'
                  ? (<><span className="btn-spinner"></span>Re-compressing…</>)
                  : 'Re-compress JPEG'}
              </button>
            </div>
          </div>
        </>
      )}

      {error && <div className="feature-error">⚠ {error}</div>}

      {downloadUrl && (
        <div className="feature-result success">
          <div className="result-row">
            <span>✅ Tampered file ready: <code>{downloadName}</code></span>
          </div>
          {tamperSummary && <div className="result-row"><span>{tamperSummary}</span></div>}
          <button className="feature-btn download" onClick={handleDownload}>
            Download tampered file
          </button>
          <div className="result-row">
            <span>
              Drop it into the <strong>Invisible Watermarking</strong> tab and click <strong>Decode watermark</strong> to confirm the message is destroyed.
            </span>
          </div>
        </div>
      )}
    </section>
  );
}

const TABS = [
  { id: 'c2pa',      label: 'C2PA',                       render: () => <C2paPanel /> },
  { id: 'wm',        label: 'Invisible Watermarking',     render: () => <WatermarkPanel /> },
  { id: 'combined',  label: 'DCP',                        render: () => <CombinedPanel /> },
  { id: 'tamper',    label: 'C2PA Tamper',                render: () => <TamperPanel /> },
  { id: 'wm-tamper', label: 'Invisible Watermark Tamper', render: () => <WatermarkTamperPanel /> },
];

// Scroll to a section by id, accounting for the sticky nav height.
function scrollToId(id) {
  const el = document.getElementById(id);
  if (!el) return;
  const navH = 64;
  const top = el.getBoundingClientRect().top + window.scrollY - navH - 8;
  window.scrollTo({ top, behavior: 'smooth' });
}

// Add a 'visible' class to elements with class 'reveal' once they enter the
// viewport. Plain IntersectionObserver — no third-party dependency.
function useScrollReveal() {
  useEffect(() => {
    const els = document.querySelectorAll('.reveal');
    if (!('IntersectionObserver' in window)) {
      els.forEach(e => e.classList.add('visible'));
      return;
    }
    const io = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('visible');
          io.unobserve(entry.target);
        }
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -40px 0px' });
    els.forEach(el => io.observe(el));
    return () => io.disconnect();
  }, []);
}

function GlobalNav() {
  return (
    <nav className="global-nav" role="navigation" aria-label="Primary">
      <div className="global-nav-inner">
        <div className="global-nav-brand" onClick={() => scrollToId('top')}>
          <div className="global-nav-logo" aria-hidden="true">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
              <path d="m9 12 2 2 4-4" />
            </svg>
          </div>
          <span className="global-nav-brand-acronym">DCP</span>
          <span className="global-nav-brand-full">— Digital Content Protector</span>
        </div>

        <div className="global-nav-links">
          <button className="global-nav-link" onClick={() => scrollToId('features')}>Features</button>
          <button className="global-nav-link" onClick={() => scrollToId('novelty')}>Novelty</button>
          <button className="global-nav-link" onClick={() => scrollToId('how')}>How it works</button>
          <button className="global-nav-link" onClick={() => scrollToId('docs')}>Docs</button>
          <button className="global-nav-link" onClick={() => scrollToId('usecases')}>Use cases</button>
          <button className="global-nav-link" onClick={() => scrollToId('team')}>Team</button>
          <button className="global-nav-cta" onClick={() => scrollToId('demo')}>Try the demo</button>
        </div>
      </div>
    </nav>
  );
}

function Hero() {
  return (
    <section id="top" className="hero bg-grid-fade">
      <div className="section-container">
        <div className="hero-inner">
          <div className="hero-text reveal">
            <h1 className="hero-title">
              Safety runs on images.<br />
              <span className="hero-title-accent">Make every one provable.</span>
            </h1>
            <p className="hero-tagline">
              Health, Safety and Environment (HSE) teams document inspections, hazards
              and incidents with site images that end up in reports, audits, insurance
              claims and regulatory evidence. Once shared across contractors and
              systems, their ownership and integrity get hard to verify. The Digital
              Content Protector (DCP) embeds invisible copyright watermarks and attaches
              Content Credentials (C2PA), so organisations can prove who created an
              image, confirm it hasn't been modified, and keep trusted visual records
              across the HSE workflow.
            </p>
            <div className="hero-ctas">
              <button className="cta cta-primary" onClick={() => scrollToId('demo')}>
                Try the demo
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="5" y1="12" x2="19" y2="12"></line>
                  <polyline points="12 5 19 12 12 19"></polyline>
                </svg>
              </button>
              <button className="cta cta-secondary" onClick={() => scrollToId('how')}>
                How it works
              </button>
            </div>
          </div>

        </div>
      </div>
    </section>
  );
}

function pillarPoster(c1, c2, label) {
  const svg =
    '<svg xmlns="http://www.w3.org/2000/svg" width="480" height="270">' +
    '<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">' +
    `<stop offset="0" stop-color="${c1}"/><stop offset="1" stop-color="${c2}"/>` +
    '</linearGradient></defs>' +
    '<rect width="480" height="270" fill="url(#g)"/>' +
    '<circle cx="240" cy="118" r="38" fill="rgba(255,255,255,0.18)"/>' +
    '<path d="M229 100 v36 l30 -18 z" fill="rgba(255,255,255,0.92)"/>' +
    `<text x="28" y="240" font-family="Inter,Arial,sans-serif" font-size="26" font-weight="700" fill="rgba(255,255,255,0.96)">${label}</text>` +
    '</svg>';
  return `data:image/svg+xml,${encodeURIComponent(svg)}`;
}

function DemoVideoStrip() {
  // Three windows under the hero, one per HSE pillar — each shows a workplace
  // scenario where digital imagery must be trusted (the problem DCP protects
  // against). Drop the clips into `public/videos/` as demo-health.mp4,
  // demo-safety.mp4 and demo-environment.mp4; until then the poster renders.
  const clips = [
    {
      key: 'health',
      accent: 'health',
      poster: pillarPoster('#5e94c0', '#3a6a93', 'Health'),
      title: 'Health',
      text: 'Health records and medical scans — kept authentic for compliance and liability.',
    },
    {
      key: 'safety',
      accent: 'safety',
      poster: pillarPoster('#d2a648', '#b07f24', 'Safety'),
      title: 'Safety',
      text: 'Inspection data and incident reports — so safety decisions rest on real evidence.',
    },
    {
      key: 'environment',
      accent: 'environment',
      poster: pillarPoster('#48a99b', '#2f8174', 'Environment'),
      title: 'Environment',
      text: 'Site and aerial environmental imagery — provably unaltered for regulators.',
    },
  ];

  return (
    <section className="video-strip-section" aria-label="Health, Safety and Environment use cases">
      <div className="section-container">
        <div className="video-strip-header reveal">
          <span className="section-eyebrow">Where it matters</span>
          <h2 className="video-strip-title">Protecting the evidence behind Health, Safety &amp; Environment.</h2>
        </div>
        <div className="video-strip-grid">
          {clips.map((c) => (
            <figure className="video-window reveal" key={c.key}>
              <div className={`video-window-media video-window-media--${c.accent}`}>
                <video
                  className="video-window-video"
                  poster={c.poster}
                  autoPlay
                  muted
                  loop
                  playsInline
                  preload="auto"
                >
                  <source
                    src={`${process.env.PUBLIC_URL}/videos/demo-${c.key}.mp4`}
                    type="video/mp4"
                  />
                </video>
              </div>
              <figcaption className="video-window-caption">
                <span className="video-window-title">{c.title}</span>
                <span className="video-window-text">{c.text}</span>
              </figcaption>
            </figure>
          ))}
        </div>
      </div>
    </section>
  );
}

function ExistingToolsSection() {
  // Mirrors slide 5 ("Existing tools don't survive real workflows") + the slide-4 stats.
  // Establishes the trust gap that motivates DCP — incident reports / audit logs /
  // insurance claims are all built on phone photos that today no one can verify.
  const rows = [
    'Cryptographic origin proof',
    'Survives metadata stripping',
    'Robust to JPEG / noise / screenshots',
    'Cross-verified end-to-end',
  ];
  const cols = [
    { name: 'C2PA only',      marks: [true,  false, false, false] },
    { name: 'Watermark only', marks: [false, true,  true,  false] },
    { name: 'DCP (combined)', marks: [true,  true,  true,  true ], highlight: true },
  ];
  return (
    <section id="gap" className="section section--alt">
      <div className="section-container">
        <div className="section-header reveal">
          <span className="section-eyebrow">The trust gap</span>
          <h2 className="section-title">Existing tools don't survive real workflows.</h2>
          <p className="section-lede">
            Incident reports, audit logs and insurance claims are all built on phone photos
            forwarded through email, chats and claim portals. Today none of them can be
            cryptographically verified — and the threat is growing fast.
          </p>
        </div>

        <div className="trust-stats reveal">
          <div className="trust-stat">
            <span className="trust-stat-value">2.8 M</span>
            <span className="trust-stat-label">
              US private-industry workplace injuries &amp; illnesses (2022)<br />
              <em>Source: US BLS, Nov 2023.</em>
            </span>
          </div>
          <div className="trust-stat trust-stat--alt">
            <span className="trust-stat-value">10×</span>
            <span className="trust-stat-label">
              Global deepfake fraud incidents, 2022 → 2023<br />
              <em>Source: Sumsub Identity Fraud Report (2023).</em>
            </span>
          </div>
        </div>

        <figure className="trust-figure reveal">
          <img src={figAiGrowth} alt="" loading="lazy" />
          <figcaption>Year-over-year growth in deepfake fraud, 2022 → 2023. Source: Sumsub Identity Fraud Report (2023).</figcaption>
        </figure>

        <div className="compare-table reveal" role="table" aria-label="Existing-tools comparison">
          <div className="compare-row compare-row--head" role="row">
            <div className="compare-cell compare-cell--rowlabel" role="columnheader"></div>
            {cols.map(c => (
              <div
                key={c.name}
                role="columnheader"
                className={`compare-cell compare-cell--colhead ${c.highlight ? 'compare-cell--hl' : ''}`}
              >
                {c.name}
              </div>
            ))}
          </div>
          {rows.map((label, i) => (
            <div className="compare-row" role="row" key={label}>
              <div className="compare-cell compare-cell--rowlabel" role="rowheader">{label}</div>
              {cols.map(c => (
                <div
                  key={c.name}
                  role="cell"
                  className={`compare-cell ${c.marks[i] ? 'compare-mark-ok' : 'compare-mark-no'}`}
                  aria-label={c.marks[i] ? 'yes' : 'no'}
                >
                  {c.marks[i] ? '✓' : '✗'}
                </div>
              ))}
            </div>
          ))}
        </div>

        <p className="compare-caption reveal">
          Each existing approach has a gap. The combination closes them.
        </p>
      </div>
    </section>
  );
}

function FeaturesSection() {
  return (
    <section id="features" className="section">
      <div className="section-container">
        <div className="section-header reveal">
          <span className="section-eyebrow">Capabilities</span>
          <h2 className="section-title">Two layers of trust. One workflow.</h2>
          <p className="section-lede">
            A signed manifest tells a verifier <em>who</em> created an image and <em>when</em>.
            An invisible watermark survives downloads, screenshots and re-uploads.
            Together they make tampering both detectable and traceable.
          </p>
        </div>

        <figure className="architecture-figure reveal">
          <img src={figArchitecture} alt="" loading="lazy" />
          <figcaption>C2PA manifest + invisible neural watermark — bound to each other so tampering either layer breaks both.</figcaption>
        </figure>

        <div className="features-grid">
          <div className="feature-card reveal">
            <div className="feature-card-icon feature-card-icon--c2pa">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                <path d="m9 12 2 2 4-4" />
              </svg>
            </div>
            <h3 className="feature-card-title">C2PA cryptographic signing</h3>
            <p className="feature-card-text">
              Bind each image to its origin with a tamper-evident manifest signed
              by a trusted certificate. Anyone can verify the chain of custody
              without contacting you.
            </p>
          </div>

          <div className="feature-card reveal">
            <div className="feature-card-icon feature-card-icon--wm">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
              </svg>
            </div>
            <h3 className="feature-card-title">Invisible neural watermarks</h3>
            <p className="feature-card-text">
              Our decoder embeds a recoverable 12-byte message directly into the pixels.
              The image looks identical to the eye yet carries provenance even
              when metadata is stripped.
            </p>
          </div>

          <div className="feature-card reveal">
            <div className="feature-card-icon feature-card-icon--guard">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
                <line x1="12" y1="9" x2="12" y2="13" />
                <line x1="12" y1="17" x2="12.01" y2="17" />
              </svg>
            </div>
            <h3 className="feature-card-title">Tamper detection</h3>
            <p className="feature-card-text">
              Any pixel-level edit invalidates the C2PA asset hash. Any aggressive
              re-compression or noise attack collapses the watermark. Both signals
              are surfaced clearly to the viewer.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}

function NoveltiesSection() {
  // Mirrors slides 7-9 — DCP's three research/engineering contributions.
  // Kept consistent with the website's existing palette (teal accent, info blue, etc.).
  return (
    <section id="novelty" className="section">
      <div className="section-container">
        <div className="section-header reveal">
          <span className="section-eyebrow">What's new</span>
          <h2 className="section-title">Three things only DCP does.</h2>
          <p className="section-lede">
            C2PA and watermarks have existed separately for years. DCP combines them so
            they verify each other — and adds a neural watermark that survives the way
            HSE images really travel.
          </p>
        </div>

        <div className="novelty-grid">
          <div className="novelty-card reveal">
            <div className="novelty-tag">Novelty 1</div>
            <h3 className="novelty-title">Mutual cross-binding</h3>
            <p className="novelty-text">
              The watermark's payload is a <code>SHA-256</code> of the C2PA manifest.
              Tamper with the pixels and the C2PA hash fails. Tamper with the manifest
              and the watermark stops matching. Either layer alone can be defeated;
              together they cannot.
            </p>
            <img src={figCrossBinding} alt="" className="novelty-figure" loading="lazy" />
          </div>

          <div className="novelty-card reveal">
            <div className="novelty-tag novelty-tag--alt">Novelty 2</div>
            <h3 className="novelty-title">Survives metadata stripping</h3>
            <p className="novelty-text">
              C2PA dies the moment a platform strips metadata — which most do (claim
              portals, social, chat). The neural watermark lives in the pixels, so
              provenance keeps working through the messy real workflows HSE photos
              actually traverse.
            </p>
            <img src={figStripSurvival} alt="" className="novelty-figure" loading="lazy" />
          </div>

          <div className="novelty-card reveal">
            <div className="novelty-tag novelty-tag--secondary">Novelty 3</div>
            <h3 className="novelty-title">Robust neural watermark</h3>
            <p className="novelty-text">
              A learned, diffusion-based encoder embeds an imperceptible mark in the
              pixels. It's designed for the real attack channel: JPEG re-compression,
              additive noise, screenshots, re-uploads — where frequency-domain
              baselines drop to chance.
            </p>
            <img src={figRobustness} alt="" className="novelty-figure" loading="lazy" />
            <div className="novelty-bullets">
              <span>· Survives JPEG re-compression</span>
              <span>· Survives noise &amp; resizing</span>
              <span>· Bound to the C2PA manifest (Novelty 1)</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function HowItWorksSection() {
  return (
    <section id="how" className="section section--alt">
      <div className="section-container">
        <div className="section-header reveal">
          <span className="section-eyebrow">Workflow</span>
          <h2 className="section-title">Three steps from raw image to verifiable asset.</h2>
          <p className="section-lede">
            DCP keeps the pipeline simple: upload, protect, share. Verification is
            a single drag-and-drop away for anyone receiving the file.
          </p>
        </div>

        <div className="steps">
          <div className="step reveal">
            <div className="step-number">1</div>
            <h3 className="step-title">Upload an image</h3>
            <p className="step-text">
              Drop a JPEG or PNG into the demo. Everything runs locally against
              the bundled Docker stack — your file never leaves your machine.
            </p>
          </div>
          <div className="step reveal">
            <div className="step-number">2</div>
            <h3 className="step-title">Sign &amp; watermark</h3>
            <p className="step-text">
              C2PA signs the file with a trusted certificate. The neural
              encoder embeds a user-supplied 12-byte message into the pixels.
              Both happen in seconds, in any order, or together in one pass.
            </p>
          </div>
          <div className="step reveal">
            <div className="step-number">3</div>
            <h3 className="step-title">Verify anywhere</h3>
            <p className="step-text">
              Any recipient can drop the file back in to read the manifest and
              recover the watermark. Tampering shows up loud and red — no
              guesswork required.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}

// One node in a flow diagram. Variant "input" / "process" / "output" gives a colour hint.
function FlowNode({ children, variant = 'process', mono = false }) {
  return (
    <div className={`flow-node flow-node--${variant} ${mono ? 'flow-node--mono' : ''}`}>
      {children}
    </div>
  );
}

function FlowArrow({ label, direction = 'right' }) {
  return (
    <div className={`flow-arrow flow-arrow--${direction}`}>
      {label && <span className="flow-arrow-label">{label}</span>}
      <svg width="24" height="14" viewBox="0 0 24 14" fill="none" aria-hidden="true">
        {direction === 'right' ? (
          <path d="M0 7h22M16 1l6 6-6 6" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" fill="none" />
        ) : (
          <path d="M24 7H2M8 1L2 7l6 6" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" fill="none" />
        )}
      </svg>
    </div>
  );
}

function DocsSection() {
  return (
    <section id="docs" className="section section--alt">
      <div className="section-container">
        <div className="section-header reveal">
          <span className="section-eyebrow">Technical documentation</span>
          <h2 className="section-title">How DCP works under the hood.</h2>
          <p className="section-lede">
            DCP layers two independent trust mechanisms over the same image:
            a cryptographic provenance manifest (C2PA) and a neural pixel-level
            watermark. The sections below walk through each pipeline, the data
            it produces, and why tampering is detectable in both layers.
          </p>
        </div>

        {/* ---------------- C2PA ---------------- */}
        <article className="docs-block reveal">
          <header className="docs-block-header">
            <span className="docs-block-tag docs-block-tag--c2pa">Layer 1</span>
            <h3 className="docs-block-title">C2PA — Cryptographic Provenance</h3>
            <p className="docs-block-lede">
              The Coalition for Content Provenance and Authenticity (C2PA)
              defines an open standard for tamper-evident provenance metadata
              embedded directly in media files. A signed <em>manifest</em>
              binds together <em>assertions</em> about who created the asset,
              when, with what tools, and a cryptographic hash of the asset
              bytes themselves.
            </p>
          </header>

          <h4 className="docs-subtitle">Signing pipeline</h4>
          <div className="flow flow--row">
            <FlowNode variant="input">Original<br />image</FlowNode>
            <FlowArrow />
            <FlowNode>Assertions<br /><span className="flow-node-sub">actions, hashes, thumbnail</span></FlowNode>
            <FlowArrow />
            <FlowNode>Build claim<br /><span className="flow-node-sub">CBOR-encoded</span></FlowNode>
            <FlowArrow label="sign" />
            <FlowNode variant="key" mono>Signer<br /><span className="flow-node-sub">cert + private key</span></FlowNode>
            <FlowArrow />
            <FlowNode>Embed JUMBF<br /><span className="flow-node-sub">in JPEG / PNG box</span></FlowNode>
            <FlowArrow />
            <FlowNode variant="output">Signed<br />image</FlowNode>
          </div>

          <h4 className="docs-subtitle">Verification pipeline</h4>
          <div className="flow flow--row">
            <FlowNode variant="input">Received<br />image</FlowNode>
            <FlowArrow />
            <FlowNode>Parse JUMBF<br /><span className="flow-node-sub">extract manifest</span></FlowNode>
            <FlowArrow />
            <FlowNode>Verify signature<br /><span className="flow-node-sub">against cert chain</span></FlowNode>
            <FlowArrow />
            <FlowNode>Re-hash asset<br /><span className="flow-node-sub">compare to claim</span></FlowNode>
            <FlowArrow />
            <FlowNode variant="output">Valid&nbsp;✓ or<br />Invalid&nbsp;⚠</FlowNode>
          </div>

          <h4 className="docs-subtitle">Key concepts</h4>
          <div className="docs-concepts">
            <div className="docs-concept">
              <h5>Manifest</h5>
              <p>The top-level container. Holds one claim plus its assertions, signature, and any embedded thumbnails. Stored inside a JUMBF box appended to the image.</p>
            </div>
            <div className="docs-concept">
              <h5>Claim</h5>
              <p>A CBOR-encoded statement that references and hashes a set of assertions. Signed once; everything else is derived from it.</p>
            </div>
            <div className="docs-concept">
              <h5>Assertions</h5>
              <p>Individual facts about the asset: <code>c2pa.actions</code> (created / edited), <code>c2pa.hash.data</code> (asset bytes hash), <code>c2pa.thumbnail.claim</code> and more.</p>
            </div>
            <div className="docs-concept">
              <h5>Signature</h5>
              <p>A COSE_Sign1 envelope over the claim CBOR, bound to a leaf X.509 certificate. Anyone can verify the chain without contacting the signer.</p>
            </div>
            <div className="docs-concept">
              <h5>JUMBF</h5>
              <p>JPEG Universal Metadata Box Format. The container standard used to embed the entire manifest into JPEG, PNG, MP4 and other media as a self-contained binary blob.</p>
            </div>
            <div className="docs-concept">
              <h5>Validation result</h5>
              <p>Per-assertion success / failure codes (<code>assertion.hashedURI.mismatch</code>, <code>claimSignature.mismatch</code>, …). DCP surfaces these as the red warning when anything fails.</p>
            </div>
          </div>

          <div className="docs-callout">
            <strong>Why tampering is detectable:</strong> any pixel-level edit changes the
            asset hash, breaking the <code>c2pa.hash.data</code> assertion. Editing
            text inside the manifest itself (e.g. a certificate subject byte) changes
            the bytes covered by the signature, breaking
            <code>claimSignature.mismatch</code>. The image and the manifest are
            cryptographically interlocked.
          </div>
        </article>

        {/* ---------------- Invisible watermarking ---------------- */}
        <article className="docs-block reveal">
          <header className="docs-block-header">
            <span className="docs-block-tag docs-block-tag--wm">Layer 2</span>
            <h3 className="docs-block-title">Invisible Watermarking — Neural Encoder / Decoder</h3>
            <p className="docs-block-lede">
              Where C2PA lives in the metadata, the invisible watermark lives in
              the pixels themselves. A pair of trained neural networks embed a
              fixed-length message into the image with no human-visible
              difference, and recover that message later — even after the image
              has been re-encoded, downloaded, or screenshotted.
            </p>
          </header>

          <h4 className="docs-subtitle">Encoding pipeline</h4>
          <div className="flow flow--row">
            <FlowNode variant="input">Original<br />image</FlowNode>
            <FlowArrow />
            <FlowNode variant="model">Encoder<br /><span className="flow-node-sub">U-Net-style CNN</span></FlowNode>
            <FlowArrow />
            <FlowNode variant="output">Watermarked<br />image</FlowNode>
            <div className="flow-stack-divider">+</div>
            <FlowNode mono>Message<br /><span className="flow-node-sub">12 UTF-8 bytes ≈ 96 bits</span></FlowNode>
          </div>

          <h4 className="docs-subtitle">Decoding pipeline (with realistic channel)</h4>
          <div className="flow flow--row">
            <FlowNode variant="input">Watermarked<br />image</FlowNode>
            <FlowArrow label="channel" />
            <FlowNode variant="distortion">JPEG re-encode<br />noise · crop · scale</FlowNode>
            <FlowArrow />
            <FlowNode variant="model">Decoder<br /><span className="flow-node-sub">CNN classifier per bit</span></FlowNode>
            <FlowArrow />
            <FlowNode variant="output">Recovered bits<br /><span className="flow-node-sub">+ confidence</span></FlowNode>
          </div>

          <h4 className="docs-subtitle">Key concepts</h4>
          <div className="docs-concepts">
            <div className="docs-concept">
              <h5>Encoder</h5>
              <p>A convolutional network that takes <em>(image, message bits)</em> and outputs a residual added to the image. Trained so the residual is statistically invisible.</p>
            </div>
            <div className="docs-concept">
              <h5>Decoder</h5>
              <p>A separate convolutional network that maps the (possibly tampered) image back to a bit vector. Trained jointly with the encoder.</p>
            </div>
            <div className="docs-concept">
              <h5>Robustness layer</h5>
              <p>Training applies random transformations (JPEG, noise, crop, resize) <em>between</em> encoder and decoder so the decoder learns to be invariant to common channel distortions.</p>
            </div>
            <div className="docs-concept">
              <h5>Capacity</h5>
              <p>~96-bit payload by default. DCP exposes this as a 12-character UTF-8 string — long enough for a user ID, content hash prefix or short license tag.</p>
            </div>
            <div className="docs-concept">
              <h5>Imperceptibility</h5>
              <p>Loss objective penalises perceptual difference (LPIPS / SSIM-style) so the watermark stays under the human-visible threshold even at high payload.</p>
            </div>
            <div className="docs-concept">
              <h5>Decoded accuracy</h5>
              <p>Reported as the per-bit agreement with the embedded message. Above ~85% the recovered text is reliable; below that the message is considered destroyed.</p>
            </div>
          </div>

          <div className="docs-callout">
            <strong>Complementary trust signals:</strong> a C2PA manifest can be
            stripped by a re-uploader, but the invisible watermark survives.
            Pixel tampering breaks C2PA's hash assertion but the watermark may
            still partially decode. Aggressive transforms destroy the watermark
            but a re-signed C2PA manifest still proves who issued the file.
            Stacking both gives you a defence-in-depth posture.
          </div>
        </article>

        {/* ---------------- DCP combined ---------------- */}
        <article className="docs-block reveal">
          <header className="docs-block-header">
            <span className="docs-block-tag docs-block-tag--dcp">DCP</span>
            <h3 className="docs-block-title">End-to-end DCP pipeline</h3>
            <p className="docs-block-lede">
              Both layers are applied to the same asset in one pass. The
              ordering matters: watermarking first lets the watermark be
              authenticated by the C2PA signature too.
            </p>
          </header>
          <div className="flow flow--row">
            <FlowNode variant="input">Image +<br />Message</FlowNode>
            <FlowArrow />
            <FlowNode variant="model">Watermark<br /><span className="flow-node-sub">neural encoder</span></FlowNode>
            <FlowArrow />
            <FlowNode>Watermarked<br />image</FlowNode>
            <FlowArrow />
            <FlowNode variant="key" mono>C2PA signer<br /><span className="flow-node-sub">cert + private key</span></FlowNode>
            <FlowArrow />
            <FlowNode variant="output">Signed +<br />watermarked</FlowNode>
          </div>
          <p className="docs-block-foot">
            On the verification side a recipient runs the C2PA reader (this
            page's <strong>C2PA</strong> tab) and the watermark decoder (the
            <strong> Invisible Watermarking</strong> tab) against the same file.
            DCP renders a red warning the moment either signal fails — even if
            the other still validates.
          </p>
        </article>
      </div>
    </section>
  );
}

function UseCasesSection() {
  const cases = [
    {
      photo: hseRefinery,
      title: 'Incident reports',
      stake: 'decides workers’ comp claims & legal liability',
      text: 'Slips, near-misses, equipment damage — every report photo cryptographically bound to the time and place of the incident.',
    },
    {
      photo: hseClimb,
      title: 'Safety inspections',
      stake: 'decides permits & site reopen',
      text: 'Walkthrough and PPE-compliance photos auditors can verify at a glance, so safety decisions rest on real evidence.',
    },
    {
      photo: hseBoiler,
      title: 'Contractor verification',
      stake: 'decides progress payments & sign-off',
      text: '‘Work completed’ photos bound to who, when, and the original pixels — so resellers and subcontractors can’t swap shots.',
    },
    {
      photo: hsePpe,
      title: 'Compliance audits',
      stake: 'decides regulator’s pass or fail',
      text: 'Tamper-evident audit trail of PPE checks and compliance evidence — verifiable years later, with the manifest intact.',
    },
    {
      photo: hseSandblast,
      title: 'Insurance claims',
      stake: 'decides claim payout',
      text: 'Injury and damage photos provably from the time and place of the incident, so fraudulent claims fail verification.',
    },
    {
      photo: hseWater,
      title: 'Environmental records',
      stake: 'decides fines & remediation orders',
      text: 'Spill, emissions and before/after remediation imagery bound to its source — regulatory evidence that can’t be quietly doctored.',
    },
  ];

  return (
    <section id="usecases" className="section section--alt">
      <div className="section-container">
        <div className="section-header reveal">
          <span className="section-eyebrow">HSE use cases</span>
          <h2 className="section-title">Built for the photos every workplace already takes.</h2>
          <p className="section-lede">
            Incident reports, safety inspections, contractor verification, compliance audits,
            insurance claims, environmental records — DCP makes each photo provable so
            the decisions resting on them can stand.
          </p>
        </div>

        <div className="hse-cases-grid">
          {cases.map((c) => (
            <article className="hse-case reveal" key={c.title}>
              <div className="hse-case-media">
                <img src={c.photo} alt="" loading="lazy" />
                <span className="hse-case-stake">{c.stake}</span>
              </div>
              <div className="hse-case-body">
                <h3 className="hse-case-title">{c.title}</h3>
                <p className="hse-case-text">{c.text}</p>
              </div>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

function DemoSection() {
  const [active, setActive] = useState('c2pa');
  const activeTab = TABS.find(t => t.id === active) || TABS[0];
  return (
    <section id="demo" className="demo-section">
      <div className="section-container">
        <div className="section-header reveal">
          <span className="section-eyebrow">Live demo</span>
          <h2 className="section-title">Try every capability of Digital Content Protector.</h2>
          <p className="section-lede">
            Each tab is independent — sign an image, embed an invisible watermark,
            simulate an attacker tampering with the result, or run the whole pipeline at once.
          </p>
        </div>

        <div className="demo-shell reveal">
          <div className="tab-bar" role="tablist">
            {TABS.map(t => (
              <button
                key={t.id}
                role="tab"
                aria-selected={active === t.id}
                className={`tab-btn ${active === t.id ? 'active' : ''}`}
                onClick={() => setActive(t.id)}
              >
                {t.label}
              </button>
            ))}
          </div>
          <div className="tab-panel">
            {activeTab.render()}
          </div>
        </div>
      </div>
    </section>
  );
}

function TeamSection() {
  const members = [
    {
      name: 'Wei Song',
      role: 'Postdoctoral Researcher · UNSW',
      photo: teamWeiSong,
      bio: 'Works on the security, reliability and real-world deployment of AI-enabled systems — including trustworthy media, adversarial robustness, and multimodal model safety.',
      url: 'https://wweisong.github.io/',
    },
    {
      name: 'Yulei Sui',
      role: 'Professor · UNSW',
      photo: teamYuleiSui,
      bio: 'ARC Future Fellow and Fellow of Engineers Australia. Builds open-source frameworks for static program analysis and verification, and studies the intersection of programming languages and code LLMs.',
      url: 'https://yuleisui.github.io/',
    },
    {
      name: 'Zhenchang Xing',
      role: 'Senior Principal Research Scientist · CSIRO Data61',
      photo: teamZhenchangXing,
      bio: 'Leads the SE4AI team at Data61. Research focuses on knowledge-graph methods, behaviour analytics, and tooling for responsible AI in software engineering.',
      url: 'https://people.csiro.au/X/Z/Zhenchang-Xing/',
    },
    {
      name: 'Jingling Xue',
      role: 'Scientia Professor · UNSW',
      photo: teamJinglingXue,
      bio: 'Leads the Programming Languages and Compilers group at UNSW. Research spans compiler techniques, pointer/alias analysis at million-line scale, and static and dynamic program analysis.',
      url: 'https://cgi.cse.unsw.edu.au/~jingling/',
    },
  ];

  return (
    <section id="team" className="section section--alt">
      <div className="section-container">
        <div className="section-header reveal">
          <span className="section-eyebrow">Team</span>
          <h2 className="section-title">A CSIRO Data61 × UNSW collaboration, supporting Tech4HSE.</h2>
          <p className="section-lede">
            The Digital Content Protector contributes a trustworthy-media capability
            toward the responsible-AI and cybersecurity goals of Tech4HSE — CSIRO
            Data61’s program for safer workplaces — built by researchers working
            across content provenance, program analysis, neural media security and
            responsible-AI tooling.
          </p>
        </div>

        <div className="partners-row reveal">
          <img src={unswLogo}   alt="UNSW Logo"   className="partners-logo" />
          <img src={data61Logo} alt="Data61 Logo" className="partners-logo" />
        </div>
        <p className="partners-note reveal">
          Supporting <strong>Tech4HSE</strong> — CSIRO Data61’s research program
          developing artificial intelligence (AI), augmented reality (AR) and
          cybersecurity for safer workplaces.
        </p>

        <div className="team-grid">
          {members.map((m) => (
            <a className="team-card reveal" key={m.name} href={m.url} target="_blank" rel="noopener noreferrer">
              <img src={m.photo} alt={`${m.name} portrait`} className="team-photo" />
              <div className="team-name">{m.name}</div>
              <div className="team-role">{m.role}</div>
              <p className="team-bio">{m.bio}</p>
            </a>
          ))}
        </div>
      </div>
    </section>
  );
}

function Footer() {
  return (
    <footer className="footer" role="contentinfo">
      <div className="section-container">
        <div className="footer-inner">
          <div className="footer-brand-block">
            <div className="footer-brand">
              <div className="global-nav-logo" aria-hidden="true">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                  <path d="m9 12 2 2 4-4" />
                </svg>
              </div>
              Digital Content Protector
            </div>
            <p className="footer-tagline">
              Content Credentials (C2PA) provenance and invisible neural
              watermarking in one open research stack — supporting Tech4HSE’s
              responsible-AI and cybersecurity goals.
            </p>
          </div>
          <div>
            <div className="footer-col-title">Product</div>
            <button className="footer-link" onClick={() => scrollToId('features')}>Features</button>
            <button className="footer-link" onClick={() => scrollToId('how')}>How it works</button>
            <button className="footer-link" onClick={() => scrollToId('docs')}>Docs</button>
            <button className="footer-link" onClick={() => scrollToId('demo')}>Live demo</button>
          </div>
          <div>
            <div className="footer-col-title">Project</div>
            <button className="footer-link" onClick={() => scrollToId('usecases')}>Use cases</button>
            <button className="footer-link" onClick={() => scrollToId('team')}>Team</button>
          </div>
          <div>
            <div className="footer-col-title">Partners</div>
            <div className="footer-partners-row">
              <img src={unswLogo}   alt="UNSW Logo"   className="footer-partner-logo" />
              <img src={data61Logo} alt="Data61 Logo" className="footer-partner-logo" />
            </div>
          </div>
        </div>
        <div className="footer-bottom">
          <span>© UNSW CSE FutureAI 2026 — Digital Content Protector</span>
          <span>Supporting Tech4HSE · CSIRO Data61 × UNSW · Built on C2PA &amp; neural watermarking</span>
        </div>
      </div>
    </footer>
  );
}

function App() {
  useScrollReveal();
  return (
    <div className="App">
      <GlobalNav />
      <Hero />
      <UseCasesSection />
      <DemoVideoStrip />
      <ExistingToolsSection />
      <FeaturesSection />
      <NoveltiesSection />
      <HowItWorksSection />
      <DocsSection />
      <DemoSection />
      <TeamSection />
      <Footer />
    </div>
  );
}

export default App;
