/**
 * Custom JavaScript for the AI Job Search Automation System
 */

// Wait for DOM to be loaded
document.addEventListener('DOMContentLoaded', function() {
    console.log("DOM loaded - initializing UI components");

    // Enable tooltips everywhere
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Enable popovers
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });

    // Auto-hide alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert:not(.alert-dismissible)');
    alerts.forEach(function(alert) {
        setTimeout(function() {
            if (alert && alert.parentNode) {
                alert.classList.add('fade');
                setTimeout(function() {
                    if (alert && alert.parentNode) {
                        alert.parentNode.removeChild(alert);
                    }
                }, 500);
            }
        }, 5000);
    });

    // Handle form validation
    const forms = document.querySelectorAll('.needs-validation');
    Array.from(forms).forEach(form => {
        form.addEventListener('submit', event => {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
            }
            form.classList.add('was-validated');
        }, false);
    });

    // Mobile detection for better UI experience
    const isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
    if (isMobile) {
        document.body.classList.add('mobile-device');

        // Collapse navbar after click on mobile
        const navLinks = document.querySelectorAll('.navbar-nav .nav-link');
        const menuToggle = document.getElementById('navbarNav');
        if (menuToggle && typeof bootstrap !== 'undefined') {
            const bsCollapse = new bootstrap.Collapse(menuToggle, {toggle: false});

            navLinks.forEach(link => {
                link.addEventListener('click', () => {
                    bsCollapse.hide();
                });
            });
        }
    }

    // Format dates and times
    formatDateElements();

    // Add confirmation for dangerous actions
    setupConfirmationDialogs();

    // Check for running jobs
    console.log("Checking for running jobs...");
    setTimeout(() => JobTracker.checkForRunningJobs(), 500);
});

/**
 * Format date elements for better readability
 */
function formatDateElements() {
    const dateElements = document.querySelectorAll('.format-date');

    dateElements.forEach(element => {
        const dateStr = element.textContent.trim();
        if (dateStr && dateStr !== 'None' && dateStr !== 'Never') {
            try {
                const date = new Date(dateStr);
                const now = new Date();
                let formattedDate;

                // If date is today, show time with seconds
                if (date.toDateString() === now.toDateString()) {
                    formattedDate = `Today at ${date.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit', second:'2-digit'})}`;
                }
                // If date is yesterday
                else if (date.toDateString() === new Date(now - 86400000).toDateString()) {
                    formattedDate = `Yesterday at ${date.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit', second:'2-digit'})}`;
                }
                // If date is within last 7 days
                else if ((now - date) < 7 * 86400000) {
                    const days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
                    formattedDate = `${days[date.getDay()]} at ${date.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit', second:'2-digit'})}`;
                }
                // Otherwise, show full date with time including seconds
                else {
                    formattedDate = date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit', second:'2-digit'});
                }

                element.textContent = formattedDate;
            } catch (e) {
                console.warn("Date parsing error:", e);
            }
        }
    });
}

/**
 * Setup confirmation dialogs for dangerous actions
 */
function setupConfirmationDialogs() {
    const confirmActions = document.querySelectorAll('[data-confirm]');

    confirmActions.forEach(element => {
        element.addEventListener('click', function(e) {
            const message = this.getAttribute('data-confirm');
            if (!confirm(message)) {
                e.preventDefault();
                return false;
            }
            return true;
        });
    });
}

/**
 * Set form data from an object
 * @param {string} formId - The ID of the form to fill
 * @param {object} data - Object containing the data
 */
function setFormData(formId, data) {
    const form = document.getElementById(formId);
    if (!form) return;

    for (const [key, value] of Object.entries(data)) {
        const element = form.elements[key];
        if (!element) continue;

        if (element.type === 'checkbox') {
            element.checked = value;
        } else if (element.type === 'radio') {
            const radio = form.querySelector(`input[name="${key}"][value="${value}"]`);
            if (radio) radio.checked = true;
        } else if (element.tagName === 'SELECT') {
            element.value = value;
        } else {
            element.value = value;
        }
    }
}

/**
 * Get form data as an object
 * @param {string} formId - The ID of the form to get data from
 * @returns {object} Form data as object
 */
