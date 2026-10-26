(() => {
  'use strict';

  // Change these three values to update every contact link and label on the page.
  const contact = Object.freeze({
    whatsappNumber: '972528337144',
    whatsappMessage: 'היי ירדן, אשמח לתאם שיחת היכרות',
    email: 'r.yarden@gmail.com',
  });

  function formatPhoneNumber(number) {
    const digits = String(number).replace(/\D/g, '').replace(/^00/, '');
    const local = digits.startsWith('972') ? `0${digits.slice(3)}` : digits;

    if (/^0\d{9}$/.test(local)) return `${local.slice(0, 3)}-${local.slice(3)}`;
    if (/^0[23489]\d{7}$/.test(local)) return `${local.slice(0, 2)}-${local.slice(2)}`;
    return digits.startsWith('0') ? digits : `+${digits}`;
  }

  function initializeContacts() {
    const whatsappUrl = `https://wa.me/${contact.whatsappNumber}?text=${encodeURIComponent(contact.whatsappMessage)}`;

    document.querySelectorAll('[data-contact="whatsapp"]').forEach((link) => {
      link.href = whatsappUrl;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
    });

    document.querySelectorAll('[data-contact="email"]').forEach((link) => {
      link.href = `mailto:${contact.email}`;
      link.removeAttribute('target');
    });

    document.querySelectorAll('[data-contact-label="email"]').forEach((label) => {
      label.textContent = contact.email;
    });

    document.querySelectorAll('[data-contact-label="phone"]').forEach((label) => {
      label.textContent = formatPhoneNumber(contact.whatsappNumber);
    });

    // Reveal live desktop labels if the owner edits the original contact details.
    // Default labels remain transparent over the pixel-identical source artwork.
    document.querySelectorAll('[data-design-label]').forEach((label) => {
      label.classList.toggle('contact-label--updated', label.textContent !== label.dataset.designLabel);
    });

    const trigger = document.getElementById('terms-trigger');
    const popover = document.getElementById('terms-popover');
    if (!trigger || !popover) return;

    function setTermsOpen(open) {
      popover.hidden = !open;
      trigger.setAttribute('aria-expanded', String(open));
    }

    trigger.setAttribute('aria-controls', popover.id);
    setTermsOpen(false);

    trigger.addEventListener('click', () => {
      setTermsOpen(popover.hidden);
    });

    document.addEventListener('click', (event) => {
      if (!trigger.contains(event.target) && !popover.contains(event.target)) {
        setTermsOpen(false);
      }
    });

    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && !popover.hidden) {
        setTermsOpen(false);
        trigger.focus();
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeContacts, { once: true });
  } else {
    initializeContacts();
  }
})();
