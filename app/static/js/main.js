/**
 * SchoolBell – main.js
 * Global JavaScript loaded on every page via base.html
 * Note: PDF.js teaching mode logic lives inline in teach.html
 */

document.addEventListener('DOMContentLoaded', function () {

  // ── 1. Flash Message Auto-Dismiss ──────────────────────────────────────────
  // Fade out and remove .alert elements after 4 seconds
  const alerts = document.querySelectorAll('.alert');
  alerts.forEach(function (alert) {
    setTimeout(function () {
      alert.style.transition = 'opacity 0.6s ease';
      alert.style.opacity = '0';
      setTimeout(function () {
        if (alert.parentNode) {
          alert.parentNode.removeChild(alert);
        }
      }, 600);
    }, 4000);
  });


  // ── 2. Quiz Option Button Highlight ────────────────────────────────────────
  // Clicking an .option-btn selects it and sets #chosen-answer
  // (quiz.html also has an inline selectOption() function — this is a safe
  //  enhancement that works independently)
  const optionBtns = document.querySelectorAll('.option-btn');
  const chosenAnswerInput = document.getElementById('chosen-answer');

  optionBtns.forEach(function (btn) {
    btn.addEventListener('click', function () {
      // Remove selected from all siblings
      optionBtns.forEach(function (b) { b.classList.remove('selected'); });
      // Mark this one
      btn.classList.add('selected');
      // Store the value
      if (chosenAnswerInput) {
        chosenAnswerInput.value = btn.dataset.value || '';
      }
    });
  });


  // ── 3. Quiz Countdown Timer ─────────────────────────────────────────────────
  // Only runs on the quiz page where #quiz-timer exists.
  // quiz.html has its own inline timer too — this one is the canonical version
  // that runs if the inline one hasn't already started (guard via window flag).
  const timerEl = document.getElementById('quiz-timer');
  const quizForm = document.getElementById('quiz-form');
  const timeTakenInput = document.getElementById('time-taken');

  if (timerEl && quizForm && !window._quizTimerStarted) {
    window._quizTimerStarted = true;

    const TOTAL_SECONDS = 60;
    let secondsLeft = TOTAL_SECONDS;

    const timerInterval = setInterval(function () {
      secondsLeft--;
      timerEl.textContent = '⏱ ' + secondsLeft + 's';

      if (secondsLeft <= 10) {
        timerEl.classList.add('timer-danger');
      }

      if (secondsLeft <= 0) {
        clearInterval(timerInterval);
        // Record elapsed time
        if (timeTakenInput) {
          timeTakenInput.value = TOTAL_SECONDS;
        }
        // Auto-submit the quiz form
        quizForm.submit();
      }
    }, 1000);

    // Stop timer when form is submitted manually
    quizForm.addEventListener('submit', function () {
      clearInterval(timerInterval);
      if (timeTakenInput) {
        timeTakenInput.value = TOTAL_SECONDS - secondsLeft;
      }
    });
  }


  // ── 4. Confirm Dialog on Destructive Actions ────────────────────────────────
  // Any element with data-confirm="Are you sure?" will prompt before proceeding.
  // Works on both <a> links and <button>/<input type="submit"> elements.
  document.querySelectorAll('[data-confirm]').forEach(function (el) {
    el.addEventListener('click', function (e) {
      const message = el.dataset.confirm || 'Are you sure?';
      if (!window.confirm(message)) {
        e.preventDefault();
        e.stopPropagation();
      }
    });
  });


  // ── 5. File Input Label Update ──────────────────────────────────────────────
  // When a file is chosen via #pdf-input, show filename in #file-chosen.
  const pdfInput = document.getElementById('pdf-input');
  const fileChosen = document.getElementById('file-chosen');

  if (pdfInput && fileChosen) {
    pdfInput.addEventListener('change', function () {
      if (pdfInput.files && pdfInput.files.length > 0) {
        fileChosen.textContent = '📎 ' + pdfInput.files[0].name;
      } else {
        fileChosen.textContent = '';
      }
    });
  }


  // ── 6. Range Slider Live Update ─────────────────────────────────────────────
  // #q-slider value is mirrored live into #q-count text node.
  const qSlider = document.getElementById('q-slider');
  const qCount = document.getElementById('q-count');

  if (qSlider && qCount) {
    qSlider.addEventListener('input', function () {
      qCount.textContent = qSlider.value;
    });
  }

}); // end DOMContentLoaded
