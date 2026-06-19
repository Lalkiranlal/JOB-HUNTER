// Global Application State
let jobsData = [];
let currentView = 'grid'; // 'grid' or 'list'
let activeJobId = null;
let eventSource = null;

function getSessionId() {
    let sid = localStorage.getItem('session_id');
    if (!sid) {
        sid = crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).substring(2, 15);
        localStorage.setItem('session_id', sid);
    }
    return sid;
}
const SESSION_ID = getSessionId();

// DOM Elements
const jobsGrid = document.getElementById('jobs-grid');
const jobsTableContainer = document.getElementById('jobs-table-container');
const jobsTableBody = document.getElementById('jobs-table-body');
const contentLoader = document.getElementById('content-loader');
const emptyState = document.getElementById('empty-state');

const searchInput = document.getElementById('search-input');
const filterCountry = document.getElementById('filter-country');
const filterSite = document.getElementById('filter-site');
const filterStatus = document.getElementById('filter-status');
const filterRemote = document.getElementById('filter-remote');

const viewGridBtn = document.getElementById('view-grid-btn');
const viewListBtn = document.getElementById('view-list-btn');

// Drawer elements - Scraper
const openScrapeBtn = document.getElementById('open-scrape-btn');
const emptyScrapeBtn = document.getElementById('empty-scrape-btn');
const scraperDrawer = document.getElementById('scraper-drawer');
const scraperDrawerOverlay = document.getElementById('scraper-drawer-overlay');
const closeScrapeDrawerBtn = document.getElementById('close-scrape-drawer-btn');
const cancelScrapeBtn = document.getElementById('cancel-scrape-btn');
const scraperForm = document.getElementById('scraper-form');
const scrapeBoards = document.getElementsByName('scrape-boards');
const indeedCountryWrapper = document.getElementById('indeed-country-wrapper');

// Drawer elements - Details
const detailsDrawer = document.getElementById('details-drawer');
const detailsDrawerOverlay = document.getElementById('details-drawer-overlay');
const closeDetailsBtn = document.getElementById('close-details-btn');
const detailTitle = document.getElementById('detail-title');
const detailCompany = document.getElementById('detail-company');
const detailLocation = document.getElementById('detail-location');
const detailJobType = document.getElementById('detail-job-type');
const detailDatePosted = document.getElementById('detail-date-posted');
const detailSalary = document.getElementById('detail-salary');
const detailBoardBadge = document.getElementById('detail-board-badge');
const detailStatus = document.getElementById('detail-status');
const detailDateApplied = document.getElementById('detail-date-applied');
const detailNotes = document.getElementById('detail-notes');
const detailDescription = document.getElementById('detail-description');
const detailApplyLink = document.getElementById('detail-apply-link');
const saveDetailsTrackerBtn = document.getElementById('save-details-tracker-btn');

// Terminal/Console
const scrapeConsole = document.getElementById('scrape-console');
const consoleLogs = document.getElementById('console-logs');
const closeConsoleBtn = document.getElementById('close-console-btn');

// Export Excel Button
const exportExcelBtn = document.getElementById('export-excel-btn');
const clearJobsBtn = document.getElementById('clear-jobs-btn');


// Initial setup on DOM Content Loaded
document.addEventListener('DOMContentLoaded', () => {
    loadStats();
    loadJobs();
    setupEventListeners();
});

