// frontend/script.js (v2 - 用户认证版 - 健壮性更新)

const API_BASE_URL = 'http://localhost:5000/api'; // 后端API基础URL

// --- DOM 元素获取 ---
const menuItemsDiv = document.getElementById('menuItems');
const cartItemsDiv = document.getElementById('cartItems');
const cartTotalSpan = document.getElementById('cartTotal');
const placeOrderBtn = document.getElementById('placeOrderBtn');
const clearCartBtn = document.getElementById('clearCartBtn');

const getSuggestionBtn = document.getElementById('getSuggestionBtn');
const userPreferencesInput = document.getElementById('userPreferences');
const llmSuggestionDiv = document.getElementById('llmSuggestion');

// 消息提示模态框
const messageModal = document.getElementById('messageModal');
const modalMessageText = document.getElementById('modalMessageText');

// 用户认证相关DOM
const userAuthSection = document.getElementById('userAuthSection');
const userInfoSection = document.getElementById('userInfoSection');
const loggedInUsernameSpan = document.getElementById('loggedInUsername');
const loginModal = document.getElementById('loginModal');
const registerModal = document.getElementById('registerModal');
const loginForm = document.getElementById('loginForm');
const registerForm = document.getElementById('registerForm');
const showRegisterModalLink = document.getElementById('showRegisterModalLink');
const showLoginModalLink = document.getElementById('showLoginModalLink');

// 订单相关输入
const paymentMethodSelect = document.getElementById('paymentMethod');
const deliveryAddressInput = document.getElementById('deliveryAddress');
const orderNotesTextarea = document.getElementById('orderNotes');


// 用户历史订单相关DOM
const userOrdersSection = document.getElementById('userOrdersSection');
const myOrdersListDiv = document.getElementById('myOrdersList');
const myOrdersPaginationDiv = document.getElementById('myOrdersPagination');


// --- 全局状态 ---
let cart = []; // 购物车状态
let currentUser = null; // 当前登录用户信息 { id, username, role, access_token, full_name }
let myOrdersCurrentPage = 1;
const MY_ORDERS_PER_PAGE = 5;


// --- 辅助函数 ---
function showModal(message, isError = false) {
    modalMessageText.textContent = message;
    modalMessageText.style.color = isError ? '#ef4444' : '#10b981'; // Tailwind red-500 or emerald-500
    modalMessageText.style.textAlign = 'center'; // 确保消息居中
    messageModal.style.display = 'flex'; // 使用flex居中
}

function closeModal() {
    messageModal.style.display = 'none';
}

function openAuthModal(modalId) {
    if (modalId === 'loginModal') loginModal.style.display = 'flex';
    if (modalId === 'registerModal') registerModal.style.display = 'flex';
}

function closeAuthModal(modalId) {
    if (modalId === 'loginModal') loginModal.style.display = 'none';
    if (modalId === 'registerModal') registerModal.style.display = 'none';
    if (loginForm) loginForm.reset();
    if (registerForm) registerForm.reset();
}

// 获取存储的Token
function getAuthToken() {
    return localStorage.getItem('accessToken');
}

// 保存Token和用户信息
function saveAuthData(token, user) {
    localStorage.setItem('accessToken', token);
    localStorage.setItem('currentUser', JSON.stringify(user)); // 保存整个用户信息对象
    currentUser = user; // 更新全局变量
}

// 清除Token和用户信息
function clearAuthData() {
    localStorage.removeItem('accessToken');
    localStorage.removeItem('currentUser');
    currentUser = null; // 清除全局变量
}

// 封装 fetch 请求，自动添加 Authorization 头
async function fetchWithAuth(url, options = {}) {
    const token = getAuthToken();
    const headers = {
        'Content-Type': 'application/json',
        ...options.headers, // 允许覆盖或添加其他头
    };
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }
    const response = await fetch(url, { ...options, headers });
    return response;
}


