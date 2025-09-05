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

// Function to add "Ask Carebot" text to the header
function addAskCarebotToHeader() {
  const header = document.getElementById('header');
  
  if (header && !header.querySelector('.ask-carebot-text')) {
    // Create the text element
    const askCarebotText = document.createElement('div');
    askCarebotText.className = 'ask-carebot-text';
    askCarebotText.textContent = 'Ask Carebot';
    askCarebotText.style.cssText = `
      position: absolute;
      left: 50%;
      top: 50%;
      transform: translate(-50%, -50%);
      font-size: 2.4rem;
      font-weight: 600;
      color: hsl(var(--muted-foreground));
      pointer-events: none;
      z-index: 10;
    `;
    
    // Ensure header has relative positioning
    if (window.getComputedStyle(header).position === 'static') {
      header.style.position = 'relative';
    }
    
    // Add the text to the header
    header.appendChild(askCarebotText);
    console.log('Ask Carebot text added to header');
  } else if (!header) {
    // If header doesn't exist yet, check again after a short delay
    setTimeout(addAskCarebotToHeader, 300);
  }
}

// Also use a MutationObserver to catch dynamically added elements
const observer = new MutationObserver(function(mutations) {
  for (const mutation of mutations) {
    if (mutation.addedNodes.length) {
      waitForReadmeButton();
      addAskCarebotToHeader();
    }
  }
});

// Start observing once the DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', function() {
    addAskCarebotToHeader();
    observer.observe(document.body, { childList: true, subtree: true });
  });
} else {
  addAskCarebotToHeader();
  observer.observe(document.body, { childList: true, subtree: true });
}
