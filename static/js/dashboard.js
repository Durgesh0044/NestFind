console.log('Dashboard JavaScript initializing...');

// Global State
let currentEditingId = null;
let selectedImageFiles = [];   // multi-image array for Add modal
let editSelectedImageFile = null;


function escapeHtml(text) {
  if (!text) return '';
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function quickEditProperty(propertyId, field, currentValue) {
    Swal.fire({
        title: `Edit ${field}`,
        input: 'text',
        inputValue: currentValue || '',
        inputPlaceholder: `Enter ${field.toLowerCase()}`,
        showCancelButton: true,
        confirmButtonText: 'Save',
        cancelButtonText: 'Cancel',
        preConfirm: (newValue) => {
            if (!newValue) {
                Swal.showValidationMessage(`${field} cannot be empty`);
                return false;
            }
            return newValue;
        }
    }).then((result) => {
        if (result.isConfirmed) {
            updatePropertyField(propertyId, field, result.value);
        }
    });
}

function updatePropertyField(propertyId, field, value) {
    fetch(`/admin/api/property/${propertyId}`, {
        method: 'PUT',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ [field]: value })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            Swal.fire({
                icon: 'success',
                title: 'Updated!',
                text: `${field} updated successfully`,
                toast: true,
                position: 'top-end',
                showConfirmButton: false,
                timer: 1500
            });
            setTimeout(() => location.reload(), 1500);
        } else {
            Swal.fire('Error', 'Failed to update', 'error');
        }
    });
}

// ========== ENHANCED CHART SYSTEM ==========

let currentChartPeriod = 'week';
let chartData = null;
let chartProperties = []; // Store properties for each bar

function initChart() {
  const bars = document.getElementById('chartBars');
  if (!bars) {
    console.warn('Chart container #chartBars not found');
    return;
  }

  // Get chart data from backend
  chartData = window.dashboardChartData || {
    sale_data: [0, 0, 0, 0, 0, 0, 0],
    rent_data: [0, 0, 0, 0, 0, 0, 0],
    months: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
    properties: [] // Store property IDs for each bar
  };

  renderChart(currentChartPeriod);
}

function setChartPeriod(period) {
  currentChartPeriod = period;

  // Update active button state
  document.querySelectorAll('.chart-filter-btn').forEach(btn => {
    btn.classList.remove('active');
    if (btn.getAttribute('data-period') === period) {
      btn.classList.add('active');
    }
  });

  renderChart(period);
}

function renderChart(period) {
  const bars = document.getElementById('chartBars');
  if (!bars) return;

  // Get real data from backend (window.dashboardChartData is passed from Flask)
  const backendData = window.dashboardChartData || {};

  let labels = [];
  let saleData = [];
  let rentData = [];
  let propertiesData = [];

  if (period === 'week') {
    // Use REAL weekly data from backend
    labels = backendData.weekly_labels || ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
    saleData = backendData.weekly_sale || [0, 0, 0, 0, 0, 0, 0];
    rentData = backendData.weekly_rent || [0, 0, 0, 0, 0, 0, 0];

    // If all data is zero, show message
    const total = saleData.reduce((a, b) => a + b, 0) + rentData.reduce((a, b) => a + b, 0);
    if (total === 0) {
      bars.innerHTML = `<div style="text-align: center; padding: 40px; color: var(--grey);">
        <i class="fa-solid fa-chart-line fa-2x mb-2"></i>
        <p>No property data for this week.</p>
        <p style="font-size: 12px;">Add properties to see statistics!</p>
      </div>`;
      return;
    }
  }
  else if (period === 'month') {
    // Use REAL monthly data from backend
    labels = backendData.monthly_labels || [];
    saleData = backendData.monthly_sale || [];
    rentData = backendData.monthly_rent || [];

    if (labels.length === 0) {
      bars.innerHTML = `<div style="text-align: center; padding: 40px; color: var(--grey);">
        <i class="fa-solid fa-chart-line fa-2x mb-2"></i>
        <p>No property data available for monthly view yet.</p>
        <p style="font-size: 12px;">Add some properties to see statistics!</p>
      </div>`;
      return;
    }
  }
  else { // year
    // Use REAL yearly data from backend
    labels = backendData.yearly_labels || [];
    saleData = backendData.yearly_sale || [];
    rentData = backendData.yearly_rent || [];

    if (labels.length === 0 || (saleData.reduce((a, b) => a + b, 0) === 0 && rentData.reduce((a, b) => a + b, 0) === 0)) {
      bars.innerHTML = `<div style="text-align: center; padding: 40px; color: var(--grey);">
        <i class="fa-solid fa-chart-line fa-2x mb-2"></i>
        <p>No property data available for yearly view yet.</p>
        <p style="font-size: 12px;">Add some properties to see statistics!</p>
      </div>`;
      return;
    }
  }

  // Calculate stats from REAL data
  const totalListings = backendData.total_listings || 0;
  const periodCount = saleData[saleData.length - 1] + rentData[rentData.length - 1];
  const prevCount = saleData.length > 1 ? saleData[saleData.length - 2] + rentData[rentData.length - 2] : 0;
  const percentChange = prevCount > 0 ? ((periodCount - prevCount) / prevCount * 100).toFixed(1) : 0;
  const avgPrice = backendData.avg_price || '₹0';

  // Update stats display
  const totalListingsEl = document.getElementById('chartTotalListings');
  const periodCountEl = document.getElementById('chartPeriodCount');
  const vsElement = document.getElementById('chartVsPrevious');
  const avgPriceEl = document.getElementById('chartAvgPrice');

  if (totalListingsEl) totalListingsEl.textContent = totalListings;
  if (periodCountEl) periodCountEl.textContent = periodCount;
  if (vsElement) {
    vsElement.innerHTML = `${percentChange >= 0 ? '+' : ''}${percentChange}%`;
    vsElement.style.color = percentChange >= 0 ? 'var(--green)' : 'var(--red)';
  }
  if (avgPriceEl) avgPriceEl.textContent = avgPrice;

  const maxVal = Math.max(...saleData, ...rentData);
  const max = maxVal === 0 ? 1 : maxVal;

  // Clear and rebuild bars
  bars.innerHTML = '';

  labels.forEach((label, i) => {
    const saleHeight = Math.round(((saleData[i] || 0) / max) * 100);
    const rentHeight = Math.round(((rentData[i] || 0) / max) * 100);

    const barGroup = document.createElement('div');
    barGroup.className = 'bar-group';
    barGroup.style.cssText = 'flex:1;display:flex;flex-direction:column;align-items:center;gap:3px;height:100%;justify-content:flex-end;position:relative;';

    const barsContainer = document.createElement('div');
    barsContainer.style.cssText = 'display:flex;gap:2px;align-items:flex-end;width:100%;height:calc(100% - 24px);position:relative;';

    // Sale bar
    const saleBar = document.createElement('div');
    saleBar.className = 'bar chart-clickable';
    saleBar.style.cssText = `flex:1;height:${saleHeight}%;background:var(--navy);border-radius:4px 4px 0 0;position:relative;cursor:pointer;transition:all 0.2s;`;
    saleBar.title = `${saleData[i] || 0} For Sale properties`;

    const saleTooltip = document.createElement('div');
    saleTooltip.className = 'bar-tooltip';
    saleTooltip.textContent = `${saleData[i] || 0} For Sale`;
    saleTooltip.style.cssText = 'position:absolute;bottom:100%;left:50%;transform:translateX(-50%);background:var(--navy);color:white;padding:4px 8px;border-radius:6px;font-size:10px;white-space:nowrap;opacity:0;visibility:hidden;transition:all 0.2s;z-index:10;margin-bottom:5px;';
    saleBar.appendChild(saleTooltip);

    saleBar.addEventListener('mouseenter', () => saleTooltip.style.opacity = '1');
    saleBar.addEventListener('mouseleave', () => saleTooltip.style.opacity = '0');

    saleBar.addEventListener('click', (e) => {
      e.stopPropagation();
      if ((saleData[i] || 0) > 0) {
        showPropertiesByType('For Sale', label, period, saleData[i]);
      } else {
        showToast(`No For Sale properties in ${label}`, 'info');
      }
    });

    // Rent bar
    const rentBar = document.createElement('div');
    rentBar.className = 'bar chart-clickable';
    rentBar.style.cssText = `flex:1;height:${rentHeight}%;background:var(--accent);border-radius:4px 4px 0 0;position:relative;cursor:pointer;transition:all 0.2s;`;
    rentBar.title = `${rentData[i] || 0} For Rent properties`;

    const rentTooltip = document.createElement('div');
    rentTooltip.className = 'bar-tooltip';
    rentTooltip.textContent = `${rentData[i] || 0} For Rent`;
    rentTooltip.style.cssText = 'position:absolute;bottom:100%;left:50%;transform:translateX(-50%);background:var(--accent);color:var(--navy);padding:4px 8px;border-radius:6px;font-size:10px;white-space:nowrap;opacity:0;visibility:hidden;transition:all 0.2s;z-index:10;margin-bottom:5px;';
    rentBar.appendChild(rentTooltip);

    rentBar.addEventListener('mouseenter', () => rentTooltip.style.opacity = '1');
    rentBar.addEventListener('mouseleave', () => rentTooltip.style.opacity = '0');

    rentBar.addEventListener('click', (e) => {
      e.stopPropagation();
      if ((rentData[i] || 0) > 0) {
        showPropertiesByType('For Rent', label, period, rentData[i]);
      } else {
        showToast(`No For Rent properties in ${label}`, 'info');
      }
    });

    barsContainer.appendChild(saleBar);
    barsContainer.appendChild(rentBar);

    const barLabel = document.createElement('div');
    barLabel.className = 'bar-label';
    barLabel.textContent = label;
    barLabel.style.cssText = 'font-size:10px;color:var(--grey-dark);margin-top:5px;';

    barGroup.appendChild(barsContainer);
    barGroup.appendChild(barLabel);
    bars.appendChild(barGroup);
  });
}