// --- 用户界面更新 ---
function updateLoginStateUI() {
    const token = getAuthToken();
    // 尝试从 localStorage 加载 currentUser，如果全局变量中没有的话
    if (!currentUser && token) {
        const storedUser = localStorage.getItem('currentUser');
        if (storedUser) {
            currentUser = JSON.parse(storedUser);
        }
    }
    
    if (token && currentUser) { // 确保currentUser也已设置
        let authButtonsHtml = `
            <button id="myOrdersBtn" class="button button-secondary text-sm py-2 px-3 mr-2"><i class="fas fa-receipt mr-1"></i>我的订单</button>
        `;
        // 如果是管理员，添加管理后台入口
        if (currentUser.role === 'admin') {
            authButtonsHtml += `
                <a href="admin.html" class="button bg-purple-700 hover:bg-purple-800 text-sm py-2 px-3 mr-2"><i class="fas fa-user-shield mr-1"></i>管理后台</a>
            `;
        }
        authButtonsHtml += `
            <button id="logoutBtn" class="button button-danger text-sm py-2 px-3"><i class="fas fa-sign-out-alt mr-1"></i>登出</button>
        `;
        userAuthSection.innerHTML = authButtonsHtml;

        userInfoSection.style.display = 'block';
        loggedInUsernameSpan.textContent = currentUser.full_name || currentUser.username;
        userOrdersSection.style.display = 'block'; // 显示历史订单区域
        fetchMyOrders(); // 登录后获取历史订单

        document.getElementById('logoutBtn').addEventListener('click', handleLogout);
        document.getElementById('myOrdersBtn').addEventListener('click', () => {
            userOrdersSection.scrollIntoView({ behavior: 'smooth' });
            fetchMyOrders(myOrdersCurrentPage); // 点击时也刷新一次
        });
        placeOrderBtn.disabled = false; // 允许下单
        placeOrderBtn.classList.remove('disabled', 'opacity-50', 'cursor-not-allowed');
        placeOrderBtn.title = "";


    } else {
        userAuthSection.innerHTML = `
            <button id="showLoginBtn" class="button text-sm py-2 px-3 mr-2"><i class="fas fa-sign-in-alt mr-1"></i>登录</button>
            <button id="showRegisterBtn" class="button button-secondary text-sm py-2 px-3"><i class="fas fa-user-plus mr-1"></i>注册</button>
        `;
        userInfoSection.style.display = 'none';
        userOrdersSection.style.display = 'none'; // 隐藏历史订单区域
        myOrdersListDiv.innerHTML = '<p class="text-gray-500">请先登录查看历史订单。</p>';
        myOrdersPaginationDiv.innerHTML = '';


        document.getElementById('showLoginBtn').addEventListener('click', () => openAuthModal('loginModal'));
        document.getElementById('showRegisterBtn').addEventListener('click', () => openAuthModal('registerModal'));
        placeOrderBtn.disabled = true; // 未登录时禁止下单
        placeOrderBtn.classList.add('disabled', 'opacity-50', 'cursor-not-allowed');
        placeOrderBtn.title = "请先登录再下单";
    }
}

// --- 用户认证逻辑 ---
async function handleRegister(event) {
    event.preventDefault();
    const formData = new FormData(registerForm);
    const data = Object.fromEntries(formData.entries());

    if (!data.username || !data.password) {
        showModal('用户名和密码不能为空！', true);
        return;
    }
    if (data.password.length < 6) {
        showModal('密码长度至少为6位！', true);
        return;
    }

    try {
        const response = await fetch(`${API_BASE_URL}/auth/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });
        const result = await response.json();
        if (response.ok) {
            showModal('注册成功！现在您可以登录了。');
            closeAuthModal('registerModal');
            openAuthModal('loginModal'); 
        } else {
            showModal(`注册失败: ${result.error || '未知错误'}`, true);
        }
    } catch (error) {
        console.error('注册请求失败:', error);
        showModal('注册请求失败，请检查网络连接。', true);
    }
}

async function handleLogin(event) {
    event.preventDefault();
    const formData = new FormData(loginForm);
    const data = Object.fromEntries(formData.entries());

    if (!data.username || !data.password) {
        showModal('用户名和密码不能为空！', true);
        return;
    }

    try {
        const response = await fetch(`${API_BASE_URL}/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });
        const result = await response.json();
        if (response.ok) {
            saveAuthData(result.access_token, result.user); // 保存Token和用户信息
            showModal('登录成功！');
            closeAuthModal('loginModal');
            updateLoginStateUI();
        } else {
            showModal(`登录失败: ${result.error || '用户名或密码错误'}`, true);
        }
    } catch (error) {
        console.error('登录请求失败:', error);
        showModal('登录请求失败，请检查网络连接。', true);
    }
}

