document.addEventListener('DOMContentLoaded', function() {
    // Get all toggle buttons
    const toggleButtons = document.querySelectorAll('.sources-toggle');
    
    // Add click event listener to each button
    toggleButtons.forEach(toggle => {
        toggle.addEventListener('click', function() {
            const isExpanded = toggle.getAttribute('aria-expanded') === 'true';
            const contentId = toggle.id.replace('Toggle', 'Content');
            const content = document.getElementById(contentId);
            
            toggle.setAttribute('aria-expanded', !isExpanded);
            content.classList.toggle('open');
        });
    });
});