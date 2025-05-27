// frontend/admin.js
const API_BASE_URL = 'http://localhost:5000/api'; // 后端API基础URL

// --- DOM 元素获取 ---
const adminContentArea = document.getElementById('adminContentArea');
const mainContentTitle = document.getElementById('mainContentTitle');
const adminUsernameSpan = document.getElementById('adminUsername');
const adminLogoutBtn = document.getElementById('adminLogoutBtn');

// 导航链接
const navDashboard = document.getElementById('navDashboard');
const navMenuManagement = document.getElementById('navMenuManagement');
const navOrderManagement = document.getElementById('navOrderManagement');
const navUserManagement = document.getElementById('navUserManagement');
const navCategoryManagement = document.getElementById('navCategoryManagement');
const navLinks = document.querySelectorAll('.nav-link');

// 模态框
const adminModal = document.getElementById('adminModal');
const adminModalTitle = document.getElementById('adminModalTitle');
const adminModalBody = document.getElementById('adminModalBody');
const adminModalFooter = document.getElementById('adminModalFooter');
const closeAdminModalBtn = document.getElementById('closeAdminModalBtn');

// --- 全局状态 ---
let currentAdmin = null;
let allMenuItemsCache = []; 
let allCategoriesCache = []; 
let currentEditingItemId = null;
let ordersCurrentPage = 1; // MODIFIED: 移到全局，方便各函数访问
const ORDERS_PER_PAGE_ADMIN = 10;

// --- 辅助函数 ---
function showAdminModal(title, bodyContent, footerButtons = [{ text: '关闭', class: 'button-secondary', action: closeAdminModal }]) {
    adminModalTitle.textContent = title;
    if (typeof bodyContent === 'string') {
        adminModalBody.innerHTML = bodyContent;
    } else {
        adminModalBody.innerHTML = ''; 
        adminModalBody.appendChild(bodyContent); 
    }
    
    adminModalFooter.innerHTML = '';
    footerButtons.forEach(btnInfo => {
        const button = document.createElement('button');
        button.textContent = btnInfo.text;
        button.className = `button ${btnInfo.class || 'button-primary'} py-2 px-4`;
        button.addEventListener('click', btnInfo.action);
        adminModalFooter.appendChild(button);
    });
    adminModal.style.display = 'flex';
}

function closeAdminModal() {
    adminModal.style.display = 'none';
    adminModalBody.innerHTML = ''; 
    adminModalFooter.innerHTML = '';
    currentEditingItemId = null; 
}

function getAuthToken() {
    return localStorage.getItem('accessToken');
}

async function fetchWithAuth(url, options = {}) {
    const token = getAuthToken();
    const headers = {
        'Content-Type': 'application/json',
        ...options.headers,
    };
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }
    const response = await fetch(url, { ...options, headers });

    if (response.status === 401) { 
        localStorage.removeItem('accessToken');
        localStorage.removeItem('currentUser');
        currentAdmin = null;
        showAdminModal('会话已过期', '您的登录已过期，请重新登录。', [{ text: '去登录', class: 'button-primary', action: () => window.location.href = 'index.html#login' }]); // MODIFIED: 跳转到登录页并带上hash
        throw new Error('Unauthorized'); 
    }
    return response;
}

function setActiveNavLink(activeLink) {
    navLinks.forEach(link => link.classList.remove('active-nav-link', 'bg-purple-700'));
    if (activeLink) { // MODIFIED: 增加 activeLink 是否存在的检查
        activeLink.classList.add('active-nav-link', 'bg-purple-700');
    }
}

// --- 认证与初始化 ---
async function checkAdminAuthAndInit() {
    const token = getAuthToken();
    const storedUser = localStorage.getItem('currentUser');

    if (!token || !storedUser) {
        window.location.href = 'index.html#login'; 
        return;
    }

    try {
        currentAdmin = JSON.parse(storedUser);
        if (!currentAdmin || currentAdmin.role !== 'admin') { // MODIFIED: 增加 currentAdmin 是否存在的检查
            alert('访问拒绝：您不是管理员。');
            localStorage.removeItem('accessToken'); // 清理无效凭证
            localStorage.removeItem('currentUser');
            window.location.href = 'index.html';
            return;
        }
        adminUsernameSpan.textContent = currentAdmin.full_name || currentAdmin.username;
        
        await fetchWithAuth(`${API_BASE_URL}/admin/orders?page=1&per_page=1`); 

        loadDashboard();
    } catch (error) {
        console.error("Admin auth check failed:", error);
        if (error.message !== 'Unauthorized') { 
             showAdminModal('初始化失败', `无法验证管理员身份: ${error.message}`, [{ text: '去登录', class: 'button-primary', action: () => window.location.href = 'index.html#login' }]);
        }
    }
}