function handleLogout() {
    clearAuthData(); // 清除Token和用户信息
    showModal('您已成功登出。');
    updateLoginStateUI();
    cart = []; 
    renderCart();
}

async function fetchUserProfileOnLoad() {
    const token = getAuthToken();
    if (token) {
        const storedUser = localStorage.getItem('currentUser');
        if (storedUser) {
            currentUser = JSON.parse(storedUser);
        } else {
            // 如果本地没有用户信息，但有token，尝试从后端获取
            try {
                const response = await fetchWithAuth(`${API_BASE_URL}/auth/me`);
                if (response.ok) {
                    const userProfile = await response.json();
                    // 后端返回的profile可能不包含token，所以我们只更新用户信息
                    // token依然使用localStorage中已有的
                    saveAuthData(token, userProfile); // 更新用户信息到localStorage和全局变量
                } else if (response.status === 401) { 
                    clearAuthData(); 
                } else {
                    console.error('获取用户信息失败:', response.statusText);
                    // 不清除token，可能只是临时网络问题，但currentUser会是null
                }
            } catch (error) {
                console.error('请求用户信息时出错:', error);
            }
        }
    }
    updateLoginStateUI(); 
}


// --- 菜单加载 ---
async function fetchMenu() {
    try {
        const response = await fetch(`${API_BASE_URL}/menu`); 
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        const menu = await response.json();
        renderMenu(menu);
    } catch (error) {
        console.error('获取菜单失败:', error);
        menuItemsDiv.innerHTML = '<p class="text-red-500 col-span-full">加载菜单失败，请稍后再试。</p>';
        showModal(`加载菜单失败: ${error.message}`, true);
    }
}

function renderMenu(menu) {
    menuItemsDiv.innerHTML = '';
    if (!menu || menu.length === 0) {
        menuItemsDiv.innerHTML = '<p class="text-gray-500 col-span-full">暂无可售菜品。</p>';
        return;
    }
    menu.forEach(item => {
        if (!item || typeof item.name === 'undefined' || typeof item.price === 'undefined') {
            console.warn('检测到无效的菜单项数据，已跳过渲染:', item);
            return; 
        }

        const itemDiv = document.createElement('div');
        itemDiv.className = 'menu-item'; 
        itemDiv.innerHTML = `
            <img src="${item.image_url || 'https://placehold.co/400x300/E2E8F0/A0AEC0?text=菜品图片'}" alt="${item.name}" onerror="this.onerror=null;this.src='https://placehold.co/400x300/E2E8F0/A0AEC0?text=图片加载失败';">
            <div class="flex-grow flex flex-col p-1">
                <h3 class="menu-item-name mb-1">${item.name}</h3>
                <p class="menu-item-category">${item.category_name || '未分类'}</p>
                <p class="menu-item-description mb-2">${item.description || '暂无描述'}</p>
            </div>
            <div class="mt-auto">
                <p class="menu-item-price">¥${parseFloat(item.price).toFixed(2)}</p>
                <div class="flex items-center mt-2">
                    <label for="qty-${item.id}" class="text-sm mr-2 sr-only">数量:</label>
                    <input type="number" id="qty-${item.id}" value="1" min="1" class="w-16 p-1.5 border border-gray-300 rounded-md text-sm focus:ring-purple-500 focus:border-purple-500">
                    <button class="button text-sm py-1.5 px-3 ml-2 flex-grow" onclick="addToCart(${item.id}, '${String(item.name).replace(/'/g, "\\'")}', ${item.price}, 'qty-${item.id}')">
                        <i class="fas fa-cart-plus mr-1"></i>加入餐车
                    </button>
                </div>
            </div>
        `;
        menuItemsDiv.appendChild(itemDiv);
    });
}