function showPropertiesByType(type, period, periodType, count) {
  if (count === 0) {
    showToast(`No ${type} properties in ${period} (${periodType})`, 'info');
    return;
  }

  // Create modal to show properties
  Swal.fire({
    title: `<i class="fa-solid fa-building"></i> ${type} Properties`,
    html: `
      <div style="text-align: left;">
        <p><strong>Period:</strong> ${period} (${periodType === 'week' ? 'Week' : periodType === 'month' ? 'Month' : 'Year'})</p>
        <p><strong>Total Properties:</strong> ${count}</p>
        <div id="propertyListModal" style="max-height: 400px; overflow-y: auto; margin-top: 15px;">
          <div class="text-center">
            <div class="spinner-border text-gold" role="status"></div>
            <p>Loading properties...</p>
          </div>
        </div>
      </div>
    `,
    width: '650px',
    showConfirmButton: true,
    confirmButtonText: 'Close',
    confirmButtonColor: '#C9A84C',
    showCancelButton: true,
    cancelButtonText: 'View All',
    cancelButtonColor: '#0B1F3A'
  }).then((result) => {
    if (result.dismiss === 'cancel') {
      // View all properties of this type
      window.location.href = `/properties?type=${encodeURIComponent(type)}`;
    }
  });

  // Fetch properties filtered by type AND period
  let url = `/admin/api/properties?type=${encodeURIComponent(type)}&limit=20`;

  // Add period filters
  if (periodType === 'week') {
    url += `&period=week&label=${encodeURIComponent(period)}`;
  } else if (periodType === 'month') {
    url += `&period=month&label=${encodeURIComponent(period)}`;
  } else if (periodType === 'year') {
    url += `&period=year&label=${encodeURIComponent(period)}`;
  }

  fetch(url)
    .then(response => response.json())
    .then(properties => {
      const listContainer = document.getElementById('propertyListModal');
      if (listContainer) {
        if (properties && properties.length > 0) {
          listContainer.innerHTML = properties.map(prop => `
            <div onclick="goToProperty(${prop.id})" style="cursor: pointer; padding: 12px; margin-bottom: 10px; border: 1px solid var(--grey-light); border-radius: 10px; transition: all 0.2s; background: white;" 
                 onmouseover="this.style.background='rgba(201,168,76,0.08)'; this.style.transform='translateX(5px)'" 
                 onmouseout="this.style.background='white'; this.style.transform='translateX(0)'">
              <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">
                <div style="flex: 1;">
                  <div style="font-weight: 700; color: var(--navy); margin-bottom: 4px;">${escapeHtml(prop.property)}</div>
                  <div style="font-size: 12px; color: var(--grey);">
                    <i class="fa-solid fa-location-dot" style="color: var(--gold); width: 16px;"></i> ${escapeHtml(prop.location || 'N/A')}
                  </div>
                </div>
                <div style="text-align: right;">
                  <div style="font-weight: 800; color: var(--gold); font-size: 16px;">${escapeHtml(prop.price)}</div>
                  <div style="font-size: 11px; color: var(--grey); margin-top: 4px;">
                    <span class="badge ${prop.type && prop.type.toLowerCase().includes('rent') ? 'badge-rent' : 'badge-sale'}">${escapeHtml(prop.type || 'For Sale')}</span>
                  </div>
                </div>
              </div>
              <div style="margin-top: 8px; font-size: 11px; color: var(--grey-light);">
                <i class="fa-regular fa-calendar"></i> Listed: ${prop.created_at ? new Date(prop.created_at).toLocaleDateString() : 'Recently'}
              </div>
            </div>
          `).join('');
        } else {
          listContainer.innerHTML = '<div class="text-center py-4 text-muted"><i class="fa-regular fa-building fa-2x mb-2"></i><p>No properties found for this period</p></div>';
        }
      }
    })
    .catch(error => {
      console.error('Error loading properties:', error);
      const listContainer = document.getElementById('propertyListModal');
      if (listContainer) {
        listContainer.innerHTML = '<div class="text-center py-4 text-danger">Error loading properties. Please try again.</div>';
      }
    });
}

function goToProperty(propertyId) {
  window.location.href = `/property/${propertyId}`;
}

function refreshActivities() {
  fetch('/api/activities')
    .then(response => response.json())
    .then(data => {
      if (data.success) {
        const timeline = document.getElementById('activityTimeline');
        if (timeline && data.activities) {
          timeline.innerHTML = data.activities.map(act => `
                        <div class="activity-item-premium">
                            <div class="activity-dot" style="background:rgba(61,184,122,0.12);color:var(--green)">
                                ${act.icon}
                            </div>
                            <div class="act-text">
                                <div class="act-msg" style="font-size: 0.8rem;">${act.message}</div>
                                <div class="act-time" style="font-size: 0.7rem;">${act.time_ago}</div>
                            </div>
                        </div>
                    `).join('');
          showToast('Activities refreshed!', 'success');
        }
      }
    })
    .catch(error => console.error('Error refreshing activities:', error));
}

// Initialize chart when page loads
document.addEventListener('DOMContentLoaded', function () {
  initChart();
});

// Run chart init
try {
  initChart();
} catch (e) {
  console.error('Error initializing chart:', e);
}

/* ── Modal ── */
function openModal() {
  clearAllImages();
  console.log('Opening Add Property modal...');
  const modal = document.getElementById('modal');
  if (modal) {
    modal.classList.add('open');
    modal.style.display = 'flex';
    console.log('Add Property modal class added and display set to flex.');
  } else {
    console.error('CRITICAL: Element #modal not found in DOM.');
    showToast('Add Listing form not found', 'error');
  }
}

function closeModal() {
  console.log('Closing all modals...');
  const modal = document.getElementById('modal');
  if (modal) {
    modal.classList.remove('open');
    modal.style.display = 'none';
  }
  const previewModal = document.getElementById('previewModal');
  if (previewModal) {
    previewModal.classList.remove('open');
    previewModal.style.display = 'none';
  }
  const editModal = document.getElementById('editModal');
  if (editModal) {
    editModal.classList.remove('open');
    editModal.style.display = 'none';
  }
  clearAllImages();
}

// Close modal on click outside
document.querySelectorAll('.modal-overlay').forEach(overlay => {
  overlay.addEventListener('click', e => {
    if (e.target === overlay) closeModal();
  });
});

function setTab(el) {
  document.querySelectorAll('.type-tab').forEach(t => t.classList.remove('active'));
  el.classList.add('active');
}

/* ── Upload ── */
function handleFileSelect(e, type) {
  const file = e.target.files[0];
  if (file) {
    processFile(file, type);
  }
  e.target.value = '';
}

function handleDrop(e, type) {
  e.preventDefault();
  e.currentTarget.classList.remove('dragover');
  const file = e.dataTransfer.files[0];
  if (file) processFile(file, type);
}

function handleModalFile(e) {
  const file = e.target.files[0];
  if (file) {
    showToast(`📄 ${file.name} attached`, 'info');
  }
}

function processFile(file, type) {
  if (file.size > 50 * 1024 * 1024) {
    showToast('File too large (max 50MB)', 'error');
    return;
  }

  const fileName = file.name.toLowerCase();
  if (type === 'pdf' && !fileName.endsWith('.pdf')) {
    showToast('Please select a valid PDF file (.pdf)', 'error');
    return;
  }
  if (type === 'csv' && !/\.(csv|xlsx|xls)$/i.test(fileName)) {
    showToast('Please select a valid CSV or Excel file (.csv .xlsx .xls)', 'error');
    return;
  }

  const sizeKB = Math.round(file.size / 1024);
  const sizeStr = sizeKB > 1024 ? (sizeKB / 1024).toFixed(1) + ' MB' : sizeKB + ' KB';
  addFileToList(file.name, sizeStr, type, 'uploading');

  const formData = new FormData();
  formData.append('file', file);
  formData.append('type', type);

  fetch('/admin/api/upload', {
    method: 'POST',
    body: formData,
    credentials: 'same-origin'
  })
    .then(function (response) {
      if (response.redirected || response.status === 401 || response.status === 302) {
        throw new Error('Session expired. Please refresh and log in again.');
      }
      var ct = response.headers.get('content-type') || '';
      if (!ct.includes('application/json')) {
        throw new Error('Server error (HTTP ' + response.status + '). Please refresh the page.');
      }
      return response.json();
    })
    .then(function (data) {
      if (data.success) {
        updateFileStatus(file.name, 'completed', data.size, data.rows, data.message);
        showToast('Import complete: ' + (data.imported_count || 0) + ' properties added from ' + file.name, 'success');
        if (typeof Swal !== 'undefined') {
          Swal.fire({
            title: 'Import Complete!',
            text: data.message || 'File imported successfully.',
            icon: 'success',
            confirmButtonText: 'Great!'
          });
        }
        setTimeout(function () { location.reload(); }, 2500);
      } else {
        var errMsg = data.error || data.message || 'Unknown error';
        updateFileStatus(file.name, 'error', null, null, errMsg);
        showToast('Import failed: ' + errMsg, 'error');
      }
    })
    .catch(function (error) {
      console.error('Upload error:', error);
      var msg = error.message || 'Upload failed. Check your connection.';
      updateFileStatus(file.name, 'error', null, null, msg);
      showToast(msg, 'error');
    });
}

function addFileToList(name, size, type, status = 'pending') {
  const list = document.getElementById('fileList');
  const item = document.createElement('div');
  item.className = 'file-item';
  item.setAttribute('data-filename', name);

  const statusText = status === 'uploading' ? 'Uploading' : status === 'completed' ? 'Done' : 'Pending';
  const statusClass = status === 'uploading' ? 'pending' : status === 'completed' ? 'done' : 'pending';
  const progressWidth = status === 'completed' ? '100%' : '0%';
  const progressColor = status === 'completed' ? 'var(--green)' : 'var(--accent)';

  item.innerHTML = `
    <div class="file-thumb ${type}">${type.toUpperCase()}</div>
    <div class="file-info">
      <div class="file-name">${name}</div>
      <div class="file-meta">${size} · Just now</div>
      <div class="progress-bar"><div class="progress-fill" style="width:${progressWidth};background:${progressColor}" id="prog_${Date.now()}"></div></div>
      <div class="error-details" style="display:none;margin-top:8px;padding:8px;background:rgba(224,82,82,0.1);border-radius:4px;font-size:12px;color:var(--red);border:1px solid rgba(224,82,82,0.2);"></div>
    </div>
    <div class="file-status ${statusClass}">${statusText}</div>`;

  list.insertBefore(item, list.firstChild);

  if (status === 'uploading') {
    const fill = item.querySelector('.progress-fill');
    let w = 0;
    const iv = setInterval(() => {
      w += Math.random() * 15;
      if (w >= 90) {
        w = 90;
        clearInterval(iv);
      }
      fill.style.width = w + '%';
    }, 120);
  }

  return item;
}

