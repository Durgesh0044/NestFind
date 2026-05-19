/* =============================================
   NESTFIND – REAL ESTATE | script.js
============================================= */

/* ---- 1. NAVBAR SCROLL EFFECT ---- */
const navbar = document.getElementById('mainNavbar');

if (navbar) {
  window.addEventListener('scroll', () => {
    if (window.scrollY > 60) {
      navbar.classList.add('scrolled');
    } else {
      navbar.classList.remove('scrolled');
    }
  });
}

/* ---- 2. ACTIVE NAV LINK ON SCROLL ---- */
const sections = document.querySelectorAll('section[id]');
const navLinks = document.querySelectorAll('.nav-link');

const sectionObserver = new IntersectionObserver((entries) => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      const id = entry.target.getAttribute('id');
      navLinks.forEach(link => {
        link.classList.remove('active');
        if (link.getAttribute('href') === `#${id}`) {
          link.classList.add('active');
        }
      });
    }
  });
}, { threshold: 0.4 });

sections.forEach(section => sectionObserver.observe(section));

/* ---- 3. SMOOTH SCROLL FOR NAV LINKS ---- */
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
  anchor.addEventListener('click', function (e) {
    const target = document.querySelector(this.getAttribute('href'));
    if (target) {
      e.preventDefault();
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });

      // Close mobile menu if open
      const navMenu = document.getElementById('navMenu');
      const toggler = document.querySelector('.navbar-toggler');
      if (navMenu && toggler && navMenu.classList.contains('show')) {
        toggler.click();
      }
    }
  });
});

/* ---- 4. SCROLL REVEAL ANIMATION ---- */
const revealElements = document.querySelectorAll('.reveal');

const revealObserver = new IntersectionObserver((entries) => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      entry.target.classList.add('visible');
      revealObserver.unobserve(entry.target);
    }
  });
}, { threshold: 0.12, rootMargin: '0px 0px -40px 0px' });

revealElements.forEach(el => revealObserver.observe(el));

/* ---- 5. FAVOURITE BUTTON TOGGLE ---- */
document.querySelectorAll('.apt-fav').forEach(btn => {
  btn.addEventListener('click', function () {
    const icon = this.querySelector('i');
    icon.classList.toggle('fa-regular');
    icon.classList.toggle('fa-solid');
    icon.style.color = icon.classList.contains('fa-solid') ? '#e74c3c' : '';
    this.style.transform = 'scale(1.3)';
    setTimeout(() => (this.style.transform = ''), 200);
  });
});



/* ---- 6. LEAFLET MAP INITIALISATION WITH DYNAMIC PROPERTIES ---- */
document.addEventListener('DOMContentLoaded', async () => {
  if (typeof L === 'undefined') return;

  const map = L.map('propertyMap', {
    center: [30.7333, 76.7794],
    zoom: 12,
    scrollWheelZoom: false,
    attributionControl: false  // Disable attribution
  });

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '',
    maxZoom: 18,
  }).addTo(map);

  // Custom icon factory
  const createIcon = (price) =>
    L.divIcon({
      html: `<div class="custom-marker" style="background: #C9A84C; color: #0B1F3A; padding: 4px 10px; border-radius: 20px; font-size: 11px; font-weight: bold; white-space: nowrap; border: 2px solid #0B1F3A;">${price}</div>`,
      className: '',
      iconAnchor: [30, 20],
    });

  // Fetch properties from database for map
  try {
    const response = await fetch('/api/properties-for-map');
    const properties = await response.json();

    const markers = [];
    const mapList = document.getElementById('mapList');

    // Clear existing list
    if (mapList) {
      mapList.innerHTML = '';
    }

    if (properties.length === 0) {
      if (mapList) {
        mapList.innerHTML = '<li class="p-3 text-center text-muted">No properties on map yet.<br>Add locations to properties!</li>';
      }
    }

    // Show only first 5 properties in sidebar (limit)
    const displayLimit = 5;
    const showAll = properties.length <= displayLimit;

    properties.forEach((prop, idx) => {
      // Create marker for ALL properties (always show all on map)
      const marker = L.marker([prop.lat, prop.lng], { icon: createIcon(prop.price) })
        .addTo(map)
        .bindPopup(`
          <div style="font-family:'DM Sans',sans-serif;min-width:160px">
            <strong style="color:#0B1F3A;font-size:.9rem">${prop.name}</strong><br/>
            <span style="color:#6B7A99;font-size:.75rem">${prop.location}</span><br/>
            <span style="color:#C9A84C;font-weight:600">${prop.price}</span><br/>
            <a href="/property/${prop.id}" target="_blank" style="color:#0B1F3A; font-size:.7rem; text-decoration:underline;">View Details →</a>
          </div>
        `);
      markers.push(marker);

      // Add to sidebar list (only first 5)
      if (mapList && idx < displayLimit) {
        const listItem = document.createElement('li');
        listItem.className = 'map-list-item';
        if (idx === 0) listItem.classList.add('active');
        listItem.setAttribute('data-lat', prop.lat);
        listItem.setAttribute('data-lng', prop.lng);
        listItem.innerHTML = `
          <div class="mli-name">${prop.name}</div>
          <div class="mli-loc">${prop.location}</div>
          <div class="mli-price">${prop.price}</div>
        `;
        listItem.addEventListener('click', () => {
          document.querySelectorAll('.map-list-item').forEach(i => i.classList.remove('active'));
          listItem.classList.add('active');
          map.flyTo([prop.lat, prop.lng], 14, { duration: 1.2 });
          markers[idx].openPopup();
        });
        mapList.appendChild(listItem);
      }
    });

    // Add "View More" button if there are more than 5 properties
    // Add "View More" button if there are more than 5 properties
    if (mapList && properties.length > displayLimit) {
      const viewMoreItem = document.createElement('li');
      viewMoreItem.className = 'map-list-item';
      viewMoreItem.style.background = 'rgba(201,168,76,0.15)';
      viewMoreItem.style.cursor = 'pointer';
      viewMoreItem.style.border = '1px solid rgba(201,168,76,0.3)';
      viewMoreItem.style.marginTop = '8px';
      viewMoreItem.style.textAlign = 'center';
      viewMoreItem.innerHTML = `
        <div style="display: flex; align-items: center; justify-content: center; gap: 10px; padding: 8px;">
          <i class="fa-solid fa-building" style="color: #C9A84C;"></i>
          <span style="font-weight: 600; color: #C9A84C;">View All ${properties.length} Properties</span>
          <i class="fa-solid fa-arrow-right" style="color: #C9A84C;"></i>
        </div>
      `;
      viewMoreItem.addEventListener('click', () => {
        window.location.href = '/properties';
      });

      // Add hover effect
      viewMoreItem.addEventListener('mouseenter', () => {
        viewMoreItem.style.background = 'rgba(201,168,76,0.25)';
        viewMoreItem.style.transform = 'translateX(5px)';
      });
      viewMoreItem.addEventListener('mouseleave', () => {
        viewMoreItem.style.background = 'rgba(201,168,76,0.15)';
        viewMoreItem.style.transform = 'translateX(0)';
      });

      mapList.appendChild(viewMoreItem);
    }

    // Open first popup if properties exist
    if (markers.length > 0) {
      setTimeout(() => markers[0].openPopup(), 600);
    }

  } catch (error) {
    console.error('Error loading map properties:', error);
    const mapList = document.getElementById('mapList');
    if (mapList) {
      mapList.innerHTML = '<li class="p-3 text-center text-danger">Error loading map. Please refresh.</li>';
    }
  }
});


/* ---- 8. HERO TYPING EFFECT ---- */
(function heroReveal() {
  const title = document.querySelector('.hero-title');
  if (!title) return;
  title.style.opacity = '0';
  title.style.transform = 'translateY(30px)';
  setTimeout(() => {
    title.style.transition = 'opacity .9s ease, transform .9s ease';
    title.style.opacity = '1';
    title.style.transform = 'translateY(0)';
  }, 300);
})();

/* ---- 9. GALLERY HOVER TITLE ---- */
document.querySelectorAll('.gallery-item').forEach(item => {
  item.addEventListener('mouseenter', () => {
    item.style.transition = 'transform .4s cubic-bezier(.4,0,.2,1)';
  });
});

/* ---- 10. LOAD MORE BUTTON (DEMO) ---- */
const loadMoreBtn = document.querySelector('.btn-outline-load');
if (loadMoreBtn) {
  loadMoreBtn.addEventListener('click', () => {
    loadMoreBtn.textContent = 'Loading...';
    loadMoreBtn.disabled = true;
    setTimeout(() => {
      loadMoreBtn.textContent = 'All Properties Loaded ✓';
      loadMoreBtn.style.background = 'var(--navy)';
      loadMoreBtn.style.color = 'var(--white)';
    }, 1500);
  });
}

