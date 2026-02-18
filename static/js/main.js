// ============================================================================
// STOCK CHECKER SYSTEM - COMPLETE JAVASCRIPT
// ============================================================================

// System Configuration
const SystemConfig = {
    primaryColor: getComputedStyle(document.documentElement).getPropertyValue('--primary-color').trim() || '#2563eb',
    successColor: getComputedStyle(document.documentElement).getPropertyValue('--success-color').trim() || '#059669',
    warningColor: getComputedStyle(document.documentElement).getPropertyValue('--warning-color').trim() || '#d97706',
    dangerColor: getComputedStyle(document.documentElement).getPropertyValue('--danger-color').trim() || '#dc2626'
};

// ============================================================================
// INITIALIZATION
// ============================================================================
document.addEventListener('DOMContentLoaded', function() {
    console.log('📦 Stock Checker System Initialized');
    
    // Initialize all components
    initializeTooltips();
    initializeCopyButtons();
    initializeFileSelector();
    initializeSearch();
    initializeContainerModals();
    initializeLogoutProtection();
    initializePagination();
    initializeFileUpload();
    initializeStatusBadges();
    initializeTableHover();
    initializeModalCloseButtons();
});

// ============================================================================
// COPY TO CLIPBOARD FUNCTIONALITY
// ============================================================================
function initializeCopyButtons() {
    document.querySelectorAll('.copy-btn').forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            
            const targetId = this.dataset.target;
            const targetElement = document.getElementById(targetId);
            
            if (targetElement) {
                const textToCopy = targetElement.innerText || targetElement.value;
                
                navigator.clipboard.writeText(textToCopy).then(() => {
                    // Visual feedback
                    const originalText = this.innerHTML;
                    this.innerHTML = '✓ Copied!';
                    this.classList.add('copied');
                    
                    showNotification('📋 Copied to clipboard!', 'success');
                    
                    setTimeout(() => {
                        this.innerHTML = originalText;
                        this.classList.remove('copied');
                    }, 2000);
                }).catch(err => {
                    console.error('Copy failed:', err);
                    showNotification('❌ Failed to copy', 'error');
                });
            }
        });
    });
}

// ============================================================================
// CONTAINER DETAILS MODAL
// ============================================================================
function initializeContainerModals() {
    // View container details buttons
    document.querySelectorAll('.view-container-btn').forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            const sku = this.dataset.sku;
            const containerDetails = this.dataset.containerDetails;
            const containerQty = this.dataset.containerQty;
            
            showContainerModal(sku, containerDetails, containerQty);
        });
    });
}

// Global function to show container modal (accessible from onclick)
window.showContainerModal = function(sku, containerDetails, containerQty) {
    console.log('🔍 Opening container modal for:', sku);
    console.log('📦 Container Details:', containerDetails);
    console.log('📊 Container Qty:', containerQty);
    
    const modal = document.getElementById('containerModal');
    if (!modal) {
        console.error('❌ Modal element not found!');
        showNotification('Error: Modal not found', 'error');
        return;
    }
    
    const modalTitle = modal.querySelector('.modal-title');
    const modalBody = modal.querySelector('.modal-body');
    
    if (!modalTitle || !modalBody) {
        console.error('❌ Modal components not found!');
        return;
    }
    
    modalTitle.textContent = `📦 Container Details - ${sku}`;
    
    let html = `
        <div class="container-summary" style="margin-bottom: 1.5rem; padding: 1rem; background: linear-gradient(135deg, #f3f4f6, #e5e7eb); border-radius: 0.75rem;">
            <p style="margin: 0; font-size: 1rem;">
                <strong>Total Incoming:</strong> 
                <span style="color: var(--success-color); font-weight: 700; font-size: 1.25rem;">${containerQty}</span> 
                units
            </p>
        </div>
    `;
    
    if (containerDetails && containerDetails !== 'null' && containerDetails !== '' && containerDetails !== '0') {
        html += '<h4 style="margin: 1.5rem 0 1rem; color: var(--text-dark); font-weight: 600;">📅 Expected Arrivals:</h4>';
        html += '<ul class="container-list">';
        
        // Parse format like: "200 (1/28/26), 250 (1/31/26)"
        const containers = parseContainerDetails(containerDetails);
        
        if (containers.length > 0) {
            containers.forEach(container => {
                html += `
                    <li class="container-item">
                        <span class="container-quantity">${container.quantity} units</span>
                        <span class="container-date">📅 ${container.date}</span>
                    </li>
                `;
            });
        } else {
            // Fallback for unparseable format - show raw details
            html += `
                <li class="container-item">
                    <span class="container-quantity">${containerQty} units</span>
                    <span class="container-date">${containerDetails}</span>
                </li>
            `;
        }
        
        html += '</ul>';
    } else {
        html += '<p style="color: var(--text-light); margin-top: 1rem; padding: 1rem; text-align: center; background: var(--background); border-radius: 0.5rem;">No container details available for this SKU.</p>';
    }
    
    modalBody.innerHTML = html;
    modal.style.display = 'block';
    
    // Prevent body scrolling when modal is open
    document.body.style.overflow = 'hidden';
};