function adminLogout() {
    localStorage.removeItem('accessToken');
    localStorage.removeItem('currentUser');
    currentAdmin = null;
    window.location.href = 'index.html';
}

// --- 视图加载函数 ---
function loadDashboard() {
    mainContentTitle.textContent = '仪表盘';
    setActiveNavLink(navDashboard);
    adminContentArea.innerHTML = `
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            <div class="bg-white p-6 rounded-lg shadow hover:shadow-lg transition-shadow">
                <h2 class="text-xl font-semibold text-purple-600 mb-2">总订单数</h2>
                <p id="dashboardTotalOrders" class="text-3xl font-bold text-slate-700">加载中...</p>
            </div>
            <div class="bg-white p-6 rounded-lg shadow hover:shadow-lg transition-shadow">
                <h2 class="text-xl font-semibold text-purple-600 mb-2">总菜品数</h2>
                <p id="dashboardTotalMenuItems" class="text-3xl font-bold text-slate-700">加载中...</p>
            </div>
            <div class="bg-white p-6 rounded-lg shadow hover:shadow-lg transition-shadow">
                <h2 class="text-xl font-semibold text-purple-600 mb-2">待处理订单</h2>
                <p id="dashboardPendingOrders" class="text-3xl font-bold text-slate-700">加载中...</p>
            </div>
        </div>
    `;
    fetchDashboardData();
}

async function fetchDashboardData() {
    try {
        // 并行获取数据以提高效率
        const [ordersRes, menuRes, pendingOrdersRes] = await Promise.all([
            fetchWithAuth(`${API_BASE_URL}/admin/orders?page=1&per_page=1`), // 获取总订单数
            fetchWithAuth(`${API_BASE_URL}/menu?include_unavailable=true`), // 获取所有菜品，包括不可用的
            fetchWithAuth(`${API_BASE_URL}/admin/orders?status=pending&page=1&per_page=1`) // 获取待处理订单数
        ]);

        if (ordersRes.ok) {
            const ordersData = await ordersRes.json();
            if (document.getElementById('dashboardTotalOrders')) {
                document.getElementById('dashboardTotalOrders').textContent = ordersData.total_orders || 0;
            }
        } else {
             if (document.getElementById('dashboardTotalOrders')) document.getElementById('dashboardTotalOrders').textContent = '错误';
        }

        if (menuRes.ok) {
            const menuData = await menuRes.json();
            if (document.getElementById('dashboardTotalMenuItems')) {
                document.getElementById('dashboardTotalMenuItems').textContent = menuData.length || 0;
            }
        } else {
            if (document.getElementById('dashboardTotalMenuItems')) document.getElementById('dashboardTotalMenuItems').textContent = '错误';
        }

        if (pendingOrdersRes.ok) {
            const pendingOrdersData = await pendingOrdersRes.json();
            if (document.getElementById('dashboardPendingOrders')) {
                document.getElementById('dashboardPendingOrders').textContent = pendingOrdersData.total_orders || 0;
            }
        } else {
            if (document.getElementById('dashboardPendingOrders')) document.getElementById('dashboardPendingOrders').textContent = '错误';
        }

    } catch (error) {
        console.error("获取仪表盘数据失败:", error);
        if (document.getElementById('dashboardTotalOrders')) document.getElementById('dashboardTotalOrders').textContent = '错误';
        if (document.getElementById('dashboardTotalMenuItems')) document.getElementById('dashboardTotalMenuItems').textContent = '错误';
        if (document.getElementById('dashboardPendingOrders')) document.getElementById('dashboardPendingOrders').textContent = '错误';
    }
}


// == 菜品管理 ==
async function loadMenuManagement() {
    mainContentTitle.textContent = '菜品管理';
    setActiveNavLink(navMenuManagement);
    adminContentArea.innerHTML = `
        <div class="bg-white p-6 rounded-lg shadow">
            <div class="flex justify-between items-center mb-6">
                <h2 class="text-xl font-semibold text-slate-700">所有菜品</h2>
                <button id="addMenuItemBtn" class="button button-primary py-2 px-4 flex items-center">
                    <i class="fas fa-plus mr-2"></i>添加新菜品
                </button>
            </div>
            <div id="menuManagementTableContainer" class="overflow-x-auto">
                <p class="text-slate-500">正在加载菜品列表...</p>
            </div>
        </div>
    `;
    const addMenuItemBtn = document.getElementById('addMenuItemBtn');
    if (addMenuItemBtn) { // MODIFIED: 增加元素存在性检查
        addMenuItemBtn.addEventListener('click', () => showAddEditMenuItemModal());
    }
    await fetchAllCategories(); // MODIFIED: 确保分类在获取菜品前加载
    fetchAllMenuItemsAdmin();
}