function updateFileStatus(filename, status, size = null, rows = null, processingResult = null) {
  const items = document.querySelectorAll('.file-item');
  for (let item of items) {
    if (item.getAttribute('data-filename') === filename) {
      const statusEl = item.querySelector('.file-status');
      const progressFill = item.querySelector('.progress-fill');
      const metaEl = item.querySelector('.file-meta');

      if (status === 'completed') {
        statusEl.textContent = 'Done';
        statusEl.className = 'file-status done';
        progressFill.style.width = '100%';
        progressFill.style.background = 'var(--green)';

        const errorDetails = item.querySelector('.error-details');
        if (errorDetails) {
          errorDetails.style.display = 'none';
        }

        if (size) {
          const rowsText = rows ? `${rows} rows · ` : '';
          metaEl.textContent = `${rowsText}${size} · Just now`;
        }
      } else if (status === 'error') {
        statusEl.textContent = 'Failed';
        statusEl.className = 'file-status error';
        progressFill.style.width = '100%';
        progressFill.style.background = 'var(--red)';

        const errorDetails = item.querySelector('.error-details');
        if (processingResult) {
          errorDetails.textContent = `Error: ${processingResult}`;
          errorDetails.style.display = 'block';
          errorDetails.style.cursor = 'pointer';
          errorDetails.title = 'Click to hide error details';

          errorDetails.onclick = function () {
            if (this.style.display === 'none') {
              this.style.display = 'block';
              this.title = 'Click to hide error details';
            } else {
              this.style.display = 'none';
              this.title = 'Click to show error details';
            }
          };
        }
      }
      break;
    }
  }
}

function saveProperty() {
  console.log('saveProperty called');

  const modal = document.getElementById('modal');
  if (!modal) {
    console.error('Modal not found');
    showToast('Modal not found', 'error');
    return;
  }

  const modalBody = modal.querySelector('.modal-body');
  const allInputs = modalBody.querySelectorAll('.form-input');
  const allSelects = modalBody.querySelectorAll('.form-select');
  const activeTab = modalBody.querySelector('.type-tab.active');

  const title = allInputs[0] ? allInputs[0].value.trim() : '';
  const location = allInputs[1] ? allInputs[1].value.trim() : '';
  const price = allInputs[2] ? allInputs[2].value.trim() : '';
  const area = allInputs[3] ? allInputs[3].value.trim() : '';
  const propertyType = allSelects[0] ? allSelects[0].value : 'Apartment / Flat';
  const bedrooms = allSelects[1] ? allSelects[1].value : '2 BHK';
  const propertyCategory = activeTab ? activeTab.textContent.trim() : '🏡 For Sale';
  // Get map picker coordinates (ADD THIS)
  const pickerLat = document.getElementById('pickerLat')?.value;
  const pickerLng = document.getElementById('pickerLng')?.value;

  console.log('Extracted form values:', {
    title, location, price, area, propertyType, bedrooms, propertyCategory
  });

  if (!title || !price) {
    showToast('Please fill in required fields (Title and Price)', 'error');
    return;
  }

  const propertyData = {
    title: title,
    location: location,
    property_type: propertyCategory,
    category: propertyType,
    price: price,
    area: area,
    bedrooms: bedrooms,
    agent: 'Admin',
    manual_lat: pickerLat || null,    // ADD THIS LINE
    manual_lng: pickerLng || null     // ADD THIS LINE
  };

  const formData = new FormData();
  formData.append('property_data', JSON.stringify(propertyData));
  selectedImageFiles.filter(Boolean).forEach(file => formData.append('images[]', file));

  const brochureFile = document.getElementById('modalPdf').files[0];
  if (brochureFile) {
    formData.append('brochure', brochureFile);
  }

  fetch('/admin/api/property-with-image', {
    method: 'POST',
    body: formData
  })
    .then(response => {
      console.log('Response status:', response.status);
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
      return response.json();
    })
    .then(data => {
      console.log('Response data:', data);
      if (data.success) {
        showToast('🏡 New listing saved successfully!', 'success');
        closeModal();
        modal.querySelectorAll('.form-input').forEach(input => input.value = '');
        modal.querySelectorAll('.form-select').forEach(select => select.selectedIndex = 0);
        modal.querySelectorAll('.type-tab').forEach(tab => tab.classList.remove('active'));
        modal.querySelector('.type-tab').classList.add('active');
        clearAllImages();
        setTimeout(() => location.reload(), 1000);
      } else {
        showToast('Failed to save property: ' + (data.message || 'Unknown error'), 'error');
      }
    })
    .catch(error => {
      console.error('Error:', error);
      showToast('Error saving property: ' + error.message, 'error');
    });
}

/* ── Toast ── */
function showToast(msg, type = 'info') {
  const c = document.getElementById('toastContainer');
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  t.innerHTML = `<span>${type === 'success' ? '✅' : 'ℹ️'}</span>${msg}`;
  c.appendChild(t);
  setTimeout(() => { t.style.opacity = '0'; t.style.transform = 'translateX(60px)'; t.style.transition = 'all .3s'; setTimeout(() => t.remove(), 300); }, 3000);
}

function testSaveProperty() {
  console.log('Testing saveProperty function...');
  saveProperty();
}

window.testSaveProperty = testSaveProperty;

/* ── Property Selection & Deletion ── */

function toggleSelectAll() {
  const selectAllCheckbox = document.getElementById('selectAll');
  const checkboxes = document.querySelectorAll('.property-checkbox');

  checkboxes.forEach(checkbox => {
    checkbox.checked = selectAllCheckbox.checked;
  });

  updateDeleteButton();
}

function updateDeleteButton() {
  const checkboxes = document.querySelectorAll('.property-checkbox:checked');
  const deleteBtn = document.getElementById('deleteSelectedBtn');

  if (checkboxes.length > 0) {
    deleteBtn.style.display = 'inline-block';
    deleteBtn.textContent = `🗑 Delete Selected (${checkboxes.length})`;
  } else {
    deleteBtn.style.display = 'none';
  }
}

function deleteProperty(propertyId) {
  Swal.fire({
    title: 'Delete Property?',
    text: 'This action cannot be undone. Are you sure you want to delete this property?',
    icon: 'warning',
    showCancelButton: true,
    confirmButtonColor: '#d33',
    cancelButtonColor: '#3085d6',
    confirmButtonText: 'Yes, delete it!'
  }).then((result) => {
    if (result.isConfirmed) {
      performDelete([propertyId]);
    }
  });
}

function deleteSelectedProperties() {
  const selectedIds = Array.from(document.querySelectorAll('.property-checkbox:checked')).map(cb => parseInt(cb.value));

  if (selectedIds.length === 0) {
    showToast('No properties selected', 'error');
    return;
  }

  const message = selectedIds.length === 1
    ? 'Delete this property?'
    : `Delete ${selectedIds.length} selected properties?`;

  Swal.fire({
    title: message,
    text: 'This action cannot be undone.',
    icon: 'warning',
    showCancelButton: true,
    confirmButtonColor: '#d33',
    cancelButtonColor: '#3085d6',
    confirmButtonText: 'Yes, delete!'
  }).then((result) => {
    if (result.isConfirmed) {
      performDelete(selectedIds);
    }
  });
}

function performDelete(propertyIds) {
  console.log('Deleting properties:', propertyIds);

  showToast('Deleting properties...', 'info');

  fetch('/admin/api/properties/delete', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ property_ids: propertyIds })
  })
    .then(response => {
      console.log('Delete response status:', response.status);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      return response.json();
    })
    .then(data => {
      console.log('Delete response data:', data);
      if (data.success) {
        showToast(`✅ ${data.message}`, 'success');

        propertyIds.forEach(id => {
          const row = document.querySelector(`tr[data-property-id="${id}"]`);
          if (row) {
            row.remove();
          }
        });

        document.getElementById('selectAll').checked = false;
        updateDeleteButton();
        updatePropertyStats();

      } else {
        showToast('Failed to delete properties: ' + (data.message || 'Unknown error'), 'error');
      }
    })
    .catch(error => {
      console.error('Error deleting properties:', error);
      showToast('Error deleting properties: ' + error.message, 'error');
    });
}

function updatePropertyStats() {
  const statValue = document.querySelector('.stat-value');
  if (statValue && statValue.textContent.includes(',')) {
    setTimeout(() => location.reload(), 1000);
  }
}

/* ── Property Preview & Edit ── */

function previewProperty(propertyId) {
  console.log('Previewing property:', propertyId);
  currentEditingId = propertyId;

  fetch(`/admin/api/property/${propertyId}`)
    .then(response => {
      console.log('Preview fetch response status:', response.status);
      return response.json();
    })
    .then(data => {
      console.log('Preview data received:', data);
      if (data) {
        const previewContent = document.getElementById('previewContent');
        const previewModal = document.getElementById('previewModal');

        if (!previewContent || !previewModal) {
          console.error('CRITICAL: Preview elements missing in DOM.');
          return;
        }

        previewContent.innerHTML = `
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;">
          <div>
            <h3 style="margin-bottom:15px;color:var(--navy);font-size:18px;">${data.property}</h3>
            <div style="display:grid;gap:10px;">
              <div><strong>Type:</strong> ${data.type}</div>
              <div><strong>Location:</strong> ${data.location || 'N/A'}</div>
              <div><strong>Category:</strong> ${data.category}</div>
              <div><strong>Price:</strong> ₹${data.price}</div>
              <div><strong>Area:</strong> ${data.area || 'N/A'}</div>
              <div><strong>Bedrooms:</strong> ${data.bedrooms || 'N/A'}</div>
              <div><strong>Status:</strong> ${data.status}</div>
              <div><strong>Agent:</strong> ${data.agent}</div>
              <div><strong>Created:</strong> ${new Date(data.created_at).toLocaleDateString()}</div>
              ${data.brochure ? `
                <div style="margin-top:15px;">
                  <a href="/static/uploads/${data.brochure}" target="_blank" class="btn btn-sm btn-outline-danger" style="border-radius:6px;">
                    <i class="fa-solid fa-file-pdf me-1"></i> View Brochure (PDF)
                  </a>
                </div>
              ` : '<div class="text-muted mt-2 small">No brochure attached</div>'}
            </div>
          </div>
          <div style="margin-top: 15px; max-width: 100%; overflow: hidden;">
            ${(() => {
            if (!data.image) {
              return '<div style="width:100%;height:200px;background:var(--grey-light);border-radius:12px;display:flex;align-items:center;justify-content:center;color:var(--grey-dark);border:2px dashed var(--grey-light);">No Image Available</div>';
            }
            let imgs = [];
            try { imgs = JSON.parse(data.image); } catch (e) { imgs = [data.image]; }
            if (!Array.isArray(imgs)) imgs = [imgs];

            if (imgs.length === 1) {
              return `<img src="/static/uploads/${imgs[0]}" style="width:100%;max-height:280px;object-fit:cover;border-radius:12px;border:1px solid var(--grey-light);" alt="Property Image" />`;
            }

            return `
                <div id="previewCarousel" class="carousel slide mt-2 rounded overflow-hidden shadow-sm" data-bs-ride="carousel" style="border:1px solid var(--grey-light);">
                  <div class="carousel-inner" style="height: 250px;">
                    ${imgs.map((fn, idx) => `
                      <div class="carousel-item h-100 ${idx === 0 ? 'active' : ''}">
                        <img src="/static/uploads/${fn}" class="d-block w-100 h-100" style="object-fit: cover;" alt="Property Image">
                      </div>
                    `).join('')}
                  </div>
                  <button class="carousel-control-prev" type="button" data-bs-target="#previewCarousel" data-bs-slide="prev" style="background: rgba(0,0,0,0.2); border: none; width: 40px; justify-content: center;">
                    <span class="carousel-control-prev-icon" aria-hidden="true" style="width: 20px; height: 20px;"></span>
                    <span class="visually-hidden">Previous</span>
                  </button>
                  <button class="carousel-control-next" type="button" data-bs-target="#previewCarousel" data-bs-slide="next" style="background: rgba(0,0,0,0.2); border: none; width: 40px; justify-content: center;">
                    <span class="carousel-control-next-icon" aria-hidden="true" style="width: 20px; height: 20px;"></span>
                    <span class="visually-hidden">Next</span>
                  </button>
                </div>
                <div style="text-align: center; font-size: 0.75rem; color: var(--grey-dark); margin-top: 5px;">
                    <i class="fa-solid fa-images me-1"></i> ${imgs.length} images available
                </div>
              `;
          })()}
          </div>
        </div>
        `;
        previewModal.classList.add('open');
        previewModal.style.display = 'flex';
        console.log('Preview modal shown and display set to flex.');
      } else {
        showToast('Property not found', 'error');
      }
    })
    .catch(err => {
      console.error('Error loading property preview:', err);
      showToast('Error loading preview', 'error');
    });
}

