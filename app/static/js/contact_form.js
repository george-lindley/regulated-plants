// contact-form.js
document.addEventListener('DOMContentLoaded', function() {
    const contactForm = document.getElementById('contact-form');
    
    if (contactForm) {
        const subjectSelect = contactForm.querySelector('#subject');
        const messageField = contactForm.querySelector('#message');
        const defaultMessages = window.CONTACT_FORM_DEFAULTS || {};

        function isKnownDefault(value) {
            const normalized = (value || '').trim();
            return Object.values(defaultMessages).some(message => (message || '').trim() === normalized);
        }

        if (subjectSelect && messageField) {
            subjectSelect.addEventListener('change', function() {
                const nextMessage = defaultMessages[subjectSelect.value] || '';
                const currentMessage = messageField.value || '';
                if (nextMessage) {
                    if (!currentMessage.trim() || isKnownDefault(currentMessage)) {
                        messageField.value = nextMessage;
                    }
                } else if (isKnownDefault(currentMessage)) {
                    messageField.value = '';
                }
            });
        }

        contactForm.addEventListener('submit', function(e) {
            // We don't prevent default here since we want the form to submit to the server
            
            // Disable form during submission
            const submitBtn = contactForm.querySelector('button[type="submit"]');
            const originalText = submitBtn.textContent;
            submitBtn.disabled = true;
            submitBtn.textContent = 'Sending...';
            
            // We'll enable the button again when the page reloads after submission
            // This is a fallback in case the form submission fails
            setTimeout(() => {
                submitBtn.disabled = false;
                submitBtn.textContent = originalText;
            }, 10000); // 10-second timeout as a fallback
        });
        
        // Auto-hide flash messages after 5 seconds
        const flashMessages = document.querySelectorAll('.alert');
        if (flashMessages.length > 0) {
            flashMessages.forEach(message => {
                setTimeout(() => {
                    // Add fade-out animation
                    message.style.opacity = '0';
                    message.style.transition = 'opacity 0.5s';
                    
                    // Remove element after animation
                    setTimeout(() => {
                        message.remove();
                    }, 500);
                }, 5000);
            });
        }
    }
});
