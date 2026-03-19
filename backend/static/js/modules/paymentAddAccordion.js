const setupPaymentAddAccordion = () => {
  const details = document.querySelector(".payment-add");
  if (!(details instanceof HTMLDetailsElement)) return;

  const summary = details.querySelector("summary");
  const content = details.querySelector(".payment-add__content");
  if (!(summary instanceof HTMLElement) || !(content instanceof HTMLElement)) return;

  let isAnimating = false;

  const setCollapsedState = () => {
    content.style.maxHeight = "0px";
    content.style.opacity = "0";
    content.style.transform = "translateY(-6px)";
    summary.setAttribute("aria-expanded", "false");
  };

  const setExpandedState = () => {
    content.style.maxHeight = "none";
    content.style.opacity = "1";
    content.style.transform = "translateY(0)";
    summary.setAttribute("aria-expanded", "true");
  };

  if (details.open) {
    setExpandedState();
  } else {
    setCollapsedState();
  }

  const finishExpand = (event) => {
    if (event.target !== content || event.propertyName !== "max-height") return;
    content.removeEventListener("transitionend", finishExpand);
    isAnimating = false;
    details.dataset.animating = "false";
    setExpandedState();
  };

  const finishCollapse = (event) => {
    if (event.target !== content || event.propertyName !== "max-height") return;
    content.removeEventListener("transitionend", finishCollapse);
    isAnimating = false;
    details.dataset.animating = "false";
    details.open = false;
    setCollapsedState();
  };

  const expand = () => {
    if (isAnimating) return;
    isAnimating = true;
    details.dataset.animating = "true";
    details.open = true;
    summary.setAttribute("aria-expanded", "true");
    content.style.maxHeight = "0px";
    content.style.opacity = "0";
    content.style.transform = "translateY(-6px)";

    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        content.addEventListener("transitionend", finishExpand);
        content.style.maxHeight = `${content.scrollHeight}px`;
        content.style.opacity = "1";
        content.style.transform = "translateY(0)";
      });
    });
  };

  const collapse = () => {
    if (isAnimating) return;
    isAnimating = true;
    details.dataset.animating = "true";
    summary.setAttribute("aria-expanded", "false");
    content.style.maxHeight = `${content.scrollHeight}px`;
    content.style.opacity = "1";
    content.style.transform = "translateY(0)";
    void content.offsetHeight;

    content.addEventListener("transitionend", finishCollapse);
    content.style.maxHeight = "0px";
    content.style.opacity = "0";
    content.style.transform = "translateY(-6px)";
  };

  summary.addEventListener("click", (event) => {
    event.preventDefault();
    if (details.open) {
      collapse();
      return;
    }
    expand();
  });

  window.addEventListener("resize", () => {
    if (!details.open || isAnimating) return;
    content.style.maxHeight = "none";
  });
};

export { setupPaymentAddAccordion };