/* ---- 11. VIEW PROPERTY DETAILS ---- */
async function viewPropertyDetails(card, event) {
  // If event exists, check if we should ignore the click (e.g. clicked on carousel button or fav icon)
  if (event) {
    const ignoredSelectors = '.carousel-control-prev, .carousel-control-next, .apt-fav, .btn-outline-gold, .apt-img img';
    if (event.target.closest(ignoredSelectors)) {
      return;
    }
  }

  const propertyId = card.getAttribute('data-property-id');
  if (!propertyId) return;

  // Show modal
  const modalElement = document.getElementById('propertyModal');
  if (!modalElement) return;
  const modal = new bootstrap.Modal(modalElement);
  modal.show();

  // Show loading
  const modalBody = document.getElementById('propertyModalBody');
  modalBody.innerHTML = `
    <div class="text-center py-5">
      <div class="spinner-border text-gold" role="status">
        <span class="visually-hidden">Loading...</span>
      </div>
      <p class="mt-3 text-muted">Discovering luxury details...</p>
    </div>
  `;

  try {
    // Fetch property details
    const response = await fetch(`/api/property/${propertyId}`);
    if (!response.ok) throw new Error('Property not found');
    const data = await response.json();

    if (data.id) {
      // Populate modal with property details
      modalBody.innerHTML = `
        <div class="row g-0">
          <div class="col-md-6 border-end">
            ${data.all_images && data.all_images.length > 1 ? `
              <div id="modalCarousel" class="carousel slide h-100" data-bs-ride="carousel">
                <div class="carousel-inner h-100" style="min-height: 400px;">
                  ${data.all_images.map((img, idx) => `
                    <div class="carousel-item h-100 ${idx === 0 ? 'active' : ''}">
                      <div class="w-100 h-100" style="background-image:url('${img}'); background-size:cover; background-position:center; min-height:400px;"></div>
                    </div>
                  `).join('')}
                </div>
                <button class="carousel-control-prev" type="button" data-bs-target="#modalCarousel" data-bs-slide="prev">
                  <span class="carousel-control-prev-icon" aria-hidden="true"></span>
                </button>
                <button class="carousel-control-next" type="button" data-bs-target="#modalCarousel" data-bs-slide="next">
                  <span class="carousel-control-next-icon" aria-hidden="true"></span>
                </button>
              </div>
            ` : `
              <div class="w-100 img-expand-trigger" style="background-image:url('${data.image}'); background-size:cover; background-position:center; min-height:400px; cursor:zoom-in;"></div>
            `}
          </div>
          <div class="col-md-6 p-4">
            <div class="mb-2">
              <span class="badge bg-navy text-black px-3 py-2 rounded-pill font- outfit" style="font-size:0.75rem;">${data.category || 'Apartment'}</span>
              <span class="badge text-black ${data.type && data.type.toLowerCase().includes('rent') ? 'bg-info' : 'bg-gold'} px-3 py-2 rounded-pill font-outfit" style="font-size:0.75rem;">${data.type || 'For Sale'}</span>
            </div>
            <h3 class="mb-1 font-serif fw-bold text-navy">${data.property}</h3>
            <p class="text-muted mb-3"><i class="fa-solid fa-location-dot me-2 text-gold"></i>${data.location || 'Chandigarh Region'}</p>
            
            <div class="h4 fw-bold text-navy mb-4">${data.price}</div>
            
            <div class="row g-3 mb-4 text-center">
              <div class="col-4">
                <div class="p-2 border rounded bg-light">
                  <i class="fa-solid fa-bed text-gold mb-1"></i>
                  <div class="small text-muted">Beds</div>
                  <div class="fw-bold">${data.bedrooms || '—'}</div>
                </div>
              </div>
              <div class="col-4">
                <div class="p-2 border rounded bg-light">
                  <i class="fa-solid fa-bath text-gold mb-1"></i>
                  <div class="small text-muted">Baths</div>
                  <div class="fw-bold">2</div>
                </div>
              </div>
              <div class="col-4">
                <div class="p-2 border rounded bg-light">
                  <i class="fa-solid fa-vector-square text-gold mb-1"></i>
                  <div class="small text-muted">Area</div>
                  <div class="fw-bold">${data.area || '—'}</div>
                </div>
              </div>
            </div>
            
            <div class="card border-0 bg-light p-3 mb-4">
              <div class="d-flex align-items-center">
                <div class="flex-shrink-0">
                  <div class="bg-navy text-white rounded-circle d-flex align-items-center justify-content-center" style="width: 48px; height: 48px;">
                    <i class="fa-solid fa-user-tie"></i>
                  </div>
                </div>
                <div class="flex-grow-1 ms-3">
                  <div class="small text-muted">Listing Agent</div>
                  <div class="fw-bold text-navy">${data.broker_name || data.agent}</div>
                </div>
              </div>
            </div>
            
            <p class="text-muted small">ID: NF-${String(data.id).padStart(4, '0')} • Listed on ${new Date(data.created_at).toLocaleDateString()}</p>
          </div>
        </div>
      `;

      // Update contact broker button - Pass property ID
      const contactBtn = document.getElementById('contactBrokerBtn');
      if (contactBtn) {
        contactBtn.onclick = () => contactBroker(data.broker_name || data.agent, data.property, data.id, data.broker_id);
      }

    } else {
      modalBody.innerHTML = `
        <div class="alert alert-danger m-3">
          <h5>Error loading property details</h5>
          <p>Unable to load property information. Please try again later.</p>
        </div>
      `;
    }
  } catch (error) {
    console.error('Error loading property details:', error);
    modalBody.innerHTML = `
      <div class="alert alert-danger m-3">
        <h5>Error loading property details</h5>
        <p>Network error. Please check your connection and try again.</p>
      </div>
    `;
  }
}

function contactBroker(agentName, propertyName, propertyId, brokerId) {
  console.log('contactBroker called with:', propertyName, 'ID:', propertyId);

  // Close modal first
  const modal = bootstrap.Modal.getInstance(document.getElementById('propertyModal'));
  if (modal) {
    modal.hide();
  }

  // Remove backdrops
  const backdrops = document.querySelectorAll('.modal-backdrop');
  backdrops.forEach(backdrop => backdrop.remove());
  document.body.classList.remove('modal-open');
  document.body.style.overflow = '';

  // Store property info
  const propertyInfo = {
    id: propertyId,
    name: propertyName,
    broker_id: brokerId
  };
  localStorage.setItem('inquiryProperty', JSON.stringify(propertyInfo));
  console.log('Stored property info:', propertyInfo);

  // Redirect to HOME page (not properties page)
  console.log('Redirecting to home page...');
  window.location.href = '/';  // Changed from '/#contact' to '/'
}


// Convert budget selection to price range for search
function getBudgetPriceRange(budgetValue) {
  const budgetMap = {
    // Rent ranges
    'rent-0-5k': { type: 'rent', min: 0, max: 5000 },
    'rent-5-10k': { type: 'rent', min: 5000, max: 10000 },
    'rent-10-15k': { type: 'rent', min: 10000, max: 15000 },
    'rent-15-20k': { type: 'rent', min: 15000, max: 20000 },
    'rent-20-30k': { type: 'rent', min: 20000, max: 30000 },
    'rent-30-40k': { type: 'rent', min: 30000, max: 40000 },
    'rent-40-50k': { type: 'rent', min: 40000, max: 50000 },
    'rent-50k+': { type: 'rent', min: 50000, max: null },

    // Buy ranges
    'buy-0-10l': { type: 'buy', min: 0, max: 1000000 },
    'buy-10-20l': { type: 'buy', min: 1000000, max: 2000000 },
    'buy-20-30l': { type: 'buy', min: 2000000, max: 3000000 },
    'buy-30-50l': { type: 'buy', min: 3000000, max: 5000000 },
    'buy-50-80l': { type: 'buy', min: 5000000, max: 8000000 },
    'buy-80l-1cr': { type: 'buy', min: 8000000, max: 10000000 },
    'buy-1cr-2cr': { type: 'buy', min: 10000000, max: 20000000 },
    'buy-2cr-3cr': { type: 'buy', min: 20000000, max: 30000000 },
    'buy-3cr+': { type: 'buy', min: 30000000, max: null }
  };

  return budgetMap[budgetValue] || null;
}

/* ---- 13. SEARCH FUNCTIONALITY ---- */
// Main search function
function performSearch() {
  const params = new URLSearchParams();

  // Location filter
  const location = document.getElementById('searchLocation')?.value.trim();
  if (location) params.append('location', location);

  // Property Type filter
  const type = document.getElementById('searchType')?.value;
  if (type && type !== '') params.append('type', type);

  // Budget filter - Convert to proper price range
  const budgetValue = document.getElementById('searchBudget')?.value;
  if (budgetValue && budgetValue !== '') {
    const budgetRange = getBudgetPriceRange(budgetValue);
    if (budgetRange) {
      // Set listing type based on budget type
      if (budgetRange.type === 'rent') {
        params.append('listing_type', 'For Rent');
      } else if (budgetRange.type === 'buy') {
        params.append('listing_type', 'For Sale');
      }
      // Set price range
      if (budgetRange.min !== null && budgetRange.min > 0) {
        params.append('min_price', budgetRange.min);
      }
      if (budgetRange.max !== null) {
        params.append('max_price', budgetRange.max);
      }
    }
  }

  // Advanced filters - Price Range
  const minPrice = document.getElementById('minPrice')?.value;
  const maxPrice = document.getElementById('maxPrice')?.value;
  if (minPrice) params.append('min_price', minPrice);
  if (maxPrice) params.append('max_price', maxPrice);

  // Advanced filters - Area Range
  const minArea = document.getElementById('minArea')?.value;
  const maxArea = document.getElementById('maxArea')?.value;
  if (minArea) params.append('min_area', minArea);
  if (maxArea) params.append('max_area', maxArea);

  // Bedrooms filter
  const bedrooms = [];
  document.querySelectorAll('.filter-checkbox[data-filter="bedrooms"]:checked').forEach(cb => {
    bedrooms.push(cb.value);
  });
  if (bedrooms.length) params.append('bedrooms', bedrooms.join(','));

  // Category filter
  const categories = [];
  document.querySelectorAll('.filter-checkbox[data-filter="category"]:checked').forEach(cb => {
    categories.push(cb.value);
  });
  if (categories.length) params.append('category', categories.join(','));

  // Redirect to search results
  window.location.href = `/properties?${params.toString()}`;
}


// Also update the search input to trigger on Enter key
document.getElementById('searchLocation')?.addEventListener('keypress', function (e) {
  if (e.key === 'Enter') {
    e.preventDefault();
    performSearch();
  }
});