// --- 购物车操作 ---
function addToCart(id, name, price, quantityInputId) {
    const quantityInput = document.getElementById(quantityInputId);
    const quantity = parseInt(quantityInput.value);

    if (isNaN(quantity) || quantity <= 0) {
        showModal('请输入有效的数量!', true);
        return;
    }
    const itemName = (typeof name === 'string' || name instanceof String) ? name : '未知菜品';


    const existingItem = cart.find(cartItem => cartItem.id === id);
    if (existingItem) {
        existingItem.quantity += quantity;
    } else {
        cart.push({ id, name: itemName, price, quantity, special_requests: '' }); 
    }
    renderCart();
    quantityInput.value = "1";
    showModal(`${itemName} 已添加到餐车!`);
}

function removeFromCart(itemId) {
    cart = cart.filter(item => item.id !== itemId);
    renderCart();
}

function updateCartQuantity(itemId, change) {
    const item = cart.find(cartItem => cartItem.id === itemId);
    if (item) {
        item.quantity += change;
        if (item.quantity <= 0) {
            removeFromCart(itemId);
        } else {
            renderCart();
        }
    }
}

function updateSpecialRequest(itemId, value) {
    const item = cart.find(cartItem => cartItem.id === itemId);
    if (item) {
        item.special_requests = value;
    }
}


function renderCart() {
    cartItemsDiv.innerHTML = '';
    let total = 0;
    if (cart.length === 0) {
        cartItemsDiv.innerHTML = '<p class="text-gray-500 p-2">餐车是空的。</p>';
    } else {
        cart.forEach(item => {
            if (!item || typeof item.name === 'undefined' || typeof item.price === 'undefined') {
                console.warn('购物车中检测到无效的菜品数据，已跳过渲染:', item);
                return; 
            }
            const itemTotal = item.price * item.quantity;
            total += itemTotal;
            const cartItemDiv = document.createElement('div');
            cartItemDiv.className = 'cart-item';
            cartItemDiv.innerHTML = `
                <div class="flex-grow">
                    <span class="cart-item-name">${item.name}</span>
                    <span class="cart-item-details block">(¥${parseFloat(item.price).toFixed(2)} x ${item.quantity})</span>
                    <input type="text" value="${item.special_requests || ''}" oninput="updateSpecialRequest(${item.id}, this.value)" placeholder="特殊要求,如不放辣" class="mt-1 text-xs p-1 border rounded w-full">
                </div>
                <div class="text-right ml-2 flex-shrink-0">
                    <span class="cart-item-subtotal block mb-1">¥${itemTotal.toFixed(2)}</span>
                    <div class="cart-item-actions">
                        <button class="button-secondary text-xs py-1 px-1.5 rounded mr-1" onclick="updateCartQuantity(${item.id}, -1)" aria-label="减少数量"><i class="fas fa-minus"></i></button>
                        <button class="button-danger text-xs py-1 px-1.5 rounded" onclick="removeFromCart(${item.id})" aria-label="移除商品"><i class="fas fa-trash-alt"></i></button>
                    </div>
                </div>
            `;
            cartItemsDiv.appendChild(cartItemDiv);
        });
    }
    cartTotalSpan.textContent = total.toFixed(2);
}

function clearCart() {
    cart = [];
    renderCart();
    showModal('餐车已清空。');
}

// --- 下单操作 ---
async function placeOrder() {
    if (!currentUser) {
        showModal('请先登录再下单！', true);
        openAuthModal('loginModal');
        return;
    }
    if (cart.length === 0) {
        showModal('餐车是空的，请先添加菜品!', true);
        return;
    }

    const orderData = {
        items: cart.map(item => ({
            menu_item_id: item.id,
            quantity: item.quantity,
            special_requests: item.special_requests || null 
        })),
        payment_method: paymentMethodSelect.value,
        delivery_address: deliveryAddressInput.value.trim() || null,
        notes: orderNotesTextarea.value.trim() || null
    };

    try {
        placeOrderBtn.disabled = true;
        placeOrderBtn.textContent = '正在下单...';

        const response = await fetchWithAuth(`${API_BASE_URL}/orders`, { 
            method: 'POST',
            body: JSON.stringify(orderData),
        });
        const result = await response.json();

        if (response.ok) {
            showModal(`订单创建成功! 订单ID: ${result.order_id}, 总金额: ¥${parseFloat(result.total_amount).toFixed(2)}`);
            clearCart();
            deliveryAddressInput.value = '';
            orderNotesTextarea.value = '';
            fetchMyOrders(1); 
        } else {
            if (response.status === 401) { 
                 showModal(`下单失败: ${result.message || '请重新登录'}`, true);
                 handleLogout(); 
            } else {
                 showModal(`下单失败: ${result.error || '未知错误'}`, true);
            }
        }
    } catch (error) {
        console.error('下单失败:', error);
        showModal(`下单请求失败: ${error.message}`, true);
    } finally {
        placeOrderBtn.disabled = false;
        placeOrderBtn.textContent = '确认下单';
    }
}

