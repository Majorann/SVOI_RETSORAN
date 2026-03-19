const translitMap = {
  "А": "A", "Б": "B", "В": "V", "Г": "G", "Д": "D",
  "Е": "E", "Ё": "YO", "Ж": "ZH", "З": "Z", "И": "I",
  "Й": "Y", "К": "K", "Л": "L", "М": "M", "Н": "N",
  "О": "O", "П": "P", "Р": "R", "С": "S", "Т": "T",
  "У": "U", "Ф": "F", "Х": "KH", "Ц": "TS", "Ч": "CH",
  "Ш": "SH", "Щ": "SHCH", "Ъ": "", "Ы": "Y", "Ь": "",
  "Э": "E", "Ю": "YU", "Я": "YA",
  "а": "A", "б": "B", "в": "V", "г": "G", "д": "D",
  "е": "E", "ё": "YO", "ж": "ZH", "з": "Z", "и": "I",
  "й": "Y", "к": "K", "л": "L", "м": "M", "н": "N",
  "о": "O", "п": "P", "р": "R", "с": "S", "т": "T",
  "у": "U", "ф": "F", "х": "KH", "ц": "TS", "ч": "CH",
  "ш": "SH", "щ": "SHCH", "ъ": "", "ы": "Y", "ь": "",
  "э": "E", "ю": "YU", "я": "YA",
};

const normalizeHolder = (value, trimTail = false) => {
  const transliterated = Array.from(String(value || ""))
    .map((ch) => (Object.prototype.hasOwnProperty.call(translitMap, ch) ? translitMap[ch] : ch))
    .join("");
  let cleaned = transliterated
    .toUpperCase()
    .replace(/[^A-Z\s-]/g, "")
    .replace(/\s+/g, " ")
    .replace(/^\s+/, "");
  if (trimTail) {
    cleaned = cleaned.trim();
  }
  return cleaned.slice(0, 26);
};

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
  cardNumberInput,
  expiryInput,
  holderInput,
  phoneInputs = [],
}) => {
  const syncCardVisualState = (input, isValid, hasValue) => {
    if (!input) return;
    input.classList.toggle("is-card-valid", Boolean(hasValue && isValid));
    input.classList.toggle("is-card-invalid", Boolean(hasValue && !isValid));
  };

  if (cardNumberInput) {
    const validateCardNumber = () => {
      const digits = cardNumberInput.value.replace(/\D/g, "");
      const isValid = digits.length === 16;
      syncCardVisualState(cardNumberInput, isValid, digits.length > 0);
      return isValid;
    };

    cardNumberInput.addEventListener("input", () => {
      const digits = cardNumberInput.value.replace(/\D/g, "").slice(0, 16);
      const groups = digits.match(/.{1,4}/g) || [];
      cardNumberInput.value = groups.join(" ");
      validateCardNumber();
    });
    cardNumberInput.addEventListener("blur", validateCardNumber);
  }

  if (expiryInput) {
    const validateExpiryInput = () => {
      const raw = (expiryInput.value || "").trim();
      if (!raw) {
        expiryInput.setCustomValidity("");
        syncCardVisualState(expiryInput, false, false);
        return;
      }
      const match = raw.match(/^(\d{2})\/(\d{2})$/);
      if (!match) {
        expiryInput.setCustomValidity("Введите срок в формате MM/YY");
        syncCardVisualState(expiryInput, false, true);
        return;
      }
      const month = Number(match[1]);
      const year = Number(match[2]);
      if (month < 1 || month > 12) {
        expiryInput.setCustomValidity("Месяц должен быть от 01 до 12");
        syncCardVisualState(expiryInput, false, true);
        return;
      }
      const now = new Date();
      const currentMonth = now.getMonth() + 1;
      const currentYear = now.getFullYear() % 100;
      if (year < currentYear || (year === currentYear && month < currentMonth)) {
        expiryInput.setCustomValidity("Срок карты в прошлом");
        syncCardVisualState(expiryInput, false, true);
        return;
      }
      expiryInput.setCustomValidity("");
      syncCardVisualState(expiryInput, true, true);
    };

    expiryInput.addEventListener("input", () => {
      const digits = expiryInput.value.replace(/\D/g, "").slice(0, 4);
      if (digits.length >= 3) {
        expiryInput.value = `${digits.slice(0, 2)}/${digits.slice(2)}`;
      } else {
        expiryInput.value = digits;
      }
      validateExpiryInput();
    });

    expiryInput.addEventListener("blur", () => {
      const digits = expiryInput.value.replace(/\D/g, "");
      if (digits.length >= 2) {
        const month = Math.min(Math.max(parseInt(digits.slice(0, 2), 10) || 1, 1), 12);
        const year = digits.slice(2, 4);
        expiryInput.value = `${String(month).padStart(2, "0")}${year ? `/${year}` : ""}`;
      }
      validateExpiryInput();
    });
  }

  if (holderInput) {
    const validateHolderInput = () => {
      const value = holderInput.value.trim();
      const isValid = value.length >= 2;
      syncCardVisualState(holderInput, isValid, value.length > 0);
      return isValid;
    };

    holderInput.addEventListener("input", () => {
      holderInput.value = normalizeHolder(holderInput.value, false);
      validateHolderInput();
    });
    holderInput.addEventListener("blur", () => {
      holderInput.value = normalizeHolder(holderInput.value, true);
      validateHolderInput();
    });
  }

  phoneInputs.forEach((input) => {
    const enforcePhoneMask = () => {
      input.value = formatPhone(input.value);
      input.setCustomValidity("");
    };

    const syncPhoneVisualState = () => {
      const digits = input.value.replace(/\D/g, "");
      const isValidPhone = digits.length === 11 && digits.startsWith("7");
      input.classList.toggle("is-phone-valid", isValidPhone);
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
      if ((event.key === "Backspace" || event.key === "Delete") && (touchesPrefix || deletesAll)) {
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