function closePreviewModal() {
  const modal = document.getElementById('previewModal');
  if (modal) {
    modal.classList.remove('open');
    modal.style.display = 'none';
  }
}

function editFromPreview() {
  closePreviewModal();
  if (currentEditingId) {
    editProperty(currentEditingId);
  }
}

function editProperty(propertyId) {
  console.log('Editing property:', propertyId);
  currentEditingId = propertyId;

  fetch(`/admin/api/property/${propertyId}`)
    .then(response => {
      console.log('Edit fetch response status:', response.status);
      return response.json();
    })
    .then(data => {
      console.log('Edit data received:', data);
      if (data && !data.error) {
        document.getElementById('editTitle').value = data.property || '';
        document.getElementById('editLocation').value = data.location || '';
        document.getElementById('editPrice').value = data.price || '';
        document.getElementById('editArea').value = data.area || '';

        const propertyTypeSelect = document.getElementById('editPropertyType');
        propertyTypeSelect.value = data.category || 'Apartment / Flat';

        const bedroomsSelect = document.getElementById('editBedrooms');
        bedroomsSelect.value = data.bedrooms || '2 BHK';

        const typeTabs = document.querySelectorAll('#editModal .type-tab');
        typeTabs.forEach(tab => tab.classList.remove('active'));
        if (data.type && data.type.includes('For Sale')) {
          typeTabs[0].classList.add('active');
        } else if (data.type && data.type.includes('For Rent')) {
          typeTabs[1].classList.add('active');
        } else {
          typeTabs[2].classList.add('active');
        }

        const existingImagesGrid = document.getElementById('existingImagesGrid');
        const existingImagesContainer = existingImagesGrid?.querySelector('.existing-images-container');

        // ========== FIXED: Handle image data correctly ==========
        if (data.image) {
          let imageList = [];

          if (Array.isArray(data.image)) {
            imageList = data.image;
          }
          else if (typeof data.image === 'string') {
            try {
              const parsed = JSON.parse(data.image);
              if (Array.isArray(parsed)) {
                imageList = parsed;
              } else {
                imageList = [data.image];
              }
            } catch (e) {
              imageList = [data.image];
            }
          }

          console.log('Image list for edit:', imageList);

          if (imageList.length > 0 && existingImagesContainer) {
            existingImagesContainer.innerHTML = imageList.map(img => `
              <div class="existing-image-item" style="position: relative; display: inline-block; margin: 4px;">
                <img src="/static/uploads/${img}" style="width: 80px; height: 60px; object-fit: cover; border-radius: 4px; border: 1px solid var(--grey-light);" 
                     onerror="this.src='https://placehold.co/80x60?text=No+Image'" />
                <button type="button" onclick="removeExistingImage('${img}', this)" 
                  style="position: absolute; top: -5px; right: -5px; width: 18px; height: 18px; border-radius: 50%; background: var(--red); color: white; border: none; font-size: 10px; cursor: pointer; display: flex; align-items: center; justify-content: center;">×</button>
              </div>
            `).join('');
            existingImagesGrid.style.display = 'block';
          } else {
            if (existingImagesContainer) existingImagesContainer.innerHTML = '';
            existingImagesGrid.style.display = 'none';
          }
        } else {
          if (existingImagesContainer) existingImagesContainer.innerHTML = '';
          existingImagesGrid.style.display = 'none';
        }
        // ========== END FIX ==========

        const editModal = document.getElementById('editModal');
        if (editModal) {
          editModal.classList.add('open');
          editModal.style.display = 'flex';
          console.log('Edit modal shown and display set to flex.');
        } else {
          console.error('CRITICAL: Element #editModal not found.');
          showToast('Edit form not found', 'error');
        }
      } else {
        showToast('Property not found', 'error');
      }
    })
    .catch(err => {
      console.error('Error loading property for edit:', err);
      showToast('Error loading property', 'error');
    });
}

function closeEditModal() {
  const modal = document.getElementById('editModal');
  if (modal) {
    modal.classList.remove('open');
    modal.style.display = 'none';
  }
  currentEditingId = null;
  editSelectedImageFile = null;
  
  // Clear file inputs and preview containers
  document.getElementById('editImage').value = '';
  const newImagesContainer = document.querySelector('.new-images-container');
  if (newImagesContainer) newImagesContainer.innerHTML = '';
  document.getElementById('editImagePreview').style.display = 'none';
  
  const existingImagesContainer = document.querySelector('.existing-images-container');
  if (existingImagesContainer) existingImagesContainer.innerHTML = '';
}

function setEditTab(el) {
  document.querySelectorAll('#editModal .type-tab').forEach(t => t.classList.remove('active'));
  el.classList.add('active');
}

function updateProperty() {
  if (!currentEditingId) {
    showToast('No property selected for editing', 'error');
    return;
  }

  const title = document.getElementById('editTitle').value.trim();
  const location = document.getElementById('editLocation').value.trim();
  const price = document.getElementById('editPrice').value.trim();
  const area = document.getElementById('editArea').value.trim();
  const propertyType = document.getElementById('editPropertyType').value;
  const bedrooms = document.getElementById('editBedrooms').value;
  const activeTab = document.querySelector('#editModal .type-tab.active');
  const propertyCategory = activeTab ? activeTab.textContent.trim() : '🏡 For Sale';

  if (!title || !price) {
    showToast('Please fill in required fields (Title and Price)', 'error');
    return;
  }

  const propertyData = {
    title: title,
    location: location,
    property_type: propertyCategory,
    category: propertyType,
    price: price,
    area: area,
    bedrooms: bedrooms,
    agent: 'Admin'
  };

  const updateBtn = document.getElementById('updateBtn');
  const originalText = updateBtn.textContent;
  updateBtn.textContent = 'Updating...';
  updateBtn.disabled = true;

  const newImageFiles = Array.from(document.getElementById('editImage').files);
  const existingImages = Array.from(document.querySelectorAll('.existing-image-item img')).map(img => {
    const src = img.src;
    return src.substring(src.lastIndexOf('/') + 1);
  });

  if (newImageFiles.length > 0) {
    const formData = new FormData();
    newImageFiles.forEach(file => formData.append('images[]', file));

    fetch('/admin/api/upload-images', {
      method: 'POST',
      body: formData
    })
      .then(response => response.json())
      .then(imageData => {
        if (imageData.success) {
          propertyData.image = JSON.stringify([...existingImages, ...imageData.filenames]);
          return updatePropertyData(propertyData);
        } else {
          throw new Error(imageData.message || 'Image upload failed');
        }
      })
      .catch(error => {
        console.error('Image upload error:', error);
        showToast('Error uploading images: ' + error.message, 'error');
        updateBtn.textContent = originalText;
        updateBtn.disabled = false;
      });
  } else {
    if (existingImages.length > 0) {
      propertyData.image = JSON.stringify(existingImages);
    } else {
      propertyData.image = null;
    }
    updatePropertyData(propertyData);
  }

  function updatePropertyData(data) {
    fetch(`/admin/api/property/${currentEditingId}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data)
    })
      .then(response => {
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
      })
      .then(result => {
        if (result.success) {
          showToast('✅ Property updated successfully!', 'success');
          closeEditModal();
          setTimeout(() => location.reload(), 1000);
        } else {
          showToast('Failed to update property: ' + (result.message || 'Unknown error'), 'error');
        }
      })
      .catch(error => {
        console.error('Error updating property:', error);
        showToast('Error updating property: ' + error.message, 'error');
      })
      .finally(() => {
        updateBtn.textContent = originalText;
        updateBtn.disabled = false;
      });
  }
}

/* ── Multi-Image Handling (Add Modal) ── */

function handleImageFile(event) {
  addImagesToList(Array.from(event.target.files));
  event.target.value = '';
}

function handleImageDrop(event) {
  event.preventDefault();
  document.getElementById('imageDropZone').classList.remove('dragover');
  addImagesToList(Array.from(event.dataTransfer.files).filter(f => f.type.startsWith('image/')));
}

function addImagesToList(files) {
  const grid = document.getElementById('imagePreviewGrid');
  files.forEach(file => {
    if (!file.type.startsWith('image/')) {
      showToast(`${file.name} is not an image`, 'error');
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      showToast(`${file.name} exceeds 10 MB limit`, 'error');
      return;
    }
    const idx = selectedImageFiles.length;
    selectedImageFiles.push(file);

    const reader = new FileReader();
    reader.onload = function (e) {
      const card = document.createElement('div');
      card.style.cssText = 'position:relative;width:110px;height:90px;border-radius:8px;overflow:hidden;border:2px solid var(--grey-light);flex-shrink:0;';
      card.setAttribute('data-img-idx', idx);
      card.innerHTML = `
        <img src="${e.target.result}" style="width:100%;height:100%;object-fit:cover;" />
        <button type="button" onclick="removeImageAt(${idx})"
          style="position:absolute;top:4px;right:4px;background:rgba(224,82,82,0.9);color:white;
                 border:none;border-radius:50%;width:22px;height:22px;cursor:pointer;
                 font-size:13px;line-height:1;display:flex;align-items:center;justify-content:center;">✕</button>
        <div style="position:absolute;bottom:0;left:0;right:0;background:rgba(0,0,0,0.45);
                    color:white;font-size:9px;padding:2px 4px;white-space:nowrap;overflow:hidden;
                    text-overflow:ellipsis;">${file.name}</div>`;
      grid.appendChild(card);
      grid.style.display = 'flex';
    };
    reader.readAsDataURL(file);
  });
  if (files.length) showToast(`📷 ${files.length} image(s) added`, 'info');
}

