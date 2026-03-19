const DELIVERY_CART_KEY = "delivery_cart";
const DELIVERY_SERVICE_FEE = 42;

const loadDeliveryCart = () => {
  try {
    const parsed = JSON.parse(localStorage.getItem(DELIVERY_CART_KEY) || "[]");
    if (!Array.isArray(parsed)) return [];
    return parsed;
  } catch {
    return [];
  }
};

const saveDeliveryCart = (cart) => {
  localStorage.setItem(DELIVERY_CART_KEY, JSON.stringify(cart));
};

const normalizeCart = (cart) =>
  cart
    .map((item) => ({
      id: Number(item.id),
      name: String(item.name || "Позиция"),
      price: Number(item.price) || 0,
      qty: Number(item.qty) || 0,
      photo: String(item.photo || ""),
    }))
    .filter((item) => Number.isFinite(item.id) && item.qty > 0);

const upsertCartItem = (rawItem) => {
  const cart = normalizeCart(loadDeliveryCart());
  const existing = cart.find((item) => item.id === rawItem.id);
  if (existing) {
    existing.qty += 1;
  } else {
    cart.push({ ...rawItem, qty: 1 });
  }
  saveDeliveryCart(cart);
  return cart;
};

const updateMenuButtons = (cart) => {
  const ids = new Set(cart.map((item) => item.id));
  document.querySelectorAll(".delivery-add-button").forEach((button) => {
    const id = Number(button.dataset.id);
    const inCart = ids.has(id);
    button.classList.toggle("is-remove", inCart);
    button.textContent = inCart ? "В корзине" : "В корзину";
  });
};

const setupDeliveryMenu = () => {
  const menuRoot = document.querySelector(".page-delivery-menu");
  if (!menuRoot) return;

  const listNode = document.getElementById("deliveryCartList");
  const emptyNode = document.getElementById("deliveryCartEmpty");
  const totalNode = document.getElementById("deliveryCartTotal");
  const countNode = document.getElementById("deliveryCartCount");
  const checkoutLink = document.getElementById("deliveryGoCheckout");
  if (!listNode || !totalNode || !countNode || !checkoutLink) return;

  const render = () => {
    const cart = normalizeCart(loadDeliveryCart());
    const count = cart.reduce((sum, item) => sum + item.qty, 0);
    const total = cart.reduce((sum, item) => sum + item.qty * item.price, 0);

    listNode.innerHTML = "";
    cart.forEach((item) => {
      const row = document.createElement("div");
      row.className = "delivery-cart-row";
      row.innerHTML = `
        <div class="delivery-cart-row__meta">
          <p>${item.name}</p>
          <small>${item.price} ₽</small>
        </div>
        <div class="delivery-cart-row__actions">
          <button type="button" data-action="dec" data-id="${item.id}">−</button>
          <span>${item.qty}</span>
          <button type="button" data-action="inc" data-id="${item.id}">+</button>
        </div>
      `;
      listNode.appendChild(row);
    });

    countNode.textContent = String(count);
    totalNode.textContent = String(total);
    if (emptyNode) emptyNode.hidden = count > 0;
    checkoutLink.classList.toggle("is-disabled", count === 0);
    checkoutLink.setAttribute("aria-disabled", count === 0 ? "true" : "false");
    updateMenuButtons(cart);
  };

  document.querySelectorAll(".delivery-add-button").forEach((button) => {
    button.addEventListener("click", () => {
      const id = Number(button.dataset.id);
      const cart = normalizeCart(loadDeliveryCart());
      const exists = cart.some((item) => item.id === id);
      if (exists) {
        const next = cart.filter((item) => item.id !== id);
        saveDeliveryCart(next);
        render();
        return;
      }
      upsertCartItem({
        id,
        name: button.dataset.name || "Позиция",
        price: Number(button.dataset.price) || 0,
        photo: button.dataset.photo || "",
      });
      render();
    });
  });

  listNode.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-action]");
    if (!button) return;
    const id = Number(button.dataset.id);
    const action = button.dataset.action;
    const cart = normalizeCart(loadDeliveryCart());
    const row = cart.find((item) => item.id === id);
    if (!row) return;

    if (action === "inc") {
      row.qty += 1;
    } else if (action === "dec") {
      row.qty -= 1;
    }
    saveDeliveryCart(cart.filter((item) => item.qty > 0));
    render();
  });

  checkoutLink.addEventListener("click", (event) => {
    const cart = normalizeCart(loadDeliveryCart());
    if (cart.length > 0) return;
    event.preventDefault();
  });

  render();
};

const setupDeliveryCheckout = () => {
  const checkoutRoot = document.querySelector(".page-delivery-checkout");
  if (!checkoutRoot) return;

  const form = document.getElementById("deliveryCheckoutForm");
  const itemsJson = document.getElementById("deliveryItemsJson");
  const submitButton = document.getElementById("deliverySubmit");
  const itemsTotalNode = document.getElementById("deliveryCheckoutItemsTotal");
  const serviceFeeNode = document.getElementById("deliveryCheckoutServiceFee");
  const payableNode = document.getElementById("deliveryCheckoutPayable");
  const commentNode = document.getElementById("deliveryComment");
  const commentCountNode = document.getElementById("deliveryCommentCount");
  if (!form || !itemsJson || !submitButton) {
    return;
  }

  const updateCommentCounter = () => {
    if (!commentNode || !commentCountNode) return;
    commentCountNode.textContent = String(commentNode.value.length);
  };

  const syncCartPayload = () => {
    const cart = normalizeCart(loadDeliveryCart());
    const itemsTotal = cart.reduce((sum, item) => sum + (Number(item.qty) * Number(item.price)), 0);
    const payableTotal = itemsTotal + DELIVERY_SERVICE_FEE;
    submitButton.disabled = cart.length === 0;
    itemsJson.value = JSON.stringify(cart.map((item) => ({ id: item.id, qty: item.qty })));
    if (itemsTotalNode) itemsTotalNode.textContent = `${itemsTotal} ₽`;
    if (serviceFeeNode) serviceFeeNode.textContent = `${DELIVERY_SERVICE_FEE} ₽`;
    if (payableNode) payableNode.textContent = `${payableTotal} ₽`;
    return cart;
  };

  form.addEventListener("submit", (event) => {
    const cart = syncCartPayload();
    if (!cart.length) {
      event.preventDefault();
      return;
    }
    if (!form.checkValidity()) {
      event.preventDefault();
      form.reportValidity();
      return;
    }
  });

  commentNode?.addEventListener("input", updateCommentCounter);
  updateCommentCounter();
  syncCartPayload();
};

const clearDeliveryCartOnSuccess = () => {
  const params = new URLSearchParams(window.location.search);
  if (params.get("delivery") !== "1" || params.get("paid") !== "1") return;
  localStorage.removeItem(DELIVERY_CART_KEY);
};

const setupDeliveryFlow = () => {
  setupDeliveryMenu();
  setupDeliveryCheckout();
  clearDeliveryCartOnSuccess();
};

export { setupDeliveryFlow };
