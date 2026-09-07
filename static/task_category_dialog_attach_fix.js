(() => {
  if (window.__taskCategoryDialogAttachFixApplied) return;
  window.__taskCategoryDialogAttachFixApplied = true;

  const originalShowModal = HTMLDialogElement.prototype.showModal;

  HTMLDialogElement.prototype.showModal = function (...args) {
    if (!this.isConnected) {
      document.body.appendChild(this);
    }
    return originalShowModal.apply(this, args);
  };
})();