function removeImageAt(idx) {
  selectedImageFiles[idx] = null;
  const grid = document.getElementById('imagePreviewGrid');
  const card = grid.querySelector(`[data-img-idx="${idx}"]`);
  if (card) card.remove();
  if (!selectedImageFiles.some(f => f !== null)) {
    grid.style.display = 'none';
  }
}

function clearAllImages() {
  selectedImageFiles = [];
  document.getElementById('modalImage').value = '';
  const grid = document.getElementById('imagePreviewGrid');
  if (grid) {
    grid.innerHTML = '';
    grid.style.display = 'none';
  }
}

/* ── Single-Image Handling (Edit Modal) ── */

function handleEditImageFile(event) {
  const files = event.target.files;
  if (files.length > 0) {
    const newImagesContainer = document.querySelector('.new-images-container');
    newImagesContainer.innerHTML = '';

    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      if (!file.type.startsWith('image/')) {
        showToast('Please select valid image files', 'error');
        continue;
      }
      if (file.size > 10 * 1024 * 1024) {
        showToast(`Image ${file.name} exceeds 10MB limit`, 'error');
        continue;
      }

      const reader = new FileReader();
      reader.onload = function (e) {
        const imageItem = document.createElement('div');
        imageItem.className = 'new-image-item';
        imageItem.style.cssText = 'position: relative; display: inline-block; margin: 4px;';
        imageItem.innerHTML = `
          <img src="${e.target.result}" style="width: 80px; height: 60px; object-fit: cover; border-radius: 4px; border: 1px solid var(--grey-light);" />
          <button type="button" onclick="removeNewImage(this)" 
            style="position: absolute; top: -5px; right: -5px; width: 16px; height: 16px; border-radius: 50%; background: var(--red); color: white; border: none; font-size: 10px; cursor: pointer; display: flex; align-items: center; justify-content: center;">×</button>
        `;
        newImagesContainer.appendChild(imageItem);
      };
      reader.readAsDataURL(file);
    }

    document.getElementById('editImagePreview').style.display = 'block';
    showToast(`📷 ${files.length} image(s) selected for update`, 'info');
  }
}

function removeEditImage() {
  editSelectedImageFile = null;
  document.getElementById('editImage').value = '';
  const previewImg = document.getElementById('editPreviewImg');
  if (previewImg.src.includes('/static/uploads/')) return;
  document.getElementById('editImagePreview').style.display = 'none';
}

function removeExistingImage(imageName, buttonElement) {
  buttonElement.parentElement.remove();
  console.log('Removed existing image:', imageName);
}

function removeNewImage(buttonElement) {
  buttonElement.parentElement.remove();
}

function togglePropertyStatus(propertyId, isChecked) {
  console.log(`Toggling status for property ${propertyId} to ${isChecked ? 'Active' : 'Disconnected'}`);

  fetch(`/admin/api/property/toggle-status/${propertyId}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    }
  })
    .then(response => response.json())
    .then(data => {
      if (data.success) {
        showToast(`✅ ${data.message}`, 'success');
        console.log(`Status updated successfully: ${data.new_status}`);
      } else {
        showToast('Error: ' + data.message, 'error');
      }
    })
    .catch(error => {
      console.error('Error toggling property status:', error);
      showToast('Failed to update visibility', 'error');
    });
}

function copyPortfolioLink(brokerId) {

    const link = `${window.location.origin}/portfolio/${brokerId}`;

    // SweetAlert popup
    const showPortfolioPopup = () => {

        Swal.fire({
            icon: 'success',

            title: `
                <span style="font-family: 'DM Sans', sans-serif;">
                    Portfolio Link Ready!
                </span>
            `,

            html: `
                <div style="
                    text-align: left;
                    font-family: 'DM Sans', sans-serif;
                ">

                    <!-- LINK BOX -->
                    <div style="
                        background: #F8F6F0;
                        padding: 16px;
                        border-radius: 12px;
                        margin-bottom: 16px;
                    ">

                        <p style="
                            margin-bottom: 8px;
                            color: #6B7A99;
                            font-size: 12px;
                            font-weight: 500;
                        ">
                            SHAREABLE LINK
                        </p>

                        <code style="
                            background: white;
                            display: block;
                            padding: 12px;
                            border-radius: 8px;
                            font-size: 13px;
                            color: #0B1F3A;
                            word-break: break-all;
                            border: 1px solid #E8ECF4;
                        ">
                            ${link}
                        </code>

                    </div>

                    <!-- FEATURES -->
                    <div style="
                        background: #F8F6F0;
                        padding: 12px;
                        border-radius: 12px;
                        margin-bottom: 16px;
                    ">

                        <p style="
                            margin-bottom: 8px;
                            color: #6B7A99;
                            font-size: 12px;
                            font-weight: 500;
                        ">
                            WHAT CUSTOMERS SEE
                        </p>

                        <p style="
                            font-size: 13px;
                            color: #0B1F3A;
                            margin: 0;
                        ">
                            <i class="fa-solid fa-building"
                               style="color: #C9A84C; width: 20px;">
                            </i>

                            All your property listings
                        </p>

                        <p style="
                            font-size: 13px;
                            color: #0B1F3A;
                            margin-top: 8px;
                        ">
                            <i class="fa-solid fa-phone"
                               style="color: #C9A84C; width: 20px;">
                            </i>

                            Contact information included
                        </p>

                    </div>

                </div>
            `,

            showCancelButton: true,
            showConfirmButton: true,

            confirmButtonText:
                '<i class="fa-brands fa-whatsapp me-2"></i>Send via WhatsApp',

            cancelButtonText:
                '<i class="fa-regular fa-copy me-2"></i>Copy Only',

            confirmButtonColor: '#25D366',
            cancelButtonColor: '#0B1F3A',

            reverseButtons: false,

            customClass: {
                popup: 'professional-popup',
                confirmButton: 'professional-confirm-btn',
                cancelButton: 'professional-cancel-btn'
            }

        }).then((result) => {

            // WhatsApp Share
            if (result.isConfirmed) {

                const message =
                    `Check out my property portfolio:\n${link}`;

                const whatsappUrl =
                    `https://wa.me/?text=${encodeURIComponent(message)}`;

                window.open(whatsappUrl, '_blank');
            }

            // Copy Only
            else if (result.dismiss === Swal.DismissReason.cancel) {

                fallbackCopy(link);
            }
        });
    };

    // Modern Clipboard API
    if (navigator.clipboard && window.isSecureContext) {

        navigator.clipboard.writeText(link)

            .then(() => {

                if (typeof showToast === 'function') {
                    showToast('Portfolio link copied!', 'success');
                }

                showPortfolioPopup();
            })

            .catch((err) => {

                console.error('Clipboard API failed:', err);

                fallbackCopy(link);

                showPortfolioPopup();
            });

    } else {

        // HTTP / Local IP fallback
        fallbackCopy(link);

        showPortfolioPopup();
    }
}


// FALLBACK COPY
function fallbackCopy(text) {

    const textArea = document.createElement("textarea");

    textArea.value = text;

    textArea.style.position = "fixed";
    textArea.style.left = "-999999px";
    textArea.style.top = "-999999px";

    document.body.appendChild(textArea);

    textArea.focus();
    textArea.select();

    try {

        document.execCommand('copy');

        if (typeof showToast === 'function') {
            showToast('Link copied successfully!', 'success');
        }

    } catch (err) {

        console.error('Fallback copy failed:', err);

        if (typeof showToast === 'function') {
            showToast('Failed to copy link', 'error');
        }
    }

    document.body.removeChild(textArea);
}

function copyPropertyLink(propertyId, propertyName) {

    const link = `${window.location.origin}/property/${propertyId}`;

    // Reusable popup function
    const showSharePopup = () => {

        Swal.fire({
            icon: 'success',
            title: '<span style="font-family: \'DM Sans\', sans-serif;">Property Link Ready!</span>',
            html: `
                <div style="text-align: left; font-family: 'DM Sans', sans-serif;">
                    
                    <div style="
                        background: #F8F6F0;
                        padding: 12px;
                        border-radius: 12px;
                        margin-bottom: 16px;
                    ">
                        <p style="
                            margin-bottom: 4px;
                            font-weight: 600;
                            color: #0B1F3A;
                            font-size: 14px;
                        ">
                            ${propertyName}
                        </p>

                        <code style="
                            background: white;
                            display: block;
                            padding: 10px;
                            border-radius: 8px;
                            font-size: 12px;
                            color: #6B7A99;
                            word-break: break-all;
                            margin-top: 8px;
                            border: 1px solid #E8ECF4;
                        ">
                            ${link}
                        </code>
                    </div>

                    <div style="
                        display: flex;
                        gap: 12px;
                        justify-content: center;
                    ">
                        <div style="text-align:center; flex:1;">
                            <i class="fa-solid fa-phone"
                               style="font-size:20px;color:#25D366;margin-bottom:4px;display:inline-block;">
                            </i>
                            <p style="font-size:11px;color:#6B7A99;margin:0;">WhatsApp</p>
                        </div>

                        <div style="text-align:center; flex:1;">
                            <i class="fa-regular fa-envelope"
                               style="font-size:20px;color:#C9A84C;margin-bottom:4px;display:inline-block;">
                            </i>
                            <p style="font-size:11px;color:#6B7A99;margin:0;">Email</p>
                        </div>

                        <div style="text-align:center; flex:1;">
                            <i class="fa-regular fa-message"
                               style="font-size:20px;color:#0B1F3A;margin-bottom:4px;display:inline-block;">
                            </i>
                            <p style="font-size:11px;color:#6B7A99;margin:0;">SMS</p>
                        </div>
                    </div>

                </div>
            `,
            showCancelButton: true,
            showConfirmButton: true,

            confirmButtonText:
                '<i class="fa-brands fa-whatsapp me-2"></i>WhatsApp',

            cancelButtonText:
                '<i class="fa-regular fa-copy me-2"></i>Copy Link',

            confirmButtonColor: '#25D366',
            cancelButtonColor: '#0B1F3A',

            customClass: {
                popup: 'professional-popup',
                confirmButton: 'professional-confirm-btn',
                cancelButton: 'professional-cancel-btn'
            }

        }).then((result) => {

            // WhatsApp Share
            if (result.isConfirmed) {

                const message =
                    `Check out this property: ${propertyName} - ${link}`;

                const whatsappUrl =
                    `https://wa.me/?text=${encodeURIComponent(message)}`;

                window.open(whatsappUrl, '_blank');
            }

            // Manual Copy Button
            else if (result.dismiss === Swal.DismissReason.cancel) {

                fallbackCopy(link);
            }
        });
    };

    // Modern Clipboard API
    if (navigator.clipboard && window.isSecureContext) {

        navigator.clipboard.writeText(link)
            .then(() => {
                showSharePopup();
            })
            .catch((err) => {

                console.error('Clipboard API failed:', err);

                fallbackCopy(link);

                showSharePopup();
            });

    } else {

        // HTTP / LAN fallback
        fallbackCopy(link);

        showSharePopup();
    }
}