/* ---- 14. IMAGE EXPANSION ---- */
document.addEventListener('DOMContentLoaded', () => {
  const imageModal = document.getElementById('imageViewerModal');
  const expandedImg = document.getElementById('expandedImage');

  if (imageModal && expandedImg) {
    const bsModal = new bootstrap.Modal(imageModal);

    // Add click listener to all property images
    document.addEventListener('click', (e) => {
      // Find if clicked element is a property image
      const target = e.target;
      const isAptImg = target.closest('.apt-img');

      if (isAptImg) {
        // Find the actual image URL
        let imageUrl = '';

        // Handle images inside carousel or single div
        const bgImg = target.style.backgroundImage;

        if (bgImg && bgImg !== 'none') {
          imageUrl = bgImg.slice(4, -1).replace(/['"]/g, "");
        } else {
          // Check computed style if inline style is missing
          const computedStyle = window.getComputedStyle(target);
          if (computedStyle.backgroundImage && computedStyle.backgroundImage !== 'none') {
            imageUrl = computedStyle.backgroundImage.slice(4, -1).replace(/['"]/g, "");
          }
        }

        // If still not found, check if clicked on an IMG tag inside
        if (!imageUrl && target.tagName === 'IMG') {
          imageUrl = target.src;
        }

        if (imageUrl && !e.target.closest('.carousel-control-prev') && !e.target.closest('.carousel-control-next') && !e.target.closest('.apt-fav')) {
          expandedImg.src = imageUrl;
          bsModal.show();
        }
      }
    });
  }



  // Add cursor pointer to property images
  const style = document.createElement('style');
  style.textContent = `
    .apt-img { cursor: zoom-in; }
    .carousel-control-prev, .carousel-control-next, .apt-fav { cursor: pointer; }
  `;
  document.head.appendChild(style);
});

/* ---- GET CURRENT LOCATION ---- */
function getCurrentLocation() {
  if (navigator.geolocation) {
    // Show loading indicator on button
    const nearMeBtn = document.querySelector('.btn-nearme');
    const originalText = nearMeBtn.innerHTML;
    nearMeBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Getting location...';
    nearMeBtn.disabled = true;

    navigator.geolocation.getCurrentPosition(async function (position) {
      const lat = position.coords.latitude;
      const lng = position.coords.longitude;

      try {
        const response = await fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lng}&zoom=14`);
        const data = await response.json();

        if (data && data.display_name) {
          const city = data.address.city || data.address.town || data.address.village || data.address.county;
          if (city) {
            // ONLY fill the search box, DO NOT search
            document.getElementById('searchLocation').value = city;
            showToast(`📍 Location set to: ${city}. Now add filters and click Search.`, 'success');
          } else {
            // If no city found, use the area name
            const area = data.display_name.split(',')[0];
            document.getElementById('searchLocation').value = area;
            showToast(`📍 Location set to: ${area}. Now add filters and click Search.`, 'success');
          }
        }
      } catch (error) {
        console.error('Error getting location name:', error);
        showToast('Location detected! Add filters and click Search.', 'info');
      }

      // Reset button
      nearMeBtn.innerHTML = originalText;
      nearMeBtn.disabled = false;

    }, function (error) {
      showToast('Unable to get your location. Please enable location services.', 'error');
      nearMeBtn.innerHTML = originalText;
      nearMeBtn.disabled = false;
    });
  } else {
    showToast('Geolocation is not supported by your browser', 'error');
  }
}



/* ---- 15. GOOGLE MAPS-LIKE REAL-TIME LOCATION AUTOCOMPLETE ---- */
let searchTimeout = null;
let currentSearchQuery = '';
const locationInput = document.getElementById('searchLocation');
const suggestionsBox = document.getElementById('locationSuggestions');

// Make function globally accessible
// Make function globally accessible
window.selectLocation = function (locationName, lat, lon) {
  console.log('Location selected:', locationName);
  const inputField = document.getElementById('searchLocation');
  if (inputField) {
    // Extract just the main name (before first comma)
    const mainName = locationName.split(',')[0];
    inputField.value = mainName;
  }
  if (suggestionsBox) {
    suggestionsBox.style.display = 'none';
  }
  // REMOVED: performSearch(); - Don't auto-search
  // User will click Search button manually after adding filters
};

async function fetchLocationSuggestions(query) {
  if (!query || query.length < 2) {
    if (suggestionsBox) suggestionsBox.style.display = 'none';
    return;
  }

  currentSearchQuery = query;

  if (suggestionsBox) {
    suggestionsBox.innerHTML = `
            <div class="suggestion-loading">
                <i class="fa-solid fa-spinner fa-spin"></i> Searching locations...
            </div>
        `;
    suggestionsBox.style.display = 'block';
  }

  try {
    // Use OpenStreetMap Nominatim API
    const response = await fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(query)}&limit=8&addressdetails=1&countrycodes=in&accept-language=en`);
    const data = await response.json();

    if (data && data.length > 0 && suggestionsBox) {
      suggestionsBox.innerHTML = data.map(place => {
        let mainName = place.display_name.split(',')[0];
        let subName = place.display_name.split(',').slice(1, 3).join(',').trim();

        let icon = 'fa-solid fa-location-dot';
        if (place.type === 'city') icon = 'fa-solid fa-city';
        else if (place.type === 'town') icon = 'fa-solid fa-town';
        else if (place.type === 'village') icon = 'fa-solid fa-tree';

        return `
            <div class="suggestion-item" onclick="selectLocation('${place.display_name.replace(/'/g, "\\'")}', ${place.lat}, ${place.lon})">
                <div class="suggestion-icon">
                    <i class="${icon}"></i>
                </div>
                <div class="suggestion-text">
                    <div class="suggestion-main">${highlightMatchText(mainName, query)}</div>
                    ${subName ? `<div class="suggestion-sub">${highlightMatchText(subName, query)}</div>` : ''}
                </div>
            </div>
        `;
      }).join('');
    }
    else if (suggestionsBox) {
      suggestionsBox.innerHTML = `
                <div class="suggestion-item" style="justify-content: center; color: var(--grey);">
                    <i class="fa-solid fa-map-marker-alt"></i>
                    <span>No locations found. Try a different search.</span>
                </div>
            `;
    }
  } catch (error) {
    console.error('Error fetching suggestions:', error);
    if (suggestionsBox) {
      suggestionsBox.innerHTML = `
                <div class="suggestion-item" style="justify-content: center; color: var(--red);">
                    <i class="fa-solid fa-exclamation-triangle"></i>
                    <span>Error loading suggestions. Please try again.</span>
                </div>
            `;
    }
  }
}

function highlightMatchText(text, query) {
  if (!text || !query) return text;
  const regex = new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
  return text.replace(regex, '<strong>$1</strong>');
}

// Real-time input handler
if (locationInput) {
  locationInput.addEventListener('input', function (e) {
    if (searchTimeout) clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
      fetchLocationSuggestions(e.target.value);
    }, 400);
  });

  // Close suggestions when clicking outside
  document.addEventListener('click', function (e) {
    if (suggestionsBox && !locationInput.contains(e.target) && !suggestionsBox.contains(e.target)) {
      suggestionsBox.style.display = 'none';
    }
  });

  // Handle Enter key
  locationInput.addEventListener('keypress', function (e) {
    if (e.key === 'Enter') {
      if (suggestionsBox) suggestionsBox.style.display = 'none';
      performSearch();
    }
  });
}

// ========== FAVORITE PROPERTIES FUNCTIONS - SINGLE CLEAN VERSION ==========
// Load favorite statuses for all favorite buttons on page
async function loadFavoriteStatuses() {
  // First check if user is likely logged in by looking for dashboard elements
  const isLoggedIn = document.querySelector('.dropdown') !== null ||
    document.querySelector('a[href*="logout"]') !== null;

  if (!isLoggedIn) {
    console.log('User not logged in, skipping favorite status load');
    // Set all favorite buttons to inactive state
    document.querySelectorAll('.favorite-btn').forEach(btn => {
      const icon = btn.querySelector('i');
      icon.classList.remove('fa-solid');
      icon.classList.add('fa-regular');
      icon.style.color = '#666';
      btn.setAttribute('data-favorited', 'false');
    });
    return;
  }

  const buttons = document.querySelectorAll('.favorite-btn');
  if (buttons.length === 0) return;

  console.log(`Loading favorite status for ${buttons.length} properties`);

  for (let btn of buttons) {
    const propertyId = btn.getAttribute('data-property-id');
    if (!propertyId) continue;

    try {
      const response = await fetch(`/api/favorites/check?property_id=${propertyId}`, {
        credentials: 'same-origin',
        headers: {
          'Accept': 'application/json'
        }
      });

      // Check if response is JSON
      const contentType = response.headers.get('content-type');
      if (!contentType || !contentType.includes('application/json')) {
        console.log('Non-JSON response received, user may not be logged in');
        return;
      }

      if (!response.ok) {
        if (response.status === 401) {
          console.log('Not authenticated, stopping favorite status load');
          return;
        }
        continue;
      }

      const data = await response.json();
      if (data.success && data.is_favorite) {
        const icon = btn.querySelector('i');
        icon.classList.remove('fa-regular');
        icon.classList.add('fa-solid');
        icon.style.color = '#e74c3c';
        btn.setAttribute('data-favorited', 'true');
      } else {
        btn.setAttribute('data-favorited', 'false');
      }
    } catch (error) {
      console.error('Error loading favorite status:', error);
      // If we get HTML response, user is likely not logged in
      if (error.message.includes('Unexpected token')) {
        console.log('Received HTML response - user not logged in');
        return;
      }
    }
  }
}

// Toggle favorite status
async function toggleFavorite(event, propertyId) {
  // Stop event propagation to prevent card click
  if (event) {
    event.stopPropagation();
    event.preventDefault();
  }

  const btn = event ? event.currentTarget : document.querySelector(`.favorite-btn[data-property-id="${propertyId}"]`);
  if (!btn) return;

  const icon = btn.querySelector('i');

  // Optimistic UI update
  const isCurrentlyFavorited = icon.classList.contains('fa-solid');

  if (isCurrentlyFavorited) {
    icon.classList.remove('fa-solid');
    icon.classList.add('fa-regular');
    icon.style.color = '#666';
  } else {
    icon.classList.remove('fa-regular');
    icon.classList.add('fa-solid');
    icon.style.color = '#e74c3c';
  }

  try {
    const response = await fetch('/api/favorites/toggle', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      credentials: 'same-origin',
      body: JSON.stringify({ property_id: propertyId })
    });

    if (!response.ok) {
      if (response.status === 401) {
        // Revert the heart
        if (isCurrentlyFavorited) {
          icon.classList.remove('fa-regular');
          icon.classList.add('fa-solid');
          icon.style.color = '#e74c3c';
        } else {
          icon.classList.remove('fa-solid');
          icon.classList.add('fa-regular');
          icon.style.color = '#666';
        }
        showToast('Please login to save favorites', 'warning');
        setTimeout(() => {
          window.location.href = '/signin?next=' + encodeURIComponent(window.location.pathname);
        }, 2000);
        return;
      }
      throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();

    if (!data.success) {
      // Revert on error
      if (isCurrentlyFavorited) {
        icon.classList.remove('fa-regular');
        icon.classList.add('fa-solid');
        icon.style.color = '#e74c3c';
      } else {
        icon.classList.remove('fa-solid');
        icon.classList.add('fa-regular');
        icon.style.color = '#666';
      }
      showToast(data.message || 'Error saving favorite', 'error');
    } else {
      btn.setAttribute('data-favorited', data.is_favorite ? 'true' : 'false');
      showToast(data.message, 'success');

      // Update any other favorite buttons for the same property on the page
      document.querySelectorAll(`.favorite-btn[data-property-id="${propertyId}"]`).forEach(otherBtn => {
        if (otherBtn !== btn) {
          const otherIcon = otherBtn.querySelector('i');
          if (data.is_favorite) {
            otherIcon.classList.remove('fa-regular');
            otherIcon.classList.add('fa-solid');
            otherIcon.style.color = '#e74c3c';
          } else {
            otherIcon.classList.remove('fa-solid');
            otherIcon.classList.add('fa-regular');
            otherIcon.style.color = '#666';
          }
        }
      });
    }
  } catch (error) {
    console.error('Error:', error);
    // Revert on error
    if (isCurrentlyFavorited) {
      icon.classList.remove('fa-regular');
      icon.classList.add('fa-solid');
      icon.style.color = '#e74c3c';
    } else {
      icon.classList.remove('fa-solid');
      icon.classList.add('fa-regular');
      icon.style.color = '#666';
    }
    showToast('Network error. Please try again.', 'error');
  }
}

// Initialize favorites on page load - SINGLE CALL ONLY
document.addEventListener('DOMContentLoaded', function () {
  // Small delay to ensure everything is loaded
  setTimeout(() => {
    loadFavoriteStatuses();
  }, 500);
});


function showToast(message, type = 'info') {
  // Create toast container if not exists
  let container = document.getElementById('toastContainer');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toastContainer';
    container.style.cssText = 'position: fixed; bottom: 20px; right: 20px; z-index: 9999;';
    document.body.appendChild(container);
  }

  const toast = document.createElement('div');
  toast.className = `toast align-items-center text-white bg-${type === 'success' ? 'success' : type === 'error' ? 'danger' : 'warning'} border-0`;
  toast.setAttribute('role', 'alert');
  toast.style.marginTop = '10px';
  toast.style.minWidth = '250px';
  toast.style.animation = 'slideInRight 0.3s ease';
  toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">${message}</div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
    `;
  container.appendChild(toast);

  const bsToast = new bootstrap.Toast(toast, { delay: 3000 });
  bsToast.show();

  setTimeout(() => toast.remove(), 3500);
}

// Add animation CSS
const style = document.createElement('style');
style.textContent = `
    @keyframes slideInRight {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
`;
document.head.appendChild(style);

// Initialize favorites on page load - SINGLE CALL ONLY
document.addEventListener('DOMContentLoaded', function () {
  setTimeout(() => {
    loadFavoriteStatuses();
  }, 500);
});



// // Call this on properties page load
// if (window.location.pathname === '/properties') {
//   document.addEventListener('DOMContentLoaded', loadPropertiesWithFilters);
// }



// ========== SEARCH FUNCTIONS - WORKING VERSION ==========

// // ========== CLEAN SEARCH FUNCTIONALITY ==========

// let currentFilters = {
//     location: '',
//     propertyType: '',
//     budget: '',
//     bedrooms: '',
//     listingType: ''
// };

// // Initialize search
// document.addEventListener('DOMContentLoaded', function() {
//     const searchBtn = document.getElementById('searchBtn');
//     const nearMeBtn = document.getElementById('nearMeBtn');
//     const clearFiltersBtn = document.getElementById('clearAllFiltersBtn');
//     const searchLocation = document.getElementById('searchLocation');

//     if (searchBtn) searchBtn.addEventListener('click', performSearch);
//     if (nearMeBtn) nearMeBtn.addEventListener('click', getCurrentLocationAndSearch);
//     if (clearFiltersBtn) clearFiltersBtn.addEventListener('click', clearAllFilters);

//     // Filter chips
//     document.querySelectorAll('.filter-chip').forEach(chip => {
//         chip.addEventListener('click', function() {
//             this.classList.toggle('active');

//             // Handle bedroom filters
//             const bedrooms = this.getAttribute('data-bedrooms');
//             if (bedrooms) {
//                 currentFilters.bedrooms = this.classList.contains('active') ? bedrooms : '';
//             }

//             // Handle listing type filters
//             const listingType = this.getAttribute('data-listing');
//             if (listingType) {
//                 currentFilters.listingType = this.classList.contains('active') ? listingType : '';
//             }

//             updateActiveFiltersDisplay();
//         });
//     });

//     // Main search inputs
//     if (searchLocation) {
//         searchLocation.addEventListener('input', function() {
//             currentFilters.location = this.value;
//             updateActiveFiltersDisplay();
//         });
//     }

//     const searchType = document.getElementById('searchType');
//     if (searchType) {
//         searchType.addEventListener('change', function() {
//             currentFilters.propertyType = this.value;
//             updateActiveFiltersDisplay();
//         });
//     }

//     const searchBudget = document.getElementById('searchBudget');
//     if (searchBudget) {
//         searchBudget.addEventListener('change', function() {
//             currentFilters.budget = this.value;
//             updateActiveFiltersDisplay();
//         });
//     }

//     // Enter key on location input
//     if (searchLocation) {
//         searchLocation.addEventListener('keypress', function(e) {
//             if (e.key === 'Enter') performSearch();
//         });
//     }
// });

// // Update active filters display
// function updateActiveFiltersDisplay() {
//     const container = document.getElementById('activeFiltersContainer');
//     const listContainer = document.getElementById('activeFiltersList');
//     const activeFilters = [];

//     if (currentFilters.location) activeFilters.push({ type: 'location', label: `📍 ${currentFilters.location}` });
//     if (currentFilters.propertyType) activeFilters.push({ type: 'type', label: `🏢 ${currentFilters.propertyType}` });
//     if (currentFilters.budget) activeFilters.push({ type: 'budget', label: `💰 ${getBudgetLabel(currentFilters.budget)}` });
//     if (currentFilters.bedrooms) activeFilters.push({ type: 'bedrooms', label: `🛏️ ${currentFilters.bedrooms} BHK` });
//     if (currentFilters.listingType) activeFilters.push({ type: 'listingType', label: `🏷️ ${currentFilters.listingType}` });

//     if (activeFilters.length > 0) {
//         container.style.display = 'block';
//         listContainer.innerHTML = activeFilters.map(filter => `
//             <span class="filter-tag">
//                 ${filter.label}
//                 <span class="remove-tag" onclick="removeFilter('${filter.type}')">
//                     <i class="fa-solid fa-times"></i>
//                 </span>
//             </span>
//         `).join('');
//     } else {
//         container.style.display = 'none';
//     }
// }

// function getBudgetLabel(budgetCode) {
//     const budgets = {
//         '0-30lakhs': 'Under ₹30 Lakhs',
//         '30-50lakhs': '₹30L - ₹50L',
//         '50-80lakhs': '₹50L - ₹80L',
//         '80lakhs-1cr': '₹80L - ₹1Cr',
//         '1cr-2cr': '₹1Cr - ₹2Cr',
//         '2cr+': '₹2Cr+',
//         'rent-0-20k': 'Under ₹20k/mo',
//         'rent-20-40k': '₹20k - ₹40k/mo',
//         'rent-40-60k': '₹40k - ₹60k/mo',
//         'rent-60k+': '₹60k+/mo'
//     };
//     return budgets[budgetCode] || budgetCode;
// }

// function removeFilter(type) {
//     switch(type) {
//         case 'location':
//             currentFilters.location = '';
//             document.getElementById('searchLocation').value = '';
//             break;
//         case 'type':
//             currentFilters.propertyType = '';
//             document.getElementById('searchType').value = '';
//             break;
//         case 'budget':
//             currentFilters.budget = '';
//             document.getElementById('searchBudget').value = '';
//             break;
//         case 'bedrooms':
//             currentFilters.bedrooms = '';
//             document.querySelectorAll('.filter-chip[data-bedrooms]').forEach(chip => {
//                 chip.classList.remove('active');
//             });
//             break;
//         case 'listingType':
//             currentFilters.listingType = '';
//             document.querySelectorAll('.filter-chip[data-listing]').forEach(chip => {
//                 chip.classList.remove('active');
//             });
//             break;
//     }
//     updateActiveFiltersDisplay();
// }

// function clearAllFilters() {
//     currentFilters = {
//         location: '',
//         propertyType: '',
//         budget: '',
//         bedrooms: '',
//         listingType: ''
//     };

//     document.getElementById('searchLocation').value = '';
//     document.getElementById('searchType').value = '';
//     document.getElementById('searchBudget').value = '';

//     document.querySelectorAll('.filter-chip').forEach(chip => {
//         chip.classList.remove('active');
//     });

//     updateActiveFiltersDisplay();
//     showToast('✨ All filters cleared', 'success');
// }

// // Perform Search
// function performSearch() {
//     // Collect current filters
//     currentFilters.location = document.getElementById('searchLocation')?.value || '';
//     currentFilters.propertyType = document.getElementById('searchType')?.value || '';
//     currentFilters.budget = document.getElementById('searchBudget')?.value || '';

//     // Collect active chips
//     let bedrooms = '';
//     let listingType = '';

//     document.querySelectorAll('.filter-chip[data-bedrooms].active').forEach(chip => {
//         bedrooms = chip.getAttribute('data-bedrooms');
//     });

//     document.querySelectorAll('.filter-chip[data-listing].active').forEach(chip => {
//         listingType = chip.getAttribute('data-listing');
//     });

//     currentFilters.bedrooms = bedrooms;
//     currentFilters.listingType = listingType;

//     updateActiveFiltersDisplay();

//     // Build search URL
//     const params = new URLSearchParams();

//     if (currentFilters.location) params.append('location', currentFilters.location);
//     if (currentFilters.propertyType) params.append('type', currentFilters.propertyType);
//     if (currentFilters.budget) params.append('budget', currentFilters.budget);
//     if (currentFilters.bedrooms) params.append('bedrooms', currentFilters.bedrooms);
//     if (currentFilters.listingType) params.append('listing_type', currentFilters.listingType);

//     window.location.href = `/properties?${params.toString()}`;
// }

// // Near Me functionality
// function getCurrentLocationAndSearch() {
//     if (!navigator.geolocation) {
//         showToast('Geolocation not supported', 'error');
//         return;
//     }

//     const btn = document.getElementById('nearMeBtn');
//     const originalText = btn.innerHTML;
//     btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Getting location...';
//     btn.disabled = true;

//     navigator.geolocation.getCurrentPosition(async function(position) {
//         try {
//             const response = await fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${position.coords.latitude}&lon=${position.coords.longitude}&zoom=14`);
//             const data = await response.json();
//             const city = data.address?.city || data.address?.town || data.address?.village;

//             if (city) {
//                 document.getElementById('searchLocation').value = city;
//                 currentFilters.location = city;
//                 updateActiveFiltersDisplay();
//                 performSearch();
//             } else {
//                 showToast('Could not detect your city', 'warning');
//             }
//         } catch (error) {
//             console.error('Location error:', error);
//             showToast('Error detecting location', 'error');
//         }

//         btn.innerHTML = originalText;
//         btn.disabled = false;
//     }, function(error) {
//         showToast('Unable to get your location. Please enable location services.', 'error');
//         btn.innerHTML = originalText;
//         btn.disabled = false;
//     });
// }


// // ========== COMPLETE WORKING SEARCH FUNCTIONS ==========

// // Toggle advanced filters panel
// function toggleAdvancedFilters() {
//   const panel = document.getElementById('advancedFilters');
//   if (panel) {
//     const isVisible = panel.style.display === 'block';
//     panel.style.display = isVisible ? 'none' : 'block';
//   }
// }

// // Clear all filters
// // Clear all filters
// function clearAllFilters() {
//   // Clear main search inputs
//   const searchLocation = document.getElementById('searchLocation');
//   const searchType = document.getElementById('searchType');
//   const searchBudget = document.getElementById('searchBudget');

//   if (searchLocation) searchLocation.value = '';
//   if (searchType) searchType.value = '';
//   if (searchBudget) searchBudget.value = '';

//   // Clear advanced inputs
//   const minPrice = document.getElementById('minPrice');
//   const maxPrice = document.getElementById('maxPrice');
//   const minArea = document.getElementById('minArea');
//   const maxArea = document.getElementById('maxArea');

//   if (minPrice) minPrice.value = '';
//   if (maxPrice) maxPrice.value = '';
//   if (minArea) minArea.value = '';
//   if (maxArea) maxArea.value = '';

//   // Clear all checkboxes
//   document.querySelectorAll('.filter-checkbox').forEach(cb => cb.checked = false);

//   // Update display
//   updateActiveFiltersDisplay();

//   // Show success message
//   showToast('All filters cleared!', 'success');
// }


// // Update active filters display
// // Update active filters display
// function updateActiveFiltersDisplay() {
//   const activeBar = document.getElementById('activeFiltersBar');
//   const activeList = document.getElementById('activeFiltersList');
//   const filters = [];

//   // Location filter
//   const location = document.getElementById('searchLocation')?.value.trim();
//   if (location) filters.push({ type: 'location', label: `📍 ${location}` });

//   // Property type filter
//   const type = document.getElementById('searchType')?.value;
//   if (type && type !== '') filters.push({ type: 'type', label: `🏢 ${type}` });

//   // Budget filter
//   const budget = document.getElementById('searchBudget')?.value;
//   if (budget && budget !== '') {
//     const budgetLabels = {
//       'rent-0-5k': '💰 Under ₹5k/mo (PG)',
//       'rent-5-10k': '💰 ₹5k - ₹10k/mo',
//       'rent-10-15k': '💰 ₹10k - ₹15k/mo',
//       'rent-15-20k': '💰 ₹15k - ₹20k/mo',
//       'rent-20-30k': '💰 ₹20k - ₹30k/mo',
//       'rent-30-40k': '💰 ₹30k - ₹40k/mo',
//       'rent-40-50k': '💰 ₹40k - ₹50k/mo',
//       'rent-50k+': '💰 ₹50k+/mo',
//       'buy-0-10l': '💰 Under ₹10L',
//       'buy-10-20l': '💰 ₹10L - ₹20L',
//       'buy-20-30l': '💰 ₹20L - ₹30L',
//       'buy-30-50l': '💰 ₹30L - ₹50L',
//       'buy-50-80l': '💰 ₹50L - ₹80L',
//       'buy-80l-1cr': '💰 ₹80L - ₹1Cr',
//       'buy-1cr-2cr': '💰 ₹1Cr - ₹2Cr',
//       'buy-2cr-3cr': '💰 ₹2Cr - ₹3Cr',
//       'buy-3cr+': '💰 ₹3Cr+'
//     };
//     filters.push({ type: 'budget', label: budgetLabels[budget] || budget });
//   }

//   // Price range
//   const minPrice = document.getElementById('minPrice')?.value;
//   const maxPrice = document.getElementById('maxPrice')?.value;
//   if (minPrice || maxPrice) {
//     let priceLabel = '💰 Price: ';
//     if (minPrice) priceLabel += `₹${formatNumber(minPrice)}`;
//     if (minPrice && maxPrice) priceLabel += ' - ';
//     if (maxPrice) priceLabel += `₹${formatNumber(maxPrice)}`;
//     filters.push({ type: 'price', label: priceLabel });
//   }

//   // Area range
//   const minArea = document.getElementById('minArea')?.value;
//   const maxArea = document.getElementById('maxArea')?.value;
//   if (minArea || maxArea) {
//     let areaLabel = '📐 Area: ';
//     if (minArea) areaLabel += `${minArea} sqft`;
//     if (minArea && maxArea) areaLabel += ' - ';
//     if (maxArea) areaLabel += `${maxArea} sqft`;
//     filters.push({ type: 'area', label: areaLabel });
//   }

//   // Bedrooms
//   document.querySelectorAll('.filter-checkbox[data-filter="bedrooms"]:checked').forEach(cb => {
//     filters.push({ type: 'bedrooms', value: cb.value, label: `🛏️ ${cb.value}` });
//   });

//   // Category
//   document.querySelectorAll('.filter-checkbox[data-filter="category"]:checked').forEach(cb => {
//     const shortCat = cb.value.split('/')[0];
//     filters.push({ type: 'category', value: cb.value, label: `🏠 ${shortCat}` });
//   });

//   if (filters.length > 0 && activeBar && activeList) {
//     activeBar.style.display = 'block';
//     activeList.innerHTML = filters.map(filter => `
//             <span class="filter-tag">
//                 ${filter.label}
//                 <span class="remove-tag" onclick="removeFilter('${filter.type}', '${filter.value || ''}')">
//                     <i class="fa-solid fa-times"></i>
//                 </span>
//             </span>
//         `).join('');
//   } else if (activeBar) {
//     activeBar.style.display = 'none';
//   }
// }

// // Helper function to format numbers
// function formatNumber(num) {
//   if (num >= 10000000) return (num / 10000000).toFixed(1) + 'Cr';
//   if (num >= 100000) return (num / 100000).toFixed(0) + 'L';
//   if (num >= 1000) return (num / 1000).toFixed(0) + 'k';
//   return num;
// }

// // Remove individual filter
// function removeFilter(type, value) {
//   switch (type) {
//     case 'location':
//       document.getElementById('searchLocation').value = '';
//       break;
//     case 'type':
//       document.getElementById('searchType').value = '';
//       break;
//     case 'budget':
//       document.getElementById('searchBudget').value = '';
//       break;
//     case 'price':
//       document.getElementById('minPrice').value = '';
//       document.getElementById('maxPrice').value = '';
//       break;
//     case 'area':
//       document.getElementById('minArea').value = '';
//       document.getElementById('maxArea').value = '';
//       break;
//     case 'bedrooms':
//       document.querySelectorAll(`.filter-checkbox[data-filter="bedrooms"][value="${value}"]`).forEach(cb => cb.checked = false);
//       break;
//     case 'category':
//       document.querySelectorAll(`.filter-checkbox[data-filter="category"][value="${value}"]`).forEach(cb => cb.checked = false);
//       break;
//   }
//   updateActiveFiltersDisplay();
//   performSearch();
// }

// // Remove individual filter
// function removeFilter(type, value) {
//   switch (type) {
//     case 'location':
//       document.getElementById('searchLocation').value = '';
//       break;
//     case 'type':
//       document.getElementById('searchType').value = '';
//       break;
//     case 'budget':
//       document.getElementById('searchBudget').value = '';
//       break;
//     case 'price':
//       document.getElementById('minPrice').value = '';
//       document.getElementById('maxPrice').value = '';
//       break;
//     case 'area':
//       document.getElementById('minArea').value = '';
//       document.getElementById('maxArea').value = '';
//       break;
//     case 'bedrooms':
//       document.querySelectorAll(`.filter-checkbox[data-filter="bedrooms"][value="${value}"]`).forEach(cb => cb.checked = false);
//       break;
//     case 'category':
//       document.querySelectorAll(`.filter-checkbox[data-filter="category"][value="${value}"]`).forEach(cb => cb.checked = false);
//       break;
//   }
//   updateActiveFiltersDisplay();
//   performSearch();
// }

// // Format currency
// function formatCurrency(amount) {
//   if (amount >= 10000000) return (amount / 10000000).toFixed(1) + 'Cr';
//   if (amount >= 100000) return (amount / 100000).toFixed(0) + 'L';
//   if (amount >= 1000) return (amount / 1000).toFixed(0) + 'k';
//   return amount;
// }

// // Main search function
// function performSearch() {
//   const params = new URLSearchParams();

//   // Main search filters
//   const location = document.getElementById('searchLocation')?.value.trim();
//   const type = document.getElementById('searchType')?.value;
//   const budget = document.getElementById('searchBudget')?.value;

//   if (location) params.append('location', location);
//   if (type && type !== '') params.append('type', type);
//   if (budget && budget !== '') params.append('budget', budget);

//   // Advanced filters
//   const minPrice = document.getElementById('minPrice')?.value;
//   const maxPrice = document.getElementById('maxPrice')?.value;
//   const minArea = document.getElementById('minArea')?.value;
//   const maxArea = document.getElementById('maxArea')?.value;

//   if (minPrice) params.append('min_price', minPrice);
//   if (maxPrice) params.append('max_price', maxPrice);
//   if (minArea) params.append('min_area', minArea);
//   if (maxArea) params.append('max_area', maxArea);

//   // Bedrooms
//   const bedrooms = [];
//   document.querySelectorAll('.filter-checkbox[data-filter="bedrooms"]:checked').forEach(cb => {
//     bedrooms.push(cb.value);
//   });
//   if (bedrooms.length) params.append('bedrooms', bedrooms.join(','));

//   // Categories
//   const categories = [];
//   document.querySelectorAll('.filter-checkbox[data-filter="category"]:checked').forEach(cb => {
//     categories.push(cb.value);
//   });
//   if (categories.length) params.append('category', categories.join(','));

//   window.location.href = `/properties?${params.toString()}`;
// }

// ========== COMPLETE WORKING SEARCH FUNCTIONS ==========

// DOM Elements
const mainSearchBtn = document.getElementById('mainSearchBtn');
const filterToggleBtn = document.getElementById('filterToggleBtn');
const applyFiltersBtn = document.getElementById('applyFiltersBtn');
const resetFiltersBtn = document.getElementById('resetFiltersBtn');
const clearAllFiltersBtn = document.getElementById('clearAllFiltersBtn');
const advancedFiltersPanel = document.getElementById('advancedFiltersPanel');

// Set price range from quick buttons
function setPriceRange(min, max) {
  const minInput = document.getElementById('minPriceMain');
  const maxInput = document.getElementById('maxPriceMain');
  if (minInput) minInput.value = min || '';
  if (maxInput) maxInput.value = max || '';
  updateActiveFiltersDisplay();
  // Auto search after price selection
}

// Toggle advanced filters panel
function toggleAdvancedFilters() {
  if (advancedFiltersPanel) {
    const isVisible = advancedFiltersPanel.style.display === 'block';
    advancedFiltersPanel.style.display = isVisible ? 'none' : 'block';
    if (filterToggleBtn) {
      filterToggleBtn.innerHTML = isVisible ? '<i class="fa-solid fa-sliders-h"></i>' : '<i class="fa-solid fa-times"></i>';
    }
  }
}

// Update active filters display
function updateActiveFiltersDisplay() {
  const activeBar = document.getElementById('activeFiltersBar');
  const activeList = document.getElementById('activeFiltersList');
  const filters = [];

  // Location
  const location = document.getElementById('searchLocation')?.value.trim();
  if (location) filters.push({ type: 'location', label: `📍 ${location}` });

  // Property Type
  const type = document.getElementById('searchType')?.value;
  if (type && type !== '') filters.push({ type: 'type', label: `🏢 ${type}` });

  // Price Range
  const minPrice = document.getElementById('minPriceMain')?.value;
  const maxPrice = document.getElementById('maxPriceMain')?.value;
  if (minPrice || maxPrice) {
    let priceLabel = '💰 Price: ';
    if (minPrice) priceLabel += `₹${formatNumber(parseInt(minPrice))}`;
    if (minPrice && maxPrice) priceLabel += ' - ';
    if (maxPrice) priceLabel += `₹${formatNumber(parseInt(maxPrice))}`;
    filters.push({ type: 'price', label: priceLabel });
  }

  // Area
  const minArea = document.getElementById('minArea')?.value;
  const maxArea = document.getElementById('maxArea')?.value;
  if (minArea || maxArea) {
    let areaLabel = '📐 Area: ';
    if (minArea) areaLabel += `${minArea} sqft`;
    if (minArea && maxArea) areaLabel += ' - ';
    if (maxArea) areaLabel += `${maxArea} sqft`;
    filters.push({ type: 'area', label: areaLabel });
  }

  // Bedrooms
  document.querySelectorAll('.filter-checkbox[data-filter="bedrooms"]:checked').forEach(cb => {
    filters.push({ type: 'bedrooms', value: cb.value, label: `🛏️ ${cb.value}` });
  });

  // Category
  document.querySelectorAll('.filter-checkbox[data-filter="category"]:checked').forEach(cb => {
    const shortCat = cb.value.split('/')[0];
    filters.push({ type: 'category', value: cb.value, label: `🏠 ${shortCat}` });
  });

  // Listing Type
  document.querySelectorAll('.filter-checkbox[data-filter="listing_type"]:checked').forEach(cb => {
    filters.push({ type: 'listing', value: cb.value, label: `🏷️ ${cb.value}` });
  });

  if (filters.length > 0 && activeBar && activeList) {
    activeBar.style.display = 'block';
    activeList.innerHTML = filters.map(filter => `
            <span class="filter-tag">
                ${filter.label}
                <span class="remove-tag" onclick="removeFilter('${filter.type}', '${filter.value || ''}')">
                    <i class="fa-solid fa-times"></i>
                </span>
            </span>
        `).join('');
  } else if (activeBar) {
    activeBar.style.display = 'none';
  }
}

// Format numbers for display
function formatNumber(num) {
  if (num >= 10000000) return (num / 10000000).toFixed(1) + 'Cr';
  if (num >= 100000) return (num / 100000).toFixed(0) + 'L';
  if (num >= 1000) return (num / 1000).toFixed(0) + 'k';
  return num.toString();
}

// Remove individual filter
function removeFilter(type, value) {
  switch (type) {
    case 'location':
      document.getElementById('searchLocation').value = '';
      break;
    case 'type':
      document.getElementById('searchType').value = '';
      break;
    case 'price':
      document.getElementById('minPriceMain').value = '';
      document.getElementById('maxPriceMain').value = '';
      break;
    case 'area':
      document.getElementById('minArea').value = '';
      document.getElementById('maxArea').value = '';
      break;
    case 'bedrooms':
      document.querySelectorAll(`.filter-checkbox[data-filter="bedrooms"][value="${value}"]`).forEach(cb => cb.checked = false);
      break;
    case 'category':
      document.querySelectorAll(`.filter-checkbox[data-filter="category"][value="${value}"]`).forEach(cb => cb.checked = false);
      break;
    case 'listing':
      document.querySelectorAll(`.filter-checkbox[data-filter="listing_type"][value="${value}"]`).forEach(cb => cb.checked = false);
      break;
  }
  updateActiveFiltersDisplay();
  performSearch();
}

// Clear all filters
function clearAllFilters() {
  document.getElementById('searchLocation').value = '';
  document.getElementById('searchType').value = '';
  document.getElementById('minPriceMain').value = '';
  document.getElementById('maxPriceMain').value = '';
  document.getElementById('minArea').value = '';
  document.getElementById('maxArea').value = '';

  document.querySelectorAll('.filter-checkbox').forEach(cb => cb.checked = false);
  // document.querySelectorAll('.filter-checkbox[data-filter="listing_type"][value="For Sale"]').forEach(cb => cb.checked = true);

  updateActiveFiltersDisplay();
  showToast('All filters cleared!', 'success');
}

// Main search function - USES ALL FILTERS
function performSearch() {
  const params = new URLSearchParams();

  // 1. Location
  const location = document.getElementById('searchLocation')?.value.trim();
  if (location) params.append('location', location);

  // 2. Property Type
  const type = document.getElementById('searchType')?.value;
  if (type && type !== '') params.append('type', type);

  // 3. Price Range
  const minPrice = document.getElementById('minPriceMain')?.value;
  const maxPrice = document.getElementById('maxPriceMain')?.value;
  if (minPrice) params.append('min_price', minPrice);
  if (maxPrice) params.append('max_price', maxPrice);

  // 4. Area
  const minArea = document.getElementById('minArea')?.value;
  const maxArea = document.getElementById('maxArea')?.value;
  if (minArea) params.append('min_area', minArea);
  if (maxArea) params.append('max_area', maxArea);

  // 5. Bedrooms
  const bedrooms = [];
  document.querySelectorAll('.filter-checkbox[data-filter="bedrooms"]:checked').forEach(cb => {
    bedrooms.push(cb.value);
  });
  if (bedrooms.length) params.append('bedrooms', bedrooms.join(','));

  // 6. Category
  const categories = [];
  document.querySelectorAll('.filter-checkbox[data-filter="category"]:checked').forEach(cb => {
    categories.push(cb.value);
  });
  if (categories.length) params.append('category', categories.join(','));

  // 7. Listing Type
  const listingTypes = [];
  document.querySelectorAll('.filter-checkbox[data-filter="listing_type"]:checked').forEach(cb => {
    listingTypes.push(cb.value);
  });
  if (listingTypes.length) params.append('listing_type', listingTypes.join(','));

  // Close advanced panel
  if (advancedFiltersPanel) advancedFiltersPanel.style.display = 'none';
  if (filterToggleBtn) filterToggleBtn.innerHTML = '<i class="fa-solid fa-sliders-h"></i>';

  window.location.href = `/properties?${params.toString()}`;
}

// Initialize all event listeners
document.addEventListener('DOMContentLoaded', function () {
  // Search button
  if (mainSearchBtn) mainSearchBtn.addEventListener('click', performSearch);

  // Apply filters button
  // if (applyFiltersBtn) applyFiltersBtn.addEventListener('click', performSearch);
  // Apply filters button - Just closes panel, NO search
  if (applyFiltersBtn) applyFiltersBtn.addEventListener('click', applyFiltersAndClose);

  // Reset filters button
  if (resetFiltersBtn) resetFiltersBtn.addEventListener('click', clearAllFilters);

  // Clear all button
  if (clearAllFiltersBtn) clearAllFiltersBtn.addEventListener('click', clearAllFilters);

  // Filter toggle button
  if (filterToggleBtn) filterToggleBtn.addEventListener('click', toggleAdvancedFilters);

  // Quick price buttons
  document.querySelectorAll('.price-quick').forEach(btn => {
    btn.addEventListener('click', function () {
      const min = this.getAttribute('data-min');
      const max = this.getAttribute('data-max');
      setPriceRange(min, max);
    });
  });

  // Auto update display on filter changes
  const filterInputs = ['searchLocation', 'searchType', 'minPriceMain', 'maxPriceMain', 'minArea', 'maxArea'];
  filterInputs.forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('input', updateActiveFiltersDisplay);
    if (el && el.tagName === 'SELECT') el.addEventListener('change', updateActiveFiltersDisplay);
  });

  document.querySelectorAll('.filter-checkbox').forEach(cb => {
    cb.addEventListener('change', updateActiveFiltersDisplay);
  });

  // Enter key on location input
  const locationInput = document.getElementById('searchLocation');
  if (locationInput) {
    locationInput.addEventListener('keypress', function (e) {
      if (e.key === 'Enter') performSearch();
    });
  }

  updateActiveFiltersDisplay();
});


// Apply Filters - Just closes panel, does NOT search
function applyFiltersAndClose() {
  const panel = document.getElementById('advancedFiltersPanel');
  const btn = document.getElementById('filterToggleBtn');

  if (panel) panel.style.display = 'none';
  if (btn) btn.innerHTML = '<i class="fa-solid fa-sliders-h"></i>';

  // Just update the display, don't search
  updateActiveFiltersDisplay();

  // Change the color - use 'info', 'warning', 'success', or 'error'
  showToast('Filters applied! Click Search to find properties.', 'info');
}

// Show toast function (if not already exists)
function showToast(message, type = 'info') {
  let container = document.getElementById('toastContainer');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toastContainer';
    container.style.cssText = 'position: fixed; bottom: 20px; right: 20px; z-index: 9999;';
    document.body.appendChild(container);
  }

  const toast = document.createElement('div');
  toast.className = `toast align-items-center text-white bg-${type === 'success' ? 'success' : 'danger'} border-0`;
  toast.setAttribute('role', 'alert');
  toast.style.marginTop = '10px';
  toast.style.minWidth = '250px';
  toast.style.animation = 'slideInRight 0.3s ease';
  toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">${message}</div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
    `;
  container.appendChild(toast);
  const bsToast = new bootstrap.Toast(toast, { delay: 3000 });
  bsToast.show();
  setTimeout(() => toast.remove(), 3500);
}

// Animation CSS
const styleSheet = document.createElement('style');
styleSheet.textContent = `
    @keyframes slideInRight {
        from { transform: translateX(100%); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
`;
document.head.appendChild(styleSheet);




// Near Me functionality
function getCurrentLocationAndSearch() {
  if (!navigator.geolocation) {
    showToast('Geolocation not supported', 'error');
    return;
  }

  const btn = document.getElementById('nearMeBtn');
  if (!btn) return;

  const originalText = btn.innerHTML;
  btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Getting...';
  btn.disabled = true;

  navigator.geolocation.getCurrentPosition(async function (position) {
    try {
      const response = await fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${position.coords.latitude}&lon=${position.coords.longitude}&zoom=14`);
      const data = await response.json();
      const city = data.address?.city || data.address?.town || data.address?.village || data.address?.suburb;

      if (city) {
        const locationInput = document.getElementById('searchLocation');
        if (locationInput) {
          locationInput.value = city;
          showToast(`📍 Location set to: ${city}`, 'success');
          performSearch();
        }
      } else {
        showToast('Could not detect your city. Please enter manually.', 'warning');
      }
    } catch (error) {
      console.error('Location error:', error);
      showToast('Error detecting location', 'error');
    }

    btn.innerHTML = originalText;
    btn.disabled = false;
  }, function (error) {
    let errorMsg = 'Unable to get location. ';
    if (error.code === 1) errorMsg += 'Please allow location access.';
    else errorMsg += 'Please try again.';
    showToast(errorMsg, 'error');
    btn.innerHTML = originalText;
    btn.disabled = false;
  });
}