function parseContainerDetails(details) {
    if (!details || details === 'null' || details === '') return [];
    
    const containers = [];
    // Matches patterns like: "200 (1/28/26)" or "250 (1/31/26)"
    const regex = /(\d+)\s*\(([^)]+)\)/g;
    let match;
    
    while ((match = regex.exec(details)) !== null) {
        containers.push({
            quantity: match[1],
            date: match[2].trim()
        });
    }
    
    return containers;
}

function initializeModalCloseButtons() {
    const modal = document.getElementById('containerModal');
    if (!modal) return;
    
    // Close button
    const closeBtn = modal.querySelector('.modal-close');
    if (closeBtn) {
        closeBtn.addEventListener('click', function() {
            modal.style.display = 'none';
            document.body.style.overflow = '';
        });
    }
    
    // Click outside modal
    window.addEventListener('click', function(e) {
        if (e.target === modal) {
            modal.style.display = 'none';
            document.body.style.overflow = '';
        }
    });
    
    // ESC key
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && modal.style.display === 'block') {
            modal.style.display = 'none';
            document.body.style.overflow = '';
        }
    });
}

// ============================================================================
// FILE SELECTOR
// ============================================================================
function initializeFileSelector() {
    const fileSelect = document.getElementById('fileSelect');
    if (fileSelect) {
        fileSelect.addEventListener('change', function() {
            const selectedFileId = this.value;
            if (!selectedFileId) return;
            
            const currentUrl = new URL(window.location.href);
            currentUrl.searchParams.set('file_id', selectedFileId);
            currentUrl.searchParams.set('page', '1'); // Reset to first page
            
            showNotification('🔄 Switching file...', 'info');
            window.location.href = currentUrl.toString();
        });
    }
}

// ============================================================================
// SEARCH WITH DEBOUNCE
// ============================================================================
function initializeSearch() {
    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
        let debounceTimer;
        let previousValue = searchInput.value;
        
        searchInput.addEventListener('input', function() {
            clearTimeout(debounceTimer);
            
            const currentValue = this.value.trim();
            
            debounceTimer = setTimeout(() => {
                if (currentValue !== previousValue) {
                    const currentUrl = new URL(window.location.href);
                    
                    if (currentValue.length >= 2) {
                        currentUrl.searchParams.set('q', currentValue);
                        currentUrl.searchParams.set('page', '1');
                        showNotification('🔍 Searching...', 'info');
                    } else {
                        currentUrl.searchParams.delete('q');
                    }
                    
                    previousValue = currentValue;
                    window.location.href = currentUrl.toString();
                }
            }, 500); // 500ms debounce
        });
        
        // Search on Enter key
        searchInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                clearTimeout(debounceTimer);
                
                const currentValue = this.value.trim();
                const currentUrl = new URL(window.location.href);
                
                if (currentValue.length >= 1) {
                    currentUrl.searchParams.set('q', currentValue);
                    currentUrl.searchParams.set('page', '1');
                    showNotification('🔍 Searching...', 'info');
                    window.location.href = currentUrl.toString();
                }
            }
        });
    }
}

// ============================================================================
// LOGOUT PROTECTION - PREVENT BACK BUTTON
// ============================================================================
function initializeLogoutProtection() {
    // Check session on page load
    checkSession();
    
    // Handle back/forward navigation
    window.addEventListener('pageshow', function(event) {
        if (event.persisted) {
            // Page was loaded from cache (back/forward)
            checkSession();
        }
    });
}

function checkSession() {
    fetch('/check-session', {
        method: 'GET',
        credentials: 'same-origin',
        headers: {
            'Cache-Control': 'no-cache'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (!data.authenticated) {
            window.location.href = '/login';
        }
    })
    .catch(err => console.error('Session check failed:', err));
}

// ============================================================================
// PAGINATION
// ============================================================================
function initializePagination() {
    const paginationLinks = document.querySelectorAll('.page-link:not(.disabled)');
    paginationLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const page = this.dataset.page;
            if (page) {
                const currentUrl = new URL(window.location.href);
                currentUrl.searchParams.set('page', page);
                window.location.href = currentUrl.toString();
            }
        });
    });
}