async function fetchAllCategories() {
    try {
        const response = await fetchWithAuth(`${API_BASE_URL}/categories`);
        if (!response.ok) throw new Error(`获取分类失败: ${response.statusText}`);
        allCategoriesCache = await response.json();
    } catch (error) {
        console.error(error.message);
        showAdminModal('错误', `无法加载菜品分类: ${error.message}`);
        allCategoriesCache = []; // 确保是空数组，避免后续逻辑出错
    }
}


async function fetchAllMenuItemsAdmin() {
    const container = document.getElementById('menuManagementTableContainer'); // MODIFIED: 获取容器
    try {
        // MODIFIED: 明确传递 include_unavailable=true
        const response = await fetchWithAuth(`${API_BASE_URL}/menu?include_unavailable=true`); 
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        allMenuItemsCache = await response.json();
        renderMenuManagementTable(allMenuItemsCache);
    } catch (error) {
        console.error('获取所有菜品失败 (admin):', error);
        if (container) { // MODIFIED: 检查容器是否存在
            container.innerHTML = `<p class="text-red-500">加载菜品列表失败: ${error.message}</p>`;
        }
    }
}

function renderMenuManagementTable(menuItems) {
    const container = document.getElementById('menuManagementTableContainer');
    if (!container) return;

    if (!menuItems || menuItems.length === 0) {
        container.innerHTML = '<p class="text-slate-500">暂无菜品。</p>';
        return;
    }

    let tableHtml = `
        <table class="min-w-full divide-y divide-slate-200">
            <thead class="bg-slate-50">
                <tr>
                    <th class="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">ID</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">图片</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">名称</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">分类</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">价格</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">状态</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">操作</th>
                </tr>
            </thead>
            <tbody class="bg-white divide-y divide-slate-200">
    `;

    menuItems.forEach(item => {
        // MODIFIED: 增加对 item 及其属性的防御性检查
        const itemId = item && typeof item.id !== 'undefined' ? item.id : 'N/A';
        const itemName = item && item.name ? item.name : '未知菜品';
        const itemImageUrl = item && item.image_url ? item.image_url : 'https://placehold.co/100x75/E2E8F0/A0AEC0?text=无图';
        const itemCategoryName = item && item.category_name ? item.category_name : '未分类';
        const itemPrice = item && typeof item.price === 'number' ? parseFloat(item.price).toFixed(2) : 'N/A';
        const itemIsAvailable = item ? item.is_available : false;


        tableHtml += `
            <tr>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-slate-500">${itemId}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-slate-500">
                    <img src="${itemImageUrl}" alt="${itemName}" class="w-16 h-12 object-cover rounded" onerror="this.onerror=null;this.src='https://placehold.co/100x75/E2E8F0/A0AEC0?text=图片错误';">
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-slate-900">${itemName}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-slate-500">${itemCategoryName}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-slate-500">¥${itemPrice}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm">
                    <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${itemIsAvailable ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}">
                        ${itemIsAvailable ? '上架中' : '已下架'}
                    </span>
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm font-medium space-x-2">
                    <button class="text-purple-600 hover:text-purple-900" onclick="showAddEditMenuItemModal(${itemId})"><i class="fas fa-edit"></i> 编辑</button>
                    <button class="text-red-600 hover:text-red-900" onclick="confirmDeleteMenuItem(${itemId})"><i class="fas fa-trash-alt"></i> 删除</button>
                </td>
            </tr>
        `;
    });

    tableHtml += `</tbody></table>`;
    container.innerHTML = tableHtml;
}