// Event Listeners Setup
function setupEventListeners() {
    // Search input debouncer
    let debounceTimer;
    searchInput.addEventListener('input', () => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
            loadJobs();
        }, 300);
    });

    // Filtering
    if (filterCountry) filterCountry.addEventListener('change', loadJobs);
    filterSite.addEventListener('change', loadJobs);
    filterStatus.addEventListener('change', loadJobs);
    filterRemote.addEventListener('change', loadJobs);

    // View toggling
    viewGridBtn.addEventListener('click', () => {
        setView('grid');
    });
    viewListBtn.addEventListener('click', () => {
        setView('list');
    });

    // Scrape configuration drawer triggers
    openScrapeBtn.addEventListener('click', () => openDrawer(scraperDrawer));
    if (emptyScrapeBtn) {
        emptyScrapeBtn.addEventListener('click', () => openDrawer(scraperDrawer));
    }
    closeScrapeDrawerBtn.addEventListener('click', () => closeDrawer(scraperDrawer));
    scraperDrawerOverlay.addEventListener('click', () => closeDrawer(scraperDrawer));
    cancelScrapeBtn.addEventListener('click', () => closeDrawer(scraperDrawer));

    // Show/hide Indeed country based on Indeed checked status
    scrapeBoards.forEach(checkbox => {
        checkbox.addEventListener('change', () => {
            const indeedChecked = Array.from(scrapeBoards).some(cb => cb.value === 'indeed' && cb.checked);
            indeedCountryWrapper.style.display = indeedChecked ? 'flex' : 'none';
        });
    });

    // Scrape Form Submission
    scraperForm.addEventListener('submit', handleScrapeSubmit);

    // Terminal Close Trigger
    closeConsoleBtn.addEventListener('click', () => {
        scrapeConsole.classList.add('hidden');
    });

    // Export Excel Trigger
    exportExcelBtn.addEventListener('click', handleExportExcel);

    // Clear Jobs Trigger
    if (clearJobsBtn) {
        clearJobsBtn.addEventListener('click', handleClearJobs);
    }


    // Details Drawer overlay
    closeDetailsBtn.addEventListener('click', () => closeDrawer(detailsDrawer));
    detailsDrawerOverlay.addEventListener('click', () => closeDrawer(detailsDrawer));
    
    // Save details status tracker
    saveDetailsTrackerBtn.addEventListener('click', handleSaveDetailsTracker);
}

// Drawer Open/Close Helpers
function openDrawer(drawer) {
    drawer.classList.add('open');
}

function closeDrawer(drawer) {
    drawer.classList.remove('open');
}

// Set View layout (grid / list)
function setView(view) {
    currentView = view;
    if (view === 'grid') {
        viewGridBtn.classList.add('active');
        viewListBtn.classList.remove('active');
        jobsGrid.classList.remove('hidden');
        jobsTableContainer.classList.add('hidden');
    } else {
        viewGridBtn.classList.remove('active');
        viewListBtn.classList.add('active');
        jobsGrid.classList.add('hidden');
        jobsTableContainer.classList.remove('hidden');
    }
    renderJobs();
}

// Load statistics metrics
async function loadStats() {
    try {
        const res = await fetch('/api/stats', { headers: { 'X-Session-Id': SESSION_ID } });
        const stats = await res.json();
        
        document.getElementById('stat-total').innerText = stats.total || 0;
        document.getElementById('stat-remote').innerText = stats.remote || 0;
        document.getElementById('stat-applied').innerText = stats.applied || 0;
        document.getElementById('stat-interviewing').innerText = stats.interviewing || 0;
    } catch (err) {
        console.error("Error loading stats:", err);
    }
}

// Build query parameter URL
function getQueryString() {
    const params = new URLSearchParams();
    
    const searchVal = searchInput.value.trim();
    const countryVal = filterCountry ? filterCountry.value : '';
    const siteVal = filterSite.value;
    const statusVal = filterStatus.value;
    const remoteVal = filterRemote.value;
    
    if (searchVal) params.append('search', searchVal);
    if (countryVal) params.append('country', countryVal);
    if (siteVal) params.append('site', siteVal);
    if (statusVal) params.append('status', statusVal);
    if (remoteVal) params.append('is_remote', remoteVal);
    
    return params.toString();
}

// Load jobs from DB
async function loadJobs() {
    contentLoader.classList.remove('hidden');
    jobsGrid.classList.add('hidden');
    jobsTableContainer.classList.add('hidden');
    emptyState.classList.add('hidden');

    try {
        const query = getQueryString();
        const res = await fetch(`/api/jobs?${query}`, { headers: { 'X-Session-Id': SESSION_ID } });
        jobsData = await res.json();
        
        renderJobs();
    } catch (err) {
        console.error("Error loading jobs:", err);
        emptyState.classList.remove('hidden');
    } finally {
        contentLoader.classList.add('hidden');
    }
}

// Render jobs list into DOM
function renderJobs() {
    // Clear lists
    jobsGrid.innerHTML = '';
    jobsTableBody.innerHTML = '';
    
    if (jobsData.length === 0) {
        emptyState.classList.remove('hidden');
        jobsGrid.classList.add('hidden');
        jobsTableContainer.classList.add('hidden');
        return;
    }
    
    emptyState.classList.add('hidden');
    
    if (currentView === 'grid') {
        jobsGrid.classList.remove('hidden');
        jobsTableContainer.classList.add('hidden');
        jobsData.forEach(job => {
            jobsGrid.appendChild(createJobCard(job));
        });
    } else {
        jobsGrid.classList.add('hidden');
        jobsTableContainer.classList.remove('hidden');
        jobsData.forEach(job => {
            jobsTableBody.appendChild(createJobTableRow(job));
        });
    }
}