// Fallback Copy Function
function fallbackCopy(text) {

    const textArea = document.createElement("textarea");

    textArea.value = text;

    textArea.style.position = "fixed";
    textArea.style.left = "-999999px";
    textArea.style.top = "-999999px";

    document.body.appendChild(textArea);

    textArea.focus();
    textArea.select();

    try {

        document.execCommand('copy');

        if (typeof showToast === 'function') {
            showToast('Link copied successfully!', 'success');
        }

    } catch (err) {

        console.error('Fallback copy failed:', err);

        if (typeof showToast === 'function') {
            showToast('Failed to copy link', 'error');
        }
    }

    document.body.removeChild(textArea);
}


/* ── Map Picker for Add Property Modal with Two-Way Sync ── */
let pickerMap = null;
let pickerMarker = null;
let geocodeTimeout = null;

function initPickerMap() {
  if (typeof L === 'undefined') {
    console.warn('Leaflet not loaded yet');
    setTimeout(initPickerMap, 500);
    return;
  }

  if (pickerMap) {
    pickerMap.remove();
  }

  pickerMap = L.map('locationPickerMap').setView([30.7333, 76.7794], 12);

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '',
    maxZoom: 18,
  }).addTo(pickerMap);

  // CORRECTED: Get the location input (the SECOND input in the modal)
  const allInputs = document.querySelectorAll('#modal .form-input');
  const locationInput = allInputs[1]; // Index 1 is the location field

  console.log('Location input found:', locationInput); // Debug

  // ========== SYNC 1: Map Click -> Update Location Input ==========
  pickerMap.on('click', async function (e) {
    const lat = e.latlng.lat.toFixed(6);
    const lng = e.latlng.lng.toFixed(6);

    // Update marker
    if (pickerMarker) {
      pickerMap.removeLayer(pickerMarker);
    }
    pickerMarker = L.marker([lat, lng]).addTo(pickerMap);

    // Update coordinate displays
    document.getElementById('selectedLat').innerText = lat;
    document.getElementById('selectedLng').innerText = lng;
    document.getElementById('pickerLat').value = lat;
    document.getElementById('pickerLng').value = lng;

    // Reverse geocode to get address and update location input
    try {
      showToast('📍 Fetching address...', 'info');
      const response = await fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lng}&zoom=18`);
      const data = await response.json();

      if (data && data.display_name) {
        // Extract short address (city/locality)
        const addressParts = data.display_name.split(',');
        let shortAddress = addressParts[0];
        if (addressParts[1]) shortAddress += ', ' + addressParts[1];

        // Update location input (THIS IS THE FIX)
        if (locationInput) {
          locationInput.value = shortAddress;
        }
        showToast(`📍 Location set to: ${shortAddress}`, 'success');
      }
    } catch (error) {
      console.error('Reverse geocoding error:', error);
      showToast('📍 Location pinned! Enter address manually if needed.', 'info');
    }
  });

  // ========== SYNC 2: Location Input -> Update Map ==========
  if (locationInput) {
    locationInput.addEventListener('input', function () {
      // Clear previous timeout
      if (geocodeTimeout) clearTimeout(geocodeTimeout);

      // Wait for user to stop typing (debounce)
      geocodeTimeout = setTimeout(async () => {
        const address = locationInput.value.trim();
        if (!address) return;

        try {
          showToast('🔍 Searching for location...', 'info');
          const response = await fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(address)}, India&limit=1`);
          const data = await response.json();

          if (data && data.length > 0) {
            const lat = parseFloat(data[0].lat).toFixed(6);
            const lng = parseFloat(data[0].lon).toFixed(6);

            // Move map to location
            pickerMap.setView([lat, lng], 14);

            // Update or add marker
            if (pickerMarker) {
              pickerMap.removeLayer(pickerMarker);
            }
            pickerMarker = L.marker([lat, lng]).addTo(pickerMap);

            // Update coordinate displays
            document.getElementById('selectedLat').innerText = lat;
            document.getElementById('selectedLng').innerText = lng;
            document.getElementById('pickerLat').value = lat;
            document.getElementById('pickerLng').value = lng;

            showToast(`📍 Found: ${address}`, 'success');
          } else {
            showToast('Location not found. Try a different address or click on map.', 'warning');
          }
        } catch (error) {
          console.error('Geocoding error:', error);
        }
      }, 800);
    });
  }
}

function clearMapSelection() {
  if (pickerMarker) {
    pickerMap.removeLayer(pickerMarker);
    pickerMarker = null;
  }
  document.getElementById('selectedLat').innerText = '--';
  document.getElementById('selectedLng').innerText = '--';
  document.getElementById('pickerLat').value = '';
  document.getElementById('pickerLng').value = '';

  // Also clear the location input field
  const allInputs = document.querySelectorAll('#modal .form-input');
  const locationInput = allInputs[1];
  if (locationInput) {
    locationInput.value = '';
  }

  showToast('Location cleared', 'info');
}

// Initialize map when modal opens
const originalOpenModal = openModal;
openModal = function () {
  originalOpenModal();
  setTimeout(() => {
    initPickerMap();
  }, 300);
};

// Clean up when modal closes
const originalCloseModal = closeModal;
closeModal = function () {
  originalCloseModal();
  if (geocodeTimeout) clearTimeout(geocodeTimeout);
  if (pickerMap) {
    pickerMap.remove();
    pickerMap = null;
    pickerMarker = null;
  }
};



