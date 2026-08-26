export function createProgressionController({
  dialog,
  titleElement,
  messageElement,
  progressBarElement,
  progressValueElement,
  mainProgressElement = null,
  mainProgressLabelElement = null
} = {}) {
  function forceOpenState() {
    if (!dialog) return;
    dialog.setAttribute("open", "open");
    dialog.dataset.visible = "true";
  }

  function clearOpenState() {
    if (!dialog) return;
    dialog.removeAttribute("open");
    delete dialog.dataset.visible;
  }

  function open(title, message) {
    if (titleElement) {
      titleElement.textContent = title;
    }
    if (messageElement) {
      messageElement.textContent = message;
    }
    if (progressBarElement) {
      progressBarElement.value = 0;
    }
    if (progressValueElement) {
      progressValueElement.textContent = "0%";
    }
    if (dialog && !dialog.open) {
      if (typeof dialog.showModal === "function") {
        try {
          dialog.showModal();
          forceOpenState();
          return;
        } catch (_error) {
        }
      }
      if (typeof dialog.show === "function") {
        try {
          dialog.show();
          forceOpenState();
          return;
        } catch (_error) {
        }
      }
      forceOpenState();
    } else if (dialog?.open) {
      forceOpenState();
    }
  }

  function close() {
    if (dialog?.open) {
      if (typeof dialog.close === "function") {
        try {
          dialog.close();
        } catch (_error) {
        }
      }
    }
    clearOpenState();
  }

  function set(value, message = null) {
    if (mainProgressElement) {
      mainProgressElement.value = value;
    }
    if (mainProgressLabelElement) {
      mainProgressLabelElement.textContent = `${value}%`;
    }
    if (progressBarElement) {
      progressBarElement.value = value;
    }
    if (progressValueElement) {
      progressValueElement.textContent = `${value}%`;
    }
    if (message && messageElement) {
      messageElement.textContent = message;
    }
  }

  return {
    open,
    close,
    set
  };
}

export function closeParameterDialogs(dialogs = []) {
  dialogs.forEach((dialog) => {
    if (dialog?.open) {
      dialog.close();
    }
  });
}