// Add event listeners for filter changes
document.addEventListener('DOMContentLoaded', function () {
  // Search button
  const searchBtn = document.querySelector('.btn-search-main');
  if (searchBtn) searchBtn.addEventListener('click', performSearch);

  // Apply filters button
  const applyBtn = document.querySelector('.btn-primary');
  if (applyBtn) applyBtn.addEventListener('click', performSearch);

  // Reset button
  const resetBtn = document.querySelector('.btn-secondary');
  if (resetBtn) resetBtn.addEventListener('click', clearAllFilters);

  // Near Me button
  const nearMeBtn = document.getElementById('nearMeBtn');
  if (nearMeBtn) nearMeBtn.addEventListener('click', getCurrentLocationAndSearch);

  // Auto update active filters when any filter changes
  const filterInputs = [
    'searchLocation', 'searchType', 'searchBudget',
    'minPrice', 'maxPrice', 'minArea', 'maxArea'
  ];
  filterInputs.forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('input', updateActiveFiltersDisplay);
    if (el && el.tagName === 'SELECT') el.addEventListener('change', updateActiveFiltersDisplay);
  });

  document.querySelectorAll('.filter-checkbox').forEach(cb => {
    cb.addEventListener('change', updateActiveFiltersDisplay);
  });

  // Enter key on location input
  const locationInput = document.getElementById('searchLocation');
  if (locationInput) {
    locationInput.addEventListener('keypress', function (e) {
      if (e.key === 'Enter') performSearch();
    });
  }

  // Initial update
  updateActiveFiltersDisplay();
});

