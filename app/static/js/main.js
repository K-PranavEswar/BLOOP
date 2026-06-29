/**
 * Main JS for HemoPulse AI Pro (SaaS UI)
 */

document.addEventListener('DOMContentLoaded', () => {
    initSidebar();
    initPasswordStrength();
    initOTPInputs();
    animateCounters();
    initTooltips();
    initAnimations();
});

function initSidebar() {
    const toggleBtn = document.getElementById('sidebarToggle');
    const sidebar = document.getElementById('sidebar');
    if(toggleBtn && sidebar) {
        toggleBtn.addEventListener('click', (e) => {
            e.preventDefault();
            sidebar.classList.toggle('show');
        });
    }
}

function initTooltips() {
    // Bootstrap tooltips
    if(typeof bootstrap !== 'undefined') {
        const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'))
        tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl)
        });
    }
}

function initPasswordStrength() {
    const pwdInput = document.querySelector('input[name="password"], input[name="new_password"]');
    const strengthBar = document.querySelector('.password-strength-bar');
    
    if (pwdInput && strengthBar) {
        pwdInput.addEventListener('input', function() {
            const val = this.value;
            let strength = 0;
            
            if (val.length >= 8) strength += 25;
            if (val.match(/[A-Z]/)) strength += 25;
            if (val.match(/[0-9]/)) strength += 25;
            if (val.match(/[^A-Za-z0-9]/)) strength += 25;
            
            strengthBar.style.width = strength + '%';
            
            if (strength <= 25) {
                strengthBar.style.backgroundColor = 'var(--danger)';
            } else if (strength <= 50) {
                strengthBar.style.backgroundColor = 'var(--warning)';
            } else if (strength <= 75) {
                strengthBar.style.backgroundColor = 'var(--info)';
            } else {
                strengthBar.style.backgroundColor = 'var(--success)';
            }
        });
    }
}

function initOTPInputs() {
    const inputs = document.querySelectorAll('.otp-inputs input');
    const hiddenInput = document.getElementById('otp_code');
    
    if (inputs.length && hiddenInput) {
        inputs.forEach((input, index) => {
            input.addEventListener('input', (e) => {
                if (e.target.value.length === 1 && index < inputs.length - 1) {
                    inputs[index + 1].focus();
                }
                updateHiddenOTP();
            });
            
            input.addEventListener('keydown', (e) => {
                if (e.key === 'Backspace' && !e.target.value && index > 0) {
                    inputs[index - 1].focus();
                }
            });
        });
        
        function updateHiddenOTP() {
            let val = '';
            inputs.forEach(i => val += i.value);
            hiddenInput.value = val;
        }
    }
}

function animateCounters() {
    const counters = document.querySelectorAll('[data-counter]');
    counters.forEach(counter => {
        const target = +counter.getAttribute('data-counter');
        const duration = 1000;
        const increment = target / (duration / 16);
        let current = 0;
        
        const updateCounter = () => {
            current += increment;
            if (current < target) {
                counter.innerText = Math.ceil(current);
                requestAnimationFrame(updateCounter);
            } else {
                counter.innerText = target;
            }
        };
        updateCounter();
    });
}

function initAnimations() {
    // Add fade-in class to main elements
    const cards = document.querySelectorAll('.saas-card, .stat-card, .camp-card');
    cards.forEach((card, i) => {
        card.style.opacity = '0';
        setTimeout(() => {
            card.classList.add('fade-in');
        }, i * 50);
    });
}

/**
 * Toast Notification System
 */
function showToast(message, type = 'info', title = null) {
    const container = document.getElementById('toast-container');
    if (!container) return;
    
    const toast = document.createElement('div');
    toast.className = 'saas-toast';
    
    let iconClass = 'fas fa-info-circle text-info';
    let defaultTitle = 'Notification';
    
    if (type === 'success') {
        iconClass = 'fas fa-check-circle text-success';
        defaultTitle = 'Success';
    } else if (type === 'danger' || type === 'error') {
        iconClass = 'fas fa-times-circle text-danger';
        defaultTitle = 'Error';
    } else if (type === 'warning') {
        iconClass = 'fas fa-exclamation-triangle text-warning';
        defaultTitle = 'Warning';
    }
    
    toast.innerHTML = `
        <div class="saas-toast-icon"><i class="${iconClass}"></i></div>
        <div class="saas-toast-content">
            <div class="saas-toast-title">${title || defaultTitle}</div>
            <p class="saas-toast-message">${message}</p>
        </div>
        <button class="saas-toast-close"><i class="fas fa-times"></i></button>
    `;
    
    container.appendChild(toast);
    
    // Close button logic
    const closeBtn = toast.querySelector('.saas-toast-close');
    closeBtn.addEventListener('click', () => {
        toast.classList.add('hiding');
        setTimeout(() => toast.remove(), 300);
    });
    
    // Auto dismiss
    setTimeout(() => {
        if(document.body.contains(toast)) {
            toast.classList.add('hiding');
            setTimeout(() => toast.remove(), 300);
        }
    }, 5000);
}

function confirmAction(message) {
    return confirm(message);
}

function validateRegistrationForm() {
    const email = document.querySelector('input[name="email"]').value;
    const phone = document.querySelector('input[name="phone"]').value;
    if (!email && !phone) {
        showToast('Either email or phone number is required.', 'danger');
        return false;
    }
    return true;
}
