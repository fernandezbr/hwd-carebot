// Custom JavaScript for Chainlit app

// Function to set default theme to light
function setDefaultLightTheme() {
  // Check if theme is already set in localStorage
  const currentTheme = localStorage.getItem('chainlit-theme');
  
  // If no theme is set, default to light
  if (!currentTheme) {
    localStorage.setItem('chainlit-theme', 'light');
    // Apply light theme class to document if it exists
    if (document.documentElement) {
      document.documentElement.classList.remove('dark');
      document.documentElement.classList.add('light');
    }
  }
}

// Set theme as early as possible
setDefaultLightTheme();

// Function to find and modify the readme button
function waitForReadmeButton() {
  // Check if button exists already
  const readmeButton = document.getElementById('readme-button');
  
  if (readmeButton) {
    // Change the text to "Feedback"
    const span = readmeButton.querySelector('span');
    if (span && span.textContent.trim() === 'Readme') {
      span.textContent = 'Feedback';
    }

    // Only add the event listener once
    if (!readmeButton.dataset.feedbackListener) {
      readmeButton.addEventListener('click', function(e) {
        e.preventDefault();
        e.stopPropagation();
        
        // Open the feedback form in a new tab
        window.open('https://forms.office.com/r/0bwLp8VNYu', '_blank');
        
        return false;
      }, true);
      readmeButton.dataset.feedbackListener = 'true';
      console.log('Feedback button is ready');
    }
  } else {
    // If button doesn't exist yet, check again after a short delay
    setTimeout(waitForReadmeButton, 300);
  }
}

// Start looking for the button as soon as possible
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', waitForReadmeButton);
} else {
  waitForReadmeButton();
}

// Also use a MutationObserver to catch dynamically added elements
const observer = new MutationObserver(function(mutations) {
  for (const mutation of mutations) {
    if (mutation.addedNodes.length) {
      waitForReadmeButton();
    }
  }
});

// Start observing once the DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', function() {
    observer.observe(document.body, { childList: true, subtree: true });
  });
} else {
  observer.observe(document.body, { childList: true, subtree: true });
}