// ========== IMPROVED LOCATION AUTOCOMPLETE ==========

let searchTimeout2 = null;
const locationInput2 = document.getElementById('searchLocation');
const suggestionsBox2 = document.getElementById('locationSuggestions');

// Location mapping - Converts API names to database-friendly names
function normalizeLocationName(apiLocationName) {
  const lowerName = apiLocationName.toLowerCase();

  // Mapping for Mohali (Sahibzada Ajit Singh Nagar -> Mohali)
  if (lowerName.includes('sahibzada ajit singh nagar') ||
    lowerName.includes('sas nagar') ||
    lowerName.includes('ajit nagar')) {
    return 'Mohali';
  }

  // Mapping for Chandigarh
  if (lowerName.includes('chandigarh')) {
    return 'Chandigarh';
  }

  // Mapping for Panchkula
  if (lowerName.includes('panchkula')) {
    return 'Panchkula';
  }

  // Mapping for Kharar
  if (lowerName.includes('kharar')) {
    return 'Kharar';
  }

  // Mapping for Zirakpur
  if (lowerName.includes('zirakpur')) {
    return 'Zirakpur';
  }

  // Extract the main city name (first part before comma)
  const mainName = apiLocationName.split(',')[0].trim();

  // Remove common suffixes like sector numbers
  let cleaned = mainName
    .replace(/sector \d+/i, '')
    .replace(/phase \d+/i, '')
    .replace(/ward \d+/i, '')
    .trim();

  return cleaned || mainName;
}

