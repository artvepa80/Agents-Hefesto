/**
 * Hefesto Landing Page - JavaScript
 * Interactive features and utilities
 */

(function() {
  'use strict';

  // ========================================
  // Mobile Menu Toggle
  // ========================================
  const mobileMenuToggle = document.getElementById('mobileMenuToggle');
  const nav = document.querySelector('.nav');

  if (mobileMenuToggle && nav) {
    mobileMenuToggle.addEventListener('click', function() {
      nav.classList.toggle('nav-active');
      this.classList.toggle('active');
    });

    // Close mobile menu when clicking outside
    document.addEventListener('click', function(event) {
      if (!nav.contains(event.target) && !mobileMenuToggle.contains(event.target)) {
        nav.classList.remove('nav-active');
        mobileMenuToggle.classList.remove('active');
      }
    });

    // Close mobile menu when clicking a link
    const navLinks = nav.querySelectorAll('.nav-link');
    navLinks.forEach(function(link) {
      link.addEventListener('click', function() {
        nav.classList.remove('nav-active');
        mobileMenuToggle.classList.remove('active');
      });
    });
  }

  // ========================================
  // Copy to Clipboard
  // ========================================
  const copyButtons = document.querySelectorAll('.copy-btn');

  copyButtons.forEach(function(button) {
    button.addEventListener('click', function() {
      const textToCopy = this.getAttribute('data-copy');
      
      // Create temporary textarea
      const textarea = document.createElement('textarea');
      textarea.value = textToCopy;
      textarea.style.position = 'fixed';
      textarea.style.left = '-9999px';
      document.body.appendChild(textarea);
      
      // Select and copy
      textarea.select();
      textarea.setSelectionRange(0, 99999); // For mobile devices
      
      try {
        document.execCommand('copy');
        
        // Visual feedback
        const originalHTML = this.innerHTML;
        this.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"><polyline points="20 6 9 17 4 12"></polyline></svg>';
        this.style.color = '#10B981';
        
        setTimeout(function() {
          button.innerHTML = originalHTML;
          button.style.color = '';
        }, 2000);
        
      } catch (err) {
        console.error('Failed to copy:', err);
      }
      
      document.body.removeChild(textarea);
    });
  });

  // Modern Clipboard API fallback
  if (navigator.clipboard && navigator.clipboard.writeText) {
    copyButtons.forEach(function(button) {
      button.addEventListener('click', async function(e) {
        e.preventDefault();
        const textToCopy = this.getAttribute('data-copy');
        
        try {
          await navigator.clipboard.writeText(textToCopy);
          
          // Visual feedback
          const originalHTML = this.innerHTML;
          this.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"><polyline points="20 6 9 17 4 12"></polyline></svg>';
          this.style.color = '#10B981';
          
          setTimeout(function() {
            button.innerHTML = originalHTML;
            button.style.color = '';
          }, 2000);
          
        } catch (err) {
          console.error('Failed to copy:', err);
        }
      });
    });
  }

  // ========================================
  // Smooth Scrolling (for older browsers)
  // ========================================
  const smoothScrollLinks = document.querySelectorAll('a[href^="#"]');
  
  smoothScrollLinks.forEach(function(link) {
    link.addEventListener('click', function(e) {
      const href = this.getAttribute('href');
      
      if (href === '#') return;
      
      const target = document.querySelector(href);
      
      if (target) {
        e.preventDefault();
        const headerOffset = 80; // Height of fixed header
        const elementPosition = target.getBoundingClientRect().top;
        const offsetPosition = elementPosition + window.pageYOffset - headerOffset;
        
        window.scrollTo({
          top: offsetPosition,
          behavior: 'smooth'
        });
      }
    });
  });

  // ========================================
  // Header Scroll Effect
  // ========================================
  const header = document.querySelector('.header');
  let lastScroll = 0;

  window.addEventListener('scroll', function() {
    const currentScroll = window.pageYOffset;
    
    if (currentScroll > 50) {
      header.classList.add('header-scrolled');
    } else {
      header.classList.remove('header-scrolled');
    }
    
    lastScroll = currentScroll;
  });

  // ========================================
  // Track CTA Clicks (for analytics)
  // ========================================
  const ctaButtons = document.querySelectorAll('.btn-founding, .btn-primary');
  
  ctaButtons.forEach(function(button) {
    button.addEventListener('click', function() {
      const buttonText = this.textContent.trim();
      const buttonHref = this.getAttribute('href');
      
      // Google Analytics 4
      if (typeof gtag !== 'undefined') {
        gtag('event', 'cta_click', {
          'event_category': 'engagement',
          'event_label': buttonText,
          'value': buttonHref
        });
      }
      
      // Facebook Pixel
      if (typeof fbq !== 'undefined') {
        fbq('track', 'Lead', {
          content_name: buttonText
        });
      }
      
      console.log('CTA Click:', buttonText, buttonHref);
    });
  });

  // ========================================
  // Founding Member Spots Counter (Optional)
  // ========================================
  const spotsElement = document.getElementById('spots-remaining');
  
  if (spotsElement) {
    // This would typically fetch from an API
    // For now, it's static text
    // Future: integrate with Stripe API to show actual spots remaining
    
    /* Example API integration:
    fetch('/api/founding-spots')
      .then(response => response.json())
      .then(data => {
        const spotsLeft = 25 - data.current;
        if (spotsLeft > 0) {
          spotsElement.textContent = `${spotsLeft} spots remaining`;
        } else {
          spotsElement.textContent = 'Sold out!';
          // Disable founding member buttons
          document.querySelectorAll('.btn-founding').forEach(btn => {
            btn.disabled = true;
            btn.style.opacity = '0.5';
            btn.style.cursor = 'not-allowed';
          });
        }
      })
      .catch(err => console.error('Failed to fetch spots:', err));
    */
  }

  // ========================================
  // Form Handling (if you add email capture)
  // ========================================
  const emailForms = document.querySelectorAll('form[data-email-capture]');
  
  emailForms.forEach(function(form) {
    form.addEventListener('submit', async function(e) {
      e.preventDefault();
      
      const email = this.querySelector('input[type="email"]').value;
      const submitButton = this.querySelector('button[type="submit"]');
      const originalText = submitButton.textContent;
      
      submitButton.textContent = 'Subscribing...';
      submitButton.disabled = true;
      
      try {
        // Send to your backend/email service
        const response = await fetch('/api/subscribe', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ email })
        });
        
        if (response.ok) {
          submitButton.textContent = 'Subscribed!';
          submitButton.style.backgroundColor = '#10B981';
          this.reset();
          
          // Track conversion
          if (typeof gtag !== 'undefined') {
            gtag('event', 'sign_up', {
              'method': 'email'
            });
          }
        } else {
          throw new Error('Subscription failed');
        }
        
      } catch (error) {
        console.error('Subscription error:', error);
        submitButton.textContent = 'Try again';
        submitButton.disabled = false;
      }
      
      setTimeout(function() {
        submitButton.textContent = originalText;
        submitButton.disabled = false;
        submitButton.style.backgroundColor = '';
      }, 3000);
    });
  });

  // ========================================
  // Intersection Observer for Animations
  // ========================================
  const observerOptions = {
    threshold: 0.1,
    rootMargin: '0px 0px -50px 0px'
  };

  const observer = new IntersectionObserver(function(entries) {
    entries.forEach(function(entry) {
      if (entry.isIntersecting) {
        entry.target.classList.add('fade-in');
        observer.unobserve(entry.target);
      }
    });
  }, observerOptions);

  // Observe elements for fade-in animation
  const animateElements = document.querySelectorAll('.feature-card, .pricing-card, .faq-item');
  animateElements.forEach(function(el) {
    observer.observe(el);
  });

  // ========================================
  // Price Toggle (Monthly/Annual) - Optional
  // ========================================
  const priceToggle = document.getElementById('price-toggle');
  
  if (priceToggle) {
    priceToggle.addEventListener('change', function() {
      const isAnnual = this.checked;
      
      // Update prices
      document.querySelectorAll('[data-monthly-price]').forEach(function(el) {
        const monthlyPrice = el.getAttribute('data-monthly-price');
        const annualPrice = el.getAttribute('data-annual-price');
        el.textContent = isAnnual ? annualPrice : monthlyPrice;
      });
      
      // Update CTAs
      document.querySelectorAll('[data-monthly-link]').forEach(function(el) {
        const monthlyLink = el.getAttribute('data-monthly-link');
        const annualLink = el.getAttribute('data-annual-link');
        el.setAttribute('href', isAnnual ? annualLink : monthlyLink);
      });
    });
  }

  // ========================================
  // Console Message (for fun)
  // ========================================
  console.log(
    '%c🔥 Hefesto %c- Built for developers who ship fast',
    'font-size: 24px; font-weight: bold; color: #5469D4;',
    'font-size: 14px; color: #6B7280;'
  );
  console.log(
    '%cInterested in joining our team? Email us: contact@narapallc.com',
    'font-size: 12px; color: #9CA3AF;'
  );

})();

