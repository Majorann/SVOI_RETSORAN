const setupProfileNameFit = () => {
  const nameNode = document.querySelector(".profile-name");
  const contentNode = document.querySelector(".profile-card__content");
  if (!(nameNode instanceof HTMLElement) || !(contentNode instanceof HTMLElement)) return;

  const MAX_FONT_SIZE = 41;
  const MIN_FONT_SIZE = 18;
  const MAX_LETTER_SPACING = 0.12;
  const MIN_LETTER_SPACING = 0.03;

  const fitName = () => {
    nameNode.style.fontSize = `${MAX_FONT_SIZE}px`;
    nameNode.style.letterSpacing = `${MAX_LETTER_SPACING}em`;

    const availableWidth = contentNode.clientWidth;
    if (!availableWidth) return;

    let fontSize = MAX_FONT_SIZE;
    while (fontSize > MIN_FONT_SIZE && nameNode.scrollWidth > availableWidth) {
      fontSize -= 1;
      nameNode.style.fontSize = `${fontSize}px`;
    }

    const fontProgress = (fontSize - MIN_FONT_SIZE) / (MAX_FONT_SIZE - MIN_FONT_SIZE || 1);
    const letterSpacing =
      MIN_LETTER_SPACING + ((MAX_LETTER_SPACING - MIN_LETTER_SPACING) * Math.max(0, Math.min(1, fontProgress)));
    nameNode.style.letterSpacing = `${letterSpacing}em`;

    while (fontSize > MIN_FONT_SIZE && nameNode.scrollWidth > availableWidth) {
      fontSize -= 1;
      nameNode.style.fontSize = `${fontSize}px`;
    }
  };

  fitName();
  window.addEventListener("resize", fitName);
};

export { setupProfileNameFit };