function showAddEditMenuItemModal(itemId = null) {
    currentEditingItemId = itemId;
    const isEditMode = itemId !== null;
    const item = isEditMode ? allMenuItemsCache.find(m => m && m.id === itemId) : {}; // MODIFIED: 增加 item 存在性检查
    
    if (isEditMode && (!item || typeof item.id === 'undefined')) { // MODIFIED: 更严格的检查
        showAdminModal('错误', '找不到要编辑的菜品或菜品数据无效。');
        return;
    }

    const formId = "menuItemForm";
    const modalBodyContent = document.createElement('form');
    modalBodyContent.id = formId;
    modalBodyContent.className = "space-y-4";
    
    let categoryOptions = '<option value="">选择分类</option>';
    if (allCategoriesCache && allCategoriesCache.length > 0) { // MODIFIED: 检查 allCategoriesCache 是否存在
        allCategoriesCache.forEach(cat => {
            // MODIFIED: 确保 item 和 item.category_id 存在才进行比较
            const selected = item && typeof item.category_id !== 'undefined' && item.category_id === cat.id ? 'selected' : '';
            categoryOptions += `<option value="${cat.id}" ${selected}>${cat.name}</option>`;
        });
    } else {
        categoryOptions = '<option value="">暂无分类，请先在“分类管理”中添加</option>';
    }

    modalBodyContent.innerHTML = `
        <div>
            <label for="itemName" class="block text-sm font-medium text-slate-700">菜品名称:</label>
            <input type="text" id="itemName" name="name" value="${item?.name || ''}" required class="mt-1 block w-full input-field">
        </div>
        <div>
            <label for="itemDescription" class="block text-sm font-medium text-slate-700">描述:</label>
            <textarea id="itemDescription" name="description" rows="3" class="mt-1 block w-full input-field">${item?.description || ''}</textarea>
        </div>
        <div>
            <label for="itemPrice" class="block text-sm font-medium text-slate-700">价格 (元):</label>
            <input type="number" id="itemPrice" name="price" value="${typeof item?.price === 'number' ? item.price : ''}" required step="0.01" min="0" class="mt-1 block w-full input-field">
        </div>
        <div>
            <label for="itemCategoryId" class="block text-sm font-medium text-slate-700">分类:</label>
            <select id="itemCategoryId" name="category_id" required class="mt-1 block w-full input-field">
                ${categoryOptions}
            </select>
        </div>
        <div>
            <label for="itemImageUrl" class="block text-sm font-medium text-slate-700">图片URL (可选):</label>
            <input type="url" id="itemImageUrl" name="image_url" value="${item?.image_url || ''}" class="mt-1 block w-full input-field">
        </div>
        <div>
            <label for="itemIsAvailable" class="flex items-center">
                <input type="checkbox" id="itemIsAvailable" name="is_available" class="h-4 w-4 text-purple-600 border-slate-300 rounded focus:ring-purple-500" ${item?.is_available !== false ? 'checked' : ''}>
                <span class="ml-2 text-sm text-slate-700">是否上架</span>
            </label>
        </div>
    `;
    
    const modalTitle = isEditMode ? '编辑菜品' : '添加新菜品';
    const footerButtons = [
        { text: '取消', class: 'button-secondary', action: closeAdminModal },
        { text: '保存', class: 'button-primary', action: () => handleSaveMenuItem(formId) }
    ];
    showAdminModal(modalTitle, modalBodyContent, footerButtons);
}

async function handleSaveMenuItem(formId) {
    const form = document.getElementById(formId);
    if (!form) return;

    const formData = new FormData(form);
    const data = Object.fromEntries(formData.entries());
    
    data.price = parseFloat(data.price);
    data.category_id = parseInt(data.category_id);
    data.is_available = form.elements['is_available'] ? form.elements['is_available'].checked : true; 

    if (isNaN(data.price) || data.price < 0) {
        // 保持模态框打开，让用户修正
        showAdminModal('错误', '请输入有效的价格。', [
            { text: '返回编辑', class: 'button-secondary', action: () => showAddEditMenuItemModal(currentEditingItemId) }
        ]);
        return;
    }
    if (isNaN(data.category_id) || !data.category_id) { // MODIFIED: 检查 category_id 是否有效
         showAdminModal('错误', '请选择一个有效的分类。', [
            { text: '返回编辑', class: 'button-secondary', action: () => showAddEditMenuItemModal(currentEditingItemId) }
        ]);
        return;
    }

    const url = currentEditingItemId 
        ? `${API_BASE_URL}/admin/menu/${currentEditingItemId}` 
        : `${API_BASE_URL}/admin/menu`;
    const method = currentEditingItemId ? 'PUT' : 'POST';

    // 在提交前禁用保存按钮，防止重复提交
    const saveButton = adminModalFooter.querySelector('.button-primary');
    if(saveButton) saveButton.disabled = true;


    try {
        const response = await fetchWithAuth(url, {
            method: method,
            body: JSON.stringify(data)
        });
        const result = await response.json();
        if (response.ok) {
            showAdminModal('成功', `菜品已${currentEditingItemId ? '更新' : '添加'}！`, [
                 { text: '关闭', class: 'button-primary', action: closeAdminModal }
            ]);
            fetchAllMenuItemsAdmin(); 
        } else {
            showAdminModal('保存失败', `${result.error || result.message || '未知错误'}`, [
                 { text: '返回编辑', class: 'button-secondary', action: () => showAddEditMenuItemModal(currentEditingItemId) } 
            ]);
        }
    } catch (error) {
        console.error('保存菜品失败:', error);
        showAdminModal('请求失败', `保存菜品时发生错误: ${error.message}`,[
            { text: '返回编辑', class: 'button-secondary', action: () => showAddEditMenuItemModal(currentEditingItemId) }
        ]);
    } finally {
        if(saveButton) saveButton.disabled = false; // 重新启用按钮
    }
}

function confirmDeleteMenuItem(itemId) {
    const item = allMenuItemsCache.find(m => m && m.id === itemId); // MODIFIED: 增加 item 存在性检查
    if (!item || typeof item.id === 'undefined') { // MODIFIED: 更严格的检查
        showAdminModal('错误', '找不到要删除的菜品或菜品数据无效。');
        return;
    }
    showAdminModal(
        '确认删除', 
        `您确定要删除菜品 "${item.name || '未知菜品'}" 吗？此操作无法撤销。`,
        [
            { text: '取消', class: 'button-secondary', action: closeAdminModal },
            { text: '删除', class: 'button-danger', action: () => handleDeleteMenuItem(itemId) }
        ]
    );
}