// ============================================================================
// FILE UPLOAD
// ============================================================================
function initializeFileUpload() {
    const uploadForm = document.getElementById('uploadForm');
    const fileInput = document.getElementById('fileInput');
    const submitBtn = uploadForm ? uploadForm.querySelector('button[type="submit"]') : null;
    
    if (uploadForm && fileInput && submitBtn) {
        uploadForm.addEventListener('submit', function(e) {
            const file = fileInput.files[0];
            
            if (!file) {
                e.preventDefault();
                showNotification('❌ Please select a file to upload', 'error');
                return;
            }
            
            // Validate filename format
            const filenamePattern = /^CheckStockTempFile_\d{2}-\d{2}-\d{2}\.xlsx?$/;
            if (!filenamePattern.test(file.name)) {
                e.preventDefault();
                showNotification('❌ Invalid filename. Expected: CheckStockTempFile_MM-DD-YY.xlsx', 'error');
                return;
            }
            
            // Validate file size (16MB max)
            const maxSize = 16 * 1024 * 1024; // 16MB in bytes
            if (file.size > maxSize) {
                e.preventDefault();
                showNotification('❌ File too large. Maximum size is 16MB', 'error');
                return;
            }
            
            // Show loading state
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<span class="spinner"></span> Uploading...';
            
            // Show notification
            showNotification('📤 Uploading file...', 'info');
        });
    }
}

// ============================================================================
// STATUS BADGES
// ============================================================================
function initializeStatusBadges() {
    document.querySelectorAll('.status-badge').forEach(badge => {
        const status = badge.textContent.trim().toLowerCase();
        
        // Add appropriate icon based on status
        let icon = '';
        if (status.includes('in stock')) {
            icon = '✅ ';
        } else if (status.includes('low stock')) {
            icon = '⚠️ ';
        } else if (status.includes('out of stock')) {
            icon = '❌ ';
        }
        
        badge.innerHTML = icon + badge.innerHTML;
    });
}

// ============================================================================
// TABLE HOVER EFFECTS
// ============================================================================
function initializeTableHover() {
    const tableRows = document.querySelectorAll('.data-table tbody tr');
    tableRows.forEach(row => {
        row.addEventListener('mouseenter', function() {
            this.style.backgroundColor = '#f9fafb';
        });
        row.addEventListener('mouseleave', function() {
            this.style.backgroundColor = '';
        });
    });
}

