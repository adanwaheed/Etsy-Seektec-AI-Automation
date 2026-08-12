(() => {
  const form = document.getElementById('listing-form');
  const imageInput = document.getElementById('image-input');
  const uploadZone = document.getElementById('upload-zone');
  const preview = document.getElementById('local-preview');
  const removeBtn = document.getElementById('remove-image');
  const results = document.getElementById('results');
  const errorBox = document.getElementById('error-box');
  const loading = document.getElementById('loading');
  const button = document.getElementById('generate-button');
  const toast = document.getElementById('toast');
  const personalizationToggle = document.getElementById('personalization-toggle');
  const personalizationValue = document.getElementById('personalization-value');
  const personalizationPreview = document.getElementById('personalization-preview');
  const personalizationHelper = document.getElementById('personalization-helper');
  const pageProgress = document.getElementById('page-progress');

  const ACCEPTED = ['image/jpeg', 'image/png', 'image/webp'];
  const MAX_UPLOAD_BYTES = 2.8 * 1024 * 1024;
  let previewUrl = null;

  const loadingSteps = [
    ['Reading your design…', 'Detecting text, names, initials, graphics and visual themes.'],
    ['Mapping Etsy search intent…', 'Building a clear product phrase and varied buyer-search keywords.'],
    ['Building custom options…', 'Classifying editable text and matching thread or print color fields.'],
    ['Validating output…', 'Checking title length, 13 tags, duplicate phrases and Etsy-style field limits.'],
  ];

  window.addEventListener('scroll', () => {
    const doc = document.documentElement;
    const max = doc.scrollHeight - window.innerHeight;
    const pct = max > 0 ? (window.scrollY / max) * 100 : 0;
    pageProgress.style.width = `${pct}%`;
  }, { passive: true });

  function flash(message) {
    toast.textContent = message;
    toast.classList.add('show');
    setTimeout(() => toast.classList.remove('show'), 1700);
  }

  function currentMethod() {
    return form.querySelector('input[name="decoration_method"]:checked')?.value || 'Embroidery';
  }

  function syncPersonalizationUI() {
    const on = personalizationToggle.checked;
    personalizationValue.value = on ? 'Yes' : 'No';
    personalizationPreview.hidden = !on;
    const method = currentMethod();
    personalizationHelper.textContent = method === 'Embroidery'
      ? 'Gemini will detect editable names/text and create a “Choose Embroidery Thread Colors” field using the actual design parts.'
      : 'Gemini will detect editable names/text and create a “Choose Print Colors” field using the actual design parts.';
  }

  personalizationToggle.addEventListener('change', syncPersonalizationUI);
  form.querySelectorAll('input[name="decoration_method"]').forEach(input => input.addEventListener('change', syncPersonalizationUI));
  syncPersonalizationUI();

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
  removeBtn.addEventListener('click', event => {
    event.preventDefault();
    event.stopPropagation();
    clearPreview();
  });

  ['dragenter', 'dragover'].forEach(name => uploadZone.addEventListener(name, event => {
    event.preventDefault();
    uploadZone.classList.add('dragging');
  }));
  uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('dragging'));
  uploadZone.addEventListener('drop', event => {
    event.preventDefault();
    uploadZone.classList.remove('dragging');
    const file = event.dataTransfer?.files?.[0];
    if (!file) return;
    const dt = new DataTransfer();
    dt.items.add(file);
    imageInput.files = dt.files;
    setPreview(file);
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

    for (let attempt = 0; attempt < 6; attempt += 1) {
      canvas.width = width;
      canvas.height = height;
      ctx.clearRect(0, 0, width, height);
      ctx.drawImage(source, 0, 0, width, height);
      const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/webp', quality));
      if (!blob) throw new Error('The browser could not compress this image.');
      if (blob.size <= MAX_UPLOAD_BYTES) return new File([blob], 'seektec-design.webp', { type: 'image/webp' });
      width = Math.max(700, Math.round(width * 0.82));
      height = Math.max(700, Math.round(height * 0.82));
      quality = Math.max(0.56, quality - 0.07);
    }
    throw new Error('Image is still too large after compression. Please use a smaller image.');
  }

  function text(id, value, fallback = '—') {
    document.getElementById(id).textContent = value || fallback;
  }

  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, char => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[char]));
  }

  function fieldIcon(type) {
    const normalized = String(type || '').toLowerCase();
    if (normalized === 'name') return 'Aa';
    if (normalized === 'initials') return 'AW';
    if (normalized === 'monogram') return 'M';
    if (normalized === 'date') return '◷';
    if (normalized === 'number') return '#';
    if (normalized === 'color') return '◉';
    return 'T';
  }

  function renderPersonalization(listing, enabled) {
    const card = document.getElementById('personalization-card');
    const list = document.getElementById('personalization-fields');
    const copy = document.getElementById('personalization-copy');
    const summary = document.getElementById('personalization-summary');

    if (!enabled) {
      card.hidden = true;
      return;
    }

    card.hidden = false;
    summary.textContent = listing.personalization_summary || 'Gemini detected the customization fields shown below.';
    list.innerHTML = '';

    const fields = listing.personalization_fields || [];
    const copyParts = [];

    fields.forEach((field, index) => {
      const item = document.createElement('article');
      item.className = `custom-option ${field.detected_type === 'color' ? 'color-option' : ''}`;
      item.innerHTML = `
        <div class="drag-handle" aria-hidden="true"><i></i><i></i><i></i></div>
        <div class="field-type-icon">${escapeHtml(fieldIcon(field.detected_type))}</div>
        <div class="custom-option-main">
          <div class="custom-title-row">
            <h4>${escapeHtml(field.field_title)}</h4>
            <span class="type-badge">${escapeHtml(field.detected_type || 'text')}</span>
          </div>
          <p class="field-meta">Text box <b>•</b> ${field.required ? 'Required' : 'Optional'}</p>
          <pre>${escapeHtml(field.instructions)}</pre>
          <div class="field-limits"><span>Title ${field.field_title.length}/45</span><span>Instructions ${field.instructions.length}/120</span></div>
        </div>
        <button type="button" class="mini-copy" data-field-copy="${index}">Copy</button>
      `;
      list.appendChild(item);
      copyParts.push(`${field.field_title}\n${field.instructions}`);
    });

    if (!fields.length) {
      list.innerHTML = '<div class="empty-state">No safe customization field could be detected. Review the design manually.</div>';
    }
    copy.textContent = copyParts.join('\n\n');

    list.querySelectorAll('[data-field-copy]').forEach(btn => {
      btn.addEventListener('click', async () => {
        const field = fields[Number(btn.dataset.fieldCopy)];
        if (!field) return;
        try {
          await navigator.clipboard.writeText(`${field.field_title}\n${field.instructions}`);
          flash('Custom option copied');
        } catch {
          flash('Copy failed');
        }
      });
    });
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

    renderPersonalization(listing, data.inputs.personalization === 'Yes');

    const warningCard = document.getElementById('warning-card');
    const warningList = document.getElementById('warning-list');
    const allWarnings = [...(listing.ip_warnings || []), ...(report.errors || []), ...(report.warnings || [])];
    warningList.innerHTML = '';
    if (allWarnings.length) {
      warningCard.hidden = false;
      [...new Set(allWarnings)].forEach(item => {
        const li = document.createElement('li');
        li.textContent = item;
        warningList.appendChild(li);
      });
    } else {
      warningCard.hidden = true;
    }

    results.hidden = false;
    setTimeout(() => results.scrollIntoView({ behavior: 'smooth', block: 'start' }), 80);
  }

  form.addEventListener('submit', async event => {
    event.preventDefault();
    errorBox.hidden = true;
    results.hidden = true;
    const sourceFile = imageInput.files?.[0];
    if (!sourceFile) {
      flash('Please upload a product image');
      return;
    }

    loading.hidden = false;
    button.disabled = true;
    const buttonLabel = button.querySelector('span:nth-child(2)');
    const oldLabel = buttonLabel.textContent;
    buttonLabel.textContent = 'Generating…';
    let step = 0;
    const stepTimer = setInterval(() => {
      step = Math.min(step + 1, loadingSteps.length - 1);
      text('loading-title', loadingSteps[step][0]);
      text('loading-message', loadingSteps[step][1]);
    }, 3000);

    try {
      text('loading-title', loadingSteps[0][0]);
      text('loading-message', loadingSteps[0][1]);
      const compressed = await compressImage(sourceFile);
      const formData = new FormData(form);
      formData.set('image', compressed);
      formData.set('personalization', personalizationToggle.checked ? 'Yes' : 'No');
      const response = await fetch('/api/generate', { method: 'POST', body: formData });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.detail || `Request failed (${response.status}).`);
      render(payload);
      flash('Etsy output generated');
    } catch (error) {
      errorBox.textContent = error.message || 'Could not generate the listing.';
      errorBox.hidden = false;
      errorBox.scrollIntoView({ behavior: 'smooth', block: 'center' });
    } finally {
      clearInterval(stepTimer);
      loading.hidden = true;
      button.disabled = false;
      buttonLabel.textContent = oldLabel;
    }
  });

  document.addEventListener('click', async event => {
    const btn = event.target.closest('[data-copy]');
    if (!btn) return;
    const target = document.getElementById(btn.dataset.copy);
    if (!target) return;
    try {
      await navigator.clipboard.writeText(target.innerText.trim());
      flash('Copied to clipboard');
    } catch {
      flash('Copy failed — select the text manually');
    }
  });
})();