// --- 获取用户历史订单 ---
async function fetchMyOrders(page = 1) {
    if (!currentUser) return;
    myOrdersCurrentPage = page; 

    try {
        const response = await fetchWithAuth(`${API_BASE_URL}/orders/my?page=${page}&per_page=${MY_ORDERS_PER_PAGE}`);
        if (response.ok) {
            const data = await response.json();
            renderMyOrders(data.orders);
            renderMyOrdersPagination(data.total_orders, data.page, data.per_page);
        } else if (response.status === 401) {
            showModal('会话已过期或无效，请重新登录查看订单。', true);
            handleLogout();
        } 
        else {
            const errorResult = await response.json();
            myOrdersListDiv.innerHTML = `<p class="text-red-500">获取历史订单失败: ${errorResult.error || response.statusText}</p>`;
            myOrdersPaginationDiv.innerHTML = '';
        }
    } catch (error) {
        console.error('获取历史订单请求失败:', error);
        myOrdersListDiv.innerHTML = `<p class="text-red-500">获取历史订单请求失败，请检查网络。</p>`;
        myOrdersPaginationDiv.innerHTML = '';
    }
}

function renderMyOrders(orders) {
    myOrdersListDiv.innerHTML = '';
    if (!orders || orders.length === 0) {
        myOrdersListDiv.innerHTML = '<p class="text-gray-500">您还没有历史订单。</p>';
        return;
    }
    orders.forEach(order => {
        if (!order || typeof order.id === 'undefined' || typeof order.total_amount === 'undefined') {
            console.warn('检测到无效的历史订单数据，已跳过渲染:', order);
            return; 
        }
        const orderDiv = document.createElement('div');
        orderDiv.className = 'order-history-item p-4 border rounded-md shadow-sm hover:shadow-md transition-shadow'; 
        const orderTime = new Date(order.order_time).toLocaleString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit' });
        const statusClass = `order-status-${order.status}`;

        orderDiv.innerHTML = `
            <div class="flex justify-between items-center mb-2">
                <span class="order-id text-lg font-semibold text-purple-700">订单号: #${order.id}</span>
                <span class="text-sm text-gray-500">${orderTime}</span>
            </div>
            <div class="mb-1">总金额: <span class="font-semibold">¥${parseFloat(order.total_amount).toFixed(2)}</span></div>
            <div class="mb-1">订单状态: <span class="font-semibold ${statusClass}">${translateOrderStatus(order.status)}</span></div>
            <div class="text-sm">支付状态: <span class="font-medium">${translatePaymentStatus(order.payment_status)}</span></div>
            <button class="button text-xs py-1 px-2 mt-2" onclick="fetchAndShowOrderDetails(${order.id})">查看详情</button>
        `;
        myOrdersListDiv.appendChild(orderDiv);
    });
}

function renderMyOrdersPagination(totalOrders, currentPage, perPage) {
    myOrdersPaginationDiv.innerHTML = '';
    const totalPages = Math.ceil(totalOrders / perPage);

    if (totalPages <= 1) return; 

    const maxVisibleButtons = 5; 
    let startPage = Math.max(1, currentPage - Math.floor(maxVisibleButtons / 2));
    let endPage = Math.min(totalPages, startPage + maxVisibleButtons - 1);
    
    if (endPage - startPage + 1 < maxVisibleButtons && startPage > 1) {
        startPage = Math.max(1, endPage - maxVisibleButtons + 1);
    }

    if (currentPage > 1) {
        const prevButton = document.createElement('button');
        prevButton.textContent = '上一页';
        prevButton.className = 'button button-secondary text-sm py-1 px-3';
        prevButton.onclick = () => fetchMyOrders(currentPage - 1);
        myOrdersPaginationDiv.appendChild(prevButton);
    }

    for (let i = startPage; i <= endPage; i++) {
        const pageButton = document.createElement('button');
        pageButton.textContent = i;
        pageButton.className = `button text-sm py-1 px-3 ${i === currentPage ? 'bg-purple-700 text-white' : 'button-secondary'}`;
        if (i !== currentPage) {
            pageButton.onclick = () => fetchMyOrders(i);
        } else {
            pageButton.disabled = true;
        }
        myOrdersPaginationDiv.appendChild(pageButton);
    }
    
    if (currentPage < totalPages) {
        const nextButton = document.createElement('button');
        nextButton.textContent = '下一页';
        nextButton.className = 'button button-secondary text-sm py-1 px-3';
        nextButton.onclick = () => fetchMyOrders(currentPage + 1);
        myOrdersPaginationDiv.appendChild(nextButton);
    }
}