// Location suggestion selection - Converts to database-friendly name
window.selectLocationSuggestion = function (locationName, originalQuery) {
  console.log('Selected location API name:', locationName);

  const inputField = document.getElementById('searchLocation');
  if (inputField) {
    // Convert to database-friendly name
    const dbFriendlyName = normalizeLocationName(locationName);
    inputField.value = dbFriendlyName;
    console.log('Set input to (DB friendly):', dbFriendlyName);
  }

  if (suggestionsBox2) {
    suggestionsBox2.style.display = 'none';
  }

  if (typeof updateActiveFiltersDisplay === 'function') {
    updateActiveFiltersDisplay();
  }
};

// Fetch location suggestions
async function fetchLocationSuggestions2(query) {
  if (!query || query.length < 2) {
    if (suggestionsBox2) suggestionsBox2.style.display = 'none';
    return;
  }

  if (suggestionsBox2) {
    suggestionsBox2.innerHTML = `
            <div class="suggestion-loading">
                <i class="fa-solid fa-spinner fa-spin"></i> Searching locations...
            </div>
        `;
    suggestionsBox2.style.display = 'block';
  }

  try {
    const response = await fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(query)}&limit=6&addressdetails=1&countrycodes=in&accept-language=en`);
    const data = await response.json();

    if (data && data.length > 0 && suggestionsBox2) {
      suggestionsBox2.innerHTML = data.map(place => {
        const fullName = place.display_name;
        const mainName = fullName.split(',')[0];
        const dbName = normalizeLocationName(fullName);

        let icon = 'fa-solid fa-location-dot';
        if (place.type === 'city') icon = 'fa-solid fa-city';
        else if (place.type === 'town') icon = 'fa-solid fa-town';
        else if (place.type === 'village') icon = 'fa-solid fa-tree';

        const willSearchAs = (dbName !== mainName) ? ` → Will search: "${dbName}"` : '';

        return `
                    <div class="suggestion-item" onclick="selectLocationSuggestion('${fullName.replace(/'/g, "\\'")}', '${query.replace(/'/g, "\\'")}')">
                        <div class="suggestion-icon">
                            <i class="${icon}"></i>
                        </div>
                        <div class="suggestion-text">
                            <div class="suggestion-main">${mainName}</div>
                            <div class="suggestion-sub" style="font-size: 11px; color: #C9A84C;">
                                <i class="fa-solid fa-magnifying-glass"></i> ${willSearchAs || 'Click to select'}
                            </div>
                        </div>
                    </div>
                `;
      }).join('');
    } else if (suggestionsBox2) {
      suggestionsBox2.innerHTML = `
                <div class="suggestion-item" style="justify-content: center; color: #999;">
                    <i class="fa-solid fa-map-marker-alt"></i>
                    <span>No locations found. Try a different search.</span>
                </div>
            `;
    }
  } catch (error) {
    console.error('Error fetching suggestions:', error);
    if (suggestionsBox2) {
      suggestionsBox2.innerHTML = `
                <div class="suggestion-item" style="justify-content: center; color: #e74c3c;">
                    <i class="fa-solid fa-exclamation-triangle"></i>
                    <span>Error loading suggestions</span>
                </div>
            `;
    }
  }
}

// Initialize autocomplete
if (locationInput2) {
  locationInput2.addEventListener('input', function (e) {
    if (searchTimeout2) clearTimeout(searchTimeout2);
    const query = e.target.value.trim();

    if (query.length >= 2) {
      searchTimeout2 = setTimeout(() => {
        fetchLocationSuggestions2(query);
      }, 400);
    } else {
      if (suggestionsBox2) suggestionsBox2.style.display = 'none';
    }
  });

  document.addEventListener('click', function (e) {
    if (suggestionsBox2 &&
      !locationInput2.contains(e.target) &&
      !suggestionsBox2.contains(e.target)) {
      suggestionsBox2.style.display = 'none';
    }
  });

  // Escape key closes dropdown
  locationInput2.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      if (suggestionsBox2) suggestionsBox2.style.display = 'none';
    }
  });
}

// Add CSS for active filters if missing
const filterStyles = document.createElement('style');
filterStyles.textContent = `
    .filter-tag {
        background: white;
        border: 1px solid #C9A84C;
        border-radius: 20px;
        padding: 5px 12px;
        font-size: 0.7rem;
        display: inline-flex;
        align-items: center;
        gap: 8px;
        color: #0B1F3A;
    }
    .filter-tag .remove-tag {
        cursor: pointer;
        color: #999;
    }
    .filter-tag .remove-tag:hover {
        color: #e74c3c;
    }
    .active-filters-bar {
        background: #F8F6F0;
        border-radius: 12px;
        padding: 12px 16px;
        margin-top: 1rem;
    }
    .active-filters-header {
        display: flex;
        justify-content: space-between;
        margin-bottom: 10px;
        font-size: 0.75rem;
        font-weight: 600;
    }
    .active-filters-list {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
    }