async function handleDeleteMenuItem(itemId) {
    try {
        const response = await fetchWithAuth(`${API_BASE_URL}/admin/menu/${itemId}`, { // 假设后端有此API
            method: 'DELETE'
        });
        if (response.ok) {
            showAdminModal('成功', '菜品已删除！', [{ text: '关闭', class: 'button-primary', action: closeAdminModal }]);
            fetchAllMenuItemsAdmin(); 
        } else {
            const result = await response.json().catch(() => ({})); 
            showAdminModal('删除失败', `${result.error || result.message || '无法删除菜品，请检查服务器日志。'}`, [{ text: '关闭', class: 'button-primary', action: closeAdminModal }]);
        }
    } catch (error) {
        console.error('删除菜品失败:', error);
        showAdminModal('请求失败', `删除菜品时发生错误: ${error.message}`, [{ text: '关闭', class: 'button-primary', action: closeAdminModal }]);
    }
    // MODIFIED: 不论成功失败，删除操作后通常关闭确认框，由新的提示框接管。
}


// == 订单管理 ==
async function loadOrderManagement(page = 1) {
    mainContentTitle.textContent = '订单管理';
    setActiveNavLink(navOrderManagement);
    ordersCurrentPage = page;

    adminContentArea.innerHTML = `
        <div class="bg-white p-6 rounded-lg shadow">
            <div class="flex flex-wrap justify-between items-center mb-6 gap-4">
                <h2 class="text-xl font-semibold text-slate-700">所有订单</h2>
                <div class="flex items-center gap-x-4">
                    <label for="orderStatusFilter" class="text-sm whitespace-nowrap">状态筛选:</label>
                    <select id="orderStatusFilter" class="input-field py-1.5 px-2 text-sm w-auto rounded-md border-slate-300 focus:border-purple-500 focus:ring-purple-500">
                        <option value="">全部</option>
                        <option value="pending">待处理</option>
                        <option value="confirmed">已确认</option>
                        <option value="preparing">备餐中</option>
                        <option value="delivered">已送达</option>
                        <option value="completed">已完成</option>
                        <option value="cancelled">已取消</option>
                    </select>
                </div>
            </div>
            <div id="orderManagementTableContainer" class="overflow-x-auto">
                <p class="text-slate-500">正在加载订单列表...</p>
            </div>
            <div id="orderPaginationContainer" class="mt-6 text-center"></div>
        </div>
    `;
    
    const statusFilter = document.getElementById('orderStatusFilter');
    if (statusFilter) { // MODIFIED: 增加元素存在性检查
        statusFilter.addEventListener('change', () => fetchAllOrdersAdmin(1, statusFilter.value));
    }
    
    fetchAllOrdersAdmin(page, statusFilter ? statusFilter.value : ''); // MODIFIED: 传递空字符串如果过滤器不存在
}

async function fetchAllOrdersAdmin(page = 1, status = '') {
    const container = document.getElementById('orderManagementTableContainer');
    const paginationContainer = document.getElementById('orderPaginationContainer'); // MODIFIED: 获取分页容器

    try {
        let url = `${API_BASE_URL}/admin/orders?page=${page}&per_page=${ORDERS_PER_PAGE_ADMIN}`;
        if (status) {
            url += `&status=${status}`;
        }
        const response = await fetchWithAuth(url);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        const data = await response.json();
        renderOrderManagementTable(data.orders);
        renderOrderPagination(data.total_orders, data.page, data.per_page);
    } catch (error) {
        console.error('获取所有订单失败 (admin):', error);
        if(container) {
             container.innerHTML = `<p class="text-red-500">加载订单列表失败: ${error.message}</p>`;
        }
        if (paginationContainer) { // MODIFIED: 错误时清空分页
            paginationContainer.innerHTML = '';
        }
    }
}