function translateOrderStatus(status) {
    const map = {
        'pending': '待处理', 'confirmed': '已确认', 'preparing': '备餐中',
        'completed': '已完成', 'cancelled': '已取消', 'delivered': '已送达'
    };
    return map[status] || status;
}
function translatePaymentStatus(status) {
    const map = { 'unpaid': '未支付', 'paid': '已支付', 'failed': '支付失败', 'refunded': '已退款' };
    return map[status] || status;
}

async function fetchAndShowOrderDetails(orderId) {
    try {
        const response = await fetchWithAuth(`${API_BASE_URL}/orders/${orderId}`);
        if (response.ok) {
            const orderDetails = await response.json();
            if (!orderDetails || typeof orderDetails.id === 'undefined') {
                showModal('无法获取有效的订单详情数据。', true);
                return;
            }
            let detailsHtml = `<h4 class="text-xl font-semibold mb-3 text-purple-600">订单 #${orderDetails.id} 详情</h4>`;
            detailsHtml += `<p><strong>下单时间:</strong> ${new Date(orderDetails.order_time).toLocaleString('zh-CN')}</p>`;
            detailsHtml += `<p><strong>总金额:</strong> ¥${parseFloat(orderDetails.total_amount).toFixed(2)}</p>`;
            detailsHtml += `<p><strong>订单状态:</strong> ${translateOrderStatus(orderDetails.status)}</p>`;
            detailsHtml += `<p><strong>支付状态:</strong> ${translatePaymentStatus(orderDetails.payment_status)}</p>`;
            if (orderDetails.user_full_name) {
                detailsHtml += `<p><strong>顾客:</strong> ${orderDetails.user_full_name} (${orderDetails.user_username || 'N/A'})</p>`;
            } else {
                detailsHtml += `<p><strong>顾客:</strong> ${orderDetails.customer_name || '匿名用户'}</p>`;
            }
            if(orderDetails.delivery_address) detailsHtml += `<p><strong>配送地址:</strong> ${orderDetails.delivery_address}</p>`;
            if(orderDetails.notes) detailsHtml += `<p><strong>备注:</strong> ${orderDetails.notes}</p>`;

            detailsHtml += `<h5 class="text-md font-semibold mt-3 mb-1">订单项目:</h5><ul class="list-disc pl-5 text-sm">`;
            if (orderDetails.items && Array.isArray(orderDetails.items)) {
                orderDetails.items.forEach(item => {
                    if (!item || typeof item.item_name === 'undefined' || typeof item.quantity === 'undefined' || typeof item.unit_price === 'undefined' || typeof item.subtotal === 'undefined') {
                        console.warn('订单详情中检测到无效的订单项数据:', item);
                        detailsHtml += `<li>无效的订单项数据</li>`;
                        return; 
                    }
                    detailsHtml += `<li>${item.item_name} x ${item.quantity} (单价: ¥${parseFloat(item.unit_price).toFixed(2)}) - 小计: ¥${parseFloat(item.subtotal).toFixed(2)}`;
                    if(item.special_requests) detailsHtml += `<br><small class="text-gray-600">特殊要求: ${item.special_requests}</small>`;
                    detailsHtml += `</li>`;
                });
            } else {
                detailsHtml += `<li>无订单项目信息</li>`;
            }
            detailsHtml += `</ul>`;
            
            modalMessageText.innerHTML = detailsHtml; 
            modalMessageText.style.textAlign = 'left'; 
            modalMessageText.style.color = 'inherit'; 
            showModal(''); 
        } else {
            const errorResult = await response.json();
            showModal(`获取订单详情失败: ${errorResult.error || response.statusText}`, true);
        }
    } catch (error) {
        showModal(`获取订单详情请求失败: ${error.message}`, true);
    }
}


