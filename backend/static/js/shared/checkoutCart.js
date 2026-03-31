const getCartStorageKey = () => (
  document.body.classList.contains("page-delivery-menu") ? "delivery_cart" : "cart"
);

const loadCart = () => {
  try {
    return JSON.parse(localStorage.getItem(getCartStorageKey()) || "[]");
  } catch {
    return [];
  }
};

const saveCart = (cart) => {
  localStorage.setItem(getCartStorageKey(), JSON.stringify(cart));
};

const normalizeCart = (cart) =>
  cart
    .map((item) => ({
      ...item,
      id: Number(item.id),
      qty: Number(item.qty) || 0,
      price: Number(item.price) || 0,
    }))
    .filter((item) => Number.isFinite(item.id) && item.qty > 0);

export { loadCart, saveCart, normalizeCart };
