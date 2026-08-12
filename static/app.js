(() => {
  const form = document.getElementById('listing-form');
  const imageInput = document.getElementById('image-input');
  const preview = document.getElementById('local-preview');
  const uploadZone = document.getElementById('upload-zone');
  const removeBtn = document.getElementById('remove-image');
  const button = document.getElementById('generate-button');
  const loading = document.getElementById('loading');
  const errorBox = document.getElementById('error-box');
  const results = document.getElementById('results');
  const toast = document.getElementById('toast');
  let previewUrl = null;

  const MAX_UPLOAD_BYTES = 2.8 * 1024 * 1024;
  const ACCEPTED = ['image/jpeg', 'image/png', 'image/webp'];

  const loadingSteps = [
    ['Reading your design…', 'Gemini is detecting the design subject, visible text, audience, and search intent.'],
    ['Building Etsy keywords…', 'The strongest product phrase and 13 varied buyer search tags are being created.'],
    ['Checking personalization…', 'The design is being reviewed for realistic editable elements.'],
    ['Running Etsy format checks…', 'Title length, tag count, tag length, and duplication are being validated.'],
  ];

  function flash(message) {
    toast.textContent = message;
    toast.classList.add('show');
    setTimeout(() => toast.classList.remove('show'), 1500);
  }

  function setPreview(file) {
    if (!file) return clearPreview();
    if (!ACCEPTED.includes(file.type)) {
      flash('Please use JPG, PNG, or WebP');
      return clearPreview();
    }
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    previewUrl = URL.createObjectURL(file);
    preview.src = previewUrl;
    preview.hidden = false;
    removeBtn.hidden = false;
    uploadZone.classList.add('has-image');
  }

  function clearPreview() {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    previewUrl = null;
    imageInput.value = '';
    preview.src = '';
    preview.hidden = true;
    removeBtn.hidden = true;
    uploadZone.classList.remove('has-image');
  }

  imageInput.addEventListener('change', () => setPreview(imageInput.files?.[0]));
  removeBtn.addEventListener('click', (event) => { event.preventDefault(); event.stopPropagation(); clearPreview(); });

  ['dragenter', 'dragover'].forEach(name => uploadZone.addEventListener(name, event => {
    event.preventDefault(); uploadZone.classList.add('dragging');
  }));
  uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('dragging'));
  uploadZone.addEventListener('drop', event => {
    event.preventDefault(); uploadZone.classList.remove('dragging');
    const file = event.dataTransfer?.files?.[0];
    if (!file) return;
    const dt = new DataTransfer(); dt.items.add(file); imageInput.files = dt.files; setPreview(file);
  });

  async function loadBitmap(file) {
    if ('createImageBitmap' in window) return createImageBitmap(file);
    return new Promise((resolve, reject) => {
      const img = new Image();
      const url = URL.createObjectURL(file);
      img.onload = () => { URL.revokeObjectURL(url); resolve(img); };
      img.onerror = reject;
      img.src = url;
    });
  }

  async function compressImage(file) {
    if (!ACCEPTED.includes(file.type)) throw new Error('Only JPG, PNG, and WebP images are supported.');
    const source = await loadBitmap(file);
    let width = source.width;
    let height = source.height;
    const maxDimension = 1800;
    const scale = Math.min(1, maxDimension / Math.max(width, height));
    width = Math.max(1, Math.round(width * scale));
    height = Math.max(1, Math.round(height * scale));

    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d', { alpha: true });
    let quality = 0.84;

    for (let attempt = 0; attempt < 5; attempt += 1) {
      canvas.width = width; canvas.height = height;
      ctx.clearRect(0, 0, width, height);
      ctx.drawImage(source, 0, 0, width, height);
      const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/webp', quality));
      if (!blob) throw new Error('The browser could not compress this image.');
      if (blob.size <= MAX_UPLOAD_BYTES) {
        return new File([blob], 'seektec-design.webp', { type: 'image/webp' });
      }
      width = Math.max(700, Math.round(width * 0.82));
      height = Math.max(700, Math.round(height * 0.82));
      quality = Math.max(0.58, quality - 0.07);
    }
    throw new Error('Image is still too large after compression. Please use a smaller image.');
  }

  function text(id, value, fallback = '—') {
    document.getElementById(id).textContent = value || fallback;
  }

  function render(data) {
    const listing = data.listing;
    const report = data.validation;
    text('title-output', listing.title);
    text('title-count', `${listing.title.length}/140`);
    text('score-value', report.score);
    text('design-subject', listing.design_subject);
    text('detected-text', listing.detected_text.length ? listing.detected_text.join(' · ') : 'No readable text detected');
    text('design-themes', listing.design_themes.length ? listing.design_themes.join(' · ') : 'General design');

    const tags = document.getElementById('tags-output');
    tags.innerHTML = '';
    listing.tags.forEach((tag, index) => {
      const chip = document.createElement('span');
      chip.innerHTML = `<b>${index + 1}</b><em>${escapeHtml(tag)}</em><small>${tag.length}</small>`;
      tags.appendChild(chip);
    });
    document.getElementById('tags-copy').textContent = listing.tags.join(', ');

    const pCard = document.getElementById('personalization-card');
    if (data.inputs.personalization === 'Yes') {
      pCard.hidden = false;
      const list = document.getElementById('personalization-options');
      list.innerHTML = '';
      (listing.personalization_options || []).forEach(item => {
        const li = document.createElement('li'); li.textContent = item; list.appendChild(li);
      });
      if (!listing.personalization_options.length) {
        const li = document.createElement('li'); li.textContent = 'No clear editable design element detected — review manually.'; list.appendChild(li);
      }
      text('personalization-instruction', listing.personalization_instruction, 'Review the design and enter your requested customization.');
      document.getElementById('personalization-copy').textContent =
        `Changes that can be made:\n${(listing.personalization_options || []).map(x => `• ${x}`).join('\n')}\n\nPersonalization field:\n${listing.personalization_instruction || ''}`;
    } else {
      pCard.hidden = true;
    }

    const warningCard = document.getElementById('warning-card');
    const warningList = document.getElementById('warning-list');
    const allWarnings = [...(listing.ip_warnings || []), ...(report.errors || []), ...(report.warnings || [])];
    warningList.innerHTML = '';
    if (allWarnings.length) {
      warningCard.hidden = false;
      [...new Set(allWarnings)].forEach(item => { const li = document.createElement('li'); li.textContent = item; warningList.appendChild(li); });
    } else {
      warningCard.hidden = true;
    }

    results.hidden = false;
    results.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function escapeHtml(value) {
    return String(value).replace(/[&<>"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[char]));
  }

  form.addEventListener('submit', async event => {
    event.preventDefault();
    errorBox.hidden = true;
    results.hidden = true;
    const sourceFile = imageInput.files?.[0];
    if (!sourceFile) { flash('Please upload a product image'); return; }

    loading.hidden = false; button.disabled = true;
    const buttonLabel = button.querySelector('span:nth-child(2)');
    const oldLabel = buttonLabel.textContent; buttonLabel.textContent = 'Generating…';
    let step = 0;
    const stepTimer = setInterval(() => {
      step = Math.min(step + 1, loadingSteps.length - 1);
      text('loading-title', loadingSteps[step][0]); text('loading-message', loadingSteps[step][1]);
    }, 3200);

    try {
      text('loading-title', loadingSteps[0][0]); text('loading-message', loadingSteps[0][1]);
      const compressed = await compressImage(sourceFile);
      const formData = new FormData(form);
      formData.set('image', compressed);
      const response = await fetch('/api/generate', { method: 'POST', body: formData });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.detail || `Request failed (${response.status}).`);
      render(payload);
    } catch (error) {
      errorBox.textContent = error.message || 'Could not generate the listing.';
      errorBox.hidden = false;
      errorBox.scrollIntoView({ behavior: 'smooth', block: 'center' });
    } finally {
      clearInterval(stepTimer); loading.hidden = true; button.disabled = false; buttonLabel.textContent = oldLabel;
    }
  });

  document.addEventListener('click', async event => {
    const btn = event.target.closest('[data-copy]');
    if (!btn) return;
    const target = document.getElementById(btn.dataset.copy);
    if (!target) return;
    try { await navigator.clipboard.writeText(target.innerText.trim()); flash('Copied to clipboard'); }
    catch { flash('Copy failed — select the text manually'); }
  });
})();