function renderOrderManagementTable(orders) {
    const container = document.getElementById('orderManagementTableContainer');
    if (!container) return;

    if (!orders || orders.length === 0) {
        container.innerHTML = '<p class="text-slate-500">暂无订单符合当前筛选条件。</p>'; // MODIFIED: 提示更具体
        return;
    }

    let tableHtml = `
        <table class="min-w-full divide-y divide-slate-200">
            <thead class="bg-slate-50">
                <tr>
                    <th class="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">订单ID</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">顾客</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">时间</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">总金额</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">状态</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">操作</th>
                </tr>
            </thead>
            <tbody class="bg-white divide-y divide-slate-200">
    `;

    orders.forEach(order => {
        // MODIFIED: 增加对 order 及其属性的防御性检查
        const orderId = order && typeof order.id !== 'undefined' ? order.id : 'N/A';
        const customerName = order && (order.customer_name || order.user_username) ? (order.customer_name || order.user_username) : '匿名用户';
        const orderTime = order && order.order_time ? new Date(order.order_time).toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : 'N/A';
        const totalAmount = order && typeof order.total_amount === 'number' ? parseFloat(order.total_amount).toFixed(2) : 'N/A';
        const currentStatus = order && order.status ? order.status : 'unknown';
        
        tableHtml += `
            <tr>
                <td class="px-4 py-3 whitespace-nowrap text-sm text-slate-500">#${orderId}</td>
                <td class="px-4 py-3 whitespace-nowrap text-sm text-slate-900">${customerName}</td>
                <td class="px-4 py-3 whitespace-nowrap text-sm text-slate-500">${orderTime}</td>
                <td class="px-4 py-3 whitespace-nowrap text-sm text-slate-500">¥${totalAmount}</td>
                <td class="px-4 py-3 whitespace-nowrap text-sm">
                    <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${statusClassMapping(currentStatus).bg} ${statusClassMapping(currentStatus).text}">
                        ${translateOrderStatus(currentStatus)}
                    </span>
                </td>
                <td class="px-4 py-3 whitespace-nowrap text-sm font-medium space-x-2">
                    <button class="text-blue-600 hover:text-blue-900" onclick="showOrderDetailsModal(${orderId})"><i class="fas fa-eye"></i> 查看</button>
                    <button class="text-purple-600 hover:text-purple-900" onclick="showUpdateOrderStatusModal(${orderId}, '${currentStatus}')"><i class="fas fa-edit"></i> 改状态</button>
                </td>
            </tr>
        `;
    });
    tableHtml += `</tbody></table>`;
    container.innerHTML = tableHtml;
}

function statusClassMapping(status) {
    const map = {
        'pending': { bg: 'bg-yellow-100', text: 'text-yellow-800' },
        'confirmed': { bg: 'bg-blue-100', text: 'text-blue-800' },
        'preparing': { bg: 'bg-indigo-100', text: 'text-indigo-800' },
        'delivered': { bg: 'bg-teal-100', text: 'text-teal-800' },
        'completed': { bg: 'bg-green-100', text: 'text-green-800' },
        'cancelled': { bg: 'bg-red-100', text: 'text-red-800' }
    };
    return map[status] || {bg: 'bg-slate-100', text: 'text-slate-800'}; // 默认样式
}

function translateOrderStatus(status) { 
    const map = {
        'pending': '待处理', 'confirmed': '已确认', 'preparing': '备餐中',
        'completed': '已完成', 'cancelled': '已取消', 'delivered': '已送达', 'unknown': '未知状态'
    };
    return map[status] || status;
}
function translatePaymentStatus(status) { 
    const map = { 'unpaid': '未支付', 'paid': '已支付', 'failed': '支付失败', 'refunded': '已退款', 'unknown': '未知状态' };
    return map[status] || status;
}


function renderOrderPagination(totalOrders, currentPage, perPage) {
    const container = document.getElementById('orderPaginationContainer');
    if (!container) return;
    container.innerHTML = '';
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
        prevButton.innerHTML = `<i class="fas fa-chevron-left mr-1"></i> 上一页`; // MODIFIED: 图标和文字间距
        prevButton.className = 'button button-secondary text-sm py-1.5 px-3';
        prevButton.onclick = () => {
            const statusFilterElement = document.getElementById('orderStatusFilter');
            fetchAllOrdersAdmin(currentPage - 1, statusFilterElement ? statusFilterElement.value : '');
        };
        container.appendChild(prevButton);
    }

    for (let i = startPage; i <= endPage; i++) {
        const pageButton = document.createElement('button');
        pageButton.textContent = i;
        pageButton.className = `button text-sm py-1.5 px-3 mx-1 ${i === currentPage ? 'bg-purple-700 text-white cursor-default' : 'button-secondary'}`; // MODIFIED: 当前页样式
        if (i !== currentPage) {
            pageButton.onclick = () => {
                 const statusFilterElement = document.getElementById('orderStatusFilter');
                 fetchAllOrdersAdmin(i, statusFilterElement ? statusFilterElement.value : '');
            };
        } else {
            pageButton.disabled = true;
        }
        container.appendChild(pageButton);
    }
    
    if (currentPage < totalPages) {
        const nextButton = document.createElement('button');
        nextButton.innerHTML = `下一页 <i class="fas fa-chevron-right ml-1"></i>`; // MODIFIED: 图标和文字间距
        nextButton.className = 'button button-secondary text-sm py-1.5 px-3';
        nextButton.onclick = () => {
            const statusFilterElement = document.getElementById('orderStatusFilter');
            fetchAllOrdersAdmin(currentPage + 1, statusFilterElement ? statusFilterElement.value : '');
        };
        container.appendChild(nextButton);
    }
}

