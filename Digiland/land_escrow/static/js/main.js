/* ============================================================================= */
/* Digiland Main JavaScript */
/* ============================================================================= */

// Initialize Bootstrap tooltips
document.addEventListener('DOMContentLoaded', function() {
    // Initialise Bootstrap tooltips globally
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Initialise Bootstrap popovers
    var popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    var popoverList = popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });

    // Auto-hide alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(function(alert) {
        if (!alert.classList.contains('alert-permanent')) {
            setTimeout(function() {
                alert.style.transition = 'opacity 0.3s ease-out';
                alert.style.opacity = '0';
                setTimeout(function() {
                    alert.remove();
                }, 300);
            }, 5000);
        }
    });

    // Form validation enhancements
    const forms = document.querySelectorAll('form');
    forms.forEach(function(form) {
        form.addEventListener('submit', function(e) {
            const submitBtn = form.querySelector('button[type="submit"]');
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.innerHTML = '<span class="spinner-grow spinner-grow-sm me-2" role="status"></span>Processing...';
                
                // Re-enable after 10 seconds (fallback)
                setTimeout(function() {
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = submitBtn.getAttribute('data-original-text') || submitBtn.innerText;
                }, 10000);
            }
        });
    });

    // Password strength indicator
    const passwordInputs = document.querySelectorAll('input[type="password"]');
    passwordInputs.forEach(function(input) {
        const strengthIndicator = document.createElement('div');
        strengthIndicator.className = 'password-strength';
        input.parentNode.insertBefore(strengthIndicator, input.nextSibling);

        input.addEventListener('input', function() {
            const password = input.value;
            const strength = calculatePasswordStrength(password);
            
            strengthIndicator.className = 'password-strength ' + strength.level;
            strengthIndicator.style.width = strength.percentage + '%';
        });
    });

    // Smooth scroll for anchor links
    const anchorLinks = document.querySelectorAll('a[href^="#"]');
    anchorLinks.forEach(function(link) {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });

    // Copy to clipboard functionality
    const copyButtons = document.querySelectorAll('[data-copy]');
    copyButtons.forEach(function(button) {
        button.addEventListener('click', function() {
            const textToCopy = document.querySelector(this.getAttribute('data-copy'));
            if (textToCopy) {
                navigator.clipboard.writeText(textToCopy.textContent).then(function() {
                    // Show success feedback
                    const originalText = button.innerHTML;
                    button.innerHTML = '<i class="bi bi-check-circle"></i> Copied!';
                    button.classList.add('text-success');
                    
                    setTimeout(function() {
                        button.innerHTML = originalText;
                        button.classList.remove('text-success');
                    }, 2000);
                }).catch(function(err) {
                    console.error('Failed to copy: ', err);
                });
            }
        });
    });

    // Auto-resize textareas
    const textareas = document.querySelectorAll('textarea');
    textareas.forEach(function(textarea) {
        textarea.addEventListener('input', function() {
            textarea.style.height = 'auto';
            textarea.style.height = textarea.scrollHeight + 'px';
        });
    });

    // Custom form functions for admin dashboard
    window.clearMessageForm = function() {
        const form = document.querySelector('form[action*="send_admin_message"]');
        if (form) {
            form.reset();
            // Show custom emails input if needed
            const recipientSelect = form.querySelector('select[name="recipient_type"]');
            const customEmailsInput = document.getElementById('customEmailsInput');
            if (recipientSelect && customEmailsInput) {
                if (recipientSelect.value === 'custom') {
                    customEmailsInput.style.display = 'block';
                    customEmailsInput.required = true;
                } else {
                    customEmailsInput.style.display = 'none';
                    customEmailsInput.required = false;
                }
            }
        }
    };

    // Handle recipient type change
    const recipientSelect = document.querySelector('select[name="recipient_type"]');
    if (recipientSelect) {
        recipientSelect.addEventListener('change', function() {
            const customEmailsInput = document.getElementById('customEmailsInput');
            if (customEmailsInput) {
                if (this.value === 'custom') {
                    customEmailsInput.style.display = 'block';
                    customEmailsInput.required = true;
                } else {
                    customEmailsInput.style.display = 'none';
                    customEmailsInput.required = false;
                }
            }
        });
    }
});

// Password strength calculator
function calculatePasswordStrength(password) {
    let strength = 0;
    let level = 'weak';
    
    if (password.length >= 8) strength += 25;
    if (password.length >= 12) strength += 25;
    if (/[a-z]/.test(password)) strength += 10;
    if (/[A-Z]/.test(password)) strength += 10;
    if (/[0-9]/.test(password)) strength += 10;
    if (/[^a-zA-Z0-9]/.test(password)) strength += 20;
    
    if (strength < 40) {
        level = 'weak';
    } else if (strength < 60) {
        level = 'fair';
    } else {
        level = 'strong';
    }
    
    return {
        level: level,
        percentage: Math.min(strength, 100)
    };
}

// Utility functions
function showLoadingSpinner(element) {
    element.disabled = true;
    element.innerHTML = '<span class="spinner-grow spinner-grow-sm me-2"></span>Loading...';
}

function hideLoadingSpinner(element, originalText) {
    element.disabled = false;
    element.innerHTML = originalText;
}

function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `alert alert-${type} position-fixed top-0 end-0 m-3`;
    toast.style.zIndex = '9999';
    toast.style.minWidth = '300px';
    toast.innerHTML = `
        <div class="d-flex align-items-center">
            <i class="bi bi-${getIconForType(type)} me-2"></i>
            <span>${message}</span>
            <button type="button" class="btn-close ms-auto" data-bs-dismiss="alert">
                <i class="bi bi-x"></i>
            </button>
        </div>
    `;
    
    document.body.appendChild(toast);
    
    // Auto-remove after 5 seconds
    setTimeout(function() {
        toast.style.transition = 'opacity 0.3s ease-out';
        toast.style.opacity = '0';
        setTimeout(function() {
            toast.remove();
        }, 300);
    }, 5000);
}

function getIconForType(type) {
    const icons = {
        'success': 'check-circle-fill',
        'danger': 'exclamation-triangle-fill',
        'warning': 'exclamation-triangle-fill',
        'info': 'info-circle-fill'
    };
    return icons[type] || 'info-circle-fill';
}

// Form validation
function validateForm(form) {
    const requiredFields = form.querySelectorAll('[required]');
    let isValid = true;
    
    requiredFields.forEach(function(field) {
        if (!field.value.trim()) {
            field.classList.add('is-invalid');
            isValid = false;
        } else {
            field.classList.remove('is-invalid');
        }
    });
    
    return isValid;
}

// AJAX helper functions
function makeAjaxRequest(url, method, data, onSuccess, onError) {
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]');
    
    fetch(url, {
        method: method,
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken ? csrfToken.value : ''
        },
        body: JSON.stringify(data)
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            onSuccess(data);
        } else {
            onError(data.message || 'An error occurred');
        }
    })
    .catch(error => {
        console.error('AJAX Error:', error);
        onError('Network error occurred');
    });
}

// Export functions for global use
window.Digiland = {
    showLoadingSpinner,
    hideLoadingSpinner,
    showToast,
    validateForm,
    makeAjaxRequest
};