/* ── Get Current Location for Property ── */
function getCurrentLocationForProperty() {
  const btn = document.getElementById('getCurrentLocationBtn');
  const originalText = btn.innerHTML;

  if (!navigator.geolocation) {
    showToast('Geolocation is not supported by your browser', 'error');
    return;
  }

  btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Getting location...';
  btn.disabled = true;

  navigator.geolocation.getCurrentPosition(async function (position) {
    const lat = position.coords.latitude;
    const lng = position.coords.longitude;

    try {
      // Reverse geocode to get address
      const response = await fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lng}&zoom=18`);
      const data = await response.json();

      if (data && data.display_name) {
        // Extract short address
        const addressParts = data.display_name.split(',');
        let shortAddress = addressParts[0];
        if (addressParts[1]) shortAddress += ', ' + addressParts[1];

        // Update location input
        const locationInput = document.getElementById('locationInput');
        if (locationInput) locationInput.value = shortAddress;

        // Update map if it exists
        if (pickerMap) {
          pickerMap.setView([lat, lng], 15);

          if (pickerMarker) {
            pickerMap.removeLayer(pickerMarker);
          }
          pickerMarker = L.marker([lat, lng]).addTo(pickerMap);

          document.getElementById('selectedLat').innerText = lat.toFixed(6);
          document.getElementById('selectedLng').innerText = lng.toFixed(6);
          document.getElementById('pickerLat').value = lat.toFixed(6);
          document.getElementById('pickerLng').value = lng.toFixed(6);
        }

        showToast(`📍 Location set to: ${shortAddress}`, 'success');
      } else {
        // Just set coordinates without address
        if (pickerMap) {
          pickerMap.setView([lat, lng], 15);

          if (pickerMarker) {
            pickerMap.removeLayer(pickerMarker);
          }
          pickerMarker = L.marker([lat, lng]).addTo(pickerMap);

          document.getElementById('selectedLat').innerText = lat.toFixed(6);
          document.getElementById('selectedLng').innerText = lng.toFixed(6);
          document.getElementById('pickerLat').value = lat.toFixed(6);
          document.getElementById('pickerLng').value = lng.toFixed(6);
        }

        showToast(`📍 Location pinned at coordinates: ${lat.toFixed(4)}, ${lng.toFixed(4)}`, 'success');
      }
    } catch (error) {
      console.error('Reverse geocoding error:', error);
      // Still set coordinates even if address lookup fails
      if (pickerMap) {
        pickerMap.setView([lat, lng], 15);

        if (pickerMarker) {
          pickerMap.removeLayer(pickerMarker);
        }
        pickerMarker = L.marker([lat, lng]).addTo(pickerMap);

        document.getElementById('selectedLat').innerText = lat.toFixed(6);
        document.getElementById('selectedLng').innerText = lng.toFixed(6);
        document.getElementById('pickerLat').value = lat.toFixed(6);
        document.getElementById('pickerLng').value = lng.toFixed(6);
      }
      showToast(`📍 Location pinned! Enter address manually if needed.`, 'info');
    }

    btn.innerHTML = originalText;
    btn.disabled = false;

  }, function (error) {
    console.error('Geolocation error:', error);
    let errorMessage = 'Unable to get your location. ';
    switch (error.code) {
      case error.PERMISSION_DENIED:
        errorMessage += 'Please allow location access.';
        break;
      case error.POSITION_UNAVAILABLE:
        errorMessage += 'Location information unavailable.';
        break;
      case error.TIMEOUT:
        errorMessage += 'Location request timed out.';
        break;
    }
    showToast(errorMessage, 'error');
    btn.innerHTML = originalText;
    btn.disabled = false;
  });
}


// ========== COMPLETE NOTIFICATION SYSTEM ==========

let notificationCheckInterval = null;
let currentNotifications = [];
let lastUnreadCount = 0;

function loadNotifications() {
  fetch('/api/notifications')
    .then(response => response.json())
    .then(data => {
      if (data.success) {
        currentNotifications = data.notifications;
        updateNotificationUI(data.notifications, data.unread_count);

        // Show toast for new notifications
        if (data.unread_count > lastUnreadCount && lastUnreadCount > 0) {
          const newCount = data.unread_count - lastUnreadCount;
          showToast(`📬 You have ${newCount} new notification(s)!`, 'info');
          // Play sound (optional)
          // playNotificationSound();
        }
        lastUnreadCount = data.unread_count;
      }
    })
    .catch(error => console.error('Error loading notifications:', error));
}

function updateNotificationUI(notifications, unreadCount) {
  // Update bell badge
  const badge = document.getElementById('notificationBadge');
  if (badge) {
    if (unreadCount > 0) {
      badge.style.display = 'flex';
      badge.textContent = unreadCount > 99 ? '99+' : unreadCount;
    } else {
      badge.style.display = 'none';
    }
  }

  // Update dropdown list
  const notificationsList = document.getElementById('notificationsList');
  if (!notificationsList) return;

  if (!notifications || notifications.length === 0) {
    notificationsList.innerHTML = `
            <div style="padding: 60px 20px; text-align: center; color: var(--grey);">
                <i class="fa-regular fa-bell-slash fa-3x mb-3" style="opacity: 0.5;"></i>
                <p style="font-size: 14px;">No notifications yet</p>
                <p style="font-size: 12px; margin-top: 8px;">When you get inquiries, they'll appear here</p>
            </div>
        `;
    return;
  }

  notificationsList.innerHTML = notifications.map(notif => `
        <div class="notification-item ${!notif.is_read ? 'unread' : ''}" 
             onclick="handleNotificationClick(${notif.id}, '${notif.link || '#'}')"
             style="cursor: pointer; transition: background 0.2s;">
            <div class="notification-icon" style="width: 40px; height: 40px; border-radius: 10px; background: ${!notif.is_read ? 'rgba(201,168,76,0.1)' : 'var(--cream)'}; display: flex; align-items: center; justify-content: center; margin-right: 12px; font-size: 20px;">
                ${notif.icon || '🔔'}
            </div>
            <div class="notification-content" style="flex: 1;">
                <div class="notification-title" style="font-weight: ${!notif.is_read ? '700' : '600'}; font-size: 14px; color: var(--navy); margin-bottom: 4px;">
                    ${notif.title}
                </div>
                <div class="notification-message" style="font-size: 12px; color: var(--grey); margin-bottom: 4px;">
                    ${notif.message}
                </div>
                <div class="notification-time" style="font-size: 11px; color: var(--grey-light);">
                    <i class="fa-regular fa-clock"></i> ${notif.time_ago}
                </div>
            </div>
            ${!notif.is_read ? '<div class="notification-dot" style="width: 8px; height: 8px; background: var(--gold); border-radius: 50%; margin-left: 8px;"></div>' : ''}
        </div>
    `).join('');
}

function handleNotificationClick(notificationId, link) {
  // Mark this notification as read
  fetch('/api/notifications/mark-read', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ notification_ids: [notificationId] })
  })
    .then(() => {
      if (link && link !== '#') {
        window.location.href = link;
      } else {
        // Just refresh notifications
        loadNotifications();
        // Close dropdown
        const dropdown = document.getElementById('notificationsDropdown');
        if (dropdown) dropdown.style.display = 'none';
      }
    })
    .catch(error => {
      console.error('Error marking notification read:', error);
      // Still navigate even if marking fails
      if (link && link !== '#') {
        window.location.href = link;
      }
    });
}

function markAllNotificationsRead() {
  if (!confirm('Mark all notifications as read?')) return;

  fetch('/api/notifications/mark-read', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ notification_ids: [] })  // Empty array marks all as read
  })
    .then(response => response.json())
    .then(data => {
      if (data.success) {
        showToast('✅ All notifications marked as read', 'success');
        loadNotifications();  // Refresh the list
      } else {
        showToast('Failed to mark notifications as read', 'error');
      }
    })
    .catch(error => {
      console.error('Error marking all read:', error);
      showToast('Error marking notifications as read', 'error');
    });
}

function viewAllNotifications(event) {
  if (event) event.preventDefault();

  // Close dropdown
  const dropdown = document.getElementById('notificationsDropdown');
  if (dropdown) dropdown.style.display = 'none';

  // Create a modal to show all notifications
  const modalHtml = `
        <div id="allNotificationsModal" style="position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); z-index: 10000; display: flex; align-items: center; justify-content: center;">
            <div style="background: white; border-radius: 20px; width: 90%; max-width: 600px; max-height: 80vh; overflow: hidden;">
                <div style="padding: 20px; border-bottom: 1px solid var(--grey-light); display: flex; justify-content: space-between; align-items: center;">
                    <h3 style="margin: 0; font-size: 20px;">
                        <i class="fa-regular fa-bell"></i> All Notifications
                    </h3>
                    <button onclick="closeAllNotificationsModal()" style="background: none; border: none; font-size: 24px; cursor: pointer;">&times;</button>
                </div>
                <div id="allNotificationsList" style="padding: 20px; max-height: 60vh; overflow-y: auto;">
                    <div style="text-align: center; padding: 40px;">
                        <div class="spinner-border text-gold" role="status"></div>
                        <p>Loading notifications...</p>
                    </div>
                </div>
            </div>
        </div>
    `;

  // Remove existing modal if any
  const existingModal = document.getElementById('allNotificationsModal');
  if (existingModal) existingModal.remove();

  // Add modal to body
  document.body.insertAdjacentHTML('beforeend', modalHtml);

  // Load all notifications
  fetch('/api/notifications')
    .then(response => response.json())
    .then(data => {
      const listContainer = document.getElementById('allNotificationsList');
      if (!listContainer) return;

      if (!data.notifications || data.notifications.length === 0) {
        listContainer.innerHTML = `
                    <div style="text-align: center; padding: 60px 20px; color: var(--grey);">
                        <i class="fa-regular fa-bell-slash fa-3x mb-3"></i>
                        <p>No notifications yet</p>
                    </div>
                `;
        return;
      }

      listContainer.innerHTML = data.notifications.map(notif => `
                <div class="notification-item ${!notif.is_read ? 'unread' : ''}" 
                     onclick="handleNotificationClickFromModal(${notif.id}, '${notif.link || '#'}')"
                     style="cursor: pointer; padding: 12px; margin-bottom: 8px; border-radius: 8px; background: ${!notif.is_read ? 'rgba(201,168,76,0.05)' : 'white'}; border: 1px solid var(--grey-light);">
                    <div style="display: flex; gap: 12px;">
                        <div style="font-size: 24px;">${notif.icon || '🔔'}</div>
                        <div style="flex: 1;">
                            <div style="font-weight: ${!notif.is_read ? '700' : '600'}; margin-bottom: 4px;">${notif.title}</div>
                            <div style="font-size: 13px; color: var(--grey); margin-bottom: 4px;">${notif.message}</div>
                            <div style="font-size: 11px; color: var(--grey-light);">${notif.time_ago}</div>
                        </div>
                        ${!notif.is_read ? '<div style="width: 8px; height: 8px; background: var(--gold); border-radius: 50%;"></div>' : ''}
                    </div>
                </div>
            `).join('');
    });
}

function closeAllNotificationsModal() {
  const modal = document.getElementById('allNotificationsModal');
  if (modal) modal.remove();
}

function handleNotificationClickFromModal(notificationId, link) {
  fetch('/api/notifications/mark-read', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ notification_ids: [notificationId] })
  })
    .then(() => {
      closeAllNotificationsModal();
      if (link && link !== '#') {
        window.location.href = link;
      }
    });
}

// Handle status change from dropdown
document.addEventListener('DOMContentLoaded', function() {
    // Attach event listeners to status selects
    const statusSelects = document.querySelectorAll('.status-select');
    statusSelects.forEach(select => {
        select.addEventListener('change', function() {
            const propertyId = this.getAttribute('data-property-id');
            const newStatus = this.value;
            updatePropertyStatus(propertyId, newStatus, this);
        });
    });
});

function updatePropertyStatus(propertyId, newStatus, selectElement) {
    // Show loading state
    const originalText = selectElement.style;
    selectElement.style.opacity = '0.5';
    selectElement.disabled = true;
    
    fetch(`/admin/api/property/update-status/${propertyId}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ status: newStatus })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Show success message
            Swal.fire({
                icon: 'success',
                title: 'Status Updated!',
                text: `Property marked as ${newStatus}`,
                toast: true,
                position: 'top-end',
                showConfirmButton: false,
                timer: 2000
            });
            
            // Update the status badge in the table
            const row = selectElement.closest('tr');
            const statusBadge = row.querySelector('.badge');
            if (statusBadge) {
                statusBadge.textContent = newStatus;
                statusBadge.className = `badge ${newStatus === 'Active' ? 'bg-success' : newStatus === 'Sold' ? 'bg-danger' : newStatus === 'Rented' ? 'bg-warning' : 'bg-secondary'}`;
            }
            
            // Refresh stats after status change
            refreshDashboardStats();
        } else {
            Swal.fire({
                icon: 'error',
                title: 'Error',
                text: data.message || 'Failed to update status',
                toast: true,
                position: 'top-end',
                showConfirmButton: false,
                timer: 3000
            });
            // Revert select value
            selectElement.value = selectElement.getAttribute('data-old-value') || 'Active';
        }
    })
    .catch(error => {
        console.error('Error:', error);
        Swal.fire({
            icon: 'error',
            title: 'Error',
            text: 'Network error. Please try again.',
            toast: true,
            position: 'top-end',
            showConfirmButton: false,
            timer: 3000
        });
    })
    .finally(() => {
        selectElement.style.opacity = '1';
        selectElement.disabled = false;
    });
}

function refreshDashboardStats() {
    // Refresh the page to update stats
    setTimeout(() => {
        location.reload();
    }, 1500);
}

// ========== PORTFOLIO TABLE FILTER FUNCTIONS ==========

// Pagination Tracking for Property Portfolio
let portfolioCurrentPage = 1;
const portfolioItemsPerPage = 5;

function filterPortfolioTable(resetPage = true) {
    if (resetPage === true) {
        portfolioCurrentPage = 1;
    }

    const searchTerm = document.getElementById('portfolioSearchInput')?.value.toLowerCase() || '';
    const typeFilter = document.getElementById('portfolioTypeFilter')?.value || '';
    const statusFilter = document.getElementById('portfolioStatusFilter')?.value || '';
    const categoryFilter = document.getElementById('portfolioCategoryFilter')?.value || '';
    
    const tableRows = document.querySelectorAll('.card .card-body table tbody tr');
    // Filter out any injected helper/empty rows
    const realRows = Array.from(tableRows).filter(row => row.id !== 'noResultsMessage');
    const matchedRows = [];
    
    realRows.forEach(row => {
        // Get text content from the row
        const propertyName = row.cells[1]?.innerText.toLowerCase() || '';
        const location = row.cells[1]?.innerHTML.toLowerCase() || '';
        const type = row.cells[2]?.innerText.toLowerCase() || '';
        const price = row.cells[3]?.innerText.toLowerCase() || '';
        const category = row.cells[6]?.innerText.toLowerCase() || '';
        
        // Get status from toggle or dropdown
        let status = 'active';
        const toggleInput = row.cells[7]?.querySelector('input');
        const statusSelect = row.cells[8]?.querySelector('.status-select');
        
        if (toggleInput) {
            status = toggleInput.checked ? 'active' : 'disconnected';
        }
        if (statusSelect) {
            status = statusSelect.value.toLowerCase();
        }
        
        // Check if row matches all filters
        let matches = true;
        
        // Search term filter
        if (searchTerm) {
            const matchesSearch = propertyName.includes(searchTerm) || 
                                   location.includes(searchTerm) || 
                                   price.includes(searchTerm);
            if (!matchesSearch) matches = false;
        }
        
        // Type filter
        if (typeFilter && matches) {
            const typeLower = typeFilter.toLowerCase();
            if (!type.includes(typeLower)) matches = false;
        }
        
        // Status filter
        if (statusFilter && matches) {
            const statusLower = statusFilter.toLowerCase();
            if (status !== statusLower) matches = false;
        }
        
        // Category filter
        if (categoryFilter && matches) {
            const categoryLower = categoryFilter.toLowerCase();
            if (!category.includes(categoryLower)) matches = false;
        }
        
        if (matches) {
            matchedRows.push(row);
        } else {
            row.style.display = 'none';
        }
    });
    
    // ──────── PAGINATION ENGINE ────────
    const totalMatched = matchedRows.length;
    const totalPages = Math.ceil(totalMatched / portfolioItemsPerPage) || 1;
    
    if (portfolioCurrentPage > totalPages) portfolioCurrentPage = totalPages;
    if (portfolioCurrentPage < 1) portfolioCurrentPage = 1;
    
    // Slice and show only rows on this page
    matchedRows.forEach((row, index) => {
        const start = (portfolioCurrentPage - 1) * portfolioItemsPerPage;
        const end = start + portfolioItemsPerPage;
        if (index >= start && index < end) {
            row.style.display = '';
        } else {
            row.style.display = 'none';
        }
    });
    
    // Update result count display
    const totalRows = realRows.length;
    const resultSpan = document.getElementById('filterResultCount');
    if (resultSpan) {
        if (totalMatched === totalRows) {
            resultSpan.innerHTML = `Showing all ${totalRows} properties`;
        } else {
            resultSpan.innerHTML = `Showing ${totalMatched} of ${totalRows} properties`;
        }
    }
    
    // Show message if no results
    if (totalMatched === 0) {
        showNoResultsMessage();
    } else {
        removeNoResultsMessage();
    }

    // Render pagination buttons
    renderPortfolioPagination(totalMatched, totalPages);
}