// --- LLM建议 ---
async function fetchRecipeSuggestion() {
    if (cart.length === 0) {
        llmSuggestionDiv.innerHTML = '<p class="text-orange-600">请先选择一些菜品，我才能给您更好的搭配建议哦！</p>';
        return;
    }
    const currentDishNames = cart.map(item => item.name);
    const preferences = userPreferencesInput.value.trim();
    const requestData = { current_dishes: currentDishNames, preferences: preferences };

    try {
        getSuggestionBtn.disabled = true;
        getSuggestionBtn.textContent = '正在思考...';
        llmSuggestionDiv.innerHTML = '<p class="text-gray-500">正在向大厨顾问请求建议...</p>';

        const response = await fetchWithAuth(`${API_BASE_URL}/recipe-suggestion`, { 
            method: 'POST',
            body: JSON.stringify(requestData),
        });
        const result = await response.json();

        if (response.ok) {
            llmSuggestionDiv.innerHTML = `<p class="font-semibold mb-2 text-purple-700">大厨搭配建议:</p><div class="text-gray-700">${result.suggestion}</div>`;
        } else {
             if (response.status === 401) { 
                 showModal(`获取建议失败: ${result.message || '请先登录'}`, true);
            } else {
                 showModal(`获取建议失败: ${result.error || '未知错误'}`, true);
            }
            llmSuggestionDiv.innerHTML = `<p class="text-red-500">获取建议失败: ${result.error || '服务暂时不可用'}</p>`;
        }
    } catch (error) {
        console.error('获取建议失败:', error);
        llmSuggestionDiv.innerHTML = `<p class="text-red-500">获取建议请求失败: ${error.message}</p>`;
        showModal(`获取建议请求失败: ${error.message}`, true);
    } finally {
        getSuggestionBtn.disabled = false;
        getSuggestionBtn.textContent = '获取建议';
    }
}


// --- 事件监听器 ---
document.addEventListener('DOMContentLoaded', () => {
    fetchUserProfileOnLoad(); 
    fetchMenu();
    renderCart();

    if (loginForm) loginForm.addEventListener('submit', handleLogin);
    if (registerForm) registerForm.addEventListener('submit', handleRegister);
    
    if (showRegisterModalLink) showRegisterModalLink.addEventListener('click', (e) => {
        e.preventDefault();
        closeAuthModal('loginModal');
        openAuthModal('registerModal');
    });
    if (showLoginModalLink) showLoginModalLink.addEventListener('click', (e) => {
        e.preventDefault();
        closeAuthModal('registerModal');
        openAuthModal('loginModal');
    });
    
    [messageModal, loginModal, registerModal].forEach(modal => {
        if (modal) {
            modal.addEventListener('click', (event) => {
                if (event.target === modal) { 
                    if(modal.id === 'messageModal') closeModal();
                    else closeAuthModal(modal.id);
                }
            });
        }
    });

    if (placeOrderBtn) placeOrderBtn.addEventListener('click', placeOrder);
    if (clearCartBtn) clearCartBtn.addEventListener('click', clearCart);
    if (getSuggestionBtn) getSuggestionBtn.addEventListener('click', fetchRecipeSuggestion);

    // 处理URL hash跳转到登录
    if(window.location.hash === '#login' && !getAuthToken()){
        openAuthModal('loginModal');
    }
});

// 使函数在全局可访问，以便HTML中的onclick可以调用
window.addToCart = addToCart;
window.removeFromCart = removeFromCart;
window.updateCartQuantity = updateCartQuantity;
window.updateSpecialRequest = updateSpecialRequest;
window.fetchAndShowOrderDetails = fetchAndShowOrderDetails;
window.closeModal = closeModal; // 确保通用关闭按钮可用
window.closeAuthModal = closeAuthModal; // 确保认证模态框关闭按钮可用