// Card Builder Helper
function createJobCard(job) {
    const card = document.createElement('div');
    card.className = 'job-card';
    card.setAttribute('data-id', job.id);
    
    const salaryStr = getSalaryString(job.min_amount, job.max_amount, job.currency);
    const locationStr = job.location || "Remote";
    
    card.innerHTML = `
        <div class="job-card-header">
            <div class="job-title-company">
                <h3 class="job-title-clickable">${escapeHtml(job.title)}</h3>
                <span class="job-company">${escapeHtml(job.company)}</span>
            </div>
            <span class="site-badge badge-${job.site}">${escapeHtml(job.site)}</span>
        </div>
        
        <div class="job-meta-pills">
            <span class="meta-pill"><i class="fa-solid fa-location-dot"></i> ${escapeHtml(locationStr)}</span>
            ${job.job_type ? `<span class="meta-pill"><i class="fa-solid fa-clock"></i> ${escapeHtml(job.job_type)}</span>` : ''}
            ${job.is_remote ? `<span class="meta-pill meta-pill-remote"><i class="fa-solid fa-house-laptop"></i> Remote</span>` : ''}
        </div>
        
        <div class="job-salary">
            ${salaryStr}
        </div>
        
        <div class="job-card-footer">
            <span class="posted-date"><i class="fa-regular fa-calendar"></i> ${escapeHtml(job.date_posted)}</span>
            
            <div class="status-dropdown-container">
                <select class="status-dropdown" data-status="${job.status}">
                    <option value="Not Applied" ${job.status === 'Not Applied' ? 'selected' : ''}>Not Applied</option>
                    <option value="Interested" ${job.status === 'Interested' ? 'selected' : ''}>Interested</option>
                    <option value="Applied" ${job.status === 'Applied' ? 'selected' : ''}>Applied</option>
                    <option value="Interviewing" ${job.status === 'Interviewing' ? 'selected' : ''}>Interviewing</option>
                    <option value="Offer" ${job.status === 'Offer' ? 'selected' : ''}>Offer Received</option>
                    <option value="Rejected" ${job.status === 'Rejected' ? 'selected' : ''}>Rejected</option>
                </select>
            </div>
        </div>
    `;
    
    // Bind click events
    card.querySelector('.job-title-clickable').addEventListener('click', () => {
        openDetailsDrawer(job);
    });
    
    const dropdown = card.querySelector('.status-dropdown');
    dropdown.addEventListener('change', (e) => {
        updateJobStatus(job.id, e.target.value, dropdown);
    });
    
    return card;
}

// Table Row Builder Helper
function createJobTableRow(job) {
    const tr = document.createElement('tr');
    tr.setAttribute('data-id', job.id);
    
    const salaryStr = getSalaryString(job.min_amount, job.max_amount, job.currency);
    const locationStr = job.location || "Remote";
    
    tr.innerHTML = `
        <td><span class="site-badge badge-${job.site}">${escapeHtml(job.site)}</span></td>
        <td><div class="table-title">${escapeHtml(job.title)}</div></td>
        <td><span class="table-company">${escapeHtml(job.company)}</span></td>
        <td>${escapeHtml(locationStr)} ${job.is_remote ? '<i class="fa-solid fa-house-laptop text-purple ml-1" title="Remote"></i>' : ''}</td>
        <td>${escapeHtml(job.country || 'Global')}</td>
        <td style="text-align: center;">${escapeHtml(job.date_posted)}</td>
        <td style="text-align: right; color: var(--color-green); font-weight:500;">${salaryStr}</td>
        <td>
            <div class="status-dropdown-container" style="width: 100%;">
                <select class="status-dropdown" data-status="${job.status}" style="padding: 4px 8px;">
                    <option value="Not Applied" ${job.status === 'Not Applied' ? 'selected' : ''}>Not Applied</option>
                    <option value="Interested" ${job.status === 'Interested' ? 'selected' : ''}>Interested</option>
                    <option value="Applied" ${job.status === 'Applied' ? 'selected' : ''}>Applied</option>
                    <option value="Interviewing" ${job.status === 'Interviewing' ? 'selected' : ''}>Interviewing</option>
                    <option value="Offer" ${job.status === 'Offer' ? 'selected' : ''}>Offer Received</option>
                    <option value="Rejected" ${job.status === 'Rejected' ? 'selected' : ''}>Rejected</option>
                </select>
            </div>
        </td>
        <td style="text-align: center;">
            <button class="btn btn-secondary btn-sm table-details-btn"><i class="fa-regular fa-eye"></i></button>
        </td>
    `;
    
    tr.querySelector('.table-title').addEventListener('click', () => {
        openDetailsDrawer(job);
    });
    
    tr.querySelector('.table-details-btn').addEventListener('click', () => {
        openDetailsDrawer(job);
    });
    
    const dropdown = tr.querySelector('.status-dropdown');
    dropdown.addEventListener('change', (e) => {
        updateJobStatus(job.id, e.target.value, dropdown);
    });
    
    return tr;
}

