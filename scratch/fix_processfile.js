const fs = require('fs');
let content = fs.readFileSync('c:\\Realestate\\static\\js\\dashboard.js', 'utf8');

const start = content.indexOf('function processFile(file, type)');
const end = content.indexOf('\nfunction addFileToList');

if (start === -1 || end === -1) {
  console.log('ERROR: Could not find processFile or addFileToList in dashboard.js');
  process.exit(1);
}

const newBlock = `function processFile(file, type) {
  // Validate file size (50MB limit)
  if (file.size > 50 * 1024 * 1024) {
    showToast('File too large (max 50MB)', 'error');
    return;
  }

  // Validate by extension only (MIME type unreliable on Windows for xlsx/csv)
  const fileName = file.name.toLowerCase();
  if (type === 'pdf' && !fileName.endsWith('.pdf')) {
    showToast('Please select a valid PDF file (.pdf)', 'error');
    return;
  }
  if (type === 'csv' && !/\\.(csv|xlsx|xls)$/i.test(fileName)) {
    showToast('Please select a valid CSV or Excel file (.csv .xlsx .xls)', 'error');
    return;
  }

  // Show uploading state
  const sizeKB = Math.round(file.size / 1024);
  const sizeStr = sizeKB > 1024 ? (sizeKB/1024).toFixed(1)+' MB' : sizeKB+' KB';
  addFileToList(file.name, sizeStr, type, 'uploading');

  // Build form data
  const formData = new FormData();
  formData.append('file', file);
  formData.append('type', type);

  // POST to upload endpoint
  fetch('/admin/api/upload', {
    method: 'POST',
    body: formData,
    credentials: 'same-origin'
  })
  .then(function(response) {
    // Detect session expiry / redirect
    if (response.redirected || response.status === 401 || response.status === 302) {
      throw new Error('Session expired. Please refresh and log in again.');
    }
    var ct = response.headers.get('content-type') || '';
    if (!ct.includes('application/json')) {
      throw new Error('Server error (HTTP ' + response.status + '). Please refresh the page.');
    }
    return response.json();
  })
  .then(function(data) {
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
      setTimeout(function() { location.reload(); }, 2500);
    } else {
      var errMsg = data.error || data.message || 'Unknown error';
      updateFileStatus(file.name, 'error', null, null, errMsg);
      showToast('Import failed: ' + errMsg, 'error');
    }
  })
  .catch(function(error) {
    console.error('Upload error:', error);
    var msg = error.message || 'Upload failed. Check your connection.';
    updateFileStatus(file.name, 'error', null, null, msg);
    showToast(msg, 'error');
  });
}`;

const replaced = content.substring(0, start) + newBlock + '\n' + content.substring(end);
fs.writeFileSync('c:\\Realestate\\static\\js\\dashboard.js', replaced, 'utf8');
console.log('SUCCESS: processFile replaced. New file length: ' + replaced.length);
