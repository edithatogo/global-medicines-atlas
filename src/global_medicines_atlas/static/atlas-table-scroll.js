'use strict';

document.addEventListener('keydown', (event) => {
  if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') {
    return;
  }
  const region = event.target.closest('.table-scroll[tabindex]');
  if (!region || region.tabIndex !== 0) {
    return;
  }

  event.preventDefault();
  const direction = event.key === 'ArrowRight' ? 1 : -1;
  region.scrollLeft += direction * Math.max(40, region.clientWidth * 0.8);
});