function getFormData(formId) {
    const form = document.getElementById(formId);
    if (!form) return {};

    const formData = new FormData(form);
    const data = {};

    for (const [key, value] of formData.entries()) {
        // Handle arrays (checkboxes with same name)
        if (key.endsWith('[]')) {
            const arrayKey = key.slice(0, -2);
            if (!data[arrayKey]) {
                data[arrayKey] = [];
            }
            data[arrayKey].push(value);
        } else {
            data[key] = value;
        }
    }

    // Handle unchecked checkboxes (not included in FormData)
    const checkboxes = form.querySelectorAll('input[type="checkbox"]');
    checkboxes.forEach(checkbox => {
        if (!checkbox.checked && !checkbox.name.endsWith('[]')) {
            data[checkbox.name] = false;
        }
    });

    return data;
}

/**
 * Toast Notification System
 */
const Toast = {
  // Show a toast notification
  show: function(message, type = 'info', duration = 5000) {
    console.log(`Showing toast: ${type} - ${message.substring(0, 50)}...`);

    // Create container if it doesn't exist
    let container = document.getElementById('toast-container');
    if (!container) {
      container = document.createElement('div');
      container.id = 'toast-container';
      document.body.appendChild(container);
    }

    // Create toast element
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = message;

    // Add close button
    const closeBtn = document.createElement('button');
    closeBtn.className = 'toast-close';
    closeBtn.innerHTML = '&times;';
    closeBtn.onclick = () => this.hide(toast);
    toast.appendChild(closeBtn);

    // Add to DOM
    container.appendChild(toast);

    // Trigger animation (small delay ensures transition works)
    setTimeout(() => toast.classList.add('show'), 10);

    // Auto-dismiss after duration (if specified)
    if (duration > 0) {
      setTimeout(() => this.hide(toast), duration);
    }

    return toast; // Return reference for later manipulation
  },

  // Hide a toast notification with animation
  hide: function(toast) {
    console.log("Hiding toast");
    toast.classList.remove('show');
    setTimeout(() => toast.remove(), 300); // Wait for transition to complete
  }
};

/**
 * Job Tracking System
 */