async function showOrderDetailsModal(orderId) {
    if (typeof orderId === 'undefined' || orderId === null) { // MODIFIED: 检查 orderId
        showAdminModal('错误', '无效的订单ID。');
        return;
    }
    try {
        const response = await fetchWithAuth(`${API_BASE_URL}/orders/${orderId}`); 
        if (!response.ok) {
            const errorResult = await response.json().catch(() => ({ error: `HTTP error ${response.status}` }));
            throw new Error(errorResult.error || `获取订单详情失败: ${response.statusText}`);
        }
        const orderDetails = await response.json();
        
        // MODIFIED: 增加对 orderDetails 及其属性的防御性检查
        if (!orderDetails || typeof orderDetails.id === 'undefined') {
            showAdminModal('错误', '无法获取有效的订单详情数据。');
            return;
        }

        let detailsHtml = `<div class="text-sm space-y-1 text-left">`; // MODIFIED: 文本左对齐
        detailsHtml += `<p><strong>订单号:</strong> #${orderDetails.id}</p>`;
        detailsHtml += `<p><strong>顾客:</strong> ${orderDetails.customer_name || orderDetails.user_full_name || orderDetails.user_username || 'N/A'}</p>`;
        if (orderDetails.user_email) detailsHtml += `<p><strong>邮箱:</strong> ${orderDetails.user_email}</p>`;
        if (orderDetails.user_phone) detailsHtml += `<p><strong>电话:</strong> ${orderDetails.user_phone}</p>`;
        detailsHtml += `<p><strong>下单时间:</strong> ${orderDetails.order_time ? new Date(orderDetails.order_time).toLocaleString('zh-CN') : 'N/A'}</p>`;
        detailsHtml += `<p><strong>总金额:</strong> ¥${typeof orderDetails.total_amount === 'number' ? parseFloat(orderDetails.total_amount).toFixed(2) : 'N/A'}</p>`;
        detailsHtml += `<p><strong>订单状态:</strong> ${translateOrderStatus(orderDetails.status || 'unknown')}</p>`;
        detailsHtml += `<p><strong>支付状态:</strong> ${translatePaymentStatus(orderDetails.payment_status || 'unknown')}</p>`;
        if(orderDetails.delivery_address) detailsHtml += `<p><strong>配送地址:</strong> ${orderDetails.delivery_address}</p>`;
        if(orderDetails.notes) detailsHtml += `<p><strong>备注:</strong> ${orderDetails.notes}</p>`;

        detailsHtml += `<h5 class="text-md font-semibold mt-3 mb-1 pt-2 border-t">订单项目:</h5><ul class="list-disc pl-5 text-sm space-y-1">`;
        if (orderDetails.items && Array.isArray(orderDetails.items) && orderDetails.items.length > 0) {
            orderDetails.items.forEach(item => {
                // MODIFIED: 对 item 内部属性进行检查
                const itemName = item && item.item_name ? item.item_name : '未知菜品';
                const quantity = item && typeof item.quantity === 'number' ? item.quantity : 'N/A';
                const unitPrice = item && typeof item.unit_price === 'number' ? parseFloat(item.unit_price).toFixed(2) : 'N/A';
                const subtotal = item && typeof item.subtotal === 'number' ? parseFloat(item.subtotal).toFixed(2) : 'N/A';
                detailsHtml += `<li>${itemName} x ${quantity} (¥${unitPrice}) = ¥${subtotal}`;
                if(item && item.special_requests) detailsHtml += `<br><small class="text-slate-600">特殊要求: ${item.special_requests}</small>`;
                detailsHtml += `</li>`;
            });
        } else {
            detailsHtml += `<li>无订单项目信息或项目列表为空</li>`;
        }
        detailsHtml += `</ul></div>`;
        
        showAdminModal(`订单 #${orderDetails.id} 详情`, detailsHtml, [{ text: '关闭', class: 'button-primary', action: closeAdminModal }]);
    } catch (error) {
        showAdminModal('错误', `无法加载订单详情: ${error.message}`);
    }
}

function showUpdateOrderStatusModal(orderId, currentStatus) {
    if (typeof orderId === 'undefined' || orderId === null) { // MODIFIED: 检查 orderId
        showAdminModal('错误', '无效的订单ID。');
        return;
    }
    const formId = "updateOrderStatusForm";
    const modalBodyContent = document.createElement('form');
    modalBodyContent.id = formId;
    modalBodyContent.className = "space-y-4";
    
    const statuses = ['pending', 'confirmed', 'preparing', 'delivered', 'completed', 'cancelled'];
    let statusOptions = statuses.map(s => 
        `<option value="${s}" ${s === currentStatus ? 'selected' : ''}>${translateOrderStatus(s)}</option>`
    ).join('');

    modalBodyContent.innerHTML = `
        <p>订单ID: #${orderId}</p>
        <div>
            <label for="newOrderStatus" class="block text-sm font-medium text-slate-700">新状态:</label>
            <select id="newOrderStatus" name="status" class="mt-1 block w-full input-field">
                ${statusOptions}
            </select>
        </div>
    `;
    
    showAdminModal(
        `更新订单 #${orderId} 状态`,
        modalBodyContent,
        [
            { text: '取消', class: 'button-secondary', action: closeAdminModal },
            { text: '更新状态', class: 'button-primary', action: () => handleUpdateOrderStatus(orderId, formId) }
        ]
    );
}