// Convert salary numbers to readable format
function getSalaryString(min, max, currency) {
    if (min === null && max === null) return 'Not Disclosed';
    
    const formatCurrency = (val) => {
        const symbol = currency === 'USD' ? '$' : currency + ' ';
        if (val >= 1000) {
            return symbol + (val / 1000).toFixed(0) + 'k';
        }
        return symbol + val;
    };
    
    if (min !== null && max !== null) {
        if (min === max) return formatCurrency(min);
        return `${formatCurrency(min)} - ${formatCurrency(max)}`;
    } else if (min !== null) {
        return `>= ${formatCurrency(min)}`;
    } else {
        return `<= ${formatCurrency(max)}`;
    }
}

// Inline Status dropdown updates
async function updateJobStatus(jobId, newStatus, dropdownElement) {
    try {
        const res = await fetch(`/api/jobs/${jobId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json', 'X-Session-Id': SESSION_ID },
            body: JSON.stringify({ status: newStatus })
        });
        
        if (res.ok) {
            // Update dropdown attributes
            dropdownElement.setAttribute('data-status', newStatus);
            
            // Sync status locally in jobsData array
            const jobIndex = jobsData.findIndex(j => j.id === jobId);
            if (jobIndex !== -1) {
                jobsData[jobIndex].status = newStatus;
                if (newStatus === 'Applied') {
                    jobsData[jobIndex].date_applied = new Date().toISOString().split('T')[0];
                }
            }
            
            // Reload stats (since status changed)
            loadStats();
        } else {
            alert("Failed to update status. Please try again.");
        }
    } catch (err) {
        console.error("Error updating status:", err);
    }
}

// Details drawer bindings
function openDetailsDrawer(job) {
    activeJobId = job.id;
    
    detailTitle.innerText = job.title;
    detailCompany.innerText = job.company;
    detailLocation.innerText = job.location || "Remote";
    detailJobType.innerText = job.job_type || "Full-time";
    detailDatePosted.innerText = job.date_posted;
    detailSalary.innerText = getSalaryString(job.min_amount, job.max_amount, job.currency);
    
    // Set site badge
    detailBoardBadge.className = `site-badge badge-${job.site}`;
    detailBoardBadge.innerText = job.site;
    
    // Set tracker fields
    detailStatus.value = job.status;
    detailDateApplied.innerText = job.date_applied || "N/A";
    
    // Show/hide applied date label based on status
    toggleDateAppliedVisibility(job.status);
    
    detailNotes.value = job.notes || "";
    
    // Description text formatting
    if (job.description) {
        detailDescription.innerText = job.description;
    } else {
        detailDescription.innerHTML = `<em>No description details scraped. Please visit the job board to read more details.</em>`;
    }
    
    // Apply URL link
    if (job.job_url) {
        detailApplyLink.href = job.job_url;
        detailApplyLink.style.display = 'inline-flex';
        
        // Auto mark as Applied when clicked
        detailApplyLink.onclick = () => {
            if (detailStatus.value === 'Not Applied' || detailStatus.value === 'Interested') {
                detailStatus.value = 'Applied';
                toggleDateAppliedVisibility('Applied');
                detailDateApplied.innerText = new Date().toISOString().split('T')[0];
                handleSaveDetailsTracker(false); // save changes quietly
            }
        };
    } else {
        detailApplyLink.style.display = 'none';
    }
    
    // Status dropdown change in details drawer
    detailStatus.onchange = (e) => {
        toggleDateAppliedVisibility(e.target.value);
        if (e.target.value === 'Applied') {
            detailDateApplied.innerText = new Date().toISOString().split('T')[0];
        } else if (job.status !== 'Applied') {
            detailDateApplied.innerText = "N/A";
        }
    };
    
    openDrawer(detailsDrawer);
}

function toggleDateAppliedVisibility(status) {
    const group = document.getElementById('detail-date-applied-group');
    if (status === 'Applied') {
        group.style.display = 'flex';
    } else {
        group.style.display = 'none';
    }
}

// Save status & notes from Details Drawer
async function handleSaveDetailsTracker(closeAfterSave = true) {
    if (!activeJobId) return;
    
    const status = detailStatus.value;
    const notes = detailNotes.value;
    
    try {
        const res = await fetch(`/api/jobs/${activeJobId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json', 'X-Session-Id': SESSION_ID },
            body: JSON.stringify({ status, notes })
        });
        
        if (res.ok) {
            // Update item locally
            const idx = jobsData.findIndex(j => j.id === activeJobId);
            if (idx !== -1) {
                jobsData[idx].status = status;
                jobsData[idx].notes = notes;
                if (status === 'Applied') {
                    jobsData[idx].date_applied = detailDateApplied.innerText;
                }
            }
            
            // Re-render and reload stats
            renderJobs();
            loadStats();
            
            if (closeAfterSave) {
                closeDrawer(detailsDrawer);
            }
        } else {
            alert("Error saving application information.");
        }
    } catch (err) {
        console.error("Error saving details:", err);
    }
}