`;
document.head.appendChild(filterStyles);

// ========== CONTACT FORM FIXES ==========

// Check if user is logged in
function isUserLoggedIn() {
  return document.querySelector('.dropdown') !== null ||
    document.querySelector('a[href*="logout"]') !== null;
}

// Auto-fill contact form if user is logged in
async function autoFillContactForm() {
  if (!isUserLoggedIn()) return;
  try {
    const response = await fetch('/api/current-user');
    if (response.ok) {
      const user = await response.json();
      if (user.success) {
        const nameField = document.getElementById('contact_name');
        const emailField = document.getElementById('contact_email');
        const phoneField = document.getElementById('contact_phone');
        if (nameField && user.name) nameField.value = user.name;
        if (emailField && user.email) emailField.value = user.email;
        if (phoneField && user.phone) phoneField.value = user.phone;
      }
    }
  } catch (error) {
    console.error('Error fetching user:', error);
  }
}

function loadPropertyInquiry() {
  const savedProperty = localStorage.getItem('inquiryProperty');
  console.log('=== LOAD PROPERTY INQUIRY ===');
  console.log('Raw saved property:', savedProperty);

  if (savedProperty) {
    try {
      const property = JSON.parse(savedProperty);
      console.log('Parsed property:', property);

      // Find the hidden input fields
      const propertyIdField = document.querySelector('input[name="property_id"]');
      const propertyNameField = document.querySelector('input[name="property_name"]');
      const brokerIdField = document.querySelector('input[name="broker_id"]');
      const messageField = document.getElementById('contact_message');

      console.log('Found fields:', {
        propertyIdField: !!propertyIdField,
        propertyNameField: !!propertyNameField,
        brokerIdField: !!brokerIdField,
        messageField: !!messageField
      });

      if (propertyIdField && property.id) {
        propertyIdField.value = property.id;
        console.log('✅ Set property_id to:', property.id);
      } else {
        console.log('❌ Failed to set property_id');
      }

      if (propertyNameField && property.name) {
        propertyNameField.value = property.name;
        console.log('✅ Set property_name to:', property.name);
      } else {
        console.log('❌ Failed to set property_name');
      }

      if (brokerIdField && property.broker_id) {
        brokerIdField.value = property.broker_id;
        console.log('✅ Set broker_id to:', property.broker_id);
      } else {
        console.log('❌ Failed to set broker_id. broker_id value:', property.broker_id);
      }

      if (messageField && property.name) {
        messageField.value = `I'm interested in "${property.name}". Please share more details.`;
        console.log('✅ Set message');
      }

      // Don't remove immediately - keep for debugging
      // localStorage.removeItem('inquiryProperty');

    } catch (error) {
      console.error('Error parsing property:', error);
    }
  } else {
    console.log('No saved property inquiry found');
  }
}