async function handleUpdateOrderStatus(orderId, formId) {
    const form = document.getElementById(formId);
    if (!form) return;
    const newStatus = form.elements['status'].value;

    const updateButton = adminModalFooter.querySelector('.button-primary');
    if(updateButton) updateButton.disabled = true;


    try {
        const response = await fetchWithAuth(`${API_BASE_URL}/admin/orders/${orderId}/status`, {
            method: 'PUT',
            body: JSON.stringify({ status: newStatus })
        });
        const result = await response.json();
        if (response.ok) {
            showAdminModal('成功', `订单 #${orderId} 状态已更新为 ${translateOrderStatus(newStatus)}！`, [
                { text: '关闭', class: 'button-primary', action: closeAdminModal }
            ]);
            const statusFilterElement = document.getElementById('orderStatusFilter');
            fetchAllOrdersAdmin(ordersCurrentPage, statusFilterElement ? statusFilterElement.value : ''); 
        } else {
            showAdminModal('更新失败', `${result.error || result.message || '未知错误'}`, [
                 { text: '关闭', class: 'button-secondary', action: closeAdminModal }
            ]);
        }
    } catch (error) {
        showAdminModal('请求失败', `更新订单状态时发生错误: ${error.message}`, [
            { text: '关闭', class: 'button-secondary', action: closeAdminModal }
        ]);
    } finally {
        if(updateButton) updateButton.disabled = false;
    }
}


// == 用户管理 (占位) ==
function loadUserManagement() {
    mainContentTitle.textContent = '用户管理';
    setActiveNavLink(navUserManagement);
    adminContentArea.innerHTML = `
        <div class="bg-white p-6 rounded-lg shadow">
            <h2 class="text-xl font-semibold text-slate-700 mb-4">所有用户</h2>
            <p class="text-slate-500">用户管理功能正在开发中...</p>
            </div>
    `;
}

// == 分类管理 (占位) ==
function loadCategoryManagement() {
    mainContentTitle.textContent = '分类管理';
    setActiveNavLink(navCategoryManagement);
    adminContentArea.innerHTML = `
        <div class="bg-white p-6 rounded-lg shadow">
            <h2 class="text-xl font-semibold text-slate-700 mb-4">菜品分类</h2>
            <p class="text-slate-500">分类管理功能正在开发中...</p>
            <p class="mt-2 text-sm text-slate-600">提示：菜品分类数据通常在“菜品管理”中添加或编辑菜品时选择。如需独立的分类增删改查功能，将在此处实现。</p>
            </div>
    `;
}


// --- 事件监听器 ---
document.addEventListener('DOMContentLoaded', () => {
    checkAdminAuthAndInit();

    if (navDashboard) navDashboard.addEventListener('click', (e) => { e.preventDefault(); loadDashboard(); });
    if (navMenuManagement) navMenuManagement.addEventListener('click', (e) => { e.preventDefault(); loadMenuManagement(); });
    if (navOrderManagement) navOrderManagement.addEventListener('click', (e) => { e.preventDefault(); loadOrderManagement(); });
    if (navUserManagement) navUserManagement.addEventListener('click', (e) => { e.preventDefault(); loadUserManagement(); });
    if (navCategoryManagement) navCategoryManagement.addEventListener('click', (e) => { e.preventDefault(); loadCategoryManagement(); });
    
    if (adminLogoutBtn) adminLogoutBtn.addEventListener('click', adminLogout);
    if (closeAdminModalBtn) closeAdminModalBtn.addEventListener('click', closeAdminModal);
    if (adminModal) {
        adminModal.addEventListener('click', (event) => { 
            if (event.target === adminModal) {
                closeAdminModal();
            }
        });
    }
});

// 全局可访问的函数 (用于HTML内联onclick)
window.showAddEditMenuItemModal = showAddEditMenuItemModal;
window.confirmDeleteMenuItem = confirmDeleteMenuItem;
window.showOrderDetailsModal = showOrderDetailsModal;
window.showUpdateOrderStatusModal = showUpdateOrderStatusModal;
// handleDeleteMenuItem 和 handleSaveMenuItem 不直接暴露到全局，由确认框或表单提交间接调用
