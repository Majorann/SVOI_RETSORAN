// Menu hover mood: push dish photo to whole-page background
const setupMenuHoverMood = () => {
  const cards = document.querySelectorAll(".menu-card--menu");
  if (!cards.length) return;
  const body = document.body;
  const colorCache = new Map();
  const fallbackRgb = "218, 119, 86";
  let activeMoodId = 0;
  let clearMoodTimer = null;

  const clamp = (value) => Math.max(0, Math.min(255, Math.round(value)));
  const extractUrl = (cssUrlValue) => {
    const match = cssUrlValue.match(/url\((['"]?)(.*?)\1\)/);
    return match ? match[2] : null;
  };

  const colorFromImage = (url) => new Promise((resolve) => {
    if (!url) {
      resolve(fallbackRgb);
      return;
    }
    if (colorCache.has(url)) {
      resolve(colorCache.get(url));
      return;
    }

    const image = new Image();
    image.crossOrigin = "anonymous";
    image.onload = () => {
      try {
        const canvas = document.createElement("canvas");
        const side = 26;
        canvas.width = side;
        canvas.height = side;
        const ctx = canvas.getContext("2d", { willReadFrequently: true });
        if (!ctx) throw new Error("Canvas 2D context unavailable");

        ctx.drawImage(image, 0, 0, side, side);
        const pixels = ctx.getImageData(0, 0, side, side).data;
        let red = 0;
        let green = 0;
        let blue = 0;
        let weightTotal = 0;

        for (let i = 0; i < pixels.length; i += 4) {
          const alpha = pixels[i + 3] / 255;
          if (alpha < 0.12) continue;
          const luma = (pixels[i] + pixels[i + 1] + pixels[i + 2]) / 3;
          const contrastWeight = 0.55 + (Math.abs(128 - luma) / 255) * 0.45;
          const weight = alpha * contrastWeight;
          red += pixels[i] * weight;
          green += pixels[i + 1] * weight;
          blue += pixels[i + 2] * weight;
          weightTotal += weight;
        }

        if (!weightTotal) throw new Error("No visible pixels");
        const r = clamp((red / weightTotal) * 1.08 + 8);
        const g = clamp((green / weightTotal) * 1.06 + 6);
        const b = clamp((blue / weightTotal) * 1.08 + 8);
        const rgb = `${r}, ${g}, ${b}`;
        colorCache.set(url, rgb);
        resolve(rgb);
      } catch {
        colorCache.set(url, fallbackRgb);
        resolve(fallbackRgb);
      }
    };
    image.onerror = () => {
      colorCache.set(url, fallbackRgb);
      resolve(fallbackRgb);
    };
    image.src = url;
  });

  const applyMood = (rgb) => {
    if (clearMoodTimer) {
      window.clearTimeout(clearMoodTimer);
      clearMoodTimer = null;
    }
    body.style.setProperty("--menu-hover-rgb", rgb);
    body.style.setProperty("--menu-neon-rgb", rgb);
    body.classList.add("menu-photo-hover");
  };

  const activateMood = async (card) => {
    activeMoodId += 1;
    const moodId = activeMoodId;
    const imageNode = card.querySelector(".menu-card__image");
    const inlinePhoto = getComputedStyle(card).getPropertyValue("--dish-photo").trim();
    const photoUrl = imageNode?.currentSrc || imageNode?.getAttribute("src") || extractUrl(inlinePhoto);
    const rgb = await colorFromImage(photoUrl);
    if (moodId !== activeMoodId) return;
    applyMood(rgb);
  };

  const deactivateMood = () => {
    if (document.querySelector(".menu-card--menu:hover, .menu-card--menu:focus-within")) return;
    activeMoodId += 1;
    body.classList.remove("menu-photo-hover");
    if (clearMoodTimer) {
      window.clearTimeout(clearMoodTimer);
    }
    // Keep current color during fade-out to avoid bright flicker.
    clearMoodTimer = window.setTimeout(() => {
      if (document.querySelector(".menu-card--menu:hover, .menu-card--menu:focus-within")) return;
      body.style.removeProperty("--menu-hover-rgb");
      body.style.removeProperty("--menu-neon-rgb");
      clearMoodTimer = null;
    }, 760);
  };

  cards.forEach((card) => {
    card.addEventListener("mouseenter", () => activateMood(card));
    card.addEventListener("mouseleave", () => window.setTimeout(deactivateMood, 30));
    card.addEventListener("focusin", () => activateMood(card));
    card.addEventListener("focusout", () => window.setTimeout(deactivateMood, 30));
  });
};

export { setupMenuHoverMood };
