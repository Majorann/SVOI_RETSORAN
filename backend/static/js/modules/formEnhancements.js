const formatPhone = (value) => {
  const raw = String(value || "").trim();
  let digits = String(value || "").replace(/\D/g, "");
  if (!digits) return "+7";

  if (digits.startsWith("8") && digits.length >= 11) {
    digits = digits.slice(1);
  } else if (digits.startsWith("7") && (digits.length >= 11 || raw.startsWith("+7"))) {
    digits = digits.slice(1);
  }
  const local = digits.slice(0, 10);

  let result = "+7";
  if (local.length > 0) result += ` ${local.slice(0, 3)}`;
  if (local.length > 3) result += ` ${local.slice(3, 6)}`;
  if (local.length > 6) result += `-${local.slice(6, 8)}`;
  if (local.length > 8) result += `-${local.slice(8, 10)}`;
  return result;
};

const setupFormEnhancements = ({
  phoneInputs = [],
}) => {
  phoneInputs.forEach((input) => {
    const field = input.closest(".field");

    const enforcePhoneMask = () => {
      input.value = formatPhone(input.value);
      input.setCustomValidity("");
    };

    const syncPhoneVisualState = () => {
      const digits = input.value.replace(/\D/g, "");
      const hasPhoneInput = digits.length > 1;
      const isFocused = document.activeElement === input;
      const isValidPhone = digits.length === 11 && digits.startsWith("7");
      if (field) {
        field.classList.toggle("field--phone-partial", !isValidPhone && (isFocused || hasPhoneInput));
        field.classList.toggle("field--phone-valid", isValidPhone);
      }
      input.classList.toggle("is-phone-valid", isValidPhone);
      input.classList.remove("is-card-valid", "is-card-invalid");
      return isValidPhone;
    };

    enforcePhoneMask();
    syncPhoneVisualState();
    input.addEventListener("focus", () => {
      if (!input.value.trim()) input.value = "+7";
      syncPhoneVisualState();
    });
    input.addEventListener("keydown", (event) => {
      const start = input.selectionStart ?? 0;
      const end = input.selectionEnd ?? start;
      const touchesPrefix = start <= 2;
      const deletesAll = start === 0 && end >= input.value.length;
      if ((event.key === "Backspace" || event.key === "Delete") && deletesAll) {
        event.preventDefault();
        input.value = "+7";
        input.setSelectionRange(2, 2);
        syncPhoneVisualState();
        return;
      }
      if ((event.key === "Backspace" || event.key === "Delete") && touchesPrefix) {
        event.preventDefault();
        input.value = formatPhone(input.value);
        input.setSelectionRange(2, 2);
        syncPhoneVisualState();
      }
    });
    input.addEventListener("input", () => {
      enforcePhoneMask();
      syncPhoneVisualState();
    });
    input.addEventListener("blur", () => {
      if (!syncPhoneVisualState()) {
        input.setCustomValidity("Введите номер в формате +7 999 000-00-00");
      } else {
        input.setCustomValidity("");
      }
      input.reportValidity();
    });
  });
};

export { setupFormEnhancements };
