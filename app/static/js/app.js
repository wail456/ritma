/* Interaksi kecil di luar HTMX. Tidak ada inline script (CSP: script-src 'self'). */
(function () {
  "use strict";

  /* ----- Filter kategori pada daftar habit ----- */
  var activeFilter = "all";

  function applyFilter() {
    document.querySelectorAll("#habit-list .habit-row").forEach(function (row) {
      row.hidden = activeFilter !== "all" && row.dataset.category !== activeFilter;
    });
    document.querySelectorAll(".chip[data-filter]").forEach(function (chip) {
      chip.setAttribute("aria-pressed", String(chip.dataset.filter === activeFilter));
    });
  }

  document.addEventListener("click", function (event) {
    var chip = event.target.closest(".chip[data-filter]");
    if (chip) {
      activeFilter = chip.dataset.filter;
      applyFilter();
      return;
    }

    /* ----- Dialog ----- */
    var opener = event.target.closest("[data-dialog-open]");
    if (opener) {
      var dialog = document.getElementById(opener.dataset.dialogOpen);
      if (dialog && typeof dialog.showModal === "function") {
        dialog.showModal();
        var first = dialog.querySelector("input[type='text'], textarea");
        if (first) first.focus();
      }
      return;
    }
    if (event.target.closest("[data-dialog-close]")) {
      var open = event.target.closest("dialog");
      if (open) open.close();
      return;
    }
    /* klik di area gelap (backdrop) menutup dialog */
    if (event.target.tagName === "DIALOG") {
      event.target.close();
      return;
    }

    /* ----- Tutup menu dropdown saat klik di luar ----- */
    document.querySelectorAll("details.menu[open]").forEach(function (menu) {
      if (!menu.contains(event.target)) menu.removeAttribute("open");
    });
  });

  /* ----- Konfirmasi sebelum aksi yang berisiko (mis. arsipkan) -----
     Memakai <dialog> bertema Ritma, bukan kotak konfirmasi bawaan browser. Form ditahan dulu;
     hanya kalau user menekan tombol konfirmasi, form dikirim (form.submit()
     tidak memicu event submit lagi, jadi tidak ada loop). */
  var pendingForm = null;
  var confirmDialog = null;

  document.addEventListener("submit", function (event) {
    var form = event.target;
    var message = form.getAttribute && form.getAttribute("data-confirm");
    if (!message) return;
    confirmDialog = confirmDialog || document.getElementById("confirm-dialog");
    if (!confirmDialog || typeof confirmDialog.showModal !== "function") return; /* fallback: kirim langsung */
    event.preventDefault();
    pendingForm = form;
    document.getElementById("confirm-message").textContent = message;
    confirmDialog.showModal();
  });

  document.addEventListener("click", function (event) {
    if (event.target.closest("[data-confirm-ok]")) {
      var form = pendingForm;
      pendingForm = null;
      if (confirmDialog) confirmDialog.close();
      if (form) form.submit();
    } else if (event.target.closest("[data-confirm-cancel]")) {
      pendingForm = null;
      if (confirmDialog) confirmDialog.close();
    }
  });

  document.addEventListener("close", function (event) {
    if (event.target && event.target.id === "confirm-dialog") pendingForm = null;
  }, true);

  /* ----- Esc menutup menu dropdown yang terbuka ----- */
  document.addEventListener("keydown", function (event) {
    if (event.key !== "Escape") return;
    document.querySelectorAll("details.menu[open]").forEach(function (menu) {
      menu.removeAttribute("open");
      var summary = menu.querySelector("summary");
      if (summary) summary.focus();
    });
  });

  /* ----- Heatmap: tampilkan sisi paling kanan (minggu terbaru) saat di layar sempit ----- */
  function scrollHeatmap() {
    var box = document.querySelector(".heatmap-scroll");
    if (box) box.scrollLeft = box.scrollWidth;
  }
  document.addEventListener("DOMContentLoaded", function () {
    scrollHeatmap();
    applyFilter();
  });
  /* Heatmap diganti HTMX setelah centang, jadi posisi scroll-nya di-reset ke minggu terbaru lagi. */
  document.body && document.body.addEventListener("htmx:afterSwap", scrollHeatmap);
})();