// ============================================================================
// NOTIFICATION SYSTEM
// ============================================================================
function showNotification(message, type = 'info', duration = 3000) {
    // Create notification container if it doesn't exist
    let container = document.getElementById('notification-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'notification-container';
        container.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 9999;
            display: flex;
            flex-direction: column;
            gap: 10px;
        `;
        document.body.appendChild(container);
    }
    
    // Create notification element
    const notification = document.createElement('div');
    notification.style.cssText = `
        padding: 1rem 1.5rem;
        border-radius: 0.75rem;
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
        animation: slideInRight 0.3s ease;
        max-width: 350px;
        backdrop-filter: blur(8px);
        border-left: 6px solid;
    `;
    
    // Set colors based on type
    switch(type) {
        case 'success':
            notification.style.background = 'linear-gradient(135deg, #d1fae5, #a7f3d0)';
            notification.style.color = '#059669';
            notification.style.borderLeftColor = '#059669';
            break;
        case 'error':
            notification.style.background = 'linear-gradient(135deg, #fee2e2, #fecaca)';
            notification.style.color = '#dc2626';
            notification.style.borderLeftColor = '#dc2626';
            break;
        case 'warning':
            notification.style.background = 'linear-gradient(135deg, #fef3c7, #fde68a)';
            notification.style.color = '#d97706';
            notification.style.borderLeftColor = '#d97706';
            break;
        default:
            notification.style.background = 'linear-gradient(135deg, #dbeafe, #bfdbfe)';
            notification.style.color = '#2563eb';
            notification.style.borderLeftColor = '#2563eb';
    }
    
    notification.innerHTML = message;
    
    // Add to container
    container.appendChild(notification);
    
    // Remove after duration
    setTimeout(() => {
        notification.style.animation = 'slideOutRight 0.3s ease';
        setTimeout(() => {
            notification.remove();
            if (container.children.length === 0) {
                container.remove();
            }
        }, 300);
    }, duration);
}

// ============================================================================
// TOOLTIPS
// ============================================================================
function initializeTooltips() {
    const tooltips = document.querySelectorAll('[data-tooltip]');
    tooltips.forEach(element => {
        element.addEventListener('mouseenter', showTooltip);
        element.addEventListener('mouseleave', hideTooltip);
    });
}

function showTooltip(e) {
    const tooltipText = e.target.dataset.tooltip;
    const tooltip = document.createElement('div');
    tooltip.className = 'tooltip';
    tooltip.textContent = tooltipText;
    tooltip.style.cssText = `
        position: absolute;
        background: var(--text-dark);
        color: white;
        padding: 0.5rem 0.75rem;
        border-radius: 0.375rem;
        font-size: 0.75rem;
        z-index: 1000;
        pointer-events: none;
        white-space: nowrap;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        animation: fadeIn 0.2s ease;
    `;
    
    document.body.appendChild(tooltip);
    
    const rect = e.target.getBoundingClientRect();
    tooltip.style.top = rect.top - tooltip.offsetHeight - 5 + window.scrollY + 'px';
    tooltip.style.left = rect.left + (rect.width / 2) - (tooltip.offsetWidth / 2) + 'px';
    
    e.target._tooltip = tooltip;
}

function hideTooltip(e) {
    if (e.target._tooltip) {
        e.target._tooltip.remove();
        e.target._tooltip = null;
    }
}

// ============================================================================
// EXPORT FUNCTIONS (for admin use)
// ============================================================================
window.StockChecker = {
    copyToClipboard: function(text) {
        navigator.clipboard.writeText(text).then(() => {
            showNotification('📋 Copied to clipboard!', 'success');
        });
    },
    
    showContainerModal: window.showContainerModal,
    
    exportToCSV: function(data, filename = 'stock_data.csv') {
        if (!data || !data.length) {
            showNotification('❌ No data to export', 'error');
            return;
        }
        
        const csvContent = convertToCSV(data);
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');
        const url = URL.createObjectURL(blob);
        
        link.setAttribute('href', url);
        link.setAttribute('download', filename);
        link.style.visibility = 'hidden';
        
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        
        showNotification(`📥 Exported to ${filename}`, 'success');
    },
    
    showNotification: showNotification,
    
    refreshData: function() {
        showNotification('🔄 Refreshing data...', 'info');
        setTimeout(() => {
            window.location.reload();
        }, 500);
    }
};

function convertToCSV(data) {
    const headers = Object.keys(data[0]);
    const csvRows = [];
    
    // Add headers
    csvRows.push(headers.join(','));
    
    // Add rows
    for (const row of data) {
        const values = headers.map(header => {
            const value = row[header] || '';
            // Escape quotes and wrap in quotes if contains comma
            const escaped = value.toString().replace(/"/g, '""');
            return escaped.includes(',') ? `"${escaped}"` : escaped;
        });
        csvRows.push(values.join(','));
    }
    
    return csvRows.join('\n');
}

// ============================================================================
// ADD CSS ANIMATIONS
// ============================================================================
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
    
    @keyframes slideOutRight {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(100%);
            opacity: 0;
        }
    }
    
    @keyframes fadeIn {
        from {
            opacity: 0;
        }
        to {
            opacity: 1;
        }
    }
    
    .tooltip {
        transition: opacity 0.2s;
    }
    
    .copy-btn.copied {
        background: linear-gradient(135deg, var(--success-color), #10b981) !important;
        border-color: var(--success-color) !important;
        color: white !important;
    }
`;
document.head.appendChild(style);

// ============================================================================
// EXPORT FUNCTIONS TO GLOBAL SCOPE
// ============================================================================
window.showContainerModal = window.showContainerModal;
window.StockChecker = window.StockChecker;

// ============================================================================
// FILE DELETION FUNCTIONS
// ============================================================================
window.confirmDeleteFile = function(fileId, fileDate) {
    if (confirm(`⚠️ Are you sure you want to delete the file from ${fileDate}?\n\nThis will permanently delete:\n- The file record\n- All ${document.querySelector(`option[value="${fileId}"]`)?.text.match(/\d+ items/)?.[0] || 'associated'} SKUs\n\nThis action CANNOT be undone!`)) {
        deleteFile(fileId);
    }
};

function deleteFile(fileId) {
    fetch(`/delete-file/${fileId}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification('✅ File deleted successfully!', 'success');
            setTimeout(() => {
                window.location.href = '/dashboard';
            }, 1500);
        } else {
            showNotification('❌ Error: ' + data.error, 'error');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showNotification('❌ Failed to delete file', 'error');
    });
}