function renderPortfolioPagination(totalMatched, totalPages) {
    const container = document.getElementById('portfolioPagination');
    if (!container) return;

    if (totalMatched === 0) {
        container.style.setProperty('display', 'none', 'important');
        return;
    }
    container.style.setProperty('display', 'flex', 'important');

    const infoBox = container.querySelector('.pagination-info');
    const controlsBox = container.querySelector('.pagination-controls');
    
    const startIdx = totalMatched === 0 ? 0 : ((portfolioCurrentPage - 1) * portfolioItemsPerPage) + 1;
    const endIdx = Math.min(portfolioCurrentPage * portfolioItemsPerPage, totalMatched);
    
    if (infoBox) {
        infoBox.innerHTML = `Showing <strong>${startIdx} - ${endIdx}</strong> of <strong>${totalMatched}</strong> items`;
    }

    if (controlsBox) {
        let html = '';
        
        // Previous button
        html += `<button class="pagination-btn-premium" ${portfolioCurrentPage === 1 ? 'disabled' : ''} onclick="changePortfolioPage(${portfolioCurrentPage - 1})"><i class="fa-solid fa-chevron-left" style="font-size:0.7rem"></i></button>`;
        
        // Numeric Page buttons
        for (let i = 1; i <= totalPages; i++) {
            if (i === 1 || i === totalPages || (i >= portfolioCurrentPage - 1 && i <= portfolioCurrentPage + 1)) {
                html += `<button class="pagination-btn-premium ${i === portfolioCurrentPage ? 'active' : ''}" onclick="changePortfolioPage(${i})">${i}</button>`;
            } else if (i === portfolioCurrentPage - 2 || i === portfolioCurrentPage + 2) {
                html += `<span style="align-self:center; padding: 0 4px; color:var(--grey-dark);">...</span>`;
            }
        }
        
        // Next button
        html += `<button class="pagination-btn-premium" ${portfolioCurrentPage === totalPages ? 'disabled' : ''} onclick="changePortfolioPage(${portfolioCurrentPage + 1})"><i class="fa-solid fa-chevron-right" style="font-size:0.7rem"></i></button>`;
        
        controlsBox.innerHTML = html;
    }
}

// Globally register page changing trigger
window.changePortfolioPage = function(pageNum) {
    portfolioCurrentPage = pageNum;
    // Re-run table filter without resetting to page 1
    filterPortfolioTable(false);
};

function showNoResultsMessage() {
    const tbody = document.querySelector('.card .card-body table tbody');
    if (!tbody) return;
    
    // Check if message already exists
    if (document.getElementById('noResultsMessage')) return;
    
    const noResultsRow = document.createElement('tr');
    noResultsRow.id = 'noResultsMessage';
    noResultsRow.innerHTML = `
        <td colspan="9" style="text-align: center; padding: 60px 20px;">
            <i class="fa-solid fa-building-circle-exclamation" style="font-size: 48px; color: var(--grey-light); margin-bottom: 15px; display: block;"></i>
            <h4 style="color: var(--navy); margin-bottom: 8px;">No properties found</h4>
            <p style="color: var(--grey);">Try adjusting your search or filters</p>
            <button onclick="clearPortfolioFilters()" style="margin-top: 15px; padding: 8px 20px; background: var(--gold); color: var(--navy); border: none; border-radius: 8px; cursor: pointer;">
                <i class="fa-solid fa-times"></i> Clear All Filters
            </button>
        </td>
    `;
    tbody.appendChild(noResultsRow);
}

function removeNoResultsMessage() {
    const noResultsRow = document.getElementById('noResultsMessage');
    if (noResultsRow) {
        noResultsRow.remove();
    }
}

function clearPortfolioFilters() {
    // Clear all filter inputs
    const searchInput = document.getElementById('portfolioSearchInput');
    const typeSelect = document.getElementById('portfolioTypeFilter');
    const statusSelect = document.getElementById('portfolioStatusFilter');
    const categorySelect = document.getElementById('portfolioCategoryFilter');
    
    if (searchInput) searchInput.value = '';
    if (typeSelect) typeSelect.value = '';
    if (statusSelect) statusSelect.value = '';
    if (categorySelect) categorySelect.value = '';
    
    // Trigger filter to reset table
    filterPortfolioTable();
    
    // Show toast notification
    showToast('✨ All filters cleared', 'success');
}

// Add debounce for better performance on search input
let searchTimeout;
const originalFilterPortfolioTable = filterPortfolioTable;
window.filterPortfolioTable = function(resetPage = true) {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
        originalFilterPortfolioTable(resetPage);
    }, 300);
};

// Initialize filter listeners when page loads
document.addEventListener('DOMContentLoaded', function() {
    // Add event listeners for filters
    const searchInput = document.getElementById('portfolioSearchInput');
    const typeFilter = document.getElementById('portfolioTypeFilter');
    const statusFilter = document.getElementById('portfolioStatusFilter');
    const categoryFilter = document.getElementById('portfolioCategoryFilter');
    
    if (searchInput) searchInput.addEventListener('keyup', filterPortfolioTable);
    if (typeFilter) typeFilter.addEventListener('change', filterPortfolioTable);
    if (statusFilter) statusFilter.addEventListener('change', filterPortfolioTable);
    if (categoryFilter) categoryFilter.addEventListener('change', filterPortfolioTable);
});


// Toggle notifications dropdown
document.addEventListener('DOMContentLoaded', function () {
  const bellIcon = document.getElementById('notificationBell');
  const dropdown = document.getElementById('notificationsDropdown');

  if (bellIcon && dropdown) {
    bellIcon.addEventListener('click', function (e) {
      e.stopPropagation();
      const isVisible = dropdown.style.display === 'block';

      // Close all other dropdowns first
      document.querySelectorAll('.notifications-dropdown').forEach(d => d.style.display = 'none');

      if (!isVisible) {
        dropdown.style.display = 'block';
        loadNotifications();  // Refresh when opening
      } else {
        dropdown.style.display = 'none';
      }
    });

    // Close dropdown when clicking outside
    document.addEventListener('click', function (e) {
      if (!bellIcon.contains(e.target) && !dropdown.contains(e.target)) {
        dropdown.style.display = 'none';
      }
    });
  }




  // Start polling for notifications every 30 seconds
  if (notificationCheckInterval) {
    clearInterval(notificationCheckInterval);
  }
  notificationCheckInterval = setInterval(loadNotifications, 30000);

  // Initial load
  setTimeout(loadNotifications, 1000);
});

// ========== CSV FORMAT GUIDE FUNCTIONS ==========

function openFormatGuide() {
    const modal = document.getElementById('formatGuideModal');
    if (modal) {
        modal.style.display = 'flex';
    }
}

function closeFormatGuide() {
    const modal = document.getElementById('formatGuideModal');
    if (modal) {
        modal.style.display = 'none';
    }
}

function downloadSampleTemplate() {
    // Create sample CSV content
    const csvContent = `property,price,location,type,category,bedrooms,area,status
Sunrise Villa,50 Lakhs,Sector 17 Chandigarh,For Sale,Villa / Bungalow,4 BHK,2500 sq ft,Active
Azure Apartment,35000/mo,Mohali Phase 8,For Rent,Apartment / Flat,2 BHK,1100 sq ft,Active
Green Heights,75 Lakhs,Panchkula Sector 5,For Sale,Apartment / Flat,3 BHK,1450 sq ft,Active
Commercial Plaza,1.2 Cr,Zirakpur,For Sale,Commercial,4+ BHK,5000 sq ft,Active
Studio Nest,18000/mo,Chandigarh Sector 35,For Rent,Studio,Studio,550 sq ft,Active

# ============================================
# COLUMN GUIDE:
# ============================================
# property    - Name of the property (REQUIRED)
# price       - Price formats: "50 Lakhs", "1.2 Cr", "25000/mo" (REQUIRED)
# location    - Address or area (OPTIONAL)
# type        - "For Sale" or "For Rent" (OPTIONAL)
# category    - Property category (OPTIONAL)
# bedrooms    - "2 BHK", "3 BHK", etc. (OPTIONAL)
# area        - Size in sq ft (OPTIONAL)
# status      - "Active", "Sold", "Rented" (OPTIONAL)
# ============================================`;

    // Create blob and download
    const blob = new Blob(["\uFEFF" + csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    link.href = url;
    link.setAttribute('download', 'nestfind_sample_template.csv');
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
    
    showToast('📥 Sample template downloaded!', 'success');
}

// Close modal when clicking outside
document.addEventListener('click', function(e) {
    const modal = document.getElementById('formatGuideModal');
    if (modal && modal.style.display === 'flex') {
        if (e.target === modal) {
            closeFormatGuide();
        }
    }
});



// Optional: Play sound for new notifications
function playNotificationSound() {
  try {
    const audio = new Audio('/static/sounds/notification.mp3');
    audio.play().catch(e => console.log('Audio play failed:', e));
  } catch (e) {
    console.log('Sound not supported');
  }
}