const JobTracker = {
  // Start tracking a job process
  start: function(type, id, data) {
    console.log(`Starting job tracker: ${type} - ${id}`);

    // Create job object with metadata
    const job = {
      type: type,
      id: id,
      data: data,
      status: 'running',
      startTime: Date.now()
    };

    // Save to localStorage for persistence across page navigation
    localStorage.setItem(`job_${type}_${id}`, JSON.stringify(job));

    // Show running notification
    this._showRunningToast(job);

    return job;
  },

  // Update job status
  update: function(type, id, status, result = null) {
    console.log(`Updating job: ${type} - ${id} - Status: ${status}`);

    const key = `job_${type}_${id}`;
    const storedJob = localStorage.getItem(key);

    if (storedJob) {
      try {
        // Parse stored job data
        const job = JSON.parse(storedJob);

        // Update status and add result data
        job.status = status;
        job.endTime = Date.now();
        if (result) job.result = result;

        // Save updated job data
        localStorage.setItem(key, JSON.stringify(job));

        // For completed/failed jobs, show completion notification
        if (status === 'completed' || status === 'failed') {
          this._showCompletionToast(job);

          // Clean up storage after a delay
          setTimeout(() => localStorage.removeItem(key), 60000);
        }

        return job;
      } catch (e) {
        console.error('Error updating job:', e);
      }
    }

    return null;
  },

  // Check for running jobs on page load
  checkForRunningJobs: function() {
    console.log("Checking for running jobs in localStorage");

    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);

      // Only process our job entries
      if (key && key.startsWith('job_')) {
        try {
          console.log(`Found job key: ${key}`);
          const job = JSON.parse(localStorage.getItem(key));

          // Only process running jobs
          if (job && job.status === 'running') {
            console.log(`Found running job: ${key}`);

            // Handle stalled jobs (running for too long)
            const runningTime = Date.now() - job.startTime;
            if (runningTime > 30 * 60 * 1000) { // 30 minutes
              console.log(`Job has timed out: ${key}`);
              // Mark as failed due to timeout
              job.status = 'failed';
              job.result = { message: 'Operation timed out' };
              localStorage.setItem(key, JSON.stringify(job));
              this._showCompletionToast(job);
            } else {
              // Still running, show notification
              console.log(`Showing toast for running job: ${key}`);
              this._showRunningToast(job);
            }
          }
        } catch (e) {
          console.error(`Error checking job ${key}:`, e);
        }
      }
    }
  },

  // Show toast for running job
  _showRunningToast: function(job) {
    console.log(`Showing running toast for job: ${job.type} - ${job.id}`);

    let message = '';

    // Customize message based on job type
    if (job.type === 'add_job_by_url') {
      message = '<i class="fa fa-spinner fa-spin"></i> Fetching and analyzing jobs from LinkedIn...';
    } else {
      message = '<i class="fa fa-spinner fa-spin"></i> Operation in progress...';
    }

    // Create a persistent toast (duration = 0)
    job.toast = Toast.show(message, 'info', 0);
  },

  // Show toast for completed/failed job
  _showCompletionToast: function(job) {
    console.log(`Showing completion toast for job: ${job.type} - ${job.id} - Status: ${job.status}`);

    let message = '';
    let type = '';

    if (job.status === 'completed') {
      if (job.type === 'add_job_by_url' && job.result) {
        // Get job count from several possible sources since the API response is inconsistent
        let jobCount = 0;

        // First check for our custom actual_jobs_count field
        if (job.result.actual_jobs_count !== undefined) {
          jobCount = job.result.actual_jobs_count;
          console.log(`Using actual_jobs_count: ${jobCount}`);
        }
        // Try to get from analysis result (most reliable)
        else if (job.result.analysis_result && job.result.analysis_result.analyzed) {
          // Subtract skipped jobs to get newly analyzed ones
          jobCount = job.result.analysis_result.analyzed - (job.result.analysis_result.skipped || 0);
          console.log(`Using analysis_result: ${jobCount}`);
          // Ensure minimum of 1 for successful operations
          if (jobCount <= 0) jobCount = 1;
        }
        // If no analysis result, check if we have job_ids_matched
        else if (job.result.job_ids_matched && job.result.job_ids_matched.length) {
          jobCount = job.result.job_ids_matched.length;
          console.log(`Using job_ids_matched: ${jobCount}`);
        }
        // Fall back to jobs_found
        else {
          jobCount = job.result.jobs_found || 1; // Default to at least 1 if we reached "success"
          console.log(`Using jobs_found or default: ${jobCount}`);
        }

        message = `<i class="fa fa-check-circle"></i> Successfully processed ${jobCount} job${jobCount !== 1 ? 's' : ''} from LinkedIn.`;
      } else {
        message = '<i class="fa fa-check-circle"></i> Operation completed successfully.';
      }
      type = 'success';
    } else {
      if (job.result && job.result.message) {
        message = `<i class="fa fa-times-circle"></i> Error: ${job.result.message}`;
      } else {
        message = '<i class="fa fa-times-circle"></i> Operation failed.';
      }
      type = 'error';
    }

    // If there's an existing toast, remove it
    if (job.toast) {
      Toast.hide(job.toast);
    }

    // Show the completion toast (auto-dismiss after 8 seconds)
    Toast.show(message, type, 8000);
  }
};

// Initialize job tracking on page load
document.addEventListener('DOMContentLoaded', function() {
  // Check for any running jobs after a short delay
  // (allows page to fully initialize first)
  setTimeout(() => JobTracker.checkForRunningJobs(), 500);
});

// Check for running jobs when page loads
document.addEventListener('DOMContentLoaded', function() {
  // Add this to the existing DOMContentLoaded listener in custom.js
  // or create a new one if adding to the end of the file

  // Check after a short delay to allow other scripts to initialize
  setTimeout(() => JobTracker.checkForRunningJobs(), 500);
});

// Check for running jobs when page loads
document.addEventListener('DOMContentLoaded', function() {
  // Add this to the existing DOMContentLoaded listener in custom.js
  // or create a new one if adding to the end of the file

  // Check after a short delay to allow other scripts to initialize
  setTimeout(() => JobTracker.checkForRunningJobs(), 500);
});

// Check for running jobs when page loads
document.addEventListener('DOMContentLoaded', function() {
  // Add this to the existing DOMContentLoaded listener in custom.js
  // or create a new one if adding to the end of the file

  // Check after a short delay to allow other scripts to initialize
  setTimeout(() => JobTracker.checkForRunningJobs(), 500);
});