// Handle contact form submission with login check
let isSubmitting = false;

const contactFormElement = document.getElementById('contactForm');
if (contactFormElement) {
  contactFormElement.addEventListener('submit', async function (e) {
    e.preventDefault();

    // Prevent multiple submissions
    if (isSubmitting) {
      console.log('Form already submitting, ignoring...');
      return;
    }

    // Check if user is logged in
    if (!isUserLoggedIn()) {
      Swal.fire({
        icon: 'warning',
        title: 'Login Required',
        text: 'Please login to send inquiry.',
        showCancelButton: true,
        confirmButtonText: 'Login Now',
        cancelButtonText: 'Cancel'
      }).then((result) => {
        if (result.isConfirmed) {
          // Store current form data before redirect
          const formData = new FormData(contactFormElement);
          localStorage.setItem('pendingFormData', JSON.stringify(Object.fromEntries(formData)));
          window.location.href = '/signin?next=' + encodeURIComponent(window.location.pathname);
        }
      });
      return;
    }

    // Set submitting flag
    isSubmitting = true;

    const submitBtn = document.getElementById('contactSubmitBtn');
    const originalText = submitBtn.innerHTML;

    // Change button to loading state
    submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin me-2"></i>Sending...';
    submitBtn.disabled = true;

    try {
      const formData = new FormData(contactFormElement);
      const response = await fetch('/contact', {
        method: 'POST',
        body: formData
      });
      const result = await response.json();

      if (result.success) {
        // Show success message
        await Swal.fire({
          icon: 'success',
          title: 'Message Sent!',
          text: 'Our team will contact you shortly.',
          confirmButtonColor: '#C9A84C',
          timer: 2000,
          showConfirmButton: true
        });

        // Reset form BUT preserve user details
        const currentName = document.getElementById('contact_name')?.value;
        const currentEmail = document.getElementById('contact_email')?.value;
        const currentPhone = document.getElementById('contact_phone')?.value;

        // Clear only message and looking_for fields
        const messageField = document.getElementById('contact_message');
        const lookingForField = document.getElementById('contact_looking_for');

        if (messageField) messageField.value = '';
        if (lookingForField) lookingForField.value = '';

        // Keep user details (don't clear name, email, phone)
        // Clear property hidden fields
        const propertyIdField = document.querySelector('input[name="property_id"]');
        const propertyNameField = document.querySelector('input[name="property_name"]');
        const brokerIdField = document.querySelector('input[name="broker_id"]');

        if (propertyIdField) propertyIdField.value = '';
        if (propertyNameField) propertyNameField.value = '';
        if (brokerIdField) brokerIdField.value = '';

        // Clear stored property inquiry
        localStorage.removeItem('inquiryProperty');

        // Reset button to original state
        submitBtn.innerHTML = originalText;
        submitBtn.disabled = false;

        // Small delay before allowing new submissions
        setTimeout(() => {
          isSubmitting = false;
        }, 1000);

      } else {
        throw new Error(result.message || 'Failed to send message');
      }
    } catch (error) {
      console.error('Form error:', error);
      await Swal.fire({
        icon: 'error',
        title: 'Error',
        text: error.message || 'Failed to send message. Please try again.',
        confirmButtonColor: '#C9A84C'
      });

      // Reset button on error
      submitBtn.innerHTML = originalText;
      submitBtn.disabled = false;
      isSubmitting = false;
    }
  });
}

// Initialize contact form on page load
document.addEventListener('DOMContentLoaded', function () {
  autoFillContactForm();
  loadPropertyInquiry();
});



// Contact form
function openContactFormFromProperty(agentName, propertyName, propertyId, brokerId) {
  console.log('=== Opening Contact Form ===');
  console.log('Property Name:', propertyName);
  console.log('Property ID:', propertyId);
  console.log('Broker ID:', brokerId);

  // Close any open modal
  const modal = bootstrap.Modal.getInstance(document.getElementById('propertyModal'));
  if (modal) {
    modal.hide();
  }

  // Remove any modal backdrops
  const backdrops = document.querySelectorAll('.modal-backdrop');
  backdrops.forEach(backdrop => backdrop.remove());
  document.body.classList.remove('modal-open');
  document.body.style.overflow = '';

  if (!isUserLoggedIn()) {
    Swal.fire({
      icon: 'warning',
      title: 'Login Required',
      text: 'Please login to send inquiry about this property.',
      showCancelButton: true,
      confirmButtonText: 'Login Now',
      cancelButtonText: 'Cancel'
    }).then((result) => {
      if (result.isConfirmed) {
        const propertyInfo = {
          id: propertyId,
          name: propertyName,
          broker_id: brokerId
        };
        localStorage.setItem('inquiryProperty', JSON.stringify(propertyInfo));
        window.location.href = '/signin?next=' + encodeURIComponent(window.location.pathname);
      }
    });
    return;
  }

  const propertyInfo = {
    id: propertyId,
    name: propertyName,
    broker_id: brokerId
  };
  localStorage.setItem('inquiryProperty', JSON.stringify(propertyInfo));
  console.log('Stored in localStorage:', propertyInfo);
  window.location.href = '/#contact';
}



// Fix any scroll blocking issues after modal closes
document.addEventListener('hidden.bs.modal', function () {
  document.body.style.overflow = '';
  document.body.classList.remove('modal-open');
  const backdrops = document.querySelectorAll('.modal-backdrop');
  backdrops.forEach(backdrop => backdrop.remove());
});