// ====================================================
// CONFETTI ANIMATION — TRELLO STYLE
// ====================================================
(function() {
  // Wait for the HTML to load before running
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initConfetti);
  } else {
    initConfetti();
  }

  function initConfetti() {
    // Check conditions for confetti
    const isLoggedIn = window.USER_IS_AUTHENTICATED;
    const eventDate = window.EVENT_DATE;
    const shouldShowConfetti = isLoggedIn && eventDate !== null && eventDate !== 'None';

    console.log('🔍 Confetti Debug:');
    console.log('  - isLoggedIn:', isLoggedIn);
    console.log('  - eventDate:', eventDate);
    console.log('  - shouldShowConfetti:', shouldShowConfetti);

    // IMPORTANT: If conditions aren't met, unlock the page and STOP immediately
    if (!shouldShowConfetti) {
      console.log('❌ Confetti will NOT show - conditions not met');
      document.body.style.overflow = '';
      document.documentElement.style.overflow = '';
      return;
    }

    console.log('✅ Confetti will show! 🎉');

    // DOM refs
    const overlay = document.getElementById('confetti-overlay');
    const messageEl = document.getElementById('confetti-message');
    const canvas = document.getElementById('confetti-canvas');

    // CRITICAL FIX: Wait for canvas to exist
    if (!canvas) {
      console.error('❌ Canvas element not found! Retrying...');
      setTimeout(initConfetti, 100); // Try again in 100ms
      return;
    }

    const ctx = canvas.getContext('2d');

    if (!overlay || !messageEl || !ctx) {
      console.error('❌ Required DOM elements or context not found!');
      document.body.style.overflow = '';
      document.documentElement.style.overflow = '';
      return;
    }

    // ====================================================
    // FORCE SCROLL TO TOP AND LOCK IT
    // ====================================================
    setTimeout(function() {
      if ('scrollRestoration' in history) {
        history.scrollRestoration = 'manual';
      }
      window.scrollTo(0, 0);
      document.body.style.overflow = 'hidden';
      document.documentElement.style.overflow = 'hidden';
    }, 1);

    // Activate overlay and message
    overlay.classList.add('active');

    if (messageEl) {
      messageEl.classList.add('active');
      messageEl.style.display = 'flex'; // Force it to be visible
    } else {
      console.error('❌ Could not find element with id="confetti-message"');
    }

    console.log('✅ Overlay and message activated');

    // ─── Single source of truth for "is the celebration still on" ───
    // Both the close button and the auto-timeout check/flip this flag,
    // so whichever happens first (manual close or 10s elapsing) reliably
    // stops the other one from doing anything further.
    let isActive = true;

    function closeCelebration() {
      if (!isActive) return; // already closed, avoid double work
      isActive = false;

      overlay.classList.remove('active');
      messageEl.classList.remove('active');

      // IMPORTANT: undo the inline style we forced on open, otherwise
      // it keeps overriding the CSS "display: none" rule and the card
      // stays visible even after removing the 'active' class.
      messageEl.style.display = 'none';

      overlay.style.opacity = '';
      messageEl.style.opacity = '';

      document.body.style.overflow = '';
      document.documentElement.style.overflow = '';

      // Stop drawing and clear whatever confetti is mid-flight
      ctx.clearRect(0, 0, w, h);
    }

    // Setup Close Button Listener
    const closeBtn = document.getElementById('close-confetti-btn');
    if (closeBtn) {
      closeBtn.addEventListener('click', closeCelebration);
    }

    // ─── Configuration ──────────────────────────────
    const NUM_CONFETTI = 50;
    const COLORS = [
      [235, 90, 70], [97, 189, 79], [242, 214, 0], [0, 121, 191], [195, 119, 224], [255, 159, 67], [255, 99, 132]
    ];

    let w = 0, h = 0;
    function resizeCanvas() {
      w = canvas.width = window.innerWidth;
      h = canvas.height = window.innerHeight;
    }
    window.addEventListener('resize', resizeCanvas);
    resizeCanvas();

    function range(a, b) { return (b - a) * Math.random() + a; }

    function drawCircle(x, y, r, color) {
      ctx.beginPath(); ctx.moveTo(x, y);
      ctx.bezierCurveTo(x - 17, y + 14, x + 13, y + 5, x - 5, y + 22);
      ctx.lineWidth = 2; ctx.strokeStyle = color; ctx.stroke();
    }
    function drawCircle2(x, y, r, color) {
      ctx.beginPath(); ctx.moveTo(x, y);
      ctx.lineTo(x + 6, y + 9); ctx.lineTo(x + 12, y); ctx.lineTo(x + 6, y - 9);
      ctx.closePath(); ctx.fillStyle = color; ctx.fill();
    }
    function drawCircle3(x, y, r, color) {
      ctx.beginPath(); ctx.moveTo(x, y);
      ctx.lineTo(x + 5, y + 5); ctx.lineTo(x + 10, y); ctx.lineTo(x + 5, y - 5);
      ctx.closePath(); ctx.fillStyle = color; ctx.fill();
    }

    let xpos = 0.5;
    document.onmousemove = function(e) { if (w) xpos = e.pageX / w; };

    function Confetti() {
      this.style = COLORS[~~range(0, COLORS.length)];
      this.rgb = 'rgba(' + this.style[0] + ',' + this.style[1] + ',' + this.style[2];
      this.r = ~~range(2, 6); this.r2 = 2 * this.r; this.replace();
    }
    Confetti.prototype.replace = function() {
      this.opacity = 0; this.dop = 0.03 * range(1, 4);
      this.x = range(-this.r2, w - this.r2); this.y = range(-20, h - this.r2);
      this.xmax = w - this.r; this.ymax = h - this.r;
      this.vx = range(0, 2) + 8 * xpos - 5; this.vy = 0.7 * this.r + range(-1, 1);
    };
    Confetti.prototype.draw = function() {
      this.x += this.vx; this.y += this.vy; this.opacity += this.dop;
      if (1 < this.opacity) { this.opacity = 1; this.dop *= -1; }
      if (0 > this.opacity || this.y > this.ymax) { this.replace(); }
      if (!(0 < this.x && this.x < this.xmax)) { this.x = (this.x + this.xmax) % this.xmax; }
      const color = this.rgb + ',' + this.opacity + ')';
      drawCircle(~~this.x, ~~this.y, this.r, color);
      drawCircle3(0.5 * ~~this.x, ~~this.y, this.r, color);
      drawCircle2(1.5 * ~~this.x, 1.5 * ~~this.y, this.r, color);
    };

    const confetti = [];
    for (let i = 0; i < NUM_CONFETTI; i++) { confetti.push(new Confetti()); }

    let startTime = Date.now();
    const DURATION = 10000;

    function animate() {
      // If the user already closed it manually, stop the loop entirely —
      // don't keep animating an invisible canvas in the background.
      if (!isActive) return;

      const elapsed = Date.now() - startTime;
      if (elapsed >= DURATION) {
        console.log('⏰ Confetti animation complete');
        closeCelebration();
        return;
      }

      const remaining = DURATION - elapsed;
      if (remaining < 1500) {
        const fadeProgress = remaining / 1500;
        messageEl.style.opacity = fadeProgress; overlay.style.opacity = fadeProgress;
      }

      ctx.clearRect(0, 0, w, h);
      if (w !== window.innerWidth || h !== window.innerHeight) {
        resizeCanvas();
        confetti.forEach(c => { c.xmax = w - c.r; c.ymax = h - c.r; if (c.x > w) c.x = w - c.r; if (c.y > h) c.y = h - c.r; });
      }
      for (let i = 0; i < confetti.length; i++) { confetti[i].draw(); }
      requestAnimationFrame(animate);
    }
    animate();
  }
})();