// Scrape Submit configuration handler
function handleScrapeSubmit(e) {
    e.preventDefault();
    
    const keyword = document.getElementById('scrape-search-term').value;
    const location = document.getElementById('scrape-location').value;
    const hours = document.getElementById('scrape-hours').value;
    const results = document.getElementById('scrape-results').value;
    const remoteOnly = document.getElementById('scrape-remote-only').checked;
    const clearBefore = document.getElementById('scrape-clear-before').checked;
    const indeedCountry = document.getElementById('scrape-indeed-country').value;
    
    const boards = [];
    scrapeBoards.forEach(cb => {
        if (cb.checked) boards.push(cb.value);
    });
    
    if (boards.length === 0) {
        alert("Please select at least one job board.");
        return;
    }
    
    // Build SSE connection URL
    const params = new URLSearchParams({
        search_term: keyword,
        location: location,
        hours_old: hours,
        results_per_site: results,
        is_remote: remoteOnly,
        clear_before: clearBefore,
        sites: boards.join(','),
        country_indeed: indeedCountry,
        session_id: SESSION_ID
    });
    
    closeDrawer(scraperDrawer);
    
    // Open Console and start SSE log stream
    scrapeConsole.classList.remove('hidden');
    consoleLogs.innerHTML = "";
    appendLog("Initiating request connection...\n");
    
    if (eventSource) {
        eventSource.close();
    }
    
    eventSource = new EventSource(`/api/scrape?${params.toString()}`);
    
    eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        const msg = data.message;
        
        if (msg === '---SCRAPE_COMPLETE---') {
            appendLog("\nScrape sequence finished successfully!\n");
            eventSource.close();
            eventSource = null;
            loadStats();
            loadJobs();
        } else if (msg === '---SCRAPE_FAILED---') {
            appendLog("\nCRITICAL: Scraping execution failed.\n");
            eventSource.close();
            eventSource = null;
        } else {
            appendLog(msg);
        }
    };
    
    eventSource.onerror = (err) => {
        console.error("SSE Error:", err);
        appendLog("\nConnection error occurred. Retrying stream or completed.\n");
        eventSource.close();
        eventSource = null;
    };
}

function appendLog(text) {
    consoleLogs.appendChild(document.createTextNode(text));
    consoleLogs.scrollTop = consoleLogs.scrollHeight;
}

// Export excel spreadsheet navigation
function handleExportExcel() {
    const query = getQueryString();
    const url = `/api/export?${query}&session_id=${SESSION_ID}`;
    const a = document.createElement('a');
    a.href = url;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
}

// Clear all jobs from the tracker database
async function handleClearJobs() {
    if (!confirm("⚠️ Are you sure you want to delete all jobs from your tracker database? This action cannot be undone.")) {
        return;
    }
    
    try {
        const res = await fetch('/api/jobs/clear', {
            method: 'POST',
            headers: { 'X-Session-Id': SESSION_ID }
        });
        
        if (res.ok) {
            alert("All jobs have been removed successfully.");
            loadStats();
            loadJobs();
        } else {
            alert("Failed to clear jobs. Please try again.");
        }
    } catch (err) {
        console.error("Error clearing jobs:", err);
        alert("An error occurred while clearing jobs.");
    }
}


// HTML escape helper
function escapeHtml(text) {
    if (!text) return '';
    return text
        .toString()
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}
