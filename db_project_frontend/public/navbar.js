document.addEventListener('DOMContentLoaded', () => {
    updateNavbar();
});

function randomNumber(min, max){
    min = Math.ceil(min);
    max = Math.floor(max);
    return Math.floor(Math.random() * (max - min + 1)) + min;
}

function checkSignIn(){
    const userId = sessionStorage.getItem('user_id');
    if(!userId) return false;
    else return true;
}

function updateNavbar() {
    // 檢查 sessionStorage 是否有使用者 ID
    const userId = sessionStorage.getItem('user_id');
    const authLink = document.getElementById('auth_link') || document.querySelector('a[href="sign_in.html"]');

    if (!authLink) return;

    if (userId) {
        // 已登入狀態
        authLink.textContent = "Profile";     
        authLink.href = "user.html";         
        
        authLink.classList.remove('bg-gray-600', 'hover:bg-gray-500');
        authLink.classList.add('bg-blue-950', 'hover:bg-blue-900');
    } else {
        // 未登入狀態 
        authLink.textContent = "Sign In";
        authLink.href = "sign_in.html";
        
        authLink.classList.remove('bg-blue-950', 'hover:bg-blue-900');
        authLink.classList.add('bg-gray-600', 'hover:bg-gray-500');
    }
}

function showAlert(type, message) {
    alert_box.textContent = message;

    //success green ; failed red
    if (type === 'success') alert_box.className = "px-4 py-2 rounded-xl shadow-lg text-sm font-medium bg-green-600 text-white";
    else alert_box.className = "px-4 py-2 rounded-xl shadow-lg text-sm font-medium bg-red-600 text-white";

    // 顯示
    alert_wrapper.classList.remove("opacity-0", "-translate-y-4");
    alert_wrapper.classList.add("opacity-100", "translate-y-0");

    // 幾秒後自動關閉
    setTimeout(() => {
        alert_wrapper.classList.add("opacity-0", "-translate-y-4");
        alert_wrapper.classList.remove("opacity-100", "translate-y-0");
    }, 3000);
}