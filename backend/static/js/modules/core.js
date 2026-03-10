// Simple stagger animation helper
const stagger = (selector, step = 120) => {
  document.querySelectorAll(selector).forEach((el, index) => {
    el.style.animationDelay = `${index * step}ms`;
  });
};

const getCsrfToken = () =>
  document.querySelector('meta[name="csrf-token"]')?.getAttribute("content")?.trim() || "";
export { stagger, getCsrfToken